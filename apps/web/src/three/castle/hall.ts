// The lamp-lit room's arithmetic (F-14, ux/scenes/castle.md 3): is the camera in the hall (with a margin either way,
// so standing on the threshold doesn't flip it every frame), the ~1 s ease across the threshold, the exposure the hall
// wants, when the courtyard's braziers burn, the lamps' flicker. HallLight.tsx applies them.
import { sunLook } from "../sun";

export type Box = { min: readonly number[]; max: readonly number[] };

const MARGIN = 0.3; // metres past the wall line before the camera counts as in (or out)

export function insideHall(
  p: readonly number[],
  box: Box,
  wasIn: boolean,
): boolean {
  const m = wasIn ? -MARGIN : MARGIN; // in: leave only 0.3 m outside; out: enter only 0.3 m inside
  for (let i = 0; i < 3; i++)
    if (p[i]! < box.min[i]! + m || p[i]! > box.max[i]! - m) return false;
  return true;
}

// first-order ease: about 95 % of the way in 1 s (the eye adapting, castle.md 3; frontend #52 ②)
export function ease(
  cur: number,
  target: number,
  dt: number,
  tau = 0.33,
): number {
  return target + (cur - target) * Math.exp(-Math.max(0, dt) / tau);
}

// the hall is lit by its lamps alone, day or night: its exposure is the night's (the lamps were set for it), so by day
// stepping in opens up by that much over the day's exposure, and at night nothing changes
// (worked out on first use, not at load: village/ imports this module too, and in the production build sun.ts may not
// be initialised yet when this chunk first runs)
let hallExposure: number | null = null;
export const HALL_EXPOSURE = (): number =>
  (hallExposure ??= sunLook(-20).exposure);

export function zoneExposure(dayExposure: number, inHall: number): number {
  const ratio = Math.max(1, HALL_EXPOSURE() / Math.max(dayExposure, 1e-3));
  return 1 + (ratio - 1) * inHall;
}

// the courtyard's braziers: lit from sunset (the sun's height as the y of its direction), full once it is down
export function lampsOutside(sunY: number): number {
  return Math.min(1, Math.max(0, (0.06 - sunY) / 0.1));
}

// slow and quick wavering, a few per cent: the baked light's brightness and the flames (castle.md 5.2, frontend)
export function flicker(t: number, seed: number): number {
  return (
    1 +
    0.025 * Math.sin(t * 2.3 + seed * 1.7) +
    0.015 * Math.sin(t * 7.1 + seed * 4.3) +
    0.01 * Math.sin(t * 13.7 + seed * 2.9)
  );
}
