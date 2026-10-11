// The act-end page (ux-design 4.4; slice copy in copy-ja 6): a book page over the darkened scene. The guards' rumour,
// 「三日のあいだ、あなたは──」, the exits (label; where + sub as two wholes that wrap at the full-width space), and
// 「ほかの考えがある」, which turns the lower half into the input: say or type a plan, wait while the dash grows, read
// the narrator's answer. A third try isn't offered (「夜が更けていく。…」). Once an exit is chosen the page waits for
// the act change and takes no more taps.
import type { Api } from "@zoujin/contracts";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { play } from "../../net/play";
import {
  backToExits,
  canPropose,
  clearNotHeard,
  openPropose,
  type ActEndState,
} from "../../net/story";
import { openOverlay, useStory } from "../../stores/story";
import { copy, fill } from "../copy";
import { Lines } from "../Lines";
import { TEXT_MAX } from "../hud/TextInput";

export const THINKING_LINE_MS = 3000; // 「考えをめぐらせている……」 after 3 s (ux-design 4.4)

const set = (f: (a: ActEndState) => ActEndState) => {
  const a = useStory.getState().actEnd;
  if (a) useStory.setState({ actEnd: f(a) });
};

export function ActEndPage() {
  const a = useStory((s) => s.actEnd);
  const head = useRef<HTMLHeadingElement>(null);
  useEffect(() => head.current?.focus(), []);
  if (!a) return null;
  const { end, phase } = a;
  const slice = end.actId === "act.1"; // the slice's opening lines are written in the client for now (copy-ja 6)
  const waiting =
    phase.k === "thinking" ||
    phase.k === "chosen" ||
    (phase.k === "result" && phase.accepted);
  return (
    <section
      className="page ae"
      role="dialog"
      aria-modal="true"
      aria-labelledby="ae-title"
      aria-busy={waiting}
      data-phase={phase.k}
    >
      <div className="page-body">
        <h1 id="ae-title" ref={head} tabIndex={-1}>
          {copy["actEnd.title"]}
        </h1>
        {slice && (
          <>
            <p className="ae-rumor">
              <Lines text={copy["actEnd.rumor"]} />
            </p>
            <p>{copy["actEnd.melosLeft"]}</p>
          </>
        )}
        <p className="ae-prompt">
          {copy["actEnd.prompt"]}
          {phase.k === "thinking" && <span className="ae-dash" aria-hidden />}
        </p>
        {phase.k === "choose" && <Exits a={a} />}
        {phase.k === "chosen" && <Exits a={a} />}
        {phase.k === "propose" && <Propose notHeard={phase.notHeard} />}
        {phase.k === "thinking" && <Thinking />}
        {phase.k === "result" && <Result phase={phase} />}
        <Recap lines={end.recapLines} />
      </div>
    </section>
  );
}

function Exits({ a }: { a: ActEndState }) {
  const chosen = a.phase.k === "chosen" ? a.phase.optionId : null;
  const [enRoute, setEnRoute] = useState<Api.ActOption | null>(null);
  if (enRoute?.enRoute)
    return (
      <div className="ae-enroute">
        <p>{enRoute.enRoute.line}</p>
        <div className="ae-two">
          {enRoute.enRoute.choices.map((c) => (
            <button
              key={c.index}
              className="ae-choice"
              disabled={chosen !== null}
              onClick={() => play.actChoose(enRoute.optionId, c.index)}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>
    );
  return (
    <>
      {a.giveUp && <p className="ae-narr">{copy["actEnd.propose.giveUp"]}</p>}
      <ul className="ae-exits">
        {a.end.options.map((o) => (
          <li key={o.optionId}>
            <button
              className="ae-exit"
              disabled={chosen !== null}
              aria-pressed={chosen === o.optionId}
              onClick={() =>
                o.enRoute ? setEnRoute(o) : play.actChoose(o.optionId)
              }
            >
              <span className="ae-label">{o.label}</span>
              <span className="ae-sub">
                <span className="ae-where">{o.where}</span>
                {o.sub && (
                  <>
                    {"　"}
                    <span className="ae-where">{o.sub}</span>
                  </>
                )}
              </span>
              {o.because && <span className="ae-because">{o.because}</span>}
            </button>
          </li>
        ))}
        {canPropose(a) && (
          <li>
            <button
              className="ae-exit other"
              disabled={chosen !== null}
              onClick={() => set(openPropose)}
            >
              <span className="ae-label">{copy["actEnd.other"]}</span>
              <span className="ae-sub">{copy["actEnd.other.sub"]}</span>
            </button>
          </li>
        )}
      </ul>
    </>
  );
}

function Propose({ notHeard }: { notHeard: boolean }) {
  const [text, setText] = useState("");
  const over = [...text].length > TEXT_MAX;
  function send(e: FormEvent) {
    e.preventDefault();
    if (!text.trim() || over) return;
    play.actPropose(text);
  }
  return (
    <div className="ae-propose">
      <p className="ae-ask" role={notHeard ? "status" : undefined}>
        {notHeard
          ? copy["actEnd.propose.notHeard"]
          : copy["actEnd.propose.prompt"]}
      </p>
      <form className="textinput" onSubmit={send}>
        <input
          aria-label={copy["actEnd.propose.prompt"]}
          placeholder={copy["actEnd.propose.placeholder"]}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            set(clearNotHeard);
          }}
          enterKeyHint="send"
          autoFocus
        />
        <button type="submit" disabled={!text.trim() || over}>
          {copy["actEnd.propose.send"]}
        </button>
      </form>
      {over && <p className="error">{copy["text.limit"]}</p>}
      <button className="quiet" onClick={() => set(backToExits)}>
        {copy["actEnd.propose.back"]}
      </button>
    </div>
  );
}

function Thinking() {
  const [late, setLate] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setLate(true), THINKING_LINE_MS);
    return () => clearTimeout(t);
  }, []);
  return (
    <p className="ae-narr" role="status">
      {late ? copy["actEnd.propose.thinking"] : ""}
    </p>
  );
}

function Result({
  phase,
}: {
  phase: Extract<ActEndState["phase"], { k: "result" }>;
}) {
  return (
    <div className="ae-result" role="status">
      {phase.narration.map((l, i) => (
        <p key={i} className="ae-narr">
          {l}
        </p>
      ))}
      {!phase.accepted && (
        <div className="ae-two">
          {phase.alternative && (
            <button
              className="ae-choice"
              onClick={() => play.actChoose(phase.alternative!.optionId)}
            >
              {copy["actEnd.propose.alt.yes"]}
            </button>
          )}
          <button className="ae-choice" onClick={() => set(backToExits)}>
            {copy["actEnd.propose.alt.no"]}
          </button>
        </div>
      )}
    </div>
  );
}

function Recap({ lines }: { lines: string[] }) {
  return (
    <details className="ae-recap">
      <summary>{fill(copy["actEnd.summary"], { n: lines.length })}</summary>
      {lines.length ? (
        <ul>
          {lines.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
      ) : (
        <p>{copy["actEnd.summary.empty"]}</p>
      )}
      <button className="quiet" onClick={() => openOverlay({ kind: "map" })}>
        {copy["actEnd.summary.map"]}
      </button>
    </details>
  );
}
