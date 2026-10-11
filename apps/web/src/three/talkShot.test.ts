import { describe, expect, it } from "vitest";
import { shoulderSide, TALK } from "./talkShot";

// the angle off the line of sight (to the face `distance` beyond the head) of a point `x` metres right of the head line
// at the head's depth, the camera `side` metres right of it
const off = (side: number, distance: number, x: number) =>
  Math.atan((x - (side * distance) / (TALK.back + distance)) / TALK.back);

describe("the conversation shot in portrait", () => {
  const fov = 42;
  const aspect = 390 / 844;
  const half = Math.atan(Math.tan((fov * Math.PI) / 360) * aspect);
  const headR = Math.asin(0.12 / TALK.back); // the stand-in's head
  for (const distance of [0.9, 1.4, 2, 3]) {
    it(`at ${distance} m: the player's head out of frame, the shoulder in`, () => {
      const side = shoulderSide(distance, fov, aspect);
      expect(-off(side, distance, 0) - headR).toBeGreaterThanOrEqual(half); // the head's inner edge past the left edge
      expect(-off(side, distance, TALK.shoulder)).toBeLessThan(half); // the shoulder inside it
    });
  }
});
