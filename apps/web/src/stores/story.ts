// The story's pages over the world (frontend-design 5, 10.4): the act-end page and the act change (その頃, the
// slice's jump page), and which full-page overlay is open (記憶帳, 連鎖反応マップ). The network layer writes the act
// end and the act change; the menu and the links open the overlays. While any of these covers the screen the 3D
// loop stops (10.4): `covered` is what the 3D layer reads.
import { create } from "zustand";
import type { ActEndState, TransitionState } from "../net/story";

export type Overlay =
  | { kind: "memory"; character?: string }
  // scroll to an event, or open a why straight away; from: where it was opened (map_opened)
  | {
      kind: "map";
      eventId?: string;
      why?: string;
      from?: "hud" | "sonokoro" | "ending";
    }
  | null;

type StoryStore = {
  actEnd: ActEndState | null;
  transition: TransitionState | null;
  overlay: Overlay;
};

export const useStory = create<StoryStore>()(() => ({
  actEnd: null,
  transition: null,
  overlay: null,
}));

export const resetStory = (): void =>
  useStory.setState({ actEnd: null, transition: null, overlay: null });

export const openOverlay = (o: Overlay): void =>
  useStory.setState({ overlay: o });

// a full page covers the 3D (10.4): stop its render loop
export const selectCovered = (s: StoryStore): boolean =>
  !!(s.actEnd || s.transition || s.overlay);
