// The first screen (F-2 card: S7's 西南角 shot, shots/v2-sheet1.jpg h_corner_1730; art-direction 10 check 1): a fixed
// camera per start spot, in plan coordinates (layout.json), turned a few degrees left of S7's so the player's back
// stands in the lower-left foreground. Held until the player first walks or turns; then the follow camera takes over.
// UX's opening animation (frontend-design 10.2) will end on this shot.
import type { Vec3 } from "./frame";

export type View = { from: Vec3; to: Vec3; fov: number };

export const OPENING_VIEWS: Record<string, View> = {
  "plaza-southwest": {
    from: [-16.5, -13.5, 1.65],
    to: [13, 7.9, 7.5],
    fov: 60,
  },
};
