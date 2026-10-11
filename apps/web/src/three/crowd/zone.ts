// Where the crowd stands on the execution ground (F-4): the zone, who faces where, the places kept clear. Until
// layout.json has its own crowd zone, the zone is the execution ground's place polygon. Pure (no three), so the
// tests check it.
import type { LoadedScene } from "../scene/loadScene";
import type { Clear, Plan } from "./scatter";

const PLACE = "place.execution-ground";
const POST = "stake";
const GATE = "gate-inside";
// the points the world model stands people on here (data review on #131): nobody of the crowd on them. The way from
// the gate to the post is not kept clear: the crowd stands in it and part() opens it (art-direction 4.1)
const SPOTS = [
  "scaffold",
  "crowd-front",
  "stake-front",
  "stake-front-side",
  "ground-west",
  "king-west",
];
export const GAP = 0.7;
// how far to either side of the line from the post to the gate: the crowd a block in front of the scaffold, from its
// front and the foot of its steps back, between it and whoever comes from the gate (UX on #139 and #148: 「群衆を
// かきわけ」 needs a wall of people in front of the post, not a few spread wide)
const WIDTH = 3.5;
// the scaffold, ahead of the stake spot / to either side (assets/pipeline/plaza/build_plaza.py: the platform's front
// 0.8 m ahead, 1.5 m to the side; the steps to 2.2 m ahead, 0.9 m to the side), with half a body's room
export const PLATFORM = [1.25, 1.95];
export const STEPS = [2.6, 1.25];

export function crowdSpec(scene: LoadedScene, count: number, seed = 1) {
  const { manifest, nav } = scene;
  const zone = manifest.places.find((p) => p.id === PLACE)?.polygon as
    Plan[] | undefined;
  const post = manifest.spots[POST]?.pos;
  if (!zone || !post) return null;
  const clear: Clear[] = [];
  for (const s of SPOTS) {
    const p = manifest.spots[s]?.pos;
    if (p) clear.push({ at: [p[0], p[2]], r: GAP + 0.15 });
  }
  // in front of the post, on the gate's side of it: off the scaffold and its steps, to a metre short of where the king
  // watches from (king-west: 「群衆の背後から」, C-18), and at most WIDTH to either side
  const gate = manifest.spots[GATE]?.pos;
  const king = manifest.spots["king-west"]?.pos;
  let keep: ((p: Plan) => boolean) | undefined;
  if (gate) {
    const len = Math.hypot(gate[0] - post[0], gate[2] - post[2]);
    const [gx, gz] = [(gate[0] - post[0]) / len, (gate[2] - post[2]) / len];
    const ahead = (x: number, z: number) =>
      (x - post[0]) * gx + (z - post[2]) * gz;
    const side = (x: number, z: number) =>
      Math.abs((z - post[2]) * gx - (x - post[0]) * gz);
    const far = king ? ahead(king[0], king[2]) - 1 : Infinity;
    const off = (a: number, s: number, [front, half]: number[]) =>
      a >= front! || s >= half!;
    keep = ([x, z]: Plan) => {
      const [a, s] = [ahead(x, z), side(x, z)];
      return (
        a > 0 && a < far && s < WIDTH && off(a, s, PLATFORM) && off(a, s, STEPS)
      );
    };
  }
  return {
    zone,
    facing: [post[0], post[2]] as Plan,
    ...(keep ? { keep } : {}),
    count,
    seed,
    gap: GAP,
    clear,
    height: (x: number, z: number) => nav.nearest(x, z)?.y ?? 0,
  };
}
