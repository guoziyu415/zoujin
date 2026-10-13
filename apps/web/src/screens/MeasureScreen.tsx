// The measuring page (F-2 range 6; ?measure, or the claude.ai private page scripts/measure_artifact.mjs packs): the
// start probe as the game runs it, then the plaza at each quality level L0-L3 with S7's method, so S4, S5 and older
// iPhones can be measured the same way. Per level: 6.5 s walking S7's route (frame intervals), then at one fixed pose
// the same frame drawn 2, 4, 8, 16, 32 times until the interval reaches 45 ms: one frame's GPU time ~ interval / draws
// (frontend-design 10.6.5). Then the bloom check UX asked for (PR #46): L0 against L1 at 18:45 looking at the west gate
// (the sun in the gateway) and at night by a fire, as pictures. Inside the claude.ai page a button saves the numbers
// and the pictures into the page itself (its db and assets), so the team reads them there. For the team; the text
// is English / Japanese like the dev panel.
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useCallback, useEffect, useRef, useState } from "react";
import { Color, PCFShadowMap, type WebGLRenderer } from "three";
import { sandbox, startSandbox } from "../three/dev/sandbox";
import { lighting } from "../three/Lighting";
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

startSandbox(); // no story here: the plaza's world is a local one (three/dev/sandbox.ts)

quality.manual = true; // the page sets the levels itself; no governor

const VSYNC = 1000 / 60;
const STEPS = [2, 4, 8, 16, 32];
const ROUTE_MS = 6500;

type Plan = [number, number, number]; // layout.json plan x, y and height
// UX, PR #46: does L0 (no bloom, no MSAA) turn the sun into a hard white disc, and how does a fire read at night. The
// plaza has no fire yet: a stand-in, a hot little ball and a warm point light (only on this page)
const FIRE: Plan = [13.0, -2.6, 2.0]; // by the foot of the castle steps, a held torch's height
type Look = {
  name: string;
  t: number;
  from: Plan;
  to: Plan;
  fov: number;
  fire: boolean;
};
const LOOKS: Look[] = [
  // the sun sets along the gate street (ux/slice/ending-shots.md, shot 2). UX asked for 19:00, but by then it is on the
  // horizon behind the far ground; at 18:45 it is 2.8° up, inside the gateway seen from here on its line
  {
    name: "sunset-gate",
    t: 1125,
    from: [4, 1.3, 1.65],
    to: [-31, 0, 2.6],
    fov: 50,
    fire: false,
  },
  {
    name: "night-fire",
    t: 1260,
    from: [7.0, -4.5, 1.65], // south of the platform, the castle steps behind the fire
    to: [13.0, -2.6, 1.7],
    fov: 55,
    fire: true,
  },
];
const LOOK_LEVELS: Level[] = ["L0", "L1"];
// ?measure&looks: only the pictures, no timing (a quick check of the looks)
const ONLY_LOOKS =
  typeof location !== "undefined" &&
  new URLSearchParams(location.search).has("looks");

type Shot = { look: string; level: Level; url: string };

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
  capture: null as ((url: string) => void) | null, // the next frame as a JPEG, read right after PostFX drew it
};

// after PostFX's render (priority 1), in the same frame: the drawing buffer still holds the picture
function Capturer() {
  const { gl } = useThree();
  useFrame(() => {
    const done = rec.capture;
    if (!done) return;
    rec.capture = null;
    done(gl.domElement.toDataURL("image/jpeg", 0.85));
  }, 2);
  return null;
}

function FireStandIn({ on }: { on: boolean }) {
  if (!on) return null;
  const at = planToWorld(...FIRE, loadInfo.sceneRotationDeg);
  return (
    <group position={at}>
      <mesh>
        <sphereGeometry args={[0.07, 16, 12]} />
        {/* luminance about 5, over the bloom threshold (3.0), like a flame against the night */}
        <meshBasicMaterial
          color={new Color(1, 0.45, 0.12).multiplyScalar(10)}
        />
      </mesh>
      <pointLight color="#ffa458" intensity={25} distance={15} decay={2} />
    </group>
  );
}

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
  onMsg(
    `${level}: switching level, waiting for shaders and shadows / 段階を切り替え、シェーダーと影を待機中`,
  );
  rec.route = true;
  rec.t = -2;
  await sleep(2000);
  onMsg(`${level}: walking S7's route for 6.5 s / S7 のルートを 6.5 秒歩行中`);
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
    onMsg(`${level}: stress ×${n} / 負荷 ×${n}`);
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

const capture = () =>
  new Promise<string>((resolve) => {
    rec.capture = resolve;
  });

// the bloom check: each look at L0 and L1, one picture each (no timing: the fire's light recompiles the materials)
async function shootLooks(
  onMsg: (s: string) => void,
  setFire: (on: boolean) => void,
): Promise<Shot[]> {
  const shots: Shot[] = [];
  const rot = loadInfo.sceneRotationDeg;
  for (const look of LOOKS) {
    sandbox.setClock(look.t);
    lighting.settle();
    setFire(look.fire);
    rig.fixedView = {
      from: planToWorld(...look.from, rot),
      to: planToWorld(...look.to, rot),
      fov: look.fov,
    };
    for (const level of LOOK_LEVELS) {
      quality.force(level);
      onMsg(`Bloom / ブルーム: ${look.name} ${level}`);
      await sleep(2500);
      shots.push({ look: look.name, level, url: await capture() });
    }
  }
  setFire(false);
  sandbox.setClock(1050);
  lighting.settle();
  return shots;
}

function Runner({
  go,
  onMsg,
  onDone,
  setFire,
}: {
  go: number;
  onMsg: (s: string) => void;
  onDone: (rows: Row[], env: ReturnType<typeof envInfo>, shots: Shot[]) => void;
  setFire: (on: boolean) => void;
}) {
  const { gl } = useThree();
  useEffect(() => {
    if (!go) return;
    let alive = true;
    (async () => {
      const rows: Row[] = [];
      for (const l of ONLY_LOOKS ? [] : LEVELS) {
        if (!alive) return;
        rows.push(await measureLevel(l, onMsg));
      }
      const shots = alive ? await shootLooks(onMsg, setFire) : [];
      quality.force("L1");
      rig.fixedView = null;
      if (alive) onDone(rows, envInfo(gl), shots);
    })();
    return () => {
      alive = false;
    };
  }, [go, gl, onMsg, onDone, setFire]);
  return null;
}

// Inside the claude.ai page (measure_artifact.mjs), declared with the db and assets capabilities: the pictures go to
// the page's assets and one document per run to its db (runs/<id>), so the team reads them without copying anything
type ClaudeHost = { use?: (name: string) => Promise<unknown> };
type Db = {
  collection: (p: string) => {
    doc: () => { id: string; set: (d: object) => Promise<void> };
  };
};
type Assets = {
  upload: (b: Blob, o?: { type?: string }) => Promise<{ id: string }>;
};
const host = () => (window as { claude?: ClaudeHost }).claude;
const canSave = () => !!host()?.use;

function jpegBlob(url: string): Blob {
  const bin = atob(url.slice(url.indexOf(",") + 1));
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Blob([bytes], { type: "image/jpeg" });
}

// pictures already uploaded, by "{look}-{level}": pressing save again after a failure doesn't upload them twice
const uploaded: Record<string, string> = {};

// the run's id, and whether the pictures went too (`pictures: null` in the run when the page's assets are out of reach)
async function saveRun(
  result: object,
  shots: Shot[],
): Promise<{ id: string; pictures: boolean }> {
  const use = host()?.use;
  if (!use) throw new Error("Not inside a claude.ai page / claude.ai のページ内ではありません");
  const db = (await use("db")) as Db | null;
  const assets = (await use("assets")) as Assets | null;
  if (!db) throw new Error("The page database is unavailable / ページのデータベースが使えません");
  if (assets)
    for (const s of shots) {
      const key = `${s.look}-${s.level}`;
      uploaded[key] ??= (
        await assets.upload(jpegBlob(s.url), { type: "image/jpeg" })
      ).id;
    }
  const ref = db.collection("runs").doc();
  await ref.set({ ...result, pictures: assets ? { ...uploaded } : null });
  return { id: ref.id, pictures: !!assets };
}

const NOT_SAVED = "Not saved";

function errorText(e: unknown): string {
  const { code, message } = (e ?? {}) as { code?: string; message?: string };
  return code ?? message ?? String(e);
}

export default function MeasureScreen() {
  const [stage, setStage] = useState<LoadStage>("loading");
  const [go, setGo] = useState(0);
  const [msg, setMsg] = useState(
    "Loading the plaza and running the start-level probe… / 広場を読み込み、開始段階の自己テストを実行中…",
  );
  const [result, setResult] = useState<string>("");
  const [rows, setRows] = useState<Row[]>([]);
  const [shots, setShots] = useState<Shot[]>([]);
  const [fire, setFire] = useState(false);
  const [saved, setSaved] = useState("");
  const level = useQuality((s) => s.level);
  const hiReady = useQuality((s) => s.hiReady);
  const t0 = useRef(new Date().toISOString());
  const onStage = useCallback((s: LoadStage) => {
    setStage(s);
    if (s === "ready") setMsg("The plaza is ready. / 広場の準備ができました。");
    if (s === "failed") setMsg(`Loading failed / 読み込み失敗: ${loadInfo.error}`);
  }, []);
  const onDone = useCallback(
    (r: Row[], env: ReturnType<typeof envInfo>, pics: Shot[]) => {
      setRows(r);
      setShots(pics);
      setMsg(
        canSave()
          ? "Done. Tap \"Save results\" and the frontend can read them on this page. / 完了。「結果を保存」を押せば、フロントエンドがこのページで読めます。"
          : "Done. Copy the results below and send them to the frontend. / 完了。下の結果をコピーしてフロントエンドに送ってください。",
      );
      const probe = quality.probe;
      setResult(
        JSON.stringify(
          {
            page: "zoujin-measure",
            version: 2,
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
            looks: pics.map((p) => ({ look: p.look, level: p.level })),
          },
          null,
          1,
        ),
      );
    },
    [],
  );
  const onSave = useCallback(() => {
    setSaved("Saving… / 保存中…");
    saveRun(JSON.parse(result) as object, shots).then(
      ({ id, pictures }) =>
        setSaved(
          pictures
            ? `Saved (runs/${id}); just tell the frontend the run is done. / 保存しました（runs/${id}）。フロントエンドに完了を伝えるだけで大丈夫です。`
            : `Numbers saved (runs/${id}), pictures not saved (this page's image storage is unavailable); just tell the frontend the run is done. / 数値は保存しました（runs/${id}）が、画像は保存できませんでした（このページの画像ストレージが使えません）。フロントエンドに完了を伝えるだけで大丈夫です。`,
        ),
      (e: unknown) =>
        setSaved(
          `${NOT_SAVED}: ${errorText(e)}. Tap "Copy results" and send them to the frontend. / 保存できませんでした：${errorText(e)}。「結果をコピー」を押してフロントエンドに送ってください。`,
        ),
    );
  }, [result, shots]);
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
        <Capturer />
        <FireStandIn on={fire} />
        <Runner go={go} onMsg={setMsg} onDone={onDone} setFire={setFire} />
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
          Measuring page / 計測ページ · {stage} · now / 現在 {level}
          {hiReady
            ? " · high-tier textures loaded / 高品質テクスチャ取得済み"
            : ""}
        </div>
        <div>
          Start-level probe / 開始段階の自己テスト:{" "}
          {probe
            ? `${probe.gpuMs.toFixed(1)} ms（${probe.bound}，×${probe.reps}，${probe.ms} ms）→ ${pickStartLevel(probe.gpuMs, devicePixelRatio)}`
            : "……"}
        </div>
        <div>{msg}</div>
        {stage === "ready" && !hiReady && !go && <div>Loading high-tier textures… / 高品質テクスチャを取得中…</div>}
        {stage === "ready" && hiReady && !go && (
          <button
            style={{ font: "inherit", margin: "6px 0" }}
            onClick={() => setGo(1)}
          >
            Start measuring (about 1-2 minutes; keep the phone unlocked and stay on this page) / 計測開始（約 1〜2 分。スマホをロックせず、他のアプリに切り替えないでください）
          </button>
        )}
        {rows.length > 0 && (
          <table style={{ borderCollapse: "collapse", margin: "6px 0" }}>
            <thead>
              <tr>
                {["Level / 段階", "DPR", "p50", "p95", "Jank% / コマ落ち%", "draw", "GPU ms"].map(
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
        {shots.length > 0 && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 4,
              margin: "6px 0",
            }}
          >
            {shots.map((p) => (
              <figure key={`${p.look}-${p.level}`} style={{ margin: 0 }}>
                <img src={p.url} alt="" style={{ width: "100%" }} />
                <figcaption>
                  {p.look === "sunset-gate"
                    ? "18:45 west gate / 西門"
                    : "Firelight at night (stand-in) / 夜の火明かり（代役）"}{" "}
                  {p.level}
                </figcaption>
              </figure>
            ))}
          </div>
        )}
        {result && canSave() && (
          <div>
            <button
              style={{ font: "inherit", margin: "6px 0" }}
              disabled={saved !== "" && !saved.startsWith(NOT_SAVED)}
              onClick={onSave}
            >
              Save results (numbers and 4 pictures go into this page) / 結果を保存（数値と画像 4 枚をこのページに保存）
            </button>
            {saved && <div>{saved}</div>}
          </div>
        )}
        {result && (
          <>
            <button
              style={{ font: "inherit" }}
              onClick={() => void navigator.clipboard?.writeText(result)}
            >
              Copy results / 結果をコピー
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
