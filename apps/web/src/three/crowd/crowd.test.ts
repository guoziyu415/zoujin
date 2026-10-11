// The crowd without a GPU (F-4): where people stand, the baked motions, and the staging's verbs on a clock.
import {
  Matrix4,
  type InstancedBufferGeometry,
  type MeshStandardMaterial,
} from "three";
import { describe, expect, it } from "vitest";
import { body, COSTUMES } from "./bodies";
import { Crowd } from "./Crowd";
import { parseCrowdPack, type CrowdPackJson } from "./pack";
import {
  bake,
  BONES,
  CLIPS,
  FPS,
  packSkeleton,
  skinMatrices,
  STAND_IN,
} from "./rig";
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
  it("no rotation is the rest pose; on a skeleton whose rest is its bind pose every skin matrix is the identity", () => {
    for (const m of skinMatrices({ rot: {} }, { ...STAND_IN, rest: {} }))
      expect(m.equals(new Matrix4())).toBe(true);
    // the stand-in's arms hang out a little at rest
    const arm = skinMatrices({ rot: {} })[
      BONES.findIndex((b) => b.name === "armL")
    ]!;
    expect(arm.equals(new Matrix4())).toBe(false);
  });

  it("MPFB's skeleton: the roles find their bones, and the sway leaves the legs where they stand", () => {
    const skel = packSkeleton(MPFB_BONES, MPFB_JOINTS);
    expect(skel.roles).toMatchObject({ hips: 1, chest: 2, armL: 3 });
    for (const c of CLIPS.filter((c) => c.name !== "cheer")) {
      const m = skinMatrices(c.pose(1.3), skel);
      expect(m[0]!.equals(new Matrix4())).toBe(true); // pelvis
      expect(m[4]!.equals(new Matrix4())).toBe(true); // thigh_l
    }
    const sway = skinMatrices(CLIPS[0]!.pose(1), skel);
    expect(sway[1]!.equals(new Matrix4())).toBe(false); // spine_01 moves
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

  it("each stand-in costume: every vertex has two bones whose weights add to 1, and a colour part", () => {
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

// a small MPFB-like skeleton: pelvis, spine_01, spine_03, upperarm_l, thigh_l
const MPFB_BONES = [
  { name: "pelvis", parent: -1 },
  { name: "spine_01", parent: 0 },
  { name: "spine_03", parent: 1 },
  { name: "upperarm_l", parent: 2 },
  { name: "thigh_l", parent: 0 },
];
const MPFB_JOINTS: [number, number, number][] = [
  [0, 0.93, 0],
  [0, 1.02, -0.03],
  [0, 1.15, -0.03],
  [0.19, 1.39, 0.02],
  [0.11, 0.92, 0],
];

// a pack as build_crowd.py writes it: one triangle (plus a spare vertex) a costume
function tinyPack(): { json: CrowdPackJson; bin: ArrayBuffer } {
  const n = 4;
  const per = 4 * (Math.ceil((n * 29) / 4) + Math.ceil((3 * 2) / 4)); // vertex arrays, then indices, each padded to 4
  const bin = new ArrayBuffer(per * 3);
  const costumes = {} as CrowdPackJson["costumes"];
  COSTUMES.forEach((c, k) => {
    const offset = k * per;
    const pos = new Float32Array(bin, offset, n * 3);
    pos.set([0, 0, 0, 0.5, 0, 0, 0, 1.7, 0, 0.2, 1.4, 0.1]);
    const nor = new Int16Array(bin, offset + n * 12, n * 4);
    for (let v = 0; v < n; v++) nor.set([0, 0, 32767, 0], v * 4);
    const idx = new Uint8Array(bin, offset + n * 20, n * 4);
    idx.set([0, 0, 0, 0, 4, 0, 0, 0, 3, 2, 0, 0, 1, 2, 3, 0]);
    const w = new Uint8Array(bin, offset + n * 24, n * 4);
    w.set([255, 0, 0, 0, 255, 0, 0, 0, 200, 55, 0, 0, 85, 85, 85, 0]);
    new Uint8Array(bin, offset + n * 28, n).set([1, 0, 2, 3]);
    const indexOffset = offset + Math.ceil((n * 29) / 4) * 4;
    new Uint16Array(bin, indexOffset, 3).set([0, 1, 2]);
    costumes[c] = {
      vertices: n,
      offset,
      indices: 3,
      indexOffset,
      joints: MPFB_JOINTS,
    };
  });
  return {
    json: {
      format: "zoujin-crowd-1",
      bones: MPFB_BONES,
      costumes,
      bytes: bin.byteLength,
    },
    bin,
  };
}

describe("the crowd pack", () => {
  it("reads build_crowd.py's layout into attributes", () => {
    const { json, bin } = tinyPack();
    const pack = parseCrowdPack(json, bin);
    const g = pack.veil.geometry;
    expect(g.getAttribute("position").getY(2)).toBeCloseTo(1.7, 6);
    expect(g.getAttribute("normal").getZ(3)).toBeCloseTo(1, 4);
    expect(g.getAttribute("skinIndex").getX(1)).toBe(4);
    const w = g.getAttribute("skinWeight");
    expect(w.getX(2) + w.getY(2)).toBeCloseTo(1, 6);
    expect(g.getAttribute("aPart").getX(3)).toBe(3);
    expect(Array.from(g.index!.array)).toEqual([0, 1, 2]);
    expect(pack.veil.skeleton.joints).toHaveLength(MPFB_BONES.length);
  });

  it("a pack of another size or format is refused", () => {
    const { json, bin } = tinyPack();
    expect(() => parseCrowdPack({ ...json, bytes: 1 }, bin)).toThrow();
    expect(() => parseCrowdPack({ ...json, format: "x" }, bin)).toThrow();
  });

  it("a crowd from the pack: each costume's motions baked on its own skeleton", () => {
    const { json, bin } = tinyPack();
    const c = new Crowd(
      { zone: ZONE, facing: [4, 20], count: 12, seed: 2 },
      parseCrowdPack(json, bin),
    );
    expect(c.fromPack).toBe(true);
    for (const m of c.meshes.filter(Boolean)) {
      const u = (m.material as MeshStandardMaterial).userData.uniforms as {
        uBones: { value: { image: { width: number } } };
      };
      expect(u.uBones.value.image.width).toBe(MPFB_BONES.length * 4);
      expect(m.geometry.getAttribute("iHair")).toBeTruthy();
    }
    c.dispose();
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
