// Scenes other than the plaza (F-10), in their own lazy chunk so the 3D chunk stays inside its budget (S-083 ⑤):
// which pack a scene loads in this act (its index.json), files kept in a shared pack (road-common), the water, the
// ridge that hides a low sun, the far land (land.ts), the weather (clouds.ts) and letting go of a scene. Fetching the
// next act's pack ahead of time is prefetch.ts.
import {
  DoubleSide,
  MathUtils,
  Mesh,
  MeshStandardMaterial,
  type Material,
  type Scene,
  type Texture,
} from "three";
import { lighting, lightState } from "../Lighting";
import { sunLook } from "../sun";
import { attachWater } from "../water/water";
import { clouds } from "./clouds";
import { glowFor, hills } from "./land";
import { loadWalkable, type LoadedScene } from "./loadScene";
import type { SceneManifest } from "./manifest";

type Index = { packs: { pack: string; act: string; manifest: string }[] };

// the folder of the pack for this act: base is the scene's (manifest.ts sceneBase); its index.json (written by the
// road's merge_river.mjs) names a pack per act, each a folder next to it. A scene with no index is its own pack.
export async function packFor(base: string, act?: string): Promise<string> {
  const r = await fetch(`${base}index.json`);
  if (!r.ok) return base;
  const { packs } = (await r.json()) as Index;
  const p = packs.find((q) => q.act === act);
  if (!p) console.warn(`${base}: no pack for ${act}, using the first`);
  return base.replace(/[^/]+\/$/, `${(p ?? packs[0]!).pack}/`);
}

// files with shared: <pack> live in that pack's directory next to this one: point every reference there
function shareFiles(m: SceneManifest): void {
  const moved = new Map<string, string>();
  for (const f of m.files) {
    if (!f.shared) continue;
    const to = `../${f.shared}/${f.path}`;
    moved.set(f.path, to);
    f.path = to;
  }
  const to = (e?: { file: string }) => {
    if (e && moved.has(e.file)) e.file = moved.get(e.file)!;
  };
  for (const t of Object.values(m.textures)) {
    to(t.std);
    to(t.hi);
  }
  for (const l of Object.values(m.lightmaps))
    if (l && typeof l === "object") {
      to((l as { ao?: { file: string } }).ao);
      to((l as { indirect?: { file: string } }).indirect);
    }
}

// the sky drawn as for a sun this high, the sun itself where it is (F-10 card 5: act 2's sky as at −1.5°); the test
// hook sets it
export const skyLook = { elevDeg: undefined as number | undefined };

// east of the scene a ridge stands this high (scene.json ridgeElevationDeg): below it the sun gives no direct light,
// and the sky that lights the scene loses the glow around it (F-10 card 5); Lighting.tsx calls this after the clock
function ridge(deg: number | undefined): void {
  lighting.adjust = (pos, sun, skies) => {
    const gain =
      deg === undefined || pos.azimuthDeg > 180
        ? 1
        : MathUtils.clamp((pos.elevDeg - deg) / 0.6, 0, 1);
    glowFor(pos.elevDeg, gain);
    lightState.direct = sun.intensity *= gain;
    skies[1]!.material.uniforms.mieDirectionalG!.value = 0.8 * gain;
    const e = skyLook.elevDeg;
    if (e === undefined) return;
    const sl = sunLook(e);
    const se = MathUtils.degToRad(e);
    const k = Math.cos(se) / Math.hypot(pos.dir[0], pos.dir[2]);
    for (const s of skies) {
      const u = s.material.uniforms;
      u.sunPosition!.value.set(pos.dir[0] * k, Math.sin(se), pos.dir[2] * k);
      u.uSkyGain!.value = sl.skyGain;
      u.uDusk!.value = sl.dusk;
      u.uNightSky!.value = sl.nightSky;
      u.uBelt!.value = sl.belt;
      u.uAmber!.value = sl.amber;
    }
  };
}

// the foliage (UX round 2 ④): leaf clusters, the willow's strands, the reeds, and in the village the wheat, the vines
// and the fig are alpha-tested cards and crowns, seen from both sides; until the texture is there nothing is drawn (a
// card in its flat colour would be a green tile)
const FOLIAGE = new Set([
  "poplar",
  "holmoak",
  "willow",
  "willowstrand",
  "reed",
  "wheat",
  "vine",
  "fig",
]);
function foliage(s: LoadedScene): void {
  const done = new Set<Material>();
  s.root.traverse((o) => {
    if (!(o instanceof Mesh)) return;
    const m = o.material as Material;
    if (
      !(m instanceof MeshStandardMaterial) ||
      !FOLIAGE.has(m.name) ||
      done.has(m)
    )
      return;
    done.add(m);
    m.alphaTest = 0.5;
    m.side = DoubleSide;
    const prev = m.onBeforeCompile.bind(m);
    m.onBeforeCompile = (sh, r) => {
      prev(sh, r);
      sh.fragmentShader = sh.fragmentShader.replace(
        "#include <map_fragment>",
        "#include <map_fragment>\n#ifndef USE_MAP\ndiscard;\n#endif",
      );
    };
    m.customProgramCacheKey = () => "zj-leaf";
    m.needsUpdate = true;
  });
}

export async function load(
  base: string,
  act: string | undefined,
  onBytes: (n: number) => void,
  three: Scene,
): Promise<LoadedScene> {
  const s = await loadWalkable(await packFor(base, act), onBytes);
  shareFiles(s.manifest);
  ridge(s.manifest.ridgeElevationDeg);
  hills(s, s.manifest.ridgeElevationDeg);
  foliage(s);
  const sky = clouds(s);
  const off = s.manifest.water ? attachWater(s, three) : () => {};
  s.dispose = () => {
    off();
    sky?.();
    ridge(undefined);
  };
  return s;
}

// a scene the player has left: its geometry, materials and textures go (both tiers stay in memory while it is shown,
// so two scenes together would pass the 150 MB of frontend-design 10.1)
export function dispose(s: LoadedScene): void {
  s.dispose?.();
  s.root.traverse((o) => {
    if (!(o instanceof Mesh)) return;
    o.geometry.dispose();
    for (const m of ([] as Material[]).concat(o.material)) m.dispose();
  });
  for (const p of s.textures.values())
    void p.then((t: Texture) => t.dispose()).catch(() => {});
}
