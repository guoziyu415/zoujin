// The four quality levels (frontend-design 10.6.3, D-019): ordered by "costs more, shows more". L1 is the standard
// tier every phone gets, L2 / L3 the high tier for phones the probe finds headroom on. Content and colours are the same
// at every level; only sharpness and detail differ (UX art-direction 9.5).
import type { Api } from "@zoujin/contracts";

export type Level = Api.QualityLevel;
export const LEVELS: readonly Level[] = ["L0", "L1", "L2", "L3"];

export type LevelSettings = {
  dpr: number; // device pixel ratio cap; L3 is the device's own, up to 3
  bloom: boolean;
  msaa: 0 | 4;
  shadowMap: 1024 | 2048;
  shadowRadius: number; // PCF radius in texels: 1 reads as a hard edge, 3 soft
  talkModels: number; // conversation-detail people on screen at once (10.6.2)
  hiAssets: boolean; // the high tier's 2048 textures, downloaded in the background
  budgetMs: number; // p95 frame interval this level must hold
};

// budgets sit just above a whole number of 60 Hz refreshes, like the histogram's bounds (data-design 9.3): 34 ms is
// "30 fps holds", 20 ms "60 fps holds"
export const SETTINGS: Record<Level, LevelSettings> = {
  L0: {
    dpr: 1.25,
    bloom: false,
    msaa: 0,
    shadowMap: 1024,
    shadowRadius: 1,
    talkModels: 1,
    hiAssets: false,
    budgetMs: 34,
  },
  L1: {
    dpr: 1.5,
    bloom: true,
    msaa: 4,
    shadowMap: 2048,
    shadowRadius: 1,
    talkModels: 2,
    hiAssets: false,
    budgetMs: 34,
  },
  L2: {
    dpr: 2,
    bloom: true,
    msaa: 4,
    shadowMap: 2048,
    shadowRadius: 3,
    talkModels: 4,
    hiAssets: true,
    budgetMs: 20,
  },
  L3: {
    dpr: 3,
    bloom: true,
    msaa: 4,
    shadowMap: 2048,
    shadowRadius: 3,
    talkModels: 4,
    hiAssets: true,
    budgetMs: 20,
  },
};

// the low-power mode locks Safari at 30 fps: every level is held to the 30 fps budget then (10.6.3 point 4)
export const LOW_POWER_BUDGET_MS = 34;

export const levelIndex = (l: Level): number => LEVELS.indexOf(l);
export const levelAt = (i: number): Level =>
  LEVELS[Math.max(0, Math.min(LEVELS.length - 1, i))]!;

// the pixel ratio a level draws at on this device: never above the screen's own (a 1x desktop screen draws every level
// at 1), never below 1
export function levelDpr(level: Level, deviceDpr: number): number {
  const screen = Math.max(1, deviceDpr);
  return Math.min(SETTINGS[level].dpr, screen);
}

// start level from the probe (10.6.3 point 1): the probe draws at L1's pixel ratio, and the cost scales with the number
// of pixels. Highest level whose estimate fits: L1 within 25 ms, L2 / L3 within 12 ms (an 8 ms share of the frame is
// kept for animation, logic and voice). No measurement: L1.
export const START_LIMIT_MS: Record<Level, number> = {
  L0: Infinity,
  L1: 25,
  L2: 12,
  L3: 12,
};

export function estimateMs(
  probeMs: number,
  level: Level,
  deviceDpr: number,
): number {
  const r = levelDpr(level, deviceDpr) / levelDpr("L1", deviceDpr);
  return probeMs * r * r;
}

export function pickStartLevel(
  probeMs: number | null,
  deviceDpr: number,
): Level {
  if (probeMs === null || !Number.isFinite(probeMs)) return "L1";
  for (let i = LEVELS.length - 1; i > 0; i--) {
    const l = LEVELS[i]!;
    if (estimateMs(probeMs, l, deviceDpr) <= START_LIMIT_MS[l]) return l;
  }
  return "L0";
}
