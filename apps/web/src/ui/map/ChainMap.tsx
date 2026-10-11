// 連鎖反応マップ (ux-design 9; copy-ja 8): a vertical timeline by day, a list (it reads aloud as one). Your deeds a
// scarlet dot and 「あなた」; what they caused an ink dot with a thin scarlet line back; what someone did for you with
// their name and 「あなたのために」; the original's beats in grey boxes with how they stand now; beats not yet come (or
// not known) only their time and 「？」. The deadline line on top (the crisis line opens the why of the forecast).
// Chips filter by person and by 「わたしの行動だけ」. A node opens in place: summary, time, who knows, and
// 「なぜこうなった？」, the chain from your deed to it in time order.
import type { Api } from "@zoujin/contracts";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { rest } from "../../net/rest";
import { openOverlay, useStory } from "../../stores/story";
import { useWorld } from "../../stores/world";
import { track } from "../../telemetry/telemetry";
import { copy, fill } from "../copy";
import { FullPage } from "../FullPage";
import {
  corrected,
  itemId,
  nowIndex,
  people,
  shown,
  type Filter,
} from "./view";

const BEAT = {
  canon: "map.beat.canon",
  hastened: "map.beat.hastened",
  delayed: "map.beat.delayed",
  prevented: "map.beat.prevented",
  altered: "map.beat.altered",
} as const;

export default function ChainMap({
  pid,
  names,
  eventId,
  why,
}: {
  pid: string;
  names: Record<string, string>;
  eventId?: string;
  why?: string;
}) {
  const from = useStory((s) =>
    s.overlay?.kind === "map" ? (s.overlay.from ?? "hud") : "hud",
  );
  const q = useQuery({
    queryKey: ["timeline", pid],
    queryFn: () => rest.timeline(pid),
  });
  const deadline = useWorld((s) => s.world?.deadline);
  const forecast = useWorld((s) => s.world?.forecast);
  const now = useWorld((s) => s.world?.clock.t ?? 0);
  const events = useWorld((s) => s.world?.events);
  const fixed = useMemo(() => corrected(events ?? []), [events]);
  // the timeline item doesn't name who did it; the events this page has seen do (an older one shows no name)
  const actors = useMemo(
    () => new Map((events ?? []).map((e) => [e.eventId, e.actor])),
    [events],
  );
  const [filter, setFilter] = useState<Filter>({
    character: null,
    mine: false,
  });
  const [open, setOpen] = useState<string | null>(eventId ?? null);
  const [whyOf, setWhyOf] = useState<string | null>(why ?? null);
  const list = useRef<HTMLOListElement>(null);
  const name = (id: string) => names[id] ?? id;
  const crisis = forecast?.beforeDeadline === false;

  useEffect(() => track("map_opened", { from }), [from]);
  // scroll to the event it was opened for, or the latest one
  useEffect(() => {
    if (!q.data || !list.current) return;
    const target = eventId
      ? list.current.querySelector(`[data-id="${CSS.escape(eventId)}"]`)
      : list.current.querySelector("[data-now]");
    target?.scrollIntoView({ block: "center" });
  }, [q.data, eventId]);

  const chips = q.data ? people(q.data.days) : [];
  return (
    <FullPage
      title={copy["map.title"]}
      className="map"
      onClose={() => openOverlay(null)}
    >
      {deadline?.shown &&
        (crisis ? (
          <button
            className="map-deadline crisis"
            onClick={() => setWhyOf("forecast")}
          >
            {copy["deadline.crisis"]}
          </button>
        ) : (
          <p className="map-deadline">{deadline.line}</p>
        ))}
      {whyOf === "forecast" && <Why pid={pid} target="forecast" />}
      <p className="small">{copy["map.legend"]}</p>
      <div className="map-chips" role="group" aria-label={copy["map.title"]}>
        <button
          aria-pressed={filter.mine}
          onClick={() => setFilter((f) => ({ ...f, mine: !f.mine }))}
        >
          {copy["map.filter.mine"]}
        </button>
        {chips.map((c) => (
          <button
            key={c}
            aria-pressed={filter.character === c}
            onClick={() =>
              setFilter((f) => ({
                ...f,
                character: f.character === c ? null : c,
              }))
            }
          >
            {name(c)}
          </button>
        ))}
      </div>
      {q.isError && <p className="error">{copy["net.failed"]}</p>}
      <ol className="map-days" ref={list}>
        {q.data?.days.map((d) => {
          const items = shown(d.items, filter);
          const nowAt = nowIndex(d.items, now);
          const lastDay = d === q.data.days.at(-1);
          return (
            <li key={d.day} className="map-day">
              <h2>{d.label}</h2>
              <ol className="map-items">
                {items.map((it) => (
                  <Node
                    key={itemId(it)}
                    pid={pid}
                    it={it}
                    name={name}
                    actor={actors}
                    fixed={fixed}
                    isOpen={open === itemId(it)}
                    onToggle={() =>
                      setOpen((o) => (o === itemId(it) ? null : itemId(it)))
                    }
                    now={
                      lastDay && d.items.indexOf(it) === nowAt && !filter.mine
                    }
                    showWhy={whyOf === itemId(it)}
                    onWhy={() => setWhyOf(itemId(it))}
                  />
                ))}
              </ol>
            </li>
          );
        })}
      </ol>
    </FullPage>
  );
}

function Node({
  pid,
  it,
  name,
  actor,
  fixed,
  isOpen,
  onToggle,
  now,
  showWhy,
  onWhy,
}: {
  pid: string;
  it: Api.TimelineItem;
  name: (id: string) => string;
  actor: Map<string, string>;
  fixed: Set<string>;
  isOpen: boolean;
  onToggle: () => void;
  now: boolean;
  showWhy: boolean;
  onWhy: () => void;
}) {
  const id = itemId(it);
  const nowMark = now && (
    <li className="map-now" data-now>
      {copy["map.now"]}
    </li>
  );
  if (it.kind === "beat") {
    if (!it.known)
      return (
        <>
          <li className="map-node beat future" data-id={id}>
            <span className="map-t">{it.tLabel}</span>
            <span className="map-summary">{copy["map.future"]}</span>
          </li>
          {nowMark}
        </>
      );
    const st = it.status && it.status !== "pending" ? BEAT[it.status] : null;
    return (
      <>
        <li className="map-node beat" data-id={id}>
          <button className="map-row" aria-expanded={isOpen} onClick={onToggle}>
            <span className="map-t">{it.tLabel}</span>
            <span className="map-summary">{it.title ?? ""}</span>
            {st && <span className={`map-state ${it.status}`}>{copy[st]}</span>}
          </button>
          {isOpen && (
            <div className="map-detail">
              <button className="quiet" onClick={onWhy}>
                {copy["map.why"]}
              </button>
              {showWhy && <Why pid={pid} target={id} />}
            </div>
          )}
        </li>
        {nowMark}
      </>
    );
  }
  return (
    <>
      <li className={`map-node ev ${it.style}`} data-id={id}>
        <button className="map-row" aria-expanded={isOpen} onClick={onToggle}>
          <span className="map-t">{it.tLabel}</span>
          <span className="map-summary">
            {it.style === "player" && (
              <span className="map-tag">{copy["map.you"]}</span>
            )}
            {it.style === "character" && it.forPlayer && (
              <span className="map-tag">
                {actor.get(id)
                  ? fill(copy["map.forYou"], { name: name(actor.get(id)!) })
                  : copy["map.forYou"].replace("{name}・", "")}
              </span>
            )}
            {it.summary}
            {fixed.has(id) && (
              <span className="map-fixed">{copy["map.corrected"]}</span>
            )}
          </span>
        </button>
        {isOpen && (
          <div className="map-detail">
            <p>{it.tLabel}</p>
            {it.knownBy.length > 0 && (
              <p>
                <span className="map-label">{copy["map.detail.who"]}</span>
                {it.knownBy.map(name).join("、")}
              </p>
            )}
            <button className="quiet" onClick={onWhy}>
              {copy["map.why"]}
            </button>
            {showWhy && <Why pid={pid} target={id} />}
          </div>
        )}
      </li>
      {nowMark}
    </>
  );
}

function Why({ pid, target }: { pid: string; target: string }) {
  const q = useQuery({
    queryKey: ["why", pid, target],
    queryFn: () => rest.why(pid, target),
  });
  useEffect(() => {
    track("why_opened", {
      target:
        target === "forecast"
          ? "forecast"
          : target.startsWith("beat.")
            ? "beat"
            : target.startsWith("rev")
              ? "reveal"
              : "event",
      fromKeyMoment: false,
    });
  }, [target]);
  if (q.isError) return <p className="error">{copy["net.failed"]}</p>;
  if (!q.data) return null;
  const chain = q.data.chain;
  const half = Math.ceil(chain.length / 2);
  return (
    <ol className="map-why" aria-label={copy["map.why"]}>
      {chain.map((s, i) => (
        <li
          key={"eventId" in s ? s.eventId : s.beatId}
          className={"eventId" in s && s.actor === "player" ? "you" : ""}
        >
          {q.data.collapsed > 0 && i === half && (
            <span className="map-collapsed">
              {fill(copy["map.collapsed"], { n: q.data.collapsed })}
            </span>
          )}
          <span className="map-t">{s.tLabel}</span>
          <span>{s.summary}</span>
        </li>
      ))}
    </ol>
  );
}
