// The crowd in the scene (F-4): on the execution ground, facing the post with their backs to the gate (art-direction
// 4.1, 5.5), clear of the scaffold and of the way from the gate to it. Until layout.json has its own crowd zone (the
// asset PR regenerates the scene), the zone is the execution ground's place polygon. Its own chunk: only a scene with a
// crowd downloads it.
import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import type { LoadedScene } from "../scene/loadScene";
// tied to the world chunk, so three and the shader patches stay in that one chunk: without it the bundler splits what
// this chunk and the world chunk both use into a third chunk, and three compressed apart from the rest costs ~4 KB
import "../World";
import { Crowd } from "./Crowd";
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
const GAP = 0.75;

// the scene's crowd, for the staging and the test hook
export const crowdRef: { current: Crowd | null } = { current: null };

export function crowdSpec(scene: LoadedScene, count: number, seed = 1) {
  const { manifest, nav } = scene;
  const zone = manifest.places.find((p) => p.id === PLACE)?.polygon as
    Plan[] | undefined;
  const post = manifest.spots[POST]?.pos;
  if (!zone || !post) return null;
  const clear: Clear[] = [{ at: [post[0], post[2]], r: 3 }];
  for (const s of SPOTS) {
    const p = manifest.spots[s]?.pos;
    if (p) clear.push({ at: [p[0], p[2]], r: GAP + 0.15 });
  }
  // in front of the post, on the gate's side of it: from a metre and a half on, to a metre short of where the king
  // watches from (king-west: 「群衆の背後から」, C-18)
  const gate = manifest.spots[GATE]?.pos;
  const king = manifest.spots["king-west"]?.pos;
  let keep: ((p: Plan) => boolean) | undefined;
  if (gate) {
    const len = Math.hypot(gate[0] - post[0], gate[2] - post[2]);
    const [gx, gz] = [(gate[0] - post[0]) / len, (gate[2] - post[2]) / len];
    const ahead = (x: number, z: number) =>
      (x - post[0]) * gx + (z - post[2]) * gz;
    const far = king ? ahead(king[0], king[2]) - 1 : Infinity;
    keep = ([x, z]: Plan) => ahead(x, z) > 1.5 && ahead(x, z) < far;
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

export default function CrowdLayer({
  scene,
  count,
}: {
  scene: LoadedScene;
  count: number;
}) {
  const crowd = useMemo(() => {
    const spec = crowdSpec(scene, count);
    return spec ? new Crowd(spec) : null;
  }, [scene, count]);
  useEffect(() => {
    crowdRef.current = crowd;
    return () => {
      crowdRef.current = null;
      crowd?.dispose();
    };
  }, [crowd]);
  useFrame(({ clock }) => crowd?.update(clock.elapsedTime));
  return crowd ? <primitive object={crowd} /> : null;
}
