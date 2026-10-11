// The player store (frontend-design 6): what the client keeps about the player itself. The position and heading stay
// in the 3D layer's per-frame state (three/rig.ts); here is what the screens and the network layer need from it.
import { create } from "zustand";

// the server put the player somewhere (the snapshot, a commit's patch.player, a refused move): the 3D puts them there
// once per `n`, without walking and without sending move back (api-contract 3.8). No spot: anywhere in that place,
// as near as possible to where they stand.
export type Placement = { place: string; spot?: string; n: number };

type PlayerStore = {
  place: string | null; // the place the player stands in now (the 3D's word; move goes to the server, 9.4)
  placed: Placement | null;
  nearCharacter: string | null; // the closest talkable character, the one `near` was sent for (api-contract 3.2)
  focusCharacter: string | null; // the one the player picked (focus)
  distances: Record<string, number>; // metres to each character on screen, whole numbers (「近くの人」 sorts by them)
  goal: { spot: string; n: number } | null; // 「近くの人」 picked something: the 3D walks to this spot
};

export const usePlayer = create<PlayerStore>()(() => ({
  place: null,
  placed: null,
  nearCharacter: null,
  focusCharacter: null,
  distances: {},
  goal: null,
}));

export function placePlayer(place: string, spot?: string): void {
  const n = (usePlayer.getState().placed?.n ?? 0) + 1;
  usePlayer.setState({
    place,
    placed: spot ? { place, spot, n } : { place, n },
  });
}

export function walkToSpot(spot: string): void {
  usePlayer.setState((s) => ({ goal: { spot, n: (s.goal?.n ?? 0) + 1 } }));
}
