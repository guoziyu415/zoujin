"""Event-by-event simulation (initial_state / apply / settle / world_state / check_effects).

The 24 simulations computed event by event to the end give the same results as the whole-run simulation; replaying
only the event log gives the same state; a beat waiting on preconditions that later hold happens at that moment, and
the downstream beats that require it happen at the same moment; world_state() passes the C-2 Schema; check_effects()
reports what it should.

イベントごとのシミュレーション（initial_state / apply / settle / world_state / check_effects）。

24 回のシミュレーションをイベントごとに最後まで計算すると一括シミュレーションと同じ結果になる。イベントログだけを
リプレイすると同じ状態になる。前提条件を待っていたビートは後で成り立った時点で起き、それを requires する下流も
同じ時点で続いて起きる。world_state() は C-2 の Schema を通る。check_effects() は報告すべきものを報告する。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from zoujin_worldsim import (
    OCCURRED,
    Sim,
    SimState,
    apply,
    arrival_delta,
    check_effects,
    classify,
    flat,
    initial_state,
    predict,
    settle,
    signature,
    world_state,
)

REPO = Path(__file__).resolve().parents[3]
WORLD_DIR = REPO / "worlds" / "hashire-merosu" / "1.0.0-draft"
WORLD: dict[str, Any] = json.loads((WORLD_DIR / "world.json").read_text(encoding="utf-8"))
SCENARIOS: list[dict[str, Any]] = [
    {"id": "sc.canon", "note": "原著どおり（プレイヤーは何もしない）", "expect": "canon-reunion"}
] + json.loads((WORLD_DIR / "scenarios.json").read_text(encoding="utf-8"))
ROLE = "role.traveler"
SIM = Sim(WORLD)
ITEMS = {it["id"] for it in WORLD["items"]}
SCHEMAS = REPO / "packages" / "contracts" / "schemas" / "data"
REGISTRY: Registry[Any] = Registry().with_resources(
    (doc["$id"], Resource.from_contents(doc))
    for doc in (json.loads(p.read_text(encoding="utf-8")) for p in SCHEMAS.glob("*.schema.json"))
)

type Played = Callable[[str], tuple[SimState, list[dict[str, Any]]]]
type Play = Callable[..., tuple[SimState, list[dict[str, Any]]]]


def validator(ref: str) -> Draft202012Validator:
    return Draft202012Validator({"$ref": ref}, registry=REGISTRY)


def ev(t: int, *effects: dict[str, Any], origin: str = "action", **extra: Any) -> dict[str, Any]:
    return {"t": t, "dt": 0, "origin": origin, "effects": list(effects), **extra}


def at(t: int, sc: dict[str, Any] | None = None) -> SimState:
    """The traveler starts, with the scenario's beat changes, settled to t.

    旅人で開始し、シナリオのビート変更を入れて t まで精算する。
    """
    s = initial_state(WORLD, ROLE)
    if sc and sc.get("beats"):
        s = apply(WORLD, s, ev(0, *({"op": "beat", "beat": b, **o} for b, o in sc["beats"].items())))
    return settle(WORLD, s, t)[1]


# ---- Event by event = whole run / イベントごと = 一括 ----


@pytest.mark.parametrize("sc", SCENARIOS, ids=lambda sc: sc["id"])
def test_incremental_equals_one_shot(sc: dict[str, Any], played: Played) -> None:
    one = SIM.run(sc, role=ROLE)
    s, _ = played(sc["id"])
    # The reference implementation's late, blocked and those still precondition-failed at the end are all prevented
    # in the event-by-event version
    # 参照実装の late、blocked、最後まで precondition-failed のものは、イベントごとの側ではすべて prevented
    assert s["beats"] == {b: (st if st in OCCURRED else "prevented") for b, st in one["status"].items()}
    assert s["times"] == one["times"]
    assert s["variants"] == one["variant"]
    assert s["vars"] == {v["id"]: one["state"][v["id"]] for v in WORLD["stateVars"]}
    assert {k: v for k, v in s["holdings"].items() if v is not None} == {
        k: v for k, v in one["state"].items() if k in ITEMS and v is not None
    }
    assert s["locations"] == one["where"]
    assert classify(WORLD, s) == one["outcome"]
    assert s["deadline"]


@pytest.mark.parametrize("sc", SCENARIOS, ids=lambda sc: sc["id"])
def test_signature_matches_golden(sc: dict[str, Any], played: Played, golden: dict[str, Any]) -> None:
    # 2.9.1: the signature after an event-by-event simulation to the end equals the golden file's (whole-run
    # simulation), with variables and beats in the same dict
    # 2.9.1：イベントごとに最後までシミュレーションしたシグネチャはゴールデンファイル（一括シミュレーション）と同じ。
    # 変数とビートは同じ dict に入れる
    want = golden["runs"][sc["id"]]["signature"]
    assert signature(WORLD, played(sc["id"])[0]) == {**want["vars"], **want["beats"]}


@pytest.mark.parametrize("sc", SCENARIOS, ids=lambda sc: sc["id"])
def test_replay_from_the_log(sc: dict[str, Any], played: Played) -> None:
    s, log = played(sc["id"])
    r = initial_state(WORLD, ROLE)
    for e in log:
        r = apply(WORLD, r, e)
    assert r == s
    assert json.loads(json.dumps(s)) == s, "SimState can be stored as JSON / SimState は JSON として保存できる"
    ts = [e["t"] for e in log]
    assert ts == sorted(ts), "Event t never goes backwards / イベントの t は逆行しない"


@pytest.mark.parametrize("sc", SCENARIOS, ids=lambda sc: sc["id"])
def test_same_input_same_log(sc: dict[str, Any], play_scenario: Play, played: Played) -> None:
    assert play_scenario(WORLD, sc) == played(sc["id"])


def test_settle_in_small_steps_equals_one_settle() -> None:
    s0 = initial_state(WORLD, ROLE)
    whole_drafts, whole = settle(WORLD, s0, None)
    s, drafts = s0, []
    for t2 in range(0, 6000, 37):
        d, s = settle(WORLD, s, t2)
        drafts += d
    d, s = settle(WORLD, s, None)
    assert drafts + d == whole_drafts
    assert s == whole


def test_settle_does_not_change_its_input() -> None:
    s = initial_state(WORLD, ROLE)
    before = json.dumps(s, sort_keys=True)
    settle(WORLD, s, None)
    assert json.dumps(s, sort_keys=True) == before


# ---- Drafts of system events / システムイベントの下書き ----


def test_drafts_follow_the_card(played: Played) -> None:
    effect = validator("data/event.schema.json#/$defs/Effect")
    _, log = played("sc.canon")
    for e in log:
        assert e["actor"] == "system" and e["origin"] == "schedule" and e["dt"] == 0
        for x in e["effects"]:
            assert not list(effect.iter_errors(x)), x
    b01 = next(e for e in log if any(x.get("beat") == "beat.01" for x in e["effects"]))
    x = SIM.beats["beat.01"]
    assert b01["type"] == "beat" and b01["place"] == x["place"]
    assert b01["effects"] == [{"op": "relocate", "character": p, "place": x["place"]} for p in x["participants"]] + [
        {"op": "beat", "beat": "beat.01", "to": "happened"},
        *x["outcomes"],
    ]


def test_deadline_is_one_system_event_even_when_no_rule_holds(played: Played) -> None:
    dl = WORLD["clock"]["deadline"]["t"]
    _, log = played("sc.canon")
    deadline = [e for e in log if e.get("origin") == "schedule" and e["type"] == "action"]
    # In the original story Melos arrives in time, so no rule holds / 原作ではメロスが間に合うので、成り立つルールはない
    assert [(e["t"], e["effects"]) for e in deadline] == [(dl, [])]
    _, log = played("sc.river-delay")
    deadline = [e for e in log if e.get("origin") == "schedule" and e["type"] == "action"]
    assert (
        len(deadline) == 1 and {"op": "set", "var": "var.hostage.fate", "value": "executed"} in deadline[0]["effects"]
    )


def test_variant_draft() -> None:
    sc = next(sc for sc in SCENARIOS if sc.get("expectVariant"))
    bid, vid = next(iter(sc["expectVariant"].items()))
    drafts = []
    s = at(0, sc)
    for t2 in [x["t"] for x in sc.get("events", [])] + [None]:
        d, s = settle(WORLD, s, t2)
        drafts += d
        if t2 is not None:
            s = apply(WORLD, s, next(ev(x["t"], *x["effects"]) for x in sc["events"] if x["t"] == t2))
    d = next(d for d in drafts if d["beat"] == bid)
    assert d["variant"] == vid
    assert d["event"]["effects"][-1]["to"] == "altered" and d["event"]["effects"][-1]["note"] == vid
    assert s["variants"][bid] == vid


def test_late_and_timed_beats_are_prevented_with_a_reason() -> None:
    # Delayed past latest: time is up. Giving water at the spring means beat.20 does not happen on the spot (the
    # prevented the player registered)
    # latest より後に遅れたもの：時間切れ。泉で水を渡すと beat.20 はその場で起きない（プレイヤーが登録した prevented）
    sc = {"beats": {"beat.18": {"to": "delayed", "minutes": 240}, "beat.20": {"to": "prevented"}}}
    drafts, s = settle(WORLD, at(0, sc), None)
    reason = {d["beat"]: d["reasonCode"] for d in drafts if d["event"]["effects"][-1].get("to") == "prevented"}
    assert reason["beat.20"] == "overridden"
    assert reason["beat.24"] == "late"
    assert all(d["reason"] for d in drafts if d["reasonCode"])


# ---- Rechecking / 再確認 ----


def test_recheck_until_latest(play_scenario: Play) -> None:
    # sc.king-hardened：王の信頼が 0 になり、刑場の beat.26（前提 trust >= 1）は 5475 に起きない。
    # latest 5520 より前に信頼が戻れば、その時刻に起きる。過ぎてからでは起きない（時間切れ）
    base = next(sc for sc in SCENARIOS if sc["id"] == "sc.king-hardened")
    s, _ = play_scenario(WORLD, base)
    assert s["beats"]["beat.26"] == "prevented"
    inc = {"op": "inc", "var": "var.king.trust", "by": 10}
    for t, want in ((5490, "happened"), (5520, "happened"), (5530, "prevented")):
        sc = {**base, "events": base["events"] + [{"t": t, "effects": [inc]}]}
        s, log = play_scenario(WORLD, sc)
        one = SIM.run(sc, role=ROLE)
        assert s["beats"]["beat.26"] == want == (one["status"]["beat.26"] if want == "happened" else "prevented")
        if want == "happened":
            assert s["times"]["beat.26"] == one["times"]["beat.26"] == t
        else:
            expired = [e for e in log if {"op": "beat", "beat": "beat.26", "to": "prevented"} in e["effects"]]
            assert [e["t"] for e in expired] == [5520]


def test_recheck_downstream_happens_at_the_same_moment(play_scenario: Play) -> None:
    # The literal behaviour of contract 2.4.1 item 3: after beat.05, set the promise back to false, then back to
    # true at 1450. beat.06 (1410 in the original) waits on its preconditions, and beat.07 (1425 in the original),
    # which requires it, waits too; at 1450 both happen one after the other in order
    # 契約 2.4.1 第 3 項の字義どおりの挙動：beat.05 の後で約束を false に戻し、1450 に true に戻す。
    # beat.06（原作 1410）は前提条件を待ち、それを requires する beat.07（原作 1425）も待つ。1450 に両方が order 順に
    # 続けて起きる
    off = {"op": "set", "var": "var.promise.made", "value": False}
    on = {"op": "set", "var": "var.promise.made", "value": True}
    sc = {"id": "sc.test-recheck", "events": [{"t": 1235, "effects": [off]}, {"t": 1450, "effects": [on]}]}
    s, log = play_scenario(WORLD, sc)
    one = SIM.run(sc, role=ROLE)
    assert s["times"]["beat.06"] == s["times"]["beat.07"] == 1450
    assert one["times"]["beat.06"] == one["times"]["beat.07"] == 1450
    order = [x["beat"] for e in log for x in e["effects"] if x.get("op") == "beat"]
    assert order.index("beat.06") < order.index("beat.07")


# ---- Role, world_state, prediction / ロール、world_state、予測 ----


def test_initial_state_reads_the_role() -> None:
    for role in WORLD["roles"]:
        s = initial_state(WORLD, role["id"])
        assert s["vars"]["var.player.location"] == role["startPlace"]
        assert s["vars"]["var.act.current"] == role["startAct"]
        assert sorted(k for k, v in s["holdings"].items() if v == "player") == sorted(role.get("items") or [])
        assert s["holdings"]["item.dagger"] == "char.melos"
        assert s["t"] == 0 and s["cursor"] is None and s["seq"] == 0


def test_world_state_passes_the_schema(played: Played) -> None:
    check = validator("data/world-state.schema.json#/$defs/WorldState")
    _, log = played("sc.canon")
    s = initial_state(WORLD, ROLE)
    for i, e in enumerate(log):
        s = apply(WORLD, s, e)
        if i % 5 == 0 or i == len(log) - 1:
            ws = world_state(WORLD, s, "pt_01HZY0000000000000000000AB")
            assert not list(check.iter_errors(ws)), i
            assert ws["asOfSeq"] == i + 1
            assert set(ws["beats"]) == set(SIM.beats) and set(ws["schedule"]) == set(SIM.beats) - set(s["beats"])


def test_world_state_beats_pending_delayed_hastened() -> None:
    sc = {"beats": {"beat.18": {"to": "delayed", "minutes": 30}, "beat.19": {"to": "hastened", "minutes": 10}}}
    ws = world_state(WORLD, at(1050, sc), "pt_01HZY0000000000000000000AB")
    assert ws["beats"]["beat.18"] == "delayed" and ws["beats"]["beat.19"] == "hastened"
    assert ws["beats"]["beat.24"] == "pending" and ws["beats"]["beat.01"] == "happened"


def test_world_state_needs_event_ids() -> None:
    improv = {
        "op": "improv",
        "factId": "rf_01HZY0000000000000000000AB",
        "character": "char.melos",
        "statement": "羊を飼っている",
    }
    s = apply(WORLD, at(1050), ev(1050, improv))
    with pytest.raises(ValueError, match="event ID"):
        world_state(WORLD, s, "pt_01HZY0000000000000000000AB")
    s = apply(WORLD, at(1050), ev(1050, improv, eventId="ev_01HZY0000000000000000000AB"))
    assert world_state(WORLD, s, "pt_01HZY0000000000000000000AB")["runFacts"]


@pytest.mark.parametrize("sc", SCENARIOS, ids=lambda sc: sc["id"])
def test_predict_from_the_start(sc: dict[str, Any]) -> None:
    if sc.get("events"):
        pytest.skip(
            "Scenarios with player events need the event-by-event simulation; test_incremental_equals_one_shot already"
            " compared them / プレイヤーのイベントがあるシナリオはイベントごとのシミュレーションが必要で、"
            "test_incremental_equals_one_shot で比較済み"
        )
    assert predict(WORLD, at(0, sc)) == SIM.run(sc, role=ROLE)["outcome"]


def test_arrival_delta_from_incremental_state(golden: dict[str, Any]) -> None:
    effects = {af["id"]: af["effects"] for af in WORLD["affordances"]}
    base = at(1050)
    for g in golden["arrival"]:
        if g["action"] not in effects:
            continue
        s = settle(WORLD, base, g["t"])[1]
        assert arrival_delta(WORLD, s, effects[g["action"]], g["t"]) == {"minutes": g["minutes"], "inTime": g["inTime"]}


# ---- apply and check_effects / apply と check_effects ----


def test_apply_effects() -> None:
    s = at(1050)
    eid = "ev_01HZY0000000000000000000AB"
    promise = {"op": "promise", "promiseId": "prm_01HZY0000000000000000000AB", "change": "made"}
    s = apply(
        WORLD,
        s,
        ev(
            1050,
            {"op": "inc", "var": "var.king.trust", "by": 500},
            {"op": "learn", "character": "char.melos", "fact": WORLD["facts"][0]["id"]},
            {"op": "learn", "character": "char.melos", "fact": WORLD["facts"][0]["id"]},
            {"op": "hold", "item": "item.cloak", "to": "char.melos"},
            {**promise, "from": "player", "to": "char.melos", "text": "必ず戻る"},
            eventId=eid,
            dt=15,
        ),
    )
    assert s["vars"]["var.king.trust"] == 100  # inc is clamped at max / inc は max で切り詰める
    assert s["knowledge"]["char.melos"] == [WORLD["facts"][0]["id"]]
    assert s["holdings"]["item.cloak"] == "char.melos"
    assert s["promises"]["prm_01HZY0000000000000000000AB"]["status"] == "open"
    assert s["t"] == 1065 and s["cursor"] == 1050
    s = apply(WORLD, s, ev(1065, {**promise, "change": "kept"}, eventId=eid))
    assert s["promises"]["prm_01HZY0000000000000000000AB"]["resolvedBy"] == eid
    with pytest.raises(ValueError, match="open"):
        apply(WORLD, s, ev(1065, {**promise, "change": "broken"}))


def test_apply_rejects() -> None:
    s = apply(WORLD, at(1050), ev(1050))
    with pytest.raises(ValueError, match="goes backwards"):
        apply(WORLD, s, ev(1000))
    with pytest.raises(ValueError, match="not defined"):
        apply(WORLD, s, ev(1050, {"op": "beat", "beat": "beat.24", "to": "happened"}))
    with pytest.raises(ValueError, match="already has a result"):
        apply(WORLD, s, ev(1050, {"op": "beat", "beat": "beat.01", "to": "delayed", "minutes": 10}))
    with pytest.raises(ValueError, match="worldModelVersion|world model"):
        apply({**WORLD, "worldModelVersion": "other"}, s, ev(1050))


def test_spots_follow_relocate() -> None:
    """Contract 3.1 (1.7, C-18): with a spot, stand there; without one, it is removed only on a change of place and
    kept within the same place.

    契約 3.1（1.7、C-18）：spot があればそこに立つ。なければ場所が変わったときだけ取り除き、同じ場所の中では
    動かさない。
    """
    g = "place.execution-ground"
    s = apply(
        WORLD, at(1050), ev(1050, {"op": "relocate", "character": "char.selinuntius", "place": g, "spot": "stake"})
    )
    assert s["spots"] == {"char.selinuntius": "stake"}
    s = apply(WORLD, s, ev(1050, {"op": "relocate", "character": "char.selinuntius", "place": g}))
    # A beat moves participants to the beat's place: someone already there does not move
    # ビートは参加人物をビートの場所に移す：すでにそこにいる人は動かない
    assert s["spots"] == {"char.selinuntius": "stake"}
    s = apply(WORLD, s, ev(1050, {"op": "relocate", "character": "char.selinuntius", "place": "place.castle"}))
    assert s["spots"] == {}
    assert world_state(WORLD, s, "pt_01HZY0000000000000000000AB")["spots"] == {}
    old = {k: v for k, v in at(1050).items() if k != "spots"}  # State saved before 1.7 / 1.7 より前に保存した状態
    s = apply(WORLD, old, ev(1050, {"op": "relocate", "character": "char.king", "place": g, "spot": "king-west"}))  # type: ignore[arg-type]
    assert s["spots"] == {"char.king": "king-west"}


def test_beat_s1_puts_the_friend_on_the_stake_and_the_king_behind_the_crowd() -> None:
    s = settle(WORLD, initial_state(WORLD, ROLE), 5410)[1]
    assert s["beats"]["beat.s1"] in OCCURRED
    assert s["spots"]["char.selinuntius"] == "stake" and s["spots"]["char.king"] == "king-west"
    assert "char.crowd" not in s["spots"]  # group: takes no spot / group は立ち位置を取らない


AFF = {a["id"]: a["effects"] for a in WORLD["affordances"]}


def test_beat_changes_net_out() -> None:
    """Contract section 3 (clarified in 1.6, backend review of W-1): a beat without a result yet has only one kind of
    change; delays and hastening add up as signed minutes.

    契約第 3 節（1.6 で明記、W-1 のバックエンドレビュー）：まだ結果の出ていないビートへの変更は 1 種類だけ。遅延と
    前倒しは符号付きの分数として足す。
    """
    s = at(1050)
    delay = {"op": "beat", "beat": "beat.18", "to": "delayed", "minutes": 30}
    s = apply(WORLD, s, ev(1050, delay, delay))
    assert s["overrides"]["beat.18"] == {"to": "delayed", "minutes": 60}
    s = apply(WORLD, s, ev(1050, {"op": "beat", "beat": "beat.18", "to": "hastened", "minutes": 10}))
    assert s["overrides"]["beat.18"] == {"to": "delayed", "minutes": 50}
    s = apply(WORLD, s, ev(1050, {"op": "beat", "beat": "beat.18", "to": "hastened", "minutes": 50}))
    assert "beat.18" not in s["overrides"]  # Net 0: no change / 正味 0：変更なし
    s = apply(WORLD, s, ev(1050, {"op": "beat", "beat": "beat.18", "to": "hastened", "minutes": 10}))
    assert s["overrides"]["beat.18"] == {"to": "hastened", "minutes": 10}
    s = apply(WORLD, s, ev(1050, {"op": "beat", "beat": "beat.18", "to": "prevented"}))
    assert s["overrides"]["beat.18"] == {"to": "prevented"}  # prevented replaces earlier ones / それまでを上書き
    for change in (delay, {"op": "beat", "beat": "beat.18", "to": "prevented"}):
        with pytest.raises(ValueError, match="prevented"):
            apply(WORLD, s, ev(1050, change))


def test_altered_does_not_mix() -> None:
    s = at(1050)
    altered = {"op": "beat", "beat": "beat.18", "to": "altered", "outcomes": []}
    delay = {"op": "beat", "beat": "beat.18", "to": "delayed", "minutes": 30}
    for first, second in ((altered, delay), (delay, altered), (altered, altered)):
        with pytest.raises(ValueError, match="cannot register"):
            apply(WORLD, s, ev(1050, first, second))
        assert codes(check_effects(WORLD, s, [first, second], "action")) == [(1, "bad-state")]
    s = apply(WORLD, s, ev(1050, altered, {"op": "beat", "beat": "beat.18", "to": "prevented"}))
    assert s["overrides"]["beat.18"] == {"to": "prevented"}


def test_hold_then_help_at_the_river_nets_out() -> None:
    """Backend's measurement (traveler, 4980): 「引き止める」 then 「浅瀬を探す」 = a net delay of 20, too late; the
    same in the reverse order. After holding him back, the shallows button's actual value is −10 (previously −40).

    バックエンドの実測（旅人、4980）：「引き止める」の後に「浅瀬を探す」= 正味 20 分の遅れで間に合わない。順序を
    逆にしても同じ。引き止めた後の浅瀬ボタンの実際の値は −10（以前は −40）。
    """
    s = at(4980)
    hold, shallows = AFF["aff.river-hold"], AFF["aff.river-shallows"]
    assert arrival_delta(WORLD, apply(WORLD, s, ev(4980, *hold)), shallows, 4980)["minutes"] == -10
    net = apply(WORLD, s, ev(4980, {"op": "beat", "beat": "beat.18", "to": "delayed", "minutes": 20}))
    want = settle(WORLD, net, None)[1]
    assert want["beats"]["beat.24"] == "prevented"
    for first, second in ((hold, shallows), (shallows, hold)):
        both = apply(WORLD, apply(WORLD, s, ev(4980, *first)), ev(4980, *second))
        assert both["overrides"] == net["overrides"]
        assert settle(WORLD, both, None)[1]["beats"] == want["beats"]


def test_nothing_after_a_detour_changes_the_bandits() -> None:
    """Backend's measurement: take the 脇道 first (beat.19 prevented), then 「引き止める」 (beat.19 delayed 30); the
    bandits cannot come back.

    バックエンドの実測：先に脇道を行き（beat.19 prevented）、次に「引き止める」（beat.19 delayed 30）。山賊は
    戻ってこられない。
    """
    s = at(4980)
    detour, hold = AFF["aff.pass-detour-told"], AFF["aff.pass-hold"]
    assert codes(check_effects(WORLD, s, [*detour, *hold], "action")) == [(len(detour), "bad-state")]
    s = apply(WORLD, s, ev(4980, *detour))
    assert codes(check_effects(WORLD, s, hold, "action")) == [(0, "bad-state")]
    with pytest.raises(ValueError, match="prevented"):
        apply(WORLD, s, ev(4980, *hold))
    with pytest.raises(ValueError, match="prevented"):
        arrival_delta(WORLD, s, hold, 4980)
    assert settle(WORLD, s, None)[1]["beats"]["beat.19"] == "prevented"


def test_schedule_origin_is_only_for_beats_and_the_deadline() -> None:
    """Backend review item 2: if a system event such as a bell is written as schedule / action, the deadline is
    never settled again. Now it raises ValueError.

    バックエンドレビュー第 2 項：鐘の音のようなシステムイベントを schedule / action で書くと、期限が二度と精算
    されなくなる。今は ValueError を送出する。
    """
    dl = WORLD["clock"]["deadline"]["t"]
    s = at(1050)
    with pytest.raises(ValueError, match="earlier than the deadline"):
        apply(WORLD, s, ev(1050, origin="schedule", type="action"))
    with pytest.raises(ValueError, match="used only for"):
        apply(WORLD, s, ev(1050, origin="schedule", type="say"))
    two = [{"op": "beat", "beat": b, "to": "prevented"} for b in ("beat.18", "beat.19")]
    with pytest.raises(ValueError, match="exactly one"):
        apply(WORLD, s, ev(1050, *two, origin="schedule", type="beat"))
    s = at(dl)
    assert s["deadline"]
    with pytest.raises(ValueError, match="already been settled"):
        apply(WORLD, s, ev(dl, origin="schedule", type="action"))


def test_apply_checks_seq_and_that_the_clock_was_settled() -> None:
    s = at(1050)
    s = apply(WORLD, s, ev(1050, seq=s["seq"] + 1))
    with pytest.raises(ValueError, match="seq"):
        apply(WORLD, s, ev(1050, seq=s["seq"] + 2))
    with pytest.raises(ValueError, match="first, then apply"):
        apply(WORLD, s, ev(4980))  # The beats in between were not settled / 間のビートが未精算
    with pytest.raises(ValueError, match="first, then apply"):
        apply(WORLD, initial_state(WORLD, ROLE), ev(1050))


def codes(problems: list[Any]) -> list[tuple[int, str]]:
    return [(p["index"], p["code"]) for p in problems]


def test_check_effects_shapes_and_references() -> None:
    s = at(1050)
    good = [
        {"op": "set", "var": "var.player.location", "value": "place.castle"},
        {"op": "inc", "var": "var.melos.stamina", "by": -5},
        {"op": "relocate", "character": "char.melos", "place": "place.castle"},
        {"op": "hold", "item": "item.cloak", "to": "char.melos"},
        {"op": "beat", "beat": "beat.18", "to": "delayed", "minutes": 30},
    ]
    assert check_effects(WORLD, s, good, "action") == []
    bad = [
        {"op": "set", "var": "var.nope", "value": 1},
        {"op": "set", "var": "var.king.disposition", "value": "angry"},
        {"op": "inc", "var": "var.king.disposition", "by": 1},
        {"op": "relocate", "character": "char.nobody", "place": "place.castle"},
        {"op": "hold", "item": "item.water", "to": "player"},
        {"op": "learn", "character": "char.melos", "fact": "fact.nope"},
        {"op": "beat", "beat": "beat.24", "to": "happened"},
        {"op": "beat", "beat": "beat.01", "to": "prevented"},
        {"op": "beat", "beat": "beat.18", "to": "delayed"},
        {"op": "promise", "promiseId": "prm_01HZY0000000000000000000AB", "change": "kept"},
        {"op": "teleport"},
        {"op": "relocate", "character": "char.king", "place": "place.castle", "spot": "King West"},
    ]
    assert codes(check_effects(WORLD, s, bad, "turn")) == [
        (0, "bad-value"),
        (1, "bad-value"),
        (2, "bad-op"),
        (3, "unknown-id"),
        (4, "bad-op"),
        (5, "unknown-id"),
        (6, "beat-happened"),
        (7, "beat-has-result"),
        (8, "bad-value"),
        (9, "bad-state"),
        (10, "bad-op"),
        (11, "bad-value"),
    ]


def test_check_effects_value_requires_by_origin() -> None:
    # Contract 1.6 (C-16): judged by origin, not actor. Director events (actor system, origin director) are judged too
    # 契約 1.6（C-16）：actor ではなく origin で判定する。ディレクターイベント（actor system、origin director）も判定
    s = at(1050)
    reformed = [{"op": "set", "var": "var.king.disposition", "value": "reformed"}]
    for origin in ("turn", "action", "director", "plan", None):
        got = check_effects(WORLD, s, reformed, origin)
        assert codes(got) == [(0, "value-requires")], origin
        assert got[0].get("note")
    assert check_effects(WORLD, s, reformed, "schedule") == []
    # In the same event, raise trust first and then set it: judged on the state before each effect
    # 同じイベント内で先に信頼を上げてから設定する：各 effect の前の状態で判定
    up = {"op": "inc", "var": "var.king.trust", "by": 65}
    assert check_effects(WORLD, s, [up, *reformed], "director") == []
    assert codes(check_effects(WORLD, s, [*reformed, up], "director")) == [(0, "value-requires")]


def test_flat_view_has_items_and_vars() -> None:
    s = initial_state(WORLD, ROLE)
    f = flat(s)
    assert f["item.waterskin"] == "player" and f["var.king.trust"] == s["vars"]["var.king.trust"]
