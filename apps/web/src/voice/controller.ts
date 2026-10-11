// The conversation with the focused character (frontend-design 7): turns by voice and by text, what the subtitles
// show, the waiting ladder, interrupting, retracting and correcting, and the safety card. The session hands it the
// messages about turns and the character's voice frames; the HUD calls its verbs through net/play.ts. It writes the
// voice store and drives the audio through AudioPort, so its tests run without a browser's audio.
import type { Api } from "@zoujin/contracts";
import type { AudioPort, Clip } from "../audio/engine";
import { micFrame, MIC_FRAME_MS, readVoice } from "../audio/frames";
import { turnId as newTurnId } from "../net/ids";
import { addNarration, useVoice, type Line, type Turn } from "../stores/voice";
import { usePlayer } from "../stores/player";
import { useUi } from "../stores/ui";
import { track } from "../telemetry/telemetry";
import { copy } from "../ui/copy";
import { Caption } from "./caption";
import { canPress, voiceState, type VoiceState } from "./state";
import { voiceSettings } from "./settings";

export const TOO_SHORT_MS = 250; // ux-design 7.1: a shorter press is a slip
export const HOLD_BACK_MS = 15_000; // api-contract 3.2 (v1.0.9): the whole press waits for the session, up to 15 s
export const PREPARING_MS = 2000; // frontend-design 7.1: still waiting after 2 s of voice → the key says so
export const AIZUCHI_MS = 700; // 7.8: still silent after 0.7 s → an aizuchi
export const AIZUCHI_HOLD_MS = 600; // the real answer waits for it at most this: a whole clip, its edges too (ux-design 16.2)
export const NO_RESPONSE_MS = 6000; // 7.6 no-response
export const GIVE_UP_MS = 12_000; // 7.8: the turn is retracted, the character says it didn't hear
export const CAPTION_WAIT_MS = 8000; // 7.5: no final line 8 s after turn_complete → as if it failed
export const MIC_IDLE_MS = 120_000; // S-073 ③: the microphone goes 2 minutes after the conversation ends
export const FADE_MS = 200; // 12: the voice fades out in 0.2 s on a safety pause
const TOO_SHORT_NOTE_MS = 1500;

export type Wire = {
  send(m: Api.ClientMessage): boolean;
  sendBinary(b: ArrayBuffer): boolean;
  ready(): boolean; // welcomed, socket open
};

type Rec = {
  id: string;
  seq: number; // 0 until sent
  kind: Turn["kind"];
  character: string | null;
  text?: string; // a typed turn's words, while it may still need sending
  via?: Api.TextMessage["via"];
  replaces?: string;
  pressAt?: number;
  startAt?: number; // released (voice) or sent (text): the waiting ladder counts from here
  firstVoice: boolean;
  audibleAt?: number;
  complete: boolean;
  settled: boolean;
  noVoice: boolean; // turn_complete { audio: false }: the words show without waiting for a voice
  noResponse: boolean; // the 6 s chips were shown (or turn_complete said there would be no voice)
  drop: boolean; // cut or paused: late voice frames go
  reported: boolean; // talk_turn sent
  caption: Caption;
  filler: string | null; // an aizuchi's words, until the real answer's first words show
  retract?: "cancel" | "redo" | "timeout" | "correction";
  timers: ReturnType<typeof setTimeout>[];
};

type Prerecorded = NonNullable<
  Api.ManifestResponse["characters"][number]["prerecorded"]
>;

export class VoiceController {
  private cur: Rec | null = null;
  private recs = new Map<string, Rec>();
  private holding: Rec | null = null;
  private heldBack: (ArrayBuffer | Api.ClientMessage)[] = []; // after activity_start, before session_ready
  private heldBackMs = 0;
  private outbox: Rec[] = []; // typed while the socket was down
  private inflight: Rec | null = null; // a typed turn sent, nothing back for it yet
  private clips: Record<string, Prerecorded> = {};
  private turnsDone = 0;
  private lastAizuchi = { turn: -10, url: "" };
  private micTimer: ReturnType<typeof setTimeout> | undefined;
  private noteTimer: ReturnType<typeof setTimeout> | undefined;
  private clipTimer: ReturnType<typeof setInterval> | undefined;
  private before: Line | null = null; // the character's line before the current turn (the safety card returns to it)

  constructor(
    private readonly audio: AudioPort,
    private readonly wire: Wire,
  ) {
    audio.bind({
      onFrame: (pcm) => this.frame(pcm),
      onStarted: (tag, at) => this.audible(tag, at),
      onDrained: (tag) => this.drained(tag),
      onPosition: () => this.position(),
      // a call, Siri, the silent switch took the audio (7.4): one tap brings it back
      onInterrupted: () => {
        if (
          typeof document !== "undefined" &&
          document.visibilityState === "visible"
        )
          useUi.setState({ resumeGate: true });
      },
    });
  }

  // —— what the HUD reads ——

  state(): VoiceState {
    const v = useVoice.getState();
    const ui = useUi.getState();
    return voiceState({
      connection: ui.connection,
      resumeGate: ui.resumeGate,
      paused: v.paused,
      degraded: v.degraded,
      mic: v.mic,
      sheet: v.sheet,
      focus: usePlayer.getState().focusCharacter,
      session: v.session.status,
      holding: !!v.hold,
      turn: v.turn,
    });
  }

  setClips(byCharacter: Record<string, Prerecorded>): void {
    this.clips = byCharacter;
    const focus = usePlayer.getState().focusCharacter;
    if (focus) this.preload(focus);
  }

  // a new playthrough's store: what this device remembers, and whether the browser already allows the microphone
  // (then there is no primer: 7.3 asks once, and the browser has been asked)
  init(): void {
    if (voiceSettings.text) {
      useVoice.setState({ mic: "text" });
      return;
    }
    void navigator.permissions
      ?.query({ name: "microphone" as PermissionName })
      .then((p) => {
        if (p.state === "granted" && useVoice.getState().mic === "unknown")
          useVoice.setState({ mic: "granted" });
      })
      .catch(() => {});
  }

  // —— focus and the microphone (S-073 ③) ——

  // the player picked a character (a tap: the microphone may open here, muted, ahead of the first press)
  focused(character: string): void {
    this.wake();
    clearTimeout(this.micTimer);
    this.preload(character);
    if (
      useVoice.getState().mic === "granted" &&
      voiceSettings.micMode === "session"
    )
      void this.audio.openMic().then((r) => {
        if (!r.ok) this.micFailed(r.result, r.reason, false);
      });
  }

  unfocused(): void {
    if (this.holding) this.abortHold();
    clearTimeout(this.micTimer);
    this.micTimer = setTimeout(() => this.audio.releaseMic(), MIC_IDLE_MS);
  }

  // a tap that may be the page's first (a reload straight into the story): the AudioContext can start here (7.4)
  private wake(): void {
    if (!this.audio.running) this.audio.unlock();
  }

  private preload(character: string): void {
    const p = this.clips[character];
    if (p) this.audio.preload([...p.aizuchi, ...p.unheard, p.wait]);
  }

  // the primer's two buttons (ux-design 7.3), inside the tap
  primer(choice: "mic" | "text"): void {
    if (choice === "text") {
      this.setMic("text");
      useVoice.setState({ sheet: null, textOpen: true });
      return;
    }
    this.audio.unlock();
    void this.audio.openMic().then((r) => {
      if (!r.ok) return this.micFailed(r.result, r.reason, true);
      track("mic_permission", { result: "granted", afterPrimer: true });
      this.setMic("granted");
      useVoice.setState({ sheet: null, micReady: true });
      if (
        voiceSettings.micMode === "perTurn" ||
        !usePlayer.getState().focusCharacter
      )
        this.audio.releaseMic();
    });
  }

  // 「声に戻す」 from text: try the microphone again (the player may have allowed it in the settings)
  backToVoice(): void {
    this.setMic("unknown");
    useVoice.setState({ textOpen: false, sheet: "primer" });
  }

  // the denied / unavailable sheet's 〔文字で続ける〕
  continueInText(): void {
    useVoice.setState({ sheet: null, textOpen: true });
  }

  private micFailed(
    result: "denied" | "unavailable",
    reason: string,
    afterPrimer: boolean,
  ): void {
    track("mic_permission", {
      result,
      reason: reason.slice(0, 64),
      afterPrimer,
    });
    this.setMic(result);
    useVoice.setState({ sheet: result });
    if (this.holding) this.abortHold();
  }

  private setMic(
    mic: "unknown" | "granted" | "denied" | "unavailable" | "text",
  ): void {
    useVoice.setState({ mic });
    voiceSettings.rememberText(mic === "text");
  }

  // —— the talk key (ux-design 7.1) ——

  press(): void {
    const st = this.state();
    if (this.holding || !canPress(st)) return;
    this.wake();
    const v = useVoice.getState();
    if (v.mic === "unknown") {
      useVoice.setState({ sheet: "primer" }); // this press doesn't record (7.6 primer)
      return;
    }
    if (v.mic !== "granted") return;
    const now = performance.now();
    this.cutCurrent(); // local silence first (≤ 50 ms), then tell the server
    const seq = this.nextSeq();
    const r = this.newRec("voice", seq);
    r.pressAt = now;
    this.holding = r;
    this.heldBack = [];
    this.heldBackMs = 0;
    this.audio.startTurn(seq);
    useVoice.setState({
      turn: { turnId: r.id, turnSeq: seq, kind: "voice", phase: "listening" },
      hold: { slide: false, preparing: false },
      player: null,
      suggestions: null,
      micReady: false,
      note: null,
    });
    this.wire.send({ type: "activity_start", turnId: r.id, turnSeq: seq });
    if (this.audio.micOpen() && voiceSettings.micMode === "session")
      this.audio.setSending(true);
    else
      void this.audio.openMic().then((res) => {
        if (!res.ok) return this.micFailed(res.result, res.reason, false);
        if (this.holding === r) this.audio.setSending(true);
      });
  }

  // past 60 px up while holding: letting go cancels (ux-design 7.1)
  slide(armed: boolean): void {
    const h = useVoice.getState().hold;
    if (this.holding && h && h.slide !== armed)
      useVoice.setState({ hold: { ...h, slide: armed } });
  }

  release(): void {
    const r = this.holding;
    if (!r) return;
    const now = performance.now();
    const slid = useVoice.getState().hold?.slide ?? false;
    this.holding = null;
    this.audio.setSending(false);
    if (voiceSettings.micMode === "perTurn") this.audio.releaseMic();
    useVoice.setState({ hold: null });
    const short = !voiceSettings.tap && now - (r.pressAt ?? now) < TOO_SHORT_MS;
    if (short || slid) {
      this.heldBack = [];
      this.wire.send({ type: "turn_retract", turnId: r.id });
      if (short) {
        // a slip: no line, no count (it isn't a turn the player meant)
        this.forget(r);
        useVoice.setState({ turn: null, player: null, note: "tooShort" });
        clearTimeout(this.noteTimer);
        this.noteTimer = setTimeout(
          () => useVoice.setState({ note: null }),
          TOO_SHORT_NOTE_MS,
        );
      } else {
        r.retract = "cancel";
        this.endTurn(r, { cancelled: true });
      }
      return;
    }
    r.startAt = now;
    this.post({ type: "activity_end", turnId: r.id, turnSeq: r.seq });
    this.setTurn(r, { phase: "waiting" });
    this.ladder(r);
  }

  // pagehide, a drop: a turn being held ends where it is (9.5: as if let go); the session won't hear the rest
  private abortHold(): void {
    const r = this.holding;
    if (!r) return;
    this.holding = null;
    this.heldBack = [];
    this.audio.setSending(false);
    useVoice.setState({ hold: null });
    if (this.wire.ready())
      this.post({ type: "activity_end", turnId: r.id, turnSeq: r.seq });
    r.startAt = performance.now();
    this.setTurn(r, { phase: "waiting" });
    this.ladder(r);
  }

  // degraded with the turn's voice still waiting for a session that won't come: nobody heard it. The turn is
  // retracted (no story time), the words kept on screen go, and the narrator's degraded line says the rest
  private dropUnsent(): void {
    if (!this.heldBack.some((m) => m instanceof ArrayBuffer)) return;
    const r = this.holding ?? this.cur;
    this.heldBack = [];
    this.heldBackMs = 0;
    if (!r || r.kind !== "voice") return;
    if (this.holding === r) {
      this.holding = null;
      this.audio.setSending(false);
      if (voiceSettings.micMode === "perTurn") this.audio.releaseMic();
    }
    r.retract = "timeout"; // ours: no too_late line if it comes back
    if (this.wire.ready())
      this.wire.send({ type: "turn_retract", turnId: r.id });
    this.endTurn(r, {});
    useVoice.setState((s) => ({
      hold: null,
      player: s.player?.turnId === r.id ? null : s.player,
    }));
  }

  // the microphone's 40 ms frames while the key is down
  frame(pcm: Int16Array): void {
    const r = this.holding;
    if (!r) return;
    const f = micFrame(r.seq, pcm);
    if (this.sessionReady() && !this.heldBack.length) {
      this.wire.sendBinary(f);
      return;
    }
    if (this.heldBackMs >= HOLD_BACK_MS) return; // past 15 s the rest isn't kept
    this.heldBack.push(f);
    this.heldBackMs += MIC_FRAME_MS;
    const h = useVoice.getState().hold;
    if (this.heldBackMs >= PREPARING_MS && h && !h.preparing)
      useVoice.setState({ hold: { ...h, preparing: true } }); // 「準備しています」
  }

  // what comes after activity_start waits with the held-back voice until the session is ready
  private post(m: Api.ClientMessage): void {
    if (this.sessionReady() && !this.heldBack.length) this.wire.send(m);
    else this.heldBack.push(m);
  }

  private sessionReady(): boolean {
    const s = useVoice.getState().session;
    return (
      s.status === "ready" &&
      s.character === usePlayer.getState().focusCharacter
    );
  }

  private sendHeldBack(): void {
    const q = this.heldBack;
    this.heldBack = [];
    this.heldBackMs = 0;
    for (const m of q) {
      if (m instanceof ArrayBuffer) this.wire.sendBinary(m);
      else this.wire.send(m);
    }
    const h = useVoice.getState().hold;
    if (h?.preparing) useVoice.setState({ hold: { ...h, preparing: false } });
  }

  // —— typed turns (7.1: typing and talking are equal) ——

  say(
    text: string,
    via: Api.TextMessage["via"] = "typed",
    replaces?: string,
  ): void {
    this.wake();
    this.cutCurrent(); // sending text interrupts too
    const r = this.newRec("text", 0);
    r.text = text;
    r.via = via;
    if (replaces) r.replaces = replaces;
    useVoice.setState({
      turn: { turnId: r.id, turnSeq: 0, kind: "text", phase: "waiting" },
      player: {
        turnId: r.id,
        speaker: "player",
        text,
        final: true,
        fromChip: via === "chip",
      },
      character: null,
      suggestions: null,
      note: null,
    });
    if (this.wire.ready()) this.sendText(r);
    else this.outbox.push(r);
  }

  // a correction of the player's own words (7.5): within the window the old turn is retracted and the corrected text
  // replaces it; after it, just a new turn
  correct(text: string, of: string): void {
    track("transcript_corrected", { turnId: of });
    const old = this.recs.get(of);
    useVoice.setState({ draft: null, textOpen: false });
    if (old && !old.settled) {
      old.retract = "correction";
      this.wire.send({ type: "turn_retract", turnId: of });
      this.say(text, "correction", of);
    } else this.say(text, "typed");
  }

  private sendText(r: Rec): void {
    const seq = this.nextSeq();
    r.seq = seq;
    r.startAt = performance.now();
    this.audio.startTurn(seq);
    this.inflight = r;
    useVoice.setState((s) =>
      s.turn?.turnId === r.id ? { turn: { ...s.turn, turnSeq: seq } } : s,
    );
    this.wire.send({
      type: "text",
      turnId: r.id,
      turnSeq: seq,
      text: r.text!,
      via: r.via!,
      ...(r.replaces ? { replaces: r.replaces } : {}),
    });
    this.ladder(r);
  }

  // —— the retract button, the no-response chips ——

  retract(): void {
    const r = this.cur;
    const t = useVoice.getState().turn;
    if (
      !r ||
      !t ||
      t.turnId !== r.id ||
      r.settled ||
      r.kind === "server" ||
      !r.seq
    )
      return;
    const kind = r.complete ? "redo" : "cancel";
    if (kind === "cancel" && r.audibleAt) return; // the character has started: it's 言い直す from turn_complete
    if (this.audio.playing()) this.audio.flush();
    r.retract = kind;
    this.wire.send({ type: "turn_retract", turnId: r.id });
    this.endTurn(r, { cancelled: true, cut: kind === "redo" });
  }

  // 「もう一度話す」: the chips go, the key is ready
  again(): void {
    const t = useVoice.getState().turn;
    if (t?.noResponse) useVoice.setState({ turn: { ...t, noResponse: false } });
    useVoice.setState({ textOpen: false });
  }

  // 「文字で送る」, 「文字で話す」, the player's own line tapped (a correction)
  openText(
    draft: { text: string; replaces: string | null } | null = null,
  ): void {
    useVoice.setState({ textOpen: true, draft });
  }

  closeText(): void {
    useVoice.setState({ textOpen: false, draft: null });
  }

  // —— the session's side ——

  // welcome: turnSeq starts again; the last turn's words come back; what was typed while down goes now; a safety
  // pause the server still holds comes back as the card (api-contract 4)
  connected(
    lastTurn: Api.LastTurn | null,
    pending: { safetyPause: boolean } | null = null,
  ): void {
    useVoice.setState({ nextTurnSeq: 1 });
    // a voice turn the server never got (let go while the line was already down) isn't its last turn and will
    // never settle: it's lost, said the same way (a typed one is sent again below)
    const r = this.cur;
    if (
      r?.kind === "voice" &&
      !r.settled &&
      r.audibleAt === undefined &&
      useVoice.getState().turn?.turnId === r.id &&
      lastTurn?.turnId !== r.id
    )
      this.restore({
        turnId: r.id,
        character: r.character,
        status: "lost",
        playerText: null,
        characterText: null,
      });
    else this.restore(lastTurn);
    if (pending?.safetyPause) {
      this.pause(false);
      this.outbox = []; // typed while down, into a pause: dropped like a held turn
    }
    if (this.inflight && lastTurn?.turnId !== this.inflight.id)
      this.outbox.unshift(this.inflight);
    this.inflight = null;
    const out = this.outbox;
    this.outbox = [];
    for (const r of out) this.sendText(r);
  }

  down(): void {
    if (this.holding) {
      const r = this.holding;
      this.holding = null;
      this.heldBack = [];
      this.audio.setSending(false);
      useVoice.setState({ hold: null });
      this.forget(r);
      useVoice.setState((s) =>
        s.turn?.turnId === r.id ? { turn: null, player: null } : s,
      );
    }
    useVoice.setState({
      session: { ...useVoice.getState().session, status: "none" },
    });
  }

  // the resume gate's tap (9.5): the AudioContext needs a gesture on iOS
  resumeAudio(): void {
    this.audio.unlock();
    useUi.setState({ resumeGate: false });
  }

  // error invalid_request: what we sent didn't fit the schema, so that turn didn't happen (api-contract 5)
  undelivered(): void {
    if (useVoice.getState().paused) return; // under the safety card: no line (api-contract v1.0.9, B-12)
    const r = this.inflight;
    const waiting = useVoice.getState().turn?.phase === "waiting";
    if (!r && !waiting) return; // not one of our turns (an action, say): nothing to tell the player
    this.inflight = null;
    if (r) this.endTurn(r, {});
    else useVoice.setState({ turn: null, character: null });
    addNarration(copy["reconnect.lostTurn"]);
  }

  // pagehide (9.5): a held turn is let go, the character's voice stops
  suspend(): void {
    if (this.holding) this.abortHold();
    if (this.audio.playing()) this.audio.flush();
  }

  stop(): void {
    for (const r of this.recs.values()) this.clearTimers(r);
    clearTimeout(this.micTimer);
    clearTimeout(this.noteTimer);
    clearInterval(this.clipTimer);
    this.audio.setSending(false);
    if (this.audio.playing()) this.audio.flush();
    this.audio.releaseMic();
  }

  binary(buf: ArrayBuffer): void {
    const f = readVoice(buf);
    const r = this.cur;
    if (!f || !r || r.seq !== f.turnSeq || r.drop || useVoice.getState().paused)
      return; // an old turn's: dropped
    if (!r.firstVoice) {
      r.firstVoice = true;
      useVoice.setState((s) =>
        s.character?.turnId === r.id
          ? s
          : {
              character: {
                turnId: r.id,
                speaker: r.character ?? "",
                text: r.filler ?? "",
                final: false,
              },
            },
      );
    }
    this.audio.play(f.turnSeq, f.samples);
  }

  // the audio engine's events
  audible(tag: number, at: number): void {
    const r = this.cur;
    if (!r || r.seq !== tag || r.audibleAt !== undefined || r.drop) return;
    r.audibleAt = at;
    this.clearTimers(r); // the character answered: no 6 s chips, no 12 s retract
    this.setTurn(r, {
      phase: r.complete ? "done" : "speaking",
      noResponse: false,
    });
    this.position();
  }

  drained(tag: number): void {
    const r = this.cur;
    if (!r || r.seq !== tag || !r.complete || r.drop) return; // before turn_complete: a gap in the stream
    this.caption(r, true);
    this.setTurn(r, { ended: true });
    this.report(r, false);
  }

  position(): void {
    const r = this.cur;
    if (r && !r.drop) this.caption(r, false);
  }

  message(m: Api.ServerMessage): void {
    switch (m.type) {
      case "session_preparing":
        if (m.character === usePlayer.getState().focusCharacter)
          useVoice.setState({
            session: {
              character: m.character,
              status: "preparing",
              etaMs: m.etaMs,
            },
          });
        return;
      case "session_ready":
        if (m.character !== usePlayer.getState().focusCharacter) return;
        useVoice.setState({
          session: {
            character: m.character,
            status: "ready",
            voiceAvailable: m.voiceAvailable,
          },
        });
        this.sendHeldBack();
        return;
      case "turn_started":
        return this.serverTurn(m);
      case "transcript":
        return this.transcript(m);
      case "interrupted":
        return this.answered(m.turnId);
      case "turn_complete":
        return this.complete(m);
      case "suggestions":
        useVoice.setState({
          suggestions: { character: m.character, items: m.items },
        });
        return;
      case "turn_settled":
        return this.settled(m);
      case "turn_retract_result":
        return this.retracted(m);
      case "safety_pause":
        return this.pause();
      case "safety_hint":
        if (!useVoice.getState().paused) useVoice.setState({ hint: true });
        return;
      case "safety_resumed":
        return this.resumed();
      case "degraded":
        if (!useVoice.getState().degraded) {
          addNarration(copy["voice.degraded"]);
          track("degraded_shown", { reason: m.reason });
        }
        this.dropUnsent();
        if (this.holding) this.abortHold();
        useVoice.setState({ degraded: true });
        return;
      default:
        return;
    }
  }

  // —— turns ——

  private newRec(kind: Rec["kind"], seq: number, id = newTurnId()): Rec {
    const r: Rec = {
      id,
      seq,
      kind,
      character: usePlayer.getState().focusCharacter,
      firstVoice: false,
      complete: false,
      settled: false,
      noVoice: false,
      noResponse: false,
      drop: false,
      reported: false,
      caption: new Caption(),
      filler: null,
      timers: [],
    };
    this.recs.set(id, r);
    if (this.recs.size > 16) this.recs.delete(this.recs.keys().next().value!);
    // the line the safety card goes back to (frontend-design 12 step 7): the character's last one, or just the name
    const v = useVoice.getState();
    this.before = v.character
      ? { ...v.character, cut: false }
      : r.character
        ? { turnId: "", speaker: r.character, text: "", final: true }
        : null;
    this.cur = r;
    return r;
  }

  private forget(r: Rec): void {
    this.clearTimers(r);
    this.recs.delete(r.id);
    if (this.cur === r) this.cur = null;
  }

  private nextSeq(): number {
    const seq = useVoice.getState().nextTurnSeq;
    useVoice.setState({ nextTurnSeq: seq + 1 });
    return seq;
  }

  private setTurn(r: Rec, patch: Partial<Turn>): void {
    useVoice.setState((s) =>
      s.turn?.turnId === r.id ? { turn: { ...s.turn, ...patch } } : s,
    );
  }

  // the player speaks or types over whatever the character is doing: the voice stops here first, the line breaks off
  // with 「——」, and that turn is counted now, interrupted (7.7: not when its playback would have ended)
  private cutCurrent(): void {
    const p = this.cur;
    const playing = this.audio.playing();
    if (playing) this.audio.flush();
    if (!p) return;
    this.clearTimers(p);
    const speaking = playing || (p.audibleAt !== undefined && !p.complete);
    if (p.audibleAt !== undefined || playing) {
      p.drop = true;
      p.caption.stop();
      if (playing)
        useVoice.setState((s) =>
          s.character?.turnId === p.id
            ? { character: { ...s.character, cut: true } }
            : s,
        );
    }
    if (p.kind !== "server") this.report(p, speaking);
  }

  // the waiting ladder from the release (or the send): aizuchi, chips, giving up (7.8)
  private ladder(r: Rec): void {
    this.clearTimers(r);
    r.timers.push(
      setTimeout(() => this.aizuchi(r), AIZUCHI_MS),
      setTimeout(() => {
        if (this.cur !== r || r.audibleAt !== undefined || r.noVoice) return;
        r.noResponse = true;
        this.setTurn(r, { noResponse: true });
      }, NO_RESPONSE_MS),
      setTimeout(() => this.giveUp(r), GIVE_UP_MS),
    );
  }

  private aizuchi(r: Rec): void {
    if (this.cur !== r || r.firstVoice || r.drop || !r.character) return;
    if (this.turnsDone - this.lastAizuchi.turn < 2) return; // at most every other turn
    const pool =
      this.clips[r.character]?.aizuchi.filter(
        (c) => c.url !== this.lastAizuchi.url,
      ) ?? [];
    const clip = pool[Math.floor(Math.random() * pool.length)];
    if (
      !clip ||
      !this.audio.playClip(clip, { tag: r.seq, maxMs: AIZUCHI_HOLD_MS })
    )
      return;
    this.lastAizuchi = { turn: this.turnsDone, url: clip.url };
    r.filler = clip.text;
    useVoice.setState({
      character: {
        turnId: r.id,
        speaker: r.character,
        text: clip.text,
        final: false,
        source: "script",
      },
    });
  }

  // 12 s and nothing: the turn is retracted (no story time) and the character says it didn't hear (7.8)
  private giveUp(r: Rec): void {
    if (this.cur !== r || r.audibleAt !== undefined || r.settled || r.noVoice)
      return;
    r.retract = "timeout";
    if (this.wire.ready())
      this.wire.send({ type: "turn_retract", turnId: r.id });
    this.report(r, false, true);
    this.endTurn(r, {});
    const clip = r.character ? this.clips[r.character]?.unheard[0] : undefined;
    if (clip && r.character) this.sayClip(r.character, clip);
  }

  // a prerecorded line on its own (not an answer): its words follow it, segment by segment
  private sayClip(character: string, clip: Clip): void {
    if (!this.audio.playClip(clip)) return;
    const caption = new Caption();
    caption.scripted(clip.text, clip.durationMs);
    const id = `clip:${clip.url}`;
    const started = performance.now();
    const show = () => {
      const heard = performance.now() - started;
      caption.update(heard, clip.durationMs);
      useVoice.setState({
        character: {
          turnId: id,
          speaker: character,
          text: caption.shown,
          final: true,
          source: "script",
        },
      });
      if (heard >= clip.durationMs) clearInterval(this.clipTimer);
    };
    clearInterval(this.clipTimer);
    this.clipTimer = setInterval(show, 100);
    show();
  }

  // the turn leaves the stage: cancelled (struck through), redone (the character's line cut), given up
  private endTurn(r: Rec, how: { cancelled?: boolean; cut?: boolean }): void {
    this.clearTimers(r);
    r.drop = true;
    r.caption.stop();
    useVoice.setState((s) => ({
      turn: s.turn?.turnId === r.id ? null : s.turn,
      player:
        s.player?.turnId === r.id && how.cancelled
          ? { ...s.player, cancelled: true }
          : s.player,
      character:
        s.character?.turnId === r.id
          ? how.cut
            ? { ...s.character, cut: true }
            : null
          : s.character,
    }));
    if (this.cur === r) this.cur = null;
  }

  private serverTurn(m: Api.TurnStartedMessage): void {
    if (this.holding) return; // the player is talking; their turn goes first
    this.cutCurrent();
    const r = this.newRec("server", m.turnSeq, m.turnId);
    r.character = m.speaker;
    r.startAt = performance.now();
    this.audio.startTurn(m.turnSeq);
    useVoice.setState({
      turn: {
        turnId: m.turnId,
        turnSeq: m.turnSeq,
        kind: "server",
        phase: "waiting",
      },
      player: null,
      character: null,
      suggestions: null,
    });
  }

  private transcript(t: Api.TranscriptMessage): void {
    const r = this.recs.get(t.turnId);
    const current = this.cur === r && !!r;
    if (t.speaker === "player") {
      // the player's own words, live while talking (S-025); a late one for an earlier turn stays out
      if (!current && !(this.holding && this.holding.id === t.turnId)) return;
      useVoice.setState({
        player: {
          turnId: t.turnId,
          speaker: "player",
          text: t.text,
          final: t.final,
        },
      });
      return;
    }
    this.answered(t.turnId);
    if (!r || !current || r.drop) return; // came after the player moved on: not put back (7.5)
    if (t.final)
      r.caption.finish(t.text, t.source ?? "live", this.audio.queuedMs(r.seq));
    else if (t.text !== null)
      r.caption.partial(t.text, this.audio.queuedMs(r.seq));
    if (useVoice.getState().degraded && r.audibleAt === undefined) {
      // degraded: the answer comes in text only, ahead of turn_complete { audio: false } (api-contract 3.3)
      r.noVoice = true;
      this.clearTimers(r);
      this.setTurn(r, { phase: "speaking", noResponse: false });
    }
    this.caption(r, false);
    if (t.final && t.text === null)
      useVoice.setState({
        character: {
          turnId: r.id,
          speaker: t.speaker,
          text: null,
          final: true,
          source: "fallback",
        },
      });
  }

  // a typed turn got an answer of some kind: it won't need resending
  private answered(turnId: string): void {
    if (this.inflight?.id === turnId) this.inflight = null;
  }

  private complete(m: Api.TurnCompleteMessage): void {
    this.answered(m.turnId);
    const r = this.recs.get(m.turnId);
    if (!r) return;
    r.complete = true;
    r.caption.complete(this.audio.queuedMs(r.seq));
    if (this.cur !== r || r.drop) return;
    if (!m.audio) {
      r.noVoice = true;
      this.clearTimers(r);
      const answered = !!r.caption.shown || r.caption.final; // a text answer (degraded) came first
      r.noResponse = !answered;
      this.caption(r, true);
      this.setTurn(r, {
        phase: "done",
        complete: true,
        audio: false,
        ended: true,
        noResponse: !answered,
      });
      this.report(r, false, !answered);
      return;
    }
    this.setTurn(r, {
      complete: true,
      audio: true,
      phase: r.audibleAt === undefined ? "waiting" : "done",
    });
    // the final line may come up to ~3 s later; 8 s without it counts as failed (7.5)
    r.timers.push(
      setTimeout(() => {
        if (this.cur !== r || r.caption.final) return;
        r.caption.finish(null, "fallback", 0);
        useVoice.setState({
          character: {
            turnId: r.id,
            speaker: r.character ?? "",
            text: null,
            final: true,
            source: "fallback",
          },
        });
      }, CAPTION_WAIT_MS),
    );
    if (!this.audio.playing() && r.audibleAt !== undefined) this.drained(r.seq);
  }

  // the subtitles' character line from the caption: only once the voice is audible (or there is none)
  private caption(r: Rec, flush: boolean): void {
    if (r.audibleAt === undefined && !r.noVoice && !flush) return;
    const changed = flush
      ? r.caption.flush()
      : r.caption.update(this.audio.heardMs(r.seq), this.audio.queuedMs(r.seq));
    if (!changed && !(flush && r.caption.final)) return;
    const text = r.caption.shown || r.filler || "";
    useVoice.setState((s) => ({
      character: {
        turnId: r.id,
        speaker: r.character ?? s.character?.speaker ?? "",
        text:
          r.caption.final &&
          r.caption.shown === "" &&
          r.caption.source === "fallback"
            ? null
            : text,
        final: r.caption.final && (flush || r.caption.shown !== ""),
        ...(r.caption.source ? { source: r.caption.source } : {}),
      },
    }));
  }

  private settled(m: Api.TurnSettledMessage): void {
    this.answered(m.turnId);
    const r = this.recs.get(m.turnId);
    if (r) {
      r.settled = true;
      if (m.outcome !== "no_response") this.clearTimers(r);
    }
    this.turnsDone++;
    useVoice.setState((s) => {
      if (s.turn?.turnId !== m.turnId) {
        // a retracted turn's character line goes; the struck-through player line stays until the next turn
        return m.outcome === "retracted" && s.character?.turnId === m.turnId
          ? { character: null }
          : s;
      }
      // retracted: the words are gone (3.6). paused (3.12) comes with safety_pause: the card clears them in the dark,
      // so the player never sees them go
      return {
        turn: { ...s.turn, phase: "settled" },
        ...(m.outcome === "retracted" ? { player: null, character: null } : {}),
      };
    });
  }

  private retracted(m: Api.TurnRetractResultMessage): void {
    const r = this.recs.get(m.turnId);
    track("turn_retracted", {
      turnId: m.turnId,
      kind: r?.retract ?? "cancel",
      result: m.status,
    });
    // too late: the narrator's line from our own copy, no voice, the world keeps what happened (7.5). Not after our
    // own 12 s give-up: the character has already said it didn't hear, and nothing was passed on
    if (m.status === "too_late" && r?.retract !== "timeout")
      addNarration(copy["retract.tooLate"]);
  }

  // talk_turn, once per turn of the player's (data-design 9.3): when the voice ends, at the moment it is cut
  // (interrupted), or when there was no voice
  private report(r: Rec, interrupted: boolean, noResponse = false): void {
    if (r.reported || r.kind === "server" || !r.character || !r.seq) return;
    r.reported = true;
    const ms =
      r.audibleAt !== undefined && r.startAt !== undefined
        ? Math.round(r.audibleAt - r.startAt)
        : null;
    track("talk_turn", {
      turnId: r.id,
      character: r.character,
      inputMode: r.kind === "voice" ? "voice" : "text",
      interrupted,
      noResponse: noResponse || r.noResponse,
      ...(ms !== null && ms >= 0 ? { clientReleaseToAudibleMs: ms } : {}),
    });
  }

  private clearTimers(r: Rec): void {
    for (const t of r.timers) clearTimeout(t);
    r.timers = [];
  }

  // what the subtitles showed before the drop (api-contract 4)
  private restore(lt: Api.LastTurn | null): void {
    if (!lt) return;
    const v = useVoice.getState();
    if (lt.status === "lost") {
      if (v.turn?.turnId === lt.turnId || !v.turn) {
        const r = this.recs.get(lt.turnId);
        if (r) this.forget(r);
        useVoice.setState({ turn: null, character: null });
        // the character on screen says it didn't hear; otherwise a narrator's line (ux-design 12)
        const clip = lt.character
          ? this.clips[lt.character]?.unheard[0]
          : undefined;
        if (clip && lt.character && this.audio.running)
          this.sayClip(lt.character, clip);
        else addNarration(copy["reconnect.lostTurn"]);
      }
      return;
    }
    if (v.turn && v.turn.turnId !== lt.turnId) return; // we already moved on
    const speaker = lt.character ?? "narrator";
    useVoice.setState({
      turn: {
        turnId: lt.turnId,
        turnSeq: v.turn?.turnSeq ?? 0,
        kind: v.turn?.kind ?? "text",
        phase: lt.status === "settled" ? "settled" : "done",
        ended: true,
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

  // —— the safety card (frontend-design 12, ux-design 14.1) ——

  // fade: false when the card comes back after a reload or a drop (nothing is playing to fade)
  private pause(fade = true): void {
    const v = useVoice.getState();
    if (v.paused) return;
    // 1. the voice (and an aizuchi on the same bus) fades in 0.2 s, then the buffer empties; later frames go
    if (fade) this.audio.fadeOut(FADE_MS);
    const r = this.cur;
    if (r) {
      r.drop = true;
      r.caption.stop(); // 2. the line stops where it is, without 「——」
      this.clearTimers(r);
    }
    // 4. a turn being held: no more frames, nothing to send (the server drops it); the microphone goes
    if (this.holding) {
      const h = this.holding;
      this.holding = null;
      this.heldBack = [];
      this.forget(h);
    }
    // the words that set it off aren't sent again after a drop (turn_settled paused clears this too, if it came),
    // in flight or still waiting to go (api-contract v1.0.9, B-12)
    this.inflight = null;
    if (r) this.outbox = this.outbox.filter((o) => o !== r);
    this.audio.setSending(false);
    this.audio.releaseMic();
    // 6. the card: the HUD dims, then clears this turn's lines in the dark (ui/safety/SafetyCard.tsx)
    useVoice.setState({
      paused: true,
      hold: null,
      hint: false,
      helpline: null,
      suggestions: null,
      textOpen: false,
    });
  }

  // the card has dimmed the screen: this turn's words go, from the screen and from what we keep (S-057)
  clearPausedTurn(): void {
    const r = this.cur;
    if (r) this.forget(r);
    useVoice.setState({ turn: null, player: null, character: null });
  }

  // 7. 「物語に戻る」 (a tap): back to the line before this turn; the session is rebuilt after safety_resumed
  resume(): void {
    if (!useVoice.getState().paused) return;
    this.wire.send({ type: "safety_resume" });
    useVoice.setState({
      paused: false,
      character: this.before,
      player: null,
      turn: null,
    });
    if (
      useVoice.getState().mic === "granted" &&
      usePlayer.getState().focusCharacter &&
      voiceSettings.micMode === "session"
    )
      void this.audio.openMic();
  }

  private resumed(): void {
    const focus = usePlayer.getState().focusCharacter;
    if (!focus) return;
    useVoice.setState({ session: { character: focus, status: "preparing" } });
    this.wire.send({ type: "focus", character: focus });
  }
}
