// Back from the background (frontend-design 9.5): one tap to go on. The tap is where F-1 resumes the AudioContext
// (iOS needs a gesture); F-0 only shows and clears the gate.
import { useUi } from "../../stores/ui";
import { copy } from "../copy";

export function ResumeGate() {
  const shown = useUi((s) => s.resumeGate);
  if (!shown) return null;
  return (
    <button
      className="gate"
      onClick={() => useUi.setState({ resumeGate: false })}
    >
      {copy["resume.tap"]}
    </button>
  );
}
