// Plan coordinates (layout.json: metres, +x towards the castle, +y towards the temple) <-> glTF (+Y up).
// Same maths as assets/pipeline/plaza/frame.mjs: rotate by the scene's rotation about up, then (x, y, h) -> (x, h, -y).
export type Vec3 = [number, number, number];

export function planToWorld(
  x: number,
  y: number,
  h: number,
  rotDeg: number,
): Vec3 {
  const a = (rotDeg * Math.PI) / 180;
  const xr = Math.cos(a) * x - Math.sin(a) * y;
  const yr = Math.sin(a) * x + Math.cos(a) * y;
  return [xr, h, -yr];
}

export function worldToPlan(
  X: number,
  Z: number,
  rotDeg: number,
): [number, number] {
  const a = (-rotDeg * Math.PI) / 180;
  const yr = -Z;
  return [
    Math.cos(a) * X - Math.sin(a) * yr,
    Math.sin(a) * X + Math.cos(a) * yr,
  ];
}

// rotation about +Y that turns a model's front (+Z) towards (dx, dz); the spots' yaw in scene.json uses the same
export const yawOf = (dx: number, dz: number): number => Math.atan2(dx, dz);

// clock.t counts minutes from 00:00 of the first day (api-contract 2.3: 1050 = 約束の日・17:30)
export const minuteOfDay = (t: number): number => ((t % 1440) + 1440) % 1440;
