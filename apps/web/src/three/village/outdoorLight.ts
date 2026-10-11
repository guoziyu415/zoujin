// The village's baked light outside by the story clock (F-11 card 5; village.md 5.1〜5.3): scene.json lightSets says
// which light the ground and the walls (the lightmapped nodes) show at each time, the light sub-packs
// (village-light-sunset / -night / -rain) carry the bakes. Two bakes are on the materials at once and mixed in the
// shader by the time between them; the rain takes over as the clouds close (dimmed with the daylight at night and at
// day 3's dawn).
// The day is the live sky's (as before the sub-packs): its share of the bake is none, so a blend from the day fades the
// baked light in over the live sky's, and a blend to the day fades it out. Where the bake is in, it takes the place of
// the sky's diffuse light (hemisphere, environment), as the castle's hall does; the live sun and its shadows stay.
import {
  Mesh,
  MeshStandardMaterial,
  type Texture,
  type WebGLProgramParametersWithUniforms,
  type WebGLRenderer,
} from "three";
import { textureLoader, type LoadedScene } from "../scene/loadScene";
import { fetchJson } from "../scene/manifest";
import { fogUniforms } from "../shaderPatches";

export type ClearRow = {
  from: string;
  to: string;
  outdoor: string[];
  indoor?: string;
  indoorDim?: "sky" | "dark";
};
export type LightSets = {
  outdoor: Record<string, string>; // light -> pack ("village" = the scene's own)
  clear: ClearRow[];
  rain: { outdoor: string[]; indoor: string; dimAtNight?: boolean };
};
export type SubPack = {
  pack: string;
  kind: string;
  light?: string;
  manifest: string;
};
type LightPack = {
  light: string;
  lightmaps: Record<string, { indirect: { file: string; K: number } } | number>;
  files?: { path: string; bytes: number }[];
};

export const DAY_LIGHT = "day";
const LIT: Record<string, number> = { day: 1, sunset: 0.35, night: 0.05 };

const minutes = (hhmm: string) => {
  const [h, m] = hhmm.split(":").map(Number);
  return (h ?? 0) * 60 + (m ?? 0);
};

// the clear sky's row at t: its light, or the two it blends between and how far (0 = all a)
export function clearLights(
  rows: readonly ClearRow[],
  t: number,
): { a: string; b: string; w: number } {
  const m = ((t % 1440) + 1440) % 1440;
  for (const r of rows) {
    const f = minutes(r.from);
    let to = minutes(r.to);
    if (to <= f) to += 1440; // past midnight
    const mm = m < f ? m + 1440 : m;
    if (mm >= f && mm < to) {
      const a = r.outdoor[0] ?? DAY_LIGHT;
      const b = r.outdoor[1] ?? a;
      return { a, b, w: a === b ? 0 : (mm - f) / (to - f) };
    }
  }
  return { a: DAY_LIGHT, b: DAY_LIGHT, w: 0 };
}

// what the two slots hold now: the clear pair, or (once the clouds come) the clear light nearer now and the rain,
// mixed by the clouds; k scales each slot's bake (the rain dimmed with the daylight when dimAtNight); share is how much
// of the sky's diffuse light the bake replaces
export function outdoorMix(
  sets: Pick<LightSets, "clear" | "rain">,
  t: number,
  cloud: number,
): { a: string; b: string; w: number; ka: number; kb: number; share: number } {
  const c = clearLights(sets.clear, t);
  const baked = (l: string) => (l === DAY_LIGHT ? 0 : 1);
  if (cloud <= 0) {
    return {
      ...c,
      ka: 1,
      kb: 1,
      share: baked(c.a) * (1 - c.w) + baked(c.b) * c.w,
    };
  }
  const near = c.w < 0.5 ? c.a : c.b;
  const rain = sets.rain.outdoor[0] ?? "rain";
  const lit = (l: string) => LIT[l] ?? 1;
  const dim = sets.rain.dimAtNight ? lit(c.a) + (lit(c.b) - lit(c.a)) * c.w : 1;
  return {
    a: near,
    b: rain,
    w: cloud,
    ka: 1,
    kb: dim,
    share: baked(near) * (1 - cloud) + cloud,
  };
}

// the bake's uniforms, one set per lightmapped node kind (ground, arch)
type Slot = {
  mapA: { value: Texture | null };
  mapB: { value: Texture | null };
  kA: { value: number };
  kB: { value: number };
  mix: { value: number };
  share: { value: number };
};

const LMIX_PARS = `
uniform sampler2D zjMixA;
uniform sampler2D zjMixB;
uniform float zjMixKA;
uniform float zjMixKB;
uniform float zjMix;
uniform float zjMixShare;
void main() {`;

const LMIX = `#include <lights_fragment_maps>
#if defined( ZJ_LMIX ) && defined( USE_AOMAP ) && defined( RE_IndirectDiffuse )
{
 vec3 zjBake = mix( texture2D( zjMixA, vAoMapUv ).rgb * zjMixKA, texture2D( zjMixB, vAoMapUv ).rgb * zjMixKB, zjMix );
 irradiance = irradiance * ( 1.0 - zjMixShare ) + zjBake * zjMixShare;
 iblIrradiance *= 1.0 - zjMixShare;
}
#endif`;

function patch(sh: WebGLProgramParametersWithUniforms, s: Slot): void {
  fogUniforms(sh);
  sh.uniforms.zjMixA = s.mapA;
  sh.uniforms.zjMixB = s.mapB;
  sh.uniforms.zjMixKA = s.kA;
  sh.uniforms.zjMixKB = s.kB;
  sh.uniforms.zjMix = s.mix;
  sh.uniforms.zjMixShare = s.share;
  sh.fragmentShader = sh.fragmentShader
    .replace("void main() {", LMIX_PARS)
    .replace("#include <lights_fragment_maps>", LMIX);
}

export type OutdoorBake = {
  set: (t: number, cloud: number) => void;
  dispose: () => void;
};

// the light sub-packs' bakes on the village's lightmapped materials; the sets load in the background, a light not
// loaded yet counts as the day's (the live sky)
export function outdoorBake(
  scene: LoadedScene,
  gl: WebGLRenderer,
  sets: LightSets,
  subPacks: readonly SubPack[],
): OutdoorBake {
  const slots = new Map<string, Slot>();
  const touched: MeshStandardMaterial[] = [];
  scene.root.traverse((o) => {
    if (!(o instanceof Mesh) || !(o.material instanceof MeshStandardMaterial))
      return;
    let holder: typeof o.parent | Mesh = o;
    while (holder && !scene.manifest.nodes[holder.name]) holder = holder.parent;
    const key = holder ? scene.manifest.nodes[holder.name]?.lightmap : "";
    if (!key) return;
    let s = slots.get(key);
    if (!s) {
      s = {
        mapA: { value: null },
        mapB: { value: null },
        kA: { value: 0 },
        kB: { value: 0 },
        mix: { value: 0 },
        share: { value: 0 },
      };
      slots.set(key, s);
    }
    const slot = s;
    const mat = o.material;
    mat.defines = { ...mat.defines, ZJ_LMIX: "" };
    mat.onBeforeCompile = (sh) => patch(sh, slot);
    mat.needsUpdate = true;
    touched.push(mat);
  });

  // light -> lightmap key -> texture and K (PI * K, as the village pack's)
  const bakes = new Map<string, Map<string, { tex: Texture; k: number }>>();
  let live = true;
  for (const sp of subPacks) {
    if (sp.kind !== "light" || !sp.light) continue;
    const light = sp.light;
    const url = new URL(sp.manifest, new URL(scene.base, location.href)).href;
    const base = url.replace(/[^/]+$/, "");
    void fetchJson<LightPack>(url)
      .then(async (p) => {
        const load = textureLoader(
          {
            base,
            manifest: { files: p.files ?? [] },
            textures: new Map(),
            bytes: 0,
          } as unknown as LoadedScene,
          gl,
          () => {},
        );
        const got = new Map<string, { tex: Texture; k: number }>();
        await Promise.all(
          [...slots.keys()].map(async (key) => {
            const lm = p.lightmaps[key];
            if (!lm || typeof lm === "number") return;
            const tex = await load(lm.indirect.file, true, false);
            got.set(key, { tex, k: Math.PI * lm.indirect.K });
          }),
        );
        if (live) bakes.set(light, got);
        else for (const g of got.values()) g.tex.dispose();
      })
      .catch((e: unknown) => console.warn(`village light ${light}:`, e));
  }

  return {
    set(t, cloud) {
      const m = outdoorMix(sets, t, cloud);
      for (const [key, s] of slots) {
        const a = bakes.get(m.a)?.get(key);
        const b = bakes.get(m.b)?.get(key);
        // a light not loaded (or the day) gives no bake: its side of the mix falls back to the other, its share to 0
        const ta = a ?? b;
        const tb = b ?? a;
        s.mapA.value = ta?.tex ?? null;
        s.mapB.value = tb?.tex ?? null;
        s.kA.value = a ? a.k * m.ka : (b?.k ?? 0) * m.kb;
        s.kB.value = b ? b.k * m.kb : (a?.k ?? 0) * m.ka;
        s.mix.value = m.w;
        const shareA = a ? 1 : 0;
        const shareB = b ? 1 : 0;
        const cap = shareA * (1 - m.w) + shareB * m.w;
        s.share.value = ta ? Math.min(m.share, cap) : 0;
      }
    },
    dispose() {
      live = false;
      for (const mat of touched) {
        const d = { ...mat.defines };
        delete d.ZJ_LMIX;
        mat.defines = d;
        mat.onBeforeCompile = fogUniforms;
        mat.needsUpdate = true;
      }
      for (const g of bakes.values())
        for (const b of g.values()) b.tex.dispose();
      bakes.clear();
    },
  };
}
