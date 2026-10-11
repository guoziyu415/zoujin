// The crowd in the scene (F-4): on the execution ground, facing the post with their backs to the gate (art-direction
// 4.1, 5.5), clear of the scaffold and of the way from the gate to it. Until layout.json has its own crowd zone (the
// asset PR regenerates the scene), the zone is the execution ground's place polygon. The bodies are the scene pack's
// crowd/ (pack.ts), the stand-ins when it has none. Its own chunk: only a scene with a crowd downloads it.
import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useState } from "react";
import type { LoadedScene } from "../scene/loadScene";
// tied to the world chunk, so three and the shader patches stay in that one chunk: without it the bundler splits what
// this chunk and the world chunk both use into a third chunk, and three compressed apart from the rest costs ~4 KB
import "../World";
import { Crowd } from "./Crowd";
import { loadCrowdPack, loadMotions, type CrowdPack } from "./pack";
import type { Clip } from "./rig";
import { crowdSpec } from "./zone";

// the scene's crowd, for the staging and the test hook
export const crowdRef: { current: Crowd | null } = { current: null };
let waiting: ((c: Crowd) => void)[] = [];
// the crowd once it stands (its pack may still be on the way when the staging starts): a cue given before then is
// played as soon as it's there, not dropped (data on #139). The staging chains its cue on it (whenCrowd().then), never
// awaits it in line; a scene left before its crowd stood drops what was waiting (CrowdLayer unmounts)
export function whenCrowd(): Promise<Crowd> {
  const c = crowdRef.current;
  return c ? Promise.resolve(c) : new Promise((done) => waiting.push(done));
}

export default function CrowdLayer({
  scene,
  count,
}: {
  scene: LoadedScene;
  count: number;
}) {
  // undefined: still loading
  const [pack, setPack] = useState<
    { bodies: CrowdPack | null; motions: Clip[] } | undefined
  >(undefined);
  useEffect(() => {
    let live = true;
    void Promise.all([
      loadCrowdPack(scene.base).catch(() => null),
      loadMotions(scene.base),
    ]).then(([bodies, motions]) => live && setPack({ bodies, motions }));
    return () => {
      live = false;
    };
  }, [scene]);
  const crowd = useMemo(() => {
    const spec = pack && crowdSpec(scene, count);
    return pack && spec ? new Crowd(spec, pack.bodies, pack.motions) : null;
  }, [scene, count, pack]);
  useEffect(() => {
    crowdRef.current = crowd;
    if (crowd) {
      for (const done of waiting) done(crowd);
      waiting = [];
    }
    return () => {
      crowdRef.current = null;
      crowd?.dispose();
    };
  }, [crowd]);
  useEffect(
    () => () => {
      waiting = [];
    },
    [],
  );
  useFrame(({ clock }) => crowd?.update(clock.elapsedTime));
  return crowd ? <primitive object={crowd} /> : null;
}
