// The ending's subtitles (ux-design 11.1, S-089), as a pure state machine over time so every rule is unit tested:
// - narration, and a character's line without a recording, shows whole and stays max(1.5 s, chars ÷ 7 s);
// - a recorded line follows its voice and stays until 0.5 s after it ends;
// - a line stays until the next one comes (no gap);
// - a tap: a line already whole → the next; a recorded line still coming → whole at once (the voice goes on), a
//   second tap fades the voice in 0.2 s and moves on; taps within 0.5 s of a line appearing or being completed
//   don't count; the next recording starts after the fade;
// - the first line of a new shot, when moving on by itself, also waits for the shot's action to finish (the longer
//   of the two); a tap doesn't wait and cuts straight to it;
// - auto off (「結末を自動で進める」): every line waits for a tap;
// - paused (in the background, a full page open): the clock stops.
// The component feeds it time, taps and "shot done", and carries out the effects it returns.

export const CHARS_PER_SEC = 7;
export const MIN_HOLD_MS = 1500;
export const AFTER_VOICE_MS = 500;
export const TAP_GUARD_MS = 500;
export const FADE_MS = 200;

export type StageLine = {
  text: string;
  speaker: string | null; // null: narration
  clipMs: number | null; // the recording's length when it is loaded; null: shown whole, timed like narration
  shot: number | null; // the shot this line is in (ending-shots.md); null: whatever is on
  midShot?: { at: number; shot: number }; // a cut in the middle of the line (0-1 of its time), shot 7 → 8
  key?: string; // "<pieceId>/<n>" (setPieceVoices)
};

export type Effect =
  | { k: "show"; i: number }
  | { k: "play"; i: number }
  | { k: "fade" } // the voice to silence in FADE_MS
  | { k: "shot"; n: number }
  | { k: "drained" }; // the last line has had its time and nothing else is queued

export type Pace = {
  lines: StageLine[];
  i: number; // the line on screen; -1 before the first
  since: number; // when it appeared (paused time excluded)
  whole: boolean; // the whole line is on screen
  guardUntil: number;
  shot: number | null;
  shotDone: boolean;
  midDone: boolean;
  startAt: number | null; // a line waiting for the previous voice's fade
  auto: boolean;
  pausedAt: number | null;
  drained: boolean;
  taps: number;
};

export const chars = (s: string): number => [...s].length; // punctuation counts; ruby isn't in these strings

export const holdMs = (l: StageLine): number =>
  l.clipMs !== null
    ? l.clipMs + AFTER_VOICE_MS
    : Math.max(MIN_HOLD_MS, (chars(l.text) / CHARS_PER_SEC) * 1000);

export function initPace(auto: boolean): Pace {
  return {
    lines: [],
    i: -1,
    since: 0,
    whole: true,
    guardUntil: 0,
    shot: null,
    shotDone: true,
    midDone: true,
    startAt: null,
    auto,
    pausedAt: null,
    drained: false,
    taps: 0,
  };
}

// how much of a recorded line shows: it follows the voice (7.7), a share of the characters by elapsed time
export function visibleText(p: Pace, now: number): string {
  const l = p.lines[p.i];
  if (!l) return "";
  if (p.whole || l.clipMs === null) return l.text;
  const t = now - p.since;
  const all = [...l.text];
  const n = Math.ceil((all.length * Math.max(0, t)) / Math.max(1, l.clipMs));
  return all.slice(0, Math.min(all.length, Math.max(1, n))).join("");
}

function enter(
  p: Pace,
  i: number,
  now: number,
  fx: Effect[],
  cut: boolean,
): Pace {
  const l = p.lines[i]!;
  let shot = p.shot;
  let shotDone = p.shotDone;
  if (l.shot !== null && l.shot !== p.shot) {
    shot = l.shot;
    shotDone = false;
    fx.push({ k: "shot", n: l.shot });
  }
  fx.push({ k: "show", i });
  // a recording starts after the last one's fade (a tap that cut a voice) — otherwise at once
  const startAt = cut ? now + FADE_MS : null;
  if (l.clipMs !== null && !cut) fx.push({ k: "play", i });
  return {
    ...p,
    i,
    since: cut ? now + FADE_MS : now,
    whole: l.clipMs === null,
    guardUntil: now + TAP_GUARD_MS,
    shot,
    shotDone,
    midDone: !l.midShot,
    startAt: l.clipMs !== null ? startAt : null,
    drained: false,
  };
}

export function addLines(
  p: Pace,
  more: StageLine[],
  now: number,
): [Pace, Effect[]] {
  const next = { ...p, lines: [...p.lines, ...more] };
  // nothing on screen yet, or the last line already had its time: the new one comes at once
  if (p.i < 0 || p.drained) return tick(next, now, true);
  return [next, []];
}

export function tick(p: Pace, now: number, wake = false): [Pace, Effect[]] {
  if (p.pausedAt !== null) return [p, []];
  const fx: Effect[] = [];
  let s = p;
  if (s.startAt !== null && now >= s.startAt) {
    s = { ...s, startAt: null };
    fx.push({ k: "play", i: s.i });
  }
  if (s.i < 0) {
    if (!s.lines.length) return [s, fx];
    return [enter(s, 0, now, fx, false), fx];
  }
  const l = s.lines[s.i]!;
  const t = now - s.since;
  if (!s.midDone && l.midShot && t >= l.midShot.at * holdMs(l)) {
    s = { ...s, midDone: true, shot: l.midShot.shot, shotDone: false };
    fx.push({ k: "shot", n: l.midShot.shot });
  }
  if (l.clipMs !== null && !s.whole && t >= l.clipMs) s = { ...s, whole: true };
  if (!s.auto && !wake) return [s, fx];
  if (t < holdMs(l) && !(wake && s.drained)) return [s, fx];
  const nextLine = s.lines[s.i + 1];
  if (!nextLine) {
    if (!s.drained) {
      fx.push({ k: "drained" });
      s = { ...s, drained: true };
    }
    return [s, fx];
  }
  if (!s.auto && s.drained === false) return [s, fx];
  // the first line of the next shot waits for this shot's action too
  if (nextLine.shot !== null && nextLine.shot !== s.shot && !s.shotDone)
    return [s, fx];
  return [enter(s, s.i + 1, now, fx, false), fx];
}

export function tap(p: Pace, now: number): [Pace, Effect[]] {
  if (p.pausedAt !== null || p.i < 0 || now < p.guardUntil) return [p, []];
  const fx: Effect[] = [];
  const s = { ...p, taps: p.taps + 1 };
  const l = s.lines[s.i]!;
  if (!s.whole)
    return [{ ...s, whole: true, guardUntil: now + TAP_GUARD_MS }, fx];
  const playing = l.clipMs !== null && now - s.since < l.clipMs;
  if (playing) fx.push({ k: "fade" });
  if (!s.lines[s.i + 1]) {
    if (!s.drained) fx.push({ k: "drained" });
    return [{ ...s, drained: true }, fx];
  }
  return [enter(s, s.i + 1, now, fx, playing), fx];
}

export const shotDone = (p: Pace, n: number): Pace =>
  p.shot === n ? { ...p, shotDone: true } : p;

export const pause = (p: Pace, now: number): Pace =>
  p.pausedAt === null ? { ...p, pausedAt: now } : p;

export function resume(p: Pace, now: number): Pace {
  if (p.pausedAt === null) return p;
  const gone = now - p.pausedAt;
  return {
    ...p,
    pausedAt: null,
    since: p.since + gone,
    guardUntil: Math.max(p.guardUntil, now + TAP_GUARD_MS), // the tap that brought it back isn't a tap here
    startAt: p.startAt === null ? null : p.startAt + gone,
  };
}

export const setAuto = (p: Pace, auto: boolean): Pace => ({ ...p, auto });
