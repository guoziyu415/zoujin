// The running quality level (frontend-design 10.6.3) and its telemetry (data-design 9.3). The start probe sets the
// first level; once the scene is ready the governor moves it, PostFX feeds it every frame and CameraRig tells it about
// cuts. The 3D components read `useQuality`: the pixel ratio follows `level`, everything else `applied`.
//   ?quality=L0..L3  fixed level, no probe and no governor (the measuring page, comparisons)
//   ?test            fixed L1 so the Playwright checks see the same picture every run; ?test&quality=auto runs it all
//                    (app/flags.ts: window.__zoujinTest counts as ?test, for the checks that go through the app)
import { create } from "zustand";
import { flags } from "../../app/flags";
import { track } from "../../telemetry/telemetry";
import { FrameHistogram } from "./frameHistogram";
import { Governor, type Change } from "./governor";
import {
  estimateMs,
  LEVELS,
  pickStartLevel,
  SETTINGS,
  type Level,
} from "./levels";
import type { ProbeResult } from "./probe";

export type AssetTier = "standard" | "high";

type QualityState = {
  level: Level;
  applied: Level;
  assetTier: AssetTier;
  lowPower: boolean;
  hiReady: boolean; // the high tier's textures are downloaded and can be swapped in at a cut
};

const SAMPLE_EVERY_MS = 10_000; // perf_sample
const HI_MIN_MBPS = 8; // about 1 MB/s measured on the entry pack: slower, stay on the standard textures (10.6.3 point 5)

function fixedFromUrl(): Level | null {
  if (typeof location === "undefined") return null;
  const p = new URLSearchParams(location.search);
  const q = p.get("quality");
  if (q && (LEVELS as readonly string[]).includes(q)) return q as Level;
  return flags.test && q !== "auto" ? "L1" : null;
}

export const fixedLevel = fixedFromUrl();

export const useQuality = create<QualityState>()(() => ({
  level: fixedLevel ?? "L1",
  applied: fixedLevel ?? "L1",
  assetTier: "standard",
  lowPower: false,
  hiReady: false,
}));

const deviceDpr = () =>
  typeof devicePixelRatio === "number" ? devicePixelRatio : 1;

let probe: ProbeResult | null = null;
let gov: Governor | null = null;
let assetMbps: number | null = null;
let begun = false; // the scene is ready (nothing in the background before the entry pack is in)
let probing = false; // the start probe is still measuring: the governor waits for its level
let lastFrame = -1;
let sampleStart = 0;
let longTasks = 0;
let drawCalls = 0;
let dpr = 1;
const hist = new FrameHistogram();

function observeLongTasks(): void {
  if (
    typeof PerformanceObserver === "undefined" ||
    !PerformanceObserver.supportedEntryTypes?.includes("longtask")
  )
    return; // Safari has no long-task entries: it reports 0
  new PerformanceObserver((list) => {
    longTasks += list.getEntries().length;
  }).observe({ type: "longtask", buffered: false });
}

function onChange(c: Change): void {
  // the start event comes from the governor's constructor, before `gov` is set; the level is already in the store
  if (gov)
    useQuality.setState({
      level: gov.level,
      applied: gov.applied,
      lowPower: gov.lowPower,
    });
  const props: {
    from?: Level;
    to: Level;
    reason: Change["reason"];
    probeGpuMs?: number;
    assetMbps?: number;
  } = { to: c.to, reason: c.reason };
  if (c.from) props.from = c.from;
  // rounded so they can't join deviceClass and dpr into a fingerprint (data-design 9.3)
  if (c.reason === "start" && probe)
    props.probeGpuMs = Math.round(probe.gpuMs * 10) / 10;
  if ((c.to === "L2" || c.to === "L3") && assetMbps !== null)
    props.assetMbps = Math.round(assetMbps);
  track("quality_changed", props);
}

function samplePerf(): void {
  const s = useQuality.getState();
  const mem = (performance as { memory?: { usedJSHeapSize: number } }).memory;
  track("perf_sample", {
    frameTimeHistogram: hist.take(),
    longTasks,
    ...(mem ? { jsHeapMb: Math.round(mem.usedJSHeapSize / 2 ** 20) } : {}),
    renderer: "webgl",
    qualityLevel: s.level,
    assetTier: s.assetTier,
    dpr: Math.round(dpr * 100) / 100,
    drawCalls,
    lowPower: s.lowPower,
  });
  longTasks = 0;
}

function startGovernor(now: number): void {
  if (fixedLevel || gov || quality.manual) return;
  gov = new Governor(useQuality.getState().level, now, onChange, (l) =>
    probe ? estimateMs(probe.gpuMs, l, deviceDpr()) : null,
  );
}

// the tier the textures should be on after a cut: high only at L2 / L3 and once downloaded
function wantedTier(): AssetTier {
  const s = useQuality.getState();
  return SETTINGS[s.applied].hiAssets && s.hiReady ? "high" : "standard";
}

export const quality = {
  get probe(): ProbeResult | null {
    return probe;
  },
  get governor(): Governor | null {
    return gov;
  },
  // set by the measuring page: draw every frame this many times (S7's stress)
  stressReps: 1,
  // the measuring page sets the levels itself: no start level from the probe, no governor, high tier fetched at once
  manual: false,

  probeStarted(): void {
    probing = true;
  },

  // the probe finished (null: it could not measure): the first level, usually before anything is on screen
  setProbe(result: ProbeResult | null): void {
    probe = result;
    probing = false;
    if (fixedLevel || gov || quality.manual) return;
    const l = pickStartLevel(result?.gpuMs ?? null, deviceDpr());
    useQuality.setState({ level: l, applied: l });
    if (begun) startGovernor(performance.now()); // the scene was ready first
  },

  // the scene is ready: the governor starts watching, and the start level goes out as quality_changed (reason start)
  begin(now: number, entryMbps: number | null): void {
    assetMbps = entryMbps;
    begun = true;
    sampleStart = now;
    lastFrame = -1;
    observeLongTasks();
    if (!probing) startGovernor(now);
  },

  // every frame, from PostFX: how many times to draw this frame (2 during the governor's stress). `still`: the
  // camera has not moved since the last frame (the governor's stress runs only then)
  frame(now: number, calls: number, pixelRatio: number, still = false): number {
    drawCalls = calls;
    dpr = pixelRatio;
    if (lastFrame >= 0 && sampleStart > 0) {
      const dt = now - lastFrame;
      hist.add(dt);
      gov?.frame(dt, now, still);
      if (now - sampleStart >= SAMPLE_EVERY_MS) {
        sampleStart = now;
        samplePerf();
      }
    }
    lastFrame = now;
    if (quality.stressReps > 1) return quality.stressReps;
    return gov && gov.stressing > 0 ? 2 : 1;
  },

  // a camera cut, or entering / leaving a conversation: deferred settings land, a rise may happen, textures swap
  cut(now: number): void {
    if (gov) {
      gov.cut(now);
      useQuality.setState({ level: gov.level, applied: gov.applied });
    }
    if (!gov?.busy) {
      const t = wantedTier();
      if (t !== useQuality.getState().assetTier)
        useQuality.setState({ assetTier: t });
    }
  },

  // mid-line, a key moment, the act-end page, the ending: no rise and no swapping (10.6.3 point 3)
  setBusy(busy: boolean): void {
    if (gov) gov.busy = busy;
  },

  // whether to download the high tier's textures now (applied at L2 / L3 and the entry pack came fast enough)
  wantsHighTier(): boolean {
    const s = useQuality.getState();
    if (!begun || s.hiReady) return false;
    if (quality.manual) return true;
    return (
      SETTINGS[s.applied].hiAssets &&
      (assetMbps === null || assetMbps >= HI_MIN_MBPS)
    );
  },

  hiDownloaded(): void {
    useQuality.setState({ hiReady: true });
  },

  // the measuring page and the colour check: put a level on at once, everything included; no governor from here on
  force(level: Level, tier: AssetTier = "standard"): void {
    gov = null;
    useQuality.setState({ level, applied: level, assetTier: tier });
  },
};
