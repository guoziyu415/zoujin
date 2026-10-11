// Talking by text (ux-design 7.1, 7.4): the key right of the talk key opens a field, 200 characters at most, 「送る」
// sends one turn. Opened with words already in it, it corrects the player's own line (7.6). When the voice can't be
// used (the player chose text, the microphone is refused, degraded) the field is the main way in, with 「声に戻す」
// where going back makes sense. Disabled with the reason when there is nobody to talk to or the connection is down.
import { useEffect, useState, type FormEvent } from "react";
import { play } from "../../net/play";
import { usePlayer } from "../../stores/player";
import { useUi } from "../../stores/ui";
import { useVoice } from "../../stores/voice";
import { copy } from "../copy";

export const TEXT_MAX = 200;

export function TextInput({ primary }: { primary: boolean }) {
  const focus = usePlayer((s) => s.focusCharacter);
  const connection = useUi((s) => s.connection);
  const open = useVoice((s) => s.textOpen) || primary;
  const draft = useVoice((s) => s.draft);
  const mic = useVoice((s) => s.mic);
  const degraded = useVoice((s) => s.degraded);
  const paused = useVoice((s) => s.paused);
  const [text, setText] = useState("");
  const over = [...text].length > TEXT_MAX;

  useEffect(() => {
    if (draft) setText(draft.text);
  }, [draft]);

  if (connection !== "open")
    return primary ? (
      <span className="hint grow">{copy["talk.reconnecting"]}</span>
    ) : null;
  if (!focus)
    return primary ? (
      <span className="hint grow">{copy["talk.disabled"]}</span>
    ) : null;
  if (paused) return null;
  if (!open)
    return <button onClick={() => play.openText()}>{copy["text.open"]}</button>;

  function send(e: FormEvent) {
    e.preventDefault();
    const t = text.trim();
    if (!t || over) return;
    if (draft?.replaces) play.correct(t, draft.replaces);
    else play.say(t);
    setText("");
    if (!primary) play.closeText();
  }
  return (
    <form className="textinput" onSubmit={send}>
      <input
        aria-label={copy["text.placeholder"]}
        placeholder={copy["text.placeholder"]}
        value={text}
        onChange={(e) => setText(e.target.value)}
        enterKeyHint="send"
        autoFocus={!primary}
      />
      <button type="submit" disabled={!text.trim() || over}>
        {copy["text.send"]}
      </button>
      {!degraded && (primary ? mic !== "unavailable" : true) && (
        <button
          type="button"
          onClick={() => (primary ? play.backToVoice() : play.closeText())}
        >
          {copy["text.backToVoice"]}
        </button>
      )}
      {over && (
        <span className="hint" role="alert">
          {copy["text.limit"]}
        </span>
      )}
    </form>
  );
}
