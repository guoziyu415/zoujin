// Moves the quality level while the game runs (frontend-design 10.6.3 points 2-4). Pure: the caller feeds frame
// intervals and camera cuts with its own clock, so the unit tests can drive it with made-up frame times.
//
// - Down: every 5 s look at the p95 frame interval; two checks in a row over the level's budget drop one level. Only
//   the pixel ratio follows at once (`level`); shadows, bloom, MSAA, textures and conversation models wait for the
//   next camera cut (`applied`), because a sudden change there is easier to see (UX art-direction 9.5).
// - Up: only at a camera cut or entering / leaving a conversation, never while `busy` (mid-line, a key moment, the
//   act-end page, the ending). Needs 30 s within budget at this level, no drop in the last 60 s, and a 2x stress of 30
//   frames at the cut that still runs at about 60 fps (twice the work in the same time: room for the next level, which
//   costs up to 1.8x). The level goes up at the next cut, so nothing changes mid-shot. One level at a time.
// - Two drops in a run lock the ceiling where it is (most likely heat).
// - Low-power mode: Safari locks at 30 fps; a steady 33 ms while the probe says the GPU has room. Every level is then
//   held to the 30 fps budget and nothing goes up.
import {
  LOW_POWER_BUDGET_MS,
  SETTINGS,
  levelAt,
  levelIndex,
  type Level,
} from "./levels";

export type ChangeReason = "start" | "down" | "up" | "lowPower" | "locked";
// quality_changed (data-design 9.3) without the measurements the telemetry adds. `lowPower` and `locked` keep the
// level (from = to): they mark a change in the rules, so the last event's `to` is always the level the run is at
export type Change = { from?: Level; to: Level; reason: ChangeReason };

export const CHECK_EVERY_MS = 5000;
export const OVER_CHECKS_TO_DROP = 2;
export const OK_CHECKS_TO_RISE = 6; // 6 x 5 s = the last 30 s
export const NO_RISE_AFTER_DROP_MS = 60_000;
export const DROPS_TO_LOCK = 2;
export const STRESS_FRAMES = 30;
export const STRESS_PASS_MS = 19; // "still about 16.7 ms": one 60 Hz refresh plus the jitter, not two
const MIN_FRAMES = 5; // fewer in a window: the page was hidden or stalled, skip the check
const GAP_MS = 1000; // a longer interval is the page coming back from the background, not a slow frame

const percentile = (sorted: number[], p: number): number =>
  sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))]!;

export class Governor {
  level: Level; // the pixel ratio follows this at once
  applied: Level; // everything else, changed only at a cut
  lowPower = false;
  locked = false;
  ceiling: Level = "L3";
  busy = false;
  // frames of 2x stress still to draw: the renderer draws each frame twice while this is above 0
  stressing = 0;
  private window: number[] = [];
  private windowStart: number;
  private overRun = 0;
  private okRun = 0;
  private drops = 0;
  private lastDrop = -Infinity;
  private risePassed = false;
  private stressed: number[] = [];

  constructor(
    start: Level,
    now: number,
    private readonly emit: (c: Change) => void,
    // the probe's GPU time scaled to a level, or null without a probe: tells a 30 fps lock from a slow GPU
    private readonly gpuEstimate: (l: Level) => number | null = () => null,
  ) {
    this.level = start;
    this.applied = start;
    this.windowStart = now;
    emit({ to: start, reason: "start" });
  }

  get budgetMs(): number {
    return this.lowPower ? LOW_POWER_BUDGET_MS : SETTINGS[this.level].budgetMs;
  }

  frame(intervalMs: number, now: number): void {
    if (intervalMs > GAP_MS) {
      this.window = [];
      this.windowStart = now;
      return;
    }
    if (this.stressing > 0) {
      this.stressed.push(intervalMs);
      if (--this.stressing === 0) this.judgeStress();
      return; // doubled frames say nothing about the level's own cost
    }
    this.window.push(intervalMs);
    if (now - this.windowStart >= CHECK_EVERY_MS) this.check(now);
  }

  // a camera cut, or entering / leaving a conversation
  cut(now: number): void {
    if (this.busy) return;
    if (this.applied !== this.level) {
      this.applied = this.level; // the drop's other settings
      return;
    }
    if (!this.mayRise(now)) return;
    if (this.risePassed) {
      const from = this.level;
      this.level = this.applied = levelAt(levelIndex(from) + 1);
      this.okRun = 0;
      this.risePassed = false;
      this.emit({ from, to: this.level, reason: "up" });
    } else if (this.stressing === 0) {
      this.stressed = [];
      this.stressing = STRESS_FRAMES + 1; // the first interval still belongs to the frame before the stress
    }
  }

  private mayRise(now: number): boolean {
    return (
      !this.lowPower &&
      !this.locked &&
      levelIndex(this.level) < levelIndex(this.ceiling) &&
      now - this.lastDrop >= NO_RISE_AFTER_DROP_MS &&
      this.okRun >= OK_CHECKS_TO_RISE
    );
  }

  private judgeStress(): void {
    const s = this.stressed.slice(1);
    const mean = s.reduce((a, b) => a + b, 0) / Math.max(1, s.length);
    this.risePassed = s.length > 0 && mean <= STRESS_PASS_MS;
  }

  private check(now: number): void {
    const w = this.window;
    this.window = [];
    // on a 5 s grid, so the checks don't drift later by a frame each time; a stall longer than that starts afresh
    this.windowStart += CHECK_EVERY_MS;
    if (now - this.windowStart >= CHECK_EVERY_MS) this.windowStart = now;
    if (w.length < MIN_FRAMES) return;
    const sorted = [...w].sort((a, b) => a - b);
    const p50 = percentile(sorted, 0.5);
    if (!this.lowPower && this.lockedAt30(sorted, p50)) {
      this.lowPower = true;
      this.risePassed = false;
      this.emit({ from: this.level, to: this.level, reason: "lowPower" });
    } else if (this.lowPower && p50 <= SETTINGS.L2.budgetMs) {
      this.lowPower = false; // back at 60 fps (plugged in, or the mode switched off)
    }
    if (percentile(sorted, 0.95) > this.budgetMs) {
      this.okRun = 0;
      this.risePassed = false;
      if (++this.overRun >= OVER_CHECKS_TO_DROP && this.level !== "L0")
        this.drop(now);
    } else {
      this.overRun = 0;
      this.okRun++;
    }
  }

  // steady at two refreshes (33.3 ms) while the GPU would manage 60 fps at this level
  private lockedAt30(sorted: number[], p50: number): boolean {
    const gpu = this.gpuEstimate(this.level);
    return (
      gpu !== null &&
      gpu <= 12 &&
      p50 >= 31 &&
      p50 <= 36 &&
      percentile(sorted, 0.1) >= 29 &&
      percentile(sorted, 0.9) <= 38
    );
  }

  private drop(now: number): void {
    const from = this.level;
    this.level = levelAt(levelIndex(from) - 1);
    this.overRun = 0;
    this.drops++;
    this.lastDrop = now;
    this.emit({ from, to: this.level, reason: "down" });
    if (this.drops >= DROPS_TO_LOCK && !this.locked) {
      this.locked = true;
      this.ceiling = this.level;
      this.emit({ from: this.level, to: this.level, reason: "locked" });
    }
  }
}
