"""文本模型的接口和三种实现：假模型（`fake`）、回放（`replay`）、真模型（`real`，只在 Mac 上：Claude 走
`models/claude.py`，Google 走 `models/vertex.py`，按提示类型选，`config.TEXT`）。

- 假模型：每种提示一个确定的、过 Schema 的默认输出（分流 = 可能，提取 = 没有候选，检查 = 全过，改写 = 原样，
  降级 = 做不到，回答 = 一句固定的话）。`fixtures/fake-text/*.json` 的规则按提示类型和条件覆盖默认值，也能注入延迟和
  错误（测时限、重发和 429）。规则的写法见 `fixtures/fake-text/README.md`。
- 回放：按（供应商、模型、提示版本、规范化请求的 sha256）从 `fixtures/model-replays/*.jsonl` 查，查不到抛
  `ReplayMissing`，不悄悄回空、不退回假模型。同一个请求在 Google 下录的回放，换到 Claude 查不到。

回放一行的格式（Mac 上录真模型、E-0 的 live 存回放都用它）：
`key`、`kind`（提示类型）、`provider`、`model`、`promptVersion`、`request`（脱敏后）、`response`、`usage`
（`inputTokens`、`outputTokens`；Google 另有 `cachedTokens`、`thoughtTokens`，Claude 另有 `cacheReadTokens`、
`cacheWriteTokens`）、`costUsd`、`recordedAt`（以 Z 结尾）。`model`：Google 写模型 ID，Claude 只写档名加版本
（如 `sonnet-5.5`，模型 ID 不进仓库）。`key` = `<provider>|<model>|<promptVersion>|<请求的 sha256>`
（共用包 `zoujin_llm.replay_key`，和数据的评审员同一个函数）。
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from zoujin_llm import BudgetStop, ModelCallFailed, RateLimited, Stop, canonical
from zoujin_llm import replay_key as _replay_key

from zoujin_backend.config import TEXT, ModelMode, TextSpec, text_spec
from zoujin_backend.models.prompts import MODEL_RULES, PROMPTS

if TYPE_CHECKING:
    from zoujin_backend.config import Settings

log = logging.getLogger("zoujin.models")

Json = Any

# 要整次停下的错误（`Stop`：`BudgetStop`、`RateLimited`）和 `ModelCallFailed` 在共用包里，叙事者和评审员同一套
__all__ = ["BudgetStop", "ModelCallFailed", "RateLimited", "Stop", "canonical"]


class ReplayMissing(LookupError):
    """回放里查不到这次调用（回放缺失或过期）。E-0 按类名认。"""


class BadOutput(ValueError):
    """模型的输出不是 JSON 或不过 Schema：算这次调用失败，按时限的规则重发一次。`cost_usd`：这次调用已经花的钱
    （真客户端拿到了回答才知道不合格，已经记了账；叙事者把它也加进这一轮的花费）。"""

    def __init__(self, message: str, cost_usd: float = 0.0) -> None:
        super().__init__(message)
        self.cost_usd = cost_usd


@dataclass(frozen=True)
class TextResult:
    output: Json
    kind: str
    model: str
    prompt_version: str
    usage: dict[str, int]
    cost_usd: float


class TextModel(Protocol):
    mode: ModelMode

    async def call(self, kind: str, request: Json) -> TextResult: ...

    def cancelled_cost(self, kind: str, request: Json) -> float:
        """这次调用被时限取消时记多少钱（真客户端按调用前的预计，和账本那行同一个数；假模型、回放是 0）。"""
        ...


def replay_key(provider: str, model: str, prompt_version: str, request: Json) -> str:
    return _replay_key(provider, model, prompt_version, request)


def spec(kind: str) -> TextSpec:
    """这种提示走哪家、哪个模型（Claude 是档名加版本）、思考多深、时限多长（`config.TEXT`，加上 `ZJ_TEXT_MODELS`
    的换档）。"""
    if kind not in PROMPTS:
        raise ValueError(f"没有这种提示：{kind}")
    return text_spec(kind)


def model_and_version(kind: str) -> tuple[str, str]:
    return spec(kind).model, PROMPTS[kind].version


def key_of(kind: str, request: Json) -> str:
    model, version = model_and_version(kind)
    return replay_key(spec(kind).provider, model, version, request)


# —— 假模型 ——

NO_USAGE = {"inputTokens": 0, "outputTokens": 0}


def _check_all_pass(request: Mapping[str, Any]) -> Json:
    n = len(request.get("candidates", []))
    return {"results": [{"index": i, "rules": [{"rule": r, "status": "pass"} for r in MODEL_RULES]} for i in range(n)]}


def _rewrite_same(request: Mapping[str, Any]) -> Json:
    return {"candidate": copy.deepcopy(request.get("candidate")) if request.get("mode") == "rewrite" else None}


NARRATE_LINES = {  # 假模型的一行地の文：每种 status 一句（为测试写的）
    "done": "あなたは、そうした。",
    "partial": "思ったようには、いかなかった。",
    "refused": "それは、いまはかなわなかった。",
}

FAKE_FATES = {"witness": "刑場で、日没を見届けた。", "elsewhere": "刑場には行かず、日没を迎えた。"}


def _ending(request: Mapping[str, Any]) -> Json:
    """假模型的结局（B-9）：按输入确定地写一份能过校验的。尾声从最后几个事件的摘要拼，每句引用那个事件；
    这一局有人被处刑时跳过带禁用写法的摘要。"""
    forbidden = list(request.get("forbidden", []))
    events = [
        e
        for e in request.get("events", [])
        if not any(w in str(e.get("summary", "")) for w in forbidden)
        and (e.get("beat") or {}).get("to", "happened") == "happened"  # 没照原作发生的节拍，summary 是原作那一句
    ]
    events = events or list(request.get("events", []))
    last = [str(events[-1]["eventId"])] if events else []
    picked = events[-3:]
    epilogue = [{"sentence": f"{str(e['summary']).rstrip('。')}。", "cites": [str(e["eventId"])]} for e in picked]
    while len(epilogue) < 3:
        epilogue.insert(0, {"sentence": "その日も、日は西へ傾いていった。", "cites": last})
    beats = request.get("changedBeats") or []
    fate = (request.get("place") or {}).get("fate", "elsewhere")
    return {
        "epilogue": epilogue,
        "contrast": {
            "original": "原作では、物語は書かれたとおりに進んだ。",
            "yours": "あなたの世界では、別の日没が来た。" if beats else "あなたの世界でも、物語は同じ結末を迎えた。",
            "beat": beats[0]["beat"] if beats else None,
        },
        "subtitle": str((request.get("outcome") or {}).get("label", "物語は終わった"))[:26],
        "cardContrast": "原作との違いは、あなたがそこにいたことだった。",
        "you": {
            "title": {"text": f"見届けた{request.get('role', '旅の者')}"[:14], "cites": last},
            "fate": {"text": FAKE_FATES.get(str(fate), FAKE_FATES["elsewhere"]), "cites": last},
            "didForYou": [],
            "youDid": [],
        },
        "characters": [
            {
                "character": c["character"],
                "yours": [{"sentence": f"{c['name']}の一日は、こうして暮れた。", "cites": last}],
            }
            for c in request.get("characters", [])
            if not c.get("unchanged")
        ],
    }


def _ending_broken(request: Mapping[str, Any]) -> Json:
    """`broken: true` 的结局：引用全空（cite-empty），测重写和模板。"""
    out = _ending(request)
    for row in out["epilogue"]:
        row["cites"] = []
    return out


DEFAULTS: dict[str, Callable[[Mapping[str, Any]], Json]] = {
    "triage": lambda r: {"route": "maybe"},
    "extract": lambda r: {"candidates": []},  # 没有候选事件：只走时钟
    "check": _check_all_pass,
    "rewrite": _rewrite_same,  # 改写 = 原样；降级 = 做不到
    "reply": lambda r: {"text": "……そうか。"},
    "narrate": lambda r: {"text": NARRATE_LINES.get(str(r.get("status")), NARRATE_LINES["done"])},
    "plan": lambda r: {  # 不成行，替代去处是第一个给定去处（B-3 卡「接口」）
        "accepted": False,
        "label": None,
        "with": [],
        "effects": [],
        "narration": ["その道は、いまは開けていなかった。"],
        "alternative": {"exit": r["options"][0]["optionId"]} if r.get("options") else None,
    },
    "ending": _ending,
}
ERRORS = ("rate-limit", "invalid", "unavailable")


def _summaries(request: Mapping[str, Any]) -> list[str]:
    cands = request.get("candidates") or ([request["candidate"]] if request.get("candidate") else [])
    return [str(c.get("summary", "")) for c in cands]


def _matches(when: Mapping[str, Any], request: Mapping[str, Any]) -> bool:
    """fake-text 规则的条件，每个键都满足才算：`playerContains` / `replyContains` 看这一轮的原话里有没有这几个字，
    `summaryContains` 看候选的摘要，`character` 比这一轮的人物，`confirmOpen` 看提取的请求里有没有在等回答的反问
    （B-4 的 `<confirm>`），其他键要等于请求里同名的值。"""
    turn = request.get("turn") or {}
    for k, v in when.items():
        if k == "playerContains":
            ok = v in (turn.get("player") or "")
        elif k == "replyContains":
            ok = v in (turn.get("reply") or "")
        elif k == "summaryContains":
            ok = any(v in s for s in _summaries(request))
        elif k == "character":
            ok = (turn.get("character") or request.get("character")) == v
        elif k == "confirmOpen":
            ok = ("confirm" in request) == v
        else:
            ok = request.get(k) == v
        if not ok:
            return False
    return True


class FakeText:
    mode: ModelMode = "fake"

    def __init__(self, rules_dir: Path | None = None, rules: list[Json] | None = None, seed: int | None = None) -> None:
        self.seed = seed  # 模拟局的种子（B-5）：现在按输入确定地回答、用不上，以后要随机时用它
        self.rules: list[dict[str, Any]] = []
        self.used: dict[int, int] = {}  # 规则序号 → 用过几次（`times`）
        self.calls: list[tuple[str, Json]] = []  # 测试看调用了什么
        if rules_dir is not None and rules_dir.is_dir():
            for p in sorted(rules_dir.glob("*.json")):
                for r in json.loads(p.read_text(encoding="utf-8"))["rules"]:
                    self.rules.append(self._rule(r, p.name))
        for r in rules or []:
            self.rules.append(self._rule(r, "<test>"))

    @staticmethod
    def _rule(r: Json, source: str) -> dict[str, Any]:
        if r["kind"] not in DEFAULTS:
            raise ValueError(f"{source}：没有这种提示 {r['kind']}")
        if r.get("error") not in (None, *ERRORS):
            raise ValueError(f"{source}：不认识的 error {r['error']!r}（{' / '.join(ERRORS)}）")
        return {**r, "source": source}

    def _pick(self, kind: str, request: Json) -> dict[str, Any] | None:
        for i, r in enumerate(self.rules):
            if r["kind"] != kind or not _matches(r.get("when", {}), request):
                continue
            if "times" in r and self.used.get(i, 0) >= r["times"]:
                continue
            self.used[i] = self.used.get(i, 0) + 1
            return r
        return None

    async def call(self, kind: str, request: Json) -> TextResult:
        model, version = model_and_version(kind)
        self.calls.append((kind, copy.deepcopy(request)))
        rule = self._pick(kind, request)
        output = DEFAULTS[kind](request)
        if rule is not None:
            if rule.get("latencyMs"):
                await asyncio.sleep(rule["latencyMs"] / 1000)
            if rule.get("error") == "rate-limit":
                raise RateLimited(f"假模型：{kind} 回 429（{rule['source']}）")
            if rule.get("error") == "invalid":
                raise BadOutput(f"假模型：{kind} 的输出不过 Schema（{rule['source']}）")
            if rule.get("error") == "unavailable":
                raise ModelCallFailed(f"假模型：{kind} 调用失败（{rule['source']}）")
            if "output" in rule:
                output = copy.deepcopy(rule["output"])
            elif "fail" in rule and kind == "check":
                output = _check_failing(request, rule)
            elif rule.get("broken") and kind == "ending":
                output = _ending_broken(request)
        return TextResult(output, kind, model, version, dict(NO_USAGE), 0.0)

    def cancelled_cost(self, kind: str, request: Json) -> float:
        return 0.0


def _check_failing(request: Mapping[str, Any], rule: Mapping[str, Any]) -> Json:
    """`fail` 的简写：摘要含 `when.summaryContains` 的候选（没写就是全部）这条规则判 fail，其余全过。"""
    out = _check_all_pass(request)
    needle = rule.get("when", {}).get("summaryContains")
    for res, cand in zip(out["results"], request.get("candidates", []), strict=True):
        if needle is None or needle in str(cand.get("summary", "")):
            for row in res["rules"]:
                if row["rule"] == rule["fail"]["rule"]:
                    row["status"] = "fail"
                    row["reason"] = rule["fail"].get("reason", "モデル検査で不合格")
    return out


# —— 回放 ——


class ReplayText:
    mode: ModelMode = "replay"

    def __init__(self, replay_dir: Path) -> None:
        self.records: dict[str, Json] = {}
        for p in sorted(replay_dir.glob("*.jsonl")):
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                rec = json.loads(line)
                want = replay_key(rec.get("provider", ""), rec["model"], rec["promptVersion"], rec["request"])
                if rec["key"] != want:
                    raise ValueError(f"{p.name}:{n} 的 key 和内容对不上（应为 {want}）")
                self.records[rec["key"]] = rec

    async def call(self, kind: str, request: Json) -> TextResult:
        model, version = model_and_version(kind)
        rec = self.records.get(key_of(kind, request))
        if rec is None:
            raise ReplayMissing(f"回放缺失或过期：{kind}（{spec(kind).provider} {model}，提示 {version}）")
        return TextResult(
            copy.deepcopy(rec["response"]), kind, model, version, dict(rec["usage"]), float(rec["costUsd"])
        )

    def cancelled_cost(self, kind: str, request: Json) -> float:
        return 0.0


def record(
    kind: str,
    request: Json,
    response: Json,
    *,
    recorded_at: str,
    usage: Mapping[str, int] | None = None,
    cost_usd: float = 0.0,
) -> Json:
    """一行回放（假模型录的 fixture、真模型录的回放都用它）。"""
    model, version = model_and_version(kind)
    return {
        "key": key_of(kind, request),
        "kind": kind,
        "provider": spec(kind).provider,
        "model": model,
        "promptVersion": version,
        "request": request,
        "response": response,
        "usage": dict(usage or NO_USAGE),
        "costUsd": cost_usd,
        "recordedAt": recorded_at,
    }


class Recording:
    """录回放（`ZJ_RECORD_REPLAYS=<目录>`）：每次成功的调用按回放格式在 `<目录>/<kind>.jsonl` 追加一行。
    Mac 上录真模型用；假模型也能录（测试回放这条路）。只录合成输入（S-2 的条目、评测用例），不录真人玩家的话。"""

    def __init__(self, inner: TextModel, directory: Path) -> None:
        self.inner = inner
        self.mode: ModelMode = inner.mode
        self.directory = directory

    async def call(self, kind: str, request: Json) -> TextResult:
        r = await self.inner.call(kind, request)
        line = record(kind, request, r.output, recorded_at=now_z(), usage=r.usage, cost_usd=r.cost_usd)
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory / f"{kind}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")
        return r

    def cancelled_cost(self, kind: str, request: Json) -> float:
        return self.inner.cancelled_cost(kind, request)


def now_z() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Routed:
    """真模型：每种提示按 `config.TEXT` 的 provider 交给那一家的客户端（一次评测里两家可以都有：`reply` 走 Google）。
    客户端第一次要用时才建：只调 Claude 的跑（S-2、小测）不要求 Vertex 的环境变量。"""

    mode: ModelMode = "real"

    def __init__(self, makers: Mapping[str, Callable[[], TextModel]]) -> None:
        self._makers = dict(makers)
        self._clients: dict[str, TextModel] = {}

    def client(self, provider: str) -> TextModel:
        if provider not in self._clients:
            self._clients[provider] = self._makers[provider]()
        return self._clients[provider]

    async def call(self, kind: str, request: Json) -> TextResult:
        return await self.client(spec(kind).provider).call(kind, request)

    def cancelled_cost(self, kind: str, request: Json) -> float:
        return self.client(spec(kind).provider).cancelled_cost(kind, request)


def real_text_model(settings: Settings) -> Routed:
    """real：Claude 的客户端当场建（少 Key、模型 ID、上限就退出，不发请求），Google 的到第一次调 `reply` 时才建。"""
    # 只在 real 时 import，别的模式不碰真客户端
    from zoujin_backend.models.claude import claude_text
    from zoujin_backend.models.vertex import real_text

    routed = Routed({"claude": lambda: claude_text(settings), "google": lambda: real_text(settings)})
    if any(spec(k).provider == "claude" for k in TEXT):
        routed.client("claude")
    return routed


def text_model(
    mode: ModelMode,
    *,
    fake_rules: Path | None,
    replays: Path,
    settings: Settings | None = None,
    seed: int | None = None,
) -> TextModel:
    """settings 给了、设了 `record_replays`：fake 和 real 的调用录下来（replay 不录）。seed 只给假模型（B-5）。"""
    inner: TextModel
    if mode == "fake":
        inner = FakeText(fake_rules, seed=seed)
    elif mode == "replay":
        return ReplayText(replays)
    else:
        if settings is None:
            raise ValueError("ZJ_MODEL=real 要用 Settings 建客户端（账本、上限、录回放的目录）")
        inner = real_text_model(settings)
    if settings is not None and settings.record_replays is not None:
        return Recording(inner, settings.record_replays)
    return inner
