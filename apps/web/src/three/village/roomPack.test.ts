import { describe, expect, it } from "vitest";
import { hallBox, interiorBase, personLight } from "./roomPack";

describe("village interior", () => {
  it("sits next to the village's pack", () => {
    expect(interiorBase("/scenes/0a1b2c3d/village/")).toBe(
      "/scenes/0a1b2c3d/village-interior/",
    );
    expect(interiorBase("/scenes/village/")).toBe("/scenes/village-interior/");
  });
  it("reaches the sky-free box past the room's walls", () => {
    const b = hallBox({ min: [-13.55, 0, 8.95], max: [-2.45, 3.6, 13.55] });
    expect(b.min[0]).toBeCloseTo(-13.75);
    expect(b.max[2]).toBeCloseTo(13.75);
  });
  it("lights a person mostly from the nearest floor probe, less than the floor", () => {
    const probes = {
      door: {
        pos: [-8, 0, 9.4] as [number, number, number],
        rgb: [1, 1, 1] as [number, number, number],
      },
      west: {
        pos: [-11.5, 0, 11.4] as [number, number, number],
        rgb: [0, 0, 0] as [number, number, number],
      },
    };
    const atDoor = personLight(probes, -8, 9.4);
    const between = personLight(probes, -9.75, 10.4);
    expect(atDoor[0]).toBeGreaterThan(0.5);
    expect(atDoor[0]).toBeLessThanOrEqual(0.6);
    expect(between[0]).toBeCloseTo(0.3, 1);
  });
});
