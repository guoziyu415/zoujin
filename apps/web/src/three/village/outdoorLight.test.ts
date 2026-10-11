import { describe, expect, it } from "vitest";
import { clearLights, outdoorMix, type ClearRow } from "./outdoorLight";

// scene.json lightSets (#251)
const clear: ClearRow[] = [
  { from: "06:00", to: "17:00", outdoor: ["day"] },
  { from: "17:00", to: "18:30", outdoor: ["day", "sunset"] },
  { from: "18:30", to: "18:45", outdoor: ["sunset"] },
  { from: "18:45", to: "20:00", outdoor: ["sunset", "night"] },
  { from: "20:00", to: "04:00", outdoor: ["night"] },
  { from: "04:00", to: "06:00", outdoor: ["night", "day"] },
];
const sets = {
  clear,
  rain: { outdoor: ["rain"], indoor: "feast", dimAtNight: true },
};

describe("the village's baked light outside (F-11 card 5)", () => {
  it("reads the clock off the pack's table, past midnight too", () => {
    expect(clearLights(clear, 1440 + 600)).toEqual({
      a: "day",
      b: "day",
      w: 0,
    });
    expect(clearLights(clear, 1440 + 1065).w).toBeCloseTo(0.5); // 17:45
    expect(clearLights(clear, 1440 + 1380).a).toBe("night"); // 23:00
    expect(clearLights(clear, 2880 + 60).a).toBe("night"); // 01:00
    expect(clearLights(clear, 2880 + 300)).toMatchObject({
      a: "night",
      b: "day",
      w: 0.5,
    });
  });

  it("the day leaves the sky live; the bake comes in towards the evening", () => {
    expect(outdoorMix(sets, 1440 + 600, 0).share).toBe(0);
    expect(outdoorMix(sets, 1440 + 1065, 0).share).toBeCloseTo(0.5);
    expect(outdoorMix(sets, 1440 + 1380, 0).share).toBe(1);
  });

  it("the rain takes over with the clouds, darker at night", () => {
    const noon = outdoorMix(sets, 2880 + 780, 1);
    expect(noon).toMatchObject({ b: "rain", w: 1, kb: 1, share: 1 });
    expect(outdoorMix(sets, 2880 + 780, 0.5).share).toBeCloseTo(0.5);
    expect(outdoorMix(sets, 2880 + 1380, 1).kb).toBeCloseTo(0.05);
  });
});
