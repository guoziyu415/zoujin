// The world screen (frontend-design 5): the 3D layer underneath (F-0: a placeholder; F-2d mounts the plaza on these
// stores) and the HUD on top. Opening it starts from the snapshot and the socket; leaving closes both.
import type { Api } from "@zoujin/contracts";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { manifestQuery, meQuery, takeSnapshot } from "../app/queries";
import { navigate, toLogin } from "../app/router";
import { closePlay, openPlay, play } from "../net/play";
import { ApiError, rest } from "../net/rest";
import { usePlayer } from "../stores/player";
import { useUi } from "../stores/ui";
import { setWorld, useWorld } from "../stores/world";
import { track } from "../telemetry/telemetry";
import { copy } from "../ui/copy";
import { ConnectionBanner } from "../ui/hud/ConnectionBanner";
import { NearbyList } from "../ui/hud/NearbyList";
import { ResumeGate } from "../ui/hud/ResumeGate";
import { Subtitles } from "../ui/hud/Subtitles";
import { SunBand } from "../ui/hud/SunBand";
import { TextInput } from "../ui/hud/TextInput";
import { WorldReactionToast } from "../ui/hud/WorldReactionToast";

export default function PlayScreen({ pid }: { pid: string }) {
  const qc = useQueryClient();
  const manifest = useQuery(manifestQuery);
  const [failed, setFailed] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0); // 「もう一度つなぐ」 reads the snapshot again
  const names = useMemo(
    () =>
      Object.fromEntries(
        (manifest.data?.characters ?? []).map((c) => [c.id, c.name]),
      ),
    [manifest.data],
  );

  useEffect(() => {
    let alive = true;
    const handed = takeSnapshot(pid);
    (handed ? Promise.resolve(handed) : rest.snapshot(pid))
      .then((snap: Api.Snapshot) => {
        if (!alive) return;
        if (snap.status === "ended")
          return navigate(`/ending/${encodeURIComponent(pid)}`, {
            replace: true,
          });
        openPlay(pid, snap, {
          onEnded: (why) => {
            if (why === "unauthenticated") toLogin();
            if (why === "gone") {
              void qc.invalidateQueries({ queryKey: meQuery.queryKey });
              navigate("/", { replace: true });
            }
          },
        });
      })
      .catch((err: unknown) => {
        if (!alive || (err instanceof ApiError && err.status === 401)) return; // the 401 handler goes to login
        if (
          err instanceof ApiError &&
          (err.status === 403 || err.status === 404)
        )
          navigate("/", { replace: true });
        else
          setFailed(
            err instanceof ApiError && err.body
              ? err.body.error.message
              : copy["net.lost"],
          );
      });
    return () => {
      alive = false;
      closePlay();
      setWorld(null);
      useUi.setState({
        connection: "idle",
        downSince: null,
        toasts: [],
        moreToasts: 0,
        overlay: null,
        resumeGate: false,
      });
    };
  }, [pid, qc, attempt]);

  useEffect(() => play.setNames(names), [names]);
  useResume();
  // what the page has applied, for the e2e checks of resent commits (no duplicates, nothing lost)
  const lastSeq = useWorld((s) => s.world?.lastSeq);
  const events = useWorld((s) => s.world?.events.length);

  return (
    <div className="world" data-last-seq={lastSeq} data-events={events}>
      <div className="world-3d" aria-hidden="true" />
      <div className="hud-top">
        <SunBand />
        <ConnectionBanner />
        <WorldReactionToast />
        {failed && (
          <div className="banner" role="alert">
            <span>{failed}</span>
            <button
              onClick={() => {
                setFailed(null);
                setAttempt((n) => n + 1);
              }}
            >
              {copy["net.retry"]}
            </button>
          </div>
        )}
      </div>
      <div className="hud-bottom">
        <Subtitles names={names} />
        <Controls names={names} />
      </div>
      <NearbyList names={names} />
      <ResumeGate />
    </div>
  );
}

function Controls({ names }: { names: Record<string, string> }) {
  const focus = usePlayer((s) => s.focusCharacter);
  return (
    <div className="controls">
      <button onClick={() => useUi.setState({ overlay: "nearby" })}>
        {copy["nearby.button"]}
      </button>
      <TextInput />
      {focus && (
        <button
          onClick={play.unfocus}
          aria-label={`${copy["talk.end"]}（${names[focus] ?? focus}）`}
        >
          {copy["talk.end"]}
        </button>
      )}
    </div>
  );
}

// leaving and coming back (frontend-design 9.5): pagehide closes the socket (back/forward cache); visible again
// reconnects if it dropped and shows the one-tap gate; app_resumed says how long the player was away
function useResume(): void {
  useEffect(() => {
    let hiddenAt: number | null = null;
    const back = (persisted: boolean) => {
      if (hiddenAt === null && !persisted) return;
      const awayMs =
        hiddenAt === null ? 0 : Math.round(performance.now() - hiddenAt);
      hiddenAt = null;
      const since = performance.now();
      useUi.setState({ resumeGate: true });
      play.reconnect();
      const report = () =>
        track("app_resumed", {
          awayMs,
          discarded: false,
          resumeMs: Math.round(performance.now() - since),
          contextLost: false,
        });
      if (useUi.getState().connection === "open") return report();
      const off = useUi.subscribe((s) => {
        if (s.connection !== "open") return;
        off();
        report();
      });
    };
    const visibility = () => {
      if (document.visibilityState === "hidden") hiddenAt ??= performance.now();
      else back(false);
    };
    const pagehide = () => {
      hiddenAt ??= performance.now();
      play.suspend();
    };
    const pageshow = (e: PageTransitionEvent) => e.persisted && back(true);
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("pagehide", pagehide);
    window.addEventListener("pageshow", pageshow);
    return () => {
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("pagehide", pagehide);
      window.removeEventListener("pageshow", pageshow);
    };
  }, []);
}
