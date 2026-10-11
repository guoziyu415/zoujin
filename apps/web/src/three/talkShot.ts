// The conversation's over-the-shoulder shot (ux-design 6.3): how far to the side of the player's head the camera goes
// in portrait so that only the shoulder shows. The camera aims at the other person's face, so its line of sight
// crosses the player's head closer in the nearer the two stand: the side offset grows as they come closer.
export const TALK = {
  back: 1.1, // camera behind the player's head, metres
  headR: 0.13, // a head's radius, with a little margin
  shoulder: 0.18, // the shoulder's distance to the side of the head's centre
};

// portrait: the side offset that puts the player's head just out of the frame, its shoulder still in at the left edge.
// `distance`: head to the other person's face (level), `fov` the vertical field of view in degrees, `aspect` w / h
export function shoulderSide(
  distance: number,
  fov: number,
  aspect: number,
): number {
  const half = Math.atan(Math.tan((fov * Math.PI) / 360) * aspect); // half the horizontal field of view
  // the head's centre this far from the line of sight, at its depth, is out of frame
  const clear = TALK.back * Math.tan(half + Math.asin(TALK.headR / TALK.back));
  const d = Math.max(0.5, distance);
  return Math.min(0.9, Math.max(0.35, (clear * (TALK.back + d)) / d));
}
