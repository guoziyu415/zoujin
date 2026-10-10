"""用参考实现 reference/worldsim.py 生成 W-1 的黄金文件。参考实现改了（规则改动先改它）就重跑，CI 查生成物一致。

    python3 -I packages/worldsim/tests/golden/gen_golden.py

写三个文件（都用旅人：Role.startPlace、Role.items）：
- runs.json：原作和 scenarios.json 的情景，一共 24 次推演各自跑到底的结果；
- canon_beats.json：原作里每个节拍刚发生时的 t 和人物所在地（防剧透探针的 place / when 靠它）；
- arrival.json：每个带 melosMinutes 的动作，在第四幕开始到它改的节拍发生前每 15 分钟（第四幕说一轮话的长度，
  pacing.talkTurnMinutesAct4）的 arrival_delta；
  过场二选一的选项在收幕时选，只算收幕那一刻。
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
STEP = 15  # 第四幕一轮的长度：玩家每个能做的时刻


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
    """(动作, effects, 算哪些时刻)。时刻 = 第四幕开始到它改的节拍在原作里发生前，每 STEP 分钟。"""
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
