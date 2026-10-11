// The treadmill's arithmetic (F-15, road/runway.ts), apart so it tests without the 3D layer.

// a set piece with atMinute shows from this many minutes before it to this many after (the clock jumps by talk)
const SHOW_BEFORE = 3;
const SHOW_AFTER = 8;

export function matches(name: string, patterns: readonly string[]): boolean {
  return patterns.some((p) =>
    p.endsWith("*") ? name.startsWith(p.slice(0, -1)) : name === p,
  );
}

// the belt's offset kept in (-L, 0]: how many whole tiles it moved back this step (set pieces on it move with it)
export function wrapBelt(x: number, L: number): { x: number; wraps: number } {
  let wraps = 0;
  while (x <= -L) {
    x += L;
    wraps++;
  }
  while (x > 0) {
    x -= L;
    wraps--;
  }
  return { x, wraps };
}

// is a set piece due at this minute? atMinute: around it; fromMinute: from then on; neither: only when asked for
export function due(
  p: { atMinute?: number | undefined; fromMinute?: number | undefined },
  minute: number | undefined,
): boolean {
  if (minute === undefined) return false;
  if (p.fromMinute !== undefined) return minute >= p.fromMinute;
  if (p.atMinute !== undefined)
    return (
      minute >= p.atMinute - SHOW_BEFORE && minute <= p.atMinute + SHOW_AFTER
    );
  return false;
}

// the city ahead (homeward-road.md 4.2): metres left by the clock (6 km at 17:50 on the crest, 2 km at 18:30, 300 m
// at 18:50, the gate at 18:55; day 3 = minute 4320 on), and the scale its silhouette is drawn at, standing CITY_AT_M
// ahead: the true angular size, three times that while it is far and only a few pixels tall (2 km and more)
export const CITY_AT_M = 300;
const CITY_KM = [
  [5390, 6000],
  [5430, 2000],
  [5450, 300],
  [5455, 100],
] as const;
export function cityDistanceM(minute: number): number {
  const k = CITY_KM;
  if (minute <= k[0][0]) return k[0][1];
  for (let i = 1; i < k.length; i++) {
    const [m1, d1] = k[i]!;
    const [m0, d0] = k[i - 1]!;
    if (minute <= m1) return d0 + ((d1 - d0) * (minute - m0)) / (m1 - m0);
  }
  return k[k.length - 1]![1];
}
export function cityScale(distanceM: number): number {
  const s = Math.min(1, (distanceM - 2000) / 4000);
  const boost = 1 + 2 * Math.max(0, s) ** 0.5;
  return (CITY_AT_M / Math.max(CITY_AT_M, distanceM)) * boost;
}
