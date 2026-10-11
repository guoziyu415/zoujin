"""模拟局的 AI 玩家（player.py）：能走的步骤、只看玩家看得到的、写死的玩家、Claude 玩家的回放和账本、统计，以及
运行器和 live 怎么接它。都不连数据库、不调模型（后端的替身在这里写）。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from zoujin_evals import Options, WorldIndex, run_case
from zoujin_evals.live import LIVE_SWITCH, Prices, gate
from zoujin_evals.player import (
    ClaudePlayer,
    Move,
    Names,
    Observation,
    PlayerReplays,
    ReplayMissing,
    ScriptedPlayer,
    beat_outcome,
    ends_as_question,
    legal_moves,
    load_personas,
    play,
    question_stats,
    sim_stats,
)
from zoujin_llm import BudgetStop, Reply, claude_prices

PERSONAS = load_personas()
MODEL = "test-sonnet-9-9"  # 假的模型 ID：认得出档名和版本就行
NAMES = Names(
    {"char.old-man": "老爺", "char.melos": "メロス"},
    {"place.syracuse-square": "シラクスの広場と大路", "place.execution-ground": "刑場"},
    "旅人",
    "はじめてこの市に来た。",
)


def snap(**over: Any) -> dict[str, Any]:
    s: dict[str, Any] = {
        "playthroughId": "pt_TEST",
        "lastSeq": 2,
        "status": "active",
        "clock": {"t": 1050, "tLabel": "約束の日・夕方", "deadlineT": 5460},
        "deadline": {"shown": False},
        "player": {"roleId": "role.traveler", "place": "place.syracuse-square", "spot": "plaza-southwest"},
        "places": [
            {"id": "place.syracuse-square", "enabled": True},
            {"id": "place.execution-ground", "enabled": True},
            {"id": "place.stonemason-workshop", "enabled": False},
        ],
        "characters": [
            {"id": "char.old-man", "place": "place.syracuse-square", "activity": "idle", "talkable": True},
            {"id": "char.melos", "place": "place.execution-ground", "activity": "idle", "talkable": True},
            {"id": "char.crowd", "place": "place.syracuse-square", "activity": "absent", "talkable": False},
        ],
        "interactables": [
            {"id": "obj.workshop-door", "kind": "examine", "label": "戸を叩く", "enabled": True},
            {"id": "way.castle", "kind": "go", "label": "王城", "enabled": True, "estimatedMinutes": 10},
        ],
        "actions": [
            {
                "actionId": "act_walk",
                "kind": "help",
                "target": "char.old-man",
                "label": "家まで送る",
                "estimatedMinutes": 30,
                "enabled": True,
            },
        ],
        "pending": {"actEnd": None, "confirm": None},
    }
    s.update(over)
    return s


ACT_END = {
    "options": [
        {"optionId": "exit.1.city", "label": "市に残り、メロスの帰りを待つ", "where": "刑場・三日目の夕方"},
        {
            "optionId": "exit.1.old-man",
            "label": "老爺の家に身を寄せる",
            "sub": "老爺があなたを覚えている",
            "enRoute": {
                "line": "途中で",
                "choices": [{"index": 0, "label": "急かす"}, {"index": 1, "label": "任せる"}],
            },
        },
    ],
    "freeform": {"allowed": True, "triesLeft": 2},
}


# —— 能走的步骤 ——


def test_moves_come_from_the_snapshot() -> None:
    moves = legal_moves(snap(), NAMES, None)
    steps = [m.with_text("こんにちは") for m in moves]
    assert {"to": "char.old-man", "say": "こんにちは"} in steps  # 同一地点、能说话的
    assert not any(s.get("to") == "char.melos" for s in steps)  # 不在这个地点的不能直接说
    assert {"act": {"kind": "help", "target": "char.old-man"}} in steps
    assert {"act": {"kind": "examine", "target": "obj.workshop-door"}} in steps
    assert {"act": {"kind": "go", "target": "way.castle"}} in steps
    assert {"act": {"kind": "move", "target": "place.execution-ground"}} in steps
    assert not any(s.get("act", {}).get("target") == "place.stonemason-workshop" for s in steps)  # 关着的地点
    assert {"act": {"kind": "wait"}} in steps
    assert not any("retract" in s for s in steps)
    assert {"retract": {"step": 3}} in [m.step for m in legal_moves(snap(), NAMES, 3)]
    assert all(m.label for m in moves) and "老爺に話しかける" in [m.label for m in moves]


def test_act_end_moves() -> None:
    moves = legal_moves(snap(pending={"actEnd": ACT_END}), NAMES, None)
    assert [m.step for m in moves if m.kind == "choose"] == [
        {"choose": {"exit": "exit.1.city"}},
        {"choose": {"exit": "exit.1.old-man", "enRoute": 0}},
        {"choose": {"exit": "exit.1.old-man", "enRoute": 1}},
    ]
    (prop,) = [m for m in moves if m.kind == "propose"]
    assert prop.needs_text and prop.with_text("城へ行く") == {"propose": "城へ行く"}
    assert all(m.kind in ("choose", "propose") for m in moves)  # 幕末待选时不能说话、走动
    closed = {**ACT_END, "freeform": {"allowed": False, "triesLeft": 0}}
    assert not any(m.kind == "propose" for m in legal_moves(snap(pending={"actEnd": closed}), NAMES, None))


def test_no_moves_once_the_ending_started() -> None:
    assert legal_moves(snap(status="ended"), NAMES, None) == []


def test_observation_text_has_only_what_the_player_sees() -> None:
    obs = Observation(snap(), ["［約束の日・夕方］老爺が嘆いている"], legal_moves(snap(), NAMES, None), 1)
    text = obs.text(NAMES)
    assert "約束の日・夕方" in text and "シラクスの広場と大路" in text and "老爺" in text
    assert "群衆" not in text and "char." not in text  # 不在场的不列，ID 不给
    assert "0. 老爺に話しかける" in text


# —— 一局 ——


class FakeGame:
    """玩家看得到的只有 view()、manifest() 和步骤；state()、events()、ending() 一调就错（那些只给检查）。"""

    def __init__(self, end_after: int) -> None:
        self.end_after, self.n = end_after, 0
        self.calls: list[tuple[Any, ...]] = []

    def manifest(self) -> dict[str, Any]:
        return {
            "roles": [{"roleId": "role.traveler", "name": "旅人", "summary": "はじめて"}],
            "characters": [{"id": "char.old-man", "name": "老爺"}],
            "places": [{"placeId": "place.syracuse-square", "name": "広場"}],
        }

    def view(self, after_seq: int = 0) -> dict[str, Any]:
        status = "ended" if self.n >= self.end_after else "active"
        ev: list[dict[str, Any]] = [{"seq": 2 + self.n, "tLabel": "夜", "summary": f"出来事{self.n}"}] if self.n else []
        return {"snapshot": snap(status=status, lastSeq=2 + self.n), "events": [e for e in ev if e["seq"] > after_seq]}

    def _step(self, name: str, *args: Any) -> dict[str, Any]:
        self.n += 1
        self.calls.append((name, *args))
        return {"reply": "……そうか？", "events": [{"secret": True}], "clockMinutes": 10, "status": "done"}

    def say(self, to: str, text: str) -> dict[str, Any]:
        return self._step("say", to, text)

    def act(self, kind: str, target: str | None, params: Mapping[str, Any]) -> dict[str, Any]:
        return self._step("act", kind, target)

    def retract(self, step: int) -> dict[str, Any]:
        return self._step("retract", step)

    def state(self) -> Any:
        raise AssertionError("AI 玩家不能看 state()")

    events = ending = state


def test_play_runs_until_the_ending_and_never_peeks() -> None:
    g = FakeGame(end_after=6)
    played = play(g, PERSONAS["persona.canon-follower"], ScriptedPlayer(seed=1))
    assert played.status == "ended" and played.stopped is None and len(played.steps) == 6
    assert played.playthrough_id == "pt_TEST"
    assert ("act", "help", "char.old-man") in g.calls  # 守原著的人先帮老爺
    said = [s for s in played.steps if "to" in s]
    assert said and all(s["say"] for s in said)
    assert ("player", said[0]["say"]) in played.transcript and ("char.old-man", "……そうか？") in played.transcript


def test_play_stops_at_max_steps() -> None:
    played = play(FakeGame(end_after=999), PERSONAS["persona.idle"], ScriptedPlayer(seed=1), max_steps=5)
    assert played.stopped == "max-steps" and len(played.steps) == 5 and played.status == "active"


def test_scripted_player_is_repeatable_per_seed() -> None:
    a = play(FakeGame(8), PERSONAS["persona.troublemaker"], ScriptedPlayer(seed=4)).steps
    b = play(FakeGame(8), PERSONAS["persona.troublemaker"], ScriptedPlayer(seed=4)).steps
    assert a == b


def test_scripted_player_moves_on_when_waiting_is_refused() -> None:
    obs = Observation(snap(), [], legal_moves(snap(), NAMES, None), 5, refused=True)
    p = ScriptedPlayer(seed=1, talk_budget=0)
    pick, _ = p.choose(PERSONAS["persona.troublemaker"], NAMES, obs)
    assert obs.moves[pick].step["act"]["kind"] in ("move", "go")


# —— Claude 当 AI 玩家 ——


class Transport:
    def __init__(self, *texts: str, stop: str = "end_turn") -> None:
        self.texts, self.stop = list(texts), stop
        self.sent: list[Any] = []

    def create(self, params: Any) -> Reply:
        self.sent.append(params)
        return Reply(self.texts.pop(0), self.stop, {"inputTokens": 900, "outputTokens": 60})


class Ledger:
    def __init__(self, cap: float = 1.0) -> None:
        self.cap = cap
        self.lines: list[dict[str, Any]] = []

    def before(self, estimate_usd: float) -> None:
        if estimate_usd > self.cap:
            raise BudgetStop("cap")

    def add(self, *, model: str, usage: Mapping[str, int], cost: float, kind: str = "player") -> None:
        self.lines.append({"model": model, "kind": kind, "cost": cost})


def obs() -> Observation:
    return Observation(snap(), [], legal_moves(snap(), NAMES, None), 1)


def test_claude_player_records_then_replays(tmp_path: Path) -> None:
    persona = PERSONAS["persona.king-persuader"]
    t = Transport(json.dumps({"why": "王に会いたい", "move": 0, "text": "王のことを教えてください。"}))
    ledger = Ledger()
    live = ClaudePlayer(MODEL, PlayerReplays(tmp_path), claude_prices(), ledger, t)
    assert live.choose(persona, NAMES, obs()) == (0, "王のことを教えてください。")
    params = t.sent[0]
    assert params["system"][1]["cache_control"] == {"type": "ephemeral"} and persona.goal in params["system"][1]["text"]
    assert "char." not in params["messages"][0]["content"]
    assert ledger.lines[0]["kind"] == "player" and ledger.lines[0]["model"] == "sonnet-9.9"
    rec = json.loads((tmp_path / "player.jsonl").read_text(encoding="utf-8"))
    assert rec["model"] == "sonnet-9.9" and MODEL not in json.dumps(rec)  # 回放里只写档名
    again = ClaudePlayer(MODEL, PlayerReplays(tmp_path), claude_prices())  # 只读回放：不花钱
    assert again.choose(persona, NAMES, obs()) == (0, "王のことを教えてください。")


def test_claude_player_bad_output_waits(tmp_path: Path) -> None:
    for t in (
        Transport("not json"),
        Transport(json.dumps({"why": "", "move": 99, "text": ""})),
        Transport("{}", stop="max_tokens"),
    ):
        p = ClaudePlayer(MODEL, PlayerReplays(tmp_path), claude_prices(), Ledger(), t)
        pick, text = p.choose(PERSONAS["persona.idle"], NAMES, obs())
        assert obs().moves[pick].step == {"act": {"kind": "wait"}} and text == "" and p.bad == 1
    assert not (tmp_path / "player.jsonl").exists()  # 坏的不存回放


def test_claude_player_replay_missing_and_budget(tmp_path: Path) -> None:
    with pytest.raises(ReplayMissing):
        ClaudePlayer(MODEL, PlayerReplays(tmp_path), claude_prices()).choose(PERSONAS["persona.idle"], NAMES, obs())
    p = ClaudePlayer(MODEL, PlayerReplays(tmp_path), claude_prices(), Ledger(cap=0.0), Transport("{}"))
    with pytest.raises(BudgetStop):
        p.choose(PERSONAS["persona.idle"], NAMES, obs())


# —— 统计 ——


def test_questions_and_requests() -> None:
    assert ends_as_question("……お前は誰だ？") == "question"
    assert ends_as_question("市へ行くのか。") == "question"
    assert ends_as_question("この荷を運んでくれないか。") == "request"
    assert ends_as_question("そうか。行け。") is None
    stats = question_stats(
        [
            ("player", "こんにちは？"),
            ("char.old-man", "旅の人か？"),
            ("char.old-man", "旅の人か？"),
            ("char.old-man", "家まで送ってもらえぬか。"),
            ("char.melos", "行く。"),
        ]
    )
    assert stats == {"lines": 4, "questions": 2, "requests": 1, "questionRate": 0.5, "repeatedQuestions": 1}


def test_sim_stats() -> None:
    events = [
        {"keyMoment": True, "effects": [{"op": "beat", "beat": "beat.20", "to": "happened"}]},
        {"keyMoment": True, "check": {"status": "rejected"}, "effects": []},
        {"keyMoment": False, "effects": [{"op": "beat", "beat": "beat.25", "to": "altered", "note": "v-neither"}]},
    ]
    assert beat_outcome(events, "beat.25") == "altered:v-neither" and beat_outcome(events, "beat.24") is None
    played = play(FakeGame(3), PERSONAS["persona.idle"], ScriptedPlayer(seed=1))
    st = sim_stats(played, events, {"world": {"outcome": "canon-reunion"}})
    assert st["keyMoments"] == 1 and st["beat20"] == "happened" and st["beat25"] == "altered:v-neither"
    assert st["ending"] == {"outcome": "canon-reunion", "variant": None} and st["steps"] == 3


# —— 运行器和 live ——


class GameApi:
    def __init__(self) -> None:
        self.games: list[FakeGame] = []

    def setup(self, setup: Mapping[str, Any], *, mode: str = "text") -> Any:
        assert "persona" in setup
        self.games.append(GameForChecks(4))
        return self.games[-1]


class GameForChecks(FakeGame):
    """跑完以后检查和统计可以查 events()、ending()。"""

    playing = False  # 开局时运行器查一次 events()（world_unchanged 用），AI 玩家开始玩以后不能查

    def view(self, after_seq: int = 0) -> dict[str, Any]:
        v = super().view(after_seq)
        self.playing = v["snapshot"]["status"] == "active"
        return v

    def events(self) -> list[dict[str, Any]]:
        assert not self.playing, "AI 玩家走完以前不能查"
        return []

    def ending(self) -> dict[str, Any]:
        assert not self.playing
        return {"world": {"outcome": "canon-reunion"}}


SIM_CASE: dict[str, Any] = {
    "id": "E7-101",
    "suite": "E7",
    "title": "t",
    "runs": 1,
    "setup": {"role": "role.traveler", "persona": "persona.canon-follower", "seed": 101},
    "steps": [],
    "expect": {"deterministic": [{"type": "t_monotonic"}]},
}


def test_runner_plays_simulated_cases_with_a_player(world_ix: WorldIndex) -> None:
    skipped = run_case(GameApi(), SIM_CASE, world_ix, Options(deterministic_only=True, timeout_s=0))
    assert skipped["results"][0]["skip"] == {"code": "needs-live-model"}  # 没给玩家：照旧
    opts = Options(deterministic_only=True, timeout_s=0, player=lambda case: ScriptedPlayer(case["setup"]["seed"]))
    out = run_case(GameApi(), SIM_CASE, world_ix, opts)
    (run,) = out["results"]
    assert run["playthroughId"] == "pt_TEST" and run["sim"]["status"] == "ended" and run["sim"]["steps"] == 4
    assert run["sim"]["ending"]["outcome"] == "canon-reunion"


def test_runner_stops_on_budget(world_ix: WorldIndex) -> None:
    class Broke:
        def choose(self, *a: Any) -> tuple[int, str]:
            raise BudgetStop("cap")

    with pytest.raises(BudgetStop):
        run_case(GameApi(), SIM_CASE, world_ix, Options(deterministic_only=True, timeout_s=0, player=lambda c: Broke()))


PRICES = Prices.from_json(
    {"turn": {"google": 0.03}, "judge": {"claude": 0.015}, "simulatedPlaythrough": {"claude": 0.1}}
)


def live(env: dict[str, str], **kw: Any) -> tuple[int | None, str]:
    args: dict[str, Any] = {
        "max_item_usd": 15.0,
        "caps": {"google": 30.0, "claude": 200.0},
        "confirm": True,
        "cases": [SIM_CASE],
        "prices": PRICES,
        "deterministic_only": True,
        "argv": ["--mode", "live"],
        "item": "s5",
        "player_model": "m",
        **kw,
    }
    return gate(env, **args)


def test_live_confirm_runs_when_everything_is_given() -> None:
    env = {LIVE_SWITCH: "1", "ZJ_LEDGER": "/tmp/ledger.jsonl"}
    assert live(env)[0] is None
    assert live(env, confirm=False)[0] == 0  # 不带 --confirm：只打印预计
    assert live(env, deterministic_only=False)[0] == 2  # 判分在 live 里还没接
    assert "--item" in live(env, item=None)[1] and live(env, item=None)[0] == 2
    assert "ZJ_LEDGER" in live({LIVE_SWITCH: "1"})[1]
    assert "ZJ_PLAYER_MODEL" in live(env, player_model=None)[1]
    assert live(env, player_model=None, cases=[{"id": "x", "suite": "E2", "setup": {}, "steps": []}])[0] is None


def test_move_labels_are_japanese() -> None:
    m = Move("act", "時を進める", {"act": {"kind": "wait"}})
    assert m.with_text("x") == {"act": {"kind": "wait"}}


def test_report_sums_up_simulations(world_ix: WorldIndex) -> None:
    from zoujin_evals import report

    opts = Options(deterministic_only=True, timeout_s=0, player=lambda case: ScriptedPlayer(case["setup"]["seed"]))
    helper = {**SIM_CASE, "id": "E7-107", "setup": {**SIM_CASE["setup"], "persona": "persona.melos-helper"}}
    cases = [run_case(GameApi(), c, world_ix, opts) for c in (SIM_CASE, helper)]
    rep = report.build(cases, {"mode": "fake"})
    sim = rep["simulations"]
    assert sim["all"]["runs"] == 2 and sim["all"]["ended"] == 2 and sim["all"]["outcomes"] == {"canon-reunion": 2}
    assert sim["melosHelper"]["runs"] == 1
    assert "## 模拟局" in report.markdown(rep)
    assert "simulations" not in report.build([], {"mode": "fake"})
