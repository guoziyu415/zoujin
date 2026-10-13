"""B-6 pre-recorded line generation: the list, automatic checks, running, output, mock (card "acceptance check").
Offline: fake Live, fake transcript backfill, fake encoder.

B-6 事前収録セリフの生成：リスト、自動検査、実行方法、出力、mock（カードの「受け入れ確認」）。ネットワークなし：
偽 Live、偽の文字起こしの補完、偽エンコーダー。
"""

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
    # Closing the act (S-087): keys count from 1, narration (地の文) included
    # 幕を閉じる場面（S-087）：キーは 1 から数え、地の文も数に入る
    *(f"{pc}/{n}" for pc in ("piece.crowd-makes-way", "piece.crowd-makes-way-you") for n in (4, 5, 7)),
    *(f"{pc}/{n}" for pc in ("piece.storm-in", "piece.storm-in-you") for n in (4, 7)),
    "piece.embrace/2",
    "piece.embrace/4",
    "piece.embrace-melos-doubted/2",
    "piece.embrace-selinuntius-doubted/2",
    *(f"{pc}/{n}" for pc in ("piece.king-asks", "piece.king-asks-you") for n in (2, 4)),
    "piece.scarlet-cloak/2",
}
PROMISE_3 = "三日目の日没までに戻らねば、身代わりの石工セリヌンティウスが磔だ。"


def slice_plan() -> Plan:
    spec = read_spec("hashire-merosu")
    return plan(spec, world_of(spec, REPO / "worlds"))


# —— 1. The list / リスト ——


def test_slice_has_58_recordings_and_26_set_piece_keys() -> None:
    p = slice_plan()
    assert len(p.recordings) == 58  # Slice 28 + B-6b's 6 lines for five people / スライス 28 本 + B-6b の 5 人の 6 句
    by_speaker: dict[str, int] = {}
    for r in p.recordings:
        by_speaker[r.speaker.id] = by_speaker.get(r.speaker.id, 0) + 1
    assert by_speaker == {
        "char.melos": 11,
        "char.old-man": 6,
        "char.guards": 4,
        "char.crowd": 2,
        "char.selinuntius": 4 + 6,
        "char.king": 1 + 6,
        "char.sister": 6,
        "char.groom": 6,
        "char.philostratus": 6,
    }
    pieces = [r for r in p.recordings if any(k.startswith("piece.") for k in r.keys)]
    assert {k for r in pieces for k in r.keys} == PIECE_KEYS
    assert len(PIECE_KEYS) == 26
    assert len(pieces) == 15
    shared = {tuple(sorted(r.keys)) for r in pieces if len(r.keys) > 1}
    assert shared == {
        ("piece.gate-again/1", "piece.gate-taken-again/2"),
        ("piece.gate-taken/2", "piece.gate-turned-away/2"),
        ("piece.crowd-makes-way-you/4", "piece.crowd-makes-way/4", "piece.storm-in-you/4", "piece.storm-in/4"),
        ("piece.crowd-makes-way-you/5", "piece.crowd-makes-way/5"),
        ("piece.crowd-makes-way/7", "piece.storm-in/7"),
        ("piece.crowd-makes-way-you/7", "piece.storm-in-you/7"),
        ("piece.embrace-melos-doubted/2", "piece.embrace/2"),
        ("piece.king-asks-you/2", "piece.king-asks/2"),
        ("piece.king-asks-you/4", "piece.king-asks/4"),
    }
    voices = {r.speaker.id: r.speaker.voice for r in p.recordings}
    assert voices == {
        "char.melos": "Fenrir",
        "char.old-man": "Sadaltager",
        "char.guards": "Charon",
        "char.crowd": "Despina",
        "char.selinuntius": "Iapetus",
        "char.king": "Algieba",
        "char.sister": "Leda",
        "char.groom": "Sadachbia",
        "char.philostratus": "Rasalgethi",
    }
    # From the world model / 世界モデルから読む
    assert p.recording("melos-arrival_capped-1").text == "……これなら、間に合う。"


def test_lines_match_ux_design_16_2() -> None:
    # Two aizuchi had their wording changed after UX measurement (ux/reviews/prerecorded-listen.md): メロス
    # 「……なるほど。」→「そうか。」→「おう。」, 老爺「ああ、ああ。」→「ああ。」
    # 相槌 2 句は UX の計測で文言を変えた（ux/reviews/prerecorded-listen.md）：メロス「……なるほど。」→「そうか。」→
    # 「おう。」、老爺「ああ、ああ。」→「ああ。」
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


# The ux-design 16.2 table, the five characters outside the slice (M3)
# ux-design 16.2 の表、スライス以外の 5 人の人物（M3）
M3_LINES = {
    "char.king": (["ふん。", "ほう。", "うむ。"], ["聞こえぬ。", "はっきり申せ。"], "……しばし待て。"),
    "char.selinuntius": (
        ["うん。", "うむ。", "ああ。"],
        ["すまない、聞きそびれた。", "もう一度、ゆっくり話してくれ。"],
        "少し、考えさせてくれ。",
    ),
    "char.sister": (
        ["はい。", "……ええ。", "まあ。"],
        ["ごめんなさい、よく聞こえなくて……", "もう一度、お願いします。"],
        "ええと……少しだけ、待ってください。",
    ),
    "char.groom": (
        ["ああ。", "ええ。", "……ふむ。"],
        ["すみません、聞き取れませんでした。", "もう一度、言ってもらえますか。"],
        "ちょっと待ってください。考えます。",
    ),
    "char.philostratus": (
        ["はい。", "はあ。", "ええ。"],
        ["申し訳ございません、聞き取れませんでした。", "もう一度、お聞かせくださいまし。"],
        "少々、お待ちくださいまし。",
    ),
}


# Characters whose 6 lines all pass with the fake audio (anyone with an aizuchi over 0.5 seconds drops out as a
# block; UX already changed the four lines of three or more morae to two, so all seven pass)
# 偽の音声で 6 句すべて合格する人物（相槌が 0.5 秒を超える人はブロックごとリストに入らない。3 モーラ以上の 4 句は
# UX が 2 モーラに変えたので、7 人とも合格）
FAKE_CHARACTERS = {"char.melos", "char.old-man", *M3_LINES}


def draft_plan() -> Plan:
    spec = read_spec("hashire-merosu")
    spec["world"] = "1.0.0-draft"
    return plan(spec, world_of(spec, REPO / "worlds"))


def test_all_seven_characters_have_their_six_lines() -> None:
    """B-6b: the 6 lines of all seven are recorded, voices per D-025 and D-036; the five new characters can't be talked
    to in the slice, so the manifest still leaves them out (test_manifest).

    B-6b：7 人の 6 句をすべて録り、声は D-025、D-036 に従う。スライスでは 5 人の新しい人物と話せないので、manifest には
    従来どおり出さない（test_manifest）。
    """
    s = slice_plan()
    assert {k: (v["aizuchi"], v["unheard"], v["wait"][0]) for k, v in s.lines.items() if k in M3_LINES} == M3_LINES
    assert set(s.lines) == {"char.melos", "char.old-man", *M3_LINES}
    assert {sid: s.speakers[sid].voice for sid in M3_LINES} == {
        "char.king": "Algieba",
        "char.selinuntius": "Iapetus",
        "char.sister": "Leda",
        "char.groom": "Sadachbia",
        "char.philostratus": "Rasalgethi",
    }
    assert len(s.refs) == 7 * 2
    # The new characters have no free-talk loudness yet; it's set after the refs are measured. The king's −16.3 only
    # covers those two act-closing pieces
    # 新しい人物には自由会話のラウドネスがまだなく、ref を測ってから決める。王の −16.3 は幕を閉じるその 2 場面だけ
    assert all(
        r.loudness is None for r in s.recordings if r.speaker.id in M3_LINES and not r.keys[0].startswith("piece.")
    )
    assert s.recording("king-king-asks-you-2").loudness == -16.3
    assert s.recording("king-aizuchi-1").loudness is None


def test_draft_world_has_the_same_recordings_as_the_slice() -> None:
    """--world 1.0.0-draft: since W-2 the slice's set pieces are written in the full version, so there are as many
    recordings as in the slice; the same line has the same signature, so switching the world model re-reads nothing.

    --world 1.0.0-draft：W-2 以降スライスの固定演出は完全版に書かれているので、録音の数はスライスと同じ。同じ句は署名も
    同じなので、世界モデルを切り替えても読み直さない。
    """
    s, d = slice_plan(), draft_plan()
    assert {r.id for r in d.recordings} == {r.id for r in s.recordings}
    old = {r.id: cli.sig(r.speaker.voice, r.system, r.spoken) for r in s.recordings}
    assert all(old[r.id] == cli.sig(r.speaker.voice, r.system, r.spoken) for r in d.recordings)


def test_resume_of_a_run_made_before_b6b_reads_only_the_five(tmp_path: Path) -> None:
    """--resume of the directory from the slice run on the Mac: only the five new characters' 6 lines (6 takes for
    aizuchi, 3 for the rest) and the refs are read; the slice's 28 are not re-read.

    Mac でのスライスの実行ディレクトリを --resume：5 人の新しい人物の 6 句（相槌は 6 テイク、ほかは 3 テイク）と ref
    だけを読み、スライスの 28 本は読み直さない。
    """
    repo = fake_repo(tmp_path)
    src = repo / "services" / "backend" / "voice" / "hashire-merosu.json"
    spec = json.loads(src.read_text(encoding="utf-8"))
    for sid in M3_LINES:  # The source file before B-6b / B-6b より前の元ファイル
        for k in ("lines", "scenes", "ref", "breathyOk"):
            spec["speakers"][sid].pop(k, None)
    src.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    first = FakeReader()
    deps = cli.Deps(first, FakeTranscriber(first), audio.FakeEncoder(), repo=repo)
    assert cli.main(["--out", str(tmp_path / "out")], deps, {}) == 0
    run = only_run(tmp_path)
    again = FakeReader()
    assert cli.main(["--resume", str(run)], cli.Deps(again, FakeTranscriber(again), audio.FakeEncoder()), {}) == 0
    lines = {t: n for t, n in again.reads.items() if any(t in (*a, *u, w) for a, u, w in M3_LINES.values())}
    assert sum(lines.values()) == 5 * (3 * 6 + 3 * 3)
    assert set(again.reads) - set(lines)  # The rest are refs / 残りは ref
    voices = json.loads((run / "release" / "voices.json").read_text(encoding="utf-8"))
    # The fake audio's length follows the mora count; anyone with an aizuchi over 0.5 seconds drops out as a block
    # (FAKE_CHARACTERS)
    # 偽の音声の長さはモーラ数で決まる。相槌が 0.5 秒を超える人はブロックごとリストに入らない（FAKE_CHARACTERS）
    assert set(voices["characters"]) == FAKE_CHARACTERS
    assert len(voices["setPieceVoices"]) == len(PIECE_KEYS)


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
    # After UX measured them, direction was added only to the 9 lines to re-record: both people have 「aizuchi/3」,
    # and in the speaker block it applies only to that person
    # UX の計測後、録り直す 9 句にだけ演じ方を足した：「aizuchi/3」は 2 人ともあるが、話者ブロックに書けばその人
    # だけに効く
    p = slice_plan()
    redo = ["melos-aizuchi-2", "melos-aizuchi-3", "old-man-aizuchi-1", "old-man-aizuchi-2", "old-man-aizuchi-3"]
    scene = "\n場面：相づち。聞いているしるしに、短く一度だけ。間を置かず、語尾を上げず、ささやかずに。"
    assert all(p.recording(rid).system.endswith(scene) for rid in redo)
    calm = "\n場面：落ち着いて、ふだん話すときと同じ高さと速さで。"
    assert p.recording("melos-wait-1").system.endswith(calm)
    usual = "\n場面：ふだん話すときと同じ高さと速さで。"
    assert all(p.recording(rid).system.endswith(usual) for rid in ["old-man-unheard-1", "old-man-unheard-2"])
    # With direction added, メロス unheard/2 twice read an extra 「それ」「そう」; in the third round the direction was
    # removed, per UX's default
    # メロス unheard/2 は演じ方を足すと 2 回とも「それ」「そう」を余計に読んだので、3 回目は UX の既定どおり
    # 演じ方を外した
    for rid in ["melos-aizuchi-1", "melos-unheard-1", "melos-unheard-2", "old-man-wait-1"]:
        assert "場面：" not in p.recording(rid).system
    # Lines whose direction changed have a new signature: --resume re-reads only those
    # 演じ方を変えた句は署名が変わる：--resume はそれらだけを読み直す
    spec = read_spec("hashire-merosu")
    spec["speakers"]["char.old-man"].pop("scenes")
    plain = plan(spec, world_of(spec, REPO / "worlds"))
    r = p.recording("old-man-aizuchi-2")
    assert cli.sig(r.speaker.voice, r.system, r.spoken) != cli.sig(
        r.speaker.voice, plain.recording("old-man-aizuchi-2").system, r.spoken
    )
    spec["speakers"]["char.old-man"]["scenes"] = {"aizuchi/9": "x"}
    with pytest.raises(SpecError, match="char.old-man aizuchi/9"):
        plan(spec, world_of(spec, REPO / "worlds"))


def test_sessions_never_mix_scenes(tmp_path: Path) -> None:
    reader = FakeReader()
    code = run_fake(tmp_path, reader)
    assert code == 0
    systems = [s for _, s in reader.sessions if "旅の者と話しています" not in s]
    groups = {r.group for r in slice_plan().recordings}
    # One session per group per take: different scenes never share a session; takes 4–6 are aizuchi only (aizuchi
    # are read 6 times)
    # テイクごと・グループごとに 1 セッション：場面が違うものは同じセッションに入れない。4〜6 テイク目は相槌だけ
    # （相槌は 6 回読む）
    aizuchi_groups = {r.group for r in slice_plan().recordings if r.aizuchi}
    assert len(systems) == 3 * len(groups) + 3 * len(aizuchi_groups)
    assert set(systems) == {g[1] for g in groups}


def test_refs_go_to_release_ref_not_into_voices(tmp_path: Path) -> None:
    reader = FakeReader()
    assert run_fake(tmp_path, reader) == 0
    rel = only_run(tmp_path) / "release"
    assert sorted(p.name for p in (rel / "ref").iterdir()) == sorted(
        f"{c.removeprefix('char.')}-ref-{i}.wav" for c in ("char.melos", "char.old-man", *M3_LINES) for i in (1, 2)
    )
    voices = (rel / "voices.json").read_text(encoding="utf-8")
    assert "ref" not in voices
    talk = [s for _, s in reader.sessions if "旅の者と話しています" in s]
    # One session per character, the character layer, no scene / 人物ごとに 1 セッション、人物の層だけで場面なし
    assert len(talk) == 7 and all("場面：" not in s for s in talk)
    audit = (rel / "audit.md").read_text(encoding="utf-8")
    assert "こんにちは。あなたはどんな方ですか。" in audit


# —— 2. Automatic checks / 自動検査 ——


def shape(speech: float, *, tail: bool = False) -> audio.Shape:
    return audio.Shape(seconds=speech + 0.6, voiced_start=0.3, voiced_end=0.3 + speech, tail_voiced=tail, peak_dbfs=-6)


def test_one_too_long_one_truncated_picks_the_third() -> None:
    text = "すまない、風の音で聞こえなかった。"
    v = checks.judge(
        text, {1: (shape(5.0), text), 2: (shape(2.2, tail=True), text), 3: (shape(2.3), text)}, aizuchi=False
    )
    assert v.chosen == 3
    assert any("truncated" in p for p in v.takes[1].problems)
    assert any("Longer than" in p for p in v.takes[0].problems)


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
    assert "read twice" in v.takes[0].problems[0]
    assert "CER" in v.takes[1].problems[0]


def test_transcript_in_kana_for_a_replaced_reading_is_not_a_misread() -> None:
    heard = "三日目の日没までに戻らねば、みがわりの石工セリヌンティウスがはりつけだ。"
    spoken = "三日目の日没までに戻らねば、みがわりのいしくセリヌンティウスがはりつけだ。"
    v = checks.judge(PROMISE_3, {1: (shape(5.5), heard)}, aizuchi=False, spoken=spoken)
    assert v.chosen == 1


@pytest.mark.parametrize(
    ("text", "heard"), [("ああ。", "あー"), ("へえ。", "へー"), ("ああ、ああ。", "あーあー"), ("へえ。", "ヘー")]
)
def test_long_vowel_mark_is_not_a_misread(text: str, heard: str) -> None:
    # 「ー」 is replaced by the preceding kana's vowel before comparing (UX #82)
    # 「ー」を前の仮名の母音に置き換えてから比べる（UX #82）
    assert checks.cer(text, heard) == 0.0


def test_aizuchi_failing_only_on_cer_is_kept_and_flagged() -> None:
    v = checks.judge("うむ。", {1: (shape(0.3), "うん"), 2: (shape(0.3), "うん")}, aizuchi=True)
    assert v.chosen == 1
    assert v.flags and "うん" in v.flags[0] and "kept" in v.flags[0]
    v = checks.judge("うむ。", {1: (shape(0.3), "うん"), 2: (shape(0.31), "うむ")}, aizuchi=True)
    # A take whose transcript matches is chosen when there is one / 文字起こしが合うテイクがあればそれを選ぶ
    assert v.chosen == 2 and not v.flags
    not_aizuchi = checks.judge("もう一度、頼む。", {1: (shape(1.0), "もう一度、たのしむ。。")}, aizuchi=False)
    assert not_aizuchi.chosen is None  # Non-aizuchi are still rejected / 相槌でないものは従来どおり捨てる


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
    # UX measurement: aizuchi voiced over 0.5 seconds are re-recorded, no longer just flagged
    # UX 計測：有声が 0.5 秒を超える相槌は録り直す。印を付けるだけにはしない
    v = checks.judge("へえ。", {1: (ai_shape(0.74), "へえ"), 2: (ai_shape(0.4), "へえ")}, aizuchi=True)
    assert v.chosen == 2 and not v.flags
    assert any("over 0.5s" in p for p in v.takes[0].problems)
    # The voiced span uses the UX method (span); when not measured, speech is used
    # 有声範囲は UX の測り方（span）を使う。測っていなければ speech を使う
    assert checks.judge("へえ。", {1: (shape(0.62), "へえ")}, aizuchi=True).chosen is None
    # All three over: no loosening, the line stays out of the manifest
    # 3 テイクとも超える：基準は緩めず、この句はリストに入れない
    v = checks.judge("ああ。", {n: (ai_shape(0.6 + n / 100), "ああ") for n in (1, 2, 3)}, aizuchi=True)
    assert v.chosen is None


def test_aizuchi_file_over_0_6_s_is_rejected() -> None:
    # Voiced is 0.45 seconds by the UX method, but 0.52 seconds by the −45 dBFS measure (used for trimming): trimmed
    # plus 0.1 seconds in total at both ends is over 0.6 seconds
    # UX の測り方では有声 0.45 秒だが、−45 dBFS で測った有声（頭尾のトリムに使う）は 0.52 秒：トリム後に両端合計
    # 0.1 秒を足すと 0.6 秒を超える
    v = checks.judge("うむ。", {1: (ai_shape(0.45, speech=0.52), "うむ")}, aizuchi=True)
    assert v.chosen is None
    assert any("after trimming" in p and "0.6" in p for p in v.takes[0].problems)
    assert checks.judge("うむ。", {1: (ai_shape(0.4, speech=0.42), "うむ")}, aizuchi=True).chosen == 1


def test_whispered_aizuchi_is_rejected() -> None:
    # 老爺「ああ、ああ。」 is whispered and メロス「ああ。」 turns breathy (UX measured pitched windows at 0.04 / 0.07)
    # 老爺「ああ、ああ。」はささやき声、メロス「ああ。」は後半が息まじり（UX の計測でピッチのある窓 0.04 / 0.07）
    v = checks.judge("ああ。", {1: (ai_shape(0.35, pitched=0.07), "あっ"), 2: (ai_shape(0.33), "ああ")}, aizuchi=True)
    assert v.chosen == 2
    assert any("pitched" in p for p in v.takes[0].problems)


def test_breathy_ok_keeps_the_least_breathy_take_and_flags_it() -> None:
    # 花婿「ああ。」 stays breathy even when re-read (12–36%): the source file's breathyOk accepts it for this line
    # only, picking the least breathy take and flagging it for UX, without re-reading
    # 花婿「ああ。」は読み直しても息まじり（12〜36%）：元ファイルの breathyOk でこの句だけ受け入れ、いちばん息まじりで
    # ないテイクを選んで UX 向けに印を付け、読み直さない
    takes: dict[int, tuple[audio.Shape, str | None] | str] = {
        1: (ai_shape(0.3, pitched=0.12), "ああ"),
        2: (ai_shape(0.32, pitched=0.36), "ああ"),
    }
    assert checks.judge("ああ。", takes, aizuchi=True).chosen is None
    v = checks.judge("ああ。", takes, aizuchi=True, breathy_ok=True)
    assert v.chosen == 2 and "pitched" in v.flags[0]
    # A take that isn't breathy is still preferred / 息まじりでないテイクがあればやはりそれを選ぶ
    takes[3] = (ai_shape(0.33), "ああ")
    assert checks.judge("ああ。", takes, aizuchi=True, breathy_ok=True).chosen == 3
    groom = [r for r in slice_plan().recordings if r.speaker.id == "char.groom"]
    assert [r.id for r in groom if r.breathy_ok] == ["groom-aizuchi-1"]
    assert not any(r.breathy_ok for r in slice_plan().recordings if r.speaker.id != "char.groom")


def test_aizuchi_voiced_from_the_first_frame_is_flagged_and_the_other_take_preferred() -> None:
    v = checks.judge("ああ。", {1: (ai_shape(0.3, start=0.0), "ああ"), 2: (ai_shape(0.4), "ああ")}, aizuchi=True)
    assert v.chosen == 2 and not v.flags
    v = checks.judge("ああ。", {1: (ai_shape(0.3, start=0.0), "ああ")}, aizuchi=True)
    assert v.chosen == 1 and v.flags and "voiced from the very start" in v.flags[0]


def test_slow_aizuchi_over_mora_upper_is_rejected_again() -> None:
    # 1825ca1 made aizuchi over the mora upper bound flagged rather than rejected; after UX measured, they are
    # rejected again (there is also the 0.5-second rule)
    # 1825ca1 でモーラ数の上限を超えた相槌は捨てずに印だけ付けるようにしたが、UX の計測後に捨てるよう戻した（別に
    # 0.5 秒の条件もある）
    v = checks.judge("ああ。", {1: (ai_shape(0.45, speech=0.85), "ああ")}, aizuchi=True)
    assert v.chosen is None
    assert any("upper bound" in p for p in v.takes[0].problems)
    # Reading twice is still rejected: one take is more than twice the other two
    # 二度読みは従来どおり捨てる：1 テイクがほかの 2 テイクの 2 倍以上
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
    # UX measurement: メロス「待ってくれ」 is 5.9 semitones above free talk. The take within range is preferred, even if
    # a little further from the median length
    # UX 計測：メロス「待ってくれ」は自由会話より 5.9 半音高い。範囲内のテイクを優先する（長さの中央値から少し遠くても）
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
    assert "+0.9 semitones" in (v.takes[1].talk or "")
    # None within range: pick the closest take and flag it, don't reject
    # どれも範囲外：最も近いテイクを選んで印を付け、捨てない
    v = checks.judge(
        text,
        {1: (talk_shape(2.3, 250, moras / 8.3), text), 2: (talk_shape(2.4, 214, moras / 8.3), text)},
        aizuchi=False,
        talk=talk,
    )
    assert v.chosen == 2
    assert v.flags and "no passing take is within range" in v.flags[0] and "+5.9 semitones" in v.flags[0]
    # A speech rate 28% slow is also out of range (老爺「耳が遠うてな」)
    # 話速が 28% 遅いのも範囲外（老爺「耳が遠うてな」）
    old = checks.judge(
        "……すまぬ、耳が遠うてな。",
        {1: (talk_shape(3.2, 114, 2.8), "すまぬ、耳が遠うてな")},
        aizuchi=False,
        talk=(114.0, 6.0),
    )
    assert old.chosen == 1 and old.flags and "speech rate" in old.flags[0]


def test_only_unheard_and_wait_are_compared_with_free_talk() -> None:
    p = slice_plan()
    assert p.recording("melos-wait-1").talk == (152.0, 8.5)
    assert p.recording("old-man-unheard-1").talk == (114.0, 6.0)
    for rid in ["melos-aizuchi-1", "melos-arrival_capped-1", "guards-gate-promise-3"]:
        assert p.recording(rid).talk is None


def test_heard_as_accepts_a_known_transcript_spelling_for_that_line_only() -> None:
    # 老爺「ちと」 is always transcribed as 「ちょっと」 (CER 22%): the source file's heardAs applies to this line only,
    # without loosening the 20%
    # 老爺の「ちと」は文字起こしでいつも「ちょっと」になる（文字誤り率 22%）：元ファイルの heardAs はこの句だけに効き、
    # 20% は緩めない
    text = "ちと、待ってくだされ。"
    r = slice_plan().recording("old-man-wait-1")
    assert r.heard_as == ("ちょっと、待ってくだされ。",)
    heard = "ちょっと 待っ て くださ れ 。"
    assert checks.judge(text, {1: (shape(1.8), heard)}, aizuchi=False).chosen is None
    v = checks.judge(text, {1: (shape(1.8), heard)}, aizuchi=False, heard_as=r.heard_as)
    assert v.chosen == 1 and v.takes[0].heard_as
    # A take passing only thanks to heardAs is flagged in audit.md (UX)
    # heardAs でしか合格しないテイクは audit.md で印を付ける（UX）
    assert [f for f in v.flags if "heardAs" in f]
    ok = checks.judge(text, {1: (shape(1.8), "ちと、待って くだされ。")}, aizuchi=False, heard_as=r.heard_as)
    assert ok.chosen == 1 and not ok.takes[0].heard_as and not ok.flags
    assert slice_plan().recording("old-man-unheard-1").heard_as == ()
    spec = read_spec("hashire-merosu")
    spec["heardAs"] = {"ないせりふ。": ["x"]}
    with pytest.raises(SpecError, match="heardAs"):
        plan(spec, world_of(spec, REPO / "worlds"))


def test_loudness_offset_lowers_one_line_only() -> None:
    # A line the source work describes as quiet (S-087 メロス「嗄れた声が幽かに」): the target loudness is 6 dB lower by
    # key, and four keys share one recording
    # 原作に声が小さいと書かれたセリフ（S-087 メロス「嗄れた声が幽かに」）：キーごとに目標ラウドネスをさらに 6 dB
    # 下げる。4 つのキーで 1 本の録音を共有する
    p = slice_plan()
    assert p.recording("melos-crowd-makes-way-4").loudness == pytest.approx(-22.3)
    assert p.recording("melos-crowd-makes-way-7").loudness == pytest.approx(-16.3)
    assert p.recording("melos-unheard-1").loudness == pytest.approx(-16.3)
    assert p.recording("crowd-crowd-makes-way-5").loudness is None  # 群衆: no adjustment / 群衆は調整しない
    spec = read_spec("hashire-merosu")
    spec["speakers"]["char.melos"]["loudnessOffset"] = {"wait/9": -6}
    with pytest.raises(SpecError, match="loudnessOffset"):
        plan(spec, world_of(spec, REPO / "worlds"))
    spec = read_spec("hashire-merosu")
    spec["speakers"]["char.crowd"]["loudnessOffset"] = {"piece.king-asks/4": -3}
    with pytest.raises(SpecError, match="without a target loudness"):
        plan(spec, world_of(spec, REPO / "worlds"))


def test_piece_loudness_levels_the_curtain() -> None:
    # In the act-closing sequence (beat.24–27) different people are brought to the same level (メロスの −16.3, UX);
    # セリヌンティウス's other lines are not adjusted
    # 幕を閉じる一連の場面（beat.24〜27）では違う人を同じレベルにそろえる（メロスの −16.3、UX）。セリヌンティウスの
    # ほかのセリフは調整しない
    p = slice_plan()
    for rid in ("selinuntius-embrace-4", "selinuntius-embrace-selinuntius-doubted-2", "selinuntius-scarlet-cloak-2"):
        assert p.recording(rid).loudness == pytest.approx(-16.3)
    assert p.recording("king-king-asks-you-2").loudness == pytest.approx(-16.3)
    assert p.recording("selinuntius-workshop-knock-1").loudness is None
    spec = read_spec("hashire-merosu")
    spec["speakers"]["char.selinuntius"]["pieceLoudness"]["piece.king-asks"] = -16.3
    with pytest.raises(SpecError, match="pieceLoudness"):
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
    assert "`guards-gate-taken-again-2`" in audit and "No take passed" in audit
    assert "truncated" in audit and "Not read" in audit


def test_character_missing_one_line_drops_the_whole_block(tmp_path: Path) -> None:
    reader = FakeReader(faults={"へえ。": ["silent"] * 6})  # Aizuchi are read 6 times / 相槌は 6 回読む
    assert run_fake(tmp_path, reader) == 0
    voices = json.loads((only_run(tmp_path) / "release" / "voices.json").read_text(encoding="utf-8"))
    assert set(voices["characters"]) == FAKE_CHARACTERS - {"char.old-man"}
    audit = (only_run(tmp_path) / "release" / "audit.md").read_text(encoding="utf-8")
    assert "市の老爺 (char.old-man): some of the 6 lines failed" in audit


def test_one_bad_take_out_of_three(tmp_path: Path) -> None:
    reader = FakeReader(faults={"待ってくれ。少し、考えさせてくれ。": ["long", "double", None]})
    assert run_fake(tmp_path, reader) == 0
    run = only_run(tmp_path)
    voices = json.loads((run / "release" / "voices.json").read_text(encoding="utf-8"))
    assert voices["characters"]["char.melos"]["wait"]["text"] == "待ってくれ。少し、考えさせてくれ。"
    audit = (run / "release" / "audit.md").read_text(encoding="utf-8")
    row = next(x for x in audit.splitlines() if x.startswith("| `melos-wait-1`"))
    assert "| 3 |" in row


# —— 3. Running / 実行方法 ——


def test_real_without_confirm_only_prints(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    env = {"ZJ_MODEL": "real", "ZJ_LEDGER": str(tmp_path / "ledger.jsonl")}
    code = cli.main(["--out", str(tmp_path / "out")], cli.Deps(encoder=audio.FakeEncoder()), env)
    assert code == 0
    out = capsys.readouterr().out
    assert "Estimated cost" in out and "Print only, no calls" in out and "--confirm not given" in out
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
    # The first session is メロス's group without a scene (aizuchi 2 and 3 have a scene and form another group)
    # 最初のセッションはメロスの場面なしのグループ（相槌 2、3 は場面があり、別のグループ）
    assert sorted(p.name for p in (run / "takes").glob("*.wav")) == ["melos-aizuchi-1.1.wav", "melos-unheard-1.1.wav"]
    again = FakeReader()
    code = cli.main(
        ["--resume", str(run)],
        cli.Deps(again, FakeTranscriber(again), audio.FakeEncoder(), Ledger(ledger_path, 50.0)),
        {},
    )
    assert code == 0
    # The 3rd is read from take 1 (aizuchi are read 6 times) / 3 本目はテイク 1 から読む（相槌は 6 回読む）
    assert again.reads["おう。"] == 6
    # メロス's 1st already has take 1 read; the king's and セリヌンティウス's aizuchi also include 「うむ。」, 6 reads
    # each
    # メロスの 1 本目はテイク 1 を読み済み。王とセリヌンティウスの相槌にも「うむ。」があり、それぞれ 6 回読む
    assert again.reads["うむ。"] == 5 + 6 + 6
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
    assert len(voices["setPieceVoices"]) == len(PIECE_KEYS)
    assert set(voices["characters"]) == FAKE_CHARACTERS


def test_only_estimate_without_confirm_leaves_the_old_takes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # On the Mac, first look at the estimate without --confirm: the old takes don't move, and the estimate counts the
    # re-reads
    # Mac ではまず --confirm なしで見積もりを見る：古いテイクは動かさず、見積もりは読み直す分で計算する
    assert run_fake(tmp_path, FakeReader()) == 0
    run = only_run(tmp_path)
    capsys.readouterr()
    env = {"ZJ_MODEL": "real", "ZJ_LEDGER": str(tmp_path / "ledger.jsonl")}
    argv = ["--resume", str(run), "--only", "melos-aizuchi-2", "old-man-aizuchi-3"]
    assert cli.main(argv, cli.Deps(encoder=audio.FakeEncoder()), env) == 0
    out = capsys.readouterr().out
    # 6 takes per aizuchi line / 相槌は 1 句 6 テイク
    assert "reads aloud 12 turns" in out and "Print only, no calls" in out
    assert not (run / "takes" / "discarded").exists()
    assert len(list((run / "takes").glob("melos-aizuchi-2.*.wav"))) == 6


def test_only_rejects_unknown_keys(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run_fake(tmp_path, FakeReader(), "--only", "piece.nope/1") == cli.EXIT_CONFIG
    assert "unrecognized" in capsys.readouterr().err


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
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1  # Not a single call / 一度も呼び出していない


# —— 4. Output / 出力 ——


def test_voices_json_passes_the_manifest_schema(tmp_path: Path) -> None:
    assert run_fake(tmp_path, FakeReader()) == 0
    voices = json.loads((only_run(tmp_path) / "release" / "voices.json").read_text(encoding="utf-8"))
    assert cli.voices_errors(SCHEMAS, voices) == []
    assert set(voices["setPieceVoices"]) == PIECE_KEYS
    melos = voices["characters"]["char.melos"]
    assert set(melos["cues"]) == {"arrival_capped"}
    assert voices["characters"]["char.old-man"]["cues"] == {}
    gate = voices["setPieceVoices"]
    # One recording serves two keys / 1 本の録音を 2 つのキーに使う
    assert gate["piece.gate-taken/2"] == gate["piece.gate-turned-away/2"]
    assert gate["piece.gate-promise/3"]["text"] == PROMISE_3  # Subtitles are the original text / 字幕は原文


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
    # メロス「ああ。」's raw take is voiced from the very start, so trimming left no 80 ms at the head (UX
    # measurement): pad enough silence
    # メロス「ああ。」の元のテイクは冒頭から有声で、トリム後に頭の 80 ミリ秒が残らなかった（UX 計測）：無音を十分に補う
    pcm = audio.to_bytes(audio_tone(0.3))
    s = audio.shape(pcm)
    assert audio.head_voiced(s)
    out = audio.shape(audio.trim(pcm, s))
    assert out.voiced_start == pytest.approx(0.08, abs=0.011)
    assert out.seconds - out.voiced_end == pytest.approx(0.08, abs=0.011)
    assert not audio.head_voiced(out)


def test_aizuchi_pads_20_ms_head_80_ms_tail_unless_the_onset_is_a_step() -> None:
    # UX: aizuchi get 20 ms at the head and 80 ms at the tail; when the first voiced frame is within 6 dB of the loudest
    # (a hard onset) it falls back to 50 ms each. Both total 0.1 seconds
    # UX：相槌は頭 20、尾 80 ミリ秒。最初の有声フレームが最も大きいものから 6 dB 以内（硬い立ち上がり）なら各 50 ミリ秒
    # に戻す。どちらも合計 0.1 秒
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
    # A 180 Hz sine with amplitude 3000: RMS = 3000/√2 → −23.8 dBFS (a little lower with the 5 ms fades at both
    # ends); the silence before and after doesn't count
    # 180 Hz、振幅 3000 の正弦波：RMS = 3000/√2 → −23.8 dBFS（両端 5 ミリ秒のフェードでさらに少し下がる）。前後の無音は
    # 数えない
    pcm = audio.to_bytes(audio_silence(0.3) + audio_tone(0.4) + audio_silence(0.3))
    lv = audio.level(pcm)
    assert lv.loudness_dbfs == pytest.approx(-23.8, abs=0.5)
    # A 40 ms window overlapping either edge also counts as voiced: a bit over 0.4 seconds, same as the UX method
    # 両端の境目にかかる 40 ミリ秒の窓も有声になる：0.4 秒より少し長い。UX の測り方と同じ
    assert lv.span == pytest.approx(0.46, abs=0.02)
    # A pause in the middle is also within the span / 途中で間があっても範囲に含める
    two = audio.to_bytes(audio_tone(0.2) + audio_silence(0.5) + audio_tone(0.2))
    assert 0.9 <= audio.level(two).span <= 0.96


def test_pitched_tells_voice_from_whisper() -> None:
    import random

    rng = random.Random(6)
    # Whisper, breathy voice: no period / ささやき声、息まじりの声：周期がない
    noise = array("h", (rng.randint(-3000, 3000) for _ in range(audio.RATE // 2)))
    assert audio.pitched(audio.to_bytes(audio_tone(0.4))) > 0.9
    assert audio.pitched(audio.to_bytes(noise)) < 0.1
    # Not measured unless asked (slow) / 不要なら測らない（遅い）
    assert audio.shape(audio.to_bytes(noise)).pitched is None


def test_release_is_brought_to_the_speakers_loudness(tmp_path: Path) -> None:
    assert run_fake(tmp_path, FakeReader()) == 0
    rel = only_run(tmp_path) / "release"
    p = slice_plan()
    for rid, target in [("melos-wait-1", -16.3), ("old-man-unheard-1", -19.4), ("guards-gate-promise-3", -16.5)]:
        assert p.recording(rid).speaker.loudness == target
        name = next(rel.glob(f"{rid}.*.wav"))
        assert audio.level(audio.read_wav(name)).loudness_dbfs == pytest.approx(target, abs=0.2)
    # Closing the act: セリヌンティウス follows メロス's level, and 「待て。…」 is another 6 dB lower
    # 幕を閉じる場面：セリヌンティウスはメロスのレベルに合わせ、「待て。…」はさらに 6 dB 下げる
    for rid, target in [("selinuntius-embrace-4", -16.3), ("melos-crowd-makes-way-4", -22.3)]:
        name = next(rel.glob(f"{rid}.*.wav"))
        assert audio.level(audio.read_wav(name)).loudness_dbfs == pytest.approx(target, abs=0.2)
    crowd = audio.read_wav(next(rel.glob("crowd-crowd-makes-way-5.*.wav")))
    # No target, no adjustment / 目標がなければ調整しない
    assert audio.level(crowd).loudness_dbfs == pytest.approx(-23.8, abs=0.5)
    audit = (rel / "audit.md").read_text(encoding="utf-8")
    row = next(x for x in audit.splitlines() if x.startswith("| `melos-wait-1`"))
    assert "→ -16.3 dBFS (-16.3)" in row and "| +7." in row and "dBTP" in row
    row = next(x for x in audit.splitlines() if x.startswith("| `crowd-crowd-makes-way-5`"))
    assert "(no adjustment / 調整なし)" in row and "+0.0 dB" in row


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
    # The audit sheet has the original text and the chosen take's transcript
    # 監査シートには原文と選んだテイクの文字起こしがある
    assert PROMISE_3 in audit


def test_voice_files_are_not_in_lfs_but_art_still_is() -> None:
    def attr(path: str) -> str:
        out = subprocess.run(
            ["git", "check-attr", "filter", path], cwd=REPO, check=True, capture_output=True, text=True
        )
        return out.stdout.strip().rsplit(": ", 1)[-1]

    assert attr("assets/voice/hashire-merosu/x.m4a") == "unspecified"
    assert attr("assets/scenes/x.glb") == "lfs"
    assert attr("assets/scenes/x.m4a") == "lfs"


NO_FFMPEG = (
    "No ffmpeg (the Mac has it; CI uses the fake encoder) / ffmpeg がない（Mac にはある。CI は偽エンコーダーを使う）"
)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason=NO_FFMPEG)
def test_ffmpeg_encoder_makes_a_24k_mono_aac() -> None:
    pcm = audio.to_bytes(audio_tone(1.2))
    enc = audio.FfmpegEncoder().encode(pcm)
    assert enc.data[4:8] == b"ftyp"
    assert 1150 <= enc.duration_ms <= 1300
    # Reproducible, so the hash is stable / 再現可能なので hash が安定する
    assert audio.FfmpegEncoder().encode(pcm).data == enc.data


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason=NO_FFMPEG)
def test_ffmpeg_encoder_hits_the_loudness_and_keeps_true_peak_under_minus_1() -> None:
    # A −0.8 dBFS peak, then +3 dB / −0.8 dBFS のピークにさらに +3 dB
    loud = audio.to_bytes(array("h", (x * 10 for x in audio_tone(1.0))))
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


# —— Shape of the real client (offline) / 本物のクライアントの形（ネットワークなし） ——


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
    # Without a breakdown it counts as audio / 内訳がなければ音声として数える
    assert live_usage({"promptTokenCount": 10, "candidatesTokenCount": 5})["outputAudioTokens"] == 5


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


def test_mock_without_voices_json_has_no_prerecorded_lines(tmp_path: Path) -> None:
    """B-7: the mock no longer has placeholder pre-recorded lines; like the production gateway it handles them as
    absent.

    B-7：mock にはもう仮の事前収録セリフはなく、本番のゲートウェイと同じく事前収録なしとして扱う。
    """
    with TestClient(create_app(Config(speed=0, strict=True, voices=tmp_path))) as c:
        c.post("/v1/auth/login", json={"inviteCode": "mock"}, headers={"Origin": str(c.base_url)})
        doc = c.get("/v1/books/hashire-merosu/manifest").json()
    assert not [x["id"] for x in doc["characters"] if "prerecorded" in x]
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


# —— Shared / 共通 ——


def run_fake(tmp_path: Path, reader: FakeReader, *extra: str, ledger: Ledger | None = None) -> int:
    deps = cli.Deps(reader, FakeTranscriber(reader), audio.FakeEncoder(), ledger)
    return cli.main(["--out", str(tmp_path / "out"), *extra], deps, {})


def only_run(tmp_path: Path) -> Path:
    runs = sorted((tmp_path / "out").iterdir())
    assert len(runs) == 1
    return runs[0]


def fake_repo(tmp_path: Path) -> Path:
    """For tests that edit the source file: copy the source file, and point the world model and Schema back to the
    repo.

    元ファイルを書き換えるテスト用：元ファイルをコピーし、世界モデルと Schema はリポジトリを指す。
    """
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
    # When re-picking with new checks on the Mac, don't make people think it switched to synthesized audio
    # Mac で新しい検査により選び直すとき、合成音声に切り替わったと思わせない
    assert "All takes already read" in out and "Fake models" not in out
    assert sorted(p.name for p in (run / "release").glob("*.wav")) == before
