"""评测入口（B-0 验收第 9、10 组）：S-2 的 10 条起点、和 E-0 替身逐事件比对、没做的抛 EvalNotImplemented、回放。"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from zoujin_backend import eval_api
from zoujin_backend.config import DEFAULT_WORLD, REPO
from zoujin_backend.models import prompts
from zoujin_backend.models.text import FakeText, TextResult, record
from zoujin_backend.narrator.rules import RULES

from .conftest import OLD, PLAYER_LINE, SCHEMAS, Env

pytestmark = pytest.mark.db

Json = Any

S2_DEV = [
    json.loads(line) for line in (REPO / "evals" / "s2" / "s2_dev.jsonl").read_text(encoding="utf-8").splitlines()
]
REPLAYS = REPO / "fixtures" / "model-replays" / "b0-minimal.jsonl"
MINIMAL = {"role": "role.traveler", "checkpoint": "sc.canon@t=1080", "place": "place.syracuse-square"}


def stand_in() -> ModuleType:
    """E-0 的替身（evals/tests/conftest.py 的 SimApi：只用 W-1 推演）。B-0 的起点要和它逐事件一样。"""
    name = "e0_stand_in"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO / "evals" / "tests" / "conftest.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclass 要在 sys.modules 里找到自己的模块
    spec.loader.exec_module(module)
    return module


def shape(ev: Json) -> tuple[Any, ...]:
    return (ev["t"], ev["dt"], ev["actor"], ev["type"], ev["effects"], ev["check"]["status"])


def without_pid(state: Json) -> Json:
    return {k: v for k, v in state.items() if k != "playthroughId"}


def test_s2_dev_setups_start_and_check(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """10 条起点都能起，候选事件经 check 返回过 Schema 的 CheckResult，checker 带规则和检查提示的版本；
    `scoped` 下第 3 步没过的不跑第 4 步（R5 记 skipped），`all` 下都跑。"""
    monkeypatch.setenv("DATABASE_URL", env.url)
    monkeypatch.delenv("ZJ_MODEL", raising=False)
    version = prompts.PROMPTS["check"].version
    for item in S2_DEV:
        s = eval_api.setup(item["setup"], mode="text")
        before = s.events()
        out = s.check(item["candidate"], item["turn"])
        SCHEMAS.build("data/event.schema.json", "#/$defs/CheckResult", out["check"])
        assert [r["rule"] for r in out["rules"]] == list(RULES)
        assert {r["status"] for r in out["rules"]} <= {"pass", "fail", "skipped"}
        r5 = {r["rule"]: r["status"] for r in out["rules"]}["R5-persona"]
        stage3 = item["label"].get("stage") == "rules"
        assert r5 == ("skipped" if stage3 else "pass"), item["id"]
        assert out["check"]["checker"] == ("rules@b3.1" if stage3 else f"rules@b3.1+sonnet-5.5/{version}")
        every = s.check(item["candidate"], item["turn"], model_checks="all")
        assert (
            every["check"]["checker"].endswith(version) and every["check"]["failedRules"] == out["check"]["failedRules"]
        )
        assert s.events() == before  # check 不提交
    with pytest.raises(ValueError):
        s.check(S2_DEV[0]["candidate"], S2_DEV[0]["turn"], model_checks="none")


def test_starts_match_the_e0_stand_in_event_by_event(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", env.url)
    monkeypatch.delenv("ZJ_MODEL", raising=False)
    sim = stand_in().SimApi()
    setups = [item["setup"] for item in S2_DEV] + [
        {"role": "role.traveler", "checkpoint": "sc.canon@beat.05"},
        {"role": "role.traveler", "scenario": "sc.canon"},
    ]
    for setup in setups:
        mine = eval_api.setup(copy.deepcopy(setup), mode="text")
        theirs = sim.setup(copy.deepcopy(setup), mode="text")
        assert [shape(e) for e in mine.events()] == [shape(e) for e in theirs.events()], setup
        assert without_pid(mine.state()) == without_pid(theirs.state()), setup


def test_checkpoint_say_and_advance_follow_worldsim(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """setup(checkpoint) + say + advance，state() 和同一起点的 W-1 推演一致（say 用不出候选事件的一句）。"""
    monkeypatch.setenv("DATABASE_URL", env.url)
    monkeypatch.delenv("ZJ_MODEL", raising=False)
    setup = {"role": "role.traveler", "checkpoint": "sc.canon@beat.03", "place": "place.syracuse-square"}
    mine = eval_api.setup(setup, mode="text")
    theirs = stand_in().SimApi().setup(setup, mode="text")
    steps: list[str | int] = ["こんばんは。", 120, "この市は、ずいぶん静かですね。"]  # 字符串 = say，数 = advance
    for step in steps:
        if isinstance(step, str):
            got, want = mine.say(OLD, step), theirs.say(OLD, step)
            assert got["reply"] and got["characterTextMissing"] is False
        else:
            got, want = mine.advance(step), theirs.advance(step)
        assert got["clockMinutes"] == want["clockMinutes"]
        assert [shape(e) for e in got["events"]] == [shape(e) for e in want["events"]]
        assert without_pid(mine.state()) == without_pid(theirs.state())
        for e in got["events"]:
            SCHEMAS.event(e)
    assert [e["seq"] for e in mine.events()] == list(range(1, len(mine.events()) + 1))


def test_say_returns_rejected_candidates_with_their_effects(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", env.url)
    monkeypatch.delenv("ZJ_MODEL", raising=False)
    s = eval_api.setup(MINIMAL, mode="text")
    step = s.say(OLD, PLAYER_LINE)
    rejected = [e for e in step["events"] if e["check"]["status"] == "rejected"]
    assert len(rejected) == 1 and rejected[0]["check"]["failedRules"] == ["R2-precondition"]
    assert rejected[0]["effects"] == [{"op": "beat", "beat": "beat.03", "to": "happened"}]  # 候选原本的
    (logged,) = [e for e in s.events() if e["eventId"] == rejected[0]["eventId"]]
    assert logged["effects"] == []  # 日志里那条是空的（契约第 3 节）
    assert step["clockMinutes"] == 10 and step["traceId"].startswith("turn_")


def test_setup_reads_zj_world_on_every_call(env: Env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """E-0 的运行器在 setup() 之前设 ZJ_WORLD（--slice 时是切片版）；没设就用草稿，不按目录排序挑。"""
    monkeypatch.setenv("DATABASE_URL", env.url)
    monkeypatch.delenv("ZJ_MODEL", raising=False)
    w = json.loads(DEFAULT_WORLD.read_text(encoding="utf-8"))
    draft = w["worldModelVersion"]
    w["worldModelVersion"] = "hashire-merosu@9.9.9-test"
    other = tmp_path / "9.9.9-test" / "world.json"
    other.parent.mkdir(parents=True)
    other.write_text(json.dumps(w, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setenv("ZJ_WORLD", str(other))
    s = eval_api.setup(MINIMAL, mode="text")
    assert s.book.version == "hashire-merosu@9.9.9-test"
    assert all(e["t"] <= 1080 for e in s.events())
    monkeypatch.delenv("ZJ_WORLD")
    assert eval_api.setup(MINIMAL, mode="text").book.version == draft


@pytest.mark.parametrize(
    ("method", "args"),
    [("silence", (20,))],  # B-13 做了记忆和删除的那几个（test_b13）
)
def test_steps_b0_does_not_do_raise(
    env: Env, monkeypatch: pytest.MonkeyPatch, method: str, args: tuple[Any, ...]
) -> None:
    monkeypatch.setenv("DATABASE_URL", env.url)
    s = eval_api.setup(MINIMAL, mode="text")
    with pytest.raises(eval_api.EvalNotImplemented) as e:
        getattr(s, method)(*args)
    assert e.value.args == (method,)


def test_ending_is_none_before_the_story_ends(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", env.url)
    assert eval_api.setup(MINIMAL, mode="text").ending() is None  # B-9：还没进结局（走到结局的在 test_b9）


def test_scenario_run_to_the_close_enters_the_ending_at_setup(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """情景模式一口气推到收幕（E5 的 outcome 检查）：玩家没跟着换幕，起点就进结局，结局任务在 setup 里跑完。"""
    monkeypatch.setenv("DATABASE_URL", env.url)
    s = eval_api.setup({"role": "role.traveler", "scenario": "sc.river-delay"}, mode="text")
    got = s.ending()
    assert got is not None and got["world"]["outcome"] == "too-late" and got["world"]["signature"]


def test_checkpoint_past_beat_24_does_not_enter_the_ending(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """检查点停在 beat.24 以后、玩家还没换幕：beat.27 没结果，不进结局，照旧可以对话（数据评审 #124）。"""
    monkeypatch.setenv("DATABASE_URL", env.url)
    assert eval_api.setup({"role": "role.traveler", "checkpoint": "sc.canon@beat.26"}, mode="text").ending() is None


def test_replay_fixture_is_the_fake_model_recorded(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """b0-minimal.jsonl = 最小剧本那一轮的各次调用，输出取假模型的。提示、请求或假模型的输出改了，这条不过；重写：
    ZJ_UPDATE_REPLAYS=1 DATABASE_URL=… uv run pytest services/backend/tests/test_eval_api.py -k fixture
    """
    monkeypatch.setenv("DATABASE_URL", env.url)
    monkeypatch.delenv("ZJ_MODEL", raising=False)
    calls: list[Json] = []

    class Recorder(FakeText):
        async def call(self, kind: str, request: Json) -> TextResult:
            r = await super().call(kind, request)
            calls.append(record(kind, request, r.output, recorded_at="2026-10-10T00:00:00.000Z"))
            return r

    s = eval_api.setup(MINIMAL, mode="text")
    s.text = Recorder(env.settings.fake_text)
    s.say(OLD, PLAYER_LINE)
    text = "".join(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n" for c in calls)
    if os.environ.get("ZJ_UPDATE_REPLAYS") == "1":
        REPLAYS.write_text(text, encoding="utf-8")
    # 被否决的那个：改写两次（假模型原样改回）、降级一次（做不到）
    assert [c["kind"] for c in calls] == [
        "safety",
        "reply",
        "triage",
        "extract",
        "check",
        "rewrite",
        "rewrite",
        "rewrite",
    ]
    assert REPLAYS.read_text(encoding="utf-8") == text, "回放过期：ZJ_UPDATE_REPLAYS=1 重跑这条测试"


def test_replay_mode(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """ZJ_MODEL=replay：fixture 里有的请求原样返回；改了请求或提示版本，抛「回放缺失或过期」。"""
    monkeypatch.setenv("DATABASE_URL", env.url)
    monkeypatch.setenv("ZJ_MODEL", "replay")
    records = [json.loads(line) for line in REPLAYS.read_text(encoding="utf-8").splitlines()]
    recorded = {r["kind"]: r for r in records}

    s = eval_api.setup(MINIMAL, mode="text")
    step = s.say(OLD, PLAYER_LINE)
    assert step["reply"] == recorded["reply"]["response"]["text"]
    summaries = [e["summary"] for e in step["events"]]
    assert [c["summary"] for c in recorded["extract"]["response"]["candidates"]] == summaries[:2]

    with pytest.raises(eval_api.ReplayMissing):
        eval_api.setup(MINIMAL, mode="text").say(OLD, "知らない一言。")  # 请求变了
    assert eval_api.ReplayMissing.__name__ == "ReplayMissing"

    changed = prompts.Prompt("reply", prompts.PROMPTS["reply"].text + "\n")
    monkeypatch.setitem(prompts.PROMPTS, "reply", changed)
    with pytest.raises(eval_api.ReplayMissing):
        eval_api.setup(MINIMAL, mode="text").say(OLD, PLAYER_LINE)  # 提示版本变了
