import { describe, expect, it } from "vitest";
import { cardShot, SHOTS, shotOf } from "./shots";

const through = (...pieces: string[]) => pieces.flatMap((p) => SHOTS[p]!);

describe("the card's shot", () => {
  it("Melos made it: shot 6, the two on the platform", () => {
    expect(
      cardShot(through("piece.storm-in", "piece.embrace", "piece.king-asks")),
    ).toBe(6);
  });

  it("the player was the hostage (-you, no embrace): shot 5, the rope loosened", () => {
    expect(cardShot(through("piece.storm-in-you", "piece.king-asks-you"))).toBe(
      5,
    );
  });

  it("no shot of the three: the fallback picture", () => {
    expect(cardShot(through("piece.scarlet-cloak"))).toBeNull();
  });
});

describe("shots of lines", () => {
  it("king-asks/1 cuts from 7 to 8 at 「やがて」", () => {
    const s = shotOf(
      "piece.king-asks",
      1,
      "王は黙っていた。やがて、口をひらいた。",
    );
    expect(s.shot).toBe(7);
    expect(s.midShot?.shot).toBe(8);
    expect(s.midShot!.at).toBeGreaterThan(0.3);
  });

  it("a line beyond the table stays in the shot that is on", () => {
    expect(shotOf("piece.made-it", 2, "x").shot).toBeNull();
  });
});
