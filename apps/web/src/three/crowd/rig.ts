// The crowd's skeleton and its motions baked into a texture (F-4 range 2), the way A-0's people will come: one
// skeleton for every body and costume, each frame's bone matrices in one row of a float texture that every instance
// reads in its vertex shader. Until the asset PR brings MPFB's bodies and Quaternius's motions, this is a stand-in:
// nine bones (hips to head, two per arm) and three motions written as curves. The bake and the shader don't change
// when the real ones come; only the skeleton and the frames do.
import { Euler, Matrix4, Quaternion, Vector3 } from "three";

export const FPS = 30;

// front = +Z, the person's left = +X (as the grey stand-ins, three/mannequin.ts)
type BoneDef = { name: string; parent: number; at: [number, number, number] };

export const BONES = [
  { name: "hips", parent: -1, at: [0, 0.95, 0] },
  { name: "spine", parent: 0, at: [0, 1.1, 0] },
  { name: "chest", parent: 1, at: [0, 1.3, 0] },
  { name: "neck", parent: 2, at: [0, 1.47, 0] },
  { name: "head", parent: 3, at: [0, 1.56, 0] },
  { name: "armL", parent: 2, at: [0.19, 1.42, 0] },
  { name: "foreL", parent: 5, at: [0.2, 1.15, 0] },
  { name: "armR", parent: 2, at: [-0.19, 1.42, 0] },
  { name: "foreR", parent: 7, at: [-0.2, 1.15, 0] },
] as const satisfies readonly BoneDef[];
export type Bone = (typeof BONES)[number]["name"];
export const BONE = Object.fromEntries(
  BONES.map((b, i) => [b.name, i]),
) as Record<Bone, number>;

// a pose: each bone's rotation (x, y, z radians, applied in XYZ order) and the hips' offset
export type Pose = {
  rot: Partial<Record<Bone, [number, number, number]>>;
  hips?: [number, number, number];
};

const TAU = Math.PI * 2;
const ease = (x: number) => (x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x));
// up for `rise`, held, down for `fall`, inside a clip of length 1
const bump = (t: number, rise: number, hold: number, fall: number) =>
  ease(t / rise) * (1 - ease((t - rise - hold) / fall));

// the arms hang a little out from the body and bent at the elbow at rest
const REST: Pose["rot"] = {
  armL: [0, 0, 0.08],
  armR: [0, 0, -0.08],
  foreL: [-0.15, 0, 0],
  foreR: [-0.15, 0, 0],
};

export type Clip = {
  name: string;
  seconds: number;
  loop: boolean;
  pose: (t: number) => Pose; // t in seconds
};

export const CLIPS: Clip[] = [
  {
    // standing, the weight going from one foot to the other: 4 s, every curve a whole number of periods so it loops
    name: "sway",
    seconds: 4,
    loop: true,
    pose: (t) => {
      const w = Math.sin((TAU * t) / 4);
      const h = Math.sin((TAU * 2 * t) / 4 + 1.1);
      return {
        hips: [0.025 * w, 0.006 * Math.abs(w), 0],
        rot: {
          ...REST,
          hips: [0, 0.03 * h, 0.03 * w],
          spine: [0.02, 0, -0.02 * w],
          chest: [0.03, 0.02 * h, -0.015 * w],
          head: [0.04 * Math.sin((TAU * t) / 4 + 2), 0.07 * h, 0],
          armL: [0.04 * w, 0, 0.08 + 0.02 * w],
          armR: [-0.04 * w, 0, -0.08 + 0.02 * w],
        },
      };
    },
  },
  {
    // どよめき (art-direction 5.5): a start, leaning in and looking up at the scaffold, a hand half raised, back
    name: "stir",
    seconds: 2.4,
    loop: false,
    pose: (t) => {
      const k = bump(t / 2.4, 0.18, 0.37, 0.45);
      const shake = Math.sin(TAU * 3 * (t / 2.4)) * 0.03 * k;
      return {
        hips: [0, -0.02 * k, 0.04 * k],
        rot: {
          ...REST,
          spine: [0.08 * k, 0, shake],
          chest: [0.12 * k, 0.1 * k, 0],
          neck: [-0.15 * k, 0, 0],
          head: [-0.22 * k, 0.15 * k, 0],
          armL: [-0.9 * k, 0, 0.08 + 0.15 * k],
          foreL: [-0.15 - 0.9 * k, 0, 0],
          armR: [-0.25 * k, 0, -0.08],
        },
      };
    },
  },
  {
    // the cheer after the king's change of heart: both arms up, pumping, a small bounce; 1.2 s, loops
    name: "cheer",
    seconds: 1.2,
    loop: true,
    pose: (t) => {
      const p = Math.sin((TAU * t) / 1.2);
      return {
        hips: [0, 0.025 * Math.abs(p), 0],
        rot: {
          spine: [-0.05, 0, 0],
          chest: [-0.1, 0, 0],
          head: [-0.25 + 0.05 * p, 0, 0],
          armL: [-2.5 - 0.25 * p, 0, 0.35],
          foreL: [-0.3 - 0.2 * p, 0, 0],
          armR: [-2.5 + 0.25 * p, 0, -0.35],
          foreR: [-0.3 + 0.2 * p, 0, 0],
        },
      };
    },
  },
  ...([1, -1] as const).map((s): Clip => ({
    // making way (part): turning the head and shoulders to the path, and staying turned; L = towards +X
    name: s > 0 ? "turnL" : "turnR",
    seconds: 1.2,
    loop: false,
    pose: (t) => {
      const k = ease(t / 0.9);
      return {
        rot: {
          ...REST,
          hips: [0, 0.25 * s * k, 0],
          spine: [0, 0.2 * s * k, 0],
          chest: [0.05 * k, 0.3 * s * k, 0],
          head: [0, 0.55 * s * k, 0],
        },
      };
    },
  })),
];

export type Baked = {
  data: Float32Array; // RGBA, width = BONES.length * 4, one row per frame, the rows of each clip together
  width: number;
  height: number;
  clips: Record<
    string,
    { row: number; frames: number; loop: boolean; seconds: number }
  >;
};

const e = new Euler();
const q = new Quaternion();
const one = new Vector3(1, 1, 1);

// the skin matrices (bone world × inverse bind) of one pose
export function skinMatrices(pose: Pose): Matrix4[] {
  const world: Matrix4[] = [];
  return BONES.map((b, i) => {
    const r = pose.rot[b.name] ?? [0, 0, 0];
    q.setFromEuler(e.set(r[0], r[1], r[2], "XYZ"));
    const parent: readonly [number, number, number] =
      b.parent >= 0 ? (BONES as readonly BoneDef[])[b.parent]!.at : [0, 0, 0];
    const t = new Vector3(
      b.at[0] - parent[0],
      b.at[1] - parent[1],
      b.at[2] - parent[2],
    );
    if (i === 0 && pose.hips) t.add(new Vector3(...pose.hips));
    const local = new Matrix4().compose(t, q, one);
    const w = b.parent >= 0 ? world[b.parent]!.clone().multiply(local) : local;
    world[i] = w;
    return w
      .clone()
      .multiply(new Matrix4().makeTranslation(-b.at[0], -b.at[1], -b.at[2]));
  });
}

export function bake(clips: Clip[] = CLIPS): Baked {
  const width = BONES.length * 4;
  const rows: Float32Array[] = [];
  const index: Baked["clips"] = {};
  for (const c of clips) {
    const frames = Math.round(c.seconds * FPS);
    index[c.name] = {
      row: rows.length,
      frames,
      loop: c.loop,
      seconds: c.seconds,
    };
    for (let f = 0; f < frames; f++) {
      const row = new Float32Array(width * 4);
      skinMatrices(c.pose(f / FPS)).forEach((m, b) =>
        row.set(m.elements, b * 16),
      ); // 4 columns = 4 texels
      rows.push(row);
    }
  }
  const data = new Float32Array(width * 4 * rows.length);
  rows.forEach((r, i) => data.set(r, i * width * 4));
  return { data, width, height: rows.length, clips: index };
}
