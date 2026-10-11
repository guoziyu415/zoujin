import { describe, expect, it } from "vitest";
import { SHOTS } from "../../ui/ending/stage/shots";
import type { StagePlan } from "./plan";
import {
  after,
  blocking,
  GATE,
  HOISTED,
  type Mark,
  pathLength,
  RUN,
  shotScript,
  shotSeconds,
  stageFrame,
  STEPS,
  toMark,
  toWorld,
} from "./script";

const plan: StagePlan = {
  onPost: "char.selinuntius",
  hostage: "char.selinuntius",
  melos: true,
  madeIt: false,
  crowdMakesWay: true,
  late: false,
  king: "approaching",
  maiden: true,
  oldMan: "by-player",
  player: true,
  behindPlayer: false,
};
const STAKE_FRONT: Mark = [2.8, 0, 0];

// the shots a playthrough goes through in order, with everyone's marks carried from shot to shot
function run(p: StagePlan, shots: number[]) {
  let at = blocking(p, STAKE_FRONT);
  return shots.map((n) => {
    const s = shotScript(n, p, STAKE_FRONT)!;
    const seconds = shotSeconds(s, at);
    at = after(s, at);
    return { n, s, seconds, at };
  });
}

describe("the shot script", () => {
  it("has every shot the subtitles cut to (F-12's SHOTS, and 8: the cut halfway through king-asks/1)", () => {
    const used = new Set([...Object.values(SHOTS).flat(), 8]);
    for (const n of used)
      expect(shotScript(n, plan, STAKE_FRONT)).not.toBeNull();
    expect([...used].sort((a, b) => a - b)).toEqual([
      1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11,
    ]);
  });

  it("Melos runs gate to steps in about 6 s at 6.5 m/s over shots 2 and 3 (ending-shots.md)", () => {
    const [, two, three] = run(plan, [1, 2, 3]);
    expect(pathLength(GATE, [STEPS])).toBeCloseTo(39.2, 1);
    const ran = two!.seconds + three!.seconds;
    expect(ran).toBeGreaterThan(5.5);
    expect(ran).toBeLessThan(6.5);
    expect(three!.at.melos).toEqual(STEPS);
    expect(RUN).toBe(6.5);
  });

  it("pushing through a crowd that doesn't make way takes longer", () => {
    const [, , made] = run(plan, [1, 2, 3]);
    const [, , pushed] = run({ ...plan, crowdMakesWay: false }, [1, 2, 3]);
    expect(pushed!.seconds).toBeGreaterThan(made!.seconds * 1.5);
    expect(pushed!.s.cues[0]).toMatchObject({ k: "part", width: 1 });
    expect(made!.s.cues[0]).toMatchObject({ k: "part", width: 2.2 });
  });

  it("hoists the friend in shot 1 and lets him down in shot 5", () => {
    const r = run(plan, [1, 2, 3, 4, 5]);
    expect(r[0]!.at.hostage![2]).toBe(HOISTED);
    expect(r[0]!.s.cues).toContainEqual({ k: "rope", on: true });
    expect(r[4]!.at.hostage![2]).toBe(1.2);
    expect(r[4]!.s.cues).toContainEqual({ k: "rope", on: false });
    expect(r[4]!.s.cues).toContainEqual({ k: "torches", on: true });
  });

  it("made-it: shot 2 takes him all the way up to his friend, nobody hoisted", () => {
    const p = { ...plan, madeIt: true, onPost: null };
    const [one, two] = run(p, [1, 2]);
    expect(one!.s.moves).toEqual([]);
    expect(one!.s.cues).toContainEqual({ k: "rope", on: false });
    expect(two!.at.melos![2]).toBe(1.2);
    expect(two!.seconds).toBeGreaterThan(6);
  });

  it("too late: shot 2 has no one running", () => {
    const p = { ...plan, melos: false, late: true };
    expect(shotScript(2, p, null)!.moves).toEqual([]);
    expect(blocking(p, null).melos).toBeUndefined();
  });

  it("shot 2 from behind the player who waited at ground-west", () => {
    const west: Mark = [6.4, -2.5, 0];
    const cam = shotScript(2, { ...plan, behindPlayer: true }, west)!.camera;
    const from = "from" in cam ? cam.from : [];
    expect(from[0]).toBeCloseTo(3.8);
    expect(from.slice(1)).toEqual([-2.1, 1.75]);
  });

  it("the king walks up only when he is approaching", () => {
    const [, eight] = run(plan, [7, 8]);
    expect(eight!.seconds).toBeGreaterThan(3);
    expect(eight!.s.cues[0]).toMatchObject({ k: "part" });
    const still = shotScript(8, { ...plan, king: "present" }, null)!;
    expect(still.moves).toEqual([]);
    expect(still.cues).toEqual([]);
  });
});

describe("the stage frame", () => {
  // the slice's scene.json spots (world positions; the scene is rotated 144°)
  const spots = {
    stake: { pos: [-8.42, 1.2, -6.1] as [number, number, number] },
    "gate-inside": { pos: [25.08, 0, 18.22] as [number, number, number] },
    "king-west": { pos: [-3.6, 0, -0.15] as [number, number, number] },
    "ground-west": { pos: [-1.77, 0, -4.37] as [number, number, number] },
  };

  it("measures from the post towards the gate, the king's side positive", () => {
    const f = stageFrame(spots)!;
    expect(toMark(f, spots["gate-inside"].pos)[0]).toBeCloseTo(41.4, 1);
    const king = toMark(f, spots["king-west"].pos);
    expect(king[0]).toBeCloseTo(7.4, 1);
    expect(king[1]).toBeCloseTo(2, 1);
    const west = toMark(f, spots["ground-west"].pos);
    expect(west[0]).toBeCloseTo(6.4, 1);
    expect(west[1]).toBeCloseTo(-2.5, 1);
  });

  it("goes back to the same world point", () => {
    const f = stageFrame(spots)!;
    const w = toWorld(f, [6.4, -2.5, 0]);
    expect(w[0]).toBeCloseTo(-1.77, 1);
    expect(w[2]).toBeCloseTo(-4.37, 1);
  });

  it("needs the post and the gate", () => {
    expect(stageFrame({ stake: spots.stake })).toBeNull();
  });
});
