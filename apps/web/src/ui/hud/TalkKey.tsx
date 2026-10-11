// The talk key (ux-design 7.1, frontend-design 7.4): hold to talk, let go to send, slide up 60 px to cancel; a
// press under 250 ms is a slip. Pointer events with capture (so the slide is seen), no text selection or callout
// menu, touch-action none on the key only. Tap mode (settings) starts and ends with two taps. Space or Enter work
// the same way from a keyboard. The ring follows the microphone's level, read each frame without React updates.
import {
  useEffect,
  useRef,
  type KeyboardEvent,
  type PointerEvent,
} from "react";
import { levels } from "../../audio/engine";
import { play } from "../../net/play";
import { useUi } from "../../stores/ui";
import { useVoice } from "../../stores/voice";
import { canPress } from "../../voice/state";
import { voiceSettings } from "../../voice/settings";
import { useVoiceState } from "../../voice/useVoiceState";
import { copy } from "../copy";
import { KEY_LINE, keyFontPx, phrases } from "./phrases";

const SLIDE_PX = 60;

export function TalkKey() {
  const state = useVoiceState();
  const hold = useVoice((s) => s.hold);
  const connection = useUi((s) => s.connection);
  const ref = useRef<HTMLButtonElement>(null);
  const startY = useRef(0);
  const tap = voiceSettings.tap;

  // the ring: --level from the microphone's peak while listening
  useEffect(() => {
    if (!hold) return;
    let raf = 0;
    const tick = () => {
      ref.current?.style.setProperty(
        "--level",
        Math.min(1, levels.mic * 1.4).toFixed(2),
      );
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      ref.current?.style.setProperty("--level", "0");
    };
  }, [hold]);

  const label =
    state === "listening"
      ? hold?.slide
        ? copy["talk.slideCancel"]
        : hold?.preparing
          ? copy["talk.preparing"]
          : copy["talk.listening"]
      : state === "thinking"
        ? copy["talk.thinking"]
        : state === "reconnecting"
          ? // only a drop says so: the first connect stays blank, a taken tab has its banner
            connection === "reconnecting"
            ? copy["talk.reconnecting"]
            : ""
          : state === "away"
            ? copy["talk.disabled"]
            : tap
              ? copy["talk.tap"]
              : copy["talk.hold"];
  const enabled = canPress(state) || state === "listening";
  const parts = phrases(label, KEY_LINE);

  function down(e: PointerEvent<HTMLButtonElement>) {
    if (e.button !== 0) return;
    e.preventDefault();
    if (tap) {
      if (useVoice.getState().hold) play.release();
      else play.press();
      return;
    }
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      // synthetic events
    }
    startY.current = e.clientY;
    play.press();
  }
  function move(e: PointerEvent<HTMLButtonElement>) {
    if (!tap && useVoice.getState().hold)
      play.slide(startY.current - e.clientY > SLIDE_PX);
  }
  function up() {
    if (!tap) play.release();
  }
  function key(e: KeyboardEvent<HTMLButtonElement>, isDown: boolean) {
    if (e.key !== " " && e.key !== "Enter") return;
    e.preventDefault();
    if (isDown && !e.repeat) {
      if (tap && useVoice.getState().hold) play.release();
      else play.press();
    } else if (!isDown && !tap) play.release();
  }

  return (
    <button
      ref={ref}
      className={`talk ${state}`}
      data-testid="talk"
      data-state={state}
      disabled={!enabled}
      aria-pressed={state === "listening"}
      aria-label={label ? undefined : copy["talk.hold"]}
      onPointerDown={down}
      onPointerMove={move}
      onPointerUp={up}
      onPointerCancel={up}
      onKeyDown={(e) => key(e, true)}
      onKeyUp={(e) => key(e, false)}
      onContextMenu={(e) => e.preventDefault()}
      style={{ fontSize: keyFontPx(parts) }}
    >
      {parts.map((p, i) => (
        <span key={i} className="phrase">
          {p}
        </span>
      ))}
    </button>
  );
}
