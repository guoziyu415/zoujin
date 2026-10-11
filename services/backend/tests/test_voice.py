"""B-6 预录句的生成：清单、自动检查、跑法、输出、mock（卡「验收」）。不联网：假的 Live、假的补转写、假的编码器。"""

from __future__ import annotations

import json
import shutil
import subprocess
from array import array
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from zoujin_backend.config import REPO
from zoujin_backend.mock.app import create_app
from zoujin_backend.mock.core import Config
from zoujin_backend.models.ledger import Ledger
from zoujin_backend.schemas import SchemaBook
from zoujin_backend.voice import audio, checks, cli
from zoujin_backend.voice.models import FakeReader, FakeTranscriber, LiveReader, live_usage
from zoujin_backend.voice.spec import Plan, SpecError, plan, read_spec, world_of

Json = Any
SCHEMAS = SchemaBook(REPO / "packages" / "contracts" / "schemas")
PIECE_KEYS = {
    "piece.gate-taken/2",
    "piece.gate-turned-away/2",
    "piece.gate-taken-again/2",
    "piece.gate-again/1",
    "piece.gate-promise/2",
    "piece.gate-promise/3",
    "piece.workshop-knock/1",
    "piece.crowd-makes-way/1",
}
PROMISE_3 = "三日目の日没までに戻らねば、身代わりの石工セリヌンティウスが磔だ。"


def slice_plan() -> Plan:
    spec = read_spec("hashire-merosu")
    return plan(spec, world_of(spec, REPO / "worlds"))


# —— 1. 清单 ——


def test_slice_has_19_recordings_and_8_set_piece_keys() -> None:
    p = slice_plan()
    assert len(p.recordings) == 19
    by_speaker: dict[str, int] = {}
    for r in p.recordings:
        by_speaker[r.speaker.id] = by_speaker.get(r.speaker.id, 0) + 1
    assert by_speaker == {"char.melos": 7, "char.old-man": 6, "char.guards": 4, "char.crowd": 1, "char.selinuntius": 1}
    pieces = [r for r in p.recordings if any(k.startswith("piece.") for k in r.keys)]
    assert {k for r in pieces for k in r.keys} == PIECE_KEYS
    assert len(pieces) == 6
    shared = {tuple(r.keys) for r in pieces if len(r.keys) > 1}
    assert shared == {
        ("piece.gate-taken-again/2", "piece.gate-again/1"),
        ("piece.gate-taken/2", "piece.gate-turned-away/2"),
    }
    voices = {r.speaker.id: r.speaker.voice for r in p.recordings}
    assert voices == {
        "char.melos": "Fenrir",
        "char.old-man": "Sadaltager",
        "char.guards": "Charon",
        "char.crowd": "Despina",
        "char.selinuntius": "Iapetus",
    }
    assert p.recording("melos-arrival_capped-1").text == "……これなら、間に合う。"  # 从世界模型读


def test_lines_match_ux_design_16_2() -> None:
    # 相槌两句按 UX 量测改了字（ux/reviews/prerecorded-listen.md）：メロス「……なるほど。」→「そうか。」→「おう。」，
    # 老爺「ああ、ああ。」→「ああ。」
    p = slice_plan()
    assert p.lines["char.melos"] == {
        "aizuchi": ["うむ。", "ああ。", "おう。"],
        "unheard": ["すまない、風の音で聞こえなかった。", "……もう一度、頼む。"],
        "wait": ["待ってくれ。少し、考えさせてくれ。"],
    }
    assert p.lines["char.old-man"] == {
        "aizuchi": ["へえ。", "……ふむ。", "ああ。"],
        "unheard": ["……すまぬ、耳が遠うてな。", "もう一度、言うてくだされ。"],
        "wait": ["ちと、待ってくだされ。"],
    }


def test_readings_only_in_what_live_reads() -> None:
    r = slice_plan().recording("guards-gate-promise-3")
    assert r.text == PROMISE_3
    assert r.spoken == "三日目の日没までに戻らねば、みがわりのいしくセリヌンティウスがはりつけだ。"


def test_scene_line_only_where_there_is_a_scene() -> None:
    p = slice_plan()
    assert "\n場面：走りながら。" in p.recording("melos-arrival_capped-1").system
    assert "場面：" not in p.recording("melos-aizuchi-1").system
    assert "場面：" not in p.recording("guards-gate-taken-2").system
    assert p.recording("melos-aizuchi-1").system.endswith("人物：" + p.speakers["char.melos"].direction)


def test_speaker_scenes_direct_one_slot_of_one_speaker() -> None:
    # UX 量完以后，只给要重录的 9 句加演法：「aizuchi/3」两人都有，写在说话人块里只管这个人
    p = slice_plan()
    redo = ["melos-aizuchi-2", "melos-aizuchi-3", "old-man-aizuchi-1", "old-man-aizuchi-2", "old-man-aizuchi-3"]
    scene = "\n場面：相づち。聞いているしるしに、短く一度だけ。間を置かず、語尾を上げず、ささやかずに。"
    assert all(p.recording(rid).system.endswith(scene) for rid in redo)
    calm = "\n場面：落ち着いて、ふだん話すときと同じ高さと速さで。"
    assert p.recording("melos-wait-1").system.endswith(calm)
    usual = "\n場面：ふだん話すときと同じ高さと速さで。"
    assert all(p.recording(rid).system.endswith(usual) for rid in ["old-man-unheard-1", "old-man-unheard-2"])
    # メロス unheard/2 加了演法两次都多读出「それ」「そう」，第三轮照 UX 的默认去掉演法
    for rid in ["melos-aizuchi-1", "melos-unheard-1", "melos-unheard-2", "old-man-wait-1"]:
        assert "場面：" not in p.recording(rid).system
    # 改了演法的句子签名变了：--resume 只重读这几句
    spec = read_spec("hashire-merosu")
    spec["speakers"]["char.old-man"].pop("scenes")
    plain = plan(spec, world_of(spec, REPO / "worlds"))
    r = p.recording("old-man-aizuchi-2")
    assert cli.sig(r.speaker.voice, r.system, r.spoken) != cli.sig(
        r.speaker.voice, plain.recording("old-man-aizuchi-2").system, r.spoken
    )
    spec["speakers"]["char.old-man"]["scenes"] = {"aizuchi/9": "x"}
    with pytest.raises(SpecError, match="char.old-man 的 aizuchi/9"):
        plan(spec, world_of(spec, REPO / "worlds"))


def test_sessions_never_mix_scenes(tmp_path: Path) -> None:
    reader = FakeReader()
    code = run_fake(tmp_path, reader)
    assert code == 0
    systems = [s for _, s in reader.sessions if "旅の者と話しています" not in s]
    groups = {r.group for r in slice_plan().recordings}
    # 每遍每组一条会话：场面不同的不在同一条会话里；第 4〜6 遍只有相槌（相槌读 6 遍）
    aizuchi_groups = {r.group for r in slice_plan().recordings if r.aizuchi}
    assert len(systems) == 3 * len(groups) + 3 * len(aizuchi_groups)
    assert set(systems) == {g[1] for g in groups}


def test_refs_go_to_release_ref_not_into_voices(tmp_path: Path) -> None:
    reader = FakeReader()
    assert run_fake(tmp_path, reader) == 0
    rel = only_run(tmp_path) / "release"
    assert sorted(p.name for p in (rel / "ref").iterdir()) == [
        "melos-ref-1.wav",
        "melos-ref-2.wav",
        "old-man-ref-1.wav",
        "old-man-ref-2.wav",
    ]
    voices = (rel / "voices.json").read_text(encoding="utf-8")
    assert "ref" not in voices
    talk = [s for _, s in reader.sessions if "旅の者と話しています" in s]
    assert len(talk) == 2 and all("場面：" not in s for s in talk)  # 一个人物一条会话，人物那层、不带场面
    audit = (rel / "audit.md").read_text(encoding="utf-8")
    assert "こんにちは。あなたはどんな方ですか。" in audit


# —— 2. 自动检查 ——


def shape(speech: float, *, tail: bool = False) -> audio.Shape:
    return audio.Shape(seconds=speech + 0.6, voiced_start=0.3, voiced_end=0.3 + speech, tail_voiced=tail, peak_dbfs=-6)


def test_one_too_long_one_truncated_picks_the_third() -> None:
    text = "すまない、風の音で聞こえなかった。"
    v = checks.judge(
        text, {1: (shape(5.0), text), 2: (shape(2.2, tail=True), text), 3: (shape(2.3), text)}, aizuchi=False
    )
    assert v.chosen == 3
    assert any("截断" in p for p in v.takes[1].problems)
    assert any("长" in p for p in v.takes[0].problems)


def test_misread_and_double_read_are_rejected() -> None:
    text = "もう遅い。用があるなら、明日にしてくれ。"
    v = checks.judge(
        text,
        {1: (shape(2.4), "もう遅い。用があるなら、明日にしてくれ。もう遅い。用があるなら、明日にしてくれ。"),
         2: (shape(2.4), "もう良い。様があるなら、あさってにしてくれ。"),
         3: (shape(2.4), text)},
        aizuchi=False,
    )  # fmt: skip
    assert v.chosen == 3
    assert "读两遍" in v.takes[0].problems[0]
    assert "字错率" in v.takes[1].problems[0]


def test_transcript_in_kana_for_a_replaced_reading_is_not_a_misread() -> None:
    heard = "三日目の日没までに戻らねば、みがわりの石工セリヌンティウスがはりつけだ。"
    spoken = "三日目の日没までに戻らねば、みがわりのいしくセリヌンティウスがはりつけだ。"
    v = checks.judge(PROMISE_3, {1: (shape(5.5), heard)}, aizuchi=False, spoken=spoken)
    assert v.chosen == 1


@pytest.mark.parametrize(
    ("text", "heard"), [("ああ。", "あー"), ("へえ。", "へー"), ("ああ、ああ。", "あーあー"), ("へえ。", "ヘー")]
)
def test_long_vowel_mark_is_not_a_misread(text: str, heard: str) -> None:
    assert checks.cer(text, heard) == 0.0  # 「ー」换成前一个假名的元音再比（UX #82）


def test_aizuchi_failing_only_on_cer_is_kept_and_flagged() -> None:
    v = checks.judge("うむ。", {1: (shape(0.3), "うん"), 2: (shape(0.3), "うん")}, aizuchi=True)
    assert v.chosen == 1
    assert v.flags and "うん" in v.flags[0] and "不扔" in v.flags[0]
    v = checks.judge("うむ。", {1: (shape(0.3), "うん"), 2: (shape(0.31), "うむ")}, aizuchi=True)
    assert v.chosen == 2 and not v.flags  # 有补转写对得上的那遍就选它
    not_aizuchi = checks.judge("もう一度、頼む。", {1: (shape(1.0), "もう一度、たのしむ。。")}, aizuchi=False)
    assert not_aizuchi.chosen is None  # 不是相槌的照旧扔


def test_aizuchi_with_other_problems_is_still_rejected() -> None:
    v = checks.judge("うむ。", {1: (shape(0.3, tail=True), "うん")}, aizuchi=True)
    assert v.chosen is None


def ai_shape(span: float, *, pitched: float = 0.7, start: float = 0.3, speech: float | None = None) -> audio.Shape:
    sp = span if speech is None else speech
    return audio.Shape(
        seconds=sp + 0.6, voiced_start=start, voiced_end=start + sp, tail_voiced=False, peak_dbfs=-6,
        span=span, pitched=pitched,
    )  # fmt: skip


def test_aizuchi_over_half_a_second_is_rejected() -> None:
    # UX 量测：相槌有声超过 0.5 秒的重录，不再只是标出来
    v = checks.judge("へえ。", {1: (ai_shape(0.74), "へえ"), 2: (ai_shape(0.4), "へえ")}, aizuchi=True)
    assert v.chosen == 2 and not v.flags
    assert any("超过 0.5s" in p for p in v.takes[0].problems)
    # 有声范围用 UX 的量法（span）；没量的按 speech
    assert checks.judge("へえ。", {1: (shape(0.62), "へえ")}, aizuchi=True).chosen is None
    # 三遍都超：不放宽，这句不进清单
    v = checks.judge("ああ。", {n: (ai_shape(0.6 + n / 100), "ああ") for n in (1, 2, 3)}, aizuchi=True)
    assert v.chosen is None


def test_aizuchi_file_over_0_6_s_is_rejected() -> None:
    # UX 的量法有声 0.45 秒，但 −45 dBFS 算的有声（裁头尾用的）0.52 秒：裁好加两头合计 0.1 秒超过 0.6 秒
    v = checks.judge("うむ。", {1: (ai_shape(0.45, speech=0.52), "うむ")}, aizuchi=True)
    assert v.chosen is None
    assert any("裁好" in p and "0.6" in p for p in v.takes[0].problems)
    assert checks.judge("うむ。", {1: (ai_shape(0.4, speech=0.42), "うむ")}, aizuchi=True).chosen == 1


def test_whispered_aizuchi_is_rejected() -> None:
    # 老爺「ああ、ああ。」是耳语，メロス「ああ。」后面是气声（UX 量到有音高的窗 0.04 / 0.07）
    v = checks.judge("ああ。", {1: (ai_shape(0.35, pitched=0.07), "あっ"), 2: (ai_shape(0.33), "ああ")}, aizuchi=True)
    assert v.chosen == 2
    assert any("音高" in p for p in v.takes[0].problems)


def test_aizuchi_voiced_from_the_first_frame_is_flagged_and_the_other_take_preferred() -> None:
    v = checks.judge("ああ。", {1: (ai_shape(0.3, start=0.0), "ああ"), 2: (ai_shape(0.4), "ああ")}, aizuchi=True)
    assert v.chosen == 2 and not v.flags
    v = checks.judge("ああ。", {1: (ai_shape(0.3, start=0.0), "ああ")}, aizuchi=True)
    assert v.chosen == 1 and v.flags and "开头就有声" in v.flags[0]


def test_slow_aizuchi_over_mora_upper_is_rejected_again() -> None:
    # 1825ca1 让相槌超拍数上限只标不扔；UX 量完改回扔（另有 0.5 秒那条）
    v = checks.judge("ああ。", {1: (ai_shape(0.45, speech=0.85), "ああ")}, aizuchi=True)
    assert v.chosen is None
    assert any("上限" in p for p in v.takes[0].problems)
    # 读两遍照旧扔：一遍是另两遍的两倍以上
    v = checks.judge(
        "へえ。", {1: (shape(0.2), "へえ"), 2: (shape(0.22), "へえ"), 3: (shape(0.45), "へえ")}, aizuchi=True
    )
    assert not next(c for c in v.takes if c.take == 3).ok
    assert checks.judge("待ってくれ。", {1: (shape(3.5), "待ってくれ")}, aizuchi=False).chosen is None


def talk_shape(speech: float, hz: float | None, sounding: float) -> audio.Shape:
    return audio.Shape(
        seconds=speech + 0.6, voiced_start=0.3, voiced_end=0.3 + speech, tail_voiced=False, peak_dbfs=-6,
        span=speech, pitch_hz=hz, sounding=sounding, pitched=0.6,
    )  # fmt: skip


def test_unheard_and_wait_prefer_the_take_like_free_talk() -> None:
    # UX 量测：メロス「待ってくれ」比自由对话高 5.9 半音。范围里的那遍优先，哪怕离长度中位数远一点
    text = "待ってくれ。少し、考えさせてくれ。"
    talk = (152.0, 8.5)
    moras = checks.mora(text)
    v = checks.judge(
        text,
        {1: (talk_shape(2.3, 214, moras / 8.3), text), 2: (talk_shape(2.6, 160, moras / 8.0), text)},
        aizuchi=False,
        talk=talk,
    )
    assert v.chosen == 2 and not v.flags
    assert "+0.9 半音" in (v.takes[1].talk or "")
    # 都不在范围里：挑最近的一遍，标出来，不扔
    v = checks.judge(
        text,
        {1: (talk_shape(2.3, 250, moras / 8.3), text), 2: (talk_shape(2.4, 214, moras / 8.3), text)},
        aizuchi=False,
        talk=talk,
    )
    assert v.chosen == 2
    assert v.flags and "不在范围里" in v.flags[0] and "+5.9 半音" in v.flags[0]
    # 语速慢了 28% 也算不在范围里（老爺「耳が遠うてな」）
    old = checks.judge(
        "……すまぬ、耳が遠うてな。",
        {1: (talk_shape(3.2, 114, 2.8), "すまぬ、耳が遠うてな")},
        aizuchi=False,
        talk=(114.0, 6.0),
    )
    assert old.chosen == 1 and old.flags and "语速" in old.flags[0]


def test_only_unheard_and_wait_are_compared_with_free_talk() -> None:
    p = slice_plan()
    assert p.recording("melos-wait-1").talk == (152.0, 8.5)
    assert p.recording("old-man-unheard-1").talk == (114.0, 6.0)
    for rid in ["melos-aizuchi-1", "melos-arrival_capped-1", "guards-gate-promise-3"]:
        assert p.recording(rid).talk is None


def test_heard_as_accepts_a_known_transcript_spelling_for_that_line_only() -> None:
    # 老爺「ちと」补转写总写成「ちょっと」（字错率 22%）：源文件 heardAs 只对这一句，不放宽 20%
    text = "ちと、待ってくだされ。"
    r = slice_plan().recording("old-man-wait-1")
    assert r.heard_as == ("ちょっと、待ってくだされ。",)
    heard = "ちょっと 待っ て くださ れ 。"
    assert checks.judge(text, {1: (shape(1.8), heard)}, aizuchi=False).chosen is None
    assert checks.judge(text, {1: (shape(1.8), heard)}, aizuchi=False, heard_as=r.heard_as).chosen == 1
    assert slice_plan().recording("old-man-unheard-1").heard_as == ()
    spec = read_spec("hashire-merosu")
    spec["heardAs"] = {"ないせりふ。": ["x"]}
    with pytest.raises(SpecError, match="heardAs"):
        plan(spec, world_of(spec, REPO / "worlds"))


def test_loudness_offset_lowers_one_line_only() -> None:
    # 原作写明声音小的句子（S-087 メロス「嗄れた声が幽かに」）：目标响度按键再低 6 dB
    spec = read_spec("hashire-merosu")
    spec["speakers"]["char.melos"]["loudnessOffset"] = {"wait/1": -6}
    p = plan(spec, world_of(spec, REPO / "worlds"))
    assert p.recording("melos-wait-1").loudness == pytest.approx(-22.3)
    assert p.recording("melos-unheard-1").loudness == pytest.approx(-16.3)
    assert p.recording("crowd-crowd-makes-way-1").loudness is None
    spec["speakers"]["char.melos"]["loudnessOffset"] = {"wait/9": -6}
    with pytest.raises(SpecError, match="loudnessOffset"):
        plan(spec, world_of(spec, REPO / "worlds"))


def test_all_three_fail_goes_to_audit_not_voices(tmp_path: Path) -> None:
    reader = FakeReader(faults={"二度は言わぬ。下がれ。": ["truncated", "silent", "error"]})
    assert run_fake(tmp_path, reader) == 0
    rel = only_run(tmp_path) / "release"
    voices = json.loads((rel / "voices.json").read_text(encoding="utf-8"))
    assert "piece.gate-again/1" not in voices["setPieceVoices"]
    assert "piece.gate-taken-again/2" not in voices["setPieceVoices"]
    assert set(voices["setPieceVoices"]) == PIECE_KEYS - {"piece.gate-again/1", "piece.gate-taken-again/2"}
    audit = (rel / "audit.md").read_text(encoding="utf-8")
    assert "`guards-gate-taken-again-2`" in audit and "几遍都不过" in audit
    assert "截断" in audit and "没读成" in audit


def test_character_missing_one_line_drops_the_whole_block(tmp_path: Path) -> None:
    reader = FakeReader(faults={"へえ。": ["silent"] * 6})  # 相槌读 6 遍
    assert run_fake(tmp_path, reader) == 0
    voices = json.loads((only_run(tmp_path) / "release" / "voices.json").read_text(encoding="utf-8"))
    assert set(voices["characters"]) == {"char.melos"}
    audit = (only_run(tmp_path) / "release" / "audit.md").read_text(encoding="utf-8")
    assert "市の老爺（char.old-man）的 6 句有没过的" in audit


def test_one_bad_take_out_of_three(tmp_path: Path) -> None:
    reader = FakeReader(faults={"待ってくれ。少し、考えさせてくれ。": ["long", "double", None]})
    assert run_fake(tmp_path, reader) == 0
    run = only_run(tmp_path)
    voices = json.loads((run / "release" / "voices.json").read_text(encoding="utf-8"))
    assert voices["characters"]["char.melos"]["wait"]["text"] == "待ってくれ。少し、考えさせてくれ。"
    audit = (run / "release" / "audit.md").read_text(encoding="utf-8")
    row = next(x for x in audit.splitlines() if x.startswith("| `melos-wait-1`"))
    assert "| 3 |" in row


# —— 3. 跑法 ——


def test_real_without_confirm_only_prints(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    env = {"ZJ_MODEL": "real", "ZJ_LEDGER": str(tmp_path / "ledger.jsonl")}
    code = cli.main(["--out", str(tmp_path / "out")], cli.Deps(encoder=audio.FakeEncoder()), env)
    assert code == 0
    out = capsys.readouterr().out
    assert "预计花费" in out and "只打印，不调用" in out and "没带 --confirm" in out
    assert "--max-google-usd" in out and "ZJ_VERTEX_PROJECT" in out
    assert not list((tmp_path / "out").glob("*/takes"))
    assert not (tmp_path / "ledger.jsonl").exists()


def test_rate_limit_stops_and_resume_continues_from_there(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.jsonl"
    reader = FakeReader(rate_limit_at=3)
    code = run_fake(tmp_path, reader, ledger=Ledger(ledger_path, 50.0))
    assert code == cli.EXIT_STOP
    rows = [json.loads(x) for x in ledger_path.read_text(encoding="utf-8").splitlines()]
    assert [r["kind"] for r in rows] == ["prerecorded", "prerecorded-transcribe"] * 2
    assert all(r["item"].startswith("b6/hashire-merosu/") for r in rows)
    run = only_run(tmp_path)
    # 第一条会话是メロス不带场面的那组（相槌 2、3 有场面，另一组）
    assert sorted(p.name for p in (run / "takes").glob("*.wav")) == ["melos-aizuchi-1.1.wav", "melos-unheard-1.1.wav"]
    again = FakeReader()
    code = cli.main(
        ["--resume", str(run)],
        cli.Deps(again, FakeTranscriber(again), audio.FakeEncoder(), Ledger(ledger_path, 50.0)),
        {},
    )
    assert code == 0
    assert again.reads["おう。"] == 6  # 第 3 条从第 1 遍读起（相槌读 6 遍）
    assert again.reads["うむ。"] == 5  # 第 1 条已经读过第 1 遍
    assert (run / "release" / "voices.json").is_file()


def test_resume_transcribes_a_take_that_was_read_but_not_transcribed(tmp_path: Path) -> None:
    reader = FakeReader()
    assert run_fake(tmp_path, reader) == 0
    run = only_run(tmp_path)
    meta = run / "takes" / "melos-aizuchi-1.2.json"
    doc = json.loads(meta.read_text(encoding="utf-8"))
    doc.pop("transcript")
    doc["complete"] = False
    meta.write_text(json.dumps(doc), encoding="utf-8")
    t = FakeTranscriber(reader)
    calls = reader.calls
    assert cli.main(["--resume", str(run)], cli.Deps(reader, t, audio.FakeEncoder()), {}) == 0
    assert t.calls == 1 and reader.calls == calls


def test_only_rereads_the_given_keys(tmp_path: Path) -> None:
    reader = FakeReader()
    assert run_fake(tmp_path, reader) == 0
    run = only_run(tmp_path)
    again = FakeReader()
    deps = cli.Deps(again, FakeTranscriber(again), audio.FakeEncoder())
    assert cli.main(["--resume", str(run), "--only", "piece.gate-again/1", "melos-wait-1"], deps, {}) == 0
    assert again.reads == {"二度は言わぬ。下がれ。": 3, "待ってくれ。少し、考えさせてくれ。": 3}
    assert len(list((run / "takes" / "discarded").rglob("*.wav"))) == 6
    voices = json.loads((run / "release" / "voices.json").read_text(encoding="utf-8"))
    assert len(voices["setPieceVoices"]) == 8 and set(voices["characters"]) == {"char.melos", "char.old-man"}


def test_only_estimate_without_confirm_leaves_the_old_takes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Mac 上先不带 --confirm 看估价：旧的几遍不挪，估价照重读算
    assert run_fake(tmp_path, FakeReader()) == 0
    run = only_run(tmp_path)
    capsys.readouterr()
    env = {"ZJ_MODEL": "real", "ZJ_LEDGER": str(tmp_path / "ledger.jsonl")}
    argv = ["--resume", str(run), "--only", "melos-aizuchi-2", "old-man-aizuchi-3"]
    assert cli.main(argv, cli.Deps(encoder=audio.FakeEncoder()), env) == 0
    out = capsys.readouterr().out
    assert "照读 12 轮" in out and "只打印，不调用" in out  # 相槌一句 6 遍
    assert not (run / "takes" / "discarded").exists()
    assert len(list((run / "takes").glob("melos-aizuchi-2.*.wav"))) == 6


def test_only_rejects_unknown_keys(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run_fake(tmp_path, FakeReader(), "--only", "piece.nope/1") == cli.EXIT_CONFIG
    assert "认不出" in capsys.readouterr().err


def test_changed_source_rereads_only_that_line(tmp_path: Path) -> None:
    reader = FakeReader()
    assert run_fake(tmp_path, reader) == 0
    run = only_run(tmp_path)
    repo = fake_repo(tmp_path)
    src = repo / "services" / "backend" / "voice" / "hashire-merosu.json"
    spec = json.loads(src.read_text(encoding="utf-8"))
    spec["scenes"]["piece.workshop-knock/1"] = "夜更け、戸の内側から。"
    src.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    again = FakeReader()
    deps = cli.Deps(again, FakeTranscriber(again), audio.FakeEncoder(), repo=repo)
    assert cli.main(["--resume", str(run)], deps, {}) == 0
    assert again.reads == {"もう遅い。用があるなら、明日にしてくれ。": 3}


def test_run_cap_stops(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl", 50.0)
    code = run_fake(tmp_path, FakeReader(), "--max-usd", "0.01", ledger=ledger)
    assert code == cli.EXIT_STOP
    assert ledger.spent(ledger.item) <= 0.01


def test_total_cap_counts_what_the_ledger_already_has(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    path.write_text(json.dumps({"provider": "google", "kind": "s2", "costUsd": 50.0}) + "\n", encoding="utf-8")
    assert run_fake(tmp_path, FakeReader(), ledger=Ledger(path, 50.0)) == cli.EXIT_STOP
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1  # 一次都没调


# —— 4. 输出 ——


def test_voices_json_passes_the_manifest_schema(tmp_path: Path) -> None:
    assert run_fake(tmp_path, FakeReader()) == 0
    voices = json.loads((only_run(tmp_path) / "release" / "voices.json").read_text(encoding="utf-8"))
    assert cli.voices_errors(SCHEMAS, voices) == []
    assert set(voices["setPieceVoices"]) == PIECE_KEYS
    melos = voices["characters"]["char.melos"]
    assert set(melos["cues"]) == {"arrival_capped"}
    assert voices["characters"]["char.old-man"]["cues"] == {}
    gate = voices["setPieceVoices"]
    assert gate["piece.gate-taken/2"] == gate["piece.gate-turned-away/2"]  # 同一条录音给两个键
    assert gate["piece.gate-promise/3"]["text"] == PROMISE_3  # 字幕是原文


def test_file_names_carry_a_content_hash_and_the_real_duration(tmp_path: Path) -> None:
    assert run_fake(tmp_path, FakeReader()) == 0
    rel = only_run(tmp_path) / "release"
    voices = json.loads((rel / "voices.json").read_text(encoding="utf-8"))
    for clip in voices["setPieceVoices"].values():
        name = clip["url"].removeprefix("/assets/voice/hashire-merosu/")
        stem, digest, _ = name.rsplit(".", 2)
        data = (rel / name).read_bytes()
        import hashlib

        assert hashlib.sha256(data).hexdigest()[:8] == digest
        assert abs(audio.FakeEncoder().encode(audio.read_wav(rel / name)).duration_ms - clip["durationMs"]) <= 1


def test_released_audio_is_trimmed_to_80ms_each_side(tmp_path: Path) -> None:
    assert run_fake(tmp_path, FakeReader()) == 0
    rel = only_run(tmp_path) / "release"
    name = next(p for p in rel.glob("melos-wait-1.*.wav"))
    s = audio.shape(audio.read_wav(name))
    assert s.voiced_start == pytest.approx(0.08, abs=0.011)
    assert s.seconds - s.voiced_end == pytest.approx(0.08, abs=0.011)


def test_trim_pads_a_take_that_starts_and_ends_voiced() -> None:
    # メロス「ああ。」原始那遍一开头就有声，裁完头上没留出 80 毫秒（UX 量测）：补静音补够
    pcm = audio.to_bytes(audio_tone(0.3))
    s = audio.shape(pcm)
    assert audio.head_voiced(s)
    out = audio.shape(audio.trim(pcm, s))
    assert out.voiced_start == pytest.approx(0.08, abs=0.011)
    assert out.seconds - out.voiced_end == pytest.approx(0.08, abs=0.011)
    assert not audio.head_voiced(out)


def test_aizuchi_pads_20_ms_head_80_ms_tail_unless_the_onset_is_a_step() -> None:
    # UX：相槌头 20、尾 80 毫秒；第一帧有声就离最响不到 6 dB（硬起头）的退回各 50 毫秒。合计都是 0.1 秒
    n = round(0.3 * audio.RATE)
    ramp = array("h", (round(x * min(1.0, i / n)) for i, x in enumerate(audio_tone(0.3)))) + audio_tone(0.1)
    soft = audio.to_bytes(audio_silence(0.3) + ramp + audio_silence(0.3))
    s = audio.shape(soft)
    assert s.onset_db is not None and s.onset_db > audio.ONSET_STEP_DB
    assert audio.aizuchi_pads(s) == (0.02, 0.08)
    out = audio.shape(audio.trim(soft, s, audio.aizuchi_pads(s)))
    assert out.voiced_start == pytest.approx(0.02, abs=0.011)
    assert out.seconds - out.voiced_end == pytest.approx(0.08, abs=0.011)
    hard = audio.shape(audio.to_bytes(audio_silence(0.3) + audio_tone(0.3) + audio_silence(0.3)))
    assert audio.aizuchi_pads(hard) == (0.05, 0.05)
    assert audio.released_seconds(hard, audio.aizuchi_pads(hard)) == pytest.approx(0.4, abs=0.011)


def test_level_measures_like_ux() -> None:
    # 180 Hz、振幅 3000 的正弦：RMS = 3000/√2 → −23.8 dBFS（两头 5 毫秒的淡入淡出再低一点）；前后的静音不算
    pcm = audio.to_bytes(audio_silence(0.3) + audio_tone(0.4) + audio_silence(0.3))
    lv = audio.level(pcm)
    assert lv.loudness_dbfs == pytest.approx(-23.8, abs=0.5)
    assert lv.span == pytest.approx(0.46, abs=0.02)  # 40 毫秒的窗压着两头的边也算有声：比 0.4 秒多一点，UX 的量法一样
    # 中间停一下也算在范围里
    two = audio.to_bytes(audio_tone(0.2) + audio_silence(0.5) + audio_tone(0.2))
    assert 0.9 <= audio.level(two).span <= 0.96


def test_pitched_tells_voice_from_whisper() -> None:
    import random

    rng = random.Random(6)
    noise = array("h", (rng.randint(-3000, 3000) for _ in range(audio.RATE // 2)))  # 耳语、气声：没有周期
    assert audio.pitched(audio.to_bytes(audio_tone(0.4))) > 0.9
    assert audio.pitched(audio.to_bytes(noise)) < 0.1
    assert audio.shape(audio.to_bytes(noise)).pitched is None  # 不要就不量（慢）


def test_release_is_brought_to_the_speakers_loudness(tmp_path: Path) -> None:
    assert run_fake(tmp_path, FakeReader()) == 0
    rel = only_run(tmp_path) / "release"
    p = slice_plan()
    for rid, target in [("melos-wait-1", -16.3), ("old-man-unheard-1", -19.4), ("guards-gate-promise-3", -16.5)]:
        assert p.recording(rid).speaker.loudness == target
        name = next(rel.glob(f"{rid}.*.wav"))
        assert audio.level(audio.read_wav(name)).loudness_dbfs == pytest.approx(target, abs=0.2)
    crowd = audio.read_wav(next(rel.glob("crowd-crowd-makes-way-1.*.wav")))
    assert audio.level(crowd).loudness_dbfs == pytest.approx(-23.8, abs=0.5)  # 没有目标的不调
    audit = (rel / "audit.md").read_text(encoding="utf-8")
    row = next(x for x in audit.splitlines() if x.startswith("| `melos-wait-1`"))
    assert "→ -16.3 dBFS（-16.3）" in row and "| +7." in row and "dBTP" in row
    row = next(x for x in audit.splitlines() if x.startswith("| `crowd-crowd-makes-way-1`"))
    assert "（不调）" in row and "+0.0 dB" in row


def test_fake_encoder_gain_never_goes_over_minus_1() -> None:
    enc = audio.FakeEncoder().encode(audio.to_bytes(audio_tone(0.5)), 30.0)
    assert enc.true_peak_dbtp <= audio.PEAK_DBFS


def test_logs_and_ledger_have_no_line_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ledger_path = tmp_path / "ledger.jsonl"
    assert run_fake(tmp_path, FakeReader(), ledger=Ledger(ledger_path, 50.0)) == 0
    out = capsys.readouterr()
    texts = [r.text for r in slice_plan().recordings] + [r.spoken for r in slice_plan().recordings]
    logged = out.out + out.err + ledger_path.read_text(encoding="utf-8")
    for t in texts:
        assert t not in logged
    audit = (only_run(tmp_path) / "release" / "audit.md").read_text(encoding="utf-8")
    assert PROMISE_3 in audit  # 审查单带原文和选中那遍的补转写


def test_voice_files_are_not_in_lfs_but_art_still_is() -> None:
    def attr(path: str) -> str:
        out = subprocess.run(
            ["git", "check-attr", "filter", path], cwd=REPO, check=True, capture_output=True, text=True
        )
        return out.stdout.strip().rsplit(": ", 1)[-1]

    assert attr("assets/voice/hashire-merosu/x.m4a") == "unspecified"
    assert attr("assets/scenes/x.glb") == "lfs"
    assert attr("assets/scenes/x.m4a") == "lfs"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="没有 ffmpeg（Mac 上有；CI 用假的编码器）")
def test_ffmpeg_encoder_makes_a_24k_mono_aac() -> None:
    pcm = audio.to_bytes(audio_tone(1.2))
    enc = audio.FfmpegEncoder().encode(pcm)
    assert enc.data[4:8] == b"ftyp"
    assert 1150 <= enc.duration_ms <= 1300
    assert audio.FfmpegEncoder().encode(pcm).data == enc.data  # 可复现：hash 才稳定


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="没有 ffmpeg（Mac 上有；CI 用假的编码器）")
def test_ffmpeg_encoder_hits_the_loudness_and_keeps_true_peak_under_minus_1() -> None:
    loud = audio.to_bytes(array("h", (x * 10 for x in audio_tone(1.0))))  # −0.8 dBFS 的峰，再 +3 dB
    enc = audio.FfmpegEncoder().encode(loud, 3.0)
    assert enc.true_peak_dbtp <= audio.PEAK_DBFS
    quiet = audio.to_bytes(audio_tone(1.0))
    enc = audio.FfmpegEncoder().encode(quiet, 7.5)
    assert enc.loudness_dbfs == pytest.approx(audio.level(quiet).loudness_dbfs + 7.5, abs=0.3)
    assert enc.true_peak_dbtp <= audio.PEAK_DBFS


def audio_tone(seconds: float) -> Any:
    from zoujin_backend.voice.models import _tone

    return _tone(seconds)


def audio_silence(seconds: float) -> Any:
    from zoujin_backend.voice.models import _silence

    return _silence(seconds)


# —— 真客户端的形状（不联网） ——


def test_live_setup_matches_what_the_sdk_sends() -> None:
    class NoAuth:
        def token(self) -> str:
            return "t"

    r = LiveReader("proj", "us-central1", NoAuth())
    assert (
        r.url
        == "wss://us-central1-aiplatform.googleapis.com/ws/google.cloud.aiplatform.v1beta1.LlmBidiService/BidiGenerateContent"
    )
    assert r.setup("Charon", "SYS") == {
        "setup": {
            "model": "projects/proj/locations/us-central1/publishers/google/models/gemini-3.8-live",
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voice_name": "Charon"}}},
            },
            "systemInstruction": {"parts": [{"text": "SYS"}]},
            "outputAudioTranscription": {},
        }
    }


def test_live_usage_splits_text_and_audio() -> None:
    u = live_usage(
        {
            "promptTokenCount": 300,
            "candidatesTokenCount": 90,
            "promptTokensDetails": [{"modality": "TEXT", "tokenCount": 200}, {"modality": "AUDIO", "tokenCount": 100}],
            "candidatesTokensDetails": [
                {"modality": "AUDIO", "tokenCount": 75},
                {"modality": "TEXT", "tokenCount": 15},
            ],
        }
    )
    assert u["inputTextTokens"] == 200 and u["inputAudioTokens"] == 100
    assert u["outputAudioTokens"] == 75 and u["outputTextTokens"] == 15
    assert live_usage({"promptTokenCount": 10, "candidatesTokenCount": 5})["outputAudioTokens"] == 5  # 没分项按音频


# —— 5. mock ——


def write_voices(tmp_path: Path) -> Path:
    assert run_fake(tmp_path, FakeReader()) == 0
    rel = only_run(tmp_path) / "release"
    dest = tmp_path / "voice" / "hashire-merosu"
    dest.mkdir(parents=True)
    for p in rel.iterdir():
        if p.is_file() and p.name != "audit.md":
            shutil.copy(p, dest / p.name)
    return tmp_path / "voice"


def test_mock_manifest_uses_voices_json(tmp_path: Path) -> None:
    root = write_voices(tmp_path)
    voices = json.loads((root / "hashire-merosu" / "voices.json").read_text(encoding="utf-8"))
    with TestClient(create_app(Config(speed=0, strict=True, voices=root))) as c:
        c.post("/v1/auth/login", json={"inviteCode": "mock"}, headers={"Origin": str(c.base_url)})
        doc = c.get("/v1/books/hashire-merosu/manifest").json()
    assert SCHEMAS.errors("api/rest/manifest.schema.json", "#/$defs/ManifestResponse", doc) == []
    chars = {x["id"]: x for x in doc["characters"]}
    assert chars["char.melos"]["prerecorded"] == voices["characters"]["char.melos"]
    assert chars["char.old-man"]["prerecorded"] == voices["characters"]["char.old-man"]
    assert "prerecorded" not in chars["char.philostratus"]
    assert doc["setPieceVoices"] == voices["setPieceVoices"]


def test_mock_without_voices_json_keeps_the_placeholder(tmp_path: Path) -> None:
    with TestClient(create_app(Config(speed=0, strict=True, voices=tmp_path))) as c:
        c.post("/v1/auth/login", json={"inviteCode": "mock"}, headers={"Origin": str(c.base_url)})
        doc = c.get("/v1/books/hashire-merosu/manifest").json()
    assert "prerecorded" in {x["id"]: x for x in doc["characters"]}["char.philostratus"]
    assert "setPieceVoices" not in doc


def test_mock_serves_listed_voice_files_with_immutable_cache(tmp_path: Path) -> None:
    root = write_voices(tmp_path)
    voices = json.loads((root / "hashire-merosu" / "voices.json").read_text(encoding="utf-8"))
    url = voices["setPieceVoices"]["piece.gate-promise/3"]["url"]
    (root / "hashire-merosu" / "unlisted.wav").write_bytes(b"x")
    with TestClient(create_app(Config(speed=0, strict=True, voices=root))) as c:
        r = c.get(url)
        assert r.status_code == 200
        assert r.headers["cache-control"] == "public, max-age=31536000, immutable"
        assert r.content == (root / "hashire-merosu" / url.rsplit("/", 1)[-1]).read_bytes()
        assert c.get("/assets/voice/hashire-merosu/unlisted.wav").status_code == 404
        assert c.get("/assets/voice/hashire-merosu/voices.json").status_code == 404
        assert c.get("/assets/voice/other-book/x.m4a").status_code == 404


# —— 共用 ——


def run_fake(tmp_path: Path, reader: FakeReader, *extra: str, ledger: Ledger | None = None) -> int:
    deps = cli.Deps(reader, FakeTranscriber(reader), audio.FakeEncoder(), ledger)
    return cli.main(["--out", str(tmp_path / "out"), *extra], deps, {})


def only_run(tmp_path: Path) -> Path:
    runs = sorted((tmp_path / "out").iterdir())
    assert len(runs) == 1
    return runs[0]


def fake_repo(tmp_path: Path) -> Path:
    """改源文件的测试用：源文件拷一份，世界模型和 Schema 指回仓库。"""
    repo = tmp_path / "repo"
    (repo / "services" / "backend").mkdir(parents=True)
    shutil.copytree(REPO / "services" / "backend" / "voice", repo / "services" / "backend" / "voice")
    (repo / "worlds").symlink_to(REPO / "worlds")
    (repo / "packages").symlink_to(REPO / "packages")
    return repo


def test_resume_of_a_finished_run_says_it_reuses_takes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run_fake(tmp_path, FakeReader()) == 0
    run = only_run(tmp_path)
    before = sorted(p.name for p in (run / "release").glob("*.wav"))
    capsys.readouterr()
    assert cli.main(["--resume", str(run)], cli.Deps(encoder=audio.FakeEncoder()), {}) == 0
    out = capsys.readouterr().out
    assert "都读过了" in out and "假模型" not in out  # Mac 上按新检查重挑时，别让人以为换成了合成的声音
    assert sorted(p.name for p in (run / "release").glob("*.wav")) == before
