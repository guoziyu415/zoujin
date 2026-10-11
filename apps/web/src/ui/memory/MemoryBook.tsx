// 記憶帳 (ux-design 10; copy-ja 9): the people who remember the player, one tab each. The relation as a label and five
// boxes (no number), then 約束 (never the voided ones), あなたにしてくれたこと / あなたがしたこと (each opens the map at
// its event), 覚えていること (the character's own words, when, and how they know). 「忘れてもらう」 opens a confirmation
// in place (no dialog), says what stays as it was and, for a promise, that it goes too; a delete is real and has no
// undo. At the bottom: what is kept and for how long, and deleting the whole story.
import type { Api } from "@zoujin/contracts";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { navigate } from "../../app/router";
import { uuid } from "../../net/ids";
import { closePlay } from "../../net/play";
import { rest } from "../../net/rest";
import { openOverlay } from "../../stores/story";
import { track } from "../../telemetry/telemetry";
import { copy, fill } from "../copy";
import { FullPage } from "../FullPage";
import { Lines } from "../Lines";
import {
  afterDelete,
  isEmpty,
  meter,
  shownPromises,
  memoriesKey,
} from "./view";

const VIA = {
  witnessed: "memory.via.saw",
  told: "memory.via.heard",
  rumor: "memory.via.rumor",
} as const;

const STATE = {
  open: "memory.promise.state.open",
  kept: "memory.promise.state.kept",
  broken: "memory.promise.state.broken",
} as const;

export default function MemoryBook({
  pid,
  names,
  start,
}: {
  pid: string;
  names: Record<string, string>;
  start?: string | undefined;
}) {
  const q = useQuery({
    queryKey: memoriesKey(pid),
    queryFn: () => rest.memories(pid),
  });
  const [tab, setTab] = useState<string | undefined>(start);
  const [done, setDone] = useState<string | null>(null); // 「{name}は、そのことを忘れた。」
  useEffect(() => track("memory_book_opened", {}), []);
  const name = (id: string) => names[id] ?? id;
  const people = q.data?.characters ?? [];
  const cur = people.find((c) => c.character === tab) ?? people[0];

  return (
    <FullPage
      title={copy["memory.title"]}
      className="mb"
      onClose={() => openOverlay(null)}
    >
      <p className="mb-lead">{copy["memory.lead"]}</p>
      <p className="mb-done" role="status">
        {done}
      </p>
      {q.isError && <p className="error">{copy["net.failed"]}</p>}
      {q.data && !people.length && <p>{copy["memory.empty"]}</p>}
      {people.length > 0 && (
        <div className="mb-tabs" role="tablist">
          {people.map((c) => (
            <button
              key={c.character}
              role="tab"
              id={`mb-tab-${c.character}`}
              aria-selected={c === cur}
              aria-controls="mb-panel"
              onClick={() => setTab(c.character)}
            >
              {name(c.character)}
            </button>
          ))}
        </div>
      )}
      {cur && (
        <div
          id="mb-panel"
          role="tabpanel"
          aria-labelledby={`mb-tab-${cur.character}`}
          className="mb-panel"
        >
          <Person
            pid={pid}
            c={cur}
            name={name(cur.character)}
            onForgot={(n) =>
              setDone(fill(copy["memory.forget.done"], { name: n }))
            }
          />
        </div>
      )}
      <Footer pid={pid} />
    </FullPage>
  );
}

function Person({
  pid,
  c,
  name,
  onForgot,
}: {
  pid: string;
  c: Api.MemoryBookCharacter;
  name: string;
  onForgot: (name: string) => void;
}) {
  const promises = shownPromises(c);
  const toMap = (eventId: string) => openOverlay({ kind: "map", eventId });
  return (
    <>
      <h2 className="mb-name">{name}</h2>
      <p
        className="mb-relation"
        aria-label={`${c.relationLabel}（${c.relationLevel}/5）`}
      >
        <span className="mb-meter" aria-hidden>
          {meter(c.relationLevel)}
        </span>
        <span>{c.relationLabel}</span>
      </p>
      {isEmpty(c) && <p>{fill(copy["memory.char.empty"], { name })}</p>}
      {promises.length > 0 && (
        <section className="mb-sec">
          <h3>{copy["memory.sec.promise"]}</h3>
          <ul>
            {promises.map((p) => (
              <li key={p.promiseId}>
                {/* the whole row opens the map at the event that made it, like the deeds; its words are its name */}
                <button className="mb-promise" onClick={() => toMap(p.eventId)}>
                  <span>{p.text}</span>
                  <span className="mb-dir">
                    {fill(
                      copy[
                        p.direction === "playerToCharacter"
                          ? "memory.promise.dir.mine"
                          : "memory.promise.dir.theirs"
                      ],
                      { name },
                    )}
                  </span>
                  <span className="mb-state">
                    {copy[STATE[p.status as keyof typeof STATE]]}
                  </span>
                  <span className="mb-go" aria-hidden>
                    ›
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      <Deeds
        title={copy["memory.sec.forYou"]}
        items={c.didForYou}
        onOpen={toMap}
      />
      <Deeds title={copy["memory.sec.byYou"]} items={c.youDid} onOpen={toMap} />
      {c.memories.length > 0 && (
        <section className="mb-sec">
          <h3>{copy["memory.sec.remembers"]}</h3>
          <ul>
            {c.memories.map((m) => (
              <MemoryCard
                key={m.memoryId}
                pid={pid}
                m={m}
                name={name}
                character={c.character}
                onForgot={() => onForgot(name)}
              />
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

function Deeds({
  title,
  items,
  onOpen,
}: {
  title: string;
  items: { eventId: string; text: string }[];
  onOpen: (eventId: string) => void;
}) {
  if (!items.length) return null; // an empty section isn't shown, not even 「まだありません」 (10.1)
  return (
    <section className="mb-sec">
      <h3>{title}</h3>
      <ul>
        {items.map((d) => (
          <li key={d.eventId + d.text}>
            <button className="mb-deed" onClick={() => onOpen(d.eventId)}>
              <span>{d.text}</span>
              <span aria-hidden>›</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function MemoryCard({
  pid,
  m,
  name,
  character,
  onForgot,
}: {
  pid: string;
  m: Api.MemoryView;
  name: string;
  character: string;
  onForgot: () => void;
}) {
  const qc = useQueryClient();
  const [asking, setAsking] = useState(false);
  const [key] = useState(uuid); // the same Idempotency-Key across retries of this one delete
  const impact = useQuery({
    queryKey: ["memory-impact", pid, m.memoryId],
    queryFn: () => rest.memoryImpact(pid, m.memoryId),
    enabled: asking,
  });
  const del = useMutation({
    mutationFn: () => rest.deleteMemory(pid, m.memoryId, key),
    onSuccess: (r) => {
      track("memory_deleted", { character });
      qc.setQueryData<Api.MemoriesResponse>(memoriesKey(pid), (d) =>
        d ? afterDelete(d, r) : d,
      );
      void qc.invalidateQueries({ queryKey: ["timeline", pid] });
      onForgot();
    },
  });
  return (
    <li className={`mb-card${del.isPending ? " leaving" : ""}`}>
      <p className="mb-text">「{m.text}」</p>
      <p className="mb-meta">
        <span>{m.tLabel}</span>
        <span>{copy[VIA[m.via]]}</span>
        {!asking && (
          <button className="quiet" onClick={() => setAsking(true)}>
            {copy["memory.forget"]}
          </button>
        )}
      </p>
      {asking && (
        <div
          className="mb-confirm"
          role="group"
          aria-label={copy["memory.forget"]}
        >
          <p>
            <strong>{fill(copy["memory.forget.q"], { name })}</strong>
          </p>
          <p>{fill(copy["memory.forget.body"], { name })}</p>
          {impact.data?.keeps && (
            <p>
              {fill(copy["memory.forget.keeps"], { text: impact.data.keeps })}
            </p>
          )}
          {(impact.data?.voidsPromise || m.kind === "promise") && (
            <p>{copy["memory.forget.promise"]}</p>
          )}
          {del.isError && <p className="error">{copy["net.failed"]}</p>}
          <div className="ae-two">
            <button
              className="ae-choice"
              disabled={del.isPending || impact.isPending}
              onClick={() => del.mutate()}
            >
              {copy["memory.forget"]}
            </button>
            <button className="ae-choice" onClick={() => setAsking(false)}>
              {copy["common.cancel"]}
            </button>
          </div>
        </div>
      )}
    </li>
  );
}

function Footer({ pid }: { pid: string }) {
  const [asking, setAsking] = useState(false);
  const [key] = useState(uuid);
  const del = useMutation({
    mutationFn: () => rest.deletePlaythrough(pid, key),
    onSuccess: () => {
      closePlay();
      openOverlay(null);
      navigate("/", { replace: true });
    },
  });
  return (
    <footer className="mb-footer">
      <p className="small">
        <Lines text={copy["memory.footer"]} />
      </p>
      {!asking ? (
        <button className="quiet" onClick={() => setAsking(true)}>
          {copy["memory.deleteAll"]}
        </button>
      ) : (
        <div className="mb-confirm" role="group">
          <p>{copy["memory.deleteAll.q"]}</p>
          {del.isError && <p className="error">{copy["net.failed"]}</p>}
          <div className="ae-two">
            <button
              className="ae-choice danger"
              disabled={del.isPending}
              onClick={() => del.mutate()}
            >
              {copy["memory.deleteAll.yes"]}
            </button>
            <button className="ae-choice" onClick={() => setAsking(false)}>
              {copy["common.cancel"]}
            </button>
          </div>
        </div>
      )}
    </footer>
  );
}
