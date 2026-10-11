// The ending page (ux-design 11.2; frontend-design 5): one page scrolling down, world → you → people. GET …/ending
// answers 202 while the ending is being written (「物語を綴じています（n秒）」, asked again after etaSeconds); then the
// world's ending (title, the epilogue with a small source mark on each sentence that opens the map at that event,
// 原作では／あなたの世界では), yours (title, 行方, what they did for you and what you did), the people in the
// server's order (the untouched ones in one line, opened on demand), the card, the map, another role. The words are
// shown as the server wrote them.
import type { Api } from "@zoujin/contracts";
import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { manifestQuery } from "../app/queries";
import { navigate } from "../app/router";
import { rest } from "../net/rest";
import { endingFrame, openOverlay, useStory } from "../stores/story";
import { track } from "../telemetry/telemetry";
import { copy, fill } from "../ui/copy";
import { EndingCard } from "../ui/ending/card/EndingCard";

const ChainMap = lazy(() => import("../ui/map/ChainMap"));
const MemoryBook = lazy(() => import("../ui/memory/MemoryBook"));

const SOURCE_URL = "https://www.aozora.gr.jp/cards/000035/card1567.html"; // 青空文庫『走れメロス』

const isReady = (
  d: Api.EndingView | Api.EndingPending | undefined,
): d is Api.EndingView => !!d && "endingId" in d;

export default function EndingScreen({ pid }: { pid: string }) {
  const manifest = useQuery(manifestQuery);
  const q = useQuery({
    queryKey: ["ending", pid],
    queryFn: () => rest.ending(pid),
    refetchInterval: (query) => {
      const d = query.state.data;
      return d && !isReady(d) ? Math.max(1, d.etaSeconds) * 1000 : false;
    },
  });
  const overlay = useStory((s) => s.overlay);
  const names = useMemo(
    () =>
      Object.fromEntries(
        (manifest.data?.characters ?? []).map((c) => [c.id, c.name]),
      ),
    [manifest.data],
  );
  // the role of this playthrough (kept from the staging); after a reload, the only role if there is one; else none
  const roleId = useStory((s) => s.ending?.roleId ?? null);
  const roles = manifest.data?.roles ?? [];
  const role =
    roles.find((r) => r.roleId === roleId)?.name ??
    (roles.length === 1 ? roles[0]!.name : "");
  const ending = isReady(q.data) ? q.data : null;

  // leaving the page: how long it was read, and the captured frame goes
  const opened = useRef(performance.now());
  useEffect(() => {
    if (!ending) return;
    opened.current = performance.now();
    track("ending_viewed", {
      endingId: ending.endingId,
      outcome: ending.world.outcomeId,
    });
    const id = ending.endingId;
    return () => {
      track("ending_closed", {
        endingId: id,
        dwellMs: Math.round(performance.now() - opened.current),
      });
      endingFrame.set(null);
    };
  }, [ending]);

  return (
    <main className="page end-page">
      <div className="page-body">
        {!ending &&
          (q.isError ? (
            <p className="error">{copy["net.failed"]}</p>
          ) : (
            <Binding />
          ))}
        {/* the names come with the manifest: until then the card would draw ids */}
        {ending && manifest.data && (
          <Ending e={ending} names={names} role={role} />
        )}
      </div>
      <Suspense fallback={null}>
        {overlay?.kind === "map" && (
          <ChainMap
            pid={pid}
            names={names}
            {...(overlay.eventId ? { eventId: overlay.eventId } : {})}
          />
        )}
        {overlay?.kind === "memory" && <MemoryBook pid={pid} names={names} />}
      </Suspense>
    </main>
  );
}

function Binding() {
  const [s, setS] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setS((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <p role="status" className="end-binding-page">
      {fill(copy["ending.binding"], { n: s })}
    </p>
  );
}

function Ending({
  e,
  names,
  role,
}: {
  e: Api.EndingView;
  names: Record<string, string>;
  role: string;
}) {
  const name = (id: string) => names[id] ?? id;
  // the source marks are numbered down the page
  let mark = 0;
  const cite = (cites: string[]) => {
    const n = ++mark;
    return (
      <button
        className="end-cite"
        aria-label={`${copy["ending.map"]} [${n}]`}
        onClick={() =>
          openOverlay({ kind: "map", eventId: cites[0]!, from: "ending" })
        }
      >
        [{n}]
      </button>
    );
  };
  const touched = e.characters.filter((c) => !c.unchanged);
  const untouched = e.characters.filter((c) => c.unchanged);
  const [others, setOthers] = useState(false);
  const [card, setCard] = useState(false);
  return (
    <>
      <section className="end-sec" aria-labelledby="end-world">
        <h2 id="end-world">{copy["ending.world"]}</h2>
        <h1 className="end-title">{e.world.title}</h1>
        {e.world.epilogue.map((s, i) => (
          <p key={i}>
            {s.sentence}
            {cite(s.cites)}
          </p>
        ))}
        {e.world.contrast && (
          <dl className="end-contrast">
            <dt>{copy["ending.canon"]}</dt>
            <dd>{e.world.contrast.original}</dd>
            <dt>{copy["ending.yours"]}</dt>
            <dd>{e.world.contrast.yours}</dd>
          </dl>
        )}
      </section>

      <section className="end-sec" aria-labelledby="end-you">
        <h2 id="end-you">{copy["ending.you"]}</h2>
        <p className="end-you-title">{e.you.title}</p>
        <p>{fill(copy["ending.fate"], { text: e.you.fate })}</p>
        {e.you.didForYou.length > 0 && (
          <>
            <h3>{copy["ending.forYou"]}</h3>
            {e.you.didForYou.map((s, i) => (
              <p key={i}>
                {s.sentence}
                {cite(s.cites)}
              </p>
            ))}
          </>
        )}
        {e.you.youDid.length > 0 && (
          <>
            <h3>{copy["ending.byYou"]}</h3>
            {e.you.youDid.map((s, i) => (
              <p key={i}>
                {s.sentence}
                {cite(s.cites)}
              </p>
            ))}
          </>
        )}
      </section>

      <section className="end-sec" aria-labelledby="end-chars">
        <h2 id="end-chars">{copy["ending.chars"]}</h2>
        {touched.map((c) => (
          <CharacterEnd
            key={c.character}
            c={c}
            name={name(c.character)}
            cite={cite}
          />
        ))}
        {untouched.length > 0 && (
          <div className="end-others">
            <p>
              {copy["ending.others"]}
              <span className="end-names">
                （{untouched.map((c) => name(c.character)).join("、")}）
              </span>
            </p>
            {!others ? (
              <button className="quiet" onClick={() => setOthers(true)}>
                {copy["ending.others.open"]}
              </button>
            ) : (
              untouched.map((c) => (
                <CharacterEnd
                  key={c.character}
                  c={c}
                  name={name(c.character)}
                  cite={cite}
                />
              ))
            )}
          </div>
        )}
      </section>

      <nav className="end-actions">
        <button
          className="primary"
          onClick={() => setCard((v) => !v)}
          aria-expanded={card}
        >
          {copy["ending.card"]}
        </button>
        <button
          className="secondary"
          onClick={() => openOverlay({ kind: "map", from: "ending" })}
        >
          {copy["ending.map"]}
        </button>
        <button
          className="secondary"
          onClick={() => openOverlay({ kind: "memory" })}
        >
          {copy["menu.memory"]}
        </button>
        <button className="secondary" onClick={() => navigate("/roles")}>
          {copy["ending.again"]}
        </button>
        <a
          className="quiet"
          href={SOURCE_URL}
          target="_blank"
          rel="noopener noreferrer"
        >
          {copy["ending.source"]}
        </a>
      </nav>
      {card && (
        <EndingCard
          card={e.card}
          endingId={e.endingId}
          names={names}
          role={role}
        />
      )}
    </>
  );
}

function CharacterEnd({
  c,
  name,
  cite,
}: {
  c: Api.EndingView["characters"][number];
  name: string;
  cite: (cites: string[]) => React.ReactNode;
}) {
  return (
    <div className="end-char">
      <h3>{name}</h3>
      {c.unchanged ? (
        <p>{copy["map.beat.canon"]}</p>
      ) : (
        <dl className="end-contrast">
          {c.original && (
            <>
              <dt>{copy["ending.canon"]}</dt>
              <dd>{c.original}</dd>
            </>
          )}
          <dt>{copy["ending.yours"]}</dt>
          <dd>
            {(c.yours ?? []).map((s, i) => (
              <span key={i}>
                {s.sentence}
                {cite(s.cites)}
              </span>
            ))}
          </dd>
        </dl>
      )}
    </div>
  );
}
