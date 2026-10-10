// F-2's stand-in for the world store (frontend-design 6), only the fields the 3D layer reads. F-0 brings the real
// store with the network layer; F-2d swaps this file for it and deletes it (docs/tasks/m2-0/F-2.md, 接口).
import { create } from "zustand";

export type CharacterState = { place: string; spot?: string; activity: string };

export type WorldState = {
  sceneId: string;
  clock: { t: number; tLabel: string };
  player: { roleId: string; place: string; spot?: string };
  places: Record<string, { enabled: boolean; reason?: string }>;
  characters: Record<string, CharacterState>;
};

type Actions = {
  setClock: (t: number) => void;
  setPlaceEnabled: (place: string, enabled: boolean) => void;
  // the player walked into another place of this scene; F-0 sends action { kind: "move", target } (api-contract 3.8)
  movePlayer: (place: string) => void;
};

export type WorldStore = WorldState & Actions & { moves: string[] };

export const useWorld = create<WorldStore>()((set) => ({
  sceneId: "scene.syracuse-square",
  clock: { t: 1050, tLabel: "約束の日・夕方" },
  player: {
    roleId: "role.traveler",
    place: "place.syracuse-square",
    spot: "plaza-southwest",
  },
  places: {
    "place.syracuse-square": { enabled: true },
    "place.stonemason-workshop": { enabled: true },
    "place.execution-ground": { enabled: true },
  },
  characters: {},
  moves: [],
  setClock: (t) => set((s) => ({ clock: { ...s.clock, t } })),
  setPlaceEnabled: (place, enabled) =>
    set((s) => ({ places: { ...s.places, [place]: { enabled } } })),
  movePlayer: (place) =>
    set((s) => ({
      player: { roleId: s.player.roleId, place },
      moves: [...s.moves, place],
    })),
}));
