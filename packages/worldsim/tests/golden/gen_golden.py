"""Generates the W-1 golden files with the reference implementation reference/worldsim.py. Rerun whenever the
reference implementation changes (rule changes go there first); CI checks that the generated files match.

    python3 -I packages/worldsim/tests/golden/gen_golden.py

Writes three files (all with the traveler: Role.startPlace, Role.items):
- runs.json: the original story and the scenarios of scenarios.json, the result of each of the 24 simulations run to
  the end;
- canon_beats.json: for each beat in the original story, t and the characters' locations right after it happens (the
  anti-spoiler probes' place / when rely on it);
- arrival.json: for each action with melosMinutes, arrival_delta every 15 minutes (the length of one exchange in act
  4, pacing.talkTurnMinutesAct4) from the start of act 4 until before the beat it changes happens;
  the either-or options of an interlude are chosen when closing the act, so only the moment of closing the act is
  computed.

参照実装 reference/worldsim.py で W-1 のゴールデンファイルを生成する。参照実装が変わったら（ルールの変更はまず
そちらに入れる）再実行する。CI は生成物の一致を確認する。

    python3 -I packages/worldsim/tests/golden/gen_golden.py

3 つのファイルを書く（すべて旅人：Role.startPlace、Role.items）：
- runs.json：原作と scenarios.json のシナリオ、計 24 回のシミュレーションをそれぞれ最後まで実行した結果；
- canon_beats.json：原作の各ビートが起きた直後の t と登場人物の所在地（ネタバレ防止プローブの place / when は
  これに頼る）；
- arrival.json：melosMinutes を持つ各アクションについて、第四幕の開始からそれが変えるビートの発生前まで 15 分ごと
  （第四幕で 1 回やりとりする長さ、pacing.talkTurnMinutesAct4）の arrival_delta；
  幕間の二択は幕を閉じるときに選ぶので、幕を閉じる時点だけを計算する。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
W = REPO / "worlds" / "hashire-merosu" / "1.0.0-draft"
ROLE = "role.traveler"
STEP = 15  # Length of one exchange in act 4: each moment the player can act / 第四幕の 1 回のやりとりの長さ


def load_reference() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "worldsim_reference", REPO / "packages/worldsim/reference/worldsim.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scenarios() -> list[dict[str, Any]]:
    canon = {"id": "sc.canon", "note": "原著どおり（プレイヤーは何もしない）", "expect": "canon-reunion"}
    return [canon] + json.loads((W / "scenarios.json").read_text(encoding="utf-8"))


def melos_actions(world: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]], list[int]]]:
    """(action, effects, which moments to compute). Moments = every STEP minutes from the start of act 4 until before
    the beat it changes happens in the original story.

    （アクション, effects, 計算する時刻）。時刻 = 第四幕の開始から、それが変えるビートが原作で起きる前まで、STEP 分
    ごと。
    """
    beats = {b["id"]: b for b in world["beats"]}
    acts = {a["id"]: a for a in world["acts"]}
    out = []
    for af in world["affordances"]:
        if not af.get("melos") or not isinstance(af.get("melosMinutes"), int):
            continue
        last = min(beats[e["beat"]]["window"]["canonical"] for e in af["effects"] if e["op"] == "beat")
        out.append((af["id"], af["effects"], list(range(acts[af["act"]]["start"]["t"], last, STEP))))
    for act in world["acts"]:
        for ex in act.get("exits", []):
            for i, x in enumerate((ex.get("enRoute") or {}).get("choices", [])):
                if isinstance(x.get("melosMinutes"), int):
                    ends = [beats[b]["window"]["canonical"] for b in act["end"]["onBeats"] if b in beats]
                    out.append((f"{ex['id']}.enRoute[{i}]", x["effects"], [max(ends, default=act["start"]["t"])]))
    return out


def main() -> None:
    ref = load_reference()
    world = json.loads((W / "world.json").read_text(encoding="utf-8"))
    role = next(r for r in world["roles"] if r["id"] == ROLE)
    start = {"start_place": role["startPlace"], "player_items": tuple(role.get("items") or ())}
    svars = [v["id"] for v in world["stateVars"]]
    items = {it["id"] for it in world["items"]}
    sig = world["endings"]["signature"]
    sim = ref.Sim(world)

    runs = {}
    for sc in scenarios():
        r = sim.run(sc, **start)
        runs[sc["id"]] = {
            "outcome": r["outcome"],
            "signature": {
                "vars": {v: r["state"].get(v) for v in sig["vars"]},
                "beats": {b: r["status"].get(b) == "happened" for b in sig["beats"]},
            },
            "status": r["status"],
            "times": r["times"],
            "variant": r["variant"],
            "vars": {v: r["state"].get(v) for v in svars},
            "holdings": {k: v for k, v in r["state"].items() if k in items},
            "where": r["where"],
            "arrival": r["times"].get(world["clock"]["deadline"]["watchBeat"]),
            "shift": r["shift"],
            "late": sorted(r["late"]),
            "auto": sorted(r["auto"]),
            "violations": [[t, x] for t, x in r["violations"]],
        }

    canon = {}
    for b in sorted(world["beats"], key=lambda b: b["order"]):
        r = sim.run({}, until=("beat", b["id"]), **start)
        canon[b["id"]] = {"t": r["t"], "status": r["status"].get(b["id"]), "where": r["where"]}

    arrival = []
    for aid, effects, times in melos_actions(world):
        for t in times:
            got = sim.arrival_delta({}, effects, t, **start)
            arrival.append({"action": aid, "t": t, "minutes": got["minutes"], "inTime": got["inTime"]})

    meta = {
        "role": ROLE,
        "world": world["worldModelVersion"],
        "generator": "packages/worldsim/tests/golden/gen_golden.py",
    }
    for name, data in (("runs", runs), ("canon_beats", canon), ("arrival", arrival)):
        text = json.dumps({"meta": meta, name: data}, ensure_ascii=False, indent=1) + "\n"
        (HERE / f"{name}.json").write_text(text, encoding="utf-8")
        print(f"wrote {name}.json")


if __name__ == "__main__":
    main()
