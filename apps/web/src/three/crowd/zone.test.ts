import { describe, expect, it } from "vitest";
import type { LoadedScene } from "../scene/loadScene";
import { scatter, type Plan } from "./scatter";
import { crowdSpec, GAP } from "./zone";

// the plaza's execution ground as built (scene.json of the current plaza: the place polygon and the spots, x/y/z)
const POLY: Plan[] = [
  [0.145, -3.603],
  [-0.778, -11.69],
  [-10.081, -18.449],
  [-20.661, -3.887],
  [-11.358, 2.873],
  [-3.381, 1.251],
];
const SPOTS: Record<string, [number, number, number]> = {
  stake: [-8.42, 1.2, -6.1],
  "gate-inside": [25.08, 0, 18.22],
  "king-west": [-3.6, 0, -0.15],
  scaffold: [-8.55, 1.2, -5.41],
  "stake-front": [-6.15, 0, -4.47],
  "stake-front-side": [-5.64, 0, -5.33],
  "crowd-front": [-7.9, 0, -3.76],
  "ground-west": [-1.77, 0, -4.37],
};
const scene = {
  manifest: {
    places: [{ id: "place.execution-ground", polygon: POLY }],
    spots: Object.fromEntries(
      Object.entries(SPOTS).map(([k, pos]) => [k, { pos }]),
    ),
  },
  nav: { nearest: () => ({ y: 0 }) },
} as unknown as LoadedScene;

describe("where the crowd stands (UX on #148: a wall of people in front of the scaffold)", () => {
  it.each([1, 2, 3])(
    "seed %i: all 24 stand, a gap apart, off the scaffold and its steps, in front of the post",
    (seed) => {
      const spec = crowdSpec(scene, 24, seed)!;
      const at = scatter(spec.zone, 24, { ...spec, keep: spec.keep! });
      expect(at).toHaveLength(24);
      for (const [i, p] of at.entries()) {
        expect(spec.keep!(p)).toBe(true);
        for (const q of at.slice(i + 1))
          expect(Math.hypot(p[0] - q[0], p[1] - q[1])).toBeGreaterThanOrEqual(
            GAP,
          );
      }
      // most of them within 3 m of the line from the post to the gate: rows in front of the post, not spread wide
      const [sx, , sz] = SPOTS.stake!;
      const [gx, , gz] = SPOTS["gate-inside"]!;
      const len = Math.hypot(gx - sx, gz - sz);
      const side = ([x, z]: Plan) =>
        Math.abs(((z - sz) * (gx - sx) - (x - sx) * (gz - sz)) / len);
      expect(at.filter((p) => side(p) < 3).length).toBeGreaterThanOrEqual(16);
    },
  );

  it("nobody on the scaffold or its steps", () => {
    const keep = crowdSpec(scene, 24)!.keep!;
    // just in front of the post, and on the steps' foot (0.8 m and 2.0 m towards the gate from the stake spot)
    const [sx, , sz] = SPOTS.stake!;
    const [gx, , gz] = SPOTS["gate-inside"]!;
    const len = Math.hypot(gx - sx, gz - sz);
    const ahead = (d: number): Plan => [
      sx + ((gx - sx) / len) * d,
      sz + ((gz - sz) / len) * d,
    ];
    expect(keep(ahead(0.8))).toBe(false);
    expect(keep(ahead(2.0))).toBe(false);
    expect(keep(ahead(3.2))).toBe(true);
  });
});
