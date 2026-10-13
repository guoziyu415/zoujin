"""Shared rule library for world state (W-1). The narrator, the eval runner and the data tools all use only this;
world state is computed by this one set of rules and no other.

- Whole-run simulation: Sim (run / resume / arrival_delta / classify), ported verbatim from the reference
  implementation ../../reference/worldsim.py;
- Event-by-event simulation: initial_state / apply / settle / world_state / check_effects, plus classify / signature /
  predict / arrival_delta;
- From the opening to a starting point: opening / parse_checkpoint (the three starting points in eval_api's setup:
  checkpoint, scenario, place);
- Primitives of the narrator rules: knows (R4, who knows a thing right now), travel_minutes (R3, the minimum minutes
  of walking between two places), activity (R7 and snapshots, what a character is doing right now; one that is
  absent cannot be talked to), spoilers (R4 and output-side monitoring, whether an utterance contains something that
  should not be known right now);
- (1.7) Which set piece to play: pick_set_piece (contract 2.11);
- (1.12) Whether the player can see an event: sees (contract section 3; used for writing learn, pushing events, and
  presence at set pieces);
- (1.12 addendum) Which beats a character lived through: lived (the most recent beat the narrator gives a character),
  place_at (where a character should be at the moment of a beat, according to the beat).

To change a rule, change the reference implementation first, then rerun tests/golden/gen_golden.py.

世界状態の共有ルールライブラリ（W-1）。ナレーター、評価ランナー、データのツールはすべてこれだけを使い、
世界状態を計算するルールはこの一式しかない。

- 一括シミュレーション：Sim（run / resume / arrival_delta / classify）。参照実装 ../../reference/worldsim.py から
  そのまま移植；
- イベントごとのシミュレーション：initial_state / apply / settle / world_state / check_effects、加えて classify /
  signature / predict / arrival_delta；
- オープニングから起点まで：opening / parse_checkpoint（eval_api の setup にある checkpoint、scenario、place の
  3 種類の起点）；
- ナレーター規則のプリミティブ：knows（R4、今この時点で誰が何を知っているか）、travel_minutes（R3、2 地点間を
  最短で何分歩くか）、activity（R7 とスナップショット、登場人物が今何をしているか。absent なら会話できない）、
  spoilers（R4 と出力側の監視、発話に今知っているはずのないことが含まれていないか）；
- （1.7）どの固定演出を上演するか：pick_set_piece（契約 2.11）；
- （1.12）プレイヤーがあるイベントを見られるか：sees（契約第 3 節。learn の書き込み、イベントのプッシュ、
  固定演出での在場判定のすべてで使う）；
- （1.12 補足）登場人物がどのビートを体験したか：lived（ナレーターが登場人物に渡す直近のビート）、place_at（ビートの
  その瞬間に、ビートに従って登場人物がどこにいるべきか）。

ルールを変えるときは先に参照実装を変え、tests/golden/gen_golden.py を再実行する。
"""

from .incremental import (
    Draft,
    Problem,
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
from .opening import Opened, Until, opening, parse_checkpoint
from .pieces import pick_set_piece
from .primitives import activity, knows, lived, place_at, spoilers, travel_minutes
from .sim import OCCURRED, Sim, role_of
from .visibility import same_scene, sees

__all__ = [
    "OCCURRED",
    "Draft",
    "Opened",
    "Problem",
    "Sim",
    "SimState",
    "Until",
    "activity",
    "apply",
    "arrival_delta",
    "check_effects",
    "classify",
    "flat",
    "initial_state",
    "knows",
    "lived",
    "opening",
    "parse_checkpoint",
    "pick_set_piece",
    "place_at",
    "predict",
    "role_of",
    "same_scene",
    "sees",
    "settle",
    "signature",
    "spoilers",
    "travel_minutes",
    "world_state",
]
