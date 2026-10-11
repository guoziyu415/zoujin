import { describe, expect, it } from "vitest";
import { delta } from "./SunBand";

describe("the clock's +n (copy-ja 3)", () => {
  it("minutes under an hour; from an hour, to the nearest 30 minutes with 15 rounding up", () => {
    expect(delta(10)).toBe("+10分");
    expect(delta(59)).toBe("+59分");
    expect(delta(60)).toBe("+1時間");
    expect(delta(74)).toBe("+1時間");
    expect(delta(75)).toBe("+1時間半");
    expect(delta(104)).toBe("+1時間半");
    expect(delta(105)).toBe("+2時間");
    expect(delta(134)).toBe("+2時間");
  });
});
