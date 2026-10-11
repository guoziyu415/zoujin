// The crowd pack (F-4 range 1): the three bodies from MPFB 2 that assets/pipeline/crowd/build.sh writes into the scene's
// pack as crowd/crowd.json (the bones, each body's joints, where its arrays sit) and crowd/crowd.bin (the arrays,
// laid out as crowd.json "layout" says). Read straight into buffer attributes: no glTF loader in this chunk. With them,
// when the pack has it, crowd/motions.json (build_motions.py): the standing motions from Quaternius's library on the
// nine roles, in place of the hand-made sway.
import { BufferAttribute, InstancedBufferGeometry } from "three";
import type { Costume } from "./bodies";
import { cloth, spear, type Prop } from "./props";
import { FPS, packSkeleton, type Clip, type Role, type Skeleton } from "./rig";

// what each body carries for the cast (props.ts): the spear in the right hand, the bundle on the left
const PROPS: Partial<Record<Costume, [string, (hand: Vec3) => Prop]>> = {
  worker: ["hand_r", spear],
  veil: ["hand_l", cloth],
};

type Vec3 = [number, number, number];
type Entry = {
  vertices: number;
  offset: number;
  indices: number;
  indexOffset: number;
  joints: Vec3[];
  fist?: [number, number, number, number, number][]; // finger bone, its bend axis (x, y, z) and angle at a fist
};
export type CrowdPackJson = {
  format: string;
  bones: { name: string; parent: number }[];
  costumes: Record<Costume, Entry>;
  bytes: number;
};

export type CrowdPack = Record<
  Costume,
  { geometry: InstancedBufferGeometry; skeleton: Skeleton }
>;

export function parseCrowdPack(
  json: CrowdPackJson,
  bin: ArrayBuffer,
): CrowdPack {
  if (json.format !== "zoujin-crowd-1" || bin.byteLength !== json.bytes)
    throw new Error("crowd pack: unknown format or size");
  const out = {} as CrowdPack;
  for (const [costume, c] of Object.entries(json.costumes) as [
    Costume,
    Entry,
  ][]) {
    const n = c.vertices;
    let at = c.offset;
    const take = <T>(
      make: (b: ArrayBuffer, o: number, len: number) => T,
      bytes: number,
      len: number,
    ): T => {
      const v = make(bin, at, len);
      at += bytes * len;
      return v;
    };
    const position = take((b, o, l) => new Float32Array(b, o, l), 4, n * 3);
    const padded = take((b, o, l) => new Int16Array(b, o, l), 2, n * 4); // x, y, z, pad
    const normal = new Int16Array(n * 3);
    for (let i = 0; i < n; i++)
      normal.set(padded.subarray(i * 4, i * 4 + 3), i * 3);
    const skinIndex = take((b, o, l) => new Uint8Array(b, o, l), 1, n * 4);
    const skinWeight = take((b, o, l) => new Uint8Array(b, o, l), 1, n * 4);
    const part = take((b, o, l) => new Uint8Array(b, o, l), 1, n);
    const index = new Uint16Array(bin, c.indexOffset, c.indices);
    const g = new InstancedBufferGeometry();
    const carry = PROPS[costume];
    const bone = carry ? json.bones.findIndex((b) => b.name === carry[0]) : -1;
    const joint = c.joints[bone];
    if (carry && joint) {
      // the body's arrays with the prop after them, rigid on the hand
      const prop = carry[1](joint);
      const m = prop.part.length;
      const grow = <
        T extends Float32Array | Int16Array | Uint8Array | Uint16Array,
      >(
        a: T,
        extra: ArrayLike<number>,
      ): T => {
        const out = new (a.constructor as new (n: number) => T)(
          a.length + extra.length,
        );
        out.set(a);
        out.set(extra, a.length);
        return out;
      };
      const snorm = prop.normal.map((v) => Math.round(v * 32767));
      g.setAttribute(
        "position",
        new BufferAttribute(grow(position, prop.position), 3),
      );
      g.setAttribute(
        "normal",
        new BufferAttribute(grow(normal, snorm), 3, true),
      );
      g.setAttribute(
        "skinIndex",
        new BufferAttribute(
          grow(
            skinIndex,
            Array.from({ length: m * 4 }, (_, i) => (i % 4 ? 0 : bone)),
          ),
          4,
        ),
      );
      g.setAttribute(
        "skinWeight",
        new BufferAttribute(
          grow(
            skinWeight,
            Array.from({ length: m * 4 }, (_, i) => (i % 4 ? 0 : 255)),
          ),
          4,
          true,
        ),
      );
      g.setAttribute("aPart", new BufferAttribute(grow(part, prop.part), 1));
      g.setIndex(
        new BufferAttribute(
          grow(
            index,
            prop.index.map((i) => i + n),
          ),
          1,
        ),
      );
    } else {
      g.setAttribute("position", new BufferAttribute(position, 3));
      g.setAttribute("normal", new BufferAttribute(normal, 3, true));
      g.setAttribute("skinIndex", new BufferAttribute(skinIndex, 4));
      g.setAttribute("skinWeight", new BufferAttribute(skinWeight, 4, true));
      g.setAttribute("aPart", new BufferAttribute(part, 1));
      g.setIndex(new BufferAttribute(index, 1));
    }
    out[costume] = {
      geometry: g,
      skeleton: packSkeleton(json.bones, c.joints, c.fist),
    };
  }
  return out;
}

// the scene's crowd, or null when its pack has none (the stand-ins then)
export async function loadCrowdPack(base: string): Promise<CrowdPack | null> {
  const res = await fetch(`${base}crowd/crowd.json`);
  if (!res.ok) return null;
  let json: CrowdPackJson;
  try {
    json = (await res.json()) as CrowdPackJson;
  } catch {
    return null; // a server that answers a missing file with the app's page
  }
  const bin = await fetch(`${base}crowd/crowd.bin`);
  if (!bin.ok) return null;
  return parseCrowdPack(json, await bin.arrayBuffer());
}

export type MotionsJson = {
  format: string;
  fps: number;
  roles: Role[];
  // each frame: the hips' offset, then each role's rotation (x, y, z)
  clips: Record<string, { seconds: number; loop: boolean; frames: number[][] }>;
};

export function parseMotions(json: MotionsJson): Clip[] {
  if (json.format !== "zoujin-crowd-motions-1" || json.fps !== FPS)
    throw new Error("crowd motions: unknown format");
  return Object.entries(json.clips).map(([name, c]) => ({
    name,
    seconds: c.seconds,
    loop: c.loop,
    pose: (t) => {
      const f = c.frames[Math.min(c.frames.length - 1, Math.round(t * FPS))]!;
      const v = (i: number) => [f[i]!, f[i + 1]!, f[i + 2]!] as Vec3;
      return {
        hips: v(0),
        rot: Object.fromEntries(json.roles.map((r, i) => [r, v(3 + i * 3)])),
      };
    },
  }));
}

// the pack's motions, or none (the hand-made ones then)
export async function loadMotions(base: string): Promise<Clip[]> {
  try {
    const res = await fetch(`${base}crowd/motions.json`);
    return res.ok ? parseMotions((await res.json()) as MotionsJson) : [];
  } catch {
    return [];
  }
}
