// The 3D layer of the world screen (frontend-design 4, 8): loads the scene in two steps, then sun, sky, player,
// camera and post-processing. Reads the store only; never touches the network.
import { useThree } from "@react-three/fiber";
import { useEffect, useState } from "react";
import { CameraRig } from "./CameraRig";
import { useWorld } from "./dev/fakeStore";
import { Lighting } from "./Lighting";
import { Player } from "./Player";
import { PostFX } from "./PostFX";
import { loadDetail, loadWalkable, type LoadedScene } from "./scene/loadScene";
import { patchShaderChunks } from "./shaderPatches";

patchShaderChunks();

export type LoadStage = "loading" | "walkable" | "ready" | "failed";

export const loadInfo = {
  stage: "loading" as LoadStage,
  bytes: 0,
  error: "",
  walkableMs: 0,
  readyMs: 0,
  compileMs: 0,
  sceneRotationDeg: 0,
  spots: {} as Record<string, [number, number, number]>, // world positions, for the test hook
};

export function World({ onStage }: { onStage: (s: LoadStage) => void }) {
  const { gl, scene: three, camera } = useThree();
  const sceneId = useWorld((s) => s.sceneId);
  const [scene, setScene] = useState<LoadedScene | null>(null);

  useEffect(() => {
    let alive = true;
    let loaded: LoadedScene | null = null;
    const t0 = performance.now();
    const stage = (s: LoadStage) => {
      loadInfo.stage = s;
      onStage(s);
    };
    const bytes = (n: number) => (loadInfo.bytes = n);
    loadWalkable(sceneId, bytes)
      .then(async (s) => {
        if (!alive) return;
        loaded = s;
        loadInfo.sceneRotationDeg = s.manifest.sun.sceneRotationDeg;
        loadInfo.spots = Object.fromEntries(
          Object.entries(s.manifest.spots).map(([k, v]) => [k, v.pos]),
        );
        three.add(s.root);
        setScene(s);
        // let React mount the lights first (their count is part of every shader), then compile before the first frame
        // people see (8.2)
        await new Promise((r) =>
          requestAnimationFrame(() => requestAnimationFrame(r)),
        );
        const tc = performance.now();
        await gl.compileAsync(three, camera);
        loadInfo.compileMs = Math.round(performance.now() - tc);
        loadInfo.walkableMs = Math.round(performance.now() - t0);
        stage("walkable");
        await loadDetail(s, gl, bytes);
        if (!alive) return;
        await gl.compileAsync(three, camera);
        loadInfo.readyMs = Math.round(performance.now() - t0);
        stage("ready");
      })
      .catch((e: unknown) => {
        console.error(e);
        loadInfo.error = e instanceof Error ? e.message : String(e);
        if (alive) stage("failed");
      });
    return () => {
      alive = false;
      if (loaded) three.remove(loaded.root);
    };
  }, [sceneId, gl, three, camera, onStage]);

  if (!scene) return null;
  return (
    <>
      <Lighting sun={scene.manifest.sun} />
      <Player scene={scene} />
      <CameraRig blockers={scene.blockers} />
      <PostFX />
    </>
  );
}
