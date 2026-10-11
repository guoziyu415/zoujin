// The page's one audio engine (one AudioContext for the whole page, frontend-design 7.2). The worklet modules are
// built by Vite as separate files (same origin, so the strict CSP holds) and handed in here.
import { AudioEngine } from "./engine";
import captureUrl from "./worklets/capture.ts?worker&url";
import playUrl from "./worklets/play.ts?worker&url";

export const audio = new AudioEngine({ capture: captureUrl, play: playUrl });

// the e2e checks read the engine (the barge-in budget: lastFlushMs); tests/e2e/f1.spec.ts sets the flag before load
if ((globalThis as { __zoujinTest?: boolean }).__zoujinTest)
  Object.assign(globalThis, { __zoujinAudio: audio });
