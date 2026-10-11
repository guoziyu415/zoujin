// 連鎖反応マップ (ux-design 9; copy-ja 8): a vertical timeline by day, a list (it reads aloud as one). Your deeds a
// scarlet dot and 「あなた」; what they caused an ink dot with a thin scarlet line back; what someone did for you with
// their name and 「あなたのために」; the original's beats in grey boxes with how they stand now; beats not yet come (or
// not known) only their time and 「？」. The deadline line on top (the crisis line opens the why of the forecast).
// Chips filter by person and by 「わたしの行動だけ」. A node opens in place: summary, time, where, who knows, the
// original's words (a beat's, as the server filtered them for what you know), and 「なぜこうなった？」, the chain from
// your deed to it in time order.
import type { Api } from "@zoujin/contracts";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { manifestQuery } from "../../app/queries";
import { rest } from "../../net/rest";
import { openOverlay, useStory } from "../../stores/story";
import { useWorld } from "../../stores/world";
import { track } from "../../telemetry/telemetry";
import { KnotIcon } from "../KnotIcon";
import { memoriesKey, voidedIn } from "../memory/view";
import { copy, fill } from "../copy";
import { FullPage } from "../FullPage";
import {
  corrected,
  keptPromises,
  voidedPromises,
  itemId,
  nowDayOf,
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
  const qc = useQueryClient();
  const book = qc.getQueryData<Api.MemoriesResponse>(memoriesKey(pid));
  const kept = useMemo(() => {
    const voided = voidedPromises(events ?? []);
    for (const id of voidedIn(book)) voided.add(id);
    return keptPromises(events ?? [], voided);
  }, [events, book]);
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
  // the book's places (manifest, api-contract 2.1): a name for where an event was, not what you know
  const manifest = useQuery(manifestQuery);
  const places = useMemo(
    () =>
      new Map((manifest.data?.places ?? []).map((p) => [p.placeId, p.name])),
    [manifest.data],
  );
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
          // 「いまここ」: in the last day with anything at or before now (later days may hold 「？」 beats)
          const nowAt =
            d.day === nowDayOf(q.data.days, now) ? nowIndex(d.items, now) : -2;
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
                    kept={kept}
                    fixed={fixed}
                    isOpen={open === itemId(it)}
                    onToggle={() =>
                      setOpen((o) => (o === itemId(it) ? null : itemId(it)))
                    }
                    now={d.items.indexOf(it) === nowAt && !filter.mine}
                    place={places}
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
  kept,
  fixed,
  isOpen,
  onToggle,
  now,
  place,
  showWhy,
  onWhy,
}: {
  pid: string;
  it: Api.TimelineItem;
  name: (id: string) => string;
  place: Map<string, string>;
  actor: Map<string, string>;
  kept: Set<string>;
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
              <Source cite={it.cite} />
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
            {it.style === "character" && it.forPlayer && (
              <span className="map-tag">
                {actor.get(id)
                  ? fill(copy["map.forYou"], { name: name(actor.get(id)!) })
                  : copy["map.forYou"].replace("{name}・", "")}
              </span>
            )}
            {kept.has(id) && <KnotIcon label={copy["map.kept"]} />}
            {it.summary}
            {fixed.has(id) && (
              <span className="map-fixed">{copy["map.corrected"]}</span>
            )}
          </span>
        </button>
        {isOpen && (
          <div className="map-detail">
            <p>{it.tLabel}</p>
            {place.get(it.place) && (
              <p>
                <span className="map-label">{copy["map.detail.where"]}</span>
                {place.get(it.place)}
              </p>
            )}
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
          {/* the beat opened is the chain's last step: its words are already above */}
          {"beatId" in s &&
            s.beatId !== target &&
            s.cite?.map((c) => (
              <span key={`${c.para}:${c.quote}`} className="map-cite">
                「{c.quote}」
              </span>
            ))}
        </li>
      ))}
    </ol>
  );
}

// the original's words for a beat (api-contract 2.5: only for a beat you know, filtered for what you know; none, none)
function Source({ cite }: { cite?: Api.TimelineBeatItem["cite"] }) {
  if (!cite?.length) return null;
  return (
    <div className="map-source">
      <span className="map-label">{copy["map.detail.source"]}</span>
      {cite.map((c) => (
        <p key={`${c.para}:${c.quote}`} className="map-cite">
          「{c.quote}」
        </p>
      ))}
    </div>
  );
}
