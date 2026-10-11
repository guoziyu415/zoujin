// One open playthrough (frontend-design 4, 9): owns the Live socket, writes what the server says into the stores, and
// gives the screens and the 3D a few verbs (focus, move, near, say, examine). The conversation itself (turns, voice, subtitles, the safety
// card) is the voice controller's; the session hands it those messages and the voice frames. Components call these
// verbs and read the stores; none of them sees the socket. Messages this client doesn't know yet are ignored and
// counted (api-contract 0: the protocol only adds).
import type { Api } from "@zoujin/contracts";
import type { AudioPort } from "../audio/engine";
import { audio as pageAudio } from "../audio";
import { VoiceController } from "../voice/controller";
import { addEvents, applyCommit, fromSnapshot, type WorldData } from "./apply";
import { uuid } from "./ids";
import { Live, type Ended } from "./live";
import { rest } from "./rest";
import { setWorld, useWorld } from "../stores/world";
import { addNarration, initialVoice, useVoice } from "../stores/voice";
import { placePlayer, usePlayer } from "../stores/player";
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

export type SessionHooks = {
  onEnded: (why: Ended) => void; // 4001 → the invite page; taken / gone → the screen says so
};

export class Session {
  private live: Live;
  readonly voice: VoiceController;
  private welcomed = false;
  private refilling: Promise<void> | null = null;
  private held: Api.CommitMessage[] = []; // commits that came while refilling
  private names: Record<string, string> = {};
  private moves = new Map<string, string | null>(); // move actions waiting for their action_result: where from
  private unsentMove: string | null = null; // walked into a place while the socket was down
  readonly unknown = new Map<string, number>();

  constructor(
    readonly playthroughId: string,
    private readonly hooks: SessionHooks,
    url = wsUrl(playthroughId),
    Ctor?: ConstructorParameters<typeof Live>[3],
    audio: AudioPort = pageAudio,
  ) {
    this.live = new Live(
      url,
      CLIENT_VERSION,
      {
        lastSeq: () => useWorld.getState().world?.lastSeq ?? 0,
        onMessage: (m) => this.dispatch(m),
        onBinary: (b) => this.voice.binary(b),
        onOpen: () => {},
        onDown: (reason) => this.down(reason),
        onEnded: (why) => this.ended(why),
      },
      Ctor,
    );
    this.voice = new VoiceController(audio, {
      send: (m) => this.live.send(m),
      sendBinary: (b) => this.live.sendBinary(b),
      ready: () => this.welcomed && this.live.open,
    });
  }

  // the snapshot from POST /playthroughs or GET /snapshot; then the socket
  start(snapshot: Api.Snapshot): void {
    setWorld(fromSnapshot(snapshot));
    useVoice.setState(initialVoice());
    this.voice.init();
    usePlayer.setState({
      nearCharacter: null,
      focusCharacter: null,
      distances: {},
      goal: null,
    });
    placePlayer(snapshot.player.place, snapshot.player.spot);
    useUi.setState({ connection: "connecting", downSince: null });
    setTelemetryContext({
      playthroughId: snapshot.playthroughId,
      t: snapshot.clock.t,
    });
    this.live.connect();
  }

  stop(): void {
    this.voice.stop();
    this.live.close();
    this.welcomed = false;
    setTelemetryContext({});
  }

  // pagehide (9.5): close without the banner; coming back calls reconnect()
  suspend(): void {
    this.voice.suspend();
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
    this.voice.focused(character);
  }

  unfocus(reason: Api.UnfocusMessage["reason"] = "menu"): void {
    usePlayer.setState({ focusCharacter: null });
    useVoice.setState({ session: { character: null, status: "none" } });
    this.live.send({ type: "unfocus", reason });
    this.voice.unfocused();
  }

  // the 3D: the player walked into another place of this scene (api-contract 3.8). Not waited for; a refusal sends
  // them back to where they came from.
  move(place: string, from: string | null): void {
    const clientMsgId = uuid();
    const sent = this.live.send({
      type: "action",
      clientMsgId,
      kind: "move",
      target: place,
    });
    if (sent) this.moves.set(clientMsgId, from);
    this.unsentMove = sent ? null : place;
  }

  // the 3D: the closest talkable character within 8 m, and leaving 12 m (3.2); the server warms their session
  near(character: string): void {
    usePlayer.setState({ nearCharacter: character });
    this.live.send({ type: "near", character });
  }

  far(character: string): void {
    if (usePlayer.getState().nearCharacter === character)
      usePlayer.setState({ nearCharacter: null });
    this.live.send({ type: "far", character });
  }

  // typed text (or a suggestion chip): the player's line shows at once, the character's when it comes
  say(text: string, via: Api.TextMessage["via"] = "typed"): void {
    this.voice.say(text, via);
  }

  examine(target: string): void {
    this.live.send({
      type: "action",
      clientMsgId: uuid(),
      kind: "examine",
      target,
    });
  }

  // —— the socket's side ——

  private down(reason: string): void {
    const ui = useUi.getState();
    this.welcomed = false;
    this.voice.down();
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
      case "session_ready":
      case "turn_started":
      case "transcript":
      case "interrupted":
      case "turn_complete":
      case "suggestions":
      case "turn_settled":
      case "turn_retract_result":
      case "safety_pause":
      case "safety_hint":
      case "safety_resumed":
      case "degraded":
        return this.voice.message(msg);
      case "commit":
        return void this.commit(msg);
      case "narration":
        return addNarration(msg.line);
      case "action_result":
        return this.actionResult(msg);
      case "limits":
        useVoice.setState({ voiceMinutesLeft: msg.voiceMinutesLeft });
        return;
      case "error":
        // invalid_request: what we sent didn't fit the schema; the turn didn't happen (api-contract 5)
        if (msg.error.code === "invalid_request") this.voice.undelivered();
        return;
      default:
        return; // known, handled by later cards (set pieces, confirm, approach, act end, ending: M2)
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
      degraded: w.voice.degraded || !w.voice.enabled,
      voiceMinutesLeft: w.voice.minutesLeftToday,
    });
    // the server has its own lastSeq; it resends the commits after ours right behind this welcome (api-contract 4)
    const {
      focusCharacter: focus,
      nearCharacter: near,
      place,
    } = usePlayer.getState();
    if (near) this.live.send({ type: "near", character: near });
    if (focus) this.live.send({ type: "focus", character: focus });
    if (this.unsentMove && this.unsentMove === place)
      this.move(place, world?.player.place ?? null);
    this.unsentMove = null;
    // turnSeq from 1 again, the last turn's words back, what was typed while down goes now
    this.voice.connected(w.lastTurn, w.pending);
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
    // the server put the player somewhere (a place shut with them in it, a situational action's playerSpot): 3.8
    if (c.patch.player) placePlayer(r.world.player.place, c.patch.player.spot);
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
      // the server keeps no spot for walking about inside a place: only a different place moves the player
      if (snap.player.place !== usePlayer.getState().place)
        placePlayer(snap.player.place, snap.player.spot);
    } catch {
      // the socket will reconnect and the server resends from our lastSeq
    }
  }

  private actionResult(m: Api.ActionResultMessage): void {
    if (m.narration) addNarration(m.narration);
    if (!this.moves.has(m.clientMsgId)) return;
    const from = this.moves.get(m.clientMsgId) ?? null;
    this.moves.delete(m.clientMsgId);
    // the place had just shut (3.8): back where they came from, and no move for that
    if (m.status === "refused" && from) placePlayer(from);
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
