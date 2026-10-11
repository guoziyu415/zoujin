// The voice store (frontend-design 6, 7.5, 7.6): the conversation as the HUD shows it. The voice controller writes it
// (turns, subtitles, the microphone, the safety card); the session adds narration and the connection-level facts.
// What the talk key shows is derived from these facts (voice/state.ts), not stored.
import { create } from "zustand";

export type Line = {
  turnId: string;
  speaker: string; // "player" or a character ID
  text: string | null; // what shows now (a character's line follows the voice); null: the transcript failed
  final: boolean;
  source?: "live" | "script" | "fallback";
  fromChip?: boolean;
  cut?: boolean; // the player spoke over it: 「——」 at the break (ux-design 7.1)
  cancelled?: boolean; // the player's line of a cancelled turn: faded and struck through (7.4)
};

export type Turn = {
  turnId: string;
  turnSeq: number; // 0 until sent (a typed line waiting for the connection)
  kind: "voice" | "text" | "server"; // server: the character speaks first (turn_started)
  // listening: the key is down; waiting: sent, no voice yet; speaking: the character is audible (or answered in
  // text); done: turn_complete or interrupted; settled: turn_settled (can't be retracted any more)
  phase: "listening" | "waiting" | "speaking" | "done" | "settled";
  audio?: boolean; // turn_complete.audio
  complete?: boolean; // turn_complete came: 言い直す from here until turn_settled (frontend-design 7.5)
  ended?: boolean; // the voice has played out (or there was none)
  noResponse?: boolean; // 6 s without a voice, or turn_complete { audio: false } with no words (7.6)
};

export type Suggestion = {
  text: string;
  kind: "ask" | "act" | "accept" | "decline";
};

// unknown: not asked yet (the first press opens the primer); text: the player chose 文字で話す
export type Mic = "unknown" | "granted" | "denied" | "unavailable" | "text";

type VoiceStore = {
  session: {
    character: string | null;
    status: "none" | "preparing" | "ready";
    etaMs?: number;
    voiceAvailable?: boolean;
  };
  turn: Turn | null;
  nextTurnSeq: number; // per connection, from 1 (api-contract 3.1)
  player: Line | null;
  character: Line | null;
  narration: string[]; // the latest grey lines (地の文), newest last
  suggestions: { character: string; items: Suggestion[] } | null;
  degraded: boolean;
  voiceMinutesLeft: number | null;
  mic: Mic;
  sheet: "primer" | "denied" | "unavailable" | null; // the half page over the HUD (ux-design 7.3, 12)
  micReady: boolean; // just granted: 「準備ができました…」 once
  hold: { slide: boolean; preparing: boolean } | null; // the key is down; slide: past 60 px up; preparing: > 2 s held back
  note: "tooShort" | null; // 「押したまま話してください」 for a moment
  textOpen: boolean; // the text field is open (文字で話す, 文字で送る, a correction)
  draft: { text: string; replaces: string | null } | null; // the field's starting text; replaces: a correction
  paused: boolean; // the safety card (frontend-design 12)
  hint: boolean; // the quiet safety note (12, ux-design 14.2)
  helpline: "hint" | null; // the helpline panel, opened from the note
};

export const NARRATION_KEEP = 3;

export const initialVoice = (): VoiceStore => ({
  session: { character: null, status: "none" },
  turn: null,
  nextTurnSeq: 1,
  player: null,
  character: null,
  narration: [],
  suggestions: null,
  degraded: false,
  voiceMinutesLeft: null,
  mic: "unknown",
  sheet: null,
  micReady: false,
  hold: null,
  note: null,
  textOpen: false,
  draft: null,
  paused: false,
  hint: false,
  helpline: null,
});

export const useVoice = create<VoiceStore>()(initialVoice);

export function addNarration(...lines: string[]): void {
  if (!lines.length) return;
  useVoice.setState((s) => ({
    narration: [...s.narration, ...lines].slice(-NARRATION_KEEP),
  }));
}

// which retract button the turn has now (frontend-design 7.5): 取り消す before the character speaks, 言い直す from
// turn_complete until turn_settled; none for the character's own turns or once settled
export function retractKind(t: Turn | null): "cancel" | "redo" | null {
  if (
    !t ||
    t.kind === "server" ||
    t.phase === "settled" ||
    t.phase === "listening"
  )
    return null;
  if (t.complete) return t.noResponse ? null : "redo";
  return t.phase === "waiting" && t.turnSeq > 0 ? "cancel" : null;
}
