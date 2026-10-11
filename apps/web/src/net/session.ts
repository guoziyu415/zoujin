// One open playthrough (frontend-design 4, 9): owns the Live socket, writes what the server says into the stores, and
// gives the screens a few verbs (focus, say, examine). The conversation itself (turns, voice, subtitles, the safety
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
import { usePlayer } from "../stores/player";
import { showToasts, useUi, type Toast } from "../stores/ui";
import { setTelemetryContext, track } from "../telemetry/telemetry";
import { addEndingLines, resetStory, useStory } from "../stores/story";
import * as story from "./story";
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
export const ENDING_LINE_WAIT_MS = 3000; // the line being spoken when the ending starts finishes, at most this long

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
  private actChange: Api.CommitMessage[] = []; // the act change's commits, held until act_transition (3.11)
  readonly unknown = new Map<string, number>();

  constructor(
    readonly playthroughId: string,
    private readonly hooks: SessionHooks,
    url = wsUrl(playthroughId),
    Ctor?: ConstructorParameters<typeof Live>[3],
    private readonly audio: AudioPort = pageAudio,
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
    usePlayer.setState({ nearCharacter: null, focusCharacter: null });
    resetStory();
    this.actChange = [];
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

  // —— the act end (ux-design 4.4, api-contract 3.11) ——

  actChoose(optionId: string, enRouteChoice?: number): void {
    const a = useStory.getState().actEnd;
    if (!a || a.phase.k === "chosen" || a.phase.k === "thinking") return;
    useStory.setState({ actEnd: story.chosen(a, optionId) });
    this.live.send({
      type: "act_choose",
      clientMsgId: uuid(),
      optionId,
      ...(enRouteChoice === undefined ? {} : { enRouteChoice }),
    });
  }

  actPropose(text: string): void {
    const a = useStory.getState().actEnd;
    const t = text.trim();
    if (!a || a.phase.k !== "propose" || !t) return;
    const clientMsgId = uuid();
    useStory.setState({ actEnd: story.proposed(a, { clientMsgId }) });
    this.live.send({ type: "act_propose", clientMsgId, text: t.slice(0, 200) });
  }

  // shown the landing line of an arrival with an opener: the server lets the opener speak first
  actLanded(actId: string): void {
    this.live.send({ type: "act_landed", actId });
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
        if (useStory.getState().ending)
          return addEndingLines([{ text: msg.line, speaker: null }]);
        return addNarration(msg.line);
      case "action_result":
        if (msg.narration) addNarration(msg.narration);
        return;
      case "limits":
        useVoice.setState({ voiceMinutesLeft: msg.voiceMinutesLeft });
        return;
      case "act_ended":
        return this.actEnded(msg);
      case "act_plan_result": {
        const a = useStory.getState().actEnd;
        if (!a) return;
        const next = story.planResult(a, msg);
        useStory.setState({ actEnd: next });
        if (next.phase.k === "result" && a.phase.k === "thinking")
          track("act_plan_result", {
            actId: a.end.actId,
            accepted: msg.accepted,
            try: a.end.freeform.triesLeft - msg.triesLeft,
            inputMode: msg.turnId ? "voice" : "text",
          });
        return;
      }
      case "act_transition":
        return this.actTransition(msg);
      case "ending_started":
        return void this.endingStarted(msg);
      case "ending_ready": {
        const e = useStory.getState().ending;
        if (e) useStory.setState({ ending: { ...e, endingId: msg.endingId } });
        return;
      }
      case "set_piece":
        if (useStory.getState().ending)
          addEndingLines(
            msg.lines.map((l, i) =>
              "narration" in l
                ? {
                    text: l.narration,
                    speaker: null,
                    pieceId: msg.pieceId,
                    n: i + 1,
                  }
                : {
                    text: l.line,
                    speaker: l.speaker,
                    pieceId: msg.pieceId,
                    n: i + 1,
                  },
            ),
          );
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
    this.pendingStory(w.pending);
    useVoice.setState({
      degraded: w.voice.degraded || !w.voice.enabled,
      voiceMinutesLeft: w.voice.minutesLeftToday,
    });
    // the server has its own lastSeq; it resends the commits after ours right behind this welcome (api-contract 4)
    const focus = usePlayer.getState().focusCharacter;
    if (focus) this.live.send({ type: "focus", character: focus });
    // turnSeq from 1 again, the last turn's words back, what was typed while down goes now
    this.voice.connected(w.lastTurn, w.pending);
  }

  private async commit(c: Api.CommitMessage): Promise<void> {
    // after the exit is chosen, the act change's commits wait for act_transition, which lands from its own snapshot
    const a = useStory.getState().actEnd;
    if (
      a &&
      (a.phase.k === "chosen" || (a.phase.k === "result" && a.phase.accepted))
    ) {
      this.actChange.push(c);
      return;
    }
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
    setTelemetryContext({
      playthroughId: this.playthroughId,
      t: r.world.clock.t,
    });
    // during the ending's staging the results don't run ahead of it (ux-design 11.1): no light reactions, no key
    // moment; the narration joins the staging's subtitles; the map has the events
    if (useStory.getState().ending) {
      setWorld(r.world, true);
      addEndingLines(c.narration.map((text) => ({ text, speaker: null })));
      return;
    }
    setWorld(withReveal(r.world, c.reveal), true);
    addNarration(...c.narration);
    showToasts(this.toasts(c));
  }

  // the act ends: what was being said or done is dropped (3.11: the server refuses it now); the page takes over
  private actEnded(end: Api.ActEnd): void {
    if (usePlayer.getState().focusCharacter) this.unfocus("menu");
    useStory.setState({ actEnd: story.actEnded(end), overlay: null });
  }

  // the next act: the snapshot replaces the world (complete, after the landing); the held commits only add their
  // events, for the map. Then その頃, the slice's jump page and the landing line (4.5).
  private actTransition(m: Api.ActTransitionMessage): void {
    const world = useWorld.getState().world;
    const held = this.actChange;
    this.actChange = [];
    const events = held.reduce(
      (list, c) => addEvents(list, c.events),
      world?.events ?? [],
    );
    setWorld(fromSnapshot(m.snapshot, events));
    setTelemetryContext({
      playthroughId: this.playthroughId,
      t: m.snapshot.clock.t,
    });
    // the new act starts with an empty subtitle panel: the landing line is its first line (4.5)
    useVoice.setState({
      player: null,
      character: null,
      narration: [],
      suggestions: null,
    });
    useStory.setState({ actEnd: null, transition: story.transition(m) });
  }

  // the ending (ux-design 11.1): input stops at once; a character's line being spoken finishes (at most ~3 s, then a
  // 0.2 s fade); the microphone is released so the staging plays at full quality. Then the staging takes the screen.
  private async endingStarted(m: Api.EndingStartedMessage): Promise<void> {
    if (useStory.getState().ending) return;
    useStory.setState({
      ending: {
        trigger: m.trigger,
        staging: m.staging,
        lines: [],
        endingId: null,
        roleId: useWorld.getState().world?.player.roleId ?? null,
        ready: false,
      },
      actEnd: null,
      overlay: null,
    });
    if (usePlayer.getState().focusCharacter) this.unfocus("menu");
    const until = performance.now() + ENDING_LINE_WAIT_MS;
    while (this.audio.playing() && performance.now() < until)
      await new Promise((r) => setTimeout(r, 100));
    if (this.audio.playing()) {
      this.audio.fadeOut(200);
      await new Promise((r) => setTimeout(r, 200));
    }
    this.audio.releaseMic();
    // until now the staging only gathered its lines (api-contract 3.14: the line being said is finished first)
    const e = useStory.getState().ending;
    if (e) useStory.setState({ ending: { ...e, ready: true } });
  }

  // back after a drop or a reload in the middle of an act end, or before landing (api-contract 4)
  private pendingStory(p: Api.Pending): void {
    const st = useStory.getState();
    // a plan said before the drop gets no result afterwards (3.11): back to the exits, with the server's tries left
    if (p.actEnd && (!st.actEnd || st.actEnd.phase.k === "thinking"))
      useStory.setState({ actEnd: story.actEnded(p.actEnd) });
    if (!p.actEnd && st.actEnd && st.actEnd.phase.k !== "chosen")
      useStory.setState({ actEnd: null }); // chosen while we were away; act_transition follows in the resend
    if (p.arrival && !st.transition && !p.actEnd)
      useStory.setState({
        transition: {
          ...story.transition({
            fromActId: "",
            toActId: useWorld.getState().world?.actId ?? "",
            recap: [],
            arrival: p.arrival,
          }),
        },
      });
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
