"""Narrator step 3: the deterministic rules R1-R4, R7 and the rule part of R6 (backend-design 2.4, contract section
3), without calling models.

- The judging covers at least the "simplest judging of the deterministic rules" in `evals/s2/README.md` (`judge()` in
  `evals/s2_check.py`): everything it reports is reported here too, compared item by item in `tests/test_rules.py`. The
  few places that judge more than it are noted in each function (actor and targets must be present, characters who are
  absent, the giver must hold the item).
- World rules (condition evaluation, applying effects, `valueRequires`, `OCCURRED`, `knows`, `travel_minutes`, checks
  of references and values) come only from W-1; no second copy here.
- R5 and the rest of R6 are step 4 (model check, `narrator/pipeline.py`).

A candidate's effects are judged in order: earlier effects take effect first on a flattened state (variables + item
holders) and the characters' locations, and later ones are judged after them (like `judge()` and
`Sim.value_requires`). Several candidates in one turn are also taken in order, with earlier passing ones trial-applied
to the state first (`check_candidates`). `reason` is one Japanese sentence (contract CheckResult.reason) using names
from the world model and never the player's words.

ナレーターの第 3 ステップ：決定的な規則 R1〜R4、R7 と R6 の規則部分（backend-design 2.4、契約第 3 節）。
モデルは呼ばない。

- 判定は少なくとも `evals/s2/README.md` の「決定的な規則の最も簡単な判定」（`evals/s2_check.py` の `judge()`）を
  カバーする：それが報告するものはここでもすべて報告し、`tests/test_rules.py` で 1 つずつ照合する。それより多く判定する
  箇所は各関数に書いてある（行為者と対象がその場にいること、absent の登場人物、物を渡す人が手に持っていること）。
- 世界の規則（条件評価、効果の適用、`valueRequires`、`OCCURRED`、`knows`、`travel_minutes`、参照と値の検査）は
  W-1 からだけ取り、ここに別の写しは書かない。
- R5 と R6 の残りは第 4 ステップ（モデルの検査、`narrator/pipeline.py`）。

1 つの候補の効果は順に判定する：前の効果がまず平らにした状態（変数 + 物の持ち主）と登場人物の居場所に反映され、
後の効果はその後で判定する（`judge()`、`Sim.value_requires` と同じ）。同じターンの複数の候補も順に扱い、先に通った
ものを状態に試算してから次を判定する（`check_candidates`）。`reason` は日本語の一文（契約 CheckResult.reason）で、
世界モデルの名前を使い、プレイヤーの発話は含めない。
"""

from __future__ import annotations

import copy
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from zoujin_backend.ids import IdGen
from zoujin_backend.safety import pii
from zoujin_worldsim import (
    OCCURRED,
    Sim,
    SimState,
    activity,
    apply,
    check_effects,
    flat,
    knows,
    spoilers,
    travel_minutes,
)

Json = Any

RULES = ("R1-anchor", "R2-precondition", "R3-time", "R4-knowledge", "R5-persona", "R6-safety", "R7-capability")
# Judged only by step 3 / 第 3 ステップだけが判定する
STEP3 = ("R1-anchor", "R2-precondition", "R3-time", "R4-knowledge", "R7-capability")
# Judged only by step 4; R6 is judged by both steps, and the part of R1 written in text is also step 4.
# 第 4 ステップだけが判定する。R6 は両方のステップで判定し、R1 のうち文章に書かれた部分も第 4 ステップ。
MODEL_ONLY = ("R5-persona",)
# Bump when the judging changes (b3.1: targets of end-of-act plans count as present if "reachable during the skip").
# 判定を変えたら上げる（b3.1：幕末のプランの対象は「この間に行ける」ならその場にいるとみなす）。
VERSION = "b3.1"
CHECKER = f"rules@{VERSION}"

# The dead don't come back (rule.no-resurrection): once a variable reaches this value it can't change to anything else.
# 死んだ者は生き返らない（rule.no-resurrection）：変数がこの値になったら、ほかの値には戻せない。
TERMINAL = {"var.hostage.fate": "executed", "var.player.custody": "executed", "var.melos.custody": "executed"}
# R6's rule part: personal-information patterns (`safety.pii`, shared since B-12 with storing utterances and the memory
# filter), plus the old pattern judge() uses for label checking (three groups of digits separated by dashes, not
# required to start with 0; PII in `evals/s2_check.py`), and 8 consecutive characters identical to the player's words.
# R6 の規則部分：個人情報のパターン（`safety.pii`。B-12 以降、発話の保存や記憶のフィルターと共通）に、judge() が
# ラベル確認に使う古い書き方（ハイフンで区切った 3 組の数字、0 始まりは必須でない。`evals/s2_check.py` の PII）を加え、
# プレイヤーの発話と 8 文字連続で一致するもの。
_D = "[0-9０-９]"
PII_EXTRA = re.compile(rf"{_D}{{2,4}}[-‐－]{_D}{{2,4}}[-‐－]{_D}{{3,4}}|[@＠][\w.-]+[.．]\w+|〒")


def has_pii(text: str | None) -> bool:
    return bool(text) and (bool(pii.find(text)) or PII_EXTRA.search(text or "") is not None)


VERBATIM = 8
FLAG_REASON = {
    "injection": "この発話は、物語の外からの指示として止められた",
    "pii": "この発話に現実の個人情報が含まれていた",
    # B-12: Model Armor HIGH, or the classifier refused / B-12：Model Armor の HIGH、分類器の拒答
    "harmful": "この発話は、物語に書けない内容として止められた",
    # B-12: the classifier couldn't decide twice (most conservative).
    # B-12：分類器が二度とも判定できなかった（最も控えめに）。
    "unscreened": "この発話は、安全の確認がとれなかった",
}
BEAT_TO = {
    "prevented": "起きなかったこと",
    "delayed": "遅らせること",
    "hastened": "早めること",
    "altered": "変えること",
}
BEAT_RESULT = {"happened": "もう起きた", "altered": "もう形を変えて起きた", "prevented": "もう起きないと決まった"}
# W-1 check_effects codes → rule and one Japanese sentence (bad reference, value or op: impossible in this world).
# W-1 check_effects のコード → 規則と日本語の一文（参照、値、op の誤り：この世界ではできない）。
SHAPE = {
    "unknown-id": ("R7-capability", "この世界にいない人、ない物や場所が出てくる"),
    "bad-value": ("R7-capability", "その値は、この世界では取りえない"),
    "bad-op": ("R7-capability", "その変化は、この世界の決まりでは起こせない"),
    "duplicate-id": ("R7-capability", "同じ設定や約束を二度記録しようとしている"),
}


@dataclass(frozen=True)
class Turn:
    """The turn as step 3 needs it. said = the player's words (only used for the 8-character copying check, never
    logged); act = the action (`kind`, `target`, `params`, plus `affordance` for a situational action); flags = step 0
    screening flags (`injection`, `pii`, `harmful`, `unscreened`, `ambiguous`, filled by B-12's safety screening).

    第 3 ステップが必要とするこのターン。said = プレイヤーの発話（8 文字の書き写しの比較だけに使い、ログには入れない）。
    act = アクション（`kind`、`target`、`params`。状況アクションなら `affordance` も付く）。flags = 第 0 ステップの
    スクリーニングの印（`injection`、`pii`、`harmful`、`unscreened`、`ambiguous`。B-12 の安全スクリーニングが入れる）。
    """

    said: str = ""
    act: Mapping[str, Any] | None = None
    flags: frozenset[str] = frozenset()


NO_TURN = Turn()


@dataclass(frozen=True)
class Hit:
    rule: str
    # Name of the check (for Trace, metrics and tests; never contains the player's words).
    # 判定の名前（Trace、指標、テスト用。発話は含めない）。
    code: str
    reason: str  # one Japanese sentence / 日本語の一文


@dataclass
class Checked:
    """A candidate event and its check result. effects are the candidate's own (with promiseId etc. filled in); a
    rejected one is committed with empty effects.

    候補イベントとその検査結果。effects は候補の元のもの（promiseId などは補ってある）。却下されたものはコミット時に
    effects を空にする。
    """

    candidate: Json
    effects: list[Json]
    check: Json
    rules: list[Json] = field(default_factory=list)
    hits: list[Hit] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.check["status"] != "rejected")


class Index:
    """One book's world model, indexed by ID (one per world model version, see `index()`).

    1 冊の本の世界モデルを ID で索引したもの（世界モデルのバージョンごとに 1 つ、`index()` を参照）。
    """

    def __init__(self, world: Json) -> None:
        self.world = world
        self.sim = Sim(world)
        self.chars: dict[str, Json] = {c["id"]: c for c in world["characters"]}
        self.places: dict[str, Json] = {p["id"]: p for p in world["places"]}
        self.facts: dict[str, Json] = {f["id"]: f for f in world["facts"]}
        self.items: dict[str, Json] = {x["id"]: x for x in world.get("items", [])}
        self.affs: dict[str, Json] = {a["id"]: a for a in world["affordances"]}
        self.roles: dict[str, Json] = {r["id"]: r for r in world["roles"]}
        self.anchor_beats = {b["id"] for b in world["beats"] if b["kind"] == "anchor"} | {
            a for a in world["anchors"] if a.startswith("beat.")
        }

    # —— Names (for the Japanese reason) / 名前（日本語の reason 用） ——

    def who(self, x: str | None) -> str:
        if x == "player":
            return "プレイヤー"
        c = self.chars.get(x or "")
        return str(c["name"]) if c else str(x)

    def place(self, x: str | None) -> str:
        p = self.places.get(x or "")
        return str(p["name"]) if p else str(x)

    def beat(self, x: str) -> str:
        return str(self.sim.beats[x]["title"])

    def item(self, x: str | None) -> str:
        it = self.items.get(x or "")
        return str(it.get("name", x)) if it else str(x)

    def fact(self, x: str) -> str:
        f = self.facts.get(x)
        return str(f["statement"]).rstrip("。") if f else "その話"

    def var(self, x: str) -> str:
        v = self.sim.svars.get(x)
        return str(v.get("description") or x) if v else x


_INDEX: dict[str, Index] = {}


def index(world: Json) -> Index:
    """Cached by worldModelVersion (world models are read-only).

    worldModelVersion ごとにキャッシュする（世界モデルは読み取り専用）。
    """
    key = str(world["worldModelVersion"])
    got = _INDEX.get(key)
    if got is None or got.world is not world:
        got = _INDEX[key] = Index(world)
    return got


# —— A few judgments on the world state (not in W-1; B-2 card: ask the data side whether they belong in W-1, and keep
# them here until they answer) ——
# —— 世界状態に対するいくつかの判断（W-1 にないもの。B-2 カード：W-1 に入れるべきかデータ側に聞き、返事が来るまで
# ここに書く） ——


def anchor_locked(ix: Index, state: SimState) -> dict[str, Json]:
    """Variables written by an anchor beat that happened and not changed by any later beat → value (overturning it =
    R1). Same as judge()'s anchor_locked.

    起きたアンカーのビートが書き、その後ほかのビートが変えていない変数 → 値（覆すと R1）。
    judge() の anchor_locked と同じ。
    """
    locked: dict[str, Json] = {}
    times = state["times"]
    for bid in sorted(times, key=lambda b: (times[b], ix.sim.beats[b]["order"])):
        if state["beats"].get(bid) not in OCCURRED:
            continue
        for e in ix.sim.beats[bid]["outcomes"]:
            if e["op"] != "set":
                continue
            if bid in ix.anchor_beats:
                locked[e["var"]] = (e["value"], bid)
            else:
                locked.pop(e["var"], None)
    return {v: x for v, x in locked.items() if state["vars"].get(v) == x[0]}


def absent(ix: Index, state: SimState, who: str) -> bool:
    """S-077 ⑩: not present right now (e.g. in the slice, the two at the stonemason's workshop are indoors in act 1).
    The snapshot still lists them, with `activity: absent`. The test is W-1's `activity()`: characters absent at the
    start and not yet taken away by a beat or event.

    S-077 ⑩：いまその場にいない（例：スライスでは石工の工房の 2 人は第一幕で屋内にいる）。スナップショットには
    そのまま載せ、`activity: absent` とする。判定は W-1 の `activity()`：開始時に absent で、まだビートやイベントに
    連れ出されていない登場人物。
    """
    return activity(ix.world, state, who) == "absent"


def reach(ix: Index, state: SimState, cur: Mapping[str, Any]) -> set[str]:
    """The places the player can enter right now: the role's access + the conditionalAccess that holds now + the
    current place.

    プレイヤーがいま入れる場所：役柄の access + いま成り立つ conditionalAccess + いまいる場所。
    """
    role = ix.roles[state["role"]]
    ok = set(role["access"]) | {
        ca["place"] for ca in role.get("conditionalAccess", []) if ix.sim.holds(ca["when"], cur)
    }
    ok.add(cur["var.player.location"])
    return ok


def lcs_len(a: str, b: str) -> int:
    """Length of the longest common substring (the same comparison as judge() and the eval's no_verbatim_quotes).

    最長共通部分文字列の長さ（judge() と評価の no_verbatim_quotes と同じ比べ方）。
    """
    best, prev = 0, [0] * (len(b) + 1)
    for x in a:
        now = [0] * (len(b) + 1)
        for j, y in enumerate(b, 1):
            if x == y:
                now[j] = prev[j - 1] + 1
                best = max(best, now[j])
        prev = now
    return best


# —— Judging / 判定 ——


class _Judge:
    """Step 3 for one candidate event.

    1 つの候補イベントに対する第 3 ステップ。
    """

    def __init__(self, ix: Index, state: SimState, cand: Json, effects: Sequence[Json], turn: Turn) -> None:
        self.ix, self.state, self.cand, self.effects, self.turn = ix, state, cand, effects, turn
        self.hits: list[Hit] = []
        # Flattened state, updated in effect order / 平らにした状態。効果の順に反映する
        self.cur: dict[str, Any] = flat(state)
        self.where: dict[str, str] = dict(state["locations"])
        self.ppl: str = state["vars"]["var.player.location"]
        self.actor: str = cand.get("actor", "")
        # Minutes each character walked in this candidate (R3: the legs together must not exceed dt).
        # この候補で誰が何分歩いたか（R3：何区間でも合計が dt を超えない）。
        self.walked: dict[str, int] = {}

    def hit(self, rule: str, code: str, reason: str) -> None:
        if not any(h.rule == rule and h.reason == reason for h in self.hits):
            self.hits.append(Hit(rule, code, reason))

    def here(self, who: str | None) -> bool:
        """With the player: the player themself; or someone not absent who is at the player's place or whom the player
        is accompanying (end-of-act plans: see below).

        プレイヤーのそば：プレイヤー自身。または absent でなく、プレイヤーと同じ場所にいるか、プレイヤーが同行している者
        （幕末のプランは下を参照）。
        """
        if who in (None, "player"):
            return True
        assert who is not None
        if (self.turn.act or {}).get("kind") == "world":
            # World advancement (B-16): characters act where the player isn't. The actor just must not be absent;
            # targets are reachable only at the actor's place.
            # 世界の進行（B-16）：登場人物はプレイヤーのいない場所で動く。行為者は absent でなければよく、対象は行為者と
            # 同じ場所にいるときだけ届く。
            if absent(self.ix, self.state, who):
                return False
            return who == self.actor or self.where.get(who) == self.where.get(self.actor, self.ppl)
        if (self.turn.act or {}).get("kind") == "plan":
            # End-of-act plans (B-3): they describe what to do during the skipped time, so a target counts as reachable
            # if it is somewhere the player can go (even if absent right now).
            # 幕末のプラン（B-3）：飛ばす間にすることを言うので、対象がプレイヤーの行ける場所にいれば届くとみなす
            # （いまその場にいなくても）。
            return self.where.get(who) in reach(self.ix, self.state, self.cur)
        if absent(self.ix, self.state, who):
            return False
        return self.where.get(who) == self.ppl or self.cur.get("var.player.companionOf") == who

    def run(self) -> list[Hit]:
        self.safety()
        broken = self.shape()
        ix, c = self.ix, self.cand
        if c["t"] < self.state["t"]:
            self.hit("R3-time", "time-backwards", "時間はさかのぼれない")
        if self.actor != "player" and self.actor in ix.chars and not self.here(self.actor):
            self.hit("R7-capability", "actor-away", f"{ix.who(self.actor)}は、いまここにいない")
        locked = anchor_locked(ix, self.state)
        for i, e in enumerate(self.effects):
            if i in broken:
                continue
            getattr(self, "op_" + e["op"], lambda e: None)(e)
            if e["op"] == "set" and e["var"] in locked and e["value"] != locked[e["var"]][0]:
                self.hit(
                    "R1-anchor",
                    "anchor-var",
                    f"{ix.var(e['var'])}は「{ix.beat(locked[e['var']][1])}」の結果で、変えられない",
                )
            ix.sim.apply([e], self.cur, self.where)
        self.affordance()
        return self.hits

    # References, values, op, promise state, whether beat changes can combine, valueRequires: W-1's check_effects.
    # 参照、値、op、約束の状態、ビートの変更を合わせられるか、valueRequires：W-1 の check_effects。
    def shape(self) -> set[int]:
        """Report problems with references, values and op, and return the indexes of effects that judging and trial
        application can't use (beat doesn't exist or bad `to`, bad variable for `inc`). Other faulty effects are still
        judged (e.g. a `set` with an invalid value is still checked for anchors and access), so, like judge(), nothing
        is missed because of shape.

        参照、値、op の問題を報告し、判定と試算に使えない効果の添字を返す（ビートが存在しない、`to` が誤り、`inc` の
        変数が誤り）。ほかの問題のある効果はそのまま判定する（例：値が不正な `set` もアンカーと権限は見る）。judge() と
        同じく、形の問題のせいで報告漏れが出ないようにする。
        """
        broken: set[int] = set()
        for p in check_effects(self.ix.world, self.state, self.effects, self.cand.get("origin", "turn")):
            e = self.effects[p["index"]]
            if p["code"] in SHAPE:
                rule, reason = SHAPE[p["code"]]
                self.hit(rule, p["code"], reason)
                if p["code"] != "duplicate-id" and e.get("op") in ("beat", "inc"):
                    broken.add(p["index"])
            elif p["code"] == "value-requires":
                self.hit("R2-precondition", "value-requires", p.get("note") or "その値になる条件が成り立っていない")
            elif p["code"] == "bad-state" and e.get("op") == "promise":
                self.hit(
                    "R2-precondition", "promise-closed", "その約束は、もう果たされたか、破られたか、取り消されている"
                )
            elif p["code"] == "bad-state":
                self.hit(
                    "R2-precondition",
                    "beat-change-conflict",
                    f"「{self.ix.beat(e['beat'])}」には、もう別の変化が決まっている",
                )
            # beat-happened and beat-has-result are judged by op_beat (same conditions, with the beat name in reason).
            # beat-happened と beat-has-result は op_beat が判定する（同じ条件で、reason にビート名を使う）。
        return broken

    def op_beat(self, e: Json) -> None:
        ix, b, to = self.ix, e["beat"], e["to"]
        if b in ix.anchor_beats and to != "happened":
            self.hit(
                "R1-anchor", "anchor-beat", f"「{ix.beat(b)}」は物語の要で、{BEAT_TO.get(to, '変えること')}はできない"
            )
        st = self.state["beats"].get(b)
        if st is not None:
            self.hit("R2-precondition", "beat-has-result", f"「{ix.beat(b)}」は{BEAT_RESULT.get(st, 'もう決まった')}")
            return
        # Beats are settled by the system when their time comes; to move one earlier use hastened (contract 2.4.1;
        # W-1 also reports beat-happened).
        # ビートは時刻が来たらシステムが精算する。早めるなら hastened を使う（契約 2.4.1。
        # W-1 も beat-happened を報告する）。
        if to == "happened":
            self.hit(
                "R2-precondition",
                "beat-happened",
                f"「{ix.beat(b)}」は時が来て起きる出来事で、この場で起きたことにはできない",
            )
        if to in OCCURRED:
            if not ix.sim.holds(ix.sim.beats[b]["preconditions"], self.cur):
                self.hit("R2-precondition", "beat-precondition", f"「{ix.beat(b)}」の前提が、いまは成り立っていない")
            parents = ix.sim.parents[b]
            if any(self.state["beats"].get(f) not in OCCURRED for f, ty, _ in parents if ty == "requires"):
                self.hit(
                    "R2-precondition", "beat-requires", f"「{ix.beat(b)}」の前に起きるはずの出来事が、まだ起きていない"
                )

    def op_set(self, e: Json) -> None:
        v, x = e["var"], e["value"]
        if v in TERMINAL and self.cur.get(v) == TERMINAL[v] and x != TERMINAL[v]:
            self.hit("R2-precondition", "no-resurrection", "処刑された者は生き返らない")
        if v == "var.player.location":
            if x not in reach(self.ix, self.state, self.cur):
                role = self.ix.roles[self.state["role"]]
                self.hit("R7-capability", "no-access", f"{role['name']}は{self.ix.place(x)}に入れない")
            self.walk("player", self.cur["var.player.location"], x)

    def op_relocate(self, e: Json) -> None:
        ch = e["character"]
        dead = (self.cur.get("var.hostage.fate") == "executed" and self.cur.get("var.hostage.who") == ch) or (
            ch == "char.melos" and self.cur.get("var.melos.custody") == "executed"
        )
        if dead:
            self.hit("R2-precondition", "no-resurrection", "処刑された者は生き返らない")
        self.walk(ch, self.where.get(ch), e["place"])

    def walk(self, who: str, src: str | None, dst: str) -> None:
        """R3: a player change of place, or a relocate outside the schedule, must not take longer than dt along the
        shortest route over places.adjacent (W-1 travel_minutes). Characters moving by schedule are governed by the
        schedule, not here (backend-design 2.4); relocates in candidate events are all outside the schedule.

        R3：プレイヤーの場所の移動や予定外の relocate は、places.adjacent の最短の道のり（W-1 travel_minutes）が dt を
        超えてはならない。予定どおりに動く登場人物は予定に従い、ここでは見ない（backend-design 2.4）。候補イベントの
        relocate はすべて予定外のもの。
        """
        if src is None or src == dst:
            return
        d = travel_minutes(self.ix.world, src, dst)
        total = self.walked.get(who, 0) + (10**9 if d is None else d)
        self.walked[who] = total
        if total > self.cand.get("dt", 0):
            far = "たどり着けない" if d is None else f"少なくとも{d}分かかる"
            self.hit(
                "R3-time",
                "travel",
                f"{self.ix.who(who)}が{self.ix.place(src)}から{self.ix.place(dst)}へ行くには{far}"
                f"（この出来事は{self.cand.get('dt', 0)}分）",
            )

    def op_learn(self, e: Json) -> None:
        ix, f = self.ix, e["fact"]
        fact = ix.facts.get(f)
        if fact is not None and fact["trueFrom"] != "pre" and self.state["beats"].get(fact["trueFrom"]) not in OCCURRED:
            self.hit("R4-knowledge", "fact-not-yet", f"「{ix.fact(f)}」は、この時点ではまだ事実ではない")
        elif (self.actor == "player" or self.actor in ix.chars) and not knows(ix.world, self.state, self.actor, f):
            self.hit("R4-knowledge", "actor-unaware", f"{ix.who(self.actor)}は、この時点で「{ix.fact(f)}」を知らない")
        # More than judge(): the person told must be nearby (R7 "at the same place as the target").
        # judge() より多く判定：伝える相手がそばにいること（R7「対象と同じ場所」）。
        if e["character"] != self.actor and not self.here(e["character"]):
            self.hit("R7-capability", "target-away", f"{ix.who(e['character'])}は、いまここにいない")

    def op_improv(self, e: Json) -> None:
        ix, ch, text = self.ix, e["character"], e["statement"]
        # Shared rule library, the same scope as output-side monitoring and E2.
        # 共有の規則ライブラリで、出力側の監視や E2 と同じ範囲。
        for said in spoilers(ix.world, self.state, ch, text).values():
            self.hit(
                "R4-knowledge",
                "spoiler",
                f"{ix.who(ch)}の話に、まだ知らないはずのこと（{'、'.join(said)}）が入っている",
            )

    def op_hold(self, e: Json) -> None:
        ix, item, to = self.ix, e["item"], e.get("to")
        held = self.cur.get(item)
        # judge(): what the player hands over or uses up must be in the player's hands.
        # judge()：プレイヤーが渡す・使い切る物はプレイヤーの手もとにあること。
        if self.actor == "player" and held != "player":
            self.hit("R7-capability", "not-holding", f"{ix.item(item)}は、プレイヤーの手もとにない")
        # More than judge(): when it names whose hands it comes from.
        # judge() より多く判定：誰の手からかが明記されているとき。
        elif "from" in e and e["from"] is not None and held != e["from"]:
            self.hit("R7-capability", "not-holding", f"{ix.item(item)}は、{ix.who(e['from'])}の手もとにない")
        if to not in (None, "player", self.actor) and not self.here(to):
            self.hit("R7-capability", "target-away", f"{ix.who(to)}はここにいないので、渡せない")

    def op_promise(self, e: Json) -> None:
        if e.get("change") != "made":
            return
        # More than judge(): promises are made face to face, so the other party must be nearby.
        # judge() より多く判定：約束は面と向かって交わすので、相手がそばにいること。
        for k in ("from", "to"):
            x = e.get(k)
            if x not in (None, "player", self.actor) and not self.here(x):
                self.hit("R7-capability", "target-away", f"{self.ix.who(x)}は、いまここにいない")

    def affordance(self) -> None:
        """A situational action's place, roles, when and needed item (the last part of judge()'s R7). Conditions use
        the state at the start of this turn.

        状況アクションの place、roles、when、要る物（judge() の R7 の最後の部分）。条件はこのターン開始時の状態で見る。
        """
        act = self.turn.act or {}
        a = self.ix.affs.get(act.get("affordance") or "")
        if a is None:
            return
        label, start = a["label"], flat(self.state)
        if a["place"] != self.ppl:
            self.hit("R7-capability", "affordance-place", f"「{label}」は{self.ix.place(a['place'])}でしかできない")
        if a.get("roles") and self.state["role"] not in a["roles"]:
            self.hit("R7-capability", "affordance-role", f"この身分では「{label}」はできない")
        if a.get("when") and not self.ix.sim.holds(a["when"], start):
            self.hit("R7-capability", "affordance-when", f"いまは「{label}」ができない")
        it = self.ix.items.get(a.get("item") or "")
        if it and not it.get("portable") and self.ppl not in it.get("at", []):
            self.hit("R7-capability", "affordance-item", f"「{label}」に要る{self.ix.item(it['id'])}が、ここにない")
        elif it and it.get("portable") and start.get(it["id"]) != "player":
            self.hit("R7-capability", "affordance-item", f"「{label}」に要る{self.ix.item(it['id'])}が、手もとにない")

    def safety(self) -> None:
        """R6's rule part: check every summary and improvised fact for personal-information patterns and for 8
        consecutive characters identical to the player's words; candidates with effects are checked for step 0 flags.

        R6 の規則部分：各要約と即興設定について、個人情報のパターンと、
        プレイヤーの発話と 8 文字連続で一致するかを調べる。
        効果のあるものは第 0 ステップの印を調べる。
        """
        texts = [self.cand.get("summary", "")] + [e["statement"] for e in self.effects if e.get("op") == "improv"]
        if any(has_pii(x) for x in texts):
            self.hit(
                "R6-safety", "pii-pattern", "現実の個人情報らしいもの（電話番号、メールアドレス、住所）が入っている"
            )
        said = self.turn.said
        if said and any(lcs_len(said, x) >= VERBATIM for x in texts):
            self.hit("R6-safety", "verbatim", "プレイヤーの言葉を、そのまま書き写している")
        if self.effects:
            for flag in sorted(self.turn.flags & set(FLAG_REASON)):
                self.hit("R6-safety", "flag-" + flag, FLAG_REASON[flag])


def judge(
    world: Json, state: SimState, cand: Json, effects: Sequence[Json] | None = None, turn: Turn = NO_TURN
) -> list[Hit]:
    """Step 3 judges one candidate event (state is not changed). No effects given = the candidate's effects. Returns
    the rules violated; empty = step 3 passed.

    第 3 ステップで 1 つの候補イベントを判定する（state は変えない）。effects を渡さなければ候補の effects。
    違反した規則を返し、空なら第 3 ステップを通った。
    """
    effs = list(cand.get("effects", []) if effects is None else effects)
    return _Judge(index(world), state, cand, effs, turn).run()


def failed(hits: Iterable[Hit]) -> list[str]:
    """The violated rules, in RULES order (the first one is the main rule).

    違反した規則を RULES の順に（最初のものが主な規則）。
    """
    rules = {h.rule for h in hits}
    return [r for r in RULES if r in rules]


def rule_rows(hits: Sequence[Hit], model: Mapping[str, Json] | None = None) -> list[Json]:
    """The `rules` of check() in api-contract section 7: pass / fail / skipped (+ reason) per rule. model = what step 4
    gave, {rule: {status, reason}}; if step 4 didn't run, R5 and the rest of R6 are recorded as skipped.

    api-contract 第 7 節 check() の `rules`：規則ごとに pass / fail / skipped（+ reason）。model = 第 4 ステップが
    返した {規則: {status, reason}}。第 4 ステップを実行していなければ R5 と R6 の残りは skipped とする。
    """
    out = []
    for r in RULES:
        mine = [h for h in hits if h.rule == r]
        got = (model or {}).get(r)
        if mine:
            out.append({"rule": r, "status": "fail", "reason": mine[0].reason})
        elif got is not None and got["status"] == "fail":
            out.append({"rule": r, "status": "fail", "reason": got["reason"]})
        elif r in STEP3 or got is not None:
            out.append({"rule": r, "status": "pass"})
        else:
            out.append({"rule": r, "status": "skipped", "reason": "モデル検査を行っていない"})
    return out


def fill_ids(effects: Sequence[Mapping[str, Any]], ids: IdGen) -> list[Json]:
    """Assign a promiseId when a promise is made, and a factId to an improvised fact without one (assigned only at
    commit; S-2's candidates don't carry them).

    約束が成立したら promiseId を、factId のない即興設定には factId を割り当てる（コミット時にだけ割り当て、S-2 の
    候補には付いていない）。
    """
    out = []
    for given in effects:
        e: dict[str, Any] = copy.deepcopy(dict(given))
        if e.get("op") == "promise" and e.get("change") == "made" and not e.get("promiseId"):
            e["promiseId"] = ids.new("prm")
        if e.get("op") == "improv" and not e.get("factId"):
            e["factId"] = ids.new("rf")
        out.append(e)
    return out


def trial(world: Json, state: SimState, cand: Json, effects: Sequence[Json]) -> SimState:
    """Trial-apply a passing candidate to the state, so later candidates in the same turn are judged after it. The
    clock doesn't move (dt only counts at commit).

    通った候補を状態に試算し、同じターンの後の候補はその後で判定する。時計は動かさない（dt はコミット時にだけ数える）。
    """
    if not effects:
        return state
    ev = {
        "t": state["t"],
        "dt": 0,
        "origin": cand.get("origin", "turn"),
        "type": cand.get("type", "say"),
        "effects": effects,
    }
    return apply(world, state, ev)


def check_candidates(
    world: Json, state: SimState, candidates: Sequence[Json], ids: IdGen, turn: Turn = NO_TURN
) -> list[Checked]:
    """Run step 3 only (no model check or rewriting): judge in order, trial-applying earlier passing candidates to
    the state first.

    第 3 ステップだけを実行する（モデルの検査と書き換えはなし）：順に判定し、
    先に通った候補を状態に試算してから次を見る。
    """
    out = []
    now = state
    for cand in candidates:
        effects = fill_ids(cand.get("effects", []), ids)
        hits = judge(world, now, cand, effects, turn)
        check: Json = {
            "status": "rejected" if hits else "passed",
            "attempts": 1,
            "failedRules": failed(hits),
            "checker": CHECKER,
        }
        if hits:
            check["reason"] = hits[0].reason
        out.append(Checked(dict(cand), effects, check, rule_rows(hits), hits))
        if not hits:
            now = trial(world, now, cand, effects)
    return out
