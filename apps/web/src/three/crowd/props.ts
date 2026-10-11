// The cast's things in their hands (F-4 range 5, ux style guide ending-cast.md): the guards' spear (about 2.4 m, a
// wooden shaft, an iron head, held upright, the head above everyone's) on the working man's body, and the scarlet-cloak
// maiden's bundle of cloth on the veiled woman's. Made here and added to the pack's body, rigid on a hand bone, so they
// cost no draw call of their own; the shader folds them away on everyone who doesn't carry them (shader.ts iScale.w).
// Parts: 6 the shaft, 7 the spear's head, 8 the bundle.
export const SHAFT = 6;
export const SPEARHEAD = 7;
export const BUNDLE = 8;

type Vec3 = [number, number, number];
export type Prop = {
  position: number[];
  normal: number[]; // unit
  index: number[];
  part: number[];
};

const SEG = 6;

// an upright tube or cone from y0 to y1 round (x, z), radius r0 at the bottom and r1 at the top (closed when r1 is 0)
function upright(
  out: Prop,
  [x, z]: [number, number],
  y0: number,
  y1: number,
  r0: number,
  r1: number,
  part: number,
): void {
  const base = out.position.length / 3;
  const slope = (r0 - r1) / (y1 - y0);
  for (let i = 0; i < SEG; i++) {
    const a = (i / SEG) * Math.PI * 2;
    const [c, s] = [Math.cos(a), Math.sin(a)];
    const k = 1 / Math.hypot(1, slope);
    for (const [y, r] of [
      [y0, r0],
      [y1, r1],
    ] as const) {
      out.position.push(x + c * r, y, z + s * r);
      out.normal.push(c * k, slope * k, s * k);
      out.part.push(part);
    }
  }
  for (let i = 0; i < SEG; i++) {
    const a = base + i * 2;
    const b = base + ((i + 1) % SEG) * 2;
    out.index.push(a, a + 1, b + 1, a, b + 1, b);
  }
}

// a rough ball of cloth: radii (rx, ry, rz) round c
function bundle(out: Prop, c: Vec3, [rx, ry, rz]: Vec3): void {
  const base = out.position.length / 3;
  const rows = 4;
  for (let j = 0; j <= rows; j++) {
    const v = (j / rows) * Math.PI;
    for (let i = 0; i < SEG; i++) {
      const u = (i / SEG) * Math.PI * 2;
      const n: Vec3 = [
        Math.sin(v) * Math.cos(u),
        Math.cos(v),
        Math.sin(v) * Math.sin(u),
      ];
      out.position.push(c[0] + n[0] * rx, c[1] + n[1] * ry, c[2] + n[2] * rz);
      out.normal.push(...n);
      out.part.push(BUNDLE);
    }
  }
  for (let j = 0; j < rows; j++)
    for (let i = 0; i < SEG; i++) {
      const a = base + j * SEG + i;
      const b = base + j * SEG + ((i + 1) % SEG);
      out.index.push(a, b + SEG, a + SEG, a, b, b + SEG); // counter-clockwise seen from outside
    }
}

// the spear in the hand at `hand` (the wrist joint at rest): through the fist a little under and in front of it, from
// just off the ground to 2.4 m
export function spear(hand: Vec3): Prop {
  const out: Prop = { position: [], normal: [], index: [], part: [] };
  const at: [number, number] = [hand[0], hand[2] + 0.03];
  upright(out, at, 0.04, 2.2, 0.016, 0.014, SHAFT);
  upright(out, at, 2.2, 2.42, 0.028, 0, SPEARHEAD);
  return out;
}

// the bundle held against the side at `hand`
export function cloth(hand: Vec3): Prop {
  const out: Prop = { position: [], normal: [], index: [], part: [] };
  bundle(
    out,
    [hand[0] * 0.8, hand[1] + 0.02, hand[2] + 0.07],
    [0.09, 0.11, 0.1],
  );
  return out;
}
