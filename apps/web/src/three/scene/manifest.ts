// scene.json as written by assets/pipeline/plaza/pack_scene.mjs (only the fields the page reads).
import type { SunParams } from "../sun";
import type { Vec3 } from "./frame";

export type TextureEntry = {
  slot: "base" | "nrm" | "mr";
  std: { file: string; size: number; mean?: Vec3 };
  hi?: { file: string; size: number; mean?: Vec3 };
};

export type MaterialEntry = {
  color: Vec3;
  roughness: number;
  metalness: number;
  base?: string;
  nrm?: string;
  mr?: string;
};

export type NodeEntry = {
  prims: number;
  tris: number;
  lightmap?: string;
  shadowCasterOnly?: boolean;
  movable?: boolean;
  place?: string;
  closedYawDeg?: number;
};

export type SpotEntry = {
  pos: Vec3;
  yaw: number;
  place: string;
  poly: number;
  auto?: false;
};

export type SceneManifest = {
  version: 1;
  sceneId: string;
  sun: SunParams;
  nodes: Record<string, NodeEntry>;
  materials: Record<string, MaterialEntry>;
  textures: Record<string, TextureEntry>;
  lightmaps: { res: number; bakeMinute: number } & Record<string, unknown>;
  nav: { file: string };
  defaultPlace: string;
  places: { id: string; polygon: [number, number][] }[];
  exits: { place: string; spot: string }[];
  playerStartSpot: string;
  spots: Record<string, SpotEntry>;
  files: {
    path: string;
    bytes: number;
    sha256: string;
    pack: "entry" | "hi";
  }[];
};

export type LightmapEntry = {
  indirect: { file: string; K: number };
  ao: { file: string };
};

export function lightmapOf(
  m: SceneManifest,
  mesh: string,
): LightmapEntry | undefined {
  const e = m.lightmaps[mesh];
  return e && typeof e === "object" && "ao" in e
    ? (e as LightmapEntry)
    : undefined;
}

// scene.syracuse-square -> /scenes/syracuse-square/ (vite.config.ts serves the build there)
export const sceneBase = (sceneId: string): string =>
  `${import.meta.env.BASE_URL}scenes/${sceneId.replace(/^scene\./, "")}/`;

export async function fetchJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return (await r.json()) as T;
}
