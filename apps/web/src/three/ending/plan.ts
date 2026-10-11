// What this playthrough's ending stages (F-13; ux-design 11.1, project folder ux/slice/ending-shots.md): who is on the
// post, whether Melos runs in, whether the crowd makes way, where the old man and the player stand. From
// ending_started's staging (one state per person: where they end up, B-9) and the closing set pieces received so far
// (they come after ending_started, S-087 ②), so it is worked out again as pieces arrive. Pure: the 3D only reads it.
import type { Api } from "@zoujin/contracts";

export type StagePlan = {
  onPost: "char.selinuntius" | "player" | null; // hoisted up the post at the start (freed: let down at shot 5)
  hostage: "char.selinuntius" | "player" | null; // the one Melos runs to
  melos: boolean; // runs in from the west gate (arriving); otherwise he is not on the ground
  madeIt: boolean; // piece.made-it: he came before his friend was brought out (shot 2's camera, then shot 6)
  crowdMakesWay: boolean; // piece.crowd-makes-way(-you): the crowd knew, a woman shouts, they open the way
  late: boolean; // Melos didn't make it: shots 1 and 2's cameras, still at the last light (ux-design 11.4 A)
  king: "approaching" | "present" | null; // approaching: walks to the platform (shots 8, 9); present: on the castle steps
  maiden: boolean;
  oldMan: "by-player" | "crowd-edge" | null;
  player: boolean; // the player stands on the ground (not on the post)
  behindPlayer: boolean; // the player waited at ground-west: shot 2 is taken from behind them (ending-shots.md)
};

const MAKES_WAY = new Set([
  "piece.crowd-makes-way",
  "piece.crowd-makes-way-you",
]);
const CURTAIN = new Set(["piece.storm-in", "piece.storm-in-you", ...MAKES_WAY]);

export function stagePlan(i: {
  staging: Api.Staging;
  pieces: readonly string[]; // pieceIds of the ending's lines so far
  playerSpot: string | null;
  oldManSpot: string | null;
}): StagePlan {
  const state = (id: string): Api.StagingState | null =>
    i.staging.characters.find((c) => c.id === id)?.state ?? null;
  const there = (id: string) => {
    const s = state(id);
    return s !== null && s !== "absent";
  };
  const has = (p: string) => i.pieces.includes(p);
  const tied = (id: string) => {
    const s = state(id);
    return s === "on-cross" || s === "freed";
  };
  const hostage = tied("player")
    ? "player"
    : tied("char.selinuntius")
      ? "char.selinuntius"
      : null;
  const madeIt = has("piece.made-it");
  const melos = state("char.melos") === "arriving";
  const kingState = state("char.king");
  const playerOnGround = there("player") && hostage !== "player";
  const oldMan = !there("char.old-man")
    ? null
    : i.playerSpot === "stake-front" && i.oldManSpot === "stake-front-side"
      ? "by-player"
      : "crowd-edge";
  return {
    onPost: madeIt ? null : hostage,
    hostage,
    melos,
    madeIt,
    crowdMakesWay: i.pieces.some((p) => MAKES_WAY.has(p)),
    late: !melos && !madeIt && !i.pieces.some((p) => CURTAIN.has(p)),
    king:
      kingState === "approaching"
        ? "approaching"
        : kingState && kingState !== "absent"
          ? "present"
          : null,
    maiden: there("char.maiden") || has("piece.scarlet-cloak"),
    oldMan,
    player: playerOnGround,
    behindPlayer: playerOnGround && i.playerSpot === "ground-west",
  };
}
