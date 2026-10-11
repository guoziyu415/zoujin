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

// the road's packs (F-10): the water's node and what the page's shader needs; plan coordinates (layout.json)
export type WaterEntry = {
  kind: "calm" | "flood";
  node: string;
  levelM: number;
  fog?: { heightM: number; edgeM: number };
  channelPlan?: [number, number, number][]; // centre x, y and half width every few metres
  flowDirPlan?: [number, number];
  speedMps?: number;
  splashPlan?: [number, number, number][]; // x, y, strength
  slowPlan?: [number, number, number, number][]; // ellipses x, y, rx, ry
  haze?: number;
  horizonDeg?: number; // how high the hills round the valley stand, seen from the water (what it mirrors low down)
  bankM?: number; // how high the banks stand over the water (the same)
};

// the castle (F-14, assets/pipeline/castle/lamps.mjs): the lamps and the lamp-lit room, glTF coordinates
export type LampEntry = {
  id: string;
  kind: "chandelier" | "brazier";
  indoor: boolean;
  pos: Vec3;
  flames: Vec3[];
};

export type SceneManifest = {
  version: 1;
  sceneId: string;
  sun: SunParams;
  ridgeElevationDeg?: number; // the sun gives no direct light below this, on the east side (F-10)
  water?: WaterEntry;
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
  lamps?: LampEntry[];
  hall?: { min: Vec3; max: Vec3 };
  files: {
    path: string;
    bytes: number;
    sha256: string;
    pack: "entry" | "hi";
    shared?: string; // the file lives in this shared pack's directory (road-common)
  }[];
};

export type LightmapEntry = {
  indirect: { file: string; K: number };
  ao: { file: string };
  full?: { file: string; K: number }; // the whole bake, where it is the lamps' night (the castle)
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

// Where a scene's pack is: the book manifest's scenes[].assetUrl (B-7: /scenes/<version>/<slug>/scene.json, the
// version in the path so every file of a version caches for good, and first so an index.json's ../<other pack>/
// stays inside it), else /scenes/<slug>/ (vite.config.ts serves the build at both). A scene of several packs has
// index.json there instead, naming a pack per act, each a folder next to it (scene/extra.ts, F-10).
const PACK = /^\/scenes\/[0-9a-f]{8}\/[a-z0-9-]+\/(scene|index)\.json$/;

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
