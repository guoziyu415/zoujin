"""Three-layer ending (B-9 slice + B-17 full version; backend-design 2.9, api-contract 2.8, 3.13, contract section 5).

- **When to enter** (`due`): only in the last act (the act without exits). Enter once the beat the deadline watches
  (`clock.deadline.watchBeat`) has a result, or the deadline has been settled. In the triggering commit (`enter`):
  settle this act up to its close (set pieces on the closing beat ignore where the player is and count as the ending
  set piece) → `classify` → set-piece positions `staging` → the game becomes `ended` → insert a task with `kind: "ending"` → the
  push starts with `ending_started`.
- **Staging, ranking by impact, attribution, templates, validation**: all deterministic, all here, never left to the
  model. B-17: ranking adds promises, mutual aid, memories and relationship changes; `player.relationships` is computed
  by code from the undeleted memories; the world ending may be generated for this game (`world.variant`), and both its
  claims (`claims`) and the character endings' claims must agree with the final state; characters whose memories were
  deleted don't get "remembers you"; citations can't rest only on the event that made a voided promise.
- **Model check** (B-17, backend-design 2.9 step 4, prompt `ending-check`): after the deterministic validation
  passes, the model checks whether the three layers hang together; if not, rewrite with the field names, counted as one
  try like any other failure. If the check itself times out, errors or fails the Schema, it doesn't block, and this
  ending is used.
- **Generation** (`run_ending`): Claude writes the epilogue, your ending and the character endings (prompt `ending`,
  structured output), each sentence citing this game's events; event IDs are written as `e<seq>` in the request (the
  same situation gives the same request, so replay keys match) and mapped back to real IDs on receipt. At most two
  calls (timeout, error, Schema failure and validation failure each count as one; the second carries the failed rule
  names and fields), then the template (S-065, ux-design 11.4).
- **Saving**: in one transaction store the ending, clear this game's player utterances and plan texts (S-035), fill in
  `playthrough_metrics`, mark the task done and push `ending_ready`, then NOTIFY.
- Logs and Trace hold only IDs, rule names, counts, durations and costs, never ending text or player utterances
  (data-design section 8).

3 層のエンディング（B-9 スライス版 + B-17 完全版。backend-design 2.9、api-contract 2.8、3.13、契約第 5 節）。

- **いつ入るか**（`due`）：最後の幕（exits のない幕）でだけ。期限が見張るビート（`clock.deadline.watchBeat`）に結果が
  出たか、期限を精算済みなら入る。きっかけとなったコミットの中で（`enter`）：この幕を閉じるところまで精算する（幕を
  閉じるビートの演出はプレイヤーの居場所を問わず、エンディングの演出に含める）→ `classify` → 演出の立ち位置
  `staging` → ゲームを `ended` にする → `kind: "ending"` のタスクを 1 つ入れる → プッシュの先頭は `ending_started`。
- **立ち位置、影響度の順位、署名、テンプレート、検証**：どれも決定的で、すべてここで行い、モデルには任せない。B-17：
  順位に約束、助け合い、記憶、関係の変化を加える。`player.relationships` は削除されていない記憶からコードが計算する。
  世界のエンディングはこのゲームで生成したもの（`world.variant`）でもよく、その主張（`claims`）と登場人物の
  エンディングの主張はどちらも最終状態と一致しなければならない。記憶を削除された登場人物には「あなたを覚えている」を
  書かない。引用は無効になった約束を成立させたイベントだけに頼れない。
- **モデルの検査**（B-17、backend-design 2.9 第 4 ステップ、プロンプト `ending-check`）：決定的な検証を通ったあと、
  3 層の間で話が通るかをモデルに見させる。通らなければフィールド名を付けて書き直させ、ほかの不合格と同じく 1 回と
  数える。検査そのものがタイムアウト、エラー、Schema 不合格のときは止めず、このエンディングをそのまま使う。
- **生成**（`run_ending`）：Claude がエピローグ、あなたのエンディング、登場人物のエンディングを書き
  （プロンプト `ending`、構造化出力）、各文はこのゲームのイベントを引用する。イベント ID はリクエストでは `e<seq>` と
  書き（同じ局面なら同じリクエストになり、リプレイのキーが一致する）、受け取ったら本当の ID に戻す。呼び出しは最大 2 回（タイムアウト、
  エラー、Schema 不合格、検証不合格はどれも 1 回と数える。2 回目は不合格の規則名とフィールドを付ける）、その後は
  テンプレートを使う（S-065、ux-design 11.4）。
- **保存**：同じトランザクションでエンディングを保存し、このゲームの発話とプランの文章を消し（S-035）、
  `playthrough_metrics` を補い、タスクを done にして `ending_ready` をプッシュし、NOTIFY する。
- ログと Trace には ID、規則名、回数、所要時間、費用だけを入れ、
  エンディングの文章や発話は入れない（data-design 第 8 節）。
"""

from __future__ import annotations

import asyncio
import copy
import logging
import re
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import jsonschema
from sqlalchemy import func, insert, select, update
from zoujin_backend.db import store
from zoujin_backend.db.events import recorded_at
from zoujin_backend.db.store import Run
from zoujin_backend.db.tables import endings, memory_items, playthrough_metrics, playthroughs, turns, utterances
from zoujin_backend.models.prompts import PROMPTS
from zoujin_backend.models.text import BadOutput, ModelCallFailed, RateLimited, TextResult, model_and_version, spec
from zoujin_backend.narrator.memory import initial_trust, item_json, relation
from zoujin_backend.narrator.pipeline import Spend
from zoujin_backend.narrator.rules import VERBATIM, has_pii, lcs_len
from zoujin_backend.narrator.writer import SCHEMA_VERSION, Writer, has_exits
from zoujin_backend.projection import committed, player_spot
from zoujin_backend.world import Book
from zoujin_worldsim import OCCURRED, SimState, classify, flat, signature

if TYPE_CHECKING:
    from zoujin_backend.narrator.core import Narrator, Result, Task

log = logging.getLogger("zoujin.narrator")

Json = Any

KIND = "ending"
# B-17: whether the three layers hang together (backend-design 2.9 step 4).
# B-17：3 層の間で話が通るか（backend-design 2.9 第 4 ステップ）。
CHECK_KIND = "ending-check"
# One call + one rewrite (or one resend after a timeout), then the template (backend-design line 138).
# 呼び出し 1 回 + 書き直し（またはタイムアウト後の再送）1 回、その後はテンプレート（backend-design 第 138 行）。
MAX_CALLS = 2
# The 202's etaSeconds = 15 minus seconds already elapsed, at least 5 (api-contract 2.8; one Mac probe run p95 ≈ 10 s).
# 202 の etaSeconds = 15 から経過秒数を引いたもの、最小 5（api-contract 2.8。Mac のプローブ 1 回の p95 は約 10 秒）。
ETA_SECONDS = 15
ETA_MIN = 5

# The people in the set piece (the 『走れメロス』 slice; the state table is split by them, see the card's "do" item 2).
# 演出に出る人々（『走れメロス』のスライス。状態表はこの人々で分ける。カードの「やること」第 2 項を参照）。
MELOS = "char.melos"
KING = "char.king"
FRIEND = "char.selinuntius"  # listed even when not the hostage (S-053: present by default) / 人質でなくても載せる
# The crowd's front-row spot (「身を寄せる」 lands here, S-077 ⑤).
# 群衆の最前列の立ち位置（「身を寄せる」はここに来る、S-077 ⑤）。
CROWD_SPOTS = frozenset({"stake-front"})

# S-067: an execution is only told indirectly. If someone was executed in this game, the ending text must not contain
# these expressions (ux-design 11.2, v1.0.4); matched as substrings. 「磔」 itself isn't banned. Shared by the prompt
# and the validation.
# S-067：処刑は間接的にだけ伝える。このゲームで誰かが処刑されたら、エンディングの文章にこれらの言い方を入れてはいけない
# （ux-design 11.2、v1.0.4）。部分文字列で調べる。「磔」自体は禁じない。プロンプトと検証で共用する。
FORBIDDEN = (
    "処刑",
    "死",
    "殺",
    "最期",
    "亡くな",
    "命を落と",
    "息絶え",
    "絶命",
    "事切れ",
    "帰らぬ人",
    "磔にされ",
    "磔になっ",
)
# Character counts (ux-design 11.3) / 文字数（ux-design 11.3）
TITLE_MAX = 14
SUBTITLE_MAX = 26
CARD_LINE_MAX = 40
CARD_CONTRAST_MAX = 48
EPILOGUE = (3, 5)
SIDE = (0, 2)  # didForYou, youDid
YOURS = (1, 3)
CARD_LINES = 3

# B-17: for characters whose memories were deleted, the ending doesn't say "they remember you" (contract section 4,
# deletion semantics item 2); matched as substrings in their own ending and in sentences mentioning their name.
# B-17：記憶を削除された登場人物については、エンディングに「あなたを覚えている」を書かない（契約第 4 節、削除の意味の
# 第 2 項）。その人物自身のエンディングと、その名前に触れる文を部分文字列で調べる。
REMEMBER = ("覚えて", "憶えて", "覚えてい", "忘れなかった", "忘れていなかった", "記憶", "思い出")
VARIANT_ID = re.compile(r"gen\.[a-z0-9]+(?:-[a-z0-9]+)*")
# A generated world ending cites at least two events of this game (contract section 5).
# 生成した世界のエンディングはこのゲームのイベントを少なくとも 2 つ引用する（契約第 5 節）。
VARIANT_CITES = 2
# Weights for ranking by impact (B-17, backend-design 2.9 step 1): 1 each for the player's events involving them and
# for changedBeats where they participate; +1 for mutual aid (player for them, them for the player); 2 per promise
# with the player (not counting voided ones); 1 per undeleted memory; +1 per 10 points trust has moved from its start.
# 影響度の順位の重み（B-17、backend-design 2.9 第 1 ステップ）：プレイヤーのイベントでその人物に関わるもの、
# changedBeats でその人物が参加者のものはそれぞれ 1。助け合い（プレイヤーからその人物へ、その人物からプレイヤーへ）は
# さらに 1。プレイヤーとの約束（無効になったものは除く）は 2。削除されていない記憶は 1 件につき 1。信頼が初期値から
# 10 動くごとに 1。
W_AID, W_PROMISE, W_MEMORY, W_TRUST_STEP = 1, 2, 1, 10
# Max length of a field name returned by the model check (only passed back to the rewrite, never logged).
# モデルの検査が返すフィールド名の最大文字数（書き直しに渡すだけで、ログには入れない）。
CHECK_FIELD_MAX = 60

ALIAS = re.compile(r"e([1-9][0-9]*)")
# Placeholder for proper nouns (same as the eval's text.py: one private-use character).
# 固有名詞のプレースホルダー（評価の text.py と同じ：私用領域の 1 文字）。
PLACEHOLDER = ""
_KATAKANA_RUN = re.compile(r"[ァ-ヺー]{3,}")


# —— Entering the ending / エンディングに入る ——


def due(book: Book, state: SimState) -> str | None:
    """Whether to enter the ending after this commit: if so return the trigger (`story-closed` / `deadline`), else
    None. Only judged in the last act: the beat the deadline watches has a result, or the deadline has been settled.

    このコミットのあとエンディングに入るか：入るなら trigger（`story-closed` / `deadline`）を、
    入らなければ None を返す。
    最後の幕でだけ判定する：期限が見張るビートに結果が出たか、期限を精算済み。
    """
    return None if has_exits(book, state) else closed(book, state)


def closed(book: Book, state: SimState) -> str | None:
    """Regardless of the act: the beat the deadline watches has a result, or the deadline has been settled. Eval setup
    uses this to get the trigger after `curtain_fell` (when scenario mode pushes straight to the close, the player
    doesn't change acts along with it).

    幕を問わず：期限が見張るビートに結果が出たか、期限を精算済み。評価の setup は `curtain_fell` のあとでこれを使って
    trigger を取る（シナリオモードで一気に幕を閉じるところまで進めたとき、プレイヤーは幕を移っていない）。
    """
    watch = book.world["clock"]["deadline"].get("watchBeat")
    if watch in state["beats"]:
        return "story-closed" if state["beats"][watch] in OCCURRED else "deadline"
    if state["deadline"]:
        return "deadline"
    return None


def curtain_fell(book: Book, state: SimState) -> bool:
    """The `end` of the last act (the act without exits) is met: one of `onBeats` has a result, or `atLatest` has
    come. Used by eval setup: it only counts when a scenario is pushed all the way through; old cases whose checkpoint
    stops after beat.24 without changing acts don't count (they can still talk, data review #124).

    最後の幕（exits のない幕）の `end` が満たされた：`onBeats` のどれかに結果が出たか、`atLatest` に達した。評価の
    setup が使う：シナリオを最後まで一気に進めたときだけ数え、チェックポイントが beat.24 のあとで止まり幕を移っていない
    古いケースは数えない（従来どおり対話できる、データレビュー #124）。
    """
    last = next(a for a in book.world["acts"] if not a.get("exits"))
    end = last["end"]
    return any(b in state["beats"] for b in end.get("onBeats", [])) or state["t"] >= end["atLatest"]


def outcome_of(book: Book, state: SimState) -> tuple[str, bool]:
    """The world ending's classification; if none of the 5 holds, take the last one (a world model error; Trace
    records `ending-unclassified`).

    世界のエンディングの分類。5 種類のどれも成り立たなければ最後の種類を採る（世界モデルの誤りで、Trace に
    `ending-unclassified` を記録する）。
    """
    got = classify(book.world, state)
    if got is not None:
        return got, False
    return str(book.world["endings"]["world"][-1]["id"]), True


def label_of(book: Book, outcome: str) -> str:
    return str(next(x["label"] for x in book.world["endings"]["world"] if x["id"] == outcome))


def staging(book: Book, state: SimState, run: Run | None) -> Json:
    """Set-piece positions (api-contract 3.13): from the state after settling to the close, one "from where to where"
    state per person (the table in the card's "do" item 2).

    演出の立ち位置（api-contract 3.13）：幕を閉じるところまで精算したあとの状態から、一人ずつ「どこからどこへ」の
    状態を決める（カードの「やること」第 2 項の表）。
    """
    watch = book.world["clock"]["deadline"]["watchBeat"]
    place = str(book.beats[watch]["place"])
    vars_ = state["vars"]
    hostage = str(vars_.get("var.hostage.who", "none"))
    where = dict(state["locations"])
    where["player"] = str(vars_["var.player.location"])

    def scene_ref(p: str | None) -> str | None:
        got = book.places.get(p or "", {}).get("sceneRef")
        return None if got is None else str(got)

    order: list[str] = []
    if hostage != "none":
        order.append(hostage)
    for c in (FRIEND, MELOS, KING):
        if c in book.characters and c not in order:
            order.append(c)
    order += [
        c
        for c, p in state["locations"].items()
        if p == place and c not in order and c in book.characters and not book.characters[c].get("group")
    ]
    order.append("player")

    def state_of(c: str) -> str:
        if c == FRIEND and c != hostage:
            return "absent" if scene_ref(where.get(c)) != scene_ref(place) else "in-crowd"
        if where.get(c) != place:
            return "absent"
        if c == hostage:
            return "freed" if vars_.get("var.hostage.fate") == "released" else "on-cross"
        if c == MELOS:
            return "arriving" if vars_.get("var.melos.custody") == "returned" else "collapsed"
        if c == KING:
            return "approaching" if vars_.get("var.king.disposition") == "reformed" else "present"
        if c == "player":
            return "in-crowd" if player_spot(book, state, run) in CROWD_SPOTS else "present"
        return "in-crowd"

    return {"place": place, "characters": [{"id": c, "state": state_of(c)} for c in dict.fromkeys(order)]}


def enter(w: Writer, book: Book, trigger: str) -> Json:
    """In the triggering commit (with the game locked): settle to the close, classify, and compute the positions.
    Returns the `ending_started` message and the task's request. The game's status, the task row and the push order
    are written by the caller (`Narrator._commit`).

    きっかけとなったコミットの中で（このゲームをロックして）：幕を閉じるところまで精算し、分類し、立ち位置を計算する。
    `ending_started` メッセージとタスクの request を返す。ゲームの状態、タスクの行、プッシュの順は呼び出し側
    （`Narrator._commit`）が書く。
    """
    # Last act: borrow the act-closing guard to settle until end.onBeats has a result (or atLatest), then no further.
    # 最後の幕：幕を閉じるときの止め方を借りて end.onBeats に結果が出るまで（または atLatest まで）精算し、
    # その先はしない。
    guard, w.guard = w.guard, True
    try:
        w.settle(None, anywhere=True)
    finally:
        w.guard = guard
    outcome, unclassified = outcome_of(book, w.state)
    stage = staging(book, w.state, w.run)
    return {
        "message": {"type": "ending_started", "trigger": trigger, "staging": stage},
        "request": {"trigger": trigger, "staging": stage, "outcome": outcome, "unclassified": unclassified},
    }


# —— This game's events / このゲームのイベント ——


def kept(log_: Iterable[Mapping[str, Any]]) -> list[Json]:
    """The events the ending looks at: committed ones (rejected ones don't count), excluding forget.

    エンディングが見るイベント：コミット済みのもの（却下されたものは数えない）で、forget は除く。
    """
    return [dict(e) for e in log_ if committed(e) and e["type"] != "forget"]


def by_player(e: Mapping[str, Any]) -> bool:
    """A "player event": the actor is the player, or it came from a player turn or action (the same test as `_by_player`
    in the eval's checks.py).

    「プレイヤーのイベント」：actor がプレイヤー、またはプレイヤーのターンやアクションから来たもの（評価の checks.py の
    `_by_player` と同じ判定）。
    """
    return e.get("actor") == "player" or e.get("origin") in ("turn", "action")


def involves(e: Mapping[str, Any], c: str, state: SimState) -> bool:
    """The event involves this character: they are the actor or beneficiary, or a target of an effect (the character
    of learn, relocate or improv, a party to a promise, the from / to of an item changing hands).

    イベントがこの登場人物に関わる：その人物が actor か beneficiary、または効果の対象（learn、relocate、improv の
    character、約束の相手、物の受け渡しの from / to）。
    """
    if e.get("actor") == c or e.get("beneficiary") == c:
        return True
    for x in e.get("effects", []):
        op = x.get("op")
        if op in ("learn", "relocate", "improv") and x.get("character") == c:
            return True
        if op == "hold" and c in (x.get("from"), x.get("to")):
            return True
        if op == "promise":
            p = state["promises"].get(str(x.get("promiseId")), {})
            if c in (x.get("from"), x.get("to"), p.get("from"), p.get("to")):
                return True
    return False


def changed_beats(book: Book, state: SimState, events: Sequence[Mapping[str, Any]]) -> list[Json]:
    """Beats that differ from the original (result other than happened), each pointing back to events: the events that
    changed it first, then the system event that wrote the result.

    原作と違うビート（結果が happened でないもの）。それぞれイベントを指す：変えたイベントが先、次に結果を書いた
    システムイベント。
    """
    out: list[Json] = []
    for b in book.world["beats"]:
        to = state["beats"].get(b["id"])
        if to is None or to == "happened":
            continue
        caused = [
            e["eventId"]
            for e in events
            if e.get("origin") != "schedule"
            and any(x.get("op") == "beat" and x.get("beat") == b["id"] for x in e["effects"])
        ]
        caused += [
            e["eventId"]
            for e in events
            if e.get("origin") == "schedule"
            and any(x.get("op") == "beat" and x.get("beat") == b["id"] for x in e["effects"])
        ]
        out.append({"beat": b["id"], "to": to, "causedBy": list(dict.fromkeys(caused))})
    return out


def listed(book: Book) -> list[str]:
    """Which characters the ending page lists: `endings.characters`, or the talkable characters if it isn't set.

    エンディングのページに並べる登場人物：`endings.characters`。書かれていなければ talkable の登場人物。
    """
    got = book.world["endings"].get("characters")
    if got:
        return [str(c) for c in got]
    return [c for c, x in book.characters.items() if x.get("talkable")]


def aid(e: Mapping[str, Any], c: str) -> bool:
    """Mutual aid (D-012): what the player did for them (a player event with them as beneficiary), or what they did for
    the player (they are the actor and the player is the beneficiary).

    助け合い（D-012）：プレイヤーがその人物のためにしたこと（プレイヤーのイベントで beneficiary がその人物）、または
    その人物がプレイヤーのためにしたこと（actor がその人物で beneficiary がプレイヤー）。
    """
    return (by_player(e) and e.get("beneficiary") == c) or (e.get("actor") == c and e.get("beneficiary") == "player")


def with_player(state: SimState, c: str) -> list[Json]:
    """Promises between them and the player (not counting voided ones: once the player deletes that memory, neither the
    character nor the ending mentions it again, ux-design 10.1).

    その人物とプレイヤーの間の約束（無効になったものは数えない：プレイヤーがその記憶を削除したら、登場人物も
    エンディングも二度と触れない、ux-design 10.1）。
    """
    return [
        p
        for p in state["promises"].values()
        if p.get("status") != "voided" and {p.get("from"), p.get("to")} == {"player", c}
    ]


def rank(
    book: Book,
    state: SimState,
    events: Sequence[Mapping[str, Any]],
    changed: Sequence[Mapping[str, Any]],
    memories: Sequence[Mapping[str, Any]] = (),
    moved: Mapping[str, int] | None = None,
) -> dict[str, Json]:
    """Ranking by impact (B-17 weighting, weights in `W_*`): the number of player events involving them, the number of
    changedBeats where they participate, mutual aid, promises, undeleted memories, and how far trust moved from its
    start (`moved`: character → change in trust).
    Score 0 → `unchanged`, `rank: null`; the rest get 1, 2... from the highest score, ties in `endings.characters`
    order.

    影響度の順位（B-17 の重み付け、重みは `W_*`）：プレイヤーのイベントでその人物に関わる件数、changedBeats でその人物が
    参加者のビート数、助け合い、約束、削除されていない記憶、信頼が初期値からどれだけ動いたか（`moved`：登場人物 →
    信頼の変化）。0 点なら `unchanged`、`rank: null`。それ以外は点の高い順に 1、2… を付け、同点なら
    `endings.characters` の順。
    """
    mine = [e for e in events if by_player(e)]
    names = listed(book)
    score: dict[str, int] = {}
    for c in names:
        n = sum(1 for e in mine if involves(e, c, state))
        n += sum(1 for x in changed if c in book.beats[x["beat"]].get("participants", []))
        n += W_AID * sum(1 for e in events if aid(e, c))
        n += W_PROMISE * len(with_player(state, c))
        n += W_MEMORY * sum(1 for m in memories if m["character"] == c)
        n += abs((moved or {}).get(c, 0)) // W_TRUST_STEP
        score[c] = n
    ordered = sorted((c for c in names if score[c] > 0), key=lambda c: (-score[c], names.index(c)))
    out = {c: {"character": c, "rank": None, "unchanged": True, "score": 0} for c in names}
    for i, c in enumerate(ordered, 1):
        out[c] = {"character": c, "rank": i, "unchanged": False, "score": score[c]}
    return out


def original(book: Book, c: str) -> str:
    oe = book.characters[c].get("originalEnding") or {}
    return str(oe.get("text") or book.characters[c]["name"])


def executed(state: SimState) -> bool:
    v = state["vars"]
    return v.get("var.hostage.fate") == "executed" or v.get("var.player.custody") == "executed"


def fate_id(state: SimState, place: str) -> str:
    custody = state["vars"].get("var.player.custody")
    if custody in ("hostage", "executed"):
        return str(custody)
    return "witness" if state["vars"]["var.player.location"] == place else "elsewhere"


def last_scene(book: Book, state: SimState, stage: Mapping[str, Any]) -> Json:
    place = str(stage["place"])
    present = [x["id"] for x in stage["characters"] if x["id"] != "player" and x["state"] != "absent"]
    return {
        "place": place,
        "description": f"{book.places[place]['name']}、{book.label(state['t'])}",
        "present": present,
    }


def deciders(book: Book, state: SimState, outcome: str, events: Sequence[Mapping[str, Any]]) -> list[str]:
    """The events that set the variables used by the classification to their current values (the last setting event
    for each): the template sentences cite them. If there are none (the variables still have their initial values),
    take the last event.

    分類に使う変数を現在の値にしたイベント（それぞれ最後に設定したもの）：テンプレートの文がそれらを引用する。
    1 件もなければ（変数がまだ初期値なら）最後のイベントを使う。
    """
    rule = next(x for x in book.world["endings"]["world"] if x["id"] == outcome)
    out: list[str] = []
    for cond in rule.get("when", []):
        var = cond["var"]
        now = state["vars"].get(var)
        hit = next(
            (
                e["eventId"]
                for e in reversed(events)
                if any(x.get("op") == "set" and x.get("var") == var and x.get("value") == now for x in e["effects"])
            ),
            None,
        )
        if hit is not None and hit not in out:
            out.append(hit)
    if not out and events:
        out.append(events[-1]["eventId"])
    return out


# —— Templates (S-065; ux-design 11.4, contract 2.9.2) / テンプレート（S-065。ux-design 11.4、契約 2.9.2） ——


def template_of(book: Book, state: SimState, outcome: str) -> Json:
    values = flat(state)
    for t in book.world["endings"].get("templates", []):
        if t["outcome"] == outcome and (not t.get("when") or book.sim.holds(t["when"], values)):
            return t
    raise ValueError(
        f"The world model has no ending template for {outcome}"
        f" / 世界モデルに {outcome} のエンディングのテンプレートがない"
    )


@dataclass
class Ctx:
    """What one game's ending needs: the classification, positions, events, ranking, and the code-computed parts to
    merge into the ending.

    1 ゲームのエンディングに要るもの：分類、立ち位置、イベント、順位、エンディングに組み込むコードで計算した部分。
    """

    book: Book
    state: SimState
    pid: str
    role: str  # the role name chosen at the start / 開始時の役柄名
    trigger: str
    outcome: str
    stage: Json
    events: list[Json]
    changed: list[Json]
    ranks: dict[str, Json]
    # The player's utterances (for validation, never in the request).
    # プレイヤーの発話（検証用、リクエストには入れない）。
    said: list[str] = field(default_factory=list)
    # Undeleted memories (memoryId, character, kind, text, trustDelta) / 削除されていない記憶
    memories: list[Json] = field(default_factory=list)
    forgot: frozenset[str] = frozenset()  # characters with deleted memories / 記憶を削除された登場人物
    # Source events of deleted memories (their improvised facts are no longer mentioned).
    # 削除された記憶の出どころのイベント（その即興設定にはもう触れない）。
    dropped: frozenset[str] = frozenset()
    # Character → current trust (start + undeleted memories) / 登場人物 → 現在の信頼（初期値 + 削除されていない記憶）
    trust: dict[str, int] = field(default_factory=dict)
    # Character → how far trust moved from its start / 登場人物 → 信頼が初期値からどれだけ動いたか
    moved: dict[str, int] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return label_of(self.book, self.outcome)

    @property
    def ids(self) -> set[str]:
        return {e["eventId"] for e in self.events}

    @property
    def place(self) -> str:
        return str(self.stage["place"])

    @property
    def fate(self) -> str:
        return fate_id(self.state, self.place)


def make_ctx(
    book: Book,
    state: SimState,
    pid: str,
    role_id: str,
    request: Mapping[str, Any],
    log_: Sequence[Json],
    said: list[str],
    memories: Sequence[Mapping[str, Any]] = (),
) -> Ctx:
    """`memories`: all of this game's memory rows (including deleted ones, which have `deletedAt`).

    `memories`：このゲームのすべての記憶の行（削除されたものも含み、それには `deletedAt` がある）。
    """
    events = kept(log_)
    changed = changed_beats(book, state, events)
    alive = [dict(m) for m in memories if not m.get("deletedAt")]
    gone = [m for m in memories if m.get("deletedAt")]
    trust: dict[str, int] = {}
    moved: dict[str, int] = {}
    for c in listed(book):
        delta = sum(int(m.get("trustDelta", 0)) for m in alive if m["character"] == c)
        start = initial_trust(book, role_id, c)
        trust[c] = max(-100, min(100, start + delta))
        moved[c] = trust[c] - start
    return Ctx(
        book=book,
        state=state,
        pid=pid,
        role=str(book.roles[role_id]["name"]),
        trigger=str(request["trigger"]),
        outcome=str(request["outcome"]),
        stage=copy.deepcopy(request["staging"]),
        events=events,
        changed=changed,
        ranks=rank(book, state, events, changed, alive, moved),
        said=said,
        memories=alive,
        forgot=frozenset(str(m["character"]) for m in gone),
        dropped=frozenset(str(e) for m in gone for e in m.get("fromEvents", [])),
        trust=trust,
        moved=moved,
    )


def relationships(ctx: Ctx) -> list[Json]:
    """`player.relationships` (contract section 5): characters whose trust moved from its start or who have undeleted
    memories, in ranking order. No text (`line`) is written.

    `player.relationships`（契約第 5 節）：信頼が初期値から動いた、または削除されていない記憶のある登場人物を順位順に。
    文章（`line`）は書かない。
    """
    out: list[Json] = []
    order = sorted(ctx.ranks.values(), key=lambda r: (r["rank"] is None, r["rank"] or 0))
    for r in order:
        c = r["character"]
        ids = [str(m["memoryId"]) for m in ctx.memories if m["character"] == c]
        if not ids and not ctx.moved.get(c):
            continue
        out.append({"character": c, "trust": ctx.trust[c], "label": relation(ctx.trust[c])[0], "memoryIds": ids})
    return out


def from_template(ctx: Ctx) -> Json:
    """The template ending (without outer fields such as endingId and decidedAt; `assemble` adds them).

    テンプレートのエンディング（endingId や decidedAt などの外側のフィールドは付けず、`assemble` が補う）。
    """
    book, state = ctx.book, ctx.state
    t = template_of(book, state, ctx.outcome)
    cites = deciders(book, state, ctx.outcome, ctx.events)
    fates = book.world["endings"].get("fates", {})
    fate = t.get("fate") or fates.get(ctx.fate) or fates.get("elsewhere", "日没を迎えた。")
    title = str(t["title"]).replace("{role}", ctx.role)
    written = [x["character"] for x in t["lines"]]
    characters = []
    for c in listed(book):
        if c in written:
            line = next(x["line"] for x in t["lines"] if x["character"] == c)
            characters.append(
                {
                    "character": c,
                    "rank": written.index(c) + 1,
                    "unchanged": False,
                    "original": original(book, c),
                    "yours": [{"sentence": line, "cites": cites}],
                }
            )
        else:
            characters.append({"character": c, "rank": None, "unchanged": True, "original": original(book, c)})
    return {
        "world": world_part(ctx),
        "player": {
            "fate": {"id": ctx.fate, "label": fate, "causedBy": cites},
            "relationships": relationships(ctx),
            "title": {"text": title, "causedBy": cites},
            "epilogue": [{"sentence": t["subtitle"], "cites": cites}],
            "lastScene": last_scene(book, state, ctx.stage),
            "didForYou": [],
            "youDid": [],
        },
        "characters": characters,
        "card": {
            "title": title,
            "subtitle": t["subtitle"],
            "contrast": t["contrast"],
            "characterLines": [{"character": x["character"], "line": x["line"]} for x in t["lines"]][:CARD_LINES],
        },
    }


def world_part(ctx: Ctx) -> Json:
    return {
        "outcome": ctx.outcome,
        "title": ctx.label,
        "summary": ctx.label,
        "changedBeats": copy.deepcopy(ctx.changed),
        "finalVars": copy.deepcopy(ctx.state["vars"]),
        "signature": signature(ctx.book.world, ctx.state),
    }


# —— Request / リクエスト ——


def alias_map(events: Sequence[Mapping[str, Any]]) -> tuple[dict[str, str], dict[str, str]]:
    """Event ID ↔ the alias `e<seq>` in the request.

    イベント ID ↔ リクエストでの別名 `e<seq>`。
    """
    to_alias = {e["eventId"]: f"e{e['seq']}" for e in events}
    return to_alias, {v: k for k, v in to_alias.items()}


def request_of(ctx: Ctx, problems: Sequence[Mapping[str, str]] = ()) -> Json:
    """The request sent to the model (replay keys are computed from it): the classification, final state,
    changedBeats, characters (ranking, trust, whether memories were deleted), undeleted memories, promises (not voided
    ones), improvised facts (not those recorded by source events of deleted memories), this game's events, and the
    role name. Never the player's utterances (S-046). A rewrite carries the rule names and fields that failed last time
    (without text).

    モデルに送る request（リプレイのキーはこれで計算する）：分類、最終状態、changedBeats、登場人物（順位、信頼、記憶を
    削除されたか）、削除されていない記憶、約束（無効になったものは除く）、即興設定（削除された記憶の出どころの
    イベントが記録したものは除く）、このゲームのイベント、役柄名。発話は渡さない（S-046）。書き直しでは前回不合格だった
    規則名とフィールドを付ける（文章は付けない）。
    """
    book = ctx.book
    to_alias, _ = alias_map(ctx.events)
    req: Json = {
        "worldModelVersion": book.version,
        "outcome": {"id": ctx.outcome, "label": ctx.label},
        "finalVars": {v: ctx.state["vars"][v] for v in sorted(ctx.state["vars"])},
        "changedBeats": [
            {
                "beat": x["beat"],
                "to": x["to"],
                "summary": book.beats[x["beat"]]["summary"],
                "causedBy": [to_alias[i] for i in x["causedBy"] if i in to_alias],
            }
            for x in ctx.changed
        ],
        "characters": [
            {
                "character": c,
                "name": book.characters[c]["name"],
                "rank": r["rank"],
                "unchanged": r["unchanged"],
                "originalEnding": original(book, c),
                "relation": relation(ctx.trust[c])[0],
                "forgotYou": c in ctx.forgot,
            }
            for c, r in ctx.ranks.items()
        ],
        "memories": [{"character": m["character"], "kind": m["kind"], "text": m["text"]} for m in ctx.memories],
        "promises": [
            {
                "from": p.get("from"),
                "to": p.get("to"),
                "text": p.get("text"),
                "status": p.get("status"),
                "madeBy": to_alias.get(str(p.get("madeBy")), None),
            }
            for _, p in sorted(ctx.state["promises"].items())
            if p.get("status") != "voided"
        ],
        "improv": [
            {"character": f.get("character"), "statement": f.get("statement")}
            for _, f in sorted(ctx.state["runFacts"].items())
            if f.get("statement") and str(f.get("madeBy")) not in ctx.dropped
        ],
        "events": [
            {
                "eventId": to_alias[e["eventId"]],
                "t": e["t"],
                "actor": e["actor"],
                "type": e["type"],
                "summary": e["summary"],
                **({"beneficiary": e["beneficiary"]} if e.get("beneficiary") else {}),
                **beat_result(e),
            }
            for e in ctx.events
        ],
        "role": ctx.role,
        "place": {"id": ctx.place, "name": book.places[ctx.place]["name"], "fate": ctx.fate},
        "executed": executed(ctx.state),
    }
    if executed(ctx.state):
        req["forbidden"] = list(FORBIDDEN)
    if problems:
        req["problems"] = [dict(p) for p in problems]
    return req


def beat_result(e: Mapping[str, Any]) -> Json:
    """A beat's system event carries the beat and its result: for one that didn't happen as in the original
    (prevented etc.) the summary is still the original sentence, so the model needs this to tell them apart.

    ビートのシステムイベントにはビートと結果を付ける：原作どおりに起きなかったもの（prevented など）でも summary は
    原作の一文のままなので、モデルはこれで見分ける。
    """
    for x in e.get("effects", []):
        if x.get("op") == "beat":
            return {"beat": {"id": x["beat"], "to": x.get("to", "happened")}}
    return {}


# —— Validation (deterministic, the card's "do" item 5) / 検証（決定的、カードの「やること」第 5 項） ——


def proper_nouns(world: Mapping[str, Any]) -> list[str]:
    """Proper nouns in the world model (names of characters, places and items, katakana runs of 3+ characters in
    names, quoted original text), longest first. The same method as the eval's `zoujin_evals.text.proper_nouns`.

    世界モデルの固有名詞（登場人物、場所、物の名前、名前の中の 3 文字以上のカタカナ、引用した原文）。長いものが先。
    評価の `zoujin_evals.text.proper_nouns` と同じ取り方。
    """
    names: set[str] = set()
    for key in ("characters", "places", "items"):
        for x in world.get(key, []):
            if x.get("name"):
                names.add(x["name"])
                names.update(_KATAKANA_RUN.findall(x["name"]))
    names.update(q for q in _quotes(world) if q)
    return sorted(names, key=lambda s: (-len(s), s))


def _quotes(o: Any) -> Iterable[str]:
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "quote" and isinstance(v, str):
                yield v
            else:
                yield from _quotes(v)
    elif isinstance(o, list):
        for v in o:
            yield from _quotes(v)


def mask(text: str, nouns: Iterable[str]) -> str:
    for n in nouns:
        text = text.replace(n, PLACEHOLDER)
    return text


@dataclass(frozen=True)
class Problem:
    rule: str
    field: str

    def doc(self) -> dict[str, str]:
        return {"rule": self.rule, "field": self.field}


def _sentences(out: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    """Every sentence with cites in the model output: (field, {sentence or text, cites}).

    モデル出力のうち cites を持つ各文：（フィールド, {sentence または text, cites}）。
    """
    you = out["you"]
    rows: list[tuple[str, Mapping[str, Any]]] = [(f"epilogue[{i}]", x) for i, x in enumerate(out["epilogue"])]
    rows += [("you.title", you["title"]), ("you.fate", you["fate"])]
    rows += [(f"you.didForYou[{i}]", x) for i, x in enumerate(you["didForYou"])]
    rows += [(f"you.youDid[{i}]", x) for i, x in enumerate(you["youDid"])]
    for c in out["characters"]:
        rows += [(f"characters.{c['character']}[{i}]", x) for i, x in enumerate(c["yours"])]
    if out.get("variant"):
        rows.append(("variant", {"sentence": out["variant"]["summary"], "cites": out["variant"]["cites"]}))
    return rows


def texts_of(out: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Every piece of human-facing text in the model output: (field, text).

    モデル出力のうち人に見せる各文章：（フィールド, 文章）。
    """
    rows = [(f, str(x.get("sentence", x.get("text", "")))) for f, x in _sentences(out)]
    rows += [
        ("contrast.original", out["contrast"]["original"]),
        ("contrast.yours", out["contrast"]["yours"]),
        ("subtitle", out["subtitle"]),
        ("cardContrast", out["cardContrast"]),
    ]
    if out.get("variant"):
        rows.append(("variant.title", out["variant"]["title"]))
    return rows


def validate(ctx: Ctx, out: Mapping[str, Any]) -> list[Problem]:
    """Whether the model output (cites already mapped back to real IDs) passes deterministic validation: citations,
    counts, lengths, contrast.beat, no verbatim quoting of the player's words, personal information, and S-067's
    wording. Returns the failed rule names and fields (without text).

    モデル出力（cites は本当の ID に戻し済み）が決定的な検証を通るか：引用、件数、文字数、contrast.beat、発話を
    そのまま引用しない、個人情報、S-067 の言い方。不合格の規則名とフィールドを返す（文章は付けない）。
    """
    bad: list[Problem] = []
    ids = ctx.ids
    for f, x in _sentences(out):
        cites = list(x.get("cites", []))
        if not cites:
            bad.append(Problem("cite-empty", f))
        elif any(c not in ids for c in cites):
            bad.append(Problem("cite-unknown", f))
    if not EPILOGUE[0] <= len(out["epilogue"]) <= EPILOGUE[1]:
        bad.append(Problem("count", "epilogue"))
    for k in ("didForYou", "youDid"):
        if not SIDE[0] <= len(out["you"][k]) <= SIDE[1]:
            bad.append(Problem("count", f"you.{k}"))
    want = {c for c, r in ctx.ranks.items() if not r["unchanged"]}
    got = [c["character"] for c in out["characters"]]
    if set(got) != want or len(got) != len(set(got)):
        bad.append(Problem("characters", "characters"))
    for c in out["characters"]:
        if not YOURS[0] <= len(c["yours"]) <= YOURS[1]:
            bad.append(Problem("count", f"characters.{c['character']}"))
    if len(out["you"]["title"]["text"]) > TITLE_MAX:
        bad.append(Problem("length", "you.title"))
    if len(out["subtitle"]) > SUBTITLE_MAX:
        bad.append(Problem("length", "subtitle"))
    if len(out["cardContrast"]) > CARD_CONTRAST_MAX:
        bad.append(Problem("length", "cardContrast"))
    for c in card_lines(ctx, out):
        if len(c["line"]) > CARD_LINE_MAX:
            bad.append(Problem("length", f"characters.{c['character']}[0]"))
    beat = out["contrast"].get("beat")
    if beat is not None and beat not in {x["beat"] for x in ctx.changed}:
        bad.append(Problem("contrast-beat", "contrast.beat"))
    bad += validate_b17(ctx, out)
    nouns = proper_nouns(ctx.book.world)
    said = [mask(s, nouns) for s in ctx.said if s]
    forbid = executed(ctx.state)
    for f, text in texts_of(out):
        if any(lcs_len(mask(text, nouns), s) >= VERBATIM for s in said):
            bad.append(Problem("verbatim", f))
        if has_pii(text):
            bad.append(Problem("pii", f))
        if forbid and any(w in text for w in FORBIDDEN):
            bad.append(Problem("s067", f))
    return bad


def claims_hold(ctx: Ctx, claims: Sequence[Mapping[str, Any]]) -> bool:
    """The claims are all world model variables whose values equal the final state (contract section 5: `claims`
    agree with `finalVars`).

    主張はすべて世界モデルの変数で、値が最終状態と等しい（契約第 5 節：`claims` と `finalVars` が一致する）。
    """
    vars_ = ctx.state["vars"]
    return all(str(x.get("var")) in vars_ and vars_[str(x["var"])] == x.get("value") for x in claims)


def voided_made(ctx: Ctx) -> set[str]:
    """The events that made promises later voided.

    無効になった約束を成立させたイベント。
    """
    return {str(p["madeBy"]) for p in ctx.state["promises"].values() if p.get("status") == "voided" and p.get("madeBy")}


def validate_b17(ctx: Ctx, out: Mapping[str, Any]) -> list[Problem]:
    """The deterministic validation added by B-17: the generated world ending (id, claims, at least two events),
    character endings' claims, no "remembers you" for characters with deleted memories, and citations that don't rest
    only on events that made voided promises.

    B-17 で加えた決定的な検証：生成した世界のエンディング（id、主張、少なくとも 2 つのイベント）、登場人物の
    エンディングの主張、記憶を削除された登場人物に「あなたを覚えている」を書かない、無効になった約束を成立させた
    イベントだけに頼った引用をしない。
    """
    bad: list[Problem] = []
    v = out.get("variant")
    if v:
        if not VARIANT_ID.fullmatch(str(v["id"])):
            bad.append(Problem("variant-id", "variant.id"))
        if not v["claims"] or not claims_hold(ctx, v["claims"]):
            bad.append(Problem("variant-claim", "variant.claims"))
        if len(set(v["cites"]) & ctx.ids) < VARIANT_CITES:
            bad.append(Problem("variant-cites", "variant.cites"))
        if len(v["title"]) > SUBTITLE_MAX:
            bad.append(Problem("length", "variant.title"))
    for c in out["characters"]:
        if not claims_hold(ctx, c.get("claims", [])):
            bad.append(Problem("character-claim", f"characters.{c['character']}"))
    voided = voided_made(ctx)
    for f, x in _sentences(out):
        cites = set(x.get("cites", []))
        if cites and cites <= voided:
            bad.append(Problem("cite-voided", f))
    names = {c: str(ctx.book.characters[c]["name"]) for c in ctx.forgot if c in ctx.book.characters}
    for f, x in _sentences(out):
        text = str(x.get("sentence", x.get("text", "")))
        own = next((c for c in names if f.startswith(f"characters.{c}[")), None)
        if any(w in text for w in REMEMBER) and (own or any(n in text for n in names.values())):
            bad.append(Problem("forgot", f))
    return bad


def card_lines(ctx: Ctx, out: Mapping[str, Any]) -> list[Json]:
    """The characters on the card: the first sentence of each of the top 1-3 by rank; if all are unchanged, Melos's
    originalEnding (contract 1.6).

    カードに載せる登場人物：rank が上位の 1〜3 人それぞれの最初の一文。全員 unchanged ならメロスの originalEnding
    （契約 1.6）。
    """
    yours = {c["character"]: c["yours"] for c in out["characters"] if c["yours"]}
    top = sorted((r for r in ctx.ranks.values() if not r["unchanged"]), key=lambda r: r["rank"])[:CARD_LINES]
    lines = [
        {"character": r["character"], "line": yours[r["character"]][0]["sentence"]}
        for r in top
        if r["character"] in yours
    ]
    if not lines:
        lines = [{"character": MELOS, "line": original(ctx.book, MELOS)}]
    return lines


def unalias(out: Json, back: Mapping[str, str]) -> Json:
    """Map the `e<seq>` aliases in the model output back to real IDs; unrecognized ones are left as they are
    (validation reports cite-unknown). contrast.beat is left unchanged.

    モデル出力の別名 `e<seq>` を本当の ID に戻す。分からないものはそのまま残す（検証が cite-unknown を報告する）。
    contrast.beat はそのまま。
    """
    o = copy.deepcopy(out)

    def fix(x: Json) -> None:
        if isinstance(x, dict):
            if isinstance(x.get("cites"), list):
                x["cites"] = [back.get(c, c) for c in x["cites"]]
            for v in x.values():
                fix(v)
        elif isinstance(x, list):
            for v in x:
                fix(v)

    fix(o)
    return o


def from_model(ctx: Ctx, out: Mapping[str, Any]) -> Json:
    """Model output that passed validation → the ending (the code-computed parts are filled in as usual).

    検証を通ったモデル出力 → エンディング（コードで計算する部分は従来どおり補う）。
    """
    book = ctx.book
    you = out["you"]
    yours = {c["character"]: c["yours"] for c in out["characters"]}
    contrast = {"original": out["contrast"]["original"], "yours": out["contrast"]["yours"]}
    if out["contrast"].get("beat") is not None:
        contrast["beat"] = out["contrast"]["beat"]
    characters = []
    for c, r in ctx.ranks.items():
        row: Json = {"character": c, "rank": r["rank"], "unchanged": r["unchanged"], "original": original(book, c)}
        if not r["unchanged"]:
            row["yours"] = copy.deepcopy(yours[c])
        characters.append(row)
    world: Json = {**world_part(ctx), "contrast": contrast}
    v = out.get("variant")
    if v:
        world["variant"] = {
            "id": v["id"],
            "title": v["title"],
            "summary": v["summary"],
            "claims": copy.deepcopy(v["claims"]),
            "causedBy": list(dict.fromkeys(v["cites"])),
        }
        world["summary"] = v["summary"]
    return {
        "world": world,
        "player": {
            "fate": {"id": ctx.fate, "label": you["fate"]["text"], "causedBy": list(you["fate"]["cites"])},
            "relationships": relationships(ctx),
            "title": {"text": you["title"]["text"], "causedBy": list(you["title"]["cites"])},
            "epilogue": copy.deepcopy(out["epilogue"]),
            "lastScene": last_scene(book, ctx.state, ctx.stage),
            "didForYou": copy.deepcopy(you["didForYou"]),
            "youDid": copy.deepcopy(you["youDid"]),
        },
        "characters": characters,
        "card": {
            "title": you["title"]["text"],
            "subtitle": out["subtitle"],
            "contrast": out["cardContrast"],
            "characterLines": card_lines(ctx, out),
        },
    }


def assemble(ctx: Ctx, body: Mapping[str, Any], ending_id: str, t: int) -> Json:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "endingId": ending_id,
        "playthroughId": ctx.pid,
        "worldModelVersion": ctx.book.version,
        "trigger": ctx.trigger,
        "t": t,
        "decidedAt": recorded_at(),
        **copy.deepcopy(dict(body)),
    }


# —— API projection (api-contract 2.8) / API の投影（api-contract 2.8） ——


def view(ending: Mapping[str, Any]) -> Json:
    """A stored Ending → EndingView. signature, finalVars, changedBeats and every causedBy are left out.

    保存した Ending → EndingView。signature、finalVars、changedBeats、各所の causedBy は渡さない。
    """
    w, p = ending["world"], ending["player"]
    world: Json = {
        "outcomeId": (w.get("variant") or {}).get("id", w["outcome"]),
        "baseline": "variant" not in w,
        "title": (w.get("variant") or {}).get("title", w["title"]),
        "epilogue": copy.deepcopy(p["epilogue"]),
    }
    if w.get("contrast"):
        world["contrast"] = copy.deepcopy(w["contrast"])
    return {
        "endingId": ending["endingId"],
        "world": world,
        "you": {
            "title": p["title"]["text"],
            "fate": p["fate"]["label"],
            "didForYou": copy.deepcopy(p.get("didForYou", [])),
            "youDid": copy.deepcopy(p.get("youDid", [])),
        },
        "characters": copy.deepcopy(ending.get("characters", [])),
        "card": {**copy.deepcopy(ending["card"]), "fallbackImageUrl": f"/endings/{w['outcome']}.webp"},
    }


def eta(started: float, now: float) -> int:
    return max(ETA_MIN, ETA_SECONDS - int(now - started))


# —— Generation (tasks with kind: "ending") / 生成（kind: "ending" のタスク） ——


def check_request(ctx: Ctx, out: Mapping[str, Any]) -> Json:
    """The model check request: the classification, final state, events (aliases), and this ending's text (citations
    replaced with aliases). Never the player's utterances.

    モデルの検査の request：分類、最終状態、イベント（別名）、このエンディングの文章（引用は別名に置き換える）。
    発話は渡さない。
    """
    to_alias, _ = alias_map(ctx.events)

    def cites(x: Mapping[str, Any]) -> list[str]:
        return [to_alias.get(c, c) for c in x.get("cites", [])]

    def rows(xs: Sequence[Mapping[str, Any]]) -> list[Json]:
        return [{"sentence": x["sentence"], "cites": cites(x)} for x in xs]

    you = out["you"]
    v = out.get("variant")
    return {
        "worldModelVersion": ctx.book.version,
        "outcome": {"id": ctx.outcome, "label": ctx.label},
        "finalVars": {k: ctx.state["vars"][k] for k in sorted(ctx.state["vars"])},
        "events": [
            {"eventId": to_alias[e["eventId"]], "actor": e["actor"], "summary": e["summary"]} for e in ctx.events
        ],
        "ending": {
            "variant": None if not v else {"title": v["title"], "summary": v["summary"], "claims": v["claims"]},
            "epilogue": rows(out["epilogue"]),
            "contrast": {"original": out["contrast"]["original"], "yours": out["contrast"]["yours"]},
            "you": {
                "title": you["title"]["text"],
                "fate": you["fate"]["text"],
                "didForYou": rows(you["didForYou"]),
                "youDid": rows(you["youDid"]),
            },
            "characters": [
                {
                    "character": c["character"],
                    "name": ctx.book.characters[c["character"]]["name"],
                    "forgotYou": c["character"] in ctx.forgot,
                    "yours": rows(c["yours"]),
                }
                for c in out["characters"]
                if c["character"] in ctx.book.characters
            ],
        },
    }


async def coherent(
    n: Narrator, ctx: Ctx, out: Mapping[str, Any], spend: Spend, span: Mapping[str, Any]
) -> list[Problem]:
    """Model check (backend-design 2.9 step 4): whether the three layers hang together. If not → `coherence` plus the
    field names; if the check itself times out, errors or fails the Schema it doesn't block (returns nothing, Trace
    records `skipped`), and the ending is used as is.

    モデルの検査（backend-design 2.9 第 4 ステップ）：3 層の間で話が通るか。通らなければ → `coherence` にフィールド名を
    付ける。検査そのものがタイムアウト、エラー、Schema 不合格のときは止めず（空を返し、Trace に `skipped` を記録）、
    エンディングはそのまま使う。
    """
    request = check_request(ctx, out)
    model, version = model_and_version(CHECK_KIND)
    with n.tracer.span(
        f"narrator.{CHECK_KIND}", provider=spec(CHECK_KIND).provider, model=model, prompt_version=version, **span
    ) as sp:
        try:
            r = await asyncio.wait_for(
                n.text.call(CHECK_KIND, request), n.deadlines.get(CHECK_KIND, spec(CHECK_KIND).deadline)
            )
            spend.add(r)
            try:
                jsonschema.validate(r.output, PROMPTS[CHECK_KIND].schema)
            except jsonschema.ValidationError:
                sp.set(status="skipped", reason="invalid")
                return []
        except TimeoutError:
            spend.charge(CHECK_KIND, n.text.cancelled_cost(CHECK_KIND, request))
            sp.set(status="skipped", reason="timeout")
            return []
        except BadOutput as e:
            spend.charge(CHECK_KIND, e.cost_usd)
            sp.set(status="skipped", reason="invalid")
            return []
        except ModelCallFailed:
            sp.set(status="skipped", reason="error")
            return []
        except RateLimited:
            if n.on_rate_limit == "stop":
                raise
            sp.set(status="skipped", reason="rate_limited")
            return []
        ok = bool(r.output["coherent"])
        sp.set(status="ok" if ok else "rejected", cost_usd=round(r.cost_usd, 6))
        if ok:
            return []
        fields = [str(f)[:CHECK_FIELD_MAX] for f in r.output["fields"] if str(f).strip()] or ["ending"]
        return [Problem("coherence", f) for f in dict.fromkeys(fields)]


@dataclass
class Generated:
    body: Json
    template: bool
    calls: int
    problems: list[Problem]


async def generate(n: Narrator, ctx: Ctx, spend: Spend, span: Mapping[str, Any]) -> Generated:
    """Have the model write the ending: at most twice (timeout, error, Schema failure, validation failure, and the model
    check saying it doesn't hang together each count as one; the second carries the failed rule names), then the
    template.

    モデルにエンディングを書かせる：最大 2 回（タイムアウト、エラー、Schema 不合格、検証不合格、モデルの検査で話が
    通らないとされた場合はどれも 1 回と数える。2 回目は不合格の規則名を付ける）、その後はテンプレート。
    """
    _, back = alias_map(ctx.events)
    model, version = model_and_version(KIND)
    problems: list[Problem] = []
    calls = 0
    for attempt in range(1, MAX_CALLS + 1):
        calls = attempt
        request = request_of(ctx, [p.doc() for p in problems])
        with n.tracer.span(
            f"narrator.{KIND}",
            provider=spec(KIND).provider,
            model=model,
            prompt_version=version,
            attempt=attempt,
            **span,
        ) as sp:
            got: TextResult | None = None
            try:
                r = got = await asyncio.wait_for(n.text.call(KIND, request), n.deadlines[KIND])
                spend.add(r)
                try:
                    jsonschema.validate(r.output, PROMPTS[KIND].schema)
                except jsonschema.ValidationError:
                    raise BadOutput(f"{KIND} output fails the Schema / {KIND} の出力が Schema を通らない") from None
            except TimeoutError:
                cost = n.text.cancelled_cost(KIND, request)
                spend.charge(KIND, cost)
                sp.set(status="timeout", cost_usd=round(cost, 6))
                problems = []
                continue
            except BadOutput as e:
                if got is None:
                    spend.charge(KIND, e.cost_usd)
                sp.set(status="invalid", cost_usd=round(e.cost_usd if got is None else got.cost_usd, 6))
                problems = []
                continue
            except ModelCallFailed:
                sp.set(status="error")
                problems = []
                continue
            except RateLimited:
                if n.on_rate_limit == "stop":
                    raise
                sp.set(status="rate_limited")
                problems = []
                continue
            out = unalias(r.output, back)
            problems = validate(ctx, out)
            sp.set(
                status="ok" if not problems else "rejected",
                failed_rules=sorted({p.rule for p in problems}),
                tokens_in=r.usage.get("inputTokens", 0),
                tokens_out=r.usage.get("outputTokens", 0),
                tokens_cached=r.usage.get("cachedTokens", r.usage.get("cacheReadTokens", 0)),
                cost_usd=round(r.cost_usd, 6),
            )
            if not problems:
                problems = await coherent(n, ctx, out, spend, span)
            if not problems:
                return Generated(from_model(ctx, out), False, calls, [])
    log.info("Ending %s uses the template (%d calls) / エンディングはテンプレートを使う", ctx.pid, calls)
    return Generated(from_template(ctx), True, calls, problems)


async def run_ending(n: Narrator, task: Task) -> Result:
    """The `kind: "ending"` task: call the model outside the transaction, then in one transaction store the ending,
    clear the player's utterances, and push `ending_ready`.

    `kind: "ending"` のタスク：トランザクションの外でモデルを呼び、1 つのトランザクションでエンディングを保存し、
    発話を消し、`ending_ready` をプッシュする。
    """
    from zoujin_backend.narrator.core import Gone, Result, cost_values

    started = time.monotonic()
    pt, state = await n.read(task.pid)
    book = n.library.version(pt["world_model_version"])
    async with n.engine.connect() as c:
        log_ = await store.event_log(c, task.pid, book.version)
        said = [
            str(t)
            for t in (
                await c.scalars(
                    select(utterances.c.text).where(
                        utterances.c.playthrough_id == task.pid,
                        utterances.c.speaker == "player",
                        utterances.c.text.is_not(None),
                    )
                )
            ).all()
        ]
        rows = (await c.execute(select(memory_items).where(memory_items.c.playthrough_id == task.pid))).mappings().all()
        memories = [item_json(dict(r)) for r in rows]
    request = dict(task.request or {})
    ctx = make_ctx(book, state, task.pid, pt["role_id"], request, log_, said, memories)
    spend = task.spend
    span = {"playthrough_id": task.pid, "turn_id": task.turn_id, "world_model_version": book.version}
    # World model error: none of the 5 holds / 世界モデルの誤り：5 種類のどれも成り立たない
    if request.get("unclassified"):
        with n.tracer.span("narrator.ending.unclassified", failed_rules=["ending-unclassified"], **span):
            pass
    got = await generate(n, ctx, spend, span)
    ending_id = n.ids.new("end")
    doc = assemble(ctx, got.body, ending_id, int(state["t"]))
    # Not matching the data contract raises SchemaError, and the task is retried as a failure.
    # データ契約に合わなければ SchemaError を投げ、タスクは失敗としてやり直す。
    n.schemas.ending(doc)
    ms = int((time.monotonic() - started) * 1000)
    push = [{"type": "ending_ready", "endingId": ending_id}]
    async with n.engine.begin() as c:
        live = await c.scalar(
            select(playthroughs.c.status).where(playthroughs.c.playthrough_id == task.pid).with_for_update()
        )
        if live is None:
            raise Gone(task.pid)
        status = await c.scalar(select(turns.c.status).where(turns.c.turn_id == task.turn_id).with_for_update())
        if status != "leased":
            raise Gone(task.turn_id)
        await c.execute(
            insert(endings).values(ending_id=ending_id, playthrough_id=task.pid, body=doc, decided_at=func.now())
        )
        await c.execute(
            update(utterances)
            .where(utterances.c.playthrough_id == task.pid, utterances.c.text.is_not(None))
            .values(text=None)
        )
        await store.clear_plan_texts(c, task.pid, None)
        m = playthrough_metrics.c
        await c.execute(
            update(playthrough_metrics)
            .where(m.playthrough_id == task.pid)
            .values(
                ending_outcome=ctx.outcome,
                ending_template=got.template,
                ending_calls=got.calls,
                ending_ms=ms,
                **cost_values(spend),
            )
        )
        spend.usd.clear()
        await c.execute(
            update(turns)
            .where(turns.c.turn_id == task.turn_id)
            .values(
                status="done",
                outcome="committed",
                minutes=0,
                lease_until=None,
                settled_at=func.now(),
                result={"push": push, "pieces": [], "seq": pt["last_seq"], "endingId": ending_id},
            )
        )
        await n._notify(c, task, seq=int(pt["last_seq"]), outcome="committed")
    with n.tracer.span(
        "narrator.ending.done",
        trigger=ctx.trigger,
        outcome=ctx.outcome,
        template=got.template,
        calls=got.calls,
        failed_rules=sorted({p.rule for p in got.problems}),
        **span,
    ) as sp:
        sp.attrs["duration_ms"] = ms
    log.info(
        "Ending %s: %s, template %s, %d calls, %d ms / エンディング",
        task.pid,
        ctx.outcome,
        got.template,
        got.calls,
        ms,
    )
    return Result(task, [], state, "committed", 0, [], push, {"endingId": ending_id, "template": got.template})
