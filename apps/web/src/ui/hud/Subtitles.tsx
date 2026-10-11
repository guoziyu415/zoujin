// Subtitles (ux-design 7.7): the character's line with its name and where the words came from, the player's own line
// on the right, 「……」 once the voice ended without words, the failed-transcript note, the grey narration, and the
// suggestion chips (7.8). All server text is rendered as text, never HTML.
import { play } from "../../net/play";
import { useVoice, type Line } from "../../stores/voice";
import { copy } from "../copy";

export function Subtitles({ names }: { names: Record<string, string> }) {
  const player = useVoice((s) => s.player);
  const character = useVoice((s) => s.character);
  const turn = useVoice((s) => s.turn);
  const narration = useVoice((s) => s.narration);
  const speaker = useVoice((s) => s.session.character);
  // the voice ended (or a typed turn got its answer) and still no words: grey 「……」, not the thinking dots
  const pending = !character && turn?.phase === "done";
  return (
    <>
      <div className="subs" data-testid="subtitles" aria-live="polite">
        {narration.map((n, i) => (
          <p key={`${i}:${n}`} className="narration" data-testid="narration">
            {n}
          </p>
        ))}
        {player && <PlayerLine line={player} />}
        {character ? (
          <CharacterLine
            line={character}
            name={names[character.speaker] ?? character.speaker}
          />
        ) : (
          pending &&
          speaker && (
            <div className="line">
              <div className="who">{names[speaker] ?? speaker}</div>
              <div className="grey">{copy["sub.pending"]}</div>
            </div>
          )
        )}
      </div>
      <Chips />
    </>
  );
}

function PlayerLine({ line }: { line: Line }) {
  return (
    <div className="line me" data-testid="sub-player">
      <div className="who">
        {copy["sub.me"]}
        {line.fromChip && <span>{copy["sub.fromChip"]}</span>}
      </div>
      <div>{line.text}</div>
    </div>
  );
}

function CharacterLine({ line, name }: { line: Line; name: string }) {
  const tag =
    line.source === "script"
      ? copy["sub.source"]
      : line.source === "fallback" && line.text
        ? copy["sub.transcribed"]
        : null;
  return (
    <div className="line" data-testid="sub-character">
      <div className="who">
        {name}
        {tag && <span>{tag}</span>}
      </div>
      {line.text === null ? (
        <div className="grey">{copy["sub.failed"]}</div>
      ) : (
        <div>{line.text}</div>
      )}
    </div>
  );
}

function Chips() {
  const s = useVoice((v) => v.suggestions);
  const focus = useVoice((v) => v.session.character);
  if (!s || s.character !== focus || !s.items.length) return null;
  return (
    <div className="chips">
      {s.items.map((i) => (
        <button key={i.text} onClick={() => play.say(i.text, "chip")}>
          {i.text}
        </button>
      ))}
    </div>
  );
}
