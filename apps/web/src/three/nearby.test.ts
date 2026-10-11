import { describe, expect, it } from "vitest";
import { pickNear } from "./nearby";

describe("near", () => {
  it("is the closest talkable character inside 8 m", () => {
    expect(pickNear(null, { a: 9, b: 7.5, c: 3 })).toBe("c");
    expect(pickNear(null, { a: 9 })).toBeNull();
  });
  it("keeps the one it has until 12 m (hysteresis)", () => {
    expect(pickNear("a", { a: 11.9 })).toBe("a");
    expect(pickNear("a", { a: 12.1 })).toBeNull();
    expect(pickNear("a", {})).toBeNull(); // gone from the scene
  });
  it("hands over only to someone clearly closer and inside 8 m", () => {
    expect(pickNear("a", { a: 6, b: 5 })).toBe("a");
    expect(pickNear("a", { a: 6, b: 3.5 })).toBe("b");
    expect(pickNear("a", { a: 11, b: 8.5 })).toBe("a");
    expect(pickNear("a", { a: 13, b: 7 })).toBe("b");
  });
});
