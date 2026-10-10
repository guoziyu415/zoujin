"""T-003 step 4: confirm the new project can call what the spikes need. Costs well under US$0.05.

  uv run python -m zj_spike.s0_check

Checks, in order, and stops at the first failure:
  1. application-default credentials load (quota project forced to ZJ_PROJECT)
  2. gemini-3.8-flash answers one short text request (labels app=zoujin-spike)
  3. gemini-3.8-live opens a session, speaks one short reply, and reports usage
     (if the model is not available to the project, tries the GA fallback and says so)
  4. Model Armor in ZJ_ARMOR_LOCATION (default us-central1) answers a list call (creates nothing)
"""

from __future__ import annotations

import time

from google.genai import types

from . import common
from .live_util import JA_RULE, Probe, Turn, live_config, save_wav, send_text_turn

FALLBACK_LIVE_MODEL = "gemini-live-2.5-flash-native-audio"


def ok(msg: str) -> None:
    print(f"  [OK] {msg}", flush=True)


def fail(msg: str) -> None:
    print(f"  [失败] {msg}", flush=True)


async def check_live(s: common.Settings, model: str, transcribe_lang: str | None = None) -> dict:
    client = common.genai_client(s.live_location)
    cfg = live_config("あなたは案内係です。" + JA_RULE + "一文だけで短く答えてください。", voice=None, push_to_talk=True,
                      transcribe_lang=transcribe_lang)
    t0 = time.perf_counter()
    async with client.aio.live.connect(model=model, config=cfg) as session:
        setup_ms = round((time.perf_counter() - t0) * 1000)
        probe = Probe(session)
        try:
            started = await send_text_turn(session, "こんにちは。今日はいい天気ですね。")
            turn = await probe.finish(Turn(started=started), timeout=30, what=f"s0 live {model}")
        finally:
            await probe.close()
    save_wav(s.out_dir / "s0" / "live_hello.wav", turn.audio)
    return {"model": model, "setup_ms": setup_ms, **turn.to_dict()}


async def live_step(s: common.Settings) -> dict:
    """Try the configured model; on failure, rule out the transcription hint, then try the GA fallback."""
    try:
        live = await check_live(s, s.live_model)
        ok(f"建会话 {live['setup_ms']} ms，发出到首个音频 {live['first_audio_ms']} ms，回复「{live['reply_transcript']}」")
        ok(f"用量消息 {live['usage_msgs']} 条；本次约 ${live['cost_usd']:.4f}（音频存到 out/s0/live_hello.wav）")
        return live
    except Exception as exc:
        common.stop_on_quota(exc)
        primary_error = str(exc)[:500]
        fail(f"{s.live_model}: {primary_error}")

    print("  → 先排除配置问题：同一个模型，去掉玩家转写的 ja-JP 语言提示再试一次")
    try:
        live = await check_live(s, s.live_model, transcribe_lang="")
        ok("去掉语言提示后可用。之后每条命令前加 ZJ_TRANSCRIBE_LANG= （等号后留空），并把上面的错误转给后端")
        return {"primary_error": primary_error, "needs": "ZJ_TRANSCRIBE_LANG=", **live}
    except Exception as exc:
        common.stop_on_quota(exc)
        fail(str(exc)[:300])

    print(f"  → 改试 GA 备选模型 {FALLBACK_LIVE_MODEL}")
    try:
        live = await check_live(s, FALLBACK_LIVE_MODEL)
        ok(f"备选模型可用（建会话 {live['setup_ms']} ms）。请把上面的错误转给后端；之后可设 ZJ_LIVE_MODEL={FALLBACK_LIVE_MODEL} 先跑")
        return {"primary_error": primary_error, "fallback_model": FALLBACK_LIVE_MODEL, **live}
    except Exception as exc:
        common.stop_on_quota(exc)
        fail(f"{FALLBACK_LIVE_MODEL}: {str(exc)[:500]}")
        raise SystemExit(1)


async def main() -> None:
    s = common.settings()
    common.banner(f"s0 检查项目 {s.project}")
    result: dict = {"project_set": True}

    print("1. 读取本机登录凭证（application-default）")
    try:
        creds = common.credentials()
        ok(f"凭证可用；配额项目已在代码里固定为 ZJ_PROJECT（{type(creds).__name__}）")
    except Exception as exc:
        fail(f"{exc}")
        print("  → 先运行：gcloud auth application-default login（只需一次，会打开浏览器）")
        raise SystemExit(1)

    print(f"2. 文本模型 {s.text_model}（{s.text_location}）")
    common.check_budget()
    try:
        client = common.genai_client(s.text_location)
        t0 = time.perf_counter()
        resp = await client.aio.models.generate_content(
            model=s.text_model,
            contents="「はい」とだけ答えてください。",
            config=types.GenerateContentConfig(
                labels=common.LABELS,
                max_output_tokens=16,
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
            ),
        )
        ms = round((time.perf_counter() - t0) * 1000)
        common.charge(common.flash_usage_cost(resp.usage_metadata), "s0 flash")
        ok(f"回复「{(resp.text or '').strip()}」，{ms} ms")
        result["flash"] = {"ok": True, "ms": ms}
    except Exception as exc:
        common.stop_on_quota(exc)
        fail(str(exc)[:500])
        print("  → 多半是 aiplatform.googleapis.com 还没开通，或计费账号没绑定。见 README 第 1〜3 步。")
        raise SystemExit(1)

    print(f"3. 语音模型 {s.live_model}（{s.live_location}）")
    common.check_budget()
    result["live"] = await live_step(s)

    print(f"4. Model Armor（{s.armor_location}，只列出模板，不创建）")
    try:
        from google.cloud import modelarmor_v1

        armor = modelarmor_v1.ModelArmorClient(
            credentials=common.credentials(),
            client_options={"api_endpoint": f"modelarmor.{s.armor_location}.rep.googleapis.com"},
        )
        names = [t.name.rsplit("/", 1)[-1] for t in armor.list_templates(parent=f"projects/{s.project}/locations/{s.armor_location}")]
        ok(f"可以调用；现有模板 {len(names)} 个" + (f"：{', '.join(names)}" if names else ""))
        result["model_armor"] = {"ok": True, "templates": names}
    except Exception as exc:
        common.stop_on_quota(exc)
        fail(str(exc)[:500])
        print("  → 多半是 modelarmor.googleapis.com 还没开通。见 README 第 3 步。")
        raise SystemExit(1)

    common.write_json(s.out_dir / "s0" / "result.json", result)
    print(f"\n全部通过。累计花费约 ${common.spent():.4f}。可以开始跑 s1。")


if __name__ == "__main__":
    common.run(main)
