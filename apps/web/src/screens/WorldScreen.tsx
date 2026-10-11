// The 3D chunk's way in (frontend-design 4, 5): the scene full size with a thin loading bar. Under the play screen's
// HUD (`embedded`) it shows the story's world from the stores; on its own (?world, ?dev) it is the team's sandbox with
// a local world (three/dev/sandbox.ts) and with ?dev a panel to move the clock. ?test adds the e2e hook either way.
// The team's tools (the panel, the sandbox world, the test hook) are chunks of their own: players don't download them.
import { Canvas } from "@react-three/fiber";
import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { PCFShadowMap } from "three";
import { flags } from "../app/flags";
import { levelDpr } from "../three/quality/levels";
import { QualityProbe } from "../three/quality/QualityProbe";
import { useQuality } from "../three/quality/quality";
import { selectCovered, useStory } from "../stores/story";
import { useVoice } from "../stores/voice";
import { World, type LoadStage, type ScenePacks } from "../three/World";
import { useUi } from "../stores/ui";

const DEV = new URLSearchParams(location.search).has("dev");
const DevPanel = lazy(() =>
  import("../three/dev/DevPanel").then((m) => ({ default: m.DevPanel })),
);
if (flags.test)
  void import("../three/dev/testHook").then((m) => m.installTestHook());

export default function WorldScreen({
  embedded = false,
  packs,
}: {
  embedded?: boolean;
  packs?: ScenePacks | undefined;
}) {
  useEffect(() => {
    if (!embedded)
      void import("../three/dev/sandbox").then((m) => m.startSandbox());
  }, [embedded]);
  const [stage, setStage] = useState<LoadStage>("loading");
  const onStage = useCallback((s: LoadStage) => {
    setStage(s);
    useUi.setState({ scene: s });
  }, []);
  // the pixel ratio follows the quality level at once (10.6.3): L0 1.25, L1 1.5, L2 2, L3 the screen's own
  const level = useQuality((s) => s.level);
  // a story page or the safety card over the world: the render loop stops and the canvas keeps its last frame (10.4),
  // less heat and battery. Loading goes on behind it (its own animation frames); the governor skips the gap.
  const covered = useStory(selectCovered);
  const paused = useVoice((s) => s.paused);
  return (
    <div
      style={{
        position: embedded ? "absolute" : "fixed",
        inset: 0,
        background: "#14110e",
      }}
    >
      <Canvas
        frameloop={embedded && (covered || paused) ? "never" : "always"}
        dpr={levelDpr(level, devicePixelRatio)}
        shadows={{ type: PCFShadowMap }}
        gl={{ antialias: false, powerPreference: "high-performance" }}
        camera={{ fov: 60, near: 0.1, far: 1500 }}
        style={{ touchAction: "none" }}
      >
        <QualityProbe />
        <World onStage={onStage} packs={packs} />
      </Canvas>
      {stage === "loading" && <LoadingBar />}
      {stage === "failed" && (
        <div
          role="alert"
          style={{ position: "fixed", inset: 0, background: "#14110e" }}
        />
      )}
      {DEV && !embedded && (
        <Suspense fallback={null}>
          <DevPanel stage={stage} />
        </Suspense>
      )}
    </div>
  );
}

// placeholder until UX's opening animation (10.2); no words, so no copy to decide yet
function LoadingBar() {
  return (
    <div
      style={{
        position: "fixed",
        left: 0,
        right: 0,
        bottom: 0,
        height: 3,
        background: "rgba(241,233,216,.15)",
      }}
    >
      <div
        style={{
          height: "100%",
          width: "30%",
          background: "#e0a65a",
          animation: "zjload 1.2s ease-in-out infinite alternate",
        }}
      />
      <style>
        {"@keyframes zjload{from{margin-left:0}to{margin-left:70%}}"}
      </style>
    </div>
  );
}
