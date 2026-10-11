// A crowd (F-4 range 3, 4): one instanced mesh per costume, so twenty people are three draw calls (and their shadow).
// Each instance's place, facing and size are attributes the vertex shader applies (shader.ts), not an InstancedMesh's
// matrices: that class would land in the shared 3D chunk, which has no room (frontend-design 10.1).
// Each person has a body shape (height and breadth), a costume, colours from the palette, a facing a little off the
// common one, and their own start and speed in the motion, so no two sway together. The ending's staging calls the
// three verbs; the crowd doesn't walk. The bodies come from the scene's crowd pack (pack.ts), each on its own joints
// and so with its own baked motions; without a pack, the stand-ins (bodies.ts). With the pack's motions (pack.ts
// loadMotions) they stand in Quaternius's idle, and some talk among themselves.
import {
  Color,
  DataTexture,
  FloatType,
  Group,
  InstancedBufferAttribute,
  type InstancedBufferGeometry,
  Mesh,
  type MeshStandardMaterial,
  NearestFilter,
  RGBAFormat,
  Vector4,
} from "three";
import { body, COSTUMES, type Costume } from "./bodies";
import type { CrowdPack } from "./pack";
import {
  bake,
  CHEERS,
  CLIPS,
  STAND_IN,
  type Baked,
  type Clip,
  type Skeleton,
} from "./rig";
import { mulberry32, scatter, toPath, type Clear, type Plan } from "./scatter";
import { crowdMaterials, type CrowdUniforms } from "./shader";

// ux style guide README: the palette's natural dyes, no red, no ochre (Melos's); skin from the cast's range
const CLOTH = {
  L0: "#BDB39D",
  W0: "#CBBDA3",
  N1: "#5E4636",
  B1: "#4F6A7E",
  G1: "#6B6A45",
  A1: "#7E776C",
} as const;
const MAIN: (keyof typeof CLOTH)[] = ["L0", "W0", "A1", "L0", "W0", "G1", "B1"];
const SECOND: (keyof typeof CLOTH)[] = ["N1", "A1", "B1", "G1", "W0"];
const SKIN = ["#8F6449", "#9A6A4C", "#A07A5F", "#A47B5F", "#86593E"];
// dark brown to near black, now and then grey (the cast's: melos.md, ending-cast.md)
const HAIR = ["#2A2018", "#33261C", "#1F1A16", "#4A3D33", "#2A2018", "#6E665E"];
// the palette a little greyer on them than on the cloth swatches (UX on #156: the crowd too saturated at sunset): this
// much of the way to the colour's own grey
const MUTE = { cloth: 0.3, skin: 0.15 };
// the men's beards: none, short, full (of the way from the skin's colour to the hair's)
const BEARDS = [0, 0.3, 0.55, 0.8, 0.8, 0.9];
// the head's width and depth: each face its own proportions, within a few percent
const HEAD = 0.06;
// 3–4 body shapes (art-direction 5.5): [breadth, height]
const SHAPES: [number, number][] = [
  [1, 1],
  [1.1, 0.97],
  [0.93, 1.04],
  [0.97, 0.94],
];
// the mix of costumes: most are men in mantles (style guide)
const MIX: Costume[] = [
  "mantle",
  "mantle",
  "veil",
  "worker",
  "mantle",
  "veil",
  "worker",
];

export type CrowdSpec = {
  zone: Plan[];
  facing: Plan; // what they all look at (the post)
  count: number;
  seed?: number;
  gap?: number;
  clear?: Clear[];
  keep?: (p: Plan) => boolean; // only where this holds (the side of the post towards the gate)
  height?: (x: number, z: number) => number; // the ground under each person
};

// the staging's extras on the crowd's bodies (ux style guide ending-cast.md; the staging's actors, three/ending): the
// guards in the cone helmet with a spear, the executioner bareheaded with his arms bare, the maiden small in a light
// veil with a bundle of cloth. With the pack only (the stand-ins have no helmet or spear); hidden until the staging
// puts one where its actor stands (cast()).
export type CastId = "guardN" | "guardS" | "executioner" | "maiden";
const CAST: {
  id: CastId;
  costume: Costume;
  role: [number, number];
  scale: [number, number];
  cloth: string;
  outer: string;
}[] = [
  {
    id: "guardN",
    costume: "worker",
    role: [2, 1],
    scale: [1.04, 1.03],
    cloth: "#5E4636",
    outer: "#5C4A33",
  },
  {
    id: "guardS",
    costume: "worker",
    role: [2, 1],
    scale: [1.02, 1.05],
    cloth: "#5E4636",
    outer: "#5C4A33",
  },
  {
    id: "executioner",
    costume: "worker",
    role: [0, 0],
    scale: [1.08, 1.0],
    cloth: "#7E776C",
    outer: "#7E776C",
  },
  {
    id: "maiden",
    costume: "veil",
    role: [1, 2],
    scale: [0.9, 0.88],
    cloth: "#BDB39D",
    outer: "#D9D0BE",
  },
];
// where an actor stands: its position and the turn about +Y, read every frame
export type Stand = {
  position: { x: number; y: number; z: number };
  rotation: { y: number };
};

type Person = {
  mesh: number; // which costume's InstancedMesh
  slot: number;
  at: Plan;
  y: number;
  yaw: number;
  scale: [number, number];
  speed: number;
  phase: number; // seconds into the sway loop at time 0
  idle: string; // what they do standing: sway, or talk when the pack's motions have it
  clip: string;
  shift: { from: Plan; to: Plan; t0: number; t1: number } | null; // making way
  role: [number, number]; // the outer piece and what they carry (shader.ts iScale.zw)
  cast?: CastId;
  stand?: Stand | null; // the actor this one of the cast follows; hidden till then
};

type Timed = { at: number; person: number; clip: string; loopPhase?: number };

// each skeleton's motions, baked once for the page and kept (about 170 KB each): the textures made from them go with
// each crowd. A pack's skeletons only ever bake with that pack's motions.
const baked = new WeakMap<Skeleton, Baked>();
const isCheer = (clip: string) => CHEERS.includes(clip);
const TALKING = 4; // one in so many talks among themselves, when the pack's motions have the talk

// a part's centre (x, z), lowest y and height, from the body's rest positions (the cap, for the guards' helmet)
function partBounds(g: InstancedBufferGeometry, part: number): Vector4 | null {
  const pos = g.getAttribute("position");
  const parts = g.getAttribute("aPart");
  let [x, z, n, lo, hi] = [0, 0, 0, Infinity, -Infinity];
  for (let i = 0; i < pos.count; i++) {
    if (parts.getX(i) !== part) continue;
    x += pos.getX(i);
    z += pos.getZ(i);
    lo = Math.min(lo, pos.getY(i));
    hi = Math.max(hi, pos.getY(i));
    n++;
  }
  return n ? new Vector4(x / n, lo, z / n, Math.max(0.01, hi - lo)) : null;
}

function boneTexture(b: Baked): DataTexture {
  const tex = new DataTexture(b.data, b.width, b.height, RGBAFormat, FloatType);
  tex.minFilter = tex.magFilter = NearestFilter;
  tex.needsUpdate = true;
  return tex;
}

export class Crowd extends Group {
  readonly people: Person[] = [];
  readonly extras: Person[] = []; // the staging's extras (CAST), on the same meshes after the crowd
  readonly meshes: Mesh[] = [];
  readonly started: Record<string, number> = {}; // how many times each motion has started (tests, the dev panel)
  readonly fromPack: boolean; // MPFB's bodies, not the stand-ins
  private readonly time = { value: 0 };
  private readonly baked: Baked; // the clips' rows: the same in every skeleton's texture
  private queue: Timed[] = [];
  private now = 0;

  constructor(
    spec: CrowdSpec,
    pack: CrowdPack | null = null,
    motions: Clip[] = [], // the pack's (with a pack only: they're made for its skeleton)
  ) {
    super();
    this.name = "crowd";
    this.fromPack = !!pack;
    const skeleton = (c: Costume) => pack?.[c].skeleton ?? STAND_IN;
    // the pack's motions in place of the hand-made ones of the same name, and after them
    const own = pack ? motions : [];
    const clips = [
      ...CLIPS.map((c) => own.find((m) => m.name === c.name) ?? c),
      ...own.filter((m) => !CLIPS.some((c) => c.name === m.name)),
    ];
    const bakedFor = (s: Skeleton) => {
      let b = baked.get(s);
      if (!b) baked.set(s, (b = bake(s, clips)));
      return b;
    };
    this.baked = bakedFor(skeleton(COSTUMES[0]!));
    const rnd = mulberry32((spec.seed ?? 1) * 7919);
    const pick = <T>(a: readonly T[]): T => a[Math.floor(rnd() * a.length)]!;
    const spots = scatter(spec.zone, spec.count, {
      seed: spec.seed ?? 1,
      gap: spec.gap ?? 0.75,
      clear: spec.clear ?? [],
      ...(spec.keep ? { keep: spec.keep } : {}),
    });
    const per = COSTUMES.map(() => 0);
    const talk = clips.some((c) => c.name === "talk");
    for (const at of spots) {
      const mesh = COSTUMES.indexOf(pick(MIX));
      const face = Math.atan2(spec.facing[0] - at[0], spec.facing[1] - at[1]);
      const [sx, sy] = pick(SHAPES);
      this.people.push({
        mesh,
        slot: per[mesh]!++,
        at,
        y: spec.height?.(at[0], at[1]) ?? 0,
        yaw: face + (rnd() - 0.5) * 0.4, // ±11°
        scale: [sx * (0.97 + rnd() * 0.06), sy * (0.97 + rnd() * 0.06)],
        speed: 0.85 + rnd() * 0.3,
        phase: rnd() * 4,
        idle: talk && this.people.length % TALKING === 1 ? "talk" : "sway",
        clip: "sway",
        shift: null,
        role: [1, 0],
      });
    }
    for (const c of pack ? CAST : []) {
      const mesh = COSTUMES.indexOf(c.costume);
      this.extras.push({
        mesh,
        slot: per[mesh]!++,
        at: [0, 0],
        y: 0,
        yaw: 0,
        scale: c.scale,
        speed: 0.9 + rnd() * 0.2,
        phase: rnd() * 4,
        idle: "sway",
        clip: "sway",
        shift: null,
        role: c.role,
        cast: c.id,
        stand: null,
      });
    }
    COSTUMES.forEach((c, k) => {
      const n = per[k]!;
      if (!n) return;
      const geo = pack ? pack[c].geometry.clone() : body(c);
      const sk = skeleton(c);
      const geoOf = pack?.[c].geometry;
      const cap = geoOf ? partBounds(geoOf, 2) : null;
      const hb = sk.roles.head ?? 0;
      const [hx, hy, hz] = sk.joints[hb] ?? [0, 0, 0];
      const uniforms: CrowdUniforms = {
        uBones: { value: boneTexture(bakedFor(sk)) },
        uTime: this.time,
        uHead: { value: new Vector4(hx, hy, hz, hb) },
        uCap: { value: cap ?? new Vector4(0, 10, 0, 1) },
      };
      const { material, depth } = crowdMaterials(uniforms);
      const attr = (size: number) =>
        new InstancedBufferAttribute(new Float32Array(n * size), size);
      geo.setAttribute("iClip", attr(4));
      geo.setAttribute("iPrev", attr(4));
      geo.setAttribute("iSwitch", attr(1));
      geo.setAttribute("iSkin", attr(3));
      geo.setAttribute("iCloth", attr(3));
      geo.setAttribute("iCloth2", attr(3));
      geo.setAttribute("iHair", attr(3));
      geo.setAttribute("iFace", attr(3));
      geo.setAttribute("iPlace", attr(4));
      geo.setAttribute("iScale", attr(4));
      geo.instanceCount = n;
      const mesh = new Mesh(geo, material);
      mesh.name = `crowd-${c}`;
      mesh.customDepthMaterial = depth;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.frustumCulled = false; // the geometry's own bounds aren't where the instances stand
      this.meshes[k] = mesh;
      this.add(mesh);
    });
    const col = new Color();
    const grey3 = new Color();
    const castOf = (p: Person) => CAST.find((c) => c.id === p.cast);
    for (const p of [...this.people, ...this.extras]) {
      const g = this.meshes[p.mesh]!.geometry;
      const own = castOf(p);
      const set = (name: string, hex: string, mute = MUTE.cloth) => {
        col.set(hex);
        const grey = col.r * 0.2126 + col.g * 0.7152 + col.b * 0.0722;
        col.lerp(grey3.setRGB(grey, grey, grey), mute);
        (g.getAttribute(name) as InstancedBufferAttribute).setXYZ(
          p.slot,
          col.r,
          col.g,
          col.b,
        );
      };
      set("iSkin", pick(SKIN), MUTE.skin);
      set("iCloth", own?.cloth ?? CLOTH[pick(MAIN)]);
      set(
        "iCloth2",
        own?.outer ?? CLOTH[pick(SECOND)],
        own ? 0.15 : MUTE.cloth,
      );
      set("iHair", pick(HAIR), 0);
      (g.getAttribute("iFace") as InstancedBufferAttribute).setXYZ(
        p.slot,
        pick(BEARDS),
        1 + (rnd() - 0.5) * 2 * HEAD,
        1 + (rnd() - 0.5) * 2 * HEAD,
      );
      this.place(p);
      this.start(p, p.idle, -1e3, p.phase);
    }
  }

  // one of the cast follows `stand` (the staging's actor) from now on, or hides again (null). False without the pack
  cast(id: CastId, stand: Stand | null): boolean {
    const p = this.extras.find((c) => c.cast === id);
    if (!p) return false;
    p.stand = stand;
    this.place(p);
    return true;
  }

  // —— the staging's verbs (F-4 range 4) ——

  // どよめき: from a point outwards at `speed` m/s, each person starts when it reaches them (a little scatter), then
  // back to swaying
  // (those who had turned to make way turn back for it)
  wave(from: Plan, speed = 6): void {
    const rnd = mulberry32(Math.floor(this.now * 1000) + 3);
    for (const [i, p] of this.people.entries()) {
      this.queue = this.queue.filter((x) => x.person !== i);
      const at =
        this.now +
        Math.hypot(p.at[0] - from[0], p.at[1] - from[1]) / speed +
        rnd() * 0.25;
      this.queue.push({ at, person: i, clip: "stir" });
      const stir = this.baked.clips.stir!;
      this.queue.push({
        at: at + stir.seconds / p.speed - 0.2,
        person: i,
        clip: p.idle,
        loopPhase: p.phase,
      });
    }
  }

  // the cheer: everyone, each their own way (both fists, one, at the shoulders) and up to most of a second apart; for
  // `seconds`, then they settle, or until settle()
  cheer(seconds?: number): void {
    const rnd = mulberry32(Math.floor(this.now * 1000) + 5);
    this.queue = [];
    for (const [i, p] of this.people.entries()) {
      const at = this.now + rnd() * 0.9;
      const way = rnd();
      const clip = CHEERS[way < 0.35 ? 0 : way < 0.65 ? 1 : way < 0.8 ? 2 : 3]!;
      this.queue.push({ at, person: i, clip });
      if (seconds !== undefined)
        this.queue.push({
          at: at + seconds,
          person: i,
          clip: p.idle,
          loopPhase: p.phase,
        });
    }
  }

  // quiet again (the crowd holding its breath, the cheer dying down): everyone back to swaying, facing the post, a
  // few tenths of a second apart and out of step as at the start; those who made way stay where they stepped to
  settle(): void {
    const rnd = mulberry32(Math.floor(this.now * 1000) + 7);
    this.queue = [];
    for (const [i, p] of this.people.entries())
      this.queue.push({
        at: this.now + rnd() * 0.4,
        person: i,
        clip: p.idle,
        loopPhase: p.phase,
      });
  }

  // making way along a path: for Melos running in from the gate to the scaffold, and for the king walking to it. The
  // people near it turn towards it and step aside. With `speed` (m/s, the walker's) each moves as the walker comes
  // level with them, from the path's start; without, all at once, the nearest first
  part(path: Plan[], width = 2.2, speed?: number): void {
    // making way and the cheer don't overlap (UX on #139: 「万歳」 comes after the crowd has parted): anyone cheering
    // or about to drops their arms first
    const rnd = mulberry32(Math.floor(this.now * 1000) + 11);
    for (const [i, p] of this.people.entries()) {
      const queued = this.queue.some((x) => x.person === i && isCheer(x.clip));
      if (!isCheer(p.clip) && !queued) continue;
      this.queue = this.queue.filter((x) => x.person !== i);
      this.queue.push({
        at: this.now + rnd() * 0.3,
        person: i,
        clip: p.idle,
        loopPhase: p.phase,
      });
    }
    for (const [i, p] of this.people.entries()) {
      const { d, side, along, s } = toPath(p.at, path);
      if (d >= width) continue;
      const away: Plan = [-along[1] * side, along[0] * side]; // perpendicular, away from the path
      const step = (width - d) * 0.6;
      const t0 =
        this.now +
        (speed ? Math.max(0, s / speed - 0.6) : 0) + // a little before the walker reaches them
        (d / width) * 0.3;
      p.shift = {
        from: p.at,
        to: [p.at[0] + away[0] * step, p.at[1] + away[1] * step],
        t0,
        t1: t0 + 1,
      };
      // turn towards the path: to their left (turnL, +X of their own facing) or right
      const left: Plan = [Math.cos(p.yaw), -Math.sin(p.yaw)];
      const toward =
        away[0] * left[0] + away[1] * left[1] <= 0 ? "turnL" : "turnR";
      this.queue = this.queue.filter((x) => x.person !== i);
      this.queue.push({ at: t0, person: i, clip: toward });
    }
  }

  // —— per frame ——

  update(t: number): void {
    this.now = t;
    this.time.value = t;
    if (this.queue.length) {
      const due = this.queue.filter((x) => x.at <= t);
      if (due.length) {
        this.queue = this.queue.filter((x) => x.at > t);
        for (const x of due.sort((a, b) => a.at - b.at))
          this.start(this.people[x.person]!, x.clip, x.at, x.loopPhase ?? 0);
      }
    }
    for (const p of this.people) {
      const sh = p.shift;
      if (!sh || t < sh.t0) continue;
      const k = Math.min(1, (t - sh.t0) / (sh.t1 - sh.t0));
      const e = k * k * (3 - 2 * k);
      p.at = [
        sh.from[0] + (sh.to[0] - sh.from[0]) * e,
        sh.from[1] + (sh.to[1] - sh.from[1]) * e,
      ];
      this.place(p);
      if (k >= 1) p.shift = null;
    }
    for (const p of this.extras) {
      const s = p.stand;
      if (!s) continue;
      p.at = [s.position.x, s.position.z];
      p.y = s.position.y;
      p.yaw = s.rotation.y;
      this.place(p);
    }
  }

  // which motion each person is in (for tests and the dev panel)
  clips(): string[] {
    return this.people.map((p) => p.clip);
  }

  override dispose(): void {
    for (const m of this.meshes) {
      if (!m) continue;
      m.geometry.dispose();
      const mat = m.material as MeshStandardMaterial;
      (mat.userData.uniforms as CrowdUniforms).uBones.value.dispose();
      mat.dispose();
      m.customDepthMaterial?.dispose();
    }
  }

  private place(p: Person): void {
    const g = this.meshes[p.mesh]!.geometry;
    const place = g.getAttribute("iPlace") as InstancedBufferAttribute;
    const size = g.getAttribute("iScale") as InstancedBufferAttribute;
    place.setXYZW(p.slot, p.at[0], p.y, p.at[1], p.yaw);
    const shown = p.cast && !p.stand ? 0 : 1; // the cast folded to a point till the staging places them
    size.setXYZW(p.slot, p.scale[0] * shown, p.scale[1] * shown, ...p.role);
    place.needsUpdate = size.needsUpdate = true;
  }

  // switch person i to a motion from time `at`; the one before fades out (shader.ts BLEND). A looping motion can
  // start part-way in (`phase` seconds), so people coming back to swaying together don't sway together
  private start(p: Person, name: string, at: number, phase = 0): void {
    const c = this.baked.clips[name]!;
    const g = this.meshes[p.mesh]!.geometry;
    const clip = g.getAttribute("iClip") as InstancedBufferAttribute;
    const prev = g.getAttribute("iPrev") as InstancedBufferAttribute;
    const sw = g.getAttribute("iSwitch") as InstancedBufferAttribute;
    const o = p.slot * 4;
    prev.array.set(clip.array.subarray(o, o + 4), o);
    clip.setXYZW(
      p.slot,
      c.row,
      c.loop ? c.frames : -c.frames,
      at - phase / p.speed,
      p.speed,
    );
    sw.setX(p.slot, at);
    clip.needsUpdate = prev.needsUpdate = sw.needsUpdate = true;
    p.clip = name;
    this.started[name] = (this.started[name] ?? 0) + 1;
  }
}
