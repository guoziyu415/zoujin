import { BackSide, BoxGeometry, Mesh, MeshBasicMaterial } from "three";

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

// the card's numbers for the room (F-11 card 6: the same 12.7° down as outside, the view widened as 62 -> 50)
export const ROOM_VIEW = {
  portrait: { back: 4, up: 2.4, fov: 70 },
  landscape: { back: 3.4, up: 2.3, fov: 55 },
};

// a zone over a room's box (village-interior pack.json room, glTF x, z), for a pack without cameraZones
export function roomZone(room: {
  min: readonly number[];
  max: readonly number[];
}): CameraZone {
  const [x0, , z0] = room.min as [number, number, number];
  const [x1, , z1] = room.max as [number, number, number];
  return {
    id: "melos-home",
    polygon: [
      [x0, z0],
      [x1, z0],
      [x1, z1],
      [x0, z1],
    ],
    ...ROOM_VIEW,
  };
}

// the room's box with its faces turned inwards: the camera's wall check hits only faces towards the ray, and the
// house's proxy faces outwards, so from inside nothing stopped the camera going through the wall. Never drawn: only
// raycast (Raycaster ignores visible), its matrix set once here.
export function roomWalls(room: {
  min: readonly number[];
  max: readonly number[];
}): Mesh {
  const [x0, y0, z0] = room.min as [number, number, number];
  const [x1, y1, z1] = room.max as [number, number, number];
  const m = new Mesh(
    new BoxGeometry(x1 - x0, y1 - y0, z1 - z0),
    new MeshBasicMaterial({
      side: BackSide,
      colorWrite: false,
      depthWrite: false,
    }),
  );
  m.name = "room-walls";
  m.visible = false;
  m.position.set((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
  m.updateMatrixWorld(true);
  return m;
}
