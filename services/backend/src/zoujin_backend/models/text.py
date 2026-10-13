"""The text model interface and its three implementations: fake model (`fake`), replay (`replay`), real model (`real`,
only on the Mac: Claude goes through `models/claude.py` and Google through `models/vertex.py`, chosen per prompt kind,
`config.TEXT`).

- Fake model: each prompt kind has one deterministic, Schema-passing default output (triage = possible, extraction =
  no candidates, check = all pass, rewrite = unchanged, downgrade = cannot be done, reply = one fixed line). The rules
  in `fixtures/fake-text/*.json` override the defaults by prompt kind and condition, and can also inject latency and
  errors (to test time limits, resends and 429). How to write rules: see `fixtures/fake-text/README.md`.
- Replay: looked up in `fixtures/model-replays/*.jsonl` by (provider, model, prompt version, sha256 of the normalized
  request); if not found, `ReplayMissing` is raised, with no silent empty answer and no fallback to the fake model. A
  replay recorded for a request under Google is not found after switching to Claude.

The format of one replay line (used both for recording real models on the Mac and for E-0's live run saving replays):
`key`, `kind` (prompt kind), `provider`, `model`, `promptVersion`, `request` (after redaction), `response`, `usage`
(`inputTokens`, `outputTokens`; Google also has `cachedTokens`, `thoughtTokens`, Claude also has `cacheReadTokens`,
`cacheWriteTokens`), `costUsd`, `recordedAt` (ending in Z). `model`: the model ID for Google, only the tier name plus
version for Claude (e.g. `sonnet-5.5`; model IDs stay out of the repo). `key` =
`<provider>|<model>|<promptVersion>|<sha256 of the request>` (the shared package's `zoujin_llm.replay_key`, the same
function as the data team's judge).

テキストモデルのインターフェースと 3 つの実装：偽モデル（`fake`）、リプレイ（`replay`）、実モデル（`real`。Mac 上のみ：
Claude は `models/claude.py`、Google は `models/vertex.py` を通り、プロンプトの種類ごとに選ぶ。`config.TEXT`）。

- 偽モデル：プロンプトの種類ごとに、決定的で Schema を通るデフォルト出力が 1 つある（振り分け = 可能性あり、抽出 =
  候補なし、チェック = 全通過、書き換え = 原文のまま、格下げ = できない、返答 = 決まった一言）。
  `fixtures/fake-text/*.json` のルールがプロンプトの種類と条件でデフォルトを上書きし、遅延やエラーも注入できる（時間
  制限、再送、429 のテスト用）。ルールの書き方は `fixtures/fake-text/README.md` を参照。
- リプレイ：（プロバイダ、モデル、プロンプトバージョン、正規化したリクエストの sha256）で
  `fixtures/model-replays/*.jsonl`
  から探し、見つからなければ `ReplayMissing` を投げる。黙って空を返したり、偽モデルにフォールバックしたりはしない。
  Google で録ったリクエストのリプレイは、Claude に切り替えると見つからない。

リプレイ 1 行の形式（Mac 上で実モデルを録るときも、E-0 の live がリプレイを保存するときも使う）：
`key`、`kind`（プロンプトの種類）、`provider`、`model`、`promptVersion`、`request`（マスキング後）、`response`、
`usage`（`inputTokens`、`outputTokens`。Google はほかに `cachedTokens`、`thoughtTokens`、Claude はほかに
`cacheReadTokens`、`cacheWriteTokens`）、`costUsd`、`recordedAt`（末尾は Z）。`model`：Google はモデル ID、Claude は
ティア名とバージョンだけ（例 `sonnet-5.5`。モデル ID はリポジトリに入れない）。`key` =
`<provider>|<model>|<promptVersion>|<リクエストの sha256>`（共用パッケージの `zoujin_llm.replay_key`。データ担当の
審査員と同じ関数）。
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

# The errors that stop the whole run (`Stop`: `BudgetStop`, `RateLimited`) and `ModelCallFailed` live in the shared
# package, the same set for the narrator and the judge
# 実行全体を止めるエラー（`Stop`：`BudgetStop`、`RateLimited`）と `ModelCallFailed` は共用パッケージにあり、ナレーターと
# 審査員で同じものを使う
__all__ = ["BudgetStop", "ModelCallFailed", "RateLimited", "Stop", "canonical"]


class ReplayMissing(LookupError):
    """This call was not found in the replays (replay missing or stale). E-0 recognizes it by class name.

    この呼び出しがリプレイに見つからない（リプレイが無いか期限切れ）。E-0 はクラス名で判別する。
    """


class BadOutput(ValueError):
    """The model's output is not JSON or fails the Schema: this call counts as failed and is resent once under the
    time-limit rules. `cost_usd`: what this call has already cost (the real client only learns the answer is unusable
    after receiving it, and has already recorded it in the ledger; the narrator also adds it to this turn's cost).

    モデルの出力が JSON でないか Schema を通らない：この呼び出しは失敗とみなし、時間制限の規則に従って 1 回再送する。
    `cost_usd`：この呼び出しですでにかかった費用（実クライアントは返答を受け取って初めて不合格と分かり、すでに台帳に
    記録している。ナレーターはこれもこのターンの費用に加える）。
    """

    def __init__(self, message: str, cost_usd: float = 0.0) -> None:
        super().__init__(message)
        self.cost_usd = cost_usd


class Refused(BadOutput):
    """The model's own safety filter refused to answer (Claude's `stop_reason: "refusal"`, no output). Safety screening
    treats it as harmful input (5.5); other prompts count it as a resend, like BadOutput.

    モデル自身の安全フィルターが回答を拒否した（Claude の `stop_reason: "refusal"`、出力なし）。安全審査は有害な入力と
    して扱い（5.5）、それ以外のプロンプトは BadOutput と同じく再送として数える。
    """


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
        """How much to record when this call is cancelled by the time limit (the real client uses the estimate made
        before the call, the same number as that ledger line; the fake model and replay use 0).

        この呼び出しが時間制限で取り消されたときに記録する費用（実クライアントは呼び出し前の見積もりで、台帳のその行と
        同じ数。偽モデルとリプレイは 0）。
        """
        ...


def replay_key(provider: str, model: str, prompt_version: str, request: Json) -> str:
    return _replay_key(provider, model, prompt_version, request)


def spec(kind: str) -> TextSpec:
    """Which provider and model this prompt kind uses (for Claude, the tier name plus version), how deep the thinking
    is, and how long the time limit is (`config.TEXT`, plus tier overrides from `ZJ_TEXT_MODELS`).

    このプロンプトの種類がどのプロバイダ、どのモデル（Claude はティア名とバージョン）を使い、思考の深さと時間制限は
    どれだけか（`config.TEXT` と、`ZJ_TEXT_MODELS` によるティアの差し替え）。
    """
    if kind not in PROMPTS:
        raise ValueError(f"No such prompt kind / そのようなプロンプトの種類はない: {kind}")
    return text_spec(kind)


def model_and_version(kind: str) -> tuple[str, str]:
    return spec(kind).model, PROMPTS[kind].version


def key_of(kind: str, request: Json) -> str:
    model, version = model_and_version(kind)
    return replay_key(spec(kind).provider, model, version, request)


# —— Fake model / 偽モデル ——

NO_USAGE = {"inputTokens": 0, "outputTokens": 0}


def _check_all_pass(request: Mapping[str, Any]) -> Json:
    n = len(request.get("candidates", []))
    return {"results": [{"index": i, "rules": [{"rule": r, "status": "pass"} for r in MODEL_RULES]} for i in range(n)]}


def _rewrite_same(request: Mapping[str, Any]) -> Json:
    return {"candidate": copy.deepcopy(request.get("candidate")) if request.get("mode") == "rewrite" else None}


# The fake model's one line of 地の文: one line per status (written for tests)
# 偽モデルの地の文 1 行：status ごとに 1 文（テスト用に書いたもの）
NARRATE_LINES = {
    "done": "あなたは、そうした。",
    "partial": "思ったようには、いかなかった。",
    "refused": "それは、いまはかなわなかった。",
}

FAKE_FATES = {"witness": "刑場で、日没を見届けた。", "elsewhere": "刑場には行かず、日没を迎えた。"}


def _ending(request: Mapping[str, Any]) -> Json:
    """The fake model's ending (B-9): deterministically writes, from the input, one that passes validation. The epilogue
    is assembled from the summaries of the last few events, each sentence citing that event; when someone was executed
    in this playthrough, summaries with forbidden wordings are skipped.

    偽モデルのエンディング（B-9）：入力から検証を通るものを決定的に書く。エピローグは最後の数件のイベントの要約から組み
    立て、各文がそのイベントを引用する。この周回で誰かが処刑された場合は、禁止された書き方を含む要約を飛ばす。
    """
    forbidden = list(request.get("forbidden", []))
    events = [
        e
        for e in request.get("events", [])
        if not any(w in str(e.get("summary", "")) for w in forbidden)
        # For a beat that did not happen as in the original, summary is the original's line
        # 原作どおりに起きなかったビートの summary は原作のその一文
        and (e.get("beat") or {}).get("to", "happened") == "happened"
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
        "variant": None,
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
                "claims": [],
            }
            for c in request.get("characters", [])
            if not c.get("unchanged")
        ],
    }


def _ending_broken(request: Mapping[str, Any]) -> Json:
    """The ending for `broken: true`: all citations empty (cite-empty), to test the rewrite and the template.

    `broken: true` のエンディング：引用をすべて空にする（cite-empty）。書き直しとテンプレートのテスト用。
    """
    out = _ending(request)
    for row in out["epilogue"]:
        row["cites"] = []
    return out


def _memory(request: Mapping[str, Any]) -> Json:
    """The first event's summary, with the role name replaced by 「あの人」, the trailing 「。」 removed, cut to 30
    characters.

    最初のイベントの要約。身分の名前を「あの人」に替え、文末の「。」を除き、30 字で切る。
    """
    said = str(request["events"][0]["summary"]).replace(str(request.get("role") or "\0"), "あの人")
    return {"text": said.rstrip("。")[:30], "weight": 1}


def _keeps(request: Mapping[str, Any]) -> Json:
    """There is a line only when there is a visible result (none = null, and the deletion confirmation does not show
    that line).

    目に見える結果があるときだけ一文を返す（ない = null。削除確認ではその行を表示しない）。
    """
    shown = any(e.get("visibleEffects") for e in request.get("events", []))
    return {"keeps": "そのとき起きたこと" if shown else None}


DEFAULTS: dict[str, Callable[[Mapping[str, Any]], Json]] = {
    "triage": lambda r: {"route": "maybe"},
    # No candidate events: only the clock moves
    # 候補イベントなし：時計だけ進む
    "extract": lambda r: {"candidates": []},
    "check": _check_all_pass,
    # Rewrite = unchanged; downgrade = cannot be done
    # 書き換え = 原文のまま、格下げ = できない
    "rewrite": _rewrite_same,
    "reply": lambda r: {"text": "……そうか。"},
    # B-12: by default nothing
    # B-12：デフォルトは何もなし
    "safety": lambda r: {"selfHarm": "none", "injection": False},
    # B-15: by default not lowered (better to pause by mistake) / B-15：デフォルトでは下げない（誤って止めるほうがよい）
    "safety_review": lambda r: {"story": False},
    "narrate": lambda r: {"text": NARRATE_LINES.get(str(r.get("status")), NARRATE_LINES["done"])},
    # Does not go ahead; the alternative is the first given destination (B-3 card "interface")
    # 実行しない。代わりの行き先は最初に与えられた行き先（B-3 カード「インターフェース」）
    "plan": lambda r: {
        "accepted": False,
        "label": None,
        "with": [],
        "effects": [],
        "narration": ["その道は、いまは開けていなかった。"],
        "alternative": {"exit": r["options"][0]["optionId"]} if r.get("options") else None,
    },
    "ending": _ending,
    # B-17: makes sense by default
    # B-17：デフォルトは筋が通る
    "ending-check": lambda r: {"coherent": True, "fields": []},
    # B-13: the event summary cut short (the fake model has no character point of view)
    # B-13：イベントの要約を短く切る（偽モデルは登場人物の視点を区別しない）
    "memory": _memory,
    "keeps": _keeps,
    # B-21: one question and one statement of intent (not all questions)
    # B-21：質問 1 つと意思表示 1 つ（すべて質問にはしない）
    "suggest": lambda r: {
        "items": [
            {"text": "もう少し詳しく聞かせてください。", "kind": "ask"},
            {"text": "私にできることはありますか。", "kind": "act"},
        ]
    },
    # B-16: world advance writes nothing by default
    # B-16：世界の進行はデフォルトで何も書かない
    "world": lambda r: {"events": []},
}
ERRORS = ("rate-limit", "invalid", "unavailable", "refusal")


def _summaries(request: Mapping[str, Any]) -> list[str]:
    cands = request.get("candidates") or ([request["candidate"]] if request.get("candidate") else [])
    cands = [*cands, *([request["event"]] if request.get("event") else []), *request.get("events", [])]  # B-13
    return [str(c.get("summary", "")) for c in cands]


def _matches(when: Mapping[str, Any], request: Mapping[str, Any]) -> bool:
    """Conditions of a fake-text rule; it matches only when every key holds: `playerContains` / `replyContains` check
    whether this turn's original words contain these characters, `summaryContains` checks the candidates' summaries,
    `character` compares this turn's character, `confirmOpen` checks whether the extraction request has a question
    asked back awaiting an answer (B-4's `<confirm>`), and any other key must equal the same-named value in the request.

    fake-text ルールの条件。すべてのキーを満たしたときだけ一致する：`playerContains` / `replyContains` はこのターンの
    元の発言に特定の文字が含まれるか、`summaryContains` は候補の要約、`character` はこのターンの登場人物と比べ、
    `confirmOpen` は抽出のリクエストに回答待ちの聞き返しがあるか（B-4 の `<confirm>`）を見る。それ以外のキーは
    リクエスト内の同名の値と等しくなければならない。
    """
    turn = request.get("turn") or {}
    for k, v in when.items():
        if k == "playerContains":
            ok = v in (turn.get("player") or "")
        elif k == "replyContains":
            ok = v in (turn.get("reply") or "")
        elif k == "summaryContains":
            ok = any(v in s for s in _summaries(request))
        elif k == "character":
            who = turn.get("character") or request.get("character")
            # B-13: in a memory request it is the persona summary / B-13：記憶のリクエストでは人物設定の要約
            ok = (who.get("id") if isinstance(who, dict) else who) == v
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
        # The seed of a simulated playthrough (B-5): answers are now deterministic from the input, so it is unused;
        # it is for when randomness is needed later
        # 模擬周回のシード（B-5）：今は入力から決定的に答えるので使わない。後でランダムにするときに使う
        self.seed = seed
        self.rules: list[dict[str, Any]] = []
        self.used: dict[int, int] = {}  # rule index → times used (`times`) / ルール番号 → 使用回数（`times`）
        self.calls: list[tuple[str, Json]] = []  # what was called, for tests / テストが見る呼び出し内容
        if rules_dir is not None and rules_dir.is_dir():
            for p in sorted(rules_dir.glob("*.json")):
                for r in json.loads(p.read_text(encoding="utf-8"))["rules"]:
                    self.rules.append(self._rule(r, p.name))
        for r in rules or []:
            self.rules.append(self._rule(r, "<test>"))

    @staticmethod
    def _rule(r: Json, source: str) -> dict[str, Any]:
        if r["kind"] not in DEFAULTS:
            raise ValueError(f"{source}: no such prompt kind / そのようなプロンプトの種類はない: {r['kind']}")
        if r.get("error") not in (None, *ERRORS):
            raise ValueError(f"{source}: unknown error / 不明な error: {r['error']!r} ({' / '.join(ERRORS)})")
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
                raise RateLimited(
                    f"Fake model: {kind} returned 429 / 偽モデル：{kind} が 429 を返した ({rule['source']})"
                )
            if rule.get("error") == "refusal":
                raise Refused(
                    f"Fake model: {kind} refused to answer / 偽モデル：{kind} が回答を拒否 ({rule['source']})"
                )
            if rule.get("error") == "invalid":
                raise BadOutput(
                    f"Fake model: {kind} output fails the Schema / 偽モデル：{kind} の出力が Schema を通らない "
                    f"({rule['source']})"
                )
            if rule.get("error") == "unavailable":
                raise ModelCallFailed(
                    f"Fake model: {kind} call failed / 偽モデル：{kind} の呼び出しが失敗 ({rule['source']})"
                )
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
    """Shorthand for `fail`: candidates whose summary contains `when.summaryContains` (all of them if it is not given)
    fail this rule, and everything else passes.

    `fail` の略記：要約に `when.summaryContains` を含む候補（書かなければすべて）はこのルールで fail、それ以外はすべて
    通過する。
    """
    out = _check_all_pass(request)
    needle = rule.get("when", {}).get("summaryContains")
    for res, cand in zip(out["results"], request.get("candidates", []), strict=True):
        if needle is None or needle in str(cand.get("summary", "")):
            for row in res["rules"]:
                if row["rule"] == rule["fail"]["rule"]:
                    row["status"] = "fail"
                    row["reason"] = rule["fail"].get("reason", "モデル検査で不合格")
    return out


# —— Replay / リプレイ ——


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
                    raise ValueError(
                        f"{p.name}:{n}: key does not match the content (should be {want}) / "
                        f"key が内容と一致しない（正しくは {want}）"
                    )
                self.records[rec["key"]] = rec

    async def call(self, kind: str, request: Json) -> TextResult:
        model, version = model_and_version(kind)
        rec = self.records.get(key_of(kind, request))
        if rec is None:
            raise ReplayMissing(
                f"Replay missing or stale / リプレイが無いか期限切れ: {kind} "
                f"({spec(kind).provider} {model}, prompt {version})"
            )
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
    """One replay line (used both for fixtures recorded from the fake model and for replays recorded from real models).

    リプレイ 1 行（偽モデルで録ったフィクスチャにも、実モデルで録ったリプレイにも使う）。
    """
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
    """Record replays (`ZJ_RECORD_REPLAYS=<directory>`): every successful call appends one line in replay format to
    `<directory>/<kind>.jsonl`. Used for recording real models on the Mac; the fake model can be recorded too (to test
    the replay path). Only synthetic input is recorded (S-2 entries, eval cases), never the words of real players.

    リプレイを録る（`ZJ_RECORD_REPLAYS=<ディレクトリ>`）：成功した呼び出しごとに、リプレイ形式で
    `<ディレクトリ>/<kind>.jsonl` に 1 行追記する。Mac 上で実モデルを録るのに使う。偽モデルも録れる（リプレイの経路の
    テスト用）。合成入力（S-2 の項目、評価のケース）だけを録り、実際のプレイヤーの発言は録らない。
    """

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
    """Real model: each prompt kind is handed to the client of the provider in `config.TEXT` (one eval can use both:
    `reply` goes to Google). A client is built only when first needed: runs that only call Claude (S-2, small tests) do
    not require Vertex's environment variables.

    実モデル：プロンプトの種類ごとに `config.TEXT` の provider のクライアントに渡す（1 回の評価で両方を使うこともある：
    `reply` は Google）。クライアントは最初に必要になったときに作る：Claude だけを呼ぶ実行（S-2、小テスト）は Vertex の
    環境変数を必要としない。
    """

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
    """real: Claude's client is built right away (if the key, model ID or cap is missing, it exits without sending a
    request); Google's is built only at the first `reply` call.

    real：Claude のクライアントはその場で作る（キー、モデル ID、上限が欠けていればリクエストを送らずに終了する）。
    Google のものは最初に `reply` を呼ぶときに作る。
    """
    # Import only for real; other modes never touch the real clients
    # real のときだけ import し、ほかのモードでは実クライアントに触れない
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
    """With settings given and `record_replays` set, fake and real calls are recorded (replay is not). seed is only for
    the fake model (B-5).

    settings があり `record_replays` が設定されていれば、fake と real の呼び出しを録る（replay は録らない）。seed は
    偽モデルにだけ渡す（B-5）。
    """
    inner: TextModel
    if mode == "fake":
        inner = FakeText(fake_rules, seed=seed)
    elif mode == "replay":
        return ReplayText(replays)
    else:
        if settings is None:
            raise ValueError(
                "ZJ_MODEL=real needs Settings to build the clients (ledger, caps, replay recording directory) / "
                "ZJ_MODEL=real ではクライアントを作るのに Settings が必要（台帳、上限、リプレイを録るディレクトリ）"
            )
        inner = real_text_model(settings)
    if settings is not None and settings.record_replays is not None:
        return Recording(inner, settings.record_replays)
    return inner
