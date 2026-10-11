import { describe, expect, it } from "vitest";
import { Resampler } from "./resample";

const ramp = (n: number, from = 0) =>
  Float32Array.from({ length: n }, (_, i) => (from + i) / 1000);

describe("Resampler", () => {
  it("24 kHz to 48 kHz doubles the samples and interpolates between them", () => {
    const r = new Resampler(24_000, 48_000);
    const out = r.push(ramp(100, 1));
    expect(out.length).toBeGreaterThanOrEqual(199);
    expect(out.length).toBeLessThanOrEqual(201);
    // a ramp stays a ramp: each step is half the input's
    for (let i = 3; i < out.length; i++)
      expect(out[i]! - out[i - 1]!).toBeCloseTo(0.0005, 6);
  });

  it("pieces give the same samples as the whole (no click at the joins)", () => {
    const whole = new Resampler(24_000, 44_100).push(ramp(480, 1));
    const r = new Resampler(24_000, 44_100);
    const pieces = [
      ...r.push(ramp(100, 1)),
      ...r.push(ramp(250, 101)),
      ...r.push(ramp(130, 351)),
    ];
    expect(pieces.length).toBe(whole.length);
    pieces.forEach((v, i) => expect(v).toBeCloseTo(whole[i]!, 6));
  });

  it("the same rate passes through; reset starts a new turn from silence", () => {
    const same = new Resampler(24_000, 24_000);
    const x = ramp(10);
    expect(same.push(x)).toBe(x);
    const r = new Resampler(24_000, 48_000);
    r.push(ramp(7, 500));
    r.reset();
    expect(r.push(ramp(4, 1))[0]).toBe(0);
  });
});
