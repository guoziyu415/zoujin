// The house's camera zone (F-11 card 6): scene.json cameraZones, polygons in glTF x, z. In only 0.5 m past the line,
// out only 0.5 m past it the other way, so standing on the threshold doesn't flip the camera every frame.

export type CameraZone = {
  id: string;
  polygon: [number, number][];
  portrait: { back: number; up: number; fov: number };
  landscape: { back: number; up: number; fov: number };
};

export const MARGIN = 0.5;

function contains(poly: readonly [number, number][], x: number, z: number) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, zi] = poly[i]!;
    const [xj, zj] = poly[j]!;
    if (zi > z !== zj > z && x < ((xj - xi) * (z - zi)) / (zj - zi) + xi)
      inside = !inside;
  }
  return inside;
}

function edgeDistance(poly: readonly [number, number][], x: number, z: number) {
  let d = Infinity;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [ax, az] = poly[j]!;
    const [bx, bz] = poly[i]!;
    const dx = bx - ax;
    const dz = bz - az;
    const k = Math.max(
      0,
      Math.min(1, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz || 1)),
    );
    d = Math.min(d, Math.hypot(x - ax - k * dx, z - az - k * dz));
  }
  return d;
}

// is the point in the zone, given whether it was last time
export function inZone(
  poly: readonly [number, number][],
  x: number,
  z: number,
  wasIn: boolean,
): boolean {
  const inside = contains(poly, x, z);
  const far = edgeDistance(poly, x, z) >= MARGIN;
  return wasIn ? inside || !far : inside && far;
}
