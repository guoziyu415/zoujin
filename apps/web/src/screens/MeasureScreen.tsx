// The measuring page (F-2 range 6; ?measure, or the claude.ai private page scripts/measure_artifact.mjs packs): the
// start probe as the game runs it, then the plaza at each quality level L0-L3 with S7's method, so S4, S5 and older
// iPhones can be measured the same way. Per level: 6.5 s walking S7's route (frame intervals), then at one fixed pose
// the same frame drawn 2, 4, 8, 16, 32 times until the interval reaches 45 ms: one frame's GPU time ~ interval / draws
// (frontend-design 10.6.5). For the team; the words are Chinese like the dev panel.
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useCallback, useEffect, useRef, useState } from "react";
import { PCFShadowMap, type WebGLRenderer } from "three";
import { frameStats } from "../three/PostFX";
import {
  levelDpr,
  LEVELS,
  pickStartLevel,
  SETTINGS,
  type Level,
} from "../three/quality/levels";
import { QualityProbe } from "../three/quality/QualityProbe";
import { quality, useQuality } from "../three/quality/quality";
import { rig } from "../three/rig";
import { planToWorld, type Vec3 } from "../three/scene/frame";
import { loadInfo, World, type LoadStage } from "../three/World";

quality.manual = true; // the page sets the levels itself; no governor

const VSYNC = 1000 / 60;
const STEPS = [2, 4, 8, 16, 32];
const ROUTE_MS = 6500;

type Row = {
  level: Level;
  dpr: number;
  assetTier: string;
  frames: number;
  p50: number;
  p95: number;
  p99: number;
  jankPct: number; // frames over 34 ms
  drawCalls: number;
  tris: number;
  gpuMs: number | null; // null: still at 60 fps with 32 draws (then <= gpuHi)
  gpuLo: number;
  gpuHi: number;
  bound: "gpu" | "cpu" | "under";
  steps: { n: number; tMean: number }[];
};

const pct = (a: number[], p: number) => {
  const s = [...a].sort((x, y) => x - y);
  return s[Math.min(s.length - 1, Math.floor(p * s.length))] ?? 0;
};
const trimMean = (a: number[]) => {
  const s = [...a].sort((x, y) => x - y);
  const k = Math.floor(s.length * 0.05);
  const m = s.slice(k, s.length - k || undefined);
  return m.reduce((x, y) => x + y, 0) / Math.max(1, m.length);
};
const r1 = (x: number) => Math.round(x * 10) / 10;
const r2 = (x: number) => Math.round(x * 100) / 100;

// S7's route: round the plaza's middle at 10.5 m, eye height, looking ahead and out (S7 page benchPose)
function routeView(t: number): { from: Vec3; to: Vec3; fov: number } {
  const rot = loadInfo.sceneRotationDeg;
  const a = -1.9 + t * 0.075;
  return {
    from: planToWorld(Math.cos(a) * 10.5, 2 + Math.sin(a) * 10.5, 1.65, rot),
    to: planToWorld(
      Math.cos(a + 0.9) * 22,
      2 + Math.sin(a + 0.9) * 22,
      3.2,
      rot,
    ),
    fov: 58,
  };
}

function envInfo(gl: WebGLRenderer) {
  const c = gl.getContext();
  const ext = c.getExtension("WEBGL_debug_renderer_info");
  return {
    ua: navigator.userAgent,
    dpr: devicePixelRatio,
    screen: [screen.width, screen.height],
    inner: [innerWidth, innerHeight],
    gpu: ext
      ? c.getParameter(ext.UNMASKED_RENDERER_WEBGL)
      : c.getParameter(c.RENDERER),
    maxTex: c.getParameter(c.MAX_TEXTURE_SIZE),
  };
}

// the frame loop's side of the measurement: records intervals into whatever the runner asks for
const rec = {
  intervals: null as number[] | null,
  last: -1,
  t: 0, // seconds along the route
  route: false,
};

function Recorder() {
  useFrame((_, dt) => {
    const now = performance.now();
    if (rec.route) {
      rec.t += Math.min(dt, 0.05);
      rig.fixedView = routeView(Math.max(0, rec.t));
    }
    if (rec.intervals && rec.last >= 0) rec.intervals.push(now - rec.last);
    rec.last = now;
  }, 0);
  return null;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const record = async (ms: number, maxFrames = Infinity) => {
  rec.intervals = [];
  const t0 = performance.now();
  while (performance.now() - t0 < ms && rec.intervals.length < maxFrames)
    await sleep(50);
  const out = rec.intervals;
  rec.intervals = null;
  return out;
};

async function measureLevel(
  level: Level,
  onMsg: (s: string) => void,
): Promise<Row> {
  const tier =
    SETTINGS[level].hiAssets && useQuality.getState().hiReady
      ? "high"
      : "standard";
  quality.force(level, tier);
  onMsg(`${level}：换档，等着色器和阴影`);
  rec.route = true;
  rec.t = -2;
  await sleep(2000);
  onMsg(`${level}：沿 S7 的路线走 6.5 秒`);
  const calls0 = frameStats.calls;
  const ft = await record(ROUTE_MS);
  const drawCalls = Math.max(calls0, frameStats.calls);
  const tris = frameStats.triangles;
  rec.route = false;
  rig.fixedView = routeView(5); // S7's stress pose
  const steps: Row["steps"] = [];
  let last = { n: 1, tMean: VSYNC };
  for (const n of STEPS) {
    quality.stressReps = n;
    onMsg(`${level}：加压 ×${n}`);
    await record(600, 6);
    const q = await record(2500, 30);
    last = { n, tMean: r1(trimMean(q)) };
    steps.push(last);
    if (last.tMean >= 45) break;
  }
  quality.stressReps = 1;
  const under = last.tMean < VSYNC * 1.25;
  const gpuHi = last.tMean / last.n;
  const gpuLo = Math.max(0, last.tMean - VSYNC) / last.n;
  return {
    level,
    dpr: levelDpr(level, devicePixelRatio),
    assetTier: tier,
    frames: ft.length,
    p50: r1(pct(ft, 0.5)),
    p95: r1(pct(ft, 0.95)),
    p99: r1(pct(ft, 0.99)),
    jankPct: r1(
      (100 * ft.filter((x) => x > 34).length) / Math.max(1, ft.length),
    ),
    drawCalls,
    tris,
    gpuMs: under ? null : r2((gpuHi + gpuLo) / 2),
    gpuLo: r2(gpuLo),
    gpuHi: r2(gpuHi),
    bound: under ? "under" : "gpu",
    steps,
  };
}

function Runner({
  go,
  onMsg,
  onDone,
}: {
  go: number;
  onMsg: (s: string) => void;
  onDone: (rows: Row[], env: ReturnType<typeof envInfo>) => void;
}) {
  const { gl } = useThree();
  useEffect(() => {
    if (!go) return;
    let alive = true;
    (async () => {
      const rows: Row[] = [];
      for (const l of LEVELS) {
        if (!alive) return;
        rows.push(await measureLevel(l, onMsg));
      }
      quality.force("L1");
      rig.fixedView = null;
      if (alive) onDone(rows, envInfo(gl));
    })();
    return () => {
      alive = false;
    };
  }, [go, gl, onMsg, onDone]);
  return null;
}

export default function MeasureScreen() {
  const [stage, setStage] = useState<LoadStage>("loading");
  const [go, setGo] = useState(0);
  const [msg, setMsg] = useState("加载广场，同时跑起始档自测……");
  const [result, setResult] = useState<string>("");
  const [rows, setRows] = useState<Row[]>([]);
  const level = useQuality((s) => s.level);
  const hiReady = useQuality((s) => s.hiReady);
  const t0 = useRef(new Date().toISOString());
  const onStage = useCallback((s: LoadStage) => {
    setStage(s);
    if (s === "ready") setMsg("广场好了。");
    if (s === "failed") setMsg(`加载失败：${loadInfo.error}`);
  }, []);
  const onDone = useCallback((r: Row[], env: ReturnType<typeof envInfo>) => {
    setRows(r);
    setMsg("完成。把下面的结果复制给前端。");
    const probe = quality.probe;
    setResult(
      JSON.stringify(
        {
          page: "zoujin-measure",
          version: 1,
          at: t0.current,
          env,
          scene: {
            id: "scene.syracuse-square",
            entryMbps: r1(loadInfo.entryMbps),
            readyMs: loadInfo.readyMs,
          },
          probe: probe && {
            ...probe,
            startLevel: pickStartLevel(probe.gpuMs, devicePixelRatio),
          },
          levels: r,
        },
        null,
        1,
      ),
    );
  }, []);
  const probe = quality.probe;

  return (
    <div style={{ position: "fixed", inset: 0, background: "#14110e" }}>
      <Canvas
        dpr={levelDpr(level, devicePixelRatio)}
        shadows={{ type: PCFShadowMap }}
        gl={{ antialias: false, powerPreference: "high-performance" }}
        camera={{ fov: 60, near: 0.1, far: 1500 }}
        style={{ touchAction: "none" }}
      >
        <QualityProbe />
        <World onStage={onStage} />
        <Recorder />
        <Runner go={go} onMsg={setMsg} onDone={onDone} />
      </Canvas>
      <div
        style={{
          position: "fixed",
          left: 8,
          right: 8,
          bottom: "max(8px, env(safe-area-inset-bottom))",
          maxHeight: "55%",
          overflow: "auto",
          padding: "8px 10px",
          borderRadius: 8,
          background: "rgba(0,0,0,.72)",
          color: "#f1e9d8",
          font: "12px/1.45 ui-monospace, Menlo, monospace",
        }}
      >
        <div>
          计测页 · {stage} · 现在 {level}
          {hiReady ? " · 高档贴图已下" : ""}
        </div>
        <div>
          起始档自测：
          {probe
            ? `${probe.gpuMs.toFixed(1)} ms（${probe.bound}，×${probe.reps}，${probe.ms} ms）→ ${pickStartLevel(probe.gpuMs, devicePixelRatio)}`
            : "……"}
        </div>
        <div>{msg}</div>
        {stage === "ready" && !hiReady && !go && <div>下高档贴图……</div>}
        {stage === "ready" && hiReady && !go && (
          <button
            style={{ font: "inherit", margin: "6px 0" }}
            onClick={() => setGo(1)}
          >
            开始计测（约 1〜2 分钟，手机别锁屏、别切走）
          </button>
        )}
        {rows.length > 0 && (
          <table style={{ borderCollapse: "collapse", margin: "6px 0" }}>
            <thead>
              <tr>
                {["档", "DPR", "p50", "p95", "掉帧%", "draw", "GPU ms"].map(
                  (h) => (
                    <th key={h} style={{ textAlign: "right", paddingRight: 8 }}>
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.level}>
                  {[
                    r.level,
                    r.dpr,
                    r.p50,
                    r.p95,
                    r.jankPct,
                    r.drawCalls,
                    r.gpuMs === null ? `≤${r.gpuHi}` : r.gpuMs,
                  ].map((v, i) => (
                    <td key={i} style={{ textAlign: "right", paddingRight: 8 }}>
                      {v}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {result && (
          <>
            <button
              style={{ font: "inherit" }}
              onClick={() => void navigator.clipboard?.writeText(result)}
            >
              复制结果
            </button>
            <textarea
              readOnly
              value={result}
              style={{
                display: "block",
                width: "100%",
                height: 120,
                marginTop: 6,
                font: "inherit",
              }}
              onFocus={(e) => e.currentTarget.select()}
            />
          </>
        )}
      </div>
    </div>
  );
}
