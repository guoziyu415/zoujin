import type { Api } from "@zoujin/contracts";
import { describe, expect, it } from "vitest";
import { stagePlan } from "./plan";

const staging = (
  ...cs: [Api.StagingCharacter["id"], Api.StagingState][]
): Api.Staging => ({
  place: "place.execution-ground",
  characters: cs.map(([id, state]) => ({ id, state })),
});

// B-9's table: Melos made it, the king changed his mind, the player and the old man in the front row
const reunion = staging(
  ["char.selinuntius", "freed"],
  ["char.melos", "arriving"],
  ["char.king", "approaching"],
  ["char.old-man", "in-crowd"],
  ["char.maiden", "in-crowd"],
  ["player", "in-crowd"],
);

describe("stagePlan", () => {
  it("the friend on the post, Melos running in, the king walking up", () => {
    const p = stagePlan({
      staging: reunion,
      pieces: ["piece.storm-in", "piece.embrace", "piece.king-asks"],
      playerSpot: "stake-front",
      oldManSpot: "stake-front-side",
    });
    expect(p).toMatchObject({
      onPost: "char.selinuntius",
      hostage: "char.selinuntius",
      melos: true,
      madeIt: false,
      crowdMakesWay: false,
      late: false,
      king: "approaching",
      maiden: true,
      oldMan: "by-player",
      player: true,
      behindPlayer: false,
    });
  });

  it("the crowd makes way when it knew of the promise", () => {
    const p = stagePlan({
      staging: reunion,
      pieces: ["piece.crowd-makes-way"],
      playerSpot: "ground-west",
      oldManSpot: "crowd-front",
    });
    expect(p.crowdMakesWay).toBe(true);
    expect(p.behindPlayer).toBe(true); // waited at the west end: shot 2 from behind them
    expect(p.oldMan).toBe("crowd-edge");
  });

  it("made it before his friend was brought out: nobody is hoisted", () => {
    const p = stagePlan({
      staging: reunion,
      pieces: ["piece.made-it", "piece.embrace"],
      playerSpot: null,
      oldManSpot: null,
    });
    expect(p.madeIt).toBe(true);
    expect(p.onPost).toBeNull();
    expect(p.hostage).toBe("char.selinuntius");
  });

  it("too late: the friend stays on the post, Melos isn't there", () => {
    const p = stagePlan({
      staging: staging(
        ["char.selinuntius", "on-cross"],
        ["char.melos", "absent"],
        ["char.king", "present"],
        ["player", "absent"],
      ),
      pieces: [],
      playerSpot: null,
      oldManSpot: null,
    });
    expect(p).toMatchObject({
      onPost: "char.selinuntius",
      melos: false,
      late: true,
      king: "present",
      player: false,
      oldMan: null,
      maiden: false,
    });
  });

  it("the player as the hostage is on the post, not on the ground (the -you pieces)", () => {
    const p = stagePlan({
      staging: staging(
        ["player", "freed"],
        ["char.melos", "arriving"],
        ["char.selinuntius", "in-crowd"],
      ),
      pieces: ["piece.storm-in-you"],
      playerSpot: "stake",
      oldManSpot: null,
    });
    expect(p.onPost).toBe("player");
    expect(p.player).toBe(false);
    expect(p.behindPlayer).toBe(false);
  });

  it("before any set piece arrives, Melos arriving is not late", () => {
    const p = stagePlan({
      staging: reunion,
      pieces: [],
      playerSpot: null,
      oldManSpot: null,
    });
    expect(p.late).toBe(false);
  });
});
