// The world store (frontend-design 6): only the network layer writes it, from the snapshot and the commits.
// Components and the 3D layer read it; none of them talk to the server (4).
import { create } from "zustand";
import type { WorldData } from "../net/apply";

// byCommit: the clock (if it moved) was moved by a commit. A snapshot (the welcome, a reconnect, an act change) also
// moves it, but the sun band shows 「+n」 only for a commit (ux-design 4.5: the jump page doesn't).
type WorldStore = { world: WorldData | null; byCommit: boolean };

export const useWorld = create<WorldStore>()(() => ({
  world: null,
  byCommit: false,
}));

export const setWorld = (world: WorldData | null, byCommit = false): void =>
  useWorld.setState({ world, byCommit });
