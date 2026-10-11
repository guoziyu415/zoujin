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
  startSpots?: Record<string, string>; // each place's spot for the player (layout.json startSpots)
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

// Where a scene's pack is: the book manifest's scenes[].assetUrl (B-7: /scenes/<slug>/<version>/scene.json, the
// version in the path so every file of a version caches for good), else /scenes/<slug>/ (vite.config.ts serves the
// build at both; the mock's manifest has a placeholder URL). A scene of several packs (index.json) comes with F-10.
const PACK = /^\/scenes\/[a-z0-9-]+\/[0-9a-f]{8}\/scene\.json$/;

export function sceneBase(
  sceneId: string,
  scenes: readonly { sceneId: string; assetUrl: string }[] = [],
): string {
  const url = scenes.find((s) => s.sceneId === sceneId)?.assetUrl;
  if (url && PACK.test(url))
    return `${import.meta.env.BASE_URL}${url.slice(1, url.lastIndexOf("/") + 1)}`;
  return `${import.meta.env.BASE_URL}scenes/${sceneId.replace(/^scene\./, "")}/`;
}

export async function fetchJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return (await r.json()) as T;
}
