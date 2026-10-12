// The world screen (frontend-design 5): the 3D layer underneath (the scene on these stores, its own chunk) and the
// HUD on top: the talk key in the middle of the controls (or the text field when the voice can't be
// used), the microphone's half pages, the safety note and card (F-1). Opening it starts from the snapshot and the
// socket; leaving closes both.
import type { Api } from "@zoujin/contracts";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { flags } from "../app/flags";
import {
  libraryQuery,
  manifestFor,
  meQuery,
  takeSnapshot,
} from "../app/queries";
import { audio } from "../audio";
import { navigate, toLogin } from "../app/router";
import { closePlay, openPlay, play } from "../net/play";
import { libraryEntry } from "../net/library";
import { ApiError, rest } from "../net/rest";
import { usePlayer } from "../stores/player";
import { useUi } from "../stores/ui";
import { useVoice } from "../stores/voice";
import { setWorld, useWorld } from "../stores/world";
import { track } from "../telemetry/telemetry";
import { copy } from "../ui/copy";
import { ConnectionBanner } from "../ui/hud/ConnectionBanner";
import { MicSheet } from "../ui/hud/MicSheet";
import { NearbyList } from "../ui/hud/NearbyList";
import { ResumeGate } from "../ui/hud/ResumeGate";
import { Subtitles } from "../ui/hud/Subtitles";
import { SunBand } from "../ui/hud/SunBand";
import { TalkKey } from "../ui/hud/TalkKey";
import { TextInput } from "../ui/hud/TextInput";
import { WorldReactionToast } from "../ui/hud/WorldReactionToast";
import { SafetyCard } from "../ui/safety/SafetyCard";
import { HelplinePanel, SafetyHint } from "../ui/safety/SafetyHint";
import { selectCovered, useStory } from "../stores/story";
import { StoryLayer } from "../ui/StoryLayer";
import { StoryMenu } from "../ui/StoryMenu";
import { useVoiceState } from "../voice/useVoiceState";
import { keepScenes } from "../sw/register";

const WorldScreen = lazy(() => import("./WorldScreen"));

export default function PlayScreen({ pid }: { pid: string }) {
  const qc = useQueryClient();
  const library = useQuery(libraryQuery);
  const entry = libraryEntry(library.data, pid);
  const manifest = useQuery({
    ...manifestFor(entry?.bookId ?? "", entry?.worldModelVersion),
    enabled: !!entry,
  });
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
    if (library.isSuccess && !library.isFetching && !entry)
      navigate("/", { replace: true });
  }, [library.isSuccess, library.isFetching, entry]);

  useEffect(() => {
    if (!manifest.data) return;
    // HUD-only browser tests omit WorldScreen, so there is no renderer to report
    // a walkable scene. Their act transitions must still reach the arrival line.
    if (flags.no3d) useUi.setState({ scene: "ready" });
    play.setManifest(manifest.data);
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
              void qc.invalidateQueries({ queryKey: libraryQuery.queryKey });
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
  }, [pid, qc, attempt, manifest.data]);

  useEffect(() => {
    if (!manifest.data) return;
    play.setManifest(manifest.data);
    keepScenes(manifest.data.scenes.map((s) => s.assetUrl));
  }, [manifest.data]);
  useResume();
  // what the page has applied, for the e2e checks of resent commits (no duplicates, nothing lost)
  const lastSeq = useWorld((s) => s.world?.lastSeq);
  const events = useWorld((s) => s.world?.events.length);
  const voice = useVoiceState();
  const paused = useVoice((s) => s.paused); // the card is modal: nothing behind it takes a tap or the focus
  // a story page or the ending's staging over the world: the HUD behind it takes no tap or focus either
  const covered = useStory((s) => selectCovered(s) || !!s.ending);
  // the ending's staging: only the 3D and its subtitles on screen (ux-design 11.1, v1.0.6)
  const staging = useStory((s) => !!s.ending);

  return (
    <div
      className="world"
      data-last-seq={lastSeq}
      data-events={events}
      data-voice={voice}
    >
      <div className="world-3d" aria-hidden="true">
        {!flags.no3d && manifest.isSuccess && (
          <Suspense fallback={null}>
            <WorldScreen embedded packs={manifest.data?.scenes} />
          </Suspense>
        )}
      </div>
      <div className="hud-top" inert={paused || covered} hidden={staging}>
        <SunBand />
        <StoryMenu />
        <ConnectionBanner />
        <WorldReactionToast />
        {library.isError && (
          <div className="banner" role="alert">
            <span>本の情報を取得できませんでした。</span>
            <button onClick={() => void library.refetch()}>もう一度</button>
          </div>
        )}
        {manifest.isError && (
          <div className="banner" role="alert">
            <span>本の情報を取得できませんでした。</span>
            <button onClick={() => void manifest.refetch()}>もう一度</button>
          </div>
        )}
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
      <div className="hud-bottom" inert={paused || covered} hidden={staging}>
        <SafetyHint where="portrait" />
        <Subtitles names={names} />
        <Controls names={names} />
      </div>
      {!staging && <NearbyList names={names} />}
      <StoryLayer pid={pid} names={names} />
      <MicSheet />
      <HelplinePanel />
      <SafetyCard />
      <ResumeGate />
    </div>
  );
}

// 近くの人, the talk key, the text key, 話を終える (ux-design 7.1). When the voice can't be used (the player chose text,
// the microphone is refused or doesn't work, the server said degraded) the text field takes the key's place; while
// the text field is open the talk key steps aside (「声に戻す」 brings it back).
function Controls({ names }: { names: Record<string, string> }) {
  const focus = usePlayer((s) => s.focusCharacter);
  const mic = useVoice((s) => s.mic);
  const degraded = useVoice((s) => s.degraded);
  const textOpen = useVoice((s) => s.textOpen);
  const textFirst =
    degraded || mic === "text" || mic === "denied" || mic === "unavailable";
  return (
    <div className="controls">
      <button onClick={() => useUi.setState({ overlay: "nearby" })}>
        {copy["nearby.button"]}
      </button>
      {textFirst ? (
        <>
          <SafetyHint where="landscape" />
          <TextInput primary />
        </>
      ) : (
        <>
          {!(textOpen && focus) && <TalkKey />}
          <SafetyHint where="landscape" />
          <TextInput primary={false} />
        </>
      )}
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
// reconnects if it dropped and, when the sound needs it, shows the one-tap gate; app_resumed says how long the
// player was away
function useResume(): void {
  useEffect(() => {
    let hiddenAt: number | null = null;
    const back = (persisted: boolean) => {
      if (hiddenAt === null && !persisted) return;
      const awayMs =
        hiddenAt === null ? 0 : Math.round(performance.now() - hiddenAt);
      hiddenAt = null;
      const since = performance.now();
      // the one-tap gate only when the sound can't come back without a tap (iOS after the background)
      void audio.resumeQuietly().then((ok) => {
        if (!ok && document.visibilityState === "visible")
          useUi.setState({ resumeGate: true });
      });
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
