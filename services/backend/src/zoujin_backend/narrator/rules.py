"""叙事者第 3 步：确定性规则 R1〜R4、R7 和 R6 的规则部分（backend-design 2.4，契约第 3 节），不调模型。

- 判法至少覆盖 `evals/s2/README.md`「确定性规则的最简判法」（`evals/s2_check.py` 的 `judge()`）：它报的这里都报，
  `tests/test_rules.py` 逐条对照。比它多判的几处写在各函数里（行为者和对象要在场、不在场的人物、给东西的人手上要有）。
- 世界规则（条件求值、应用效果、`valueRequires`、`OCCURRED`、`knows`、`travel_minutes`、引用和取值的检查）
  只从 W-1 拿，这里不另写一份。
- R5 和 R6 的其余部分是第 4 步（模型检查，`narrator/pipeline.py`）。

一个候选的效果按顺序判：前面的效果先在一份平铺的状态（变量 + 物品持有者）和人物所在地上生效，后面的在它之后判
（和 `judge()`、`Sim.value_requires` 一样）。同一轮的几个候选也按顺序，前面通过的先试算进状态（`check_candidates`）。
`reason` 是一句日语（契约 CheckResult.reason），用世界模型里的名字，不含玩家原话。
"""

from __future__ import annotations

import copy
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from zoujin_backend.ids import IdGen
from zoujin_backend.safety import pii
from zoujin_worldsim import OCCURRED, Sim, SimState, activity, apply, check_effects, flat, knows, travel_minutes

Json = Any

RULES = ("R1-anchor", "R2-precondition", "R3-time", "R4-knowledge", "R5-persona", "R6-safety", "R7-capability")
STEP3 = ("R1-anchor", "R2-precondition", "R3-time", "R4-knowledge", "R7-capability")  # 只由第 3 步判
MODEL_ONLY = ("R5-persona",)  # 只由第 4 步判；R6 两步都判，R1 写在文字里的那部分也是第 4 步
VERSION = "b3.1"  # 判法改了就加一（b3.1：幕末打算的对象按「这一段能碰到」判在场）
CHECKER = f"rules@{VERSION}"

# 死了的不复活（rule.no-resurrection）：变量到了这个值就不能再改回别的
TERMINAL = {"var.hostage.fate": "executed", "var.player.custody": "executed", "var.melos.custody": "executed"}
# R6 的规则部分：个人信息的模式（`safety.pii`，B-12 起和存原话、记忆过滤同一套），加上 judge() 核标注用的那条老写法
# （横线隔开的三段数字，不要求 0 开头；`evals/s2_check.py` 的 PII），和玩家原话连续 8 字相同
_D = "[0-9０-９]"
PII_EXTRA = re.compile(rf"{_D}{{2,4}}[-‐－]{_D}{{2,4}}[-‐－]{_D}{{3,4}}|[@＠][\w.-]+[.．]\w+|〒")


def has_pii(text: str | None) -> bool:
    return bool(text) and (bool(pii.find(text)) or PII_EXTRA.search(text or "") is not None)


VERBATIM = 8
FLAG_REASON = {
    "injection": "この発話は、物語の外からの指示として止められた",
    "pii": "この発話に現実の個人情報が含まれていた",
    "harmful": "この発話は、物語に書けない内容として止められた",  # B-12：Model Armor の HIGH、分類器の拒答
    "unscreened": "この発話は、安全の確認がとれなかった",  # B-12：分類器が二度とも判定できなかった（最も控えめに）
}
BEAT_TO = {
    "prevented": "起きなかったこと",
    "delayed": "遅らせること",
    "hastened": "早めること",
    "altered": "変えること",
}
BEAT_RESULT = {"happened": "もう起きた", "altered": "もう形を変えて起きた", "prevented": "もう起きないと決まった"}
SHAPE = {  # W-1 check_effects 的代码 → 规则和一句日语（引用、取值、op 不对：这个世界里做不到）
    "unknown-id": ("R7-capability", "この世界にいない人、ない物や場所が出てくる"),
    "bad-value": ("R7-capability", "その値は、この世界では取りえない"),
    "bad-op": ("R7-capability", "その変化は、この世界の決まりでは起こせない"),
    "duplicate-id": ("R7-capability", "同じ設定や約束を二度記録しようとしている"),
}


@dataclass(frozen=True)
class Turn:
    """第 3 步要的这一轮。said = 玩家原话（只用来比 8 字照抄，不进日志）；act = 动作（`kind`、`target`、`params`，
    有情境动作时带 `affordance`）；flags = 第 0 步的筛查标记（`injection`、`pii`、`harmful`、`unscreened`、
    `ambiguous`，B-12 的安全筛查填）。"""

    said: str = ""
    act: Mapping[str, Any] | None = None
    flags: frozenset[str] = frozenset()


NO_TURN = Turn()


@dataclass(frozen=True)
class Hit:
    rule: str
    code: str  # 判法名（Trace、指标和测试用，不含原话）
    reason: str  # 一句日语


@dataclass
class Checked:
    """一个候选事件和它的检查结果。effects 是候选原本的（promiseId 等已补上）；提交时被否决的写空 effects。"""

    candidate: Json
    effects: list[Json]
    check: Json
    rules: list[Json] = field(default_factory=list)
    hits: list[Hit] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.check["status"] != "rejected")


class Index:
    """一本书的世界模型，按 ID 建好索引（每个世界模型版本一份，见 `index()`）。"""

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

    @cached_property
    def spoilers(self) -> list[tuple[str, list[str]]]:
        return [(f["id"], list(f["spoilerTerms"])) for f in self.world["facts"] if f.get("spoilerTerms")]

    # —— 名字（日语 reason 用） ——

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
    """按 worldModelVersion 缓存（世界模型只读）。"""
    key = str(world["worldModelVersion"])
    got = _INDEX.get(key)
    if got is None or got.world is not world:
        got = _INDEX[key] = Index(world)
    return got


# —— 世界状态上的几个判断（W-1 没有的，B-2 卡：先问数据要不要进 W-1，等答复前写在这里） ——


def anchor_locked(ix: Index, state: SimState) -> dict[str, Json]:
    """已发生的锚点节拍写下、之后没有别的节拍改过的变量 → 值（推翻它 = R1）。和 judge() 的 anchor_locked 一样。"""
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
    """S-077 ⑩：此刻不在场（例：切片里石工房的两人第一幕在屋里）。快照照样列出，`activity: absent`。
    判法在 W-1 的 `activity()`：开局 absent、还没被节拍或事件带走的人物。"""
    return activity(ix.world, state, who) == "absent"


def reach(ix: Index, state: SimState, cur: Mapping[str, Any]) -> set[str]:
    """玩家此刻能进的地点：身份的 access + 此刻成立的 conditionalAccess + 现在所在的地点。"""
    role = ix.roles[state["role"]]
    ok = set(role["access"]) | {
        ca["place"] for ca in role.get("conditionalAccess", []) if ix.sim.holds(ca["when"], cur)
    }
    ok.add(cur["var.player.location"])
    return ok


def lcs_len(a: str, b: str) -> int:
    """最长公共子串的长度（judge() 和评测的 no_verbatim_quotes 同样的比法）。"""
    best, prev = 0, [0] * (len(b) + 1)
    for x in a:
        now = [0] * (len(b) + 1)
        for j, y in enumerate(b, 1):
            if x == y:
                now[j] = prev[j - 1] + 1
                best = max(best, now[j])
        prev = now
    return best


# —— 判法 ——


class _Judge:
    """一个候选事件的第 3 步。"""

    def __init__(self, ix: Index, state: SimState, cand: Json, effects: Sequence[Json], turn: Turn) -> None:
        self.ix, self.state, self.cand, self.effects, self.turn = ix, state, cand, effects, turn
        self.hits: list[Hit] = []
        self.cur: dict[str, Any] = flat(state)  # 平铺的状态，按效果的顺序生效
        self.where: dict[str, str] = dict(state["locations"])
        self.ppl: str = state["vars"]["var.player.location"]
        self.actor: str = cand.get("actor", "")
        self.walked: dict[str, int] = {}  # 这个候选里谁走了几分钟（R3：几段路加起来不超过 dt）

    def hit(self, rule: str, code: str, reason: str) -> None:
        if not any(h.rule == rule and h.reason == reason for h in self.hits):
            self.hits.append(Hit(rule, code, reason))

    def here(self, who: str | None) -> bool:
        """在玩家身边：玩家自己；或不是不在场、和玩家同一地点或玩家正跟着他（幕末的打算见下）。"""
        if who in (None, "player"):
            return True
        assert who is not None
        if (self.turn.act or {}).get("kind") == "plan":
            # 幕末的打算（B-3）：说的是跳过的这段时间里要做的事，对象在玩家能去的地方就算碰得到（此刻不在场也算）
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

    # 引用、取值、op、约定的状态、节拍的改动能不能合、valueRequires：W-1 的 check_effects
    def shape(self) -> set[int]:
        """报引用、取值、op 的问题，返回判法和试算用不了的效果的下标（节拍不存在或 `to` 不对、`inc` 的变量不对）。
        别的有问题的效果照判（例：取值不合法的 `set` 照样看锚点和权限），和 judge() 一样不因为形状漏报。"""
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
            # beat-happened、beat-has-result 由 op_beat 判（同样的条件，reason 用节拍名）
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
        if to == "happened":  # 节拍到点由系统结算，要早用 hastened（契约 2.4.1；W-1 也报 beat-happened）
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
        """R3：玩家换地点、排程以外的 relocate，按 places.adjacent 的最短路程（W-1 travel_minutes）不超过 dt。
        按排程走的人物看排程，不在这里（backend-design 2.4）；候选事件里的 relocate 都是排程以外的。"""
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
        # 比 judge() 多：告诉的对象要在身边（R7「和对象在同一地点」）
        if e["character"] != self.actor and not self.here(e["character"]):
            self.hit("R7-capability", "target-away", f"{ix.who(e['character'])}は、いまここにいない")

    def op_improv(self, e: Json) -> None:
        ix, ch, text = self.ix, e["character"], e["statement"]
        for fid, terms in ix.spoilers:
            said = [x for x in terms if x in text]
            if said and not knows(ix.world, self.state, ch, fid):
                self.hit(
                    "R4-knowledge",
                    "spoiler",
                    f"{ix.who(ch)}の話に、まだ知らないはずのこと（{'、'.join(said)}）が入っている",
                )

    def op_hold(self, e: Json) -> None:
        ix, item, to = self.ix, e["item"], e.get("to")
        held = self.cur.get(item)
        if self.actor == "player" and held != "player":  # judge()：玩家交出、用掉的东西要在玩家手上
            self.hit("R7-capability", "not-holding", f"{ix.item(item)}は、プレイヤーの手もとにない")
        elif "from" in e and e["from"] is not None and held != e["from"]:  # 比 judge() 多：写明了从谁手上
            self.hit("R7-capability", "not-holding", f"{ix.item(item)}は、{ix.who(e['from'])}の手もとにない")
        if to not in (None, "player", self.actor) and not self.here(to):
            self.hit("R7-capability", "target-away", f"{ix.who(to)}はここにいないので、渡せない")

    def op_promise(self, e: Json) -> None:
        if e.get("change") != "made":
            return
        for k in ("from", "to"):  # 比 judge() 多：约定当面立，对方要在身边
            x = e.get(k)
            if x not in (None, "player", self.actor) and not self.here(x):
                self.hit("R7-capability", "target-away", f"{self.ix.who(x)}は、いまここにいない")

    def affordance(self) -> None:
        """情境动作的 place、roles、when、要用的物品（judge() 的 R7 最后一段）。条件按这一轮开始时的状态。"""
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
        """R6 的规则部分：每条摘要和即兴设定查个人信息的模式、和玩家原话连续 8 字相同；有效果的查第 0 步的标记。"""
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
    """第 3 步判一个候选事件（不改 state）。effects 不给 = 候选的 effects。返回违反的规则，空 = 第 3 步过了。"""
    effs = list(cand.get("effects", []) if effects is None else effects)
    return _Judge(index(world), state, cand, effs, turn).run()


def failed(hits: Iterable[Hit]) -> list[str]:
    """违反的规则，按 RULES 的顺序（第一条是主规则）。"""
    rules = {h.rule for h in hits}
    return [r for r in RULES if r in rules]


def rule_rows(hits: Sequence[Hit], model: Mapping[str, Json] | None = None) -> list[Json]:
    """api-contract 第 7 节 check() 的 `rules`：每条规则 pass / fail / skipped（+ reason）。model = 第 4 步给的
    {规则: {status, reason}}，没跑第 4 步时 R5 和 R6 的其余部分记 skipped。"""
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
    """约定成立时分配 promiseId，即兴设定没有 factId 时分配（提交时才分配，S-2 的候选不带）。"""
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
    """把通过的候选试算进状态，同一轮后面的候选在它之后判。时钟不动（dt 在提交时才算）。"""
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
    """只跑第 3 步（没有模型检查和改写）：按顺序判，前面通过的候选先试算进状态。"""
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
