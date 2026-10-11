// One open playthrough (frontend-design 4, 9): owns the Live socket, writes what the server says into the stores, and
// gives the screens a few verbs (focus, say, examine). Components call these and read the stores; none of them sees
// the socket. Messages this client doesn't know yet are ignored and counted (api-contract 0: the protocol only adds).
import type { Api } from "@zoujin/contracts";
import { addEvents, applyCommit, fromSnapshot, type WorldData } from "./apply";
import { turnId as newTurnId, uuid } from "./ids";
import { Live, type Ended } from "./live";
import { rest } from "./rest";
import { setWorld, useWorld } from "../stores/world";
import { addNarration, initialVoice, useVoice } from "../stores/voice";
import { usePlayer } from "../stores/player";
import { showToasts, useUi, type Toast } from "../stores/ui";
import { setTelemetryContext, track } from "../telemetry/telemetry";
import { copy, fill } from "../ui/copy";

// every server message type of this contract version; a type missing here fails the typecheck when contracts grow
const KNOWN: Record<Api.ServerMessage["type"], true> = {
  welcome: true,
  session_preparing: true,
  session_ready: true,
  turn_started: true,
  transcript: true,
  interrupted: true,
  turn_complete: true,
  suggestions: true,
  turn_settled: true,
  commit: true,
  narration: true,
  set_piece: true,
  confirm: true,
  confirm_closed: true,
  approach: true,
  action_result: true,
  act_ended: true,
  act_plan_result: true,
  act_transition: true,
  safety_pause: true,
  safety_hint: true,
  safety_resumed: true,
  ending_started: true,
  ending_ready: true,
  turn_retract_result: true,
  limits: true,
  degraded: true,
  goaway: true,
  error: true,
  pong: true,
  event_rejected: true,
};

export const CLIENT_VERSION = "web-0.1.0";

type Outgoing = { turnId: string; text: string; via: Api.TextMessage["via"] };

export type SessionHooks = {
  onEnded: (why: Ended) => void; // 4001 → the invite page; taken / gone → the screen says so
};

export class Session {
  private live: Live;
  private welcomed = false;
  private outbox: Outgoing[] = []; // typed while the socket was down
  private inflight: Outgoing | null = null; // sent, nothing back for it yet
  private refilling: Promise<void> | null = null;
  private held: Api.CommitMessage[] = []; // commits that came while refilling
  private names: Record<string, string> = {};
  readonly unknown = new Map<string, number>();

  constructor(
    readonly playthroughId: string,
    private readonly hooks: SessionHooks,
    url = wsUrl(playthroughId),
    Ctor?: ConstructorParameters<typeof Live>[3],
  ) {
    this.live = new Live(
      url,
      CLIENT_VERSION,
      {
        lastSeq: () => useWorld.getState().world?.lastSeq ?? 0,
        onMessage: (m) => this.dispatch(m),
        onOpen: () => {},
        onDown: (reason) => this.down(reason),
        onEnded: (why) => this.ended(why),
      },
      Ctor,
    );
  }

  // the snapshot from POST /playthroughs or GET /snapshot; then the socket
  start(snapshot: Api.Snapshot): void {
    setWorld(fromSnapshot(snapshot));
    useVoice.setState(initialVoice());
    usePlayer.setState({ nearCharacter: null, focusCharacter: null });
    useUi.setState({ connection: "connecting", downSince: null });
    setTelemetryContext({
      playthroughId: snapshot.playthroughId,
      t: snapshot.clock.t,
    });
    this.live.connect();
  }

  stop(): void {
    this.live.close();
    this.welcomed = false;
    setTelemetryContext({});
  }

  // pagehide (9.5): close without the banner; coming back calls reconnect()
  suspend(): void {
    this.live.close();
    this.welcomed = false;
    useUi.setState({
      connection: "reconnecting",
      downSince: useUi.getState().downSince ?? performance.now(),
    });
  }

  // display names for the light reactions (from the manifest); the ID until they arrive
  setNames(names: Record<string, string>): void {
    this.names = names;
  }

  // 「もう一度つなぐ」, 「この画面で続ける」, back from the background
  reconnect(): void {
    const ui = useUi.getState();
    if (ui.connection === "open") return;
    useUi.setState({
      connection: "reconnecting",
      downSince: ui.downSince ?? performance.now(),
    });
    this.live.retryNow();
  }

  focus(character: string): void {
    usePlayer.setState({ focusCharacter: character });
    useVoice.setState({
      session: { character, status: "none" },
      suggestions: null,
    });
    this.live.send({ type: "focus", character });
  }

  unfocus(reason: Api.UnfocusMessage["reason"] = "menu"): void {
    usePlayer.setState({ focusCharacter: null });
    useVoice.setState({ session: { character: null, status: "none" } });
    this.live.send({ type: "unfocus", reason });
  }

  // typed text (or a suggestion chip): the player's line shows at once, the character's as 「……」 until it comes
  say(text: string, via: Api.TextMessage["via"] = "typed"): void {
    const o: Outgoing = { turnId: newTurnId(), text, via };
    useVoice.setState({
      player: {
        turnId: o.turnId,
        speaker: "player",
        text,
        final: true,
        fromChip: via === "chip",
      },
      character: null,
      suggestions: null,
      turn: { turnId: o.turnId, turnSeq: 0, phase: "waiting" },
    });
    if (this.welcomed && this.live.open) this.sendText(o);
    else this.outbox.push(o);
  }

  examine(target: string): void {
    this.live.send({
      type: "action",
      clientMsgId: uuid(),
      kind: "examine",
      target,
    });
  }

  private sendText(o: Outgoing): void {
    const turnSeq = useVoice.getState().nextTurnSeq;
    useVoice.setState((s) => ({
      nextTurnSeq: turnSeq + 1,
      turn: s.turn?.turnId === o.turnId ? { ...s.turn, turnSeq } : s.turn,
    }));
    this.inflight = o;
    this.live.send({
      type: "text",
      turnId: o.turnId,
      turnSeq,
      text: o.text,
      via: o.via,
    });
  }

  // —— the socket's side ——

  private down(reason: string): void {
    const ui = useUi.getState();
    this.welcomed = false;
    if (ui.connection === "open") {
      useUi.setState({
        connection: "reconnecting",
        downSince: performance.now(),
      });
      track("connection_lost", { reason });
    } else if (ui.connection === "connecting" || ui.connection === "taken") {
      useUi.setState({
        connection: "reconnecting",
        downSince: ui.downSince ?? performance.now(),
      });
    }
  }

  private ended(why: Ended): void {
    this.welcomed = false;
    useUi.setState({
      connection: why === "taken" ? "taken" : why === "gone" ? "gone" : "idle",
    });
    this.hooks.onEnded(why);
  }

  private dispatch(m: { type: string } & Record<string, unknown>): void {
    if (!(m.type in KNOWN)) {
      this.unknown.set(m.type, (this.unknown.get(m.type) ?? 0) + 1);
      if (this.unknown.get(m.type) === 1)
        console.debug(`[net] ignored unknown message type ${m.type}`);
      return;
    }
    const msg = m as unknown as Api.ServerMessage;
    switch (msg.type) {
      case "welcome":
        return this.welcome(msg);
      case "session_preparing":
        if (msg.character === usePlayer.getState().focusCharacter)
          useVoice.setState({
            session: {
              character: msg.character,
              status: "preparing",
              etaMs: msg.etaMs,
            },
          });
        return;
      case "session_ready":
        if (msg.character === usePlayer.getState().focusCharacter)
          useVoice.setState({
            session: {
              character: msg.character,
              status: "ready",
              voiceAvailable: msg.voiceAvailable,
            },
          });
        return;
      case "turn_started":
        useVoice.setState({
          turn: { turnId: msg.turnId, turnSeq: msg.turnSeq, phase: "waiting" },
          player: null,
          character: null,
          suggestions: null,
        });
        return;
      case "transcript":
        return this.transcript(msg);
      case "interrupted":
      case "turn_complete":
        this.answered(msg.turnId);
        useVoice.setState((s) =>
          s.turn?.turnId === msg.turnId && s.turn.phase !== "settled"
            ? {
                turn: {
                  ...s.turn,
                  phase: "done",
                  ...(msg.type === "turn_complete" ? { audio: msg.audio } : {}),
                },
              }
            : s,
        );
        return;
      case "suggestions":
        useVoice.setState({
          suggestions: { character: msg.character, items: msg.items },
        });
        return;
      case "turn_settled":
        this.answered(msg.turnId);
        useVoice.setState((s) => {
          if (s.turn?.turnId !== msg.turnId) return s;
          const cleared =
            msg.outcome === "retracted" || msg.outcome === "paused"; // the words are gone (3.6, 3.12)
          return {
            turn: { ...s.turn, phase: "settled" },
            ...(cleared ? { player: null, character: null } : {}),
          };
        });
        return;
      case "commit":
        return void this.commit(msg);
      case "narration":
        return addNarration(msg.line);
      case "action_result":
        if (msg.narration) addNarration(msg.narration);
        return;
      case "limits":
        useVoice.setState({ voiceMinutesLeft: msg.voiceMinutesLeft });
        return;
      case "degraded":
        if (!useVoice.getState().degraded) addNarration(copy["voice.degraded"]);
        useVoice.setState({ degraded: true });
        return;
      case "error":
        // invalid_request: what we sent didn't fit the schema; the turn didn't happen (api-contract 5)
        if (msg.error.code === "invalid_request") this.undelivered();
        return;
      default:
        return; // known, handled by later cards (voice F-1, set pieces, confirm, act end, ending: M2)
    }
  }

  private welcome(w: Api.WelcomeMessage): void {
    const ui = useUi.getState();
    if (ui.downSince !== null && ui.connection === "reconnecting")
      track("connection_restored", {
        downMs: Math.round(performance.now() - ui.downSince),
      });
    useUi.setState({ connection: "open", downSince: null });
    this.welcomed = true;
    const world = useWorld.getState().world;
    if (world) setWorld({ ...world, voice: w.voice, pending: w.pending });
    useVoice.setState({
      nextTurnSeq: 1,
      degraded: w.voice.degraded,
      voiceMinutesLeft: w.voice.minutesLeftToday,
    });
    this.restore(w.lastTurn);
    // the server has its own lastSeq; it resends the commits after ours right behind this welcome (api-contract 4)
    const focus = usePlayer.getState().focusCharacter;
    if (focus) this.live.send({ type: "focus", character: focus });
    // sent just before the drop and never seen by the server: send again (same turnId, a new turnSeq)
    if (this.inflight && w.lastTurn?.turnId !== this.inflight.turnId)
      this.outbox.unshift(this.inflight);
    this.inflight = null;
    const out = this.outbox;
    this.outbox = [];
    for (const o of out) this.sendText(o);
  }

  // what the subtitles showed before the drop (api-contract 4)
  private restore(lt: Api.LastTurn | null): void {
    if (!lt) return;
    const v = useVoice.getState();
    if (lt.status === "lost") {
      if (v.turn?.turnId === lt.turnId || !v.turn) {
        useVoice.setState({ turn: null, character: null });
        addNarration(copy["reconnect.lostTurn"]);
      }
      return;
    }
    if (v.turn && v.turn.turnId !== lt.turnId) return; // we already moved on
    const speaker = lt.character ?? "narrator";
    useVoice.setState({
      turn: {
        turnId: lt.turnId,
        turnSeq: v.turn?.turnSeq ?? 0,
        phase: lt.status === "settled" ? "settled" : "done",
      },
      player:
        lt.playerText === null
          ? v.player
          : {
              turnId: lt.turnId,
              speaker: "player",
              text: lt.playerText,
              final: true,
            },
      character:
        lt.characterText === null
          ? v.character
          : { turnId: lt.turnId, speaker, text: lt.characterText, final: true },
    });
  }

  private transcript(t: Api.TranscriptMessage): void {
    const line = {
      turnId: t.turnId,
      speaker: t.speaker,
      text: t.text,
      final: t.final,
      ...(t.source ? { source: t.source } : {}),
    };
    if (t.speaker === "player") {
      useVoice.setState({ player: line });
      return;
    }
    this.answered(t.turnId);
    useVoice.setState((s) => ({
      character: line,
      turn:
        s.turn?.turnId === t.turnId && s.turn.phase === "waiting"
          ? { ...s.turn, phase: "speaking" }
          : s.turn,
    }));
  }

  private answered(turnId: string): void {
    if (this.inflight?.turnId === turnId) this.inflight = null;
  }

  private undelivered(): void {
    this.inflight = null;
    useVoice.setState((s) =>
      s.turn?.phase === "waiting" ? { turn: null, character: null } : s,
    );
    addNarration(copy["reconnect.lostTurn"]);
  }

  private async commit(c: Api.CommitMessage): Promise<void> {
    if (this.refilling) {
      this.held.push(c);
      return;
    }
    const world = useWorld.getState().world;
    if (!world) return;
    const r = applyCommit(world, c);
    if (r.kind === "seen") return;
    if (r.kind === "gap") {
      this.held.push(c);
      this.refilling = this.refill(world).finally(
        () => (this.refilling = null),
      );
      await this.refilling;
      const held = this.held;
      this.held = [];
      for (const h of held) await this.commit(h);
      return;
    }
    setWorld(withReveal(r.world, c.reveal));
    setTelemetryContext({
      playthroughId: this.playthroughId,
      t: r.world.clock.t,
    });
    addNarration(...c.narration);
    showToasts(this.toasts(c));
  }

  // a missing range: the events after our lastSeq (page by page), then the snapshot for the rest of the state (3.4)
  private async refill(world: WorldData): Promise<void> {
    try {
      let after = world.lastSeq;
      let events = world.events;
      for (;;) {
        const page = await rest.events(this.playthroughId, after);
        events = addEvents(events, page.events);
        const last = page.events.at(-1)?.seq ?? after;
        if (!page.events.length || last >= page.lastSeq) break;
        after = last;
      }
      const snap = await rest.snapshot(this.playthroughId);
      setWorld(fromSnapshot(snap, events));
    } catch {
      // the socket will reconnect and the server resends from our lastSeq
    }
  }

  private name(id: string): string {
    return this.names[id] ?? id;
  }

  // the light reactions of one commit (ux-design 8.2): what characters remember, promises, what they did for you,
  // and the story moving; key moments get the heavy feedback instead (8.3, a later card)
  private toasts(c: Api.CommitMessage): Omit<Toast, "id">[] {
    const out: Omit<Toast, "id">[] = [];
    for (const m of c.memories) {
      if (m.change === "deleted") continue;
      const head =
        m.kind === "promise" ? copy["toast.promise"] : copy["toast.memory"];
      out.push({
        head: fill(head, { name: this.name(m.character) }),
        ...(m.text ? { body: m.text } : {}),
        tone: "memory",
      });
    }
    for (const p of c.promises) {
      if (p.status === "kept")
        out.push({
          head: copy["toast.promiseKept"],
          body: p.text,
          tone: "memory",
        });
      if (p.status === "broken")
        out.push({
          head: copy["toast.promiseBroken"],
          body: p.text,
          tone: "event",
        });
    }
    for (const e of c.events) {
      if (e.keyMoment) continue;
      if (
        e.forPlayer &&
        e.actor !== "player" &&
        e.actor !== "system" &&
        e.actor !== "narrator"
      )
        out.push({
          head: fill(copy["toast.aid"], { name: this.name(e.actor) }),
          body: e.summary,
          tone: "memory",
        });
      else if (e.visibleEffects.length)
        out.push({
          head: copy["toast.event"],
          body: e.visibleEffects.map((v) => v.label).join("\n"),
          tone: "event",
        });
    }
    return out;
  }
}

const withReveal = (w: WorldData, reveal: Api.Reveal | null): WorldData =>
  reveal ? { ...w, pending: { ...w.pending, reveal } } : w;

function wsUrl(pid: string): string {
  const { protocol, host } = window.location;
  return `${protocol === "https:" ? "wss" : "ws"}://${host}/v1/playthroughs/${encodeURIComponent(pid)}/live`;
}
