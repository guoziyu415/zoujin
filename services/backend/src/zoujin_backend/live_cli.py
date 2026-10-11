"""`zoujin-live`（B-10）：真 Live 在 Mac 上的两个入口。

  zoujin-live check [--confirm]       # 开一条真会话说一轮文字、一轮合成语音，打印时间和用量（约 0.01 美元）
  zoujin-live reconcile --ledger PATH [--item b10] [--out DIR]   # S-090：每轮 Live 的实际花费和公式对账

- check 只在 `ZJ_LIVE=real`（或 `ZJ_MODEL=real`）时跑，要 ZJ_LEDGER、ZJ_MAX_GOOGLE_USD（同 B-2）；
  不带 `--confirm` 只打印预计花费（D-030）。打印的只有毫秒、有没有文字、用量和美元，不打印人物说了什么。
- reconcile 只读账本，不调模型：账本里 `live.turn/<局>` 的每一行带这一轮的用量、会话里已有的音频毫秒、
  会话第几轮、松开到首个音频毫秒（网关记的，`gateway/voice.py`）。
  公式是 results-s1 8.5 的「每轮约 0.00086 + 0.0000788 × 会话里已有的音频秒数」（S-073 ⑤）。
  输出 Markdown 和 JSON，没有原话。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from zoujin_llm.ledger import read_lines

Json = Any

FIXED_USD = 0.00086  # results-s1 8.5：每轮固定的部分
PER_AUDIO_S_USD = 0.0000788  # 每秒会话里已有的音频
CHECK_ESTIMATE_USD = 0.01
BUCKETS = ((1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 10_000))
CHECK_SYSTEM = (
    "あなたは太宰治『走れメロス』のメロスです。村の牧人です。旅の者と話しています。"
    "一度に二文まで、短く答えてください。必ず日本語だけで話してください。"
)
CHECK_LINE = "こんにちは。どちらから来たのですか。"


def formula(session_audio_s: float) -> float:
    return FIXED_USD + PER_AUDIO_S_USD * session_audio_s


def _pct(actual: float, expect: float) -> float | None:
    return None if expect <= 0 else round((actual - expect) / expect * 100, 1)


def _p95(xs: Sequence[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    return s[min(len(s) - 1, max(0, round(0.95 * len(s)) - 1))]


def reconcile(lines: Sequence[Mapping[str, Any]], item: str | None = None) -> Json:
    rows = [
        x for x in lines if str(x.get("kind", "")).startswith("live.turn/") and (item is None or x.get("item") == item)
    ]
    fallback = sum(
        float(x.get("costUsd", 0))
        for x in lines
        if str(x.get("kind", "")).startswith("live.fallback/") and (item is None or x.get("item") == item)
    )
    games: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for x in rows:
        games[str(x["kind"]).split("/", 1)[1]].append(x)
    by_bucket: dict[str, dict[str, float]] = {}
    first: list[float] = []
    out_games = []
    for n, (_, gl) in enumerate(sorted(games.items(), key=lambda kv: str(kv[1][0].get("at", ""))), 1):
        actual = sum(float(x.get("costUsd", 0)) for x in gl)
        expect = sum(formula(int(x["usage"].get("sessionAudioMsBefore", 0)) / 1000) for x in gl)
        sessions = sum(1 for x in gl if int(x["usage"].get("sessionTurn", 0)) == 1)
        out_games.append(
            {
                "game": n,
                "turns": len(gl),
                "sessions": sessions,
                "actualUsd": round(actual, 4),
                "formulaUsd": round(expect, 4),
                "diffPct": _pct(actual, expect),
            }
        )
        for x in gl:
            u = x["usage"]
            k = int(u.get("sessionTurn", 0))
            label = next((f"{a}–{b}" if b < 10_000 else f"{a}+" for a, b in BUCKETS if a <= k <= b), "?")
            b = by_bucket.setdefault(label, {"turns": 0, "actualUsd": 0.0, "formulaUsd": 0.0})
            b["turns"] += 1
            b["actualUsd"] += float(x.get("costUsd", 0))
            b["formulaUsd"] += formula(int(u.get("sessionAudioMsBefore", 0)) / 1000)
            if int(u.get("firstAudioMs", -1)) >= 0:
                first.append(float(u["firstAudioMs"]))
    buckets = [
        {
            "sessionTurns": k,
            "turns": int(v["turns"]),
            "actualPerTurnUsd": round(v["actualUsd"] / v["turns"], 5),
            "formulaPerTurnUsd": round(v["formulaUsd"] / v["turns"], 5),
            "diffPct": _pct(v["actualUsd"], v["formulaUsd"]),
        }
        for k, v in by_bucket.items()
    ]
    total_a = sum(float(x.get("costUsd", 0)) for x in rows)
    total_f = sum(formula(int(x["usage"].get("sessionAudioMsBefore", 0)) / 1000) for x in rows)
    return {
        "item": item,
        "games": out_games,
        "bySessionTurn": buckets,
        "total": {
            "turns": len(rows),
            "actualUsd": round(total_a, 4),
            "formulaUsd": round(total_f, 4),
            "diffPct": _pct(total_a, total_f),
            "fallbackUsd": round(fallback, 4),
        },
        "releaseToFirstAudioMs": {
            "n": len(first),
            "median": statistics.median(first) if first else None,
            "p95": _p95(first),
        },
    }


def markdown(r: Json) -> str:
    out = [f"# S-090 Live 对账（{r['item'] or '全部'}）", ""]
    t = r["total"]
    out.append(f"合计 {t['turns']} 轮：实际 ${t['actualUsd']}，公式 ${t['formulaUsd']}，差 {t['diffPct']}%")
    out.append(f"补转写 ${t['fallbackUsd']}")
    f = r["releaseToFirstAudioMs"]
    out += ["", f"松开到首个音频（服务端，S-073 ①）：n={f['n']}，中位 {f['median']} ms，p95 {f['p95']} ms", ""]
    out += ["| 局 | 轮数 | 会话数 | 实际 $ | 公式 $ | 差 % |", "|---|---|---|---|---|---|"]
    out += [
        f"| {g['game']} | {g['turns']} | {g['sessions']} | {g['actualUsd']} | {g['formulaUsd']} | {g['diffPct']} |"
        for g in r["games"]
    ]
    out += ["", "| 会话第几轮 | 轮数 | 实际每轮 $ | 公式每轮 $ | 差 % |", "|---|---|---|---|---|"]
    out += [
        f"| {b['sessionTurns']} | {b['turns']} | {b['actualPerTurnUsd']} | {b['formulaPerTurnUsd']} | {b['diffPct']} |"
        for b in r["bySessionTurn"]
    ]
    return "\n".join(out) + "\n"


def cmd_reconcile(args: argparse.Namespace) -> int:
    r = reconcile(read_lines(Path(args.ledger)), args.item)
    md = markdown(r)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "reconcile.json").write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out / "reconcile.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


# —— check（只在 Mac 上） ——


def _say_pcm(text: str) -> bytes | None:  # pragma: no cover - 只在 Mac 上
    """macOS 的 say 合成一句、afconvert 转成 16 kHz PCM16。没有这两个命令就跳过语音那一轮。"""
    if not shutil.which("say") or not shutil.which("afconvert"):
        return None
    with tempfile.TemporaryDirectory() as d:
        aiff, wav = Path(d) / "x.aiff", Path(d) / "x.wav"
        subprocess.run(["say", "-v", "Kyoko", "-o", str(aiff), text], check=True)
        subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(aiff), str(wav)], check=True)
        import wave

        with wave.open(str(wav)) as w:
            frames: bytes = w.readframes(w.getnframes())
        return frames


async def _check(env: Mapping[str, str]) -> int:  # pragma: no cover - 只在 Mac 上
    from zoujin_backend.config import Settings
    from zoujin_backend.gateway.app import voices_of
    from zoujin_backend.gateway.fallback import VertexTranscriber
    from zoujin_backend.models import gemini_live
    from zoujin_backend.models.ledger import Ledger
    from zoujin_backend.voice.models import LIVE_MODEL, real_models

    s = Settings.from_env()
    if s.ledger is None or s.max_google_usd is None:
        print("要 ZJ_LEDGER、ZJ_MAX_GOOGLE_USD", file=sys.stderr)
        return 2
    ledger = Ledger(s.ledger, s.max_google_usd, s.max_item_usd, s.ledger_item)
    ledger.before(CHECK_ESTIMATE_USD)
    _, rest = real_models(env)
    live = gemini_live.real_live(env, voices_of(), VertexTranscriber(rest))
    t0 = time.monotonic()
    session = await live.open("char.melos", (), CHECK_SYSTEM)
    print(f"建会话 {round((time.monotonic() - t0) * 1000)} ms")
    turns: list[tuple[str, bytes | None]] = [("text", None)]
    pcm = _say_pcm(CHECK_LINE)
    if pcm is not None:
        turns.append(("voice", pcm))
    try:
        for mode, data in turns:
            if data is not None:
                for i in range(0, len(data), 1280):
                    session.audio_in(data[i : i + 1280])
                    await asyncio.sleep(0.04)
            released = time.monotonic()
            first = None
            texts = {"player": False, "character": False}
            usd = 0.0
            async for ev in session.respond(CHECK_LINE if mode == "text" else None):
                if ev.kind == "audio" and first is None:
                    first = time.monotonic()
                elif ev.kind == "input_final":
                    texts["player"] = bool(ev.text)
                elif ev.kind == "output_final":
                    texts["character"] = bool(ev.text)
                elif ev.kind == "usage":
                    usd = ev.usd
                    ledger.add(kind="live.check", model=LIVE_MODEL, usage=ev.usage or {}, cost=ev.usd)
            ms = None if first is None else round((first - released) * 1000)
            print(f"{mode}：松开到首音 {ms} ms，玩家文字 {texts['player']}，人物文字 {texts['character']}，${usd:.5f}")
    finally:
        await session.close()
    return 0


def cmd_check(args: argparse.Namespace) -> int:  # pragma: no cover - 只在 Mac 上
    if not args.confirm:
        print(f"预计约 ${CHECK_ESTIMATE_USD:.2f}（一轮文字 + 一轮合成语音）。确认后加 --confirm 再跑。")
        return 0
    return asyncio.run(_check(os.environ))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="zoujin-live", description="真 Live 的检查和 S-090 对账（B-10）")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="开一条真会话说两轮（只在 Mac 上）")
    c.add_argument("--confirm", action="store_true")
    r = sub.add_parser("reconcile", help="账本里每轮 Live 的花费和公式对账")
    r.add_argument("--ledger", required=True)
    r.add_argument("--item", default="b10")
    r.add_argument("--out")
    args = p.parse_args(argv)
    sys.exit(cmd_check(args) if args.cmd == "check" else cmd_reconcile(args))
