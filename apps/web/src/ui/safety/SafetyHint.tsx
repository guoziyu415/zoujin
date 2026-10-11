// The quiet note when the check wasn't sure (frontend-design 12, ux-design 14.2): no pause, no sound, the character
// goes on. Portrait: a paper strip on the right edge just above the subtitles (it moves with their height).
// Landscape: one line in the controls row. Both are rendered and CSS shows one, so only that one is announced
// (role="status", polite, no focus taken). It stays until ✕; 「窓口を見る」 swaps it for the helpline panel.
import { useEffect, useRef } from "react";
import { useVoice } from "../../stores/voice";
import { copy } from "../copy";
import { Helplines } from "./Helplines";

const openPanel = () => useVoice.setState({ hint: false, helpline: "hint" });
const close = () => useVoice.setState({ hint: false });

export function SafetyHint({ where }: { where: "portrait" | "landscape" }) {
  const hint = useVoice((s) => s.hint);
  if (!hint) return null;
  return (
    <div className={`safety-hint ${where}`} role="status" aria-live="polite">
      <button className="open" onClick={openPanel}>
        {where === "portrait" ? (
          <>
            {copy["safety.hint"]}
            <span className="link">{copy["safety.hint.open"]}</span>
          </>
        ) : (
          copy["safety.hint.landscape"]
        )}
      </button>
      <button
        className="close"
        onClick={close}
        aria-label={copy["safety.hint.close"]}
      >
        ✕
      </button>
    </div>
  );
}

// opened from the note: the story goes on underneath (the character finishes the line; the subtitles stay)
export function HelplinePanel() {
  const open = useVoice((s) => s.helpline);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (open) ref.current?.focus();
  }, [open]);
  if (!open) return null;
  return (
    <div
      ref={ref}
      className="sheet helpline"
      role="dialog"
      aria-labelledby="helpline-title"
      tabIndex={-1}
    >
      <h2 id="helpline-title">{copy["safety.panel.title"]}</h2>
      <p>{copy["safety.panel.body"]}</p>
      <Helplines />
      <p className="why">{copy["safety.panel.why"]}</p>
      <button
        className="primary"
        onClick={() => useVoice.setState({ helpline: null })}
      >
        {copy["safety.back"]}
      </button>
    </div>
  );
}
