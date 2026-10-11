// Where each person of the crowd stands (F-4 range 3): points scattered in the zone at a minimum gap, the same every
// time for the same seed, none inside the areas kept clear (the scaffold, the way to it).
export type Plan = [number, number]; // x, z

export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function inPolygon([x, z]: Plan, poly: Plan[]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, zi] = poly[i]!;
    const [xj, zj] = poly[j]!;
    if (zi > z !== zj > z && x < ((xj - xi) * (z - zi)) / (zj - zi) + xi)
      inside = !inside;
  }
  return inside;
}

export type Clear = { at: Plan; r: number };

export function scatter(
  zone: Plan[],
  count: number,
  o: {
    seed?: number;
    gap?: number;
    clear?: Clear[];
    keep?: (p: Plan) => boolean;
  } = {},
): Plan[] {
  const rnd = mulberry32(o.seed ?? 1);
  const gap = o.gap ?? 0.75;
  const clear = o.clear ?? [];
  const xs = zone.map((p) => p[0]);
  const zs = zone.map((p) => p[1]);
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)];
  const [z0, z1] = [Math.min(...zs), Math.max(...zs)];
  const out: Plan[] = [];
  for (let tries = 0; out.length < count && tries < count * 400; tries++) {
    const p: Plan = [x0 + rnd() * (x1 - x0), z0 + rnd() * (z1 - z0)];
    if (!inPolygon(p, zone) || (o.keep && !o.keep(p))) continue;
    if (clear.some((c) => Math.hypot(p[0] - c.at[0], p[1] - c.at[1]) < c.r))
      continue;
    if (out.some((q) => Math.hypot(p[0] - q[0], p[1] - q[1]) < gap)) continue;
    out.push(p);
  }
  return out;
}

// distance from a point to a polyline, and which side of it the point is on (+1 left of the direction of travel)
export function toPath(
  p: Plan,
  path: Plan[],
): { d: number; side: number; along: Plan; s: number } {
  // s: how far along the path (from its start) the nearest point is
  let best = { d: Infinity, side: 1, along: [1, 0] as Plan, s: 0 };
  let walked = 0;
  for (let i = 0; i + 1 < path.length; i++) {
    const [ax, az] = path[i]!;
    const [bx, bz] = path[i + 1]!;
    const [dx, dz] = [bx - ax, bz - az];
    const len2 = dx * dx + dz * dz || 1;
    const t = Math.max(
      0,
      Math.min(1, ((p[0] - ax) * dx + (p[1] - az) * dz) / len2),
    );
    const [cx, cz] = [ax + dx * t, az + dz * t];
    const d = Math.hypot(p[0] - cx, p[1] - cz);
    if (d < best.d) {
      const cross = dx * (p[1] - az) - dz * (p[0] - ax);
      const len = Math.sqrt(len2);
      best = {
        d,
        side: cross >= 0 ? 1 : -1,
        along: [dx / len, dz / len],
        s: walked + t * len,
      };
    }
    walked += Math.sqrt(len2);
  }
  return best;
}
