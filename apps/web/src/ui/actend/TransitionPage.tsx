// The act change (ux-design 4.5, S-080): その頃 (at most three things that happened while the player was away, a
// promise kept or broken marked in ink, each one opens the map at that event), then in the slice the jump page
// 「第四幕 三日目」 (a line per day, one after another; a tap shows the rest; only 〔つづける〕 turns the page,
// WCAG 2.2.1), then the landing: the arrival line joins the narration and, when someone speaks first, act_landed.
import { useEffect, useRef, useState } from "react";
import { play } from "../../net/play";
import { nextStep } from "../../net/story";
import { openOverlay, useStory } from "../../stores/story";
import { addNarration } from "../../stores/voice";
import { useWorld } from "../../stores/world";
import { track } from "../../telemetry/telemetry";
import { copy } from "../copy";
import { Lines } from "../Lines";

export const JUMP_LINE_MS = 1400; // the jump page's lines come one by one〔推断，R1 で調整〕

const DAYS = [
  ["jump.day1.label", "jump.day1"],
  ["jump.day2.label", "jump.day2"],
  ["jump.day3.label", "jump.day3"],
] as const;

const advance = () => {
  const t = useStory.getState().transition;
  if (t) useStory.setState({ transition: nextStep(t) });
};

export function TransitionPage() {
  const t = useStory((s) => s.transition);
  const step = t?.steps[0];
  // the landing has no page: the line goes under the subtitles, the opener is told the player can move
  useEffect(() => {
    if (!t || step !== "arrival") return;
    if (t.arrival) {
      addNarration(t.arrival.line);
      if (t.arrival.opener) play.actLanded(t.toActId);
    }
    useStory.setState({ transition: null });
  }, [t, step]);
  if (!t || !step || step === "arrival") return null;
  return step === "sonokoro" ? <SonoKoro /> : <Jump />;
}

function SonoKoro() {
  const recap = useStory((s) => s.transition?.recap ?? []);
  const head = useRef<HTMLHeadingElement>(null);
  const tapped = useRef(false);
  useEffect(() => head.current?.focus(), []);
  const leave = () => {
    track("sonokoro_viewed", {
      count: recap.length,
      tappedMap: tapped.current,
    });
    advance();
  };
  return (
    <section
      className="page sk"
      role="dialog"
      aria-modal="true"
      aria-labelledby="sk-title"
      onClick={(e) => e.target === e.currentTarget && leave()}
    >
      <div className="page-body">
        <h1 id="sk-title" ref={head} tabIndex={-1}>
          {copy["sonokoro.title"]}
        </h1>
        <ul className="sk-items">
          {recap.map((r) => (
            <li key={r.eventId}>
              <button
                className="sk-item"
                onClick={() => {
                  tapped.current = true;
                  openOverlay({
                    kind: "map",
                    eventId: r.eventId,
                    from: "sonokoro",
                  });
                }}
              >
                <span>{r.line}</span>
                {r.promise && (
                  <span className="sk-promise">
                    {
                      copy[
                        r.promise === "kept"
                          ? "sonokoro.kept"
                          : "sonokoro.broken"
                      ]
                    }
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
        <button
          className="quiet"
          onClick={() => {
            tapped.current = true;
            openOverlay({ kind: "map", from: "sonokoro" });
          }}
        >
          {copy["sonokoro.map"]}
        </button>
        <button className="primary" onClick={leave}>
          {copy["common.continue"]}
        </button>
      </div>
    </section>
  );
}

function Jump() {
  const [shown, setShown] = useState(1);
  const head = useRef<HTMLHeadingElement>(null);
  const tLabel = useWorld((s) => s.world?.clock.tLabel);
  useEffect(() => head.current?.focus(), []);
  useEffect(() => {
    if (shown >= DAYS.length) return;
    const id = setTimeout(() => setShown((n) => n + 1), JUMP_LINE_MS);
    return () => clearTimeout(id);
  }, [shown]);
  return (
    <section
      className="page jump"
      role="dialog"
      aria-modal="true"
      aria-labelledby="jump-title"
      data-time={tLabel}
      onClick={() => setShown(DAYS.length)}
    >
      <div className="page-body">
        <h1 id="jump-title" ref={head} tabIndex={-1}>
          {copy["jump.act"]}
        </h1>
        <dl className="jump-days" aria-live="polite">
          {DAYS.slice(0, shown).map(([label, body]) => (
            <div key={label} className="jump-day">
              <dt>{copy[label]}</dt>
              <dd>
                <Lines text={copy[body]} />
              </dd>
            </div>
          ))}
        </dl>
        <button
          className="primary"
          onClick={(e) => {
            e.stopPropagation();
            advance();
          }}
        >
          {copy["common.continue"]}
        </button>
        <p className="trial-note">
          <Lines text={copy["jump.trialNote"]} />
        </p>
      </div>
    </section>
  );
}
