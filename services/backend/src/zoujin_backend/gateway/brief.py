"""System instructions for a Live session (B-10, backend-design 2.3): rules (`prompt_texts/live.txt`) + persona +
the current situation + 話し相手 + さっきまでの会話.

- The persona, situation and player sections use the same building blocks the narrator gives `reply`
  (`persona`, `situation`, `player_card` in `narrator/view.py`), laid out as Japanese entries. So the knowledge
  boundary (S-086: a character who doesn't know the fact naming the day only gets the time of day) is the same as for
  the characters in the evals.
- **No world model prefix**: Live bills the whole context again every turn, and the prefix would add about $0.03 per
  turn 〔estimate〕.
- 「さっきまでの会話」: the character's last few turns of text held in the gateway's memory (skipping retracted and
  deleted ones); memory only, never written to the database or Trace.
- The situation entries (`facts`) are also used for mid-session updates: compared with what was last sent into the
  session, only what changed is sent (`changes`).
- Version = hash of the rules text (the same approach as `Prompt.version`), recorded in Trace's `live.session`.
- `live.txt` and the narrator's `reply.txt` are a pair (prompt text can't hold comments, so the note is here): when an
  S-068 conclusion changes `reply.txt`, `live.txt` changes in the same PR (#111 data review).
- 「気をつけること」: hints from B-12's output-side monitor (`monitor.notes`), included when the session opens; a
  spoiler correction never names the word itself.
- The player is addressed by the name in the 「話し相手」 section (`name` from `player_card`, i.e. the role name; since
  contract 1.8 the role name refers only to the player).

Live セッションのシステム指示（B-10、backend-design 2.3）：ルール（`prompt_texts/live.txt`）＋人物設定＋いまの状況＋
話し相手＋さっきまでの会話。

- 人物設定、状況、プレイヤーの 3 つは、ナレーターが `reply` に渡すのと同じもの（`narrator/view.py` の `persona`、
  `situation`、`player_card`）を日本語の項目として並べる。そのため知っていることの境界（S-086：日付を示す事実を
  知らない登場人物には時間帯だけを渡す）は評価での登場人物と同じになる。
- **世界モデルのプレフィックスは入れない**：Live は毎ターン文脈全体を課金し直すので、プレフィックスを入れると
  1 ターンあたり約 0.03 ドル増える〔推計〕。
- 「さっきまでの会話」：ゲートウェイのメモリにあるこの登場人物の直近数ターンの文字（取り消し・削除済みは飛ばす）。
  メモリ内だけで、データベースにも Trace にも入れない。
- 状況の項目（`facts`）は途中の更新にも使う：前回セッションに送ったものと比べ、変わったものだけを送る（`changes`）。
- バージョン = ルール文のハッシュ（`Prompt.version` と同じやり方）。Trace の `live.session` に記録する。
- `live.txt` とナレーターの `reply.txt` は対になっている（プロンプト文にはコメントを書けないのでここに書く）：
  S-068 の結論で `reply.txt` を変えるときは、同じ PR で `live.txt` も変える（#111 データのレビュー）。
- 「気をつけること」：B-12 の出力側モニターのヒント（`monitor.notes`）。セッションを開くときに付ける。
  ネタバレの訂正ではその語を名指ししない。
- プレイヤーの呼び方は「話し相手」の名前（`player_card` の `name`、つまり役名。契約 1.8 以降、役名はプレイヤー
  だけを指す）。
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from typing import Any

from zoujin_worldsim import OCCURRED, SimState

from zoujin_backend.models.live import Recent
from zoujin_backend.models.prompts import text
from zoujin_backend.narrator import roles
from zoujin_backend.narrator.view import persona, player_card, situation, state_view
from zoujin_backend.world import Book

Json = Any


@cache
def rules() -> str:
    return text("live")


def version() -> str:
    return "l" + hashlib.sha256(rules().encode()).hexdigest()[:12]


@dataclass(frozen=True)
class Brief:
    system: str
    # Situation entries (「時：…」「場所：…」「知っていること：…」), compared for mid-session updates.
    # 状況の項目（「時：…」「場所：…」「知っていること：…」）。途中の更新のときに比べる。
    facts: tuple[str, ...]


def _names(book: Book) -> dict[str, str]:
    out = {c["id"]: c["name"] for c in book.world["characters"]}
    out |= {p["id"]: p["name"] for p in book.world["places"]}
    return out


def _by_world(book: Book, state: SimState, who: str, fact: str) -> bool:
    """By the world model (`Character.knows`) the character already knows this now: since is pre, or that beat has
    happened / been altered.

    世界モデル（`Character.knows`）上、この登場人物はいま元から知っている：since が pre、またはそのビートが
    すでに起きた / 書き換えられた。
    """
    beats = state["beats"]
    return any(
        k["fact"] == fact and (k["since"] == "pre" or beats.get(k["since"]) in OCCURRED)
        for k in book.characters[who].get("knows", [])
    )


def situation_facts(book: Book, state: SimState, who: str, forgotten: frozenset[str] = frozenset()) -> tuple[str, ...]:
    view = state_view(book, state)
    s = situation(book, state, who, view)
    names = _names(book)
    statements = {f["id"]: f["statement"] for f in book.world["facts"]}
    run = state["runFacts"]
    lines = [f"時：{s['time']}", f"場所：{names.get(s['place'], s['place'])}"]
    here = [names.get(c, c) for c in s["present"]]
    lines.append("近くにいる人：" + ("、".join(here) if here else "（いない）"))
    visible_facts: set[str] = set()
    for k in s["knows"]:
        real = view.real(k)
        # What the world model lets the character know is still given (data review).
        # 世界モデル上知っていることはそのまま渡す（データの見直し）。
        if real in forgotten and not _by_world(book, state, who, real):
            continue
        if real in statements:
            lines.append("知っていること：" + statements[real])
            visible_facts.add(real)
        elif real in run:
            lines.append("知っていること：" + str(run[real]["statement"]))
    # Lived-through times are marked only on facts the character is already allowed to have. A whole beat.summary is
    # omniscient narration that may hold durations that haven't happened yet, other people's inner thoughts or the
    # novel's relative dates, so it must not be injected as the character's own experience.
    # 自分で経験した時刻は、登場人物に渡してよいと認められた事実にだけ付ける。beat.summary 全体は全知の語りで、
    # まだ起きていない長さ、他人の内心、原作の相対的な日付を含みうるので、登場人物の体験として入れてはならない。
    for recent in s["recent"]:
        beat = book.beats[recent["beat"]]
        variant = next((v for v in beat.get("variants", []) if v["id"] == recent.get("variant")), None)
        if state["beats"].get(beat["id"]) == "altered" and variant is None:
            # A freely altered beat has no right to the novel's summary; the novel's outcome must not pose as what
            # happened in this game.
            # 自由に書き換えられたビートには原作の要約を使う権限がない。原作の結果をこのゲームの体験に見せかけない。
            continue
        for fact in book.world["facts"]:
            if fact["id"] in visible_facts and fact["trueFrom"] == beat["id"]:
                lines.append(f"これまでに見聞きしたこと：（{recent['day']}）{fact['statement']}")
    return tuple(lines)


def build(
    book: Book,
    state: SimState,
    who: str,
    recent: Sequence[Recent] = (),
    notes: Sequence[str] = (),
    memories: Sequence[str] = (),
    forgotten: frozenset[str] = frozenset(),
    *,
    samples: int = 4,
) -> Brief:
    """notes: the few hints B-12's output-side monitor adds for this character (spoiler correction, too many
    questions, not pushing toward death; `gateway/monitor.py`), placed in 「# 気をつけること」 after
    「# いまの状況」. Included only when the session opens (mid-session updates only compare `facts`).
    memories: B-13, this character's undeleted memories of the player (`narrator/memory.memories_for_brief`, picked by
    salience, ordered by time), placed in 「# 覚えていること」 after 「# いまの状況」; ones deleted in the 記憶帳 are
    not here, and the session is rebuilt on deletion.
    forgotten: facts the character learned only in the source events of deleted memories
    (`narrator/memory.forgotten_facts`), left out of 「知っていること」 (UX review: the character simply doesn't know
    it, and if the player brings it up again they hear it as new). Voided promises and forget events never enter the
    situation description anyway.
    samples: how many 「口ぶりの例」 lines (2 in B-14's economy tier; the caller trims the number of memories and of
    recent turns).

    notes：B-12 の出力側モニターがこの登場人物に加えるいくつかのヒント（ネタバレの訂正、質問が多すぎる、死へ
    押しやらない。`gateway/monitor.py`）。「# いまの状況」の後の「# 気をつけること」に置く。セッションを開くときだけ
    付ける（途中の更新では `facts` だけを比べる）。
    memories：B-13、この登場人物のプレイヤーについての削除されていない記憶（`narrator/memory.memories_for_brief`。
    salience で選び、時刻順に並べる）。「# いまの状況」の後の「# 覚えていること」に置く。記憶帳で削除したものは
    ここになく、削除に合わせてセッションも作り直す。
    forgotten：削除した記憶の元のイベントで初めて知った事実（`narrator/memory.forgotten_facts`）。
    「知っていること」には入れない（UX のレビュー：登場人物はそのことを知らないだけで、プレイヤーがまた話せば新しい
    話として聞く）。無効になった約束や forget イベントはもともと状況の説明に入らない。
    samples：「口ぶりの例」を何行入れるか（B-14 の節約モードでは 2 行。記憶の件数と直近の会話のターン数は
    呼び出し側が切り詰める）。
    """
    p = persona(book, state, who)
    me = player_card(book, state, who)
    facts = situation_facts(book, state, who, forgotten)
    out = [rules(), "", "# あなた", f"名前：{p['name']}"]
    if p.get("summary"):
        out.append(str(p["summary"]))
    if p["traits"]:
        out.append("人柄：" + "／".join(p["traits"]))
    if p["goals"]:
        out.append("いまの目的：" + "／".join(p["goals"]))
    speech = p.get("speech") or {}
    if speech.get("firstPerson"):
        out.append(f"一人称：{speech['firstPerson']}")
    if speech.get("register"):
        out.append(f"口調：{speech['register']}")
    for q in speech.get("sampleLines", [])[:samples]:
        out.append(f"口ぶりの例：「{q}」")
    # Confidence in reading minds in the persona is a belief and grants no extra access to facts; it goes after the
    # persona to make the boundary between the two explicit.
    # 人物設定にある心を読む自信は信念であり、登場人物に事実への追加の権限を与えない。人物設定の後に置いて両者の
    # 境界をはっきりさせる。
    out += [
        "",
        "# 人柄と知識の区別",
        "人柄や目的にある、ほかの人への見方や思い込みは、あなた自身の信念です。"
        "その人が実際に何を思い、何をしたかを知る証拠にはなりません。"
        "特定の人のまだ知らない胸の内を問われても、その人の心情を具体的に作り足さず、"
        "あなた自身の人間観や信念として語ってください。人を信じる・信じないという気持ちや口調は保ちます。",
    ]
    out += ["", "# いまの状況"]
    out += [f"- {x}" for x in facts]
    if memories:
        out += ["", "# 覚えていること"]
        out += [f"- {x}" for x in memories]
    if notes:
        out += ["", "# 気をつけること"]
        out += [f"- {x}" for x in notes]
    out += ["", "# 話し相手", f"{me['name']}（{'顔見知り' if me['knownToYou'] else '初めて会う相手'}）"]
    out += roles.brief_lines(book, state, who)  # B-19
    said = [r for r in recent if r.player or r.reply]
    if said:
        out += ["", "# さっきまでの会話"]
        for r in said:
            if r.player:
                out.append(f"{me['name']}：{_flat(r.player)}")
            if r.reply:
                out.append(f"あなた：{_flat(r.reply)}")
    return Brief("\n".join(out), facts)


def changes(old: Sequence[str], new: Sequence[str]) -> str | None:
    """Mid-session update: send only the new entries (a changed time, place or people present, newly known things).
    None if nothing changed.

    途中の更新：新しく現れた項目だけを送る（変わった時刻、場所、その場にいる人、新しく知ったこと）。変化がなければ
    None を返す。
    """
    added = [x for x in new if x not in set(old)]
    if not added:
        return None
    return "【状況の変化】\n" + "\n".join(f"- {x}" for x in added)


def _flat(s: str) -> str:
    """Line breaks and a leading 「#」 in what was said must not pose as instruction sections.

    発言の中の改行や先頭の「#」が指示の段落になりすまさないようにする。
    """
    return " ".join(s.split()).lstrip("#")
