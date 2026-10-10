// The 3D layer of the world screen (frontend-design 4, 8): loads the scene in two steps, then sun, sky, player,
// camera and post-processing. Reads the store only; never touches the network.
import { useThree } from "@react-three/fiber";
import { useEffect, useRef, useState } from "react";
import { CameraRig } from "./CameraRig";
import { useWorld } from "./dev/fakeStore";
import { Lighting } from "./Lighting";
import { Player } from "./Player";
import { PostFX } from "./PostFX";
import { quality, useQuality } from "./quality/quality";
import {
  applyTier,
  loadDetail,
  loadHigh,
  loadWalkable,
  type LoadedScene,
} from "./scene/loadScene";
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
  entryMbps: 0, // the entry pack's download speed, Mbit/s (decides the high tier's textures)
  sceneRotationDeg: 0,
  spots: {} as Record<string, [number, number, number]>, // world positions, for the test hook
};

export function World({ onStage }: { onStage: (s: LoadStage) => void }) {
  const { gl, scene: three, camera } = useThree();
  const sceneId = useWorld((s) => s.sceneId);
  const [scene, setScene] = useState<LoadedScene | null>(null);
  const checkHigh = useRef<() => void>(() => {});

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
        const tc2 = performance.now();
        await gl.compileAsync(three, camera);
        const compile = loadInfo.compileMs + (performance.now() - tc2);
        loadInfo.readyMs = Math.round(performance.now() - t0);
        // downloading time only, roughly: the shader compiles taken out (decoding stays in, so it reads a bit low)
        loadInfo.entryMbps =
          (s.bytes * 8) /
          1e6 /
          Math.max(0.05, (loadInfo.readyMs - compile) / 1000);
        stage("ready");
        quality.begin(performance.now(), loadInfo.entryMbps);
        checkHigh.current();
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

  // the high tier's textures: downloaded in the background once the level is L2 / L3, swapped at a cut (quality.ts)
  useEffect(() => {
    if (!scene) return;
    let fetching = false;
    const check = () => {
      if (fetching || !quality.wantsHighTier()) return;
      fetching = true;
      loadHigh(scene, gl)
        .then(() => quality.hiDownloaded())
        .catch((e: unknown) => console.warn("high tier textures", e));
    };
    checkHigh.current = check;
    check();
    const offLevel = useQuality.subscribe((q, prev) => {
      if (q.applied !== prev.applied) check();
      if (q.assetTier !== prev.assetTier) void applyTier(scene, q.assetTier);
    });
    return offLevel;
  }, [scene, gl]);

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
