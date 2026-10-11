import { describe, expect, it } from "vitest";
import {
  blinkAt,
  CAST,
  castName,
  castUrl,
  clipRate,
  gaitWeights,
  mouthWeights,
  seedOf,
} from "./cast";

describe("cast (F-16)", () => {
  it("maps the seven characters and roles to their built names", () => {
    expect(Object.keys(CAST)).toHaveLength(12);
    expect(castName("char.king")).toBe("king");
    expect(castName("role.shepherd-boy")).toBe("shepherd-boy");
    expect(castName("char.melos")).toBe("melos"); // A-0's own file, exported the same way
    expect(castName("role.traveler")).toBe("traveler");
    expect(castName("char.crowd")).toBeNull();
  });

  it("dresses the bride and groom for the wedding", () => {
    expect(castName("char.sister", true)).toBe("sister-wedding");
    expect(castName("char.groom", true)).toBe("groom-wedding");
    expect(castName("char.king", true)).toBe("king");
  });

  it("serves the files from /cast/", () => {
    expect(castUrl("king", "walk")).toBe("/cast/king/walk.glb");
    expect(castUrl("sister", "talk_std")).toBe("/cast/sister/talk_std.glb");
  });

  it("blends idle, walk and run by speed, the weights adding up to one", () => {
    for (const v of [0, 0.1, 0.5, 1.4, 2.5, 3.2, 6]) {
      const g = gaitWeights(v);
      expect(g.idle + g.walk + g.run).toBeCloseTo(1);
    }
    expect(gaitWeights(0).idle).toBe(1);
    expect(gaitWeights(1.4).walk).toBe(1);
    expect(gaitWeights(3.2).run).toBe(1);
  });

  it("plays the clips at the ground speed, within limits", () => {
    expect(clipRate("walk", 0.99)).toBeCloseTo(1);
    expect(clipRate("run", 3.2)).toBeCloseTo(3.2 / 3.76);
    expect(clipRate("walk", 10)).toBe(1.6);
  });

  it("keeps the mouth shut in silence and opens it with the voice", () => {
    const quiet = mouthWeights(0, 1);
    expect(Object.values(quiet).every((x) => x === 0)).toBe(true);
    const loud = mouthWeights(1, 1);
    expect(loud.jawOpen).toBeGreaterThan(0.3);
    for (const x of Object.values(loud)) expect(x).toBeLessThanOrEqual(1);
  });

  it("blinks briefly, each person on their own rhythm", () => {
    const seed = seedOf("char.king");
    let closed = 0;
    for (let t = 0; t < 10; t += 0.01) if (blinkAt(t, seed) > 0.5) closed++;
    expect(closed).toBeGreaterThan(0);
    expect(closed).toBeLessThan(40); // under 0.4 s of 10 s
    expect(seedOf("char.king")).not.toBe(seedOf("char.groom"));
  });
});
