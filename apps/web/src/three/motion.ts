// Reduced motion (prefers-reduced-motion; F-1's 「画面の動きを減らす」 setting joins it): the camera cuts instead of
// gliding, the sun jumps to the new time instead of moving there (ux-design 6.3, 13).
const motionQuery =
  typeof window !== "undefined" && window.matchMedia
    ? window.matchMedia("(prefers-reduced-motion: reduce)")
    : null;

export const reducedMotion = (): boolean => motionQuery?.matches ?? false;
