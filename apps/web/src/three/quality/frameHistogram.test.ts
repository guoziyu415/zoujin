import { describe, expect, it } from "vitest";
import { binOf, FrameHistogram } from "./frameHistogram";

describe("frame-time histogram", () => {
  it("puts whole refreshes and their jitter in one bin each", () => {
    expect(binOf(8.3)).toBe(0); // 120 Hz
    expect(binOf(11.1)).toBe(1); // 90 Hz
    expect([16.4, 16.7, 16.99].map(binOf)).toEqual([2, 2, 2]); // 60 Hz
    expect(binOf(20)).toBe(3); // a bound belongs to the bin below it
    expect(binOf(25)).toBe(4); // 120 Hz, 3 refreshes
    expect([33.0, 33.3, 33.9].map(binOf)).toEqual([5, 5, 5]); // 30 fps
    expect(binOf(50)).toBe(6);
    expect(binOf(100)).toBe(7);
    expect(binOf(101.5)).toBe(8);
  });

  it("counts into 9 bins and starts again after take()", () => {
    const h = new FrameHistogram();
    for (const ms of [16.7, 16.7, 33.3, 250]) h.add(ms);
    expect(h.frames).toBe(4);
    expect(h.take()).toEqual([0, 0, 2, 0, 0, 1, 0, 0, 1]);
    expect(h.take()).toEqual([0, 0, 0, 0, 0, 0, 0, 0, 0]);
  });
});
