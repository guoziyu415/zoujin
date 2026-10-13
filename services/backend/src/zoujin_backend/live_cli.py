"""`zoujin-live` (B-10): entry points for real Live on the Mac.

`zoujin-live`（B-10）：Mac で本物の Live を使うための入口。

  # Open one real session, speak one text turn and one synthesized speech turn, print timing and usage (about 0.01 USD)
  # 本物のセッションを 1 つ開き、文字 1 ターンと合成音声 1 ターンを話して、時間と使用量を表示する（約 0.01 米ドル）
  zoujin-live check [--confirm]
  # Only set up sessions without speaking, trying each setup variant once: which is rejected, close code and reason
  # (free)
  # 話さずにセッションを確立するだけで、各 setup を 1 回ずつ試す：どれが拒否されるか、クローズコードと理由（費用なし）
  zoujin-live probe
  # S-090: reconcile each Live turn's actual cost with the formula / S-090：Live の各ターンの実際の費用を式と照合する
  zoujin-live reconcile --ledger PATH [--item b10] [--out DIR]

- check runs only with `ZJ_LIVE=real` (or `ZJ_MODEL=real`) and needs ZJ_LEDGER and ZJ_MAX_GOOGLE_USD (same as B-2);
  without `--confirm` it only prints the estimated cost (D-030). It prints only milliseconds, whether there was text,
  usage and dollars, never what the character said.
- probe also runs only on the Mac (needs the Vertex environment variables, not the ledger): it closes as soon as it
  gets `setupComplete`, with no input or output, so nothing is billed. Run it first when check can't set up a session,
  to see which setup field is refused.
- reconcile only reads the ledger and never calls a model: each `live.turn/<game>` row in the ledger carries the turn's
  usage, the audio milliseconds already in the session, the turn number within the session, and the milliseconds from
  release to first audio (recorded by the gateway, `gateway/voice.py`).
  The formula is results-s1 8.5's "per turn, **input** ≈ 0.00086 + 0.0000788 × seconds of audio already in the session"
  (S-073 ⑤): only the input half is compared, output is listed separately, turns without usage are not compared, and an
  extra line gives a fit of the input cost (intercept, slope). Outputs Markdown and JSON, with no original speech.

- check は `ZJ_LIVE=real`（または `ZJ_MODEL=real`）のときだけ動き、ZJ_LEDGER と ZJ_MAX_GOOGLE_USD が必要（B-2 と同じ）。
  `--confirm` がなければ見積もり費用だけを表示する（D-030）。表示するのはミリ秒、文字の有無、使用量と米ドルだけで、
  人物が何を言ったかは表示しない。
- probe も Mac のみ（Vertex の環境変数が必要で、台帳は不要）：`setupComplete` を受け取ったらすぐ閉じ、入力も出力も
  ないので課金されない。check でセッションが確立できないときに先にこれを実行し、setup のどのフィールドが拒否されるかを
  見る。
- reconcile は台帳を読むだけでモデルは呼ばない：台帳の `live.turn/<周回>` の各行には、そのターンの使用量、セッションに
  既にある音声のミリ秒、セッション内で何ターン目か、離してから最初の音声までのミリ秒（ゲートウェイが記録、
  `gateway/voice.py`）が入っている。
  式は results-s1 8.5 の「1 ターンの**入力**は約 0.00086 + 0.0000788 × セッションに既にある音声の秒数」（S-073 ⑤）：
  入力側だけを比べ、出力は別に並べ、使用量が届かなかったターンは比べず、入力費用のフィット（切片、傾き）を 1 行足す。
  Markdown と JSON を出力し、発言そのものは含めない。
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

FIXED_USD = 0.00086  # results-s1 8.5: the fixed part per turn / results-s1 8.5：1 ターンあたりの固定部分
# Per second of audio already in the session / セッションに既にある音声 1 秒あたり
PER_AUDIO_S_USD = 0.0000788
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


def _fit(points: Sequence[tuple[float, float]]) -> Json:
    """Least squares: input cost = intercept + slope × seconds of audio already in the session. Read side by side with
    the formula's 0.00086 and 0.0000788.

    最小二乗法：入力費用 = 切片 + 傾き × セッションに既にある音声の秒数。式の 0.00086、0.0000788 と並べて見る。
    """
    n = len(points)
    if n < 2:
        return {"n": n, "interceptUsd": None, "slopeUsdPerS": None}
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    sxx = sum((x - mx) ** 2 for x, _ in points)
    if sxx == 0:
        return {"n": n, "interceptUsd": round(my, 6), "slopeUsdPerS": None}
    slope = sum((x - mx) * (y - my) for x, y in points) / sxx
    return {"n": n, "interceptUsd": round(my - slope * mx, 6), "slopeUsdPerS": round(slope, 8)}


def _in_usd(x: Mapping[str, Any]) -> float:
    return int(x["usage"].get("inputMicroUsd", 0)) / 1_000_000


def _out_usd(x: Mapping[str, Any]) -> float:
    return int(x["usage"].get("outputMicroUsd", 0)) / 1_000_000


def _audio_s(x: Mapping[str, Any]) -> float:
    return int(x["usage"].get("sessionAudioMsBefore", 0)) / 1000


def reconcile(lines: Sequence[Mapping[str, Any]], item: str | None = None) -> Json:
    """results-s1 8.5 fits the **input** cost per turn: only the input half is compared with the formula and output
    is listed separately; turns without usage, recorded at the estimate (`usageEstimated`), are only counted and not
    compared (#111 data review).

    results-s1 8.5 がフィットしたのは 1 ターンの**入力**費用：入力側だけを式と比べ、出力は別に並べる。使用量が届かず
    見積もりで記録したターン（`usageEstimated`）は数えるだけで比べない（#111 データレビュー）。
    """
    rows = [
        x for x in lines if str(x.get("kind", "")).startswith("live.turn/") and (item is None or x.get("item") == item)
    ]
    fallback = sum(
        float(x.get("costUsd", 0))
        for x in lines
        if str(x.get("kind", "")).startswith("live.fallback/") and (item is None or x.get("item") == item)
    )
    measured = [x for x in rows if not int(x["usage"].get("usageEstimated", 0))]
    estimated = len(rows) - len(measured)
    games: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for x in rows:
        games[str(x["kind"]).split("/", 1)[1]].append(x)
    by_bucket: dict[str, dict[str, float]] = {}
    first: list[float] = []
    out_games = []
    for n, (_, gl) in enumerate(sorted(games.items(), key=lambda kv: str(kv[1][0].get("at", ""))), 1):
        ok = [x for x in gl if not int(x["usage"].get("usageEstimated", 0))]
        actual = sum(_in_usd(x) for x in ok)
        expect = sum(formula(_audio_s(x)) for x in ok)
        out_games.append(
            {
                "game": n,
                "turns": len(gl),
                "estimatedTurns": len(gl) - len(ok),
                "sessions": sum(1 for x in gl if int(x["usage"].get("sessionTurn", 0)) == 1),
                "totalUsd": round(sum(float(x.get("costUsd", 0)) for x in gl), 4),
                "inputUsd": round(actual, 4),
                "outputUsd": round(sum(_out_usd(x) for x in ok), 4),
                "formulaInputUsd": round(expect, 4),
                "diffPct": _pct(actual, expect),
            }
        )
    for x in rows:
        u = x["usage"]
        if int(u.get("firstAudioMs", -1)) >= 0:
            first.append(float(u["firstAudioMs"]))
        if int(u.get("usageEstimated", 0)):
            continue
        k = int(u.get("sessionTurn", 0))
        label = next((f"{a}–{b}" if b < 10_000 else f"{a}+" for a, b in BUCKETS if a <= k <= b), "?")
        b = by_bucket.setdefault(label, {"turns": 0, "inputUsd": 0.0, "formulaUsd": 0.0, "outputUsd": 0.0})
        b["turns"] += 1
        b["inputUsd"] += _in_usd(x)
        b["outputUsd"] += _out_usd(x)
        b["formulaUsd"] += formula(_audio_s(x))
    buckets = [
        {
            "sessionTurns": k,
            "turns": int(v["turns"]),
            "inputPerTurnUsd": round(v["inputUsd"] / v["turns"], 5),
            "formulaPerTurnUsd": round(v["formulaUsd"] / v["turns"], 5),
            "outputPerTurnUsd": round(v["outputUsd"] / v["turns"], 5),
            "diffPct": _pct(v["inputUsd"], v["formulaUsd"]),
        }
        for k, v in by_bucket.items()
    ]
    total_in = sum(_in_usd(x) for x in measured)
    total_f = sum(formula(_audio_s(x)) for x in measured)
    return {
        "item": item,
        "formula": {"interceptUsd": FIXED_USD, "slopeUsdPerS": PER_AUDIO_S_USD},
        "fit": _fit([(_audio_s(x), _in_usd(x)) for x in measured]),
        "games": out_games,
        "bySessionTurn": buckets,
        "total": {
            "turns": len(rows),
            "estimatedTurns": estimated,
            "totalUsd": round(sum(float(x.get("costUsd", 0)) for x in rows), 4),
            "inputUsd": round(total_in, 4),
            "outputUsd": round(sum(_out_usd(x) for x in measured), 4),
            "formulaInputUsd": round(total_f, 4),
            "diffPct": _pct(total_in, total_f),
            "fallbackUsd": round(fallback, 4),
        },
        "releaseToFirstAudioMs": {
            "n": len(first),
            "median": statistics.median(first) if first else None,
            "p95": _p95(first),
        },
    }


def markdown(r: Json) -> str:
    out = [f"# S-090 Live reconciliation ({r['item'] or 'all'}) / S-090 Live の照合（{r['item'] or 'すべて'}）", ""]
    t = r["total"]
    turns, est, total = t["turns"], t["estimatedTurns"], t["totalUsd"]
    inp, form, diff, outp = t["inputUsd"], t["formulaInputUsd"], t["diffPct"], t["outputUsd"]
    out.append(
        f"Total {turns} turns ({est} turns without usage, recorded at the estimate, not compared): cost ${total}; "
        f"input ${inp}, formula ${form}, diff {diff}%; output ${outp} / "
        f"合計 {turns} ターン（使用量が届かず見積もりで記録した {est} ターンは比べない）：費用 ${total}。"
        f"入力 ${inp}、式 ${form}、差 {diff}%。出力 ${outp}"
    )
    out.append(f"Transcript backfill ${t['fallbackUsd']} / 文字起こしの補完 ${t['fallbackUsd']}")
    f, fit = r["formula"], r["fit"]
    n, fi, fs, ki, ks = fit["n"], fit["interceptUsd"], fit["slopeUsdPerS"], f["interceptUsd"], f["slopeUsdPerS"]
    out.append(
        f"Fit (n={n}): intercept ${fi}, slope ${fs}/s; formula: intercept ${ki}, slope ${ks}/s / "
        f"フィット（n={n}）：切片 ${fi}、傾き ${fs}/秒。式：切片 ${ki}、傾き ${ks}/秒"
    )
    a = r["releaseToFirstAudioMs"]
    out += [
        "",
        f"Release to first audio (server side, S-073 ①): n={a['n']}, median {a['median']} ms, p95 {a['p95']} ms / "
        f"離してから最初の音声まで（サーバー側、S-073 ①）：n={a['n']}、中央値 {a['median']} ms、p95 {a['p95']} ms",
        "",
    ]
    out += [
        "| Game / 周回 | Turns / ターン数 | Estimated turns / 見積もりのターン | Sessions / セッション数 "
        "| Cost $ / 費用 $ | Input $ / 入力 $ | Formula $ / 式 $ | Diff % / 差 % | Output $ / 出力 $ |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    out += [
        f"| {g['game']} | {g['turns']} | {g['estimatedTurns']} | {g['sessions']} | {g['totalUsd']} | {g['inputUsd']} "
        f"| {g['formulaInputUsd']} | {g['diffPct']} | {g['outputUsd']} |"
        for g in r["games"]
    ]
    out += [
        "",
        "| Session turn / セッション内のターン | Turns / ターン数 | Input per turn $ / 1 ターンの入力 $ "
        "| Formula per turn $ / 1 ターンの式 $ | Diff % / 差 % | Output per turn $ / 1 ターンの出力 $ |",
        "|---|---|---|---|---|---|",
    ]
    out += [
        f"| {b['sessionTurns']} | {b['turns']} | {b['inputPerTurnUsd']} | {b['formulaPerTurnUsd']} | {b['diffPct']} "
        f"| {b['outputPerTurnUsd']} |"
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


# —— check (Mac only) / check（Mac のみ） ——


def _say_pcm(text: str) -> bytes | None:  # pragma: no cover - Mac only / Mac のみ
    """Synthesize a line with macOS say and convert it to 16 kHz PCM16 with afconvert. Without these two commands the
    speech turn is skipped.

    macOS の say で 1 句を合成し、afconvert で 16 kHz の PCM16 に変換する。この 2 つのコマンドがなければ音声のターンは
    飛ばす。
    """
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


async def _check(env: Mapping[str, str]) -> int:  # pragma: no cover - Mac only / Mac のみ
    from zoujin_backend.config import Settings
    from zoujin_backend.gateway.app import voices_of
    from zoujin_backend.gateway.fallback import VertexTranscriber
    from zoujin_backend.models import gemini_live
    from zoujin_backend.models.ledger import Ledger
    from zoujin_backend.voice.models import LIVE_MODEL, real_models

    s = Settings.from_env()
    if s.ledger is None or s.max_google_usd is None:
        print("ZJ_LEDGER and ZJ_MAX_GOOGLE_USD are required / ZJ_LEDGER と ZJ_MAX_GOOGLE_USD が必要", file=sys.stderr)
        return 2
    ledger = Ledger(s.ledger, s.max_google_usd, s.max_item_usd, s.ledger_item)
    ledger.before(CHECK_ESTIMATE_USD)
    _, rest = real_models(env)
    live = gemini_live.real_live(env, voices_of(), VertexTranscriber(rest))
    t0 = time.monotonic()
    session = await live.open("char.melos", (), CHECK_SYSTEM)
    setup_ms = round((time.monotonic() - t0) * 1000)
    print(f"Session set up in {setup_ms} ms / セッション確立 {setup_ms} ms")
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
            player, character = texts["player"], texts["character"]
            print(
                f"{mode}: release to first audio {ms} ms, player text {player}, character text {character}, "
                f"${usd:.5f} / {mode}：離してから最初の音声まで {ms} ms、プレイヤーの文字 {player}、"
                f"人物の文字 {character}、${usd:.5f}"
            )
    finally:
        await session.close()
    return 0


def cmd_check(args: argparse.Namespace) -> int:  # pragma: no cover - Mac only / Mac のみ
    if not args.confirm:
        usd = f"${CHECK_ESTIMATE_USD:.2f}"
        print(
            f"Estimated about {usd} (one text turn + one synthesized speech turn). Once confirmed, run again with "
            f"--confirm. / 見積もり約 {usd}（文字 1 ターン + 合成音声 1 ターン）。"
            "確認したら --confirm を付けて再実行する。"
        )
        return 0
    return asyncio.run(_check(os.environ))


async def run_probe(connect: Any, path: str, voice: str) -> list[tuple[str, str]]:
    from zoujin_backend.models.gemini_live import probe, setup_variants

    out = []
    for name, msg in setup_variants(model_path=path, voice=voice, system=CHECK_SYSTEM):
        out.append((name, await probe(connect, msg)))
    return out


def cmd_probe(args: argparse.Namespace) -> int:  # pragma: no cover - Mac only / Mac のみ
    from zoujin_backend.gateway.app import voices_of
    from zoujin_backend.models.gemini_live import real_connect

    connect, path = real_connect(os.environ)
    rows = asyncio.run(run_probe(connect, path, voices_of()["char.melos"]))
    for name, result in rows:
        print(f"{name}: {result}")
    return 0 if rows[0][1] == "ok" else 1


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        prog="zoujin-live",
        description="Real Live check and S-090 reconciliation (B-10) / 本物の Live の確認と S-090 の照合（B-10）",
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser(
        "check",
        help="Open one real session and speak two turns (Mac only) / "
        "本物のセッションを 1 つ開いて 2 ターン話す（Mac のみ）",
    )
    c.add_argument("--confirm", action="store_true")
    sub.add_parser(
        "probe",
        help="Only set up sessions without speaking, trying each setup once (Mac only, free) / "
        "話さずにセッションを確立するだけで、各 setup を 1 回ずつ試す（Mac のみ、費用なし）",
    )
    r = sub.add_parser(
        "reconcile",
        help="Reconcile each Live turn's cost in the ledger with the formula / "
        "台帳にある Live の各ターンの費用を式と照合する",
    )
    r.add_argument("--ledger", required=True)
    r.add_argument("--item", default="b10")
    r.add_argument("--out")
    args = p.parse_args(argv)
    cmds = {"check": cmd_check, "probe": cmd_probe, "reconcile": cmd_reconcile}
    sys.exit(cmds[args.cmd](args))
