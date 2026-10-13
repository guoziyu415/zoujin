"""From the opening to a starting point: the starting points in eval_api's setup (api-contract section 7) that rely
only on simulation, shared by B-0 and the eval runner.

- `checkpoint`: `"<scenario ID>@<beat ID>"` = simulate until just after that beat happens;
  `"<scenario ID>@t=<minutes>"` = simulate to that time, including beats and deadline rules due at that moment, but
  not the scenario's events at exactly that moment;
- `scenario`: simulate to the end (no model calls);
- `place`: start at a different place.

Order: `place` writes one event at clock 0; the scenario's beat changes are combined into one event at clock 0; settle
to the role's startT; the scenario's events are settled up to their t first, then written; finally stop at the
starting point. When stopping at a moment that has no event, write an event that only advances the clock (contract:
the clock is advanced only by events).

Produces only events and state. Events carry seq (from 1); the other fields (eventId, playthroughId, schemaVersion,
summary, causes, keyMoment, check…) are filled in by B-0 before writing to the database. `setup.events` (eval setup) is
not here; B-0 appends them after the starting point per api-contract section 7.

オープニングから起点まで：eval_api の setup（api-contract 第 7 節）のうちシミュレーションだけに頼る起点。B-0 と
評価ランナーが共用する。

- `checkpoint`：`"<シナリオ ID>@<ビート ID>"` = そのビートが起きた直後までシミュレーションする。
  `"<シナリオ ID>@t=<分>"` = その時刻までシミュレーションする。その時点で期限に達するビートと期限ルールは含み、
  シナリオ内でちょうどその時点にあるイベントは含まない；
- `scenario`：最後までシミュレーションする（モデルは呼ばない）；
- `place`：開始地点を変える。

順序：`place` は時刻 0 にイベントを 1 件書く。シナリオのビート変更は時刻 0 に 1 件のイベントにまとめる。ロールの
startT まで settle する。シナリオのイベントは t まで先に settle してから書く。最後に起点で止める。ある時点で止まる
がその時点にイベントがない場合は、時刻を進めるだけのイベントを書く（契約：時刻はイベントによってのみ進む）。

出すのはイベントと状態だけ。イベントは seq（1 から）を持ち、その他のフィールド（eventId、playthroughId、
schemaVersion、summary、causes、keyMoment、check…）は B-0 が補ってから DB に書く。`setup.events`（評価の配置）は
ここにはなく、B-0 が起点の後に api-contract 第 7 節に従って追加する。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, NotRequired

from .incremental import Draft, SimState, apply, initial_state, settle
from .sim import OCCURRED, World, role_of

# None = simulate to the end / None = 最後までシミュレーション
type Until = tuple[Literal["beat"], str] | tuple[Literal["t"], int] | None


class Opened(Draft):
    """One event written by the opening. Those written by settle are kept as is (source = schedule); for the rest,
    beat, variant and reason are all None.

    オープニングが書いた 1 件のイベント。settle が書いたものはそのまま（source = schedule）、それ以外は beat、
    variant、reason がすべて None。
    """

    # Starting place, scenario, due beats and deadlines, clock advance only
    # 開始地点、シナリオ、期限に達したビートと期限、時刻を進めるだけ
    source: Literal["place", "scenario", "schedule", "clock"]
    # One sentence (Japanese) for B-0 to write the summary; if a scenario event has a note, it is that
    # B-0 が summary を書くための一文（日本語）。シナリオのイベントに note があればそれ
    note: NotRequired[str]


NOTES = {"place": "開始地点", "scenario": "シナリオの設定", "clock": "時刻を進める"}


def parse_checkpoint(checkpoint: str) -> tuple[str, Until]:
    """ "sc.canon@beat.05" → ("sc.canon", ("beat", "beat.05")); "sc.canon@t=1200" → ("sc.canon", ("t", 1200))."""
    sc, sep, at = checkpoint.partition("@")
    if not sep or not sc or not at:
        raise ValueError(
            "A checkpoint must be written as 'scenario ID@beat ID' or 'scenario ID@t=minutes'"
            f" / チェックポイントは「シナリオ ID@ビート ID」か「シナリオ ID@t=分」で書く: {checkpoint!r}"
        )
    if at.startswith("t="):
        return sc, ("t", int(at[2:]))
    return sc, ("beat", at)


def opening(
    world: World,
    role: str,
    scenario: Mapping[str, Any] | None = None,
    until: Until = None,
    *,
    place: str | None = None,
) -> tuple[list[Opened], SimState]:
    """Simulates in the order above and returns (events, state). scenario is one entry of scenarios.json; for the
    original story's path (sc.canon) pass None or {}.

    上記の順序でシミュレーションし、（イベント, 状態）を返す。scenario は scenarios.json の 1 件。原作どおりの経路
    （sc.canon）には None か {} を渡す。
    """
    run = _Run(world, initial_state(world, role))
    if place is not None:
        run.write("place", {"t": 0, "effects": [{"op": "set", "var": "var.player.location", "value": place}]})
    sc = scenario or {}
    if sc.get("beats"):
        effects = [{"op": "beat", "beat": b, **o} for b, o in sc["beats"].items()]
        run.write("scenario", {"t": 0, "effects": effects})
    if until is not None and until[0] == "beat" and until[1] not in run.world_beats:
        raise ValueError(f"The checkpoint's beat does not exist / チェックポイントのビートが存在しない: {until[1]}")
    stops = [role_of(world, role)["startT"], *sorted(e["t"] for e in sc.get("events", []))]
    events = iter(sorted(sc.get("events", []), key=lambda e: e["t"]))
    for i, t in enumerate(stops):
        if run.settle_until(t, until):
            return run.out, run.s
        if i > 0:
            e = next(events)
            run.write("scenario", {"t": t, "effects": e["effects"]}, e.get("note"))
    if until is None:
        run.settle_to(None)
    elif not run.settle_until(None, until):
        raise ValueError(
            f"Simulated to the end without reaching the checkpoint / 最後までシミュレーションしてもチェックポイントに"
            f"届かない: {until}"
        )
    return run.out, run.s


class _Run:
    def __init__(self, world: World, s: SimState) -> None:
        self.world = world
        self.world_beats = {b["id"] for b in world["beats"]}
        self.s = s
        self.out: list[Opened] = []

    def write(
        self, source: Literal["place", "scenario", "clock"], e: Mapping[str, Any], note: str | None = None
    ) -> None:
        """note: if the scenario event has its own note, use it; otherwise use the one in NOTES.

        note：シナリオのイベント自身に note があればそれを使い、なければ NOTES のものを使う。
        """
        loc = self.s["vars"]["var.player.location"]
        event = {"actor": "system", "type": "action", "origin": "action", "dt": 0, "place": loc, **e}
        self._apply(
            {"event": event, "beat": None, "variant": None, "reason": None, "reasonCode": None, "source": source},
            note or NOTES[source],
        )

    def _apply(self, d: Opened, note: str | None = None) -> None:
        d["event"] = {**d["event"], "seq": self.s["seq"] + 1}
        if note is not None:
            d["note"] = note
        self.s = apply(self.world, self.s, d["event"])
        self.out.append(d)

    def settle_to(self, t2: int | None, stop_after: str | None = None) -> bool:
        """Settles to t2; when stop_after names a beat, stops right after writing the event in which that beat
        happens. Returns whether it stopped.

        t2 まで精算する。stop_after にビートが与えられたら、そのビートが起きるイベントを書いた時点で止まる。止まったか
        どうかを返す。
        """
        drafts, _ = settle(self.world, self.s, t2)
        for d in drafts:
            self._apply(_opened(d))
            if stop_after is not None and d["beat"] == stop_after and _occurred(d, stop_after):
                return True
        return False

    def settle_until(self, t2: int | None, until: Until) -> bool:
        """Settles to t2, stopping at the starting point; returns whether it stopped.

        t2 まで精算し、起点に達したら止まる。止まったかどうかを返す。
        """
        if until is None:
            self.settle_to(t2)
            return False
        if until[0] == "t":
            x = until[1]
            if t2 is None or t2 >= x:
                self.settle_to(x)
                if self.s["t"] < x:
                    self.write("clock", {"t": x, "effects": []})
                return True
            self.settle_to(t2)
            return False
        return self.settle_to(t2, stop_after=until[1])


def _opened(d: Draft) -> Opened:
    return Opened(
        event=d["event"],
        beat=d["beat"],
        variant=d["variant"],
        reason=d["reason"],
        reasonCode=d["reasonCode"],
        source="schedule",
    )


def _occurred(d: Draft, beat: str) -> bool:
    return any(
        f.get("op") == "beat" and f.get("beat") == beat and f.get("to") in OCCURRED for f in d["event"]["effects"]
    )
