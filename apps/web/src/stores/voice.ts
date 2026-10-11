// The voice store (frontend-design 6, 7.5): the conversation as the subtitles show it. The network layer writes it;
// F-1's audio engine adds the talk button states (7.6) and the audio side.
import { create } from "zustand";

export type Line = {
  turnId: string;
  speaker: string; // "player" or a character ID
  text: string | null; // null: the transcript failed (ux-design 7.7)
  final: boolean;
  source?: "live" | "script" | "fallback";
  fromChip?: boolean;
};

export type Turn = {
  turnId: string;
  turnSeq: number;
  // waiting: sent, nothing back yet; speaking: the character has started; done: turn_complete or interrupted;
  // settled: turn_settled (can't be retracted any more)
  phase: "waiting" | "speaking" | "done" | "settled";
  audio?: boolean; // turn_complete.audio
};

export type Suggestion = {
  text: string;
  kind: "ask" | "act" | "accept" | "decline";
};

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
});

export const useVoice = create<VoiceStore>()(initialVoice);

export function addNarration(...lines: string[]): void {
  if (!lines.length) return;
  useVoice.setState((s) => ({
    narration: [...s.narration, ...lines].slice(-NARRATION_KEEP),
  }));
}
