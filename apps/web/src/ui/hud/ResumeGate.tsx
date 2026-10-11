// Back from the background, or iOS interrupted the sound (frontend-design 9.5, 7.4): one tap to go on. The tap is
// the gesture iOS needs to resume the AudioContext.
import { play } from "../../net/play";
import { useUi } from "../../stores/ui";
import { copy } from "../copy";

export function ResumeGate() {
  const shown = useUi((s) => s.resumeGate);
  if (!shown) return null;
  return (
    <button
      className="gate"
      onClick={() => {
        play.resumeAudio();
        useUi.setState({ resumeGate: false });
      }}
    >
      {copy["resume.tap"]}
    </button>
  );
}
