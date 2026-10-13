"""S-5 report (B-5 item 6): per-playthrough cost of simulated playthroughs, scaled to 40 and 60 turns, latency, and
the narrator's counts. Numbers only.

    uv run zoujin-s5 --ledger <ledger.jsonl> --runs <runner's report.json> --out <dir> [--item s5]

- Reads three things:
  - the ledger (the `ZJ_LEDGER` file): rows of `item` (default `s5`), split per playthrough by `playthroughId`;
  - the DB the simulated playthroughs ran against (`DATABASE_URL`): each playthrough's `playthrough_metrics` and the
    times of its conversation turns (to assign ledger rows to turns by time);
  - the runner's `report.json`: each run's `playthroughId`, `persona`, `seed` in `cases[].results[]`, and `steps[]`
    (each step's `kind`, `elapsedMs`).
- Writes `report.json` and `report.md`. Never reads or writes original words, what the AI player said, characters'
  answers, or ending text.
- A playthrough's product cost adds only `use: "product"` rows and leaves out `reply` (in text mode it stands in for
  Live as the character, S-085 ①); Live is computed separately with the formula from results-s1 8.5 (`LIVE`,
  [estimated]). `use: "eval"` (judges, AI player) is listed separately and not counted in the per-playthrough cost.
- Scaling: kinds present in the slice use measurements; the missing ones (world advance, safety classification,
  memory, suggested utterances) follow B-8's "per-playthrough cost" estimate (`MISSING`, [estimated]). When the
  per-turn cost rises with the turn count it is extrapolated along the trend (PM #99). 1 dollar = 150 yen, compared
  with PRD 7.4's 300 yen and the saving tier's 240 yen.

S-5 のレポート（B-5 第 6 項）：シミュレーションのプレイの 1 プレイあたりの費用、40 ターンと 60 ターンへの換算、
レイテンシー、ナレーターの件数。数字だけ。

- 3 つを読む：
  - 台帳（`ZJ_LEDGER` のファイル）：`item`（デフォルト `s5`）の行を `playthroughId` でプレイごとに分ける。
  - シミュレーションのプレイを実行した DB（`DATABASE_URL`）：各プレイの `playthrough_metrics` と会話ターンの時刻
    （台帳の行を時刻で何ターン目かに振り分ける）。
  - ランナーの `report.json`：`cases[].results[]` にある各実行の `playthroughId`、`persona`、`seed` と `steps[]`
    （各ステップの `kind`、`elapsedMs`）。
- `report.json` と `report.md` を書く。発話の原文、AI プレイヤーの発言、登場人物の回答、エンディングの文章は読みも
  書きもしない。
- 1 プレイの製品費用は `use: "product"` の行だけを足し、`reply` は数えない（テキストモードでは Live の代わりに
  登場人物を演じる、S-085 ①）。Live は results-s1 8.5 の式で別に計算する（`LIVE`、〔推算〕）。`use: "eval"`
  （審査員、AI プレイヤー）は別に挙げ、1 プレイの費用には入れない。
- 換算：スライスにある種類は実測を使い、ない種類（世界の進行、安全分類、記憶、発話候補）は B-8「1 プレイのコスト」の
  推算に従う（`MISSING`、〔推算〕）。ターンあたりの費用がターン数とともに上がるときは傾向に沿って外挿する（PM #99）。
  1 ドル = 150 円で、PRD 7.4 の 300 円、節約段階の 240 円と比べる。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from zoujin_llm import read_lines, use_of

from zoujin_backend.config import DEADLINES, ConfigError, Settings
from zoujin_backend.db.tables import playthrough_metrics, turns

Json = Any

YEN = 150  # 1 dollar / 1 ドル
CAP_YEN = 300  # PRD 7.4's per-playthrough cap / PRD 7.4 の 1 プレイの上限
SAVER_YEN = 240  # Saving tier / 節約段階
# Q-B8's option "raise the cap to 350 円" (PM #117) / Q-B8 の選択肢「上限を 350 円に上げる」（PM #117）
RAISED_YEN = 350
# Q-B8's option "reduce world advance": the scaling table also gives the total with world advance halved (PM #117)
# Q-B8 の選択肢「世界の進行を減らす」：換算表には世界の進行を半分にしたときの合計も出す（PM #117）
WORLD_CUT = 0.5
TURNS = (40, 60)  # 20 minutes, 30 minutes (PRD 7.4) / 20 分、30 分（PRD 7.4）
# Stress tier: 60 turns, every turn checked, 2 attempts / 負荷段階：60 ターン、毎ターンチェック、2 回の試行
STRESS_TURNS = 60
STRESS_CHECKS = 2
SEARCH_TURNS = 200  # Search for the crossing turn up to here / 線を越えるターンをここまで探す
# Stands in for Live as the character in text mode; in the full version characters' words are spoken by Live
# テキストモードで Live の代わりに登場人物を演じる。正式版では登場人物の発話は Live が話す
NOT_IN_COST = ("reply",)
# Once-per-playthrough kinds (B-9's ending), not scaled per turn
# 1 プレイに 1 回の種類（B-9 のエンディング）、ターンで換算しない
PER_GAME = ("ending", "ending-check")
# Flag it when the ledger and playthrough_metrics differ by more than 1%
# 台帳と playthrough_metrics の差が 1% を超えたら示す
MISMATCH = 0.01
NO_DATA = "no data / データなし"
# Deadline advice: p99 plus 20%, rounded up to whole seconds / タイムアウトの提案：p99 に 2 割足し、秒単位に切り上げ
MARGIN = 1.2

# playthrough_metrics cost columns ↔ the ledger's kind / playthrough_metrics の費用の列 ↔ 台帳の kind
METRIC_COSTS = {
    "triage": "cost_triage_usd",
    "extract": "cost_extract_usd",
    "check": "cost_check_usd",
    "rewrite": "cost_rewrite_usd",
    "narrate": "cost_narrate_usd",
    "plan": "cost_plan_usd",
}
# The narrator's counts (item 4), read from playthrough_metrics; columns added since B-9 are omitted if absent
# ナレーターの件数（第 4 項）。playthrough_metrics から読む。B-9 以降に増えた列は、なければ出さない
COUNTS = (
    "turns",
    "turns_retracted",
    "turns_triage_skipped",
    "turns_timed_out",
    "candidates_rewritten",
    "candidates_downgraded",
    "candidates_rejected",
    "candidates_confirm_dropped",
    "confirms_asked",
    "actions",
    "plans_accepted",
    "plans_refused",
    # B-9: whether this playthrough's ending is the template (bool, recorded as 1 / 0 in the report, total in
    # endingsTemplated)
    # B-9：このプレイのエンディングがテンプレートか（bool。レポートでは 1 / 0 と書き、合計は endingsTemplated）
    "ending_template",
    "ending_calls",
)


@dataclass(frozen=True)
class Live:
    """Per-turn cost of Live voice [estimated]: input follows the fit to results-s1 8.5's measurements (base per turn +
    per_audio_s per second of audio already in the session), output follows the data cost model's price list (the
    character's audio and the transcripts of both sides). The session is rebuilt every rebuild_every turns
    (backend-design section 8); seconds per turn are the pre-R1 assumptions (the data cost model's player_s, char_s).

    Live 音声のターンあたりの費用〔推算〕：入力は results-s1 8.5 の実測へのあてはめ（ターンごとの base + セッションに
    すでにある音声 1 秒あたりの per_audio_s）、出力はデータのコストモデルの価格表（登場人物の音声と双方の書き起こし）。
    セッションは rebuild_every ターンごとに作り直す（backend-design 第 8 節）。ターンあたりの秒数は R1 以前の仮定
    （データのコストモデルの player_s、char_s）。
    """

    base: float = 0.00086
    per_audio_s: float = 0.0000788
    player_s: float = 9.0
    char_s: float = 9.0
    rebuild_every: int = 8
    # 25 tokens/s × output audio 12 dollars / million tokens / 25 トークン/秒 × 出力音声 100 万トークンあたり 12 ドル
    out_audio_per_s: float = 25 * 12.00 / 1_000_000
    # Transcript 6 tokens/s × output text 4.5 dollars / million tokens
    # 書き起こし 6 トークン/秒 × 出力テキスト 100 万トークンあたり 4.5 ドル
    out_text_per_s: float = 6 * 4.50 / 1_000_000

    def turn(self, k: int) -> float:
        """Turn k within the session (counting from 0).

        セッション内の k ターン目（0 から数える）。
        """
        heard = k * (self.player_s + self.char_s) + self.player_s
        out = self.char_s * self.out_audio_per_s + (self.player_s + self.char_s) * self.out_text_per_s
        return self.base + self.per_audio_s * heard + out

    def cost(self, turns: int) -> float:
        return sum(self.turn(i % self.rebuild_every) for i in range(turns))


@dataclass(frozen=True)
class Estimate:
    """A call kind not yet in the slice [estimated, B-8 "per-playthrough cost"]: cost per call, and calls per
    playthrough = fixed + per_turn × turns.

    スライスにまだない呼び出しの種類〔推算、B-8「1 プレイのコスト」〕：1 回の費用と、
    1 プレイの回数 = fixed + per_turn × ターン数。
    """

    per_call: float
    fixed: float
    per_turn: float

    def calls(self, turns: int) -> float:
        return self.fixed + self.per_turn * turns

    def cost(self, turns: int) -> float:
        return self.per_call * self.calls(turns)


LIVE = Live()
# World advance is listed separately (Q-B8's third option is to reduce it)
# 世界の進行は別に挙げる（Q-B8 の 3 つ目の選択肢はこれを減らすこと）
WORLD = "world"
MISSING: dict[str, Estimate] = {
    # 3 act changes + 4 key moments + once every 8 turns; 12 calls in 40 turns, $0.31 in total
    # 幕の切り替え 3 + 重要な瞬間 4 + 8 ターンに 1 回。40 ターンで 12 回、合計 $0.31
    WORLD: Estimate(0.31 / 12, 7, 1 / 8),
    # Once per line (player and character speaking), 44 times in 40 turns
    # 発言ごとに 1 回（プレイヤーと登場人物）、40 ターンで 44 回
    "safety": Estimate(0.007 / 44, 0, 1.1),
    "memory": Estimate(0.003 / 20, 0, 0.5),
    "candidates": Estimate(0.007 / 24, 0, 0.6),
}
# Ending generation plus check [estimated]: used when the slice's ledger has no ending rows
# エンディングの生成とチェック〔推算〕：スライスの台帳に ending の行がないときに使う
ENDING_ESTIMATE = 0.11 + 0.02


# —— Read / 読む ——


def runs_of(report: Mapping[str, Json]) -> list[Json]:
    """Every run with a playthroughId in the runner's report.json: {playthroughId, case, persona, seed, steps}.

    ランナーの report.json のうち playthroughId を持つ各実行：{playthroughId, case, persona, seed, steps}。
    """
    out = []
    for case in report.get("cases", []):
        for r in case.get("results", []):
            if not r.get("playthroughId"):
                continue
            out.append(
                {
                    "playthroughId": r["playthroughId"],
                    "case": case.get("id"),
                    "persona": r.get("persona", case.get("setup", {}).get("persona")),
                    "seed": r.get("seed", case.get("setup", {}).get("seed")),
                    "steps": [
                        {"kind": s.get("kind"), "elapsedMs": s["elapsedMs"]}
                        for s in r.get("steps", [])
                        if isinstance(s.get("elapsedMs"), int | float)
                    ],
                }
            )
    return out


async def _db(url: str, pids: Sequence[str]) -> tuple[dict[str, Json], dict[str, list[Json]]]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as c:
            rows = (
                await c.execute(select(playthrough_metrics).where(playthrough_metrics.c.playthrough_id.in_(pids)))
            ).mappings()
            metrics = {r["playthrough_id"]: {k: _num(v) for k, v in r.items()} for r in rows}
            q = (
                select(turns.c.playthrough_id, turns.c.kind, turns.c.status, turns.c.created_at, turns.c.settled_at)
                .where(turns.c.playthrough_id.in_(pids))
                .order_by(turns.c.created_at)
            )
            by_pt: dict[str, list[Json]] = defaultdict(list)
            for t in (await c.execute(q)).mappings():
                by_pt[t["playthrough_id"]].append(dict(t))
    finally:
        await engine.dispose()
    return metrics, dict(by_pt)


def _num(v: Any) -> Any:
    return float(v) if hasattr(v, "is_finite") else v  # Numeric → float


def _at(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# —— Compute / 計算 ——


def percentile(xs: Sequence[float], p: float) -> float:
    """Nearest rank (no interpolation): p95 is the ceil(0.95 n)-th value after sorting.

    最近順位（補間しない）：p95 はソート後の ceil(0.95 n) 番目。
    """
    s = sorted(xs)
    return float(s[max(0, math.ceil(p / 100 * len(s)) - 1)])


def spread(xs: Sequence[float]) -> Json:
    if not xs:
        return NO_DATA
    return {
        "n": len(xs),
        "p50": percentile(xs, 50),
        "p95": percentile(xs, 95),
        "p99": percentile(xs, 99),
        "max": float(max(xs)),
    }


def by_kind(rows: Iterable[Mapping[str, Json]]) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for r in rows:
        out[str(r["kind"])] += float(r.get("costUsd", 0.0))
    return dict(sorted(out.items()))


def product_rows(rows: Iterable[Mapping[str, Json]]) -> list[Mapping[str, Json]]:
    return [r for r in rows if use_of(r) == "product" and r.get("kind") not in NOT_IN_COST]


def per_turn_costs(rows: Sequence[Mapping[str, Json]], talks: Sequence[Mapping[str, Json]]) -> list[float]:
    """The narrator's cost of each conversation turn of this playthrough: ledger rows are assigned by their recording
    time to the nearest turn before them (actions and end of act count toward the previous turn; the opening before
    the first turn counts toward the first turn). Once-per-playthrough kinds are left out.

    このプレイの会話ターンごとのナレーターの費用：台帳の行は記録時刻でその直前のターンに振り分ける（アクションと幕末は
    前のターンに、最初のターンより前の開始処理は最初のターンに入れる）。1 プレイに 1 回の種類は数えない。
    """
    if not talks:
        return []
    starts = [t["created_at"] for t in talks]
    out = [0.0] * len(talks)
    for r in rows:
        if r.get("kind") in PER_GAME:
            continue
        at = _at(str(r["at"]))
        i = max(0, sum(1 for s in starts if s <= at) - 1)
        out[i] += float(r.get("costUsd", 0.0))
    return out


def trend(series: Sequence[Sequence[float]]) -> Json:
    """Least squares of per-turn cost against turn number (points from all playthroughs together, turns counted from
    1). If the slope is not above 0, use the mean.

    ターンあたりの費用をターン番号に対して最小二乗であてはめる（各プレイの点をまとめ、ターンは 1 から数える）。
    傾きが 0 以下なら平均を使う。
    """
    pts = [(i + 1, c) for s in series for i, c in enumerate(s)]
    if not pts:
        return {"mean": 0.0, "slope": 0.0, "intercept": 0.0, "points": 0, "rising": False}
    n = len(pts)
    mx = sum(x for x, _ in pts) / n
    my = sum(y for _, y in pts) / n
    var = sum((x - mx) ** 2 for x, _ in pts)
    slope = sum((x - mx) * (y - my) for x, y in pts) / var if var else 0.0
    rising = slope > 0
    return {
        "mean": my,
        "slope": slope if rising else 0.0,
        "intercept": my - slope * mx if rising else my,
        "points": n,
        "rising": rising,
    }


def narrator_cost(t: Mapping[str, float], turns: int) -> float:
    """The narrator's cost of the first `turns` turns: the sum of c(i) = intercept + slope × i (if not rising, the mean
    × turns).

    最初の turns ターンのナレーターの費用：c(i) = intercept + slope × i の和（上がらなければ平均 × ターン数）。
    """
    return t["intercept"] * turns + t["slope"] * turns * (turns + 1) / 2


def scaled(
    t: Mapping[str, float],
    shares: Mapping[str, float],
    ending: float,
    turns: int,
    *,
    check_factor: float = 1.0,
) -> Json:
    """Scale to `turns` turns: the measured narrator cost (along the trend) split across kinds, world advance listed
    separately, kinds missing from the slice [estimated], Live [estimated], the ending.
    Stress tier: the check share is multiplied by check_factor (every turn checked, 2 attempts ÷ the measured checks
    per turn).

    turns ターンに換算する：実測のナレーターの費用（傾向に沿って）を種類ごとに分け、世界の進行は別に挙げ、スライスに
    ない種類〔推算〕、Live〔推算〕、エンディングを加える。
    負荷段階：チェックの分に check_factor を掛ける（毎ターンチェック、2 回 ÷ 実測のターンあたりのチェック回数）。
    """
    narr = narrator_cost(t, turns)
    kinds = {k: narr * share for k, share in shares.items()}
    if "check" in kinds:
        kinds["check"] *= check_factor
    est = {k: e.cost(turns) for k, e in MISSING.items()}
    world = est.pop(WORLD)
    live = LIVE.cost(turns)
    total = sum(kinds.values()) + world + sum(est.values()) + live + ending
    return {
        "turns": turns,
        "narrator": {k: round(v, 6) for k, v in kinds.items()},
        "world": round(world, 6),
        "estimated": {k: round(v, 6) for k, v in est.items()},
        "live": round(live, 6),
        "ending": round(ending, 6),
        "totalUsd": round(total, 6),
        "totalYen": round(total * YEN, 1),
        "worldCutUsd": round(total - world * (1 - WORLD_CUT), 6),
        "share": {k: round(v / total, 4) for k, v in {**kinds, WORLD: world, **est, "live": live}.items()}
        if total
        else {},
        "overSaver": total * YEN >= SAVER_YEN,
        "overCap": total * YEN >= CAP_YEN,
    }


def crossing(t: Mapping[str, float], ending: float, yen: float) -> int | None:
    """The turn at which a playthrough crosses `yen` yen (narrator along the trend, kinds missing from the slice and
    Live by estimate, the ending once). None if it does not cross within SEARCH_TURNS turns.

    1 プレイが何ターン目に yen 円を超えるか（ナレーターは傾向に沿って、スライスにない種類と Live は推算で、
    エンディングは 1 回）。SEARCH_TURNS ターン以内に超えなければ None。
    """
    for n in range(1, SEARCH_TURNS + 1):
        usd = narrator_cost(t, n) + sum(e.cost(n) for e in MISSING.values()) + LIVE.cost(n) + ending
        if usd * YEN >= yen:
            return n
    return None


def cache_share(rows: Iterable[Mapping[str, Json]]) -> Json:
    """Share of input read from the cache: for Claude cacheReadTokens / (input + cache read + cache write), for Google
    cachedTokens / inputTokens.

    入力のうちキャッシュから読んだ割合：Claude は cacheReadTokens /（入力 + キャッシュ読み取り + キャッシュ書き込み）、
    Google は cachedTokens / inputTokens。
    """
    out: Json = {}
    for provider in ("claude", "google"):
        cached = total = 0
        for r in rows:
            if r.get("provider", "google") != provider:
                continue
            u = r.get("usage", {})
            if provider == "claude":
                cached += u.get("cacheReadTokens", 0)
                total += u.get("inputTokens", 0) + u.get("cacheReadTokens", 0) + u.get("cacheWriteTokens", 0)
            else:
                cached += u.get("cachedTokens", 0)
                total += u.get("inputTokens", 0)
        out[provider] = round(cached / total, 4) if total else NO_DATA
    return out


def latency(rows: Sequence[Mapping[str, Json]], deadlines: Mapping[str, float]) -> Json:
    """Per call kind: the latency distribution, the share over the deadline, the number of timeouts (resent), those
    with no response, those that came back unusable. Old rows have no ms: no data.

    呼び出しの種類ごと：所要時間の分布、タイムアウトを超えた割合、タイムアウト（再送）の回数、応答がなかったもの、
    返ってきたが使えなかったもの。古い行には ms がない：データなし。
    """
    out: Json = {}
    for kind in sorted({str(r["kind"]) for r in rows}):
        mine = [r for r in rows if r["kind"] == kind]
        ms = [float(r["ms"]) for r in mine if "ms" in r]
        limit = deadlines.get(kind)
        timeouts = sum(1 for r in mine if r.get("status") == "timeout")
        late = sum(1 for r in mine if "ms" in r and r.get("status") != "timeout" and limit and r["ms"] > limit * 1000)
        out[kind] = {
            "calls": len(mine),
            "ms": spread(ms),
            "deadlineS": limit,
            "overDeadline": round((late + timeouts) / len(mine), 4) if ms else NO_DATA,
            "timeouts": timeouts,
            "errors": sum(1 for r in mine if r.get("status") == "error"),
            "badOutput": sum(1 for r in mine if r.get("status") == "bad-output"),
        }
    return out


def advice(lat: Mapping[str, Json]) -> dict[str, Json]:
    """Deadline advice: p99 plus 20%, rounded up to whole seconds (advice only; changing the code is a separate PR).

    タイムアウトの提案：p99 に 2 割足して秒単位に切り上げる（提案だけで、コードの変更は別の PR で行う）。
    """
    out: dict[str, Json] = {}
    for kind, v in lat.items():
        out[kind] = math.ceil(v["ms"]["p99"] * MARGIN / 1000) if isinstance(v["ms"], dict) else NO_DATA
    return out


def report(
    rows: Sequence[Mapping[str, Json]],
    runs: Sequence[Mapping[str, Json]],
    metrics: Mapping[str, Mapping[str, Json]],
    talks: Mapping[str, Sequence[Mapping[str, Json]]],
    endings: Mapping[str, Sequence[Mapping[str, Json]]] | None = None,
    deadlines: Mapping[str, float] = DEADLINES,
) -> Json:
    """All pure computation (tests call it directly). talks: each playthrough's conversation turns (created_at
    ascending); endings: each playthrough's ending tasks (with settled_at).

    すべて純粋な計算（テストが直接呼ぶ）。talks：各プレイの会話ターン（created_at の昇順）。endings：各プレイの
    エンディングのタスク（settled_at あり）。
    """
    plays = []
    series = []
    measured_kinds: dict[str, float] = defaultdict(float)
    endings_usd: list[float] = []
    check_calls = total_turns = 0
    for run in runs:
        pid = run["playthroughId"]
        mine = [r for r in rows if r.get("playthroughId") == pid]
        product = product_rows(mine)
        kinds = by_kind(product)
        m = metrics.get(pid, {})
        n_turns = len(talks.get(pid, []))
        live = LIVE.cost(n_turns)
        mismatch = {}
        for kind, col in METRIC_COSTS.items():
            if col in m:
                ledger_usd, db_usd = kinds.get(kind, 0.0), float(m[col])
                if abs(ledger_usd - db_usd) > MISMATCH * max(ledger_usd, db_usd, 1e-9) and max(ledger_usd, db_usd) > 0:
                    mismatch[kind] = {"ledger": round(ledger_usd, 6), "metrics": round(db_usd, 6)}
        cost = sum(kinds.values())
        per_turn = per_turn_costs(product, talks.get(pid, []))
        series.append(per_turn)
        for k, v in kinds.items():
            if k not in PER_GAME:
                measured_kinds[k] += v
        ending = sum(v for k, v in kinds.items() if k in PER_GAME)
        if ending:
            endings_usd.append(ending)
        check_calls += sum(1 for r in product if r["kind"] == "check")
        total_turns += n_turns
        plays.append(
            {
                "playthroughId": pid,
                "case": run.get("case"),
                "persona": run.get("persona"),
                "seed": run.get("seed"),
                "turns": n_turns,
                "costByKind": {k: round(v, 6) for k, v in kinds.items()},
                "narratorUsd": round(cost, 6),
                "liveUsd": round(live, 6),
                "totalUsd": round(cost + live, 6),
                "totalYen": round((cost + live) * YEN, 1),
                "metricsMismatch": mismatch,
                "counts": {k: int(m[k]) if isinstance(m[k], bool) else m[k] for k in COUNTS if k in m},
                "evalUsd": round(sum(float(r.get("costUsd", 0.0)) for r in mine if use_of(r) == "eval"), 6),
            }
        )
    t = trend(series)
    narr_total = sum(measured_kinds.values())
    shares = {k: v / narr_total for k, v in measured_kinds.items()} if narr_total else {}
    ending = sum(endings_usd) / len(endings_usd) if endings_usd else ENDING_ESTIMATE
    per_turn_checks = check_calls / total_turns if total_turns else 0.0
    out_scaled = {str(n): scaled(t, shares, ending, n) for n in TURNS}
    out_scaled["stress"] = scaled(
        t,
        shares,
        ending,
        STRESS_TURNS,
        check_factor=max(1.0, STRESS_CHECKS / per_turn_checks) if per_turn_checks else 1.0,
    )
    ours = {r["playthroughId"] for r in runs}
    eval_rows = [r for r in rows if use_of(r) == "eval"]
    steps: dict[str, list[float]] = defaultdict(list)
    for run in runs:
        for s in run.get("steps", []):
            steps[str(s.get("kind"))].append(float(s["elapsedMs"]))
    ending_ms = [
        (e["settled_at"] - e["created_at"]).total_seconds() * 1000
        for pid in ours
        for e in (endings or {}).get(pid, [])
        if e.get("settled_at") is not None
    ]
    product_all = product_rows([r for r in rows if r.get("playthroughId") in ours])
    lat = latency(product_all, deadlines)
    return {
        "params": {
            "yenPerUsd": YEN,
            "capYen": CAP_YEN,
            "saverYen": SAVER_YEN,
            "raisedYen": RAISED_YEN,
            "worldCut": WORLD_CUT,
            "live": asdict(LIVE),
            "missing": {k: asdict(v) for k, v in MISSING.items()},
            "endingEstimateUsd": None if endings_usd else ENDING_ESTIMATE,
            "estimated": "live, missing, endingEstimateUsd are [estimated] / "
            "live、missing、endingEstimateUsd は〔推算〕",
        },
        "playthroughs": plays,
        "perTurn": {k: round(v, 8) for k, v in t.items()} | {"rising": t["rising"], "points": t["points"]},
        "scaled": out_scaled,
        "crossing": {str(y): crossing(t, ending, y) for y in (SAVER_YEN, CAP_YEN, RAISED_YEN)},
        "endingsTemplated": sum(1 for m in metrics.values() if m.get("ending_template") is True),
        "cacheRead": cache_share(product_all),
        "latency": lat,
        "steps": {k: spread(v) for k, v in sorted(steps.items())} or NO_DATA,
        "endingMs": spread(ending_ms),
        "deadlineAdvice": advice(lat),
        "eval": {"usd": round(sum(float(r.get("costUsd", 0.0)) for r in eval_rows), 6), "byKind": by_kind(eval_rows)},
    }


# —— Write / 書く ——


def markdown(r: Mapping[str, Json]) -> str:
    def money(usd: float) -> str:
        return f"${usd:.3f} ({usd * YEN:.0f} 円)"

    lines = [
        "# S-5 report / S-5 レポート",
        "",
        "Numbers only. Live, kinds not yet in the slice, and the ending when there is no measurement are [estimated] "
        "(parameters in report.json's params). / "
        "数字だけ。Live、スライスにまだない種類、実測がないときのエンディングは〔推算〕"
        "（パラメーターは report.json の params）。",
        "",
        "## Per playthrough / プレイごと",
        "",
        "| Playthrough / プレイ | Persona / ペルソナ | Seed / シード | Turns / ターン数 | Narrator / ナレーター "
        "| Live [estimated] / Live〔推算〕 | Total / 合計 | Mismatch with metrics / metrics と不一致 |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for p in r["playthroughs"]:
        bad = ", ".join(p["metricsMismatch"]) or "—"
        lines.append(
            f"| {p['playthroughId']} | {p['persona']} | {p['seed']} | {p['turns']} | ${p['narratorUsd']:.4f} | "
            f"${p['liveUsd']:.4f} | {money(p['totalUsd'])} | {bad} |"
        )
    t = r["perTurn"]
    rising = (
        "rises with turns: extrapolated along the trend / ターン数とともに上がる：傾向に沿って外挿"
        if t["rising"]
        else "does not rise with turns: uses the mean / ターン数とともに上がらない：平均を使う"
    )
    lines += [
        "",
        "## Narrator cost per turn / ターンあたりのナレーターの費用",
        "",
        f"Mean / 平均 ${t['mean']:.5f}; {rising} (slope / 傾き ${t['slope']:.6f}/turn, {t['points']} points / 点).",
        "",
        "## Scaling / 換算",
        "",
        "| | 40 turns / 40 ターン | 60 turns / 60 ターン "
        "| Stress (60 turns, 2 checks per turn) / 負荷（60 ターン、毎ターン 2 回チェック） |",
        "|---|---:|---:|---:|",
    ]
    cols = [r["scaled"]["40"], r["scaled"]["60"], r["scaled"]["stress"]]
    names = sorted({k for c in cols for k in c["share"]})
    for k in names:
        lines.append(f"| {k} | " + " | ".join(f"{c['share'].get(k, 0) * 100:.1f}%" for c in cols) + " |")
    lines.append("| **Total / 合計** | " + " | ".join(money(c["totalUsd"]) for c in cols) + " |")
    lines.append(
        f"| Total with world advance ×{WORLD_CUT:g} / 世界の進行 ×{WORLD_CUT:g} のときの合計 | "
        + " | ".join(money(c["worldCutUsd"]) for c in cols)
        + " |"
    )
    cross = r["crossing"]

    def at(yen: int) -> str:
        return f"turn {cross[str(yen)] or f'{SEARCH_TURNS}+'}"

    lines += [
        "",
        f"Crosses the saving tier {SAVER_YEN} 円 / 節約段階 {SAVER_YEN} 円を超える: {at(SAVER_YEN)}; "
        f"crosses the cap {CAP_YEN} 円 / 上限 {CAP_YEN} 円を超える: {at(CAP_YEN)}; "
        f"with the cap raised to {RAISED_YEN} 円 / 上限を {RAISED_YEN} 円に上げたとき: {at(RAISED_YEN)}.",
        "",
        f"Share of input read from cache / 入力のうちキャッシュ読み取りの割合: Claude {r['cacheRead']['claude']}, "
        f"Google {r['cacheRead']['google']}.",
        "",
        "## Latency (milliseconds) / レイテンシー（ミリ秒）",
        "",
        "| Kind / 種類 | Calls / 回数 | p50 | p95 | p99 | Max / 最長 | Deadline (s) / タイムアウト（秒） "
        "| Over deadline / タイムアウト超過 | Timeouts resent / タイムアウト再送 | No response / 応答なし "
        "| Unusable / 使えない | Suggested deadline (s) / 提案タイムアウト（秒） |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for kind, v in r["latency"].items():
        ms = v["ms"]
        cells = [f"{ms[k]:.0f}" for k in ("p50", "p95", "p99", "max")] if isinstance(ms, dict) else [NO_DATA] * 4
        over = f"{v['overDeadline'] * 100:.1f}%" if isinstance(v["overDeadline"], float) else NO_DATA
        lines.append(
            f"| {kind} | {v['calls']} | "
            + " | ".join(cells)
            + f" | {v['deadlineS'] or '—'} | {over} | {v['timeouts']} | "
            f"{v['errors']} | {v['badOutput']} | {r['deadlineAdvice'][kind]} |"
        )
    lines += [
        "",
        "Each step (player finishes speaking to commit, elapsedMs; measured by the eval entry point, where each "
        "step includes creating an event loop and a DB connection, so it is slower than the gateway and is an upper "
        "bound): / "
        "各ステップ（プレイヤーが話し終えてからコミットまで、elapsedMs。評価の入口で測ったもので、各ステップに"
        "イベントループと DB 接続の作成を含むため、ゲートウェイより遅く、上限値になる）：",
    ]
    steps = r["steps"]
    if isinstance(steps, dict):
        for kind, v in steps.items():
            lines.append(f"- {kind}: p50 {v['p50']:.0f}, p95 {v['p95']:.0f} ({v['n']} steps / ステップ)")
    else:
        lines.append(f"- {NO_DATA}")
    e = r["endingMs"]
    ending = f"p50 {e['p50']:.0f}, max / 最長 {e['max']:.0f}" if isinstance(e, dict) else NO_DATA
    lines.append(
        f"- Ending from start to saved / エンディングの開始から保存まで: {ending}; "
        f"template endings / テンプレートのエンディング {r['endingsTemplated']}"
    )
    lines += [
        "",
        "## Narrator counts / ナレーターの件数",
        "",
        "| Playthrough / プレイ | " + " | ".join(COUNTS) + " |",
        "|---|" + "---:|" * len(COUNTS),
    ]
    for p in r["playthroughs"]:
        lines.append(f"| {p['playthroughId']} | " + " | ".join(str(p["counts"].get(k, "—")) for k in COUNTS) + " |")
    lines += [
        "",
        "## Judges and AI player (not counted per playthrough) / 審査員と AI プレイヤー（1 プレイの費用には入れない）",
        "",
        f"Total / 合計 ${r['eval']['usd']:.4f}.",
        "",
    ]
    return "\n".join(lines)


def parse(argv: Sequence[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="zoujin-s5",
        description="S-5: per-playthrough cost of simulated playthroughs, scaling, latency (numbers only) / "
        "S-5：シミュレーションのプレイの 1 プレイあたりの費用、換算、レイテンシー（数字だけ）",
    )
    p.add_argument("--ledger", type=Path, help="Ledger (default ZJ_LEDGER) / 台帳（デフォルトは ZJ_LEDGER）")
    p.add_argument(
        "--item", default="s5", help="Only rows of this item (default s5) / この項目の行だけを見る（デフォルト s5）"
    )
    p.add_argument(
        "--runs",
        type=Path,
        required=True,
        help="The runner's report.json (each run carries a playthroughId) / "
        "ランナーの report.json（各実行に playthroughId がある）",
    )
    p.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Directory to write report.json and report.md / report.json と report.md を書くディレクトリ",
    )
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse(argv)
    try:
        settings = Settings.from_env()
    except ConfigError as e:
        print(f"Bad configuration / 設定が正しくない: {e}", file=sys.stderr)
        return 2
    ledger = args.ledger or settings.ledger
    if ledger is None or not ledger.is_file():
        print(
            "No ledger: give --ledger or set ZJ_LEDGER / 台帳がない：--ledger を渡すか ZJ_LEDGER を設定する",
            file=sys.stderr,
        )
        return 2
    rows = [r for r in read_lines(ledger) if args.item is None or r.get("item") == args.item]
    runs = runs_of(json.loads(args.runs.read_text(encoding="utf-8")))
    if not runs:
        print(
            "No runs with a playthroughId in report.json / report.json に playthroughId を持つ実行がない",
            file=sys.stderr,
        )
        return 2
    metrics, all_turns = asyncio.run(_db(settings.database_url, [r["playthroughId"] for r in runs]))
    talks = {
        pid: [t for t in ts if t["kind"] == "talk" and t["status"] != "retracted"] for pid, ts in all_turns.items()
    }
    endings = {pid: [t for t in ts if t["kind"] == "ending"] for pid, ts in all_turns.items()}
    out = report(rows, runs, metrics, talks, endings, settings.deadlines)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out / "report.md").write_text(markdown(out), encoding="utf-8")
    print(f"Report / レポート: {args.out / 'report.md'}, {args.out / 'report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
