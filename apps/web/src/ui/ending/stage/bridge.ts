// Between the ending's subtitles and the 3D staging (F-12 card, 「接口」): the subtitles say which shot is on; the 3D
// says when a shot's action is done and gives one 1080×640 frame for the ending card. Until the 3D staging card
// plugs in (setStageBridge), every shot is done at once and there is no frame (the card uses the fallback picture).
export type StageBridge = {
  shot(n: number): void;
  onShotDone(f: (n: number) => void): () => void;
  captureFrame(): Promise<ImageBitmap | null>;
  pause(on: boolean): void;
};

const listeners = new Set<(n: number) => void>();

const none: StageBridge = {
  shot: (n) => queueMicrotask(() => listeners.forEach((f) => f(n))),
  onShotDone: (f) => {
    listeners.add(f);
    return () => listeners.delete(f);
  },
  captureFrame: () => Promise.resolve(null),
  pause: () => {},
};

let current: StageBridge = none;

export const stageBridge = (): StageBridge => current;
export const setStageBridge = (b: StageBridge | null): void => {
  current = b ?? none;
};
