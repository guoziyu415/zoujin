// The 3D layer of the world screen (frontend-design 4, 8): loads the scene in two steps, then sun, sky, player,
// camera and post-processing. Reads the store only; never touches the network.
import { useThree } from "@react-three/fiber";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { flags } from "../app/flags";
import { useWorld } from "../stores/world";
import { CameraRig } from "./CameraRig";
import { groundAlbedo, Lighting } from "./Lighting";
import { People } from "./People";
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
import { sceneBase } from "./scene/manifest";
import { patchShaderChunks } from "./shaderPatches";

patchShaderChunks();

const CrowdLayer = lazy(() => import("./crowd/CrowdLayer"));

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

// the test hook fetches the high tier this way whatever the entry pack's speed (the e2e server's reads low)
export const highTier = { fetch: (): Promise<void> => Promise.resolve() };

export type ScenePacks = readonly { sceneId: string; assetUrl: string }[];

export function World({
  onStage,
  packs,
}: {
  onStage: (s: LoadStage) => void;
  packs?: ScenePacks | undefined; // the book manifest's scenes (2.1), for the pack URLs
}) {
  const { gl, scene: three, camera } = useThree();
  const sceneId = useWorld((s) => s.world?.sceneId);
  const base = sceneId ? sceneBase(sceneId, packs) : null;
  const [scene, setScene] = useState<LoadedScene | null>(null);
  const checkHigh = useRef<() => void>(() => {});

  useEffect(() => {
    if (!base) return;
    let alive = true;
    let loaded: LoadedScene | null = null;
    const t0 = performance.now();
    const stage = (s: LoadStage) => {
      loadInfo.stage = s;
      onStage(s);
    };
    const bytes = (n: number) => (loadInfo.bytes = n);
    loadWalkable(base, bytes)
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
  }, [base, gl, three, camera, onStage]);

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
    highTier.fetch = () =>
      loadHigh(scene, gl).then(() => quality.hiDownloaded());
    check();
    const offLevel = useQuality.subscribe((q, prev) => {
      if (q.applied !== prev.applied) check();
      if (q.assetTier !== prev.assetTier) void applyTier(scene, q.assetTier);
    });
    return offLevel;
  }, [scene, gl]);

  const ground = useMemo(
    () => (scene ? groundAlbedo(scene.manifest) : null),
    [scene],
  );
  if (!scene || !ground) return null;
  return (
    <>
      <Lighting
        sun={scene.manifest.sun}
        ground={ground}
        blockers={scene.blockers}
        nav={scene.nav.data}
      />
      <People scene={scene} />
      {flags.crowd > 0 && (
        <Suspense fallback={null}>
          <CrowdLayer scene={scene} count={flags.crowd} />
        </Suspense>
      )}
      <Player scene={scene} />
      <CameraRig blockers={scene.blockers} />
      <PostFX />
    </>
  );
}
