// Subtitles (ux-design 7.7): the character's line with its name and where the words came from (following the voice,
// frontend-design 7.5), 「——」 where the player spoke over it, the player's own line on the right (live while
// talking; tap it to correct the words, 7.6; struck through when cancelled), 「……」 once the voice ended without
// words, the failed-transcript note, the grey narration, and the suggestion chips (7.8) or the no-response chips
// (7.5). All server text is rendered as text, never HTML, and broken only between phrases (phrases.ts; UX on #146:
// never 人を殺しているそ / うです).
import { play } from "../../net/play";
import { retractKind, useVoice, type Line } from "../../stores/voice";
import { voiceSettings } from "../../voice/settings";
import { useVoiceState } from "../../voice/useVoiceState";
import { copy } from "../copy";
import { phrases } from "./phrases";

function Phrased({ text }: { text: string }) {
  return (
    <>
      {phrases(text).map((p, i) => (
        <span key={i} className="phrase">
          {p}
        </span>
      ))}
    </>
  );
}

export function Subtitles({ names }: { names: Record<string, string> }) {
  const player = useVoice((s) => s.player);
  const character = useVoice((s) => s.character);
  const turn = useVoice((s) => s.turn);
  const narration = useVoice((s) => s.narration);
  const speaker = useVoice((s) => s.session.character);
  // a typed turn's answer is done and still no words: grey 「……」, not the thinking dots
  const pending = !character && turn?.phase === "done";
  // the player's words can be corrected once final, for a turn spoken (not typed) and not cancelled
  const editable =
    !!player &&
    player.final &&
    !player.cancelled &&
    player.text !== null &&
    turn?.turnId === player.turnId &&
    turn.kind === "voice" &&
    turn.phase !== "listening";
  return (
    <>
      <div className="subs" data-testid="subtitles" aria-live="polite">
        {narration.map((n, i) => (
          <p key={`${i}:${n}`} className="narration" data-testid="narration">
            <Phrased text={n} />
          </p>
        ))}
        {player && <PlayerLine line={player} editable={editable} />}
        {character ? (
          <CharacterLine
            line={character}
            name={names[character.speaker] ?? character.speaker}
            ended={!!turn?.ended && turn.turnId === character.turnId}
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
      <TurnActions />
    </>
  );
}

function PlayerLine({ line, editable }: { line: Line; editable: boolean }) {
  const words = line.text ?? "";
  return (
    <div
      className={`line me${line.cancelled ? " cancelled" : ""}${line.final ? "" : " partial"}`}
      data-testid="sub-player"
    >
      <div className="who">
        {copy["sub.me"]}
        {line.fromChip && <span>{copy["sub.fromChip"]}</span>}
      </div>
      {editable ? (
        <button
          className="said"
          onClick={() => play.openText({ text: words, replaces: line.turnId })}
        >
          <Phrased text={words} />
        </button>
      ) : (
        <div>
          {line.cancelled ? (
            <s>
              <Phrased text={words} />
            </s>
          ) : (
            <Phrased text={words} />
          )}
        </div>
      )}
    </div>
  );
}

function CharacterLine({
  line,
  name,
  ended,
}: {
  line: Line;
  name: string;
  ended: boolean;
}) {
  const tag =
    line.source === "script" && line.final
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
      ) : line.text === "" && ended ? (
        <div className="grey">{copy["sub.pending"]}</div>
      ) : (
        <div>
          <Phrased text={line.text} />
          {line.cut && "——"}
        </div>
      )}
    </div>
  );
}

// under the subtitles: 取り消す / 言い直す (7.5), the no-response chips (7.5), the suggestion chips (7.8), and the
// short notes (a slip of the key, the microphone just allowed)
function TurnActions() {
  const state = useVoiceState();
  const turn = useVoice((s) => s.turn);
  const note = useVoice((s) => s.note);
  const ready = useVoice((s) => s.micReady);
  const s = useVoice((v) => v.suggestions);
  const focus = useVoice((v) => v.session.character);
  const retract = retractKind(turn);
  return (
    <div className="chips" data-testid="chips">
      {note === "tooShort" && (
        <span className="note-line" role="status">
          {copy["talk.tooShort"]}
        </span>
      )}
      {ready && (
        <span className="note-line" role="status">
          {voiceSettings.tap ? copy["primer.ready.tap"] : copy["primer.ready"]}
        </span>
      )}
      {retract && (
        <button className="retract" onClick={() => play.retract()}>
          {retract === "cancel" ? copy["retract.cancel"] : copy["retract.redo"]}
        </button>
      )}
      {state === "no-response" ? (
        <>
          <button onClick={() => play.again()}>{copy["wait.again"]}</button>
          <button onClick={() => play.openText()}>{copy["wait.text"]}</button>
        </>
      ) : (
        s &&
        s.character === focus &&
        state !== "listening" &&
        s.items.map((i) => (
          <button key={i.text} onClick={() => play.say(i.text, "chip")}>
            {i.text}
          </button>
        ))
      )}
    </div>
  );
}
