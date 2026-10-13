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
    print(f"  [FAIL / 失敗] {msg}", flush=True)


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
        ok(f"session setup / セッション確立 {live['setup_ms']} ms, send to first audio / 送信から最初の音声まで "
           f"{live['first_audio_ms']} ms, reply / 返答「{live['reply_transcript']}」")
        ok(f"usage messages / 使用量メッセージ {live['usage_msgs']}; this run about / 今回の概算 ${live['cost_usd']:.4f} "
           "(audio saved to / 音声の保存先 out/s0/live_hello.wav)")
        return live
    except Exception as exc:
        common.stop_on_quota(exc)
        primary_error = str(exc)[:500]
        fail(f"{s.live_model}: {primary_error}")

    print("  → First rule out a config problem: same model, retry without the ja-JP language hint for player transcription / "
          "まず設定の問題を切り分ける：同じモデルで、プレイヤー文字起こしの ja-JP 言語ヒントを外して再試行")
    try:
        live = await check_live(s, s.live_model, transcribe_lang="")
        ok("Works without the language hint. From now on prefix every command with ZJ_TRANSCRIBE_LANG= (empty after the "
           "equals sign) and forward the error above to the backend / 言語ヒントを外すと動作します。以降は各コマンドの前に "
           "ZJ_TRANSCRIBE_LANG= （等号の後は空）を付け、上のエラーをバックエンドに伝えてください")
        return {"primary_error": primary_error, "needs": "ZJ_TRANSCRIBE_LANG=", **live}
    except Exception as exc:
        common.stop_on_quota(exc)
        fail(str(exc)[:300])

    print(f"  → Trying the GA fallback model / GA の代替モデルで再試行 {FALLBACK_LIVE_MODEL}")
    try:
        live = await check_live(s, FALLBACK_LIVE_MODEL)
        ok(f"The fallback model works (session setup {live['setup_ms']} ms). Forward the error above to the backend; "
           f"meanwhile you can set ZJ_LIVE_MODEL={FALLBACK_LIVE_MODEL} and run / 代替モデルは動作します"
           f"（セッション確立 {live['setup_ms']} ms）。上のエラーをバックエンドに伝えてください。"
           f"当面は ZJ_LIVE_MODEL={FALLBACK_LIVE_MODEL} を設定して実行できます")
        return {"primary_error": primary_error, "fallback_model": FALLBACK_LIVE_MODEL, **live}
    except Exception as exc:
        common.stop_on_quota(exc)
        fail(f"{FALLBACK_LIVE_MODEL}: {str(exc)[:500]}")
        raise SystemExit(1)


async def main() -> None:
    s = common.settings()
    common.banner(f"s0 checking project / プロジェクトを確認 {s.project}")
    result: dict = {"project_set": True}

    print("1. Read the local login credentials (application-default) / ローカルのログイン認証情報を読む")
    try:
        creds = common.credentials()
        ok(f"Credentials work; the quota project is pinned to ZJ_PROJECT in code / 認証情報は有効。"
           f"クォータプロジェクトはコード内で ZJ_PROJECT に固定済み ({type(creds).__name__})")
    except Exception as exc:
        fail(f"{exc}")
        print("  → First run: gcloud auth application-default login (once only; it opens a browser) / "
              "先に gcloud auth application-default login を実行してください（一度だけ。ブラウザが開きます）")
        raise SystemExit(1)

    print(f"2. Text model / テキストモデル {s.text_model} ({s.text_location})")
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
        ok(f"reply / 返答「{(resp.text or '').strip()}」, {ms} ms")
        result["flash"] = {"ok": True, "ms": ms}
    except Exception as exc:
        common.stop_on_quota(exc)
        fail(str(exc)[:500])
        print("  → Most likely aiplatform.googleapis.com is not enabled yet, or no billing account is linked. "
              "See README steps 1–3. / おそらく aiplatform.googleapis.com が未有効化か、請求先アカウントが未リンクです。"
              "README の手順 1〜3 を参照。")
        raise SystemExit(1)

    print(f"3. Voice model / 音声モデル {s.live_model} ({s.live_location})")
    common.check_budget()
    result["live"] = await live_step(s)

    print(f"4. Model Armor ({s.armor_location}; only lists templates, creates none / テンプレートの一覧のみ、作成はしない)")
    try:
        from google.cloud import modelarmor_v1

        armor = modelarmor_v1.ModelArmorClient(
            credentials=common.credentials(),
            client_options={"api_endpoint": f"modelarmor.{s.armor_location}.rep.googleapis.com"},
        )
        names = [t.name.rsplit("/", 1)[-1] for t in armor.list_templates(parent=f"projects/{s.project}/locations/{s.armor_location}")]
        ok(f"Callable; existing templates / 呼び出し可能。既存テンプレート: {len(names)}" + (f" ({', '.join(names)})" if names else ""))
        result["model_armor"] = {"ok": True, "templates": names}
    except Exception as exc:
        common.stop_on_quota(exc)
        fail(str(exc)[:500])
        print("  → Most likely modelarmor.googleapis.com is not enabled yet. See README step 3. / "
              "おそらく modelarmor.googleapis.com が未有効化です。README の手順 3 を参照。")
        raise SystemExit(1)

    common.write_json(s.out_dir / "s0" / "result.json", result)
    print(f"\nAll passed. Spend so far about ${common.spent():.4f}. You can start running s1. / "
          f"すべて合格。累計費用は約 ${common.spent():.4f}。s1 を実行できます。")


if __name__ == "__main__":
    common.run(main)
