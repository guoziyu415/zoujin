// The safety card (frontend-design 12, ux-design 14.1): the one time the story steps out. The voice controller has
// already faded the voice and let go of the microphone; here the screen dims for 0.4 s, this turn's lines are
// cleared in the dark, and the card fades in with the focus on it. 「物語に戻る」 sends safety_resume and the dim
// goes back in 0.4 s. In the interface's sans-serif, not the story's mincho: these are words from outside the story.
import { useEffect, useRef, useState } from "react";
import { play } from "../../net/play";
import { useVoice } from "../../stores/voice";
import { copy } from "../copy";
import { Helplines } from "./Helplines";

export const DIM_MS = 400;

export function SafetyCard() {
  const paused = useVoice((s) => s.paused);
  const [stage, setStage] = useState<"none" | "dim" | "card" | "leaving">(
    "none",
  );
  const card = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (paused) {
      setStage("dim");
      const t = setTimeout(() => {
        play.clearPausedTurn(); // in the dark: the player never sees the words go
        setStage("card");
      }, DIM_MS);
      return () => clearTimeout(t);
    }
    setStage((s) => (s === "none" ? s : "leaving"));
    const t = setTimeout(() => setStage("none"), DIM_MS);
    return () => clearTimeout(t);
  }, [paused]);

  useEffect(() => {
    if (stage === "card") card.current?.focus(); // a screen reader starts at the first line
  }, [stage]);

  if (stage === "none") return null;
  return (
    <div
      className={`safety-dim ${stage === "leaving" ? "out" : ""}`}
      data-testid="safety"
    >
      {stage === "card" && (
        <div
          ref={card}
          className="safety-card"
          role="dialog"
          aria-modal="true"
          aria-labelledby="safety-q"
          tabIndex={-1}
        >
          <h2 id="safety-q">{copy["safety.pause.q"]}</h2>
          <p>{copy["safety.pause.body"]}</p>
          <h3>{copy["safety.pause.list"]}</h3>
          <Helplines />
          <button className="primary" onClick={() => play.resumeStory()}>
            {copy["safety.back"]}
          </button>
          <p className="why">{copy["safety.pause.why"]}</p>
        </div>
      )}
    </div>
  );
}
