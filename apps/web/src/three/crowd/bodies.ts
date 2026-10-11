// The crowd's three costumes (ux style guide ending-cast.md「刑場の群衆」) as stand-in low-poly bodies, for a scene
// whose pack has no crowd (the real bodies are MPFB's, pack.ts): 1 a man in a long tunic and a mantle, 2 a woman with the mantle drawn over her head, 3 a working
// man in a short tunic (both shoulders covered) and a low round felt cap. Nothing from the 「不放」 list: no
// wide-brimmed hat, no hood with a stick, no cone hat or pole, no bare chest. Each vertex says which bones move it
// (two at most) and which colour it takes: 0 skin, 1 the main cloth, 2 the second cloth (per instance, shader.ts).
// The shapes are written out here rather than taken from three's geometry classes: those would land in the shared
// 3D chunk, which has no room (frontend-design 10.1).
import { BufferAttribute, InstancedBufferGeometry } from "three";
import { BONE, type Role as Bone } from "./rig";

export type Costume = "mantle" | "veil" | "worker";
export const COSTUMES: Costume[] = ["mantle", "veil", "worker"];

type Weights = (y: number) => [Bone, Bone, number]; // the two bones and the first one's weight at this height

const rigid =
  (b: Bone): Weights =>
  () => [b, b, 1];
// between two bones, by height: all `lo` below y0, all `hi` above y1
const blend =
  (lo: Bone, hi: Bone, y0: number, y1: number): Weights =>
  (y) => [lo, hi, 1 - Math.min(1, Math.max(0, (y - y0) / (y1 - y0)))];

// triangles: positions and normals, three numbers a vertex
type Geo = { pos: number[]; nor: number[] };
type Part = { geo: Geo; w: Weights; colour: 0 | 1 | 2 };

function quads(
  rows: number,
  cols: number,
  at: (i: number, j: number) => { p: number[]; n: number[] },
): Geo {
  const pos: number[] = [];
  const nor: number[] = [];
  const put = (i: number, j: number) => {
    const v = at(i, j);
    pos.push(...v.p);
    nor.push(...v.n);
  };
  for (let i = 0; i < rows; i++)
    for (let j = 0; j < cols; j++) {
      put(i, j);
      put(i + 1, j);
      put(i + 1, j + 1);
      put(i, j);
      put(i + 1, j + 1);
      put(i, j + 1);
    }
  return { pos, nor };
}

// an open frustum between two heights, centred on (x, z), radii at the bottom and the top, squashed by sx, sz
function tube(
  y0: number,
  y1: number,
  r0: number,
  r1: number,
  o: { x?: number; z?: number; seg?: number; sx?: number; sz?: number } = {},
): Geo {
  const seg = o.seg ?? 8;
  const [sx, sz] = [o.sx ?? 1, o.sz ?? 1];
  const slope = (r0 - r1) / (y1 - y0);
  return quads(1, seg, (i, j) => {
    const a = (j / seg) * Math.PI * 2;
    const r = i ? r0 : r1; // row 0 at the top, so the triangles wind counter-clockwise seen from outside
    const [c, s] = [Math.sin(a), Math.cos(a)]; // j = 0 at the front (+Z)
    const n = [c / sx, slope, s / sz];
    const l = Math.hypot(n[0]!, n[1]!, n[2]!);
    return {
      p: [(o.x ?? 0) + c * r * sx, i ? y0 : y1, (o.z ?? 0) + s * r * sz],
      n: n.map((x) => x / l),
    };
  });
}

// an ellipsoid of radius r scaled by s, centred at (x, y, z)
function ball(
  r: number,
  x: number,
  y: number,
  z: number,
  s: [number, number, number] = [1, 1, 1],
): Geo {
  return quads(6, 8, (i, j) => {
    const th = (i / 6) * Math.PI;
    const ph = (j / 8) * Math.PI * 2;
    const u = [
      Math.sin(th) * Math.sin(ph),
      Math.cos(th),
      Math.sin(th) * Math.cos(ph),
    ];
    const n = [u[0]! / s[0], u[1]! / s[1], u[2]! / s[2]];
    const l = Math.hypot(n[0]!, n[1]!, n[2]!) || 1;
    return {
      p: [x + u[0]! * r * s[0], y + u[1]! * r * s[1], z + u[2]! * r * s[2]],
      n: n.map((v) => v / l),
    };
  });
}

function arms(sleeve: 0 | 1 | 2): Part[] {
  return ([1, -1] as const).flatMap((s): Part[] => {
    const [arm, fore] =
      s > 0 ? (["armL", "foreL"] as const) : (["armR", "foreR"] as const);
    return [
      {
        geo: tube(1.12, 1.44, 0.05, 0.06, { x: 0.195 * s, seg: 6 }),
        w: rigid(arm),
        colour: sleeve,
      },
      {
        geo: tube(0.9, 1.16, 0.035, 0.045, { x: 0.2 * s, seg: 6 }),
        w: rigid(fore),
        colour: 0,
      },
      {
        geo: ball(0.045, 0.2 * s, 0.86, 0.01, [0.8, 1.2, 0.6]),
        w: rigid(fore),
        colour: 0,
      },
    ];
  });
}

const head = (): Part => ({
  geo: ball(0.11, 0, 1.6, 0.01, [0.9, 1.1, 1]),
  w: rigid("head"),
  colour: 0,
});
const neck = (): Part => ({
  geo: tube(1.44, 1.53, 0.05, 0.045, { seg: 6 }),
  w: blend("chest", "head", 1.46, 1.53),
  colour: 0,
});
const torso = (colour: 0 | 1 | 2, top = 1.44): Part => ({
  geo: tube(0.92, top, 0.17, 0.2, { sz: 0.7 }),
  w: (y) =>
    y < 1.15
      ? blend("hips", "spine", 0.95, 1.15)(y)
      : blend("spine", "chest", 1.15, 1.35)(y),
  colour,
});
const shoulders = (colour: 0 | 1 | 2): Part => ({
  geo: tube(1.36, 1.47, 0.21, 0.08, { sz: 0.65 }),
  w: blend("chest", "neck", 1.44, 1.47),
  colour,
});

const BUILD: Record<Costume, () => Part[]> = {
  mantle: () => [
    {
      geo: tube(0.02, 0.95, 0.27, 0.18, { sz: 0.75 }),
      w: rigid("hips"),
      colour: 1,
    },
    torso(1),
    shoulders(1),
    // the mantle: wrapped over the left shoulder and down across the body
    {
      geo: tube(0.55, 1.42, 0.25, 0.22, { sz: 0.8, x: 0.02 }),
      w: (y) =>
        y < 1.1
          ? blend("hips", "spine", 0.8, 1.1)(y)
          : blend("spine", "chest", 1.1, 1.35)(y),
      colour: 2,
    },
    neck(),
    head(),
    ...arms(1),
  ],
  veil: () => [
    {
      geo: tube(0.02, 0.95, 0.26, 0.17, { sz: 0.75 }),
      w: rigid("hips"),
      colour: 1,
    },
    torso(1, 1.4),
    // the mantle drawn up over the head: a hood down to the shoulders
    {
      geo: tube(1.2, 1.5, 0.24, 0.12, { sz: 0.75 }),
      w: blend("chest", "neck", 1.4, 1.5),
      colour: 2,
    },
    {
      geo: ball(0.135, 0, 1.62, -0.015, [1, 1.12, 1.05]),
      w: rigid("head"),
      colour: 2,
    },
    {
      geo: ball(0.085, 0, 1.59, 0.06, [0.9, 1.1, 0.6]),
      w: rigid("head"),
      colour: 0,
    },
    ...arms(2),
  ],
  worker: () => [
    // legs below the knee-length tunic
    {
      geo: tube(0.02, 0.6, 0.045, 0.06, { x: 0.09, seg: 6 }),
      w: rigid("hips"),
      colour: 0,
    },
    {
      geo: tube(0.02, 0.6, 0.045, 0.06, { x: -0.09, seg: 6 }),
      w: rigid("hips"),
      colour: 0,
    },
    {
      geo: tube(0.5, 0.95, 0.24, 0.18, { sz: 0.75 }),
      w: rigid("hips"),
      colour: 1,
    },
    torso(1),
    shoulders(1),
    neck(),
    head(),
    // the low round felt cap
    {
      geo: tube(1.64, 1.71, 0.115, 0.1, { z: -0.005 }),
      w: rigid("head"),
      colour: 2,
    },
    ...arms(1),
  ],
};

export function body(c: Costume): InstancedBufferGeometry {
  const parts = BUILD[c]();
  const pos: number[] = [];
  const nor: number[] = [];
  const idx: number[] = [];
  const wts: number[] = [];
  const col: number[] = [];
  for (const p of parts) {
    pos.push(...p.geo.pos);
    nor.push(...p.geo.nor);
    for (let i = 1; i < p.geo.pos.length; i += 3) {
      const [a, b, wa] = p.w(p.geo.pos[i]!);
      idx.push(BONE[a], BONE[b], 0, 0);
      wts.push(wa, 1 - wa, 0, 0);
      col.push(p.colour);
    }
  }
  const g = new InstancedBufferGeometry();
  g.setAttribute("position", new BufferAttribute(new Float32Array(pos), 3));
  g.setAttribute("normal", new BufferAttribute(new Float32Array(nor), 3));
  g.setAttribute("skinIndex", new BufferAttribute(new Uint8Array(idx), 4));
  g.setAttribute("skinWeight", new BufferAttribute(new Float32Array(wts), 4));
  g.setAttribute("aPart", new BufferAttribute(new Float32Array(col), 1));
  return g;
}
