// The crowd without a GPU (F-4): where people stand, the baked motions, and the staging's verbs on a clock.
import { Matrix4, type InstancedBufferGeometry } from "three";
import { describe, expect, it } from "vitest";
import { body, COSTUMES } from "./bodies";
import { Crowd } from "./Crowd";
import { bake, BONES, CLIPS, FPS, skinMatrices } from "./rig";
import { inPolygon, scatter, toPath, type Plan } from "./scatter";

const ZONE: Plan[] = [
  [0, 0],
  [8, 0],
  [8, 6],
  [0, 6],
];

describe("scatter", () => {
  it("puts them in the zone, at the gap, out of the clear areas, the same for the same seed", () => {
    const clear = [{ at: [4, 3] as Plan, r: 1.5 }];
    const a = scatter(ZONE, 20, { seed: 7, gap: 0.75, clear });
    expect(a).toHaveLength(20);
    for (const p of a) {
      expect(inPolygon(p, ZONE)).toBe(true);
      expect(Math.hypot(p[0] - 4, p[1] - 3)).toBeGreaterThanOrEqual(1.5);
      for (const q of a)
        if (q !== p)
          expect(Math.hypot(p[0] - q[0], p[1] - q[1])).toBeGreaterThanOrEqual(
            0.75,
          );
    }
    expect(scatter(ZONE, 20, { seed: 7, gap: 0.75, clear })).toEqual(a);
    expect(scatter(ZONE, 20, { seed: 8, gap: 0.75, clear })).not.toEqual(a);
  });

  it("toPath: the distance to a polyline and the side", () => {
    const path: Plan[] = [
      [0, 0],
      [10, 0],
    ];
    expect(toPath([5, 2], path)).toMatchObject({ d: 2, side: 1 });
    expect(toPath([5, -1], path)).toMatchObject({ d: 1, side: -1 });
  });
});

describe("the baked motions", () => {
  it("no rotation is the bind pose: every skin matrix is the identity", () => {
    for (const m of skinMatrices({ rot: {} }))
      expect(m.equals(new Matrix4())).toBe(true);
  });

  it("one row per frame, nine bones of four texels; the loops close on themselves", () => {
    const b = bake();
    expect(b.width).toBe(BONES.length * 4);
    const frames = CLIPS.reduce((n, c) => n + Math.round(c.seconds * FPS), 0);
    expect(b.height).toBe(frames);
    expect(b.data).toHaveLength(b.width * 4 * frames);
    for (const c of CLIPS.filter((c) => c.loop)) {
      const first = skinMatrices(c.pose(0));
      const after = skinMatrices(c.pose(c.seconds));
      first.forEach((m, i) =>
        m.elements.forEach((x, k) =>
          expect(after[i]!.elements[k]).toBeCloseTo(x, 5),
        ),
      );
    }
  });

  it("one-shot motions end where they began (back to standing)", () => {
    const stir = CLIPS.find((c) => c.name === "stir")!;
    const a = skinMatrices(stir.pose(0));
    const z = skinMatrices(stir.pose(stir.seconds));
    a.forEach((m, i) =>
      m.elements.forEach((x, k) => expect(z[i]!.elements[k]).toBeCloseTo(x, 3)),
    );
  });

  it("each costume: every vertex has two bones whose weights add to 1, and a colour part", () => {
    for (const c of COSTUMES) {
      const g = body(c);
      const w = g.getAttribute("skinWeight");
      const part = g.getAttribute("aPart");
      for (let i = 0; i < w.count; i++) {
        expect(w.getX(i) + w.getY(i)).toBeCloseTo(1, 6);
        expect([0, 1, 2]).toContain(part.getX(i));
      }
      expect(g.getAttribute("position").count / 3).toBeLessThan(1000); // stand-in: well under A-0's 3k
    }
  });
});

describe("Crowd", () => {
  const spec = {
    zone: ZONE,
    facing: [4, 20] as Plan,
    count: 20,
    seed: 3,
  };

  it("twenty people, three draw calls; nobody sways in step", () => {
    const c = new Crowd(spec);
    expect(c.people).toHaveLength(20);
    expect(c.meshes.filter(Boolean).length).toBeLessThanOrEqual(3);
    const starts = new Set(
      c.meshes.flatMap((m) => {
        const a = m.geometry.getAttribute("iClip");
        const n = (m.geometry as InstancedBufferGeometry).instanceCount;
        return Array.from({ length: n }, (_, i) => a.getZ(i).toFixed(3));
      }),
    );
    expect(starts.size).toBe(20);
    expect(new Set(c.people.map((p) => p.speed.toFixed(3))).size).toBe(20);
  });

  it("どよめき spreads outwards from where it starts, then they sway again", () => {
    const c = new Crowd(spec);
    c.update(10);
    c.wave([0, 0], 4);
    const near = c.people
      .map((p, i) => ({ i, d: Math.hypot(p.at[0], p.at[1]) }))
      .sort((a, b) => a.d - b.d);
    c.update(10 + near[0]!.d / 4 + 0.3);
    expect(c.clips()[near[0]!.i]).toBe("stir");
    expect(c.clips()[near.at(-1)!.i]).toBe("sway");
    c.update(10 + near.at(-1)!.d / 4 + 0.3);
    expect(c.clips()[near.at(-1)!.i]).toBe("stir");
    c.update(20);
    expect(c.clips().every((x) => x === "sway")).toBe(true);
  });

  it("the cheer reaches everyone within half a second", () => {
    const c = new Crowd(spec);
    c.update(5);
    c.cheer();
    c.update(5.5);
    expect(c.clips().every((x) => x === "cheer")).toBe(true);
  });

  it("making way: the people near the path turn to it and end up further from it; the others stay", () => {
    const c = new Crowd(spec);
    c.update(1);
    const path: Plan[] = [
      [4, -1],
      [4, 7],
    ];
    const before = c.people.map((p) => toPath(p.at, path).d);
    c.part(path, 2);
    c.update(1.5);
    c.update(3);
    c.people.forEach((p, i) => {
      const d = toPath(p.at, path).d;
      if (before[i]! < 2) {
        expect(d).toBeGreaterThan(before[i]!);
        expect(p.clip).toMatch(/^turn[LR]$/);
      } else {
        expect(d).toBeCloseTo(before[i]!, 6);
        expect(p.clip).toBe("sway");
      }
    });
  });
});
