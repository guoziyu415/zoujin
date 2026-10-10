import { describe, expect, it } from "vitest";
import { planToWorld, worldToPlan } from "./scene/frame";
import { sunAt, sunLook } from "./sun";

// scene.json "sun" of scene.syracuse-square
const SUN = {
  latitudeDeg: 37,
  declinationDeg: 19,
  solarNoonMinute: 720,
  gateStreetAzimuthDeg: 294,
  sceneRotationDeg: 144,
};

describe("sun", () => {
  it("sets at about 19:00 (art-direction 3.1)", () => {
    expect(sunAt(1140, SUN).elevDeg).toBeGreaterThan(-1.5);
    expect(sunAt(1140, SUN).elevDeg).toBeLessThan(1.5);
    expect(sunAt(1050, SUN).elevDeg).toBeGreaterThan(10); // 17:30, act 1 starts in sunlight
    expect(sunAt(720, SUN).elevDeg).toBeCloseTo(90 - 37 + 19, 3);
  });

  it("goes down along the gate street (plan −x)", () => {
    const { dir } = sunAt(1135, SUN);
    const [px, py] = worldToPlan(dir[0], dir[2], SUN.sceneRotationDeg);
    expect(px).toBeLessThan(0);
    expect(Math.abs(py)).toBeLessThan(Math.abs(px));
  });

  it("matches the frame helper both ways", () => {
    const [x, , z] = planToWorld(3, -7, 0, 144);
    const [px, py] = worldToPlan(x, z, 144);
    expect(px).toBeCloseTo(3, 9);
    expect(py).toBeCloseTo(-7, 9);
  });

  it("dims the light and goes to day-for-night after sunset", () => {
    expect(sunLook(20).night).toBe(0);
    expect(sunLook(-2).intensity).toBe(0);
    expect(sunLook(-12).night).toBe(1);
    expect(sunLook(5).intensity).toBeLessThan(sunLook(30).intensity);
  });
});
