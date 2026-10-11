// LINE's own browser (S-015, ux-design 12): the microphone is often not allowed there, so the cover says so first;
// 〔このまま文字で遊ぶ〕 starts with the keyboard, 〔Safariで開く方法〕 (Chrome on Android) says how to get out of LINE
// (copy-ja 1). Text plays the whole story either way, and the microphone sheet still catches a refusal if the player
// tries their voice. 〔ブラウザで開く〕 (openExternalBrowser=1) waits until it has been tried in LINE on both phones.
import { useState } from "react";
import { voiceSettings } from "../voice/settings";
import { copy } from "./copy";
import { phoneOf } from "./hud/MicSheet";

// LINE adds "Line/<version>" to the browser's user agent (iOS and Android)
export const inLine = (ua: string): boolean => /\sLine\/\d/.test(ua);

const COPIED_MS = 2000;

export function InAppNotice() {
  const [shown, setShown] = useState(
    () =>
      typeof navigator !== "undefined" &&
      inLine(navigator.userAgent) &&
      !voiceSettings.text,
  );
  const [howto, setHowto] = useState(false);
  const [copied, setCopied] = useState<"yes" | "no" | null>(null);
  if (!shown) return null;
  const android =
    phoneOf(navigator.userAgent, navigator.maxTouchPoints) === "android";
  const link = `${location.origin}/`; // the cover's address: no path, no query (copy-ja inapp.copyLink)
  const copyLink = () => {
    const done = (ok: boolean) => {
      setCopied(ok ? "yes" : "no");
      if (ok) setTimeout(() => setCopied(null), COPIED_MS);
    };
    if (!navigator.clipboard) return done(false);
    navigator.clipboard.writeText(link).then(
      () => done(true),
      () => done(false),
    );
  };
  return (
    <div className="inapp" role="note">
      <p>{copy["inapp.notice"]}</p>
      <div className="row">
        <button
          className="quiet"
          aria-expanded={howto}
          onClick={() => setHowto(!howto)}
        >
          {android ? copy["inapp.howto.android"] : copy["inapp.howto"]}
        </button>
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
      {howto && (
        <div className="inapp-steps">
          <p>
            {android ? copy["inapp.steps.android"] : copy["inapp.steps.ios"]}
          </p>
          <p>
            {copy["inapp.steps.copy"].replace(
              "{browser}",
              android ? "Chrome" : "Safari",
            )}
          </p>
          <button onClick={copyLink}>{copy["inapp.copyLink"]}</button>
          {copied === "yes" && <p role="status">{copy["inapp.copied"]}</p>}
          {copied === "no" && <p className="inapp-link">{link}</p>}
          <p>{copy["inapp.steps.code"]}</p>
        </div>
      )}
    </div>
  );
}
