// The world store (frontend-design 6): only the network layer writes it, from the snapshot and the commits.
// Components and the 3D layer read it; none of them talk to the server (4).
import { create } from "zustand";
import type { WorldData } from "../net/apply";

type WorldStore = { world: WorldData | null };

export const useWorld = create<WorldStore>()(() => ({ world: null }));

export const setWorld = (world: WorldData | null): void =>
  useWorld.setState({ world });
