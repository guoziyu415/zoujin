// The crowd's skeletons and their motions baked into a texture (F-4 range 2): each frame's bone matrices in one row of a
// float texture that every instance reads in its vertex shader. The motions are written as curves on nine roles (hips
// to head, two per arm); a skeleton says which of its bones plays each role, and the rest follow their parents. Two
// kinds of skeleton: MPFB's game_engine rig from the crowd pack (pack.ts; each body its own joints), and the nine-bone
// stand-in the bodies in bodies.ts hang on when a scene has no pack.
import { Euler, Matrix4, Quaternion, Vector3 } from "three";

export const FPS = 30;

type Vec3 = [number, number, number];
export type Role =
  | "hips"
  | "spine"
  | "chest"
  | "neck"
  | "head"
  | "armL"
  | "foreL"
  | "armR"
  | "foreR";

// a pose: each role's rotation (x, y, z radians, applied in XYZ order, from the rest pose) and the hips' offset
export type Pose = {
  rot: Partial<Record<Role, Vec3>>;
  hips?: Vec3;
};

// front = +Z, the person's left = +X; at rest every bone has the world's axes, so a rotation means the same on any
// skeleton: armL about +Z by a positive angle swings the left arm out
export type Skeleton = {
  parents: number[];
  joints: Vec3[]; // where each bone turns, at rest
  roles: Partial<Record<Role, number>>;
  rest: Pose["rot"]; // added to every pose: the stand-in's arms hang straight in its bind pose
};

// the stand-in (as the grey stand-ins, three/mannequin.ts)
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
] as const satisfies readonly { name: Role; parent: number; at: Vec3 }[];
export const BONE = Object.fromEntries(
  BONES.map((b, i) => [b.name, i]),
) as Record<Role, number>;
export const STAND_IN: Skeleton = {
  parents: BONES.map((b) => b.parent),
  joints: BONES.map((b) => [...b.at]),
  roles: BONE,
  // the arms a little out from the body and bent at the elbow
  rest: {
    armL: [0, 0, 0.08],
    armR: [0, 0, -0.08],
    foreL: [-0.15, 0, 0],
    foreR: [-0.15, 0, 0],
  },
};

// MPFB's game_engine bones for the roles. The hips' sway goes on spine_01, not the pelvis, so the legs (children of
// the pelvis) stay planted; the bodies' rest pose already has the arms down and the elbows a little bent.
const MPFB_ROLES: Record<Role, string> = {
  hips: "spine_01",
  spine: "spine_02",
  chest: "spine_03",
  neck: "neck_01",
  head: "head",
  armL: "upperarm_l",
  foreL: "lowerarm_l",
  armR: "upperarm_r",
  foreR: "lowerarm_r",
};

export function packSkeleton(
  bones: { name: string; parent: number }[],
  joints: Vec3[],
): Skeleton {
  const index = new Map(bones.map((b, i) => [b.name, i]));
  const roles: Skeleton["roles"] = {};
  for (const [role, name] of Object.entries(MPFB_ROLES)) {
    const i = index.get(name);
    if (i !== undefined) roles[role as Role] = i;
  }
  return { parents: bones.map((b) => b.parent), joints, roles, rest: {} };
}

const TAU = Math.PI * 2;
const ease = (x: number) => (x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x));
// up for `rise`, held, down for `fall`, inside a clip of length 1
const bump = (t: number, rise: number, hold: number, fall: number) =>
  ease(t / rise) * (1 - ease((t - rise - hold) / fall));

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
          hips: [0, 0.03 * h, 0.03 * w],
          spine: [0.02, 0, -0.02 * w],
          chest: [0.03, 0.02 * h, -0.015 * w],
          head: [0.04 * Math.sin((TAU * t) / 4 + 2), 0.07 * h, 0],
          armL: [0.04 * w, 0, 0.02 * w],
          armR: [-0.04 * w, 0, 0.02 * w],
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
          spine: [0.08 * k, 0, shake],
          chest: [0.12 * k, 0.1 * k, 0],
          neck: [-0.15 * k, 0, 0],
          head: [-0.22 * k, 0.15 * k, 0],
          armL: [-0.9 * k, 0, 0.15 * k],
          foreL: [-0.9 * k, 0, 0],
          armR: [-0.25 * k, 0, 0],
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
          armL: [-2.5 - 0.25 * p, 0, 0.27],
          foreL: [-0.15 - 0.2 * p, 0, 0],
          armR: [-2.5 + 0.25 * p, 0, -0.27],
          foreR: [-0.15 + 0.2 * p, 0, 0],
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
  data: Float32Array; // RGBA, width = bones × 4, one row per frame, the rows of each clip together
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
export function skinMatrices(pose: Pose, skel: Skeleton = STAND_IN): Matrix4[] {
  const role: (Role | undefined)[] = skel.parents.map(() => undefined);
  for (const [r, i] of Object.entries(skel.roles)) role[i] = r as Role;
  const world: Matrix4[] = [];
  return skel.joints.map((at, i) => {
    const r = role[i];
    const a = (r && pose.rot[r]) || [0, 0, 0];
    const b = (r && skel.rest[r]) || [0, 0, 0];
    q.setFromEuler(e.set(a[0] + b[0], a[1] + b[1], a[2] + b[2], "XYZ"));
    const p = skel.parents[i]!;
    const from: Vec3 = p >= 0 ? skel.joints[p]! : [0, 0, 0];
    const t = new Vector3(at[0] - from[0], at[1] - from[1], at[2] - from[2]);
    if (r === "hips" && pose.hips) t.add(new Vector3(...pose.hips));
    const local = new Matrix4().compose(t, q, one);
    const w = p >= 0 ? world[p]!.clone().multiply(local) : local;
    world[i] = w;
    return w
      .clone()
      .multiply(new Matrix4().makeTranslation(-at[0], -at[1], -at[2]));
  });
}

export function bake(skel: Skeleton = STAND_IN, clips: Clip[] = CLIPS): Baked {
  const width = skel.joints.length * 4;
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
      skinMatrices(c.pose(f / FPS), skel).forEach((m, b) =>
        row.set(m.elements, b * 16),
      ); // 4 columns = 4 texels
      rows.push(row);
    }
  }
  const data = new Float32Array(width * 4 * rows.length);
  rows.forEach((r, i) => data.set(r, i * width * 4));
  return { data, width, height: rows.length, clips: index };
}
