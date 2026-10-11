// The story's pages over the world (frontend-design 5, 10.4): the act-end page and the act change (その頃, the
// slice's jump page), and which full-page overlay is open (記憶帳, 連鎖反応マップ). The network layer writes the act
// end and the act change; the menu and the links open the overlays. While any of these covers the screen the 3D
// loop stops (10.4): `covered` is what the 3D layer reads.
import type { Api } from "@zoujin/contracts";
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

// a line of the ending's staging as the server sent it: a set piece's line (its voice is "<pieceId>/<n>") or a
// line of narration
export type EndingLine = {
  text: string;
  speaker: string | null;
  pieceId?: string;
  n?: number;
};

export type EndingState = {
  trigger: "deadline" | "story-closed";
  staging: Api.Staging;
  lines: EndingLine[]; // grows while the staging plays (set pieces come after ending_started, S-087 ②)
  endingId: string | null; // ending_ready
  roleId: string | null; // this playthrough's role, for the card's footer (the world is gone on the ending page)
  ready: boolean; // the character on stage finished their line (or was faded out): the staging may begin (11.1)
};

type StoryStore = {
  actEnd: ActEndState | null;
  transition: TransitionState | null;
  overlay: Overlay;
  ending: EndingState | null;
};

export const useStory = create<StoryStore>()(() => ({
  actEnd: null,
  transition: null,
  overlay: null,
  ending: null,
}));

export const resetStory = (): void =>
  useStory.setState({
    actEnd: null,
    transition: null,
    overlay: null,
    ending: null,
  });

export function addEndingLines(more: EndingLine[]): void {
  const e = useStory.getState().ending;
  if (e && more.length)
    useStory.setState({ ending: { ...e, lines: [...e.lines, ...more] } });
}

export const openOverlay = (o: Overlay): void =>
  useStory.setState({ overlay: o });

// a full page covers the 3D (10.4): stop its render loop
export const selectCovered = (s: StoryStore): boolean =>
  !!(s.actEnd || s.transition || s.overlay);

// the frame the ending's staging captured for the card (S-055); kept outside React, released after use
let frame: ImageBitmap | null = null;
export const endingFrame = {
  get: (): ImageBitmap | null => frame,
  set: (b: ImageBitmap | null): void => {
    if (frame && frame !== b) frame.close();
    frame = b;
  },
};
