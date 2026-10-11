// The voice states of frontend-design 7.6 (names as ux-design 7.4), derived from the facts in the stores rather than
// kept as a separate machine: the connection, the safety card, coming back from the background, the microphone, the
// session with the character, the key, and the turn. One function, so each row of the table is one test. Two rows
// are moments rather than states: `interrupted` is the instant before `listening` (the cut line with 「——」 is its
// trace) and `cancelled` shows on the struck-through line while the key is back to idle. `confirming` comes with the
// intent-confirmation card (M2).
import type { Mic, Turn } from "../stores/voice";

export type VoiceState =
  | "mic-unknown"
  | "primer"
  | "denied"
  | "unavailable"
  | "preparing"
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "no-response"
  | "degraded"
  | "paused"
  | "reconnecting"
  | "suspended"
  | "away"; // nobody to talk to (not in 7.6: the key's 「人に近づくと話せます」)

export type Facts = {
  connection:
    "idle" | "connecting" | "open" | "reconnecting" | "taken" | "gone";
  resumeGate: boolean;
  paused: boolean;
  degraded: boolean;
  mic: Mic;
  sheet: "primer" | "denied" | "unavailable" | null;
  focus: string | null;
  session: "none" | "preparing" | "ready";
  holding: boolean;
  turn: Turn | null;
};

export function voiceState(f: Facts): VoiceState {
  if (f.connection !== "open") return "reconnecting";
  if (f.paused) return "paused";
  if (f.resumeGate) return "suspended";
  if (f.degraded) return "degraded";
  if (f.sheet === "primer") return "primer";
  if (f.mic === "denied" || f.mic === "unavailable") return f.mic;
  if (!f.focus) return "away";
  if (f.holding) return "listening";
  const t = f.turn;
  if (t?.noResponse) return "no-response"; // the chips stay until the player does something (7.5)
  if (t && t.phase !== "settled" && !(t.phase === "done" && t.ended)) {
    if (t.phase === "waiting") return "thinking";
    if (t.phase === "speaking" || t.phase === "done") return "speaking";
  }
  if (f.session !== "ready") return "preparing";
  return f.mic === "unknown" ? "mic-unknown" : "idle";
}

// the key can start a turn in these (preparing too: the first 2 s are held back until the session is ready)
export const canPress = (s: VoiceState): boolean =>
  s === "idle" ||
  s === "mic-unknown" ||
  s === "preparing" ||
  s === "thinking" ||
  s === "speaking" ||
  s === "no-response";
