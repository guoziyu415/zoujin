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
const WAY = ["gate-street", "king-west", "stake-front"]; // the corridor from the gate to the post
const GATE = "gate-inside";

// the scene's crowd, for the staging and the test hook
export const crowdRef: { current: Crowd | null } = { current: null };

export function crowdSpec(scene: LoadedScene, count: number, seed = 1) {
  const { manifest, nav } = scene;
  const zone = manifest.places.find((p) => p.id === PLACE)?.polygon as
    Plan[] | undefined;
  const post = manifest.spots[POST]?.pos;
  if (!zone || !post) return null;
  const clear: Clear[] = [{ at: [post[0], post[2]], r: 3 }];
  // the corridor: circles every metre along it
  const way = WAY.map((s) => manifest.spots[s]?.pos).filter(
    (p): p is [number, number, number] => !!p,
  );
  for (let i = 0; i + 1 < way.length; i++) {
    const [a, b] = [way[i]!, way[i + 1]!];
    const n = Math.ceil(Math.hypot(b[0] - a[0], b[2] - a[2]));
    for (let k = 0; k <= n; k++)
      clear.push({
        at: [a[0] + ((b[0] - a[0]) * k) / n, a[2] + ((b[2] - a[2]) * k) / n],
        r: 1.1,
      });
  }
  // in front of the post only: on the gate's side of it, a metre and a half on
  const gate = manifest.spots[GATE]?.pos;
  const keep = gate
    ? ([x, z]: Plan) => {
        const [gx, gz] = [gate[0] - post[0], gate[2] - post[2]];
        return (
          ((x - post[0]) * gx + (z - post[2]) * gz) / Math.hypot(gx, gz) > 1.5
        );
      }
    : undefined;
  return {
    zone,
    facing: [post[0], post[2]] as Plan,
    ...(keep ? { keep } : {}),
    count,
    seed,
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
