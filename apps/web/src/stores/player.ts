// The player store (frontend-design 6): what the client keeps about the player itself. F-0 has who the player is
// talking to; the position and heading come with F-2d, when the 3D layer moves onto these stores.
import { create } from "zustand";

type PlayerStore = {
  nearCharacter: string | null; // the closest talkable character (near / far, api-contract 3.2)
  focusCharacter: string | null; // the one the player picked (focus)
};

export const usePlayer = create<PlayerStore>()(() => ({
  nearCharacter: null,
  focusCharacter: null,
}));
