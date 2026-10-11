// The village's 43 hours (F-11 card 5, ux/scenes/village.md 5): which baked light set the outside and the house show
// at a story time and how far between two, the weather (clouds by the clock from 12:20 on the wedding day, rain once
// a commit says var.weather changed, with the clock as the fallback), and what the time puts in the yard (the altar
// dressed after beat.09, myrtle on the ground on the wedding day), the two lamps and the lit door on the rainy night.
// Pure: VillageLife.tsx applies it. Story time t is minutes from day 0 00:00 (一日目 starts at 1440).

export const DAY = 1440;
const at = (day: number, h: number, m = 0) => day * DAY + h * 60 + m;

export const CLOUDS_FROM = at(2, 12, 20); // t 3620: beat.12's window opens, the sky starts to close
export const RAIN_BY = at(2, 13); // t 3660: rain even without the commit (fallback)
export const CLEAR_WINDOW: [number, number] = [at(3, 8), at(3, 10)]; // beat.15: t 4800–4920
const DAWN3: [number, number] = [at(3, 4), at(3, 6)]; // 三日目 薄明: the rain one step lighter
const CLOUD_MIN = 20; // story minutes for the sky to close or to open
const RAIN_MIN = 8; // from the first big drops to the downpour

export type LightSet = "day" | "sunset" | "night" | "rain";
export type RoomSet = "day" | "feast";

export type Weather = { cloud: number; rain: number };

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));

// the weather at t: rainAt = when a commit's visibleEffects named var.weather (null: not seen), clearAt the same for
// the rain stopping (beat.15); a page loaded mid-storm goes by the clock (card 5's table)
export function weather(
  t: number,
  rainAt: number | null = null,
  clearAt: number | null = null,
): Weather {
  if (t < CLOUDS_FROM) return { cloud: 0, rain: 0 };
  const start = Math.min(Math.max(rainAt ?? Infinity, CLOUDS_FROM), RAIN_BY);
  const stop =
    clearAt !== null && clearAt >= CLEAR_WINDOW[0]
      ? Math.min(clearAt, CLEAR_WINDOW[1])
      : CLEAR_WINDOW[1];
  let cloud = clamp01((t - CLOUDS_FROM) / CLOUD_MIN);
  let rain = clamp01((t - start) / RAIN_MIN);
  if (t >= stop) {
    rain *= clamp01(1 - (t - stop) / 5);
    cloud *= clamp01(1 - (t - stop) / CLOUD_MIN);
  }
  if (t >= DAWN3[0] && t < DAWN3[1]) rain *= 0.7;
  return { cloud, rain };
}

// the clear-sky set and the next one, and how far towards it (0 = all a): the card's table
export function clearSet(t: number): { a: LightSet; b: LightSet; w: number } {
  const m = ((t % DAY) + DAY) % DAY;
  const h = (hh: number, mm = 0) => hh * 60 + mm;
  if (m < h(4)) return { a: "night", b: "night", w: 0 };
  if (m < h(6)) return { a: "night", b: "day", w: (m - h(4)) / h(2) };
  if (m < h(17)) return { a: "day", b: "day", w: 0 };
  if (m < h(18, 30))
    return { a: "day", b: "sunset", w: (m - h(17)) / h(1, 30) };
  if (m < h(18, 45)) return { a: "sunset", b: "sunset", w: 0 };
  if (m < h(20))
    return { a: "sunset", b: "night", w: (m - h(18, 45)) / h(1, 15) };
  return { a: "night", b: "night", w: 0 };
}

// outside: the clear sky's pair, then towards the rain set as far as the clouds have closed
export function outsideLight(
  t: number,
  w: Weather,
): { a: LightSet; b: LightSet; w: number; rain: number } {
  return { ...clearSet(t), rain: w.cloud };
}

// the house: the feast's fire and lamps from the weather's change on (the wedding night), else the day's light,
// dimmed with the daylight outside (1 at noon, about 0.05 at night)
export function roomLight(
  t: number,
  w: Weather,
): { set: RoomSet; dim: number } {
  if (w.cloud > 0.5 && t < CLEAR_WINDOW[1]) return { set: "feast", dim: 1 };
  const c = clearSet(t);
  const lit = (s: LightSet) => (s === "day" ? 1 : s === "sunset" ? 0.35 : 0.05);
  return { set: "day", dim: lit(c.a) + (lit(c.b) - lit(c.a)) * c.w };
}

// what the time puts in the yard (PM: in this card): the altar dressed after beat.09 (一日目 10:30), myrtle leaves on
// the ground from the wedding morning (二日目 06:00)
export function yard(t: number): { altarDressed: boolean; myrtle: boolean } {
  return { altarDressed: t >= at(1, 10, 30), myrtle: t >= at(2, 6) };
}

// the vine's lamp at the groom's (一日目 night, 20:00 to 04:00), the lantern in the hand (三日目 薄明 in the rain),
// the feast's warm door and shutter cracks (二日目 18:30 to 三日目 06:00); the two lamps never at once
export function lamps(t: number): {
  vine: boolean;
  lantern: boolean;
  door: boolean;
} {
  return {
    vine: t >= at(1, 20) && t < at(2, 4),
    lantern: t >= DAWN3[0] && t < DAWN3[1],
    door: t >= at(2, 18, 30) && t < at(3, 6),
  };
}

// slow and quick wavering of a flame, a few per cent
export function flicker(s: number, seed: number): number {
  return (
    1 +
    0.05 * Math.sin(s * 2.1 + seed * 1.3) +
    0.03 * Math.sin(s * 6.7 + seed * 3.1) +
    0.02 * Math.sin(s * 12.9 + seed * 2.3)
  );
}
