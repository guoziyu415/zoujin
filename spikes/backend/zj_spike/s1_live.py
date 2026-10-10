"""S-1: Gemini Live in Japanese, measured from zg's Mac (Japan → us-central1).

  uv run python -m zj_spike.s1_live rtt          # network round trip to the Live endpoint (free)
  uv run python -m zj_spike.s1_live latency      # let-go → first audio, 3 sessions × 12 turns
  uv run python -m zj_spike.s1_live barge        # interrupting a long reply (barge-in)
  uv run python -m zj_spike.s1_live voices       # the same line in all 30 prebuilt voices
  uv run python -m zj_spike.s1_live casting      # UX's candidate voices per character + blind-listening kits
  uv run python -m zj_spike.s1_live midsession   # does a mid-session system note take effect?
  uv run python -m zj_spike.s1_live resume       # reconnect with a resumption handle keeps context
  uv run python -m zj_spike.s1_live transcripts  # why some replies come with audio but no text, and a fallback

Results go to out/s1/. Every turn is priced from its usage metadata and charged to the ledger.
What this cannot measure: the phone's 4G leg. That needs a public address (a deployment), which
zg approves separately (D-011); the frontend's S2 page will add it.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import csv
import io
import json
import os
import random
import socket
import time
import wave
from pathlib import Path

from google.genai import types

from . import common
from .live_util import (
    JA_RULE,
    close_session,
    open_session,
    OUT_RATE,
    cer,
    Probe,
    Turn,
    live_config,
    load_wav_dir,
    save_wav,
    send_text_turn,
    stream_utterance,
    synth_utterances,
)

DATA = Path(__file__).parent / "data"

# Proper nouns the player is likely to say (S-025: bias recognition toward them).
PROPER_NOUNS = ["メロス", "セリヌンティウス", "ディオニス", "シラクス", "フィロストラトス"]

# The 30 prebuilt voices shared by Live and TTS, with Google's one-word descriptions.
VOICES = [
    ("Zephyr", "Bright"), ("Puck", "Upbeat"), ("Charon", "Informative"), ("Kore", "Firm"),
    ("Fenrir", "Excitable"), ("Leda", "Youthful"), ("Orus", "Firm"), ("Aoede", "Breezy"),
    ("Callirrhoe", "Easy-going"), ("Autonoe", "Bright"), ("Enceladus", "Breathy"), ("Iapetus", "Clear"),
    ("Umbriel", "Easy-going"), ("Algieba", "Smooth"), ("Despina", "Smooth"), ("Erinome", "Clear"),
    ("Algenib", "Gravelly"), ("Rasalgethi", "Informative"), ("Laomedeia", "Upbeat"), ("Achernar", "Soft"),
    ("Alnilam", "Firm"), ("Schedar", "Even"), ("Gacrux", "Mature"), ("Pulcherrima", "Forward"),
    ("Achird", "Friendly"), ("Zubenelgenubi", "Casual"), ("Vindemiatrix", "Gentle"), ("Sadachbia", "Lively"),
    ("Sadaltager", "Knowledgeable"), ("Sulafat", "Warm"),
]

OLD_MAN = (
    "あなたはシラクスの市に住む老人です。王の暴虐を恐れ、人目を気にしながら小声で話します。"
    "へりくだった丁寧語（〜ます、〜ございませぬ）を使います。一度に一〜二文で、短く答えてください。"
    + JA_RULE
)

READER = (
    "あなたは朗読者です。ユーザーが「」で示した台詞を、日本語で、そのまま一度だけ、感情を込めて読み上げてください。"
    "前置き、説明、感想は一切言わないでください。"
)
CASTING_LINE = "「人の心を疑うのは、最も恥ずべき悪徳だ。……いいえ、私は必ず帰って来ます。」"


def stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def utterances(args) -> list[tuple[str, bytes]]:
    if args.wav_dir:
        return load_wav_dir(Path(args.wav_dir))
    lines = [l.strip() for l in (DATA / "s1_utterances.txt").read_text().splitlines() if l.strip() and not l.startswith("#")]
    return synth_utterances(lines, common.settings().out_dir / "s1" / "uplink")


async def connect(client, model: str, cfg):
    """Open a session and return (context manager, session, setup_ms). Quota errors stop the run."""
    return await open_session(client, model, cfg)


async def close(cm, probe: Probe | None) -> None:
    await close_session(cm, probe)


# ---------------------------------------------------------------- rtt


async def cmd_rtt(args) -> None:
    s = common.settings()
    host = f"{s.live_location}-aiplatform.googleapis.com"
    common.banner(f"S-1 rtt → {host}:443")
    samples = []
    for _ in range(7):
        t0 = time.perf_counter()
        with socket.create_connection((host, 443), timeout=5):
            samples.append(round((time.perf_counter() - t0) * 1000, 1))
        await asyncio.sleep(0.2)
    summary = common.summarize_ms(samples)
    print(f"TCP 建连往返（约等于一次网络往返）：{samples} → 中位数 {summary['p50']} ms")
    common.write_json(s.out_dir / "s1" / f"rtt-{stamp()}.json", {"host": host, "samples_ms": samples, "summary": summary})


# ---------------------------------------------------------------- latency


async def cmd_latency(args) -> None:
    s = common.settings()
    utts = utterances(args)
    client = common.genai_client(s.live_location)
    vocab = PROPER_NOUNS if args.vocab else None
    tag = f"latency-{args.thinking_level or 'default'}{'-vocab' if vocab else ''}-{stamp()}"
    out = s.out_dir / "s1" / tag
    common.banner(f"S-1 latency：{args.sessions} 个会话 × {len(utts)} 轮，声音 {args.voice}，思考 {args.thinking_level or '默认'}，"
                  f"专有名词偏置 {'开' if vocab else '关'}")
    rows, setups = [], []
    for si in range(1, args.sessions + 1):
        common.check_budget()
        cfg = live_config(OLD_MAN, args.voice, push_to_talk=True, thinking_level=args.thinking_level, vocabulary=vocab)
        cm, session, setup_ms = await connect(client, s.live_model, cfg)
        setups.append(setup_ms)
        probe = Probe(session)
        print(f"  会话 {si}：建立 {setup_ms} ms")
        try:
            for ti, (label, pcm) in enumerate(utts, 1):
                common.check_budget()
                released = await stream_utterance(session, pcm)
                turn = await probe.finish(Turn(started=released), timeout=45, what=f"s1 latency s{si}t{ti}")
                d = turn.to_dict()
                known = not args.wav_dir  # with synthesized lines we know exactly what was said
                d["transcript_cer"] = cer(label, d["user_transcript"]) if known else None
                d["names_missed"] = [n for n in PROPER_NOUNS if n in label and n not in d["user_transcript"]] if known else None
                d["speech_ms"] = round(len(pcm) / 2 / 16000 * 1000)
                rows.append({"session": si, "turn": ti, "said": label, **d})
                save_wav(out / f"s{si}-t{ti:02d}.wav", turn.audio)
                print(f"    {ti:2d}. 松开→首音 {d['first_audio_ms']} ms  回复 {d['audio_s']} s  「{d['reply_transcript'][:40]}」")
                await asyncio.sleep(args.pause)
        finally:
            await close(cm, probe)
    first = [r["first_audio_ms"] for r in rows]
    summary = {
        "release_to_first_audio_ms": common.summarize_ms(first),
        "session_setup_ms": common.summarize_ms(setups),
        "turns_without_audio": sum(1 for v in first if v is None),
        "first_turn_of_session_ms": [r["first_audio_ms"] for r in rows if r["turn"] == 1],
        # Negative = the player's own transcript starts arriving while they are still talking (S-025 live subtitles).
        "first_user_transcript_ms": common.summarize_ms([r["first_user_transcript_ms"] for r in rows]),
        "cost_usd": round(sum(r["cost_usd"] for r in rows), 4),
        "pass_rule": "S-017：中位数 ≤ 1800 ms（目标 1500），p95 ≤ 3000 ms；这里不含手机 4G 那一段",
        "transcript_cer_mean": (round(sum(c) / len(c), 3) if (c := [r["transcript_cer"] for r in rows if r["transcript_cer"] is not None]) else None),
        "proper_noun_misses": sum(len(r["names_missed"] or []) for r in rows),
        "proper_noun_mentions": sum(1 for r in rows for n in PROPER_NOUNS if not args.wav_dir and n in r["said"]),
    }
    common.write_json(out / "result.json", {"model": s.live_model, "location": s.live_location, "voice": args.voice,
                                            "thinking_level": args.thinking_level, "vocabulary": vocab,
                                            "summary": summary, "turns": rows})
    l = summary["release_to_first_audio_ms"]
    print(f"\n松开→首音：中位数 {l.get('p50')} ms，p90 {l.get('p90')} ms，p95 {l.get('p95')} ms（n={l.get('n')}）")
    print(f"会话建立：中位数 {summary['session_setup_ms'].get('p50')} ms；本项花费约 ${summary['cost_usd']}")
    ut = summary["first_user_transcript_ms"]
    if ut.get("n"):
        print(f"玩家字幕第一段：相对松开 中位数 {ut.get('p50')} ms（负数 = 说话途中就开始出字幕）")
    if summary["transcript_cer_mean"] is not None:
        print(f"玩家字幕：平均字错率 {summary['transcript_cer_mean']:.1%}；专有名词认错 "
              f"{summary['proper_noun_misses']}/{summary['proper_noun_mentions']} 次")
    print(f"结果：{out}/result.json；回复音频在同一目录")


# ---------------------------------------------------------------- barge-in


async def cmd_barge(args) -> None:
    s = common.settings()
    client = common.genai_client(s.live_location)
    out = s.out_dir / "s1" / f"barge-{stamp()}"
    interrupt_pcm = synth_utterances(["ちょっと待ってください。"], out / "uplink")[0][1]
    common.banner(f"S-1 barge：{args.reps} 次，在回复播出 {args.after}s 后按下说话")
    rows = []
    for rep in range(1, args.reps + 1):
        common.check_budget()
        cfg = live_config(OLD_MAN.replace("一度に一〜二文で、短く答えてください。", ""), args.voice, push_to_talk=True)
        cm, session, _ = await connect(client, s.live_model, cfg)
        probe = Probe(session)
        try:
            started = await send_text_turn(session, "この町と王様のことを、できるだけ詳しく、ゆっくり長く話してください。")
            long_turn = Turn(started=started)
            done_early = False
            # Read until we have heard `after` seconds' worth of wall clock since the first audio.
            while True:
                try:
                    now, msg = await probe.get(0.05)
                    if probe.absorb(long_turn, now, msg):
                        done_early = True
                        break
                except asyncio.TimeoutError:
                    pass
                if long_turn.first_audio and time.perf_counter() - long_turn.first_audio >= args.after:
                    break
            if done_early:
                long_turn.completed = time.perf_counter()
                common.charge(common.live_usage_cost(long_turn.usage) or 0.01, f"s1 barge r{rep} (too short)")
                rows.append({"rep": rep, "result": "reply ended before barge-in", **long_turn.to_dict()})
                print(f"  {rep}. 回复太短，没能打断")
                continue
            pressed = time.perf_counter()
            sender = asyncio.create_task(stream_utterance(session, interrupt_pcm))
            long_turn = await probe.finish(long_turn, timeout=30, what=f"s1 barge r{rep} long")
            released = await sender
            after_press = [t for t in long_turn.audio_after if t >= pressed]
            reply = await probe.finish(Turn(started=released), timeout=30, what=f"s1 barge r{rep} reply")
            row = {
                "rep": rep,
                "press_to_interrupted_ms": None if long_turn.interrupted_at is None else round((long_turn.interrupted_at - pressed) * 1000),
                "audio_chunks_after_press": len(after_press),
                "last_audio_after_press_ms": round((after_press[-1] - pressed) * 1000) if after_press else 0,
                "long_reply_heard_s": round(pressed - long_turn.first_audio, 2),
                "long_reply_generated_s": round(long_turn.audio_seconds, 2),
                "reply_after_barge": reply.to_dict(),
            }
            rows.append(row)
            save_wav(out / f"r{rep}-long.wav", long_turn.audio)
            save_wav(out / f"r{rep}-reply.wav", reply.audio)
            print(f"  {rep}. 按下→interrupted {row['press_to_interrupted_ms']} ms，按下后还收到 {row['audio_chunks_after_press']} 个音频包；"
                  f"打断后回复首音 {row['reply_after_barge']['first_audio_ms']} ms「{row['reply_after_barge']['reply_transcript'][:30]}」")
        finally:
            await close(cm, probe)
    vals = [r.get("press_to_interrupted_ms") for r in rows if r.get("press_to_interrupted_ms") is not None]
    summary = {"press_to_interrupted_ms": common.summarize_ms(vals),
               "note": "S-014/S-017 的 0.2 s 是前端本地停播；这里量的是服务端确认打断的时间，决定模型上下文里记到哪"}
    common.write_json(out / "result.json", {"summary": summary, "reps": rows})
    print(f"\n按下→服务端确认打断：中位数 {summary['press_to_interrupted_ms'].get('p50')} ms。结果：{out}/result.json")


# ---------------------------------------------------------------- voices


async def cmd_voices(args) -> None:
    s = common.settings()
    client = common.genai_client(s.live_location)
    out = s.out_dir / "s1" / "voices"
    chosen = [v for v in VOICES if not args.only or v[0] in args.only.split(",")]
    common.banner(f"S-1 voices：{len(chosen)} 个声音读同一句台词")
    rows = []
    for name, desc in chosen:
        common.check_budget()
        row = {"voice": name, "google_desc": desc, "audio_s": None, "setup_ms": None, "transcript": "",
               "transcript_late_ms": None, "error": "", "候选角色": "", "备注": ""}
        try:
            cm, session, row["setup_ms"] = await connect(client, s.live_model, live_config(READER, name, push_to_talk=True))
            probe = Probe(session)
            try:
                started = await send_text_turn(session, CASTING_LINE)
                turn = await probe.finish(Turn(started=started), timeout=30, what=f"s1 voice {name}")
            finally:
                await close(cm, probe)
            save_wav(out / f"{name}.wav", turn.audio)
            row["audio_s"] = round(turn.audio_seconds, 1)
            row["transcript"] = turn.out_text.strip()
            row["transcript_late_ms"] = turn.to_dict()["transcript_late_ms"]
            print(f"  {name:14s} {desc:14s} {row['audio_s']} s「{row['transcript'][:30]}」")
        except common.QuotaHit:
            raise
        except common.BudgetExceeded:
            raise
        except Exception as exc:
            row["error"] = str(exc)[:300]
            print(f"  {name:14s} 不可用：{row['error'][:120]}")
        rows.append(row)
    with open(out / "voices.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\n音频和 voices.csv 在 {out}。UX 和后端试听后在「候选角色」一栏填 7 个角色的搭配。")


# ---------------------------------------------------------------- casting (ux-design §16)


CAST_READER = (
    "あなたは声優です。次の人物を演じます。ユーザーが「」で示した台詞を、この人物として、そのまま一度だけ読んでください。"
    "前置き、説明、感想、相づちは一切言わないでください。\n人物：{direction}"
)
GAP = b"\x00\x00" * int(OUT_RATE * 0.6)


def read_wav_pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as w:
        return w.readframes(w.getnframes())


def parse_pick(text: str | None, chars: dict) -> dict[str, str]:
    pick = {k: c["candidates"][0] for k, c in chars.items()}
    for item in filter(None, (text or "").split(",")):
        key, _, voice = item.partition("=")
        if key.strip() not in chars or not voice.strip():
            raise SystemExit(f"--pick 写法不对：{item}（例：melos=Fenrir,king=Charon；角色键：{', '.join(chars)}）")
        pick[key.strip()] = voice.strip()
    return pick


async def cast_voice(client, model: str, ch: dict, voice: str, lines: list[tuple[str, str]], d: Path) -> list[dict]:
    """One session per (character, voice); every line is one text turn. Returns one row per line."""
    rows = []
    cm, session, setup_ms = await connect(client, model, live_config(CAST_READER.format(direction=ch["direction"]), voice))
    probe = Probe(session)
    try:
        for clip, line in lines:
            common.check_budget()
            started = await send_text_turn(session, f"「{line}」")
            turn = await probe.finish(Turn(started=started), timeout=30, what=f"s1 casting {voice}")
            save_wav(d / f"{clip}.wav", turn.audio)
            heard = turn.out_text.strip()
            miss = cer(line, heard)
            # No transcript = unknown, not a misreading: listen to the clip.
            rows.append({"clip": clip, "line": line, "transcript": heard, "audio_s": round(turn.audio_seconds, 1),
                         "setup_ms": setup_ms, "transcript_late_ms": turn.to_dict()["transcript_late_ms"],
                         "读走样": None if not heard or miss is None else miss > 0.3, "error": ""})
    finally:
        await close(cm, probe)
    return rows


def build_blind_kits(root: Path, spec: dict, pick: dict[str, str]) -> list[dict]:
    """Per scene pair: two labelled reference clips, then the neutral clips of both in a fixed shuffled order."""
    chars = spec["characters"]
    blind = root / "blind"
    answers = []
    for i, pair in enumerate(spec["pairs"], 1):
        a, b = pair["a"], pair["b"]
        src = {k: root / "clips" / k / pick[k] for k in (a, b)}
        if not all((src[k] / "ref.wav").exists() for k in (a, b)):
            print(f"  [跳过盲听] {pair['scene']} {chars[a]['name']}/{chars[b]['name']}：{pick[a]} 或 {pick[b]} 还没生成")
            continue
        kit = blind / f"{i}-{pair['scene']}-{a}-{b}"
        kit.mkdir(parents=True, exist_ok=True)
        for old in kit.glob("*.wav"):
            old.unlink()
        save_wav(kit / f"参考A-{chars[a]['name']}.wav", read_wav_pcm(src[a] / "ref.wav"))
        save_wav(kit / f"参考B-{chars[b]['name']}.wav", read_wav_pcm(src[b] / "ref.wav"))
        clips = [(k, f"n{j}") for k in (a, b) for j in range(1, len(spec["neutral"]) + 1)]
        random.Random(f"{i}-{pick[a]}-{pick[b]}").shuffle(clips)
        for n, (k, clip) in enumerate(clips, 1):
            save_wav(kit / f"片段{n}.wav", read_wav_pcm(src[k] / f"{clip}.wav"))
            answers.append({"组": kit.name, "片段": n, "答案": "A" if k == a else "B", "角色": chars[k]["name"], "声音": pick[k]})
    if answers:
        with open(blind / "answers.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(answers[0].keys()))
            w.writeheader()
            w.writerows(answers)
        combo = ", ".join(f"{chars[k]['name']}={v}" for k, v in pick.items())
        (blind / "怎么测.txt").write_text(
            "每组给听的人：先放「参考A」「参考B」各一遍，然后按顺序放片段1〜6，每段让他说是 A 还是 B。\n"
            "片段里两个人读的是同样的句子，只能靠声音分辨。不要让听的人看到 answers.csv。\n"
            "5 个人都听完后，对照 answers.csv 算答对的比例，≥90% 算这组分得开（ux-design §16）。\n"
            f"这次用的搭配：{combo}\n"
            "换搭配：uv run python -m zj_spike.s1_live casting --pick melos=Fenrir,king=Charon（已生成的声音不再花钱）\n",
            encoding="utf-8",
        )
    return answers


async def cmd_casting(args) -> None:
    s = common.settings()
    spec = json.loads((DATA / "s1_casting.json").read_text(encoding="utf-8"))
    chars = spec["characters"]
    only = set(args.only.split(",")) if args.only else set(chars)
    pick = parse_pick(args.pick, chars)
    root = s.out_dir / "s1" / "casting"
    jobs = [(k, v) for k, c in chars.items() if k in only for v in c["candidates"]]
    jobs += [(k, v) for k, v in pick.items() if k in only and (k, v) not in jobs]
    per = len(next(iter(chars.values()))["own"]) + len(spec["neutral"]) + 1
    common.banner(f"S-1 casting：{len(jobs)} 个（角色, 声音）组合，每个读 {per} 句")
    client = common.genai_client(s.live_location)
    rows = []
    for key, voice in jobs:
        ch = chars[key]
        d = root / "clips" / key / voice
        lines = [(f"own{i}", l) for i, l in enumerate(ch["own"], 1)]
        lines += [(f"n{i}", l) for i, l in enumerate(spec["neutral"], 1)] + [("ref", spec["ref"])]
        if not args.redo and all((d / f"{c}.wav").exists() for c, _ in lines):
            print(f"  {ch['name']:10s} {voice:12s} 已有，跳过（--redo 重新生成）")
            continue
        try:
            got = await cast_voice(client, s.live_model, ch, voice, lines, d)
        except (common.QuotaHit, common.BudgetExceeded):
            raise
        except Exception as exc:
            got = [{"clip": "", "line": "", "transcript": "", "audio_s": None, "setup_ms": None,
                    "transcript_late_ms": None, "读走样": None, "error": str(exc)[:300]}]
            print(f"  {ch['name']:10s} {voice:12s} 出错：{str(exc)[:120]}")
        rows += [{"角色": ch["name"], "声音": voice, **r} for r in got]
        own = [d / f"own{i}.wav" for i in range(1, len(ch["own"]) + 1)]
        if all(p.exists() for p in own):
            save_wav(root / "listen" / f"{key}-{voice}.wav", GAP.join(read_wav_pcm(p) for p in own))
            bad = sum(1 for r in got if r["读走样"])
            unknown = sum(1 for r in got if r["读走样"] is None and not r["error"])
            print(f"  {ch['name']:10s} {voice:12s} 好了" + (f"（{bad} 句和原文不一样，听一下）" if bad else "")
                  + (f"（{unknown} 句没回传文字，听一下）" if unknown else ""))
    if rows:
        root.mkdir(parents=True, exist_ok=True)
        with open(root / f"casting-{stamp()}.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    answers = build_blind_kits(root, spec, pick)
    print(f"\n试听：{root}/listen/（一个文件 = 一个角色用一个声音读自己的 3 句）")
    print(f"盲听：{root}/blind/（{len({a['组'] for a in answers})} 组，做法见 怎么测.txt）")


# ---------------------------------------------------------------- transcripts (results-s1.md 2.3)


TALK = ("あなたは{name}です。{direction}\n旅の者と話しています。{name}として、一度に二〜四文で答えてください。" + JA_RULE)
TALK_QUESTIONS = [
    "こんにちは。あなたはどんな方ですか。",
    "この町の暮らしについて、少し聞かせてください。",
    "最近、何か心配なことはありますか。",
    "今日の天気をどう思いますか。",
    "あなたの大切な人について教えてください。",
    "もし一つだけ願いが叶うなら、何を願いますか。",
    "最後に、旅の者に一言お願いします。",
]
FALLBACK_PROMPT = ("次の音声は日本語の台詞です。聞こえたとおりに書き起こしてください。"
                   "書き起こした文だけを出力し、説明や引用符は付けないでください。")
# multi = the casting setup (one session, seven lines read in a row); fresh = one session per line;
# ja = multi with a ja-JP hint on the character's transcript; talk = one session, seven turns of free conversation.
MODES = ("multi", "fresh", "ja", "talk")
FALLBACK_TIMEOUT_S = 30.0


def wav_bytes(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(OUT_RATE)
        w.writeframes(bytes(pcm))
    return buf.getvalue()


async def fallback_transcribe(client, model: str, pcm: bytes) -> dict:
    """The production fallback candidate: transcribe the character's audio with a text model."""
    config = types.GenerateContentConfig(labels=common.LABELS, temperature=0)
    contents = [types.Part.from_bytes(data=wav_bytes(pcm), mime_type="audio/wav"), FALLBACK_PROMPT]
    common.check_budget()
    t0 = time.perf_counter()
    try:
        resp = await asyncio.wait_for(client.aio.models.generate_content(model=model, contents=contents, config=config),
                                      timeout=FALLBACK_TIMEOUT_S)
    except (common.QuotaHit, common.BudgetExceeded):
        raise
    except Exception as exc:
        common.stop_on_quota(exc)
        return {"fb_text": "", "fb_ms": None, "fb_error": f"{type(exc).__name__}: {exc}"[:200], "fb_usd": 0.0}
    cost = common.flash_usage_cost(resp.usage_metadata)  # Flash prices: errs high for Flash-Lite
    common.charge(cost, "s1 transcripts fallback")
    return {"fb_text": (resp.text or "").strip(), "fb_ms": round((time.perf_counter() - t0) * 1000),
            "fb_error": "", "fb_usd": round(cost, 6)}


async def transcript_turns(client, model: str, cfg, prompts: list[str], what: str, tail_cap: float) -> list[Turn]:
    cm, session, _ = await connect(client, model, cfg)
    probe = Probe(session)
    turns = []
    try:
        for text in prompts:
            common.check_budget()
            started = await send_text_turn(session, text)
            turns.append(await probe.finish(Turn(started=started, log=[]), timeout=40, what=what, tail_cap=tail_cap))
    finally:
        await close(cm, probe)
    return turns


async def cmd_transcripts(args) -> None:
    s = common.settings()
    spec = json.loads((DATA / "s1_casting.json").read_text(encoding="utf-8"))
    chars = spec["characters"]
    pairs = [x.split(":") for x in args.voices.split(",") if x]
    if any(len(x) != 2 or x[1] not in chars for x in pairs):
        raise SystemExit(f"--voices 写法：声音:角色，例 Charon:king（角色键：{', '.join(chars)}）")
    modes = [m for m in args.modes.split(",") if m]
    if any(m not in MODES for m in modes):
        raise SystemExit(f"--modes 只能是 {', '.join(MODES)}")
    live = common.genai_client(s.live_location)
    text = common.genai_client(s.text_location)
    fb_model = os.environ.get("ZJ_FALLBACK_MODEL", "gemini-3.5-flash-lite")
    out = s.out_dir / "s1" / "transcripts" / stamp()
    n_turns = len(pairs) * args.repeat * sum(7 for _ in modes)
    common.banner(f"S-1 transcripts：{len(pairs)} 个声音 × {len(modes)} 种情况 × {args.repeat} 遍，共 {n_turns} 轮；补转写用 {fb_model}")
    rows, logs = [], []
    for rep in range(1, args.repeat + 1):
        for voice, key in pairs:
            ch = chars[key]
            lines = list(ch["own"]) + list(spec["neutral"]) + [spec["ref"]]
            for mode in modes:
                what = f"s1 transcripts {mode} {voice}"
                try:
                    if mode == "talk":
                        cfg = live_config(TALK.format(name=ch["name"], direction=ch["direction"]), voice)
                        turns = await transcript_turns(live, s.live_model, cfg, TALK_QUESTIONS, what, args.wait)
                    elif mode == "fresh":
                        cfg = live_config(CAST_READER.format(direction=ch["direction"]), voice)
                        turns = [(await transcript_turns(live, s.live_model, cfg, [f"「{l}」"], what, args.wait))[0] for l in lines]
                    else:
                        cfg = live_config(CAST_READER.format(direction=ch["direction"]), voice, reply_lang="ja-JP" if mode == "ja" else None)
                        turns = await transcript_turns(live, s.live_model, cfg, [f"「{l}」" for l in lines], what, args.wait)
                except (common.QuotaHit, common.BudgetExceeded):
                    raise
                except Exception as exc:
                    rows.append({"mode": mode, "voice": voice, "character": key, "rep": rep, "pos": None,
                                 "error": f"{type(exc).__name__}: {exc}"[:300]})
                    print(f"  [{mode:5s}] {voice:10s} 出错：{rows[-1]['error'][:120]}")
                    continue
                for pos, turn in enumerate(turns, 1):
                    d = turn.to_dict()
                    ref = TALK_QUESTIONS[pos - 1] if mode == "talk" else lines[pos - 1]
                    heard = turn.out_text.strip()
                    fb = await fallback_transcribe(text, fb_model, turn.audio) if turn.audio else {"fb_text": "", "fb_ms": None, "fb_error": "no audio", "fb_usd": 0.0}
                    row = {"mode": mode, "voice": voice, "character": key, "rep": rep, "pos": pos, "prompt": ref,
                           "audio_s": d["audio_s"], "text": heard, "empty": not heard,
                           "live_cer": None if mode == "talk" or not heard else cer(ref, heard),
                           "transcript_late_ms": d["transcript_late_ms"], "out_msgs": d["out_transcription_msgs"],
                           "out_finished": d["out_transcription_finished"], "first_text_ms": d["first_text_ms"],
                           "generation_complete_ms": d["generation_complete_ms"], "complete_ms": d["complete_ms"],
                           "turn_complete_reason": d["turn_complete_reason"], **fb,
                           # reading: against the line; talk: against Live's own text when there is one
                           "fb_cer": (cer(heard, fb["fb_text"]) if heard else None) if mode == "talk" else cer(ref, fb["fb_text"]),
                           "error": ""}
                    rows.append(row)
                    logs.append({k: row[k] for k in ("mode", "voice", "rep", "pos")} | {"log": turn.log})
                    if not heard and turn.audio:
                        save_wav(out / "wav" / f"{mode}-{voice}-{rep}-{pos}.wav", turn.audio)
                got = [r for r in rows[-len(turns):]]
                print(f"  [{mode:5s}] {voice:10s} {ch['name']:8s} 第 {rep} 遍：没文字 {sum(r['empty'] for r in got)}/{len(got)}，"
                      f"补转写字错率 {[r['fb_cer'] for r in got]}")
    ok = [r for r in rows if not r["error"]]
    summary = {}
    for mode in modes:
        rs = [r for r in ok if r["mode"] == mode]
        if not rs:
            continue
        empty = [r for r in rs if r["empty"]]
        fbs = [r for r in rs if not r["fb_error"]]
        summary[mode] = {
            "turns": len(rs), "errors": sum(1 for r in rows if r["mode"] == mode and r["error"]),
            "empty": len(empty), "empty_rate": round(len(empty) / len(rs), 3),
            "empty_by_position": [sum(1 for r in empty if r["pos"] == i) for i in range(1, 8)],
            "empty_by_voice": dict(collections.Counter(r["voice"] for r in empty)),
            "empty_with_no_transcript_msgs": sum(1 for r in empty if not r["out_msgs"]),
            "finished_seen": sum(1 for r in rs if r["out_finished"]),
            "late_text": sum(1 for r in rs if r["transcript_late_ms"] is not None),
            "late_text_max_ms": max((r["transcript_late_ms"] for r in rs if r["transcript_late_ms"] is not None), default=None),
            "turn_complete_reason": dict(collections.Counter(str(r["turn_complete_reason"]) for r in rs)),
            "audio_s_empty": common.summarize_ms([r["audio_s"] for r in empty]),
            "audio_s_with_text": common.summarize_ms([r["audio_s"] for r in rs if not r["empty"]]),
            "live_cer": common.summarize_ms([r["live_cer"] for r in rs if r["live_cer"] is not None]),
            "fallback_errors": len(rs) - len(fbs),
            "fallback_cer": common.summarize_ms([r["fb_cer"] for r in fbs if r["fb_cer"] is not None]),
            "fallback_cer_on_empty": common.summarize_ms([r["fb_cer"] for r in fbs if r["empty"] and r["fb_cer"] is not None]),
            "fallback_ms": common.summarize_ms([r["fb_ms"] for r in fbs]),
            "fallback_usd": round(sum(r["fb_usd"] for r in fbs), 5),
        }
    common.write_json(out / "summary.json", {"model": s.live_model, "fallback_model": fb_model, "wait_s": args.wait, "summary": summary})
    with open(out / "turns.csv", "w", newline="", encoding="utf-8-sig") as f:
        fields = list(dict.fromkeys(k for r in rows for k in r))
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    (out / "log.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in logs), encoding="utf-8")
    print("\n情况    轮数  没文字  完全没有文字消息  晚到  补转写字错率(中位/p90)  补转写耗时(中位/p95 ms)")
    for mode, v in summary.items():
        print(f"{mode:6s} {v['turns']:5d} {v['empty']:6d} {v['empty_with_no_transcript_msgs']:16d} {v['late_text']:5d}"
              f"   {v['fallback_cer'].get('p50')}/{v['fallback_cer'].get('p90')}"
              f"   {v['fallback_ms'].get('p50')}/{v['fallback_ms'].get('p95')}")
    print(f"\n结果：{out}（summary.json、turns.csv、log.jsonl；没文字的那几轮的声音在 wav/）")


# ---------------------------------------------------------------- mid-session note


NOTE = "たった今、広場の鐘が三度鳴った。あなたもそれをはっきり聞いた。"
NOTE_QUESTION = "今、何か音がしませんでしたか。"
NOTE_KEYWORDS = ("鐘", "かね", "カネ")


async def cmd_midsession(args) -> None:
    s = common.settings()
    client = common.genai_client(s.live_location)
    out = s.out_dir / "s1" / f"midsession-{stamp()}"
    methods = ["system", "user_note", "none"]
    common.banner(f"S-1 midsession：3 种方式 × {args.reps} 次（none 是对照组）")
    rows = []
    for method in methods:
        for rep in range(1, args.reps + 1):
            common.check_budget()
            row = {"method": method, "rep": rep, "error": "", "unprompted_reply": False}
            cm, session, _ = await connect(client, s.live_model, live_config(OLD_MAN, args.voice, push_to_talk=True))
            probe = Probe(session)
            try:
                started = await send_text_turn(session, "こんばんは。")
                await probe.finish(Turn(started=started), timeout=30, what=f"s1 mid {method} r{rep} hello")
                if method == "system":
                    await session.send_client_content(
                        turns=types.Content(role="system", parts=[types.Part(text=NOTE)]), turn_complete=False)
                elif method == "user_note":
                    await session.send_client_content(
                        turns=types.Content(role="user", parts=[types.Part(text=f"（語り手からの注記。返事はしないこと：{NOTE}）")]),
                        turn_complete=False)
                # Anything the model says before we ask is an unwanted reply to the note.
                stray = Turn(started=time.perf_counter())
                try:
                    while True:
                        now, msg = await probe.get(1.5)
                        if probe.absorb(stray, now, msg):
                            row["unprompted_reply"] = True
                            common.charge(common.live_usage_cost(stray.usage) or 0.01, f"s1 mid {method} r{rep} stray")
                            break
                except asyncio.TimeoutError:
                    pass
                started = await send_text_turn(session, NOTE_QUESTION)
                turn = await probe.finish(Turn(started=started), timeout=30, what=f"s1 mid {method} r{rep} ask")
                text = turn.out_text.strip()
                row.update(reply=text, mentions_bell=any(k in text for k in NOTE_KEYWORDS))
                print(f"  {method:9s} {rep}. 提到钟声={row['mentions_bell']}  「{text[:50]}」")
            except (common.QuotaHit, common.BudgetExceeded):
                raise
            except Exception as exc:
                row["error"] = str(exc)[:300]
                print(f"  {method:9s} {rep}. 出错：{row['error'][:120]}")
            finally:
                await close(cm, probe)
            rows.append(row)
    summary = {m: {"mentions_bell": sum(1 for r in rows if r["method"] == m and r.get("mentions_bell")),
                   "errors": sum(1 for r in rows if r["method"] == m and r["error"]),
                   "unprompted_replies": sum(1 for r in rows if r["method"] == m and r["unprompted_reply"]),
                   "n": args.reps} for m in methods}
    common.write_json(out / "result.json", {"note": NOTE, "question": NOTE_QUESTION, "summary": summary, "reps": rows})
    print(f"\n{summary}\n结果：{out}/result.json")


# ---------------------------------------------------------------- resumption


async def cmd_resume(args) -> None:
    s = common.settings()
    client = common.genai_client(s.live_location)
    out = s.out_dir / "s1" / f"resume-{stamp()}"
    common.banner(f"S-1 resume：断开后用恢复句柄重连 × {args.reps}，另加 1 次不带句柄的对照")
    rows = []
    for rep in range(1, args.reps + 2):
        control = rep == args.reps + 1
        common.check_budget()
        row = {"rep": rep, "control": control, "error": ""}
        try:
            cm, session, _ = await connect(client, s.live_model, live_config(OLD_MAN, args.voice, resumable=True))
            probe = Probe(session)
            try:
                started = await send_text_turn(session, "私の名前はケンです。覚えておいてくださいね。")
                await probe.finish(Turn(started=started), timeout=30, what=f"s1 resume r{rep} a")
                for _ in range(40):
                    if probe.resume_handle:
                        break
                    await asyncio.sleep(0.05)
                handle = probe.resume_handle
            finally:
                await close(cm, probe)
            row["got_handle"] = bool(handle)  # the first session handed out a handle (always expected)
            row["used_handle"] = bool(handle) and not control  # the control reconnects without it
            cfg = live_config(OLD_MAN, args.voice, resumable=True, resume_handle=None if control else handle)
            cm, session, row["reconnect_ms"] = await connect(client, s.live_model, cfg)
            probe = Probe(session)
            try:
                started = await send_text_turn(session, "私の名前、覚えていますか。")
                turn = await probe.finish(Turn(started=started), timeout=30, what=f"s1 resume r{rep} b")
            finally:
                await close(cm, probe)
            text = turn.out_text.strip()
            row.update(reply=text, remembers=("ケン" in text or "けん" in text))
            print(f"  {'对照' if control else rep}. 第一次拿到句柄={row['got_handle']} 重连时用句柄={row['used_handle']} "
                  f"重连 {row['reconnect_ms']} ms 记得名字={row['remembers']}「{text[:40]}」")
        except (common.QuotaHit, common.BudgetExceeded):
            raise
        except Exception as exc:
            row["error"] = str(exc)[:300]
            print(f"  {rep}. 出错：{row['error'][:120]}")
        rows.append(row)
    common.write_json(out / "result.json", {"reps": rows})
    print(f"结果：{out}/result.json")


# ---------------------------------------------------------------- cli


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("rtt")
    p = sub.add_parser("latency")
    p.add_argument("--sessions", type=int, default=3)
    p.add_argument("--voice", default="Algenib")
    p.add_argument("--thinking-level", choices=["minimal", "low", "medium", "high"], default=None,
                   help="不填 = 模型默认；建议默认跑一遍，再用 minimal 跑一遍对比")
    p.add_argument("--wav-dir", help="用自己录的 WAV 代替 say 合成的语音")
    p.add_argument("--pause", type=float, default=0.8, help="两轮之间停顿几秒")
    p.add_argument("--vocab", action="store_true", help="给玩家转写加专有名词偏置（メロス、セリヌンティウス等）")
    p = sub.add_parser("barge")
    p.add_argument("--reps", type=int, default=5)
    p.add_argument("--after", type=float, default=1.5, help="回复开始播出几秒后打断")
    p.add_argument("--voice", default="Algenib")
    p = sub.add_parser("voices")
    p.add_argument("--only", help="只试这些声音，逗号分隔")
    p = sub.add_parser("casting")
    p.add_argument("--only", help="只做这些角色，逗号分隔（melos,king,selinuntius,sister,groom,philostratus,old-man）")
    p.add_argument("--pick", help="盲听用的搭配，例：melos=Fenrir,king=Charon；不填的角色用第一个候选")
    p.add_argument("--redo", action="store_true", help="已生成的也重新生成")
    p = sub.add_parser("midsession")
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--voice", default="Algenib")
    p = sub.add_parser("resume")
    p.add_argument("--reps", type=int, default=2)
    p.add_argument("--voice", default="Algenib")
    p = sub.add_parser("transcripts")
    p.add_argument("--voices", default="Charon:king,Despina:sister,Fenrir:melos",
                   help="声音:角色，逗号分隔；默认 casting 里没文字最多的两个和一个少的")
    p.add_argument("--modes", default=",".join(MODES), help="multi 连读、fresh 每句新会话、ja 人物转写指定日语、talk 自由对话")
    p.add_argument("--repeat", type=int, default=2)
    p.add_argument("--wait", type=float, default=10.0, help="说完后最多再等几秒人物的文字")
    args = ap.parse_args()
    handler = {"rtt": cmd_rtt, "latency": cmd_latency, "barge": cmd_barge, "voices": cmd_voices,
               "casting": cmd_casting, "midsession": cmd_midsession, "resume": cmd_resume,
               "transcripts": cmd_transcripts}[args.cmd]
    common.run(lambda: handler(args))


if __name__ == "__main__":
    main()
