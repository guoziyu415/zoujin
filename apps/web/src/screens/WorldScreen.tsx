// World screen, F-2b's version: the 3D plaza full screen, a thin loading bar, and with ?dev a panel to move the clock.
// The conversation UI, the clock band and the rest come with F-0 / F-1 (frontend-design 5).
import { Canvas } from "@react-three/fiber";
import { useCallback, useState } from "react";
import { PCFShadowMap } from "three";
import { DevPanel } from "../three/dev/DevPanel";
import { installTestHook } from "../three/dev/testHook";
import { World, type LoadStage } from "../three/World";

const params = new URLSearchParams(location.search);
const DEV = params.has("dev");
if (params.has("test")) installTestHook();

// standard tier (10.6.3 L1): DPR 1.5; F-2c's quality levels move it
const DPR: [number, number] = [1, 1.5];

export default function WorldScreen() {
  const [stage, setStage] = useState<LoadStage>("loading");
  const onStage = useCallback((s: LoadStage) => setStage(s), []);
  return (
    <div style={{ position: "fixed", inset: 0, background: "#14110e" }}>
      <Canvas
        dpr={DPR}
        shadows={{ type: PCFShadowMap }}
        gl={{ antialias: false, powerPreference: "high-performance" }}
        camera={{ fov: 60, near: 0.1, far: 1500 }}
        style={{ touchAction: "none" }}
      >
        <World onStage={onStage} />
      </Canvas>
      {stage === "loading" && <LoadingBar />}
      {stage === "failed" && (
        <div
          role="alert"
          style={{ position: "fixed", inset: 0, background: "#14110e" }}
        />
      )}
      {DEV && <DevPanel stage={stage} />}
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
