// The talk key's state for components (voice/state.ts over the stores).
import { usePlayer } from "../stores/player";
import { useUi } from "../stores/ui";
import { useVoice } from "../stores/voice";
import { voiceState, type VoiceState } from "./state";

export function useVoiceState(): VoiceState {
  const connection = useUi((s) => s.connection);
  const resumeGate = useUi((s) => s.resumeGate);
  const paused = useVoice((s) => s.paused);
  const degraded = useVoice((s) => s.degraded);
  const mic = useVoice((s) => s.mic);
  const sheet = useVoice((s) => s.sheet);
  const session = useVoice((s) => s.session.status);
  const holding = useVoice((s) => !!s.hold);
  const turn = useVoice((s) => s.turn);
  const focus = usePlayer((s) => s.focusCharacter);
  return voiceState({
    connection,
    resumeGate,
    paused,
    degraded,
    mic,
    sheet,
    focus,
    session,
    holding,
    turn,
  });
}
