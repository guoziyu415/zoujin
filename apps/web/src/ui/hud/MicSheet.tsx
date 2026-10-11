// The microphone's half pages (ux-design 7.3, 12): the primer before the first use (what is heard, what is kept),
// and what to do when the microphone is refused or doesn't work. Text is always the way on.
import { useState } from "react";
import { play } from "../../net/play";
import { useVoice } from "../../stores/voice";
import { copy } from "../copy";

// which settings to explain: this phone's only (ux-design 12); a computer, or one we can't tell, gets both
export function phoneOf(ua: string, touch: number): "ios" | "android" | null {
  if (/Android/i.test(ua)) return "android";
  if (/iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && touch > 1))
    return "ios"; // iPadOS asks for the desktop site and says Macintosh
  return null;
}

export function MicSheet() {
  const sheet = useVoice((s) => s.sheet);
  const [howto, setHowto] = useState(false);
  if (!sheet) return null;
  const phone = phoneOf(navigator.userAgent, navigator.maxTouchPoints);
  if (sheet === "primer")
    return (
      <div
        className="sheet mic"
        role="dialog"
        aria-modal="true"
        aria-labelledby="primer-title"
      >
        <h2 id="primer-title">{copy["primer.title"]}</h2>
        <p>{copy["primer.body1"]}</p>
        <p className="small">{copy["primer.body2"]}</p>
        <div className="row">
          <button className="primary" onClick={() => play.primer("mic")}>
            {copy["primer.use"]}
          </button>
          <button onClick={() => play.primer("text")}>
            {copy["primer.text"]}
          </button>
        </div>
      </div>
    );
  return (
    <div
      className="sheet mic"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="mic-title"
    >
      <h2 id="mic-title">
        {sheet === "denied" ? copy["mic.denied"] : copy["mic.unavailable"]}
      </h2>
      {sheet === "denied" && howto && (
        <ul className="howto">
          {phone !== "android" && <li>{copy["mic.denied.ios"]}</li>}
          {phone !== "ios" && <li>{copy["mic.denied.android"]}</li>}
        </ul>
      )}
      <div className="row">
        <button className="primary" onClick={() => play.continueInText()}>
          {copy["mic.textContinue"]}
        </button>
        {sheet === "denied" && !howto && (
          <button onClick={() => setHowto(true)}>{copy["mic.howto"]}</button>
        )}
      </div>
    </div>
  );
}
