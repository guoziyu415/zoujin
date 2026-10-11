// LINE's own browser (S-015, ux-design 12): the microphone is often not allowed there, so the cover says so first;
// 〔このまま文字で遊ぶ〕 starts with the keyboard. Text plays the whole story either way, and the microphone sheet
// still catches a refusal if the player tries their voice.
import { useState } from "react";
import { voiceSettings } from "../voice/settings";
import { copy } from "./copy";

// LINE adds "Line/<version>" to the browser's user agent (iOS and Android)
export const inLine = (ua: string): boolean => /\sLine\/\d/.test(ua);

export function InAppNotice() {
  const [shown, setShown] = useState(
    () =>
      typeof navigator !== "undefined" &&
      inLine(navigator.userAgent) &&
      !voiceSettings.text,
  );
  if (!shown) return null;
  return (
    <div className="inapp" role="note">
      <p>{copy["inapp.notice"]}</p>
      <button
        className="quiet"
        onClick={() => {
          voiceSettings.rememberText(true);
          setShown(false);
        }}
      >
        {copy["inapp.textOnly"]}
      </button>
    </div>
  );
}
