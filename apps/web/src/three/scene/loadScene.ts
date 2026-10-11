// Loads one scene in two steps (frontend-design 8.2): first what is needed to walk (scene.json, nav.json, the geometry
// with flat colours), then the detail (KTX2 textures and the baked occlusion) on the standard tier. The high tier's
// 2048 textures come later, in the background, only at L2 / L3 (10.6.3 point 5); applyTier swaps them in and out at a
// camera cut. Both tiers stay in memory once loaded (about 50 + 60 MB, inside the 150 MB budget of 10.1).
import {
  Color,
  DoubleSide,
  FrontSide,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  NoColorSpace,
  RepeatWrapping,
  ClampToEdgeWrapping,
  SRGBColorSpace,
  type Group,
  type Material,
  type Object3D,
  type Texture,
  type WebGLRenderer,
} from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { KTX2Loader } from "three/examples/jsm/loaders/KTX2Loader.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { NavMesh, type NavData } from "../nav/navmesh";
import { fogUniforms } from "../shaderPatches";
import {
  fetchJson,
  lightmapOf,
  type MaterialEntry,
  type SceneManifest,
  type TextureEntry,
} from "./manifest";

export type LoadedScene = {
  base: string; // the pack's directory URL; every file of the pack is relative to it (manifest.ts sceneBase)
  manifest: SceneManifest;
  nav: NavMesh;
  root: Group;
  walkable: Mesh[]; // ground and buildings: taps raycast against these
  blockers: Object3D[]; // the simplified shadow caster, for the camera's wall check
  gate: Object3D | null; // the workshop gate (scene.json nodes.*.movable)
  bytes: number; // downloaded so far
  textures: Map<string, Promise<Texture>>; // by file, both tiers
  dispose?: () => void; // what scene/extra.ts added to the scene (its water, the ridge) goes with it
};

type Slot = "base" | "nrm" | "mr";

const DOUBLE = new Set(["fabric_red", "fabric_blue"]); // awnings are single planes; everything else has a back
// buildings and ground receive the sun's shadow; the far ring (hills, cypresses) doesn't, the proxy only casts it
const RECEIVES = new Set(["ground", "arch", "workshop_gate"]);

let ktx2: KTX2Loader | null = null;
function ktx2Loader(renderer: WebGLRenderer): KTX2Loader {
  if (!ktx2) ktx2 = new KTX2Loader().detectSupport(renderer);
  return ktx2;
}

// flat colour while the textures load: the texture's mean colour (scene.json keeps it for the two-tier check)
function flatColour(m: SceneManifest, e: MaterialEntry): Color {
  const c = new Color().setRGB(e.color[0], e.color[1], e.color[2]);
  const mean = e.base ? m.textures[e.base]?.std.mean : undefined;
  if (mean)
    c.multiply(
      new Color().setRGB(
        mean[0] / 255,
        mean[1] / 255,
        mean[2] / 255,
        SRGBColorSpace,
      ),
    );
  return c;
}

function makeMaterial(m: SceneManifest, name: string): Material {
  const e = m.materials[name];
  if (!e) return new MeshStandardMaterial({ color: 0x808080, roughness: 0.9 });
  // with an mr map the factors are 1 and the map carries the values: until it arrives, plain rough stone
  const mat = new MeshStandardMaterial({
    color: flatColour(m, e),
    roughness: e.mr ? 0.9 : e.roughness,
    metalness: e.mr ? 0 : e.metalness,
    side: DOUBLE.has(name) ? DoubleSide : FrontSide,
  });
  mat.name = name;
  mat.onBeforeCompile = fogUniforms;
  return mat;
}

export async function loadWalkable(
  base: string,
  onBytes: (n: number) => void,
): Promise<LoadedScene> {
  const manifest = await fetchJson<SceneManifest>(`${base}scene.json`);
  const size = (file: string) =>
    manifest.files.find((f) => f.path === file)?.bytes ?? 0;
  const [navData, gltf] = await Promise.all([
    fetchJson<NavData>(`${base}${manifest.nav.file}`),
    new GLTFLoader()
      .setMeshoptDecoder(MeshoptDecoder)
      .loadAsync(`${base}geo.glb`),
  ]);
  const bytes = size("nav.json") + size("geo.glb");
  onBytes(bytes);
  const nav = new NavMesh(navData);
  const root = gltf.scene;
  const walkable: Mesh[] = [];
  const blockers: Object3D[] = [];
  let gate: Object3D | null = null;
  for (const [nodeName, info] of Object.entries(manifest.nodes)) {
    const node = root.getObjectByName(nodeName);
    if (!node) continue;
    if (info.movable) gate = node;
    node.traverse((o) => {
      if (!(o instanceof Mesh)) return;
      if (info.shadowCasterOnly) {
        o.material = new MeshBasicMaterial({
          colorWrite: false,
          depthWrite: false,
        });
        o.castShadow = true;
        o.receiveShadow = false;
        blockers.push(o);
        return;
      }
      const old = o.material as Material;
      o.material = makeMaterial(manifest, old.name);
      old.dispose();
      o.castShadow = false;
      o.receiveShadow = RECEIVES.has(nodeName);
      if (nodeName === "ground" || nodeName === "arch") walkable.push(o);
    });
  }
  return {
    base,
    manifest,
    nav,
    root,
    walkable,
    blockers,
    gate,
    bytes,
    textures: new Map(),
  };
}

// step two: textures and the baked occlusion; materials get their maps as they arrive
export async function loadDetail(
  scene: LoadedScene,
  renderer: WebGLRenderer,
  onBytes: (n: number) => void,
): Promise<void> {
  const { manifest } = scene;
  const load = textureLoader(scene, renderer, onBytes);
  const jobs: Promise<void>[] = [];
  scene.root.traverse((o) => {
    if (!(o instanceof Mesh) || !(o.material instanceof MeshStandardMaterial))
      return;
    const mat = o.material;
    const e = manifest.materials[mat.name];
    if (!e) return;
    const tex = (key: string | undefined) =>
      key ? manifest.textures[key] : undefined;
    const b = tex(e.base);
    const n = tex(e.nrm);
    const mr = tex(e.mr);
    mat.userData.tex = { base: e.base, nrm: e.nrm, mr: e.mr };
    if (b)
      jobs.push(
        load(b.std.file, true, true).then((t) => {
          mat.map = t;
          mat.color.setRGB(e.color[0], e.color[1], e.color[2]);
          mat.needsUpdate = true;
        }),
      );
    if (n)
      jobs.push(
        load(n.std.file, false, true).then((t) => {
          mat.normalMap = t;
          mat.normalScale.set(1, -1); // glTF normal maps with three's derivative tangents (S7)
          mat.needsUpdate = true;
        }),
      );
    if (mr)
      jobs.push(
        load(mr.std.file, false, true).then((t) => {
          mat.roughnessMap = t;
          mat.metalnessMap = t;
          mat.roughness = e.roughness;
          mat.metalness = e.metalness;
          mat.needsUpdate = true;
        }),
      );
    // baked ambient occlusion on the lightmap UVs (the realtime sun and the sky do the rest, F-2 range 2)
    let holder: Object3D | null = o;
    while (holder && !manifest.nodes[holder.name]) holder = holder.parent;
    const lm = holder?.name
      ? lightmapOf(manifest, manifest.nodes[holder.name]?.lightmap ?? "")
      : undefined;
    if (lm)
      jobs.push(
        load(lm.ao.file, false, false).then((t) => {
          t.channel = 1;
          mat.aoMap = t;
          mat.aoMapIntensity = 1;
          mat.needsUpdate = true;
        }),
      );
  });
  await Promise.all(jobs);
}

function textureLoader(
  scene: LoadedScene,
  renderer: WebGLRenderer,
  onBytes: (n: number) => void,
) {
  const base = scene.base;
  const loader = ktx2Loader(renderer);
  const size = (file: string) =>
    scene.manifest.files.find((f) => f.path === file)?.bytes ?? 0;
  return (file: string, srgb: boolean, repeat: boolean): Promise<Texture> => {
    let p = scene.textures.get(file);
    if (!p) {
      p = loader.loadAsync(`${base}${file}`).then((t) => {
        t.colorSpace = srgb ? SRGBColorSpace : NoColorSpace;
        t.wrapS = t.wrapT = repeat ? RepeatWrapping : ClampToEdgeWrapping;
        t.anisotropy = repeat ? 4 : 1;
        scene.bytes += size(file);
        onBytes(scene.bytes);
        return t;
      });
      scene.textures.set(file, p);
    }
    return p;
  };
}

// the materials' texture keys (set by loadDetail) and their entries in scene.json
function eachTexture(
  scene: LoadedScene,
  fn: (mat: MeshStandardMaterial, slot: Slot, e: TextureEntry) => void,
): void {
  scene.root.traverse((o) => {
    if (!(o instanceof Mesh) || !(o.material instanceof MeshStandardMaterial))
      return;
    const keys = o.material.userData.tex as
      Partial<Record<Slot, string>> | undefined;
    for (const slot of ["base", "nrm", "mr"] as const) {
      const e = keys?.[slot] ? scene.manifest.textures[keys[slot]] : undefined;
      if (e) fn(o.material, slot, e);
    }
  });
}

// the high tier's textures (scene.json pack "hi"), in the background; resolves when all are on the GPU's side of the
// loader, ready for applyTier
export async function loadHigh(
  scene: LoadedScene,
  renderer: WebGLRenderer,
  onBytes: (n: number) => void = () => {},
): Promise<void> {
  const load = textureLoader(scene, renderer, onBytes);
  const jobs = new Map<string, Promise<Texture>>();
  eachTexture(scene, (_, slot, e) => {
    if (e.hi && !jobs.has(e.hi.file))
      jobs.set(e.hi.file, load(e.hi.file, slot === "base", true));
  });
  await Promise.all(jobs.values());
}

// put one tier's textures on the materials; a texture that is not loaded yet keeps the one there
export async function applyTier(
  scene: LoadedScene,
  tier: "standard" | "high",
): Promise<void> {
  const swaps: Promise<void>[] = [];
  eachTexture(scene, (mat, slot, e) => {
    const file = tier === "high" && e.hi ? e.hi.file : e.std.file;
    const p = scene.textures.get(file);
    if (!p) return;
    swaps.push(
      p.then((t) => {
        if (slot === "base") mat.map = t;
        else if (slot === "nrm") mat.normalMap = t;
        else mat.roughnessMap = mat.metalnessMap = t;
      }),
    );
  });
  await Promise.all(swaps);
}
