import { describe, expect, it } from "vitest";
import { sunLook } from "../sun";
import {
  ease,
  flicker,
  HALL_EXPOSURE,
  insideHall,
  lampsOutside,
  zoneExposure,
} from "./hall";

// scene.castle-throne's hall in glTF: plan x -6..16, y -7..7 -> z -7..7, up to 8 m
const HALL = { min: [-6, -0.5, -7], max: [16, 8, 7] };

describe("castle hall", () => {
  it("counts the camera in only 0.3 m past the door line, and out only 0.3 m past it", () => {
    expect(insideHall([-5.9, 2, 0], HALL, false)).toBe(false);
    expect(insideHall([-5.6, 2, 0], HALL, false)).toBe(true);
    expect(insideHall([-6.1, 2, 0], HALL, true)).toBe(true);
    expect(insideHall([-6.4, 2, 0], HALL, true)).toBe(false);
    expect(insideHall([5, 9, 0], HALL, true)).toBe(false); // above the roof
  });

  it("eases across the threshold in about a second", () => {
    let v = 0;
    for (let i = 0; i < 60; i++) v = ease(v, 1, 1 / 60);
    expect(v).toBeGreaterThan(0.9);
    expect(v).toBeLessThan(1);
    expect(ease(0.5, 1, 0)).toBe(0.5);
  });

  it("opens up by day inside and changes nothing at night", () => {
    const noon = sunLook(72).exposure;
    expect(zoneExposure(noon, 1)).toBeCloseTo(HALL_EXPOSURE() / noon, 5);
    expect(zoneExposure(noon, 1)).toBeGreaterThan(2);
    expect(zoneExposure(noon, 0)).toBe(1);
    expect(zoneExposure(sunLook(-20).exposure, 1)).toBeCloseTo(1, 5);
  });

  it("lights the courtyard's braziers at sunset, not by day", () => {
    expect(lampsOutside(0.5)).toBe(0);
    expect(lampsOutside(0.06)).toBe(0);
    expect(lampsOutside(-0.04)).toBe(1);
    expect(lampsOutside(0.01)).toBeCloseTo(0.5, 5);
  });

  it("flickers by a few per cent", () => {
    for (let t = 0; t < 20; t += 0.37) {
      expect(Math.abs(flicker(t, 3) - 1)).toBeLessThan(0.06);
    }
  });
});
