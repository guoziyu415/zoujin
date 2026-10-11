// Talking by text (ux-design 7.4): 「文字で話す」 opens a field, 200 characters at most, 「送る」 sends one turn.
// Disabled with the reason when there is nobody to talk to or the connection is being restored.
import { useState, type FormEvent } from "react";
import { play } from "../../net/play";
import { usePlayer } from "../../stores/player";
import { useUi } from "../../stores/ui";
import { useVoice } from "../../stores/voice";
import { copy } from "../copy";

export const TEXT_MAX = 200;

export function TextInput() {
  const focus = usePlayer((s) => s.focusCharacter);
  const connection = useUi((s) => s.connection);
  const waiting = useVoice((s) => s.turn?.phase === "waiting");
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const over = [...text].length > TEXT_MAX;

  if (connection !== "open")
    return <span className="hint grow">{copy["talk.reconnecting"]}</span>;
  if (!focus) return <span className="hint grow">{copy["talk.disabled"]}</span>;
  if (!open)
    return (
      <>
        <span className="hint grow">
          {waiting ? copy["talk.thinking"] : ""}
        </span>
        <button onClick={() => setOpen(true)}>{copy["text.open"]}</button>
      </>
    );

  function send(e: FormEvent) {
    e.preventDefault();
    const t = text.trim();
    if (!t || over) return;
    play.say(t);
    setText("");
  }
  return (
    <form className="textinput" onSubmit={send}>
      <input
        aria-label={copy["text.placeholder"]}
        placeholder={copy["text.placeholder"]}
        value={text}
        onChange={(e) => setText(e.target.value)}
        enterKeyHint="send"
      />
      <button type="submit" disabled={!text.trim() || over}>
        {copy["text.send"]}
      </button>
      {over && (
        <span className="hint" role="alert">
          {copy["text.limit"]}
        </span>
      )}
    </form>
  );
}
