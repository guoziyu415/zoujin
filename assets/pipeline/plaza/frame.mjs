// Plan coordinates (layout.json, build_plaza.py: metres, +y towards the temple) <-> glTF (+Y up).
// build_plaza.py rotates the scene by rotationDeg about up; the glTF exporter maps Blender (x, y, z) to (x, z, -y).
export function planToWorld(x, y, h, rotDeg) {
  const a = (rotDeg * Math.PI) / 180;
  const xr = Math.cos(a) * x - Math.sin(a) * y;
  const yr = Math.sin(a) * x + Math.cos(a) * y;
  return [xr, h, -yr];
}

export function worldToPlan(X, Z, rotDeg) {
  const a = (-rotDeg * Math.PI) / 180;
  const xr = X;
  const yr = -Z;
  return [
    Math.cos(a) * xr - Math.sin(a) * yr,
    Math.sin(a) * xr + Math.cos(a) * yr,
  ];
}

// yaw for three.js: rotation about +Y that turns +Z (a model's front) towards the direction (dx, dz)
export const yawOf = (dx, dz) => Math.atan2(dx, dz);

export function pointInPolygon(x, y, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi)
      inside = !inside;
  }
  return inside;
}
