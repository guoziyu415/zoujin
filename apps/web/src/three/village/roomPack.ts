// The room inside Melos's house, the village's sub-pack village-interior (F-11 range 1, 5, 6;
// assets/pipeline/village/interior/pack_interior.mjs): its pack.json, and the arithmetic Interior.tsx applies.
import type { Vec3 } from "../scene/frame";
import type { MaterialEntry, TextureEntry } from "../scene/manifest";
import type { RoomSet } from "./time";

export type FloorProbe = { pos: Vec3; rgb: Vec3 };
export type InteriorPack = {
  packId: "village-interior";
  geometry: string;
  room: { min: Vec3; max: Vec3 };
  flames: { pos: Vec3; size: number }[];
  lightSets: Record<
    RoomSet,
    { file: string; K: number; floor: Record<string, FloorProbe> }
  >;
  materials: Record<string, MaterialEntry>;
  textures: Record<string, TextureEntry>;
  files: { path: string; bytes: number }[];
};

// next to the village's pack: /scenes/<version>/village/ -> /scenes/<version>/village-interior/
export const interiorBase = (villageBase: string): string =>
  villageBase.replace(/village\/$/, "village-interior/");

// the box inside which the sky's light gives way to the room's (shaderPatches HALL): the room's faces lie on its walls,
// so it reaches PAD past them (the patch fades over 0.15 m either side of the box), still short of the walls' outside
const PAD = 0.2;
export function hallBox(room: InteriorPack["room"]): { min: Vec3; max: Vec3 } {
  return {
    min: [room.min[0] - PAD, room.min[1] - PAD, room.min[2] - PAD],
    max: [room.max[0] + PAD, room.max[1] + PAD, room.max[2] + PAD],
  };
}

// the light on a person at (x, z): the floor's light at the probes, weighted by inverse squared distance; a person's
// sides see less than the floor does (SIDE)
const SIDE = 0.6;
export function personLight(
  probes: Record<string, FloorProbe>,
  x: number,
  z: number,
): Vec3 {
  let w = 0;
  const out: Vec3 = [0, 0, 0];
  for (const p of Object.values(probes)) {
    const d2 = (p.pos[0] - x) ** 2 + (p.pos[2] - z) ** 2;
    const k = 1 / Math.max(d2, 0.25);
    w += k;
    for (let i = 0; i < 3; i++) out[i]! += p.rgb[i]! * k;
  }
  return w > 0 ? (out.map((c) => (c / w) * SIDE) as Vec3) : out;
}
