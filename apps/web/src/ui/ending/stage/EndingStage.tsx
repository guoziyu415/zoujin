// The ending's staging over the 3D (ux-design 11.1, S-089): the lines of the closing set pieces and the narration,
// one at a time at the bottom, paced by pace.ts; a tap anywhere completes or moves on. The 3D layer frames the shots
// (bridge.ts). When the last line has had its time: to the ending page if the ending is written, else
// 「物語を綴じています（n秒）」 counting up, with the map offered after 20 s.
import { useQuery } from "@tanstack/react-query";
import { useEffect, useReducer, useRef, useState } from "react";
import { manifestQuery } from "../../../app/queries";
import { navigate } from "../../../app/router";
import { audio } from "../../../audio";
import { isCrowd } from "../../../audio/engine";
import {
  endingFrame,
  openOverlay,
  useStory,
  type EndingLine,
} from "../../../stores/story";
import { useUi } from "../../../stores/ui";
import { track } from "../../../telemetry/telemetry";
import { copy, fill } from "../../copy";
import { useEndingAuto } from "../settings";
import { stageBridge } from "./bridge";
import {
  addLines,
  initPace,
  insertLine,
  performed,
  pause,
  resume,
  setAuto,
  shotDone,
  tap,
  tick,
  visibleText,
  type Effect,
  type Pace,
  type StageLine,
} from "./pace";
import { cardShot, shotOf } from "./shots";

export const BINDING_LONG_S = 20; // the map is offered after 20 s of waiting (ux-design 11.1)
const TICK_MS = 100;
const NO_LINES_MS = 3000;

export function EndingStage({
  pid,
  names,
}: {
  pid: string;
  names: Record<string, string>;
}) {
  const ending = useStory((s) => s.ending);
  const overlayOpen = useStory((s) => !!s.overlay);
  const gate = useUi((s) => s.resumeGate);
  const auto = useEndingAuto();
  const manifest = useQuery(manifestQuery);
  const voices = manifest.data?.setPieceVoices;
  const pace = useRef<Pace>(initPace(auto));
  const fed = useRef(0);
  const autoAtStart = useRef(auto); // the setting can't change once the staging began (11.1)
  const reported = useRef(false);
  const [, render] = useReducer((n: number) => n + 1, 0);
  const [done, setDone] = useState(false);
  const seen = useRef(new Set<number>()); // the shots so far; the card's frame is taken when its best one comes

  const clipOf = (l: StageLine) => (l.key ? (voices?.[l.key] ?? null) : null);

  function apply(fx: Effect[]) {
    for (const e of fx) {
      if (e.k === "play") {
        const l = pace.current.lines[e.i];
        const clip = l && clipOf(l);
        // not loaded (yet): the line shows whole and is timed like narration
        if (!clip || !audio.playClip(clip, undefined, isCrowd(l.speaker))) {
          const lines = pace.current.lines.slice();
          lines[e.i] = { ...lines[e.i]!, clipMs: null };
          pace.current = { ...pace.current, lines, whole: true };
        }
      } else if (e.k === "fade") audio.fadeOut(200);
      else if (e.k === "shot") {
        stageBridge().shot(e.n);
        const had = cardShot(seen.current);
        seen.current.add(e.n);
        if (cardShot(seen.current) === e.n && had !== e.n)
          void stageBridge()
            .captureFrame()
            .then((b) => b && endingFrame.set(b));
      } else if (e.k === "drained") setDone(true);
    }
  }

  // new lines from the server
  useEffect(() => {
    // before the character on stage has finished, the lines only gather (nothing shown, no shot)
    if (!ending?.ready) return;
    const lines = ending.lines;
    if (lines.length <= fed.current) return;
    const fresh = lines.slice(fed.current);
    const more = fresh.map((l) => toStage(l, voices));
    fed.current = lines.length;
    audio.preload(
      more.flatMap((l) => {
        const c = l.key ? voices?.[l.key] : undefined;
        return c ? [c] : [];
      }),
    );
    const now = performance.now();
    let p = pace.current;
    const fx: Effect[] = [];
    const late = more.filter((_, i) => !fresh[i]!.early);
    if (late.length) {
      const [q, f] = addLines(p, late, now);
      p = q;
      fx.push(...f);
    }
    // the action that ended the story goes before the curtain (3.13, UX review of #127)
    for (const [i, l] of more.entries()) {
      if (!fresh[i]!.early) continue;
      const [q, f] = insertLine(p, l, now);
      p = q;
      fx.push(...f);
    }
    pace.current = p;
    if (more.length) setDone(false);
    apply(fx);
    render();
  }, [ending?.lines, ending?.ready, voices]);

  // the clock
  useEffect(() => {
    const id = setInterval(() => {
      const [p, fx] = tick(pace.current, performance.now());
      const changed = p !== pace.current;
      pace.current = p;
      apply(fx);
      if (changed || fx.length) render();
    }, TICK_MS);
    const off = stageBridge().onShotDone((n) => {
      pace.current = shotDone(pace.current, n);
    });
    return () => {
      clearInterval(id);
      off();
    };
  }, []);

  useEffect(() => {
    pace.current = setAuto(pace.current, auto);
    if (pace.current.t0 === null) autoAtStart.current = auto;
  }, [auto]);

  // in the background, behind a full page, behind the resume gate: the staging and its clock stop
  useEffect(() => {
    const sync = () => {
      const stop = document.visibilityState === "hidden" || overlayOpen || gate;
      pace.current = stop
        ? pause(pace.current, performance.now())
        : resume(pace.current, performance.now());
      stageBridge().pause(stop);
      // the recorded line stops where it is and goes on from there (11.1)
      if (stop) audio.pauseClip();
      else audio.resumeClip();
    };
    sync();
    document.addEventListener("visibilitychange", sync);
    return () => document.removeEventListener("visibilitychange", sync);
  }, [overlayOpen, gate]);

  // no closing lines at all: the ending is already written, or none come within NO_LINES_MS — a reload in the middle
  // of the staging (the server sends ending_started again, not the set pieces): the binding line or the ending page
  const noLines = !ending?.lines.length;
  const ready = !!ending?.ready;
  useEffect(() => {
    if (!noLines || !ready) return;
    if (ending?.endingId) return setDone(true);
    const id = setTimeout(() => setDone(true), NO_LINES_MS);
    return () => clearTimeout(id);
  }, [noLines, ready, ending?.endingId]);

  // the last line had its time: the ending page, or wait for it
  const trigger = ending?.trigger;
  useEffect(() => {
    if (!done) return;
    const m = reported.current
      ? null
      : performed(pace.current, performance.now());
    // data's pacing check (ux-design 11.1, data-design 9.3): how long it played, taps, auto on or off
    if (m && trigger) {
      reported.current = true;
      track("ending_performed", {
        ...m,
        trigger,
        autoAdvance: autoAtStart.current,
      });
    }
    if (ending?.endingId)
      navigate(`/ending/${encodeURIComponent(pid)}`, { replace: true });
  }, [done, ending?.endingId, trigger, pid]);

  if (!ending) return null;
  const p = pace.current;
  const line = p.lines[p.i];
  const onTap = () => {
    const [q, fx] = tap(pace.current, performance.now());
    pace.current = q;
    apply(fx);
    render();
  };
  return (
    <div
      className="end-stage"
      onClick={onTap}
      data-line={p.i}
      data-shot={p.shot ?? ""}
    >
      {line && !done && (
        <p
          className={`end-sub${line.speaker ? " voiced" : ""}`}
          aria-live="polite"
        >
          {line.speaker && (
            <span className="who">{names[line.speaker] ?? line.speaker}</span>
          )}
          <span>{visibleText(p, performance.now())}</span>
        </p>
      )}
      {done && !ending.endingId && <Binding />}
    </div>
  );
}

function toStage(
  l: EndingLine,
  voices: Record<string, { durationMs: number } | undefined> | undefined,
): StageLine {
  const key = l.pieceId && l.n ? `${l.pieceId}/${l.n}` : undefined;
  const clip = l.speaker && key ? voices?.[key] : undefined;
  const s = l.pieceId && l.n ? shotOf(l.pieceId, l.n, l.text) : { shot: null };
  return {
    text: l.text,
    speaker: l.speaker,
    clipMs: clip ? clip.durationMs : null,
    ...s,
    ...(key ? { key } : {}),
  };
}

// 「物語を綴じています（n秒）」 counting up; no fake progress bar
function Binding() {
  const [s, setS] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setS((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="end-binding" role="status">
      <p>{fill(copy["ending.binding"], { n: s })}</p>
      {s >= BINDING_LONG_S && (
        <button
          className="quiet"
          onClick={(e) => {
            e.stopPropagation();
            openOverlay({ kind: "map", from: "ending" });
          }}
        >
          {copy["ending.binding.long"]}
        </button>
      )}
    </div>
  );
}
