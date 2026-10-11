// The voice controller on a fake audio engine and a fake wire (frontend-design 7, 12): the order of things the player
// would notice (the voice stops before the server hears of the interruption), the waiting ladder on a fake clock, the
// retract button's two meanings, corrections, the safety card's steps, and talk_turn once per turn.
import type { Api } from "@zoujin/contracts";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { usePlayer } from "../stores/player";
import { useUi } from "../stores/ui";
import { initialVoice, retractKind, useVoice } from "../stores/voice";
import { drain, peek } from "../telemetry/telemetry";
import { copy } from "../ui/copy";
import {
  AIZUCHI_MS,
  CAPTION_WAIT_MS,
  FADE_MS,
  GIVE_UP_MS,
  HOLD_BACK_MS,
  NO_RESPONSE_MS,
  STAGED_NARRATION_MS,
  VoiceController,
  type Wire,
} from "./controller";
import { FakeAudio, voiceFrame } from "./fakeAudio";

const MELOS = "char.melos";
const clip = (url: string, text: string, durationMs = 800) => ({
  url,
  text,
  durationMs,
});
const PRERECORDED = {
  aizuchi: [
    clip("/a/1.ogg", "うむ。"),
    clip("/a/2.ogg", "ああ。"),
    clip("/a/3.ogg", "……なるほど。"),
  ],
  unheard: [
    clip("/u/1.ogg", "すまない、風の音で聞こえなかった。", 2400),
    clip("/u/2.ogg", "……もう一度、頼む。"),
  ],
  wait: clip("/w.ogg", "待ってくれ。少し、考えさせてくれ。"),
  cues: {
    arrival_capped: clip("/c/arrival.ogg", "……これなら、間に合う。", 2100),
  },
};
const KNOCK: Api.SetPieceMessage = {
  type: "set_piece",
  pieceId: "piece.workshop-knock",
  lines: [
    { narration: "戸を叩いた。" },
    {
      speaker: "char.selinuntius",
      line: "もう遅い。用があるなら、明日にしてくれ。",
    },
    { narration: "それきり、石を刻む音しか聞こえなかった。" },
  ],
};

// the wire writes into the audio's log, so one list shows what happened in which order
class FakeWire implements Wire {
  sent: Api.ClientMessage[] = [];
  binary: ArrayBuffer[] = [];
  open = true;
  constructor(private readonly log: string[]) {}
  send(m: Api.ClientMessage): boolean {
    if (!this.open) return false;
    this.sent.push(m);
    this.log.push(`send:${m.type}`);
    return true;
  }
  sendBinary(b: ArrayBuffer): boolean {
    if (!this.open) return false;
    this.binary.push(b);
    return true;
  }
  ready(): boolean {
    return this.open;
  }
  types(): string[] {
    return this.sent.map((m) => m.type);
  }
  last<T extends Api.ClientMessage["type"]>(
    type: T,
  ): Extract<Api.ClientMessage, { type: T }> {
    return this.sent.filter((m) => m.type === type).at(-1) as Extract<
      Api.ClientMessage,
      { type: T }
    >;
  }
}

function setup(
  o: { mic?: "unknown" | "granted"; ready?: boolean; clips?: boolean } = {},
) {
  useVoice.setState(initialVoice());
  useUi.setState({ connection: "open", resumeGate: false });
  usePlayer.setState({ focusCharacter: MELOS });
  const audio = new FakeAudio();
  const wire = new FakeWire(audio.log);
  const v = new VoiceController(audio, wire);
  useVoice.setState({
    mic: o.mic ?? "granted",
    session: {
      character: MELOS,
      status: (o.ready ?? true) ? "ready" : "preparing",
    },
  });
  if (o.clips) v.setClips({ [MELOS]: PRERECORDED });
  v.focused(MELOS);
  return { v, audio, wire };
}

const tick = (ms: number) => vi.advanceTimersByTime(ms);
const events = (name: string) =>
  peek().filter((e) => e.name === name) as unknown as {
    props: Record<string, unknown>;
  }[];
const turnId = () => useVoice.getState().turn!.turnId;
const transcript = (
  id: string,
  text: string | null,
  final: boolean,
  speaker = MELOS,
  source?: "live" | "script" | "fallback",
): Api.TranscriptMessage => ({
  type: "transcript",
  turnId: id,
  speaker,
  text,
  final,
  ...(source ? { source } : {}),
});
const complete = (id: string, audio = true): Api.TurnCompleteMessage => ({
  type: "turn_complete",
  turnId: id,
  audio,
  metrics: { serverReleaseToFirstAudioMs: audio ? 850 : null },
});
const settled = (
  id: string,
  outcome: Api.TurnSettledMessage["outcome"] = "committed",
): Api.TurnSettledMessage => ({
  type: "turn_settled",
  turnId: id,
  outcome,
  eventIds: [],
  minutes: 10,
});

// a typed turn the character is answering aloud: sent, voice arriving, audible
function answering(v: VoiceController, audio: FakeAudio, wire: FakeWire) {
  v.say("この市の王は");
  const t = wire.last("text");
  v.message(transcript(t.turnId, "……なんだと。", false));
  v.binary(voiceFrame(t.turnSeq, 1200));
  audio.audible(t.turnSeq);
  audio.hear(t.turnSeq, 300);
  return t;
}

beforeEach(() => {
  vi.useFakeTimers({
    toFake: [
      "setTimeout",
      "clearTimeout",
      "setInterval",
      "clearInterval",
      "Date",
      "performance",
    ],
  });
  drain(1000);
});
afterEach(() => {
  vi.useRealTimers();
});

describe("a voice turn", () => {
  it("activity_start, 40 ms frames with the turnSeq, activity_end on release; the microphone stays open, muted", () => {
    const { v, audio, wire } = setup();
    expect(audio.mic).toBe(true); // opened at focus (S-073 ③), not sending
    expect(audio.sending).toBe(false);
    v.press();
    expect(wire.last("activity_start")).toMatchObject({ turnSeq: 1 });
    expect(audio.sending).toBe(true);
    expect(v.state()).toBe("listening");
    for (let i = 0; i < 3; i++) audio.micFrame();
    expect(wire.binary).toHaveLength(3);
    const head = new DataView(wire.binary[0]!);
    expect([head.getUint8(0), head.getUint32(1)]).toEqual([0x01, 1]);
    tick(600);
    v.release();
    expect(wire.last("activity_end")).toMatchObject({
      turnId: wire.last("activity_start").turnId,
      turnSeq: 1,
    });
    expect(audio.sending).toBe(false);
    expect(audio.log).not.toContain("releaseMic");
    expect(v.state()).toBe("thinking");
    audio.micFrame(); // after the release: nothing goes
    expect(wire.binary).toHaveLength(3);
  });

  it("the player's own words show live; the character's words wait for its voice", () => {
    const { v, audio } = setup();
    v.press();
    const id = turnId();
    v.message(transcript(id, "この市の", false, "player"));
    expect(useVoice.getState().player).toMatchObject({
      text: "この市の",
      final: false,
    });
    tick(800);
    v.release();
    v.message(transcript(id, "この市の王は", true, "player"));
    v.binary(voiceFrame(1, 600));
    v.message(transcript(id, "……なんだと。", false)); // after 600 ms of voice
    expect(useVoice.getState().character?.text).toBe("");
    audio.audible(1);
    expect(v.state()).toBe("speaking");
    expect(useVoice.getState().character?.text).toBe("");
    audio.hear(1, 600);
    expect(useVoice.getState().character?.text).toBe("……なんだと。");
  });

  it("talk_turn once, when the voice has played out, with the time from release to audible", () => {
    const { v, audio } = setup();
    v.press();
    const id = turnId();
    tick(1000);
    v.release();
    tick(900);
    v.binary(voiceFrame(1, 400));
    audio.audible(1);
    v.message(complete(id));
    v.message(transcript(id, "うむ。", true, MELOS, "live"));
    expect(events("talk_turn")).toHaveLength(0);
    audio.drain(1);
    expect(events("talk_turn")).toHaveLength(1);
    expect(events("talk_turn")[0]!.props).toEqual({
      turnId: id,
      character: MELOS,
      inputMode: "voice",
      interrupted: false,
      noResponse: false,
      clientReleaseToAudibleMs: 900,
    });
    expect(useVoice.getState().character).toMatchObject({
      text: "うむ。",
      final: true,
    });
    expect(v.state()).toBe("idle");
    v.message(settled(id));
    v.press(); // the next turn doesn't count this one again
    expect(events("talk_turn")).toHaveLength(1);
  });
});

describe("interrupting (frontend-design 7.4)", () => {
  it("the voice stops here before activity_start goes out, the line breaks with 「——」, counted as interrupted", () => {
    const { v, audio, wire } = setup();
    const t = answering(v, audio, wire);
    expect(audio.playing()).toBe(true);
    v.press();
    const flush = audio.log.indexOf("flush");
    const start = audio.log.lastIndexOf("send:activity_start");
    expect(flush).toBeGreaterThan(-1);
    expect(flush).toBeLessThan(start);
    expect(useVoice.getState().character).toMatchObject({
      turnId: t.turnId,
      text: "……なんだと。",
      cut: true,
    });
    expect(events("talk_turn")[0]!.props).toMatchObject({
      turnId: t.turnId,
      inputMode: "text",
      interrupted: true,
    });
    // what the old turn still sends is dropped
    const before = audio.queuedMs(t.turnSeq);
    v.binary(voiceFrame(t.turnSeq, 400));
    expect(audio.queuedMs(t.turnSeq)).toBe(before);
    v.message(transcript(t.turnId, "……なんだと。そんな王を", false));
    expect(useVoice.getState().character?.text).toBe("……なんだと。");
  });

  it("typing over the character interrupts the same way", () => {
    const { v, audio, wire } = setup();
    answering(v, audio, wire);
    v.say("待って");
    expect(audio.log.indexOf("flush")).toBeLessThan(
      audio.log.lastIndexOf("send:text"),
    );
    expect(events("talk_turn")[0]!.props).toMatchObject({ interrupted: true });
  });
});

describe("before the session is ready (frontend-design 7.1)", () => {
  it("up to 2 s of frames wait with activity_end, then go in order; past 2 s the key says 準備中", () => {
    const { v, audio, wire } = setup({ ready: false });
    v.press();
    expect(wire.types()).toEqual(["activity_start"]);
    const frames = HOLD_BACK_MS / 40 + 10;
    for (let i = 0; i < frames; i++) audio.micFrame();
    expect(wire.binary).toHaveLength(0);
    expect(useVoice.getState().hold?.preparing).toBe(true);
    tick(3000);
    v.release();
    expect(wire.types()).toEqual(["activity_start"]);
    v.message({
      type: "session_ready",
      character: MELOS,
      voiceAvailable: true,
    });
    expect(wire.binary).toHaveLength(HOLD_BACK_MS / 40);
    expect(wire.types()).toEqual(["activity_start", "activity_end"]);
  });
});

describe("the key's gestures (ux-design 7.1)", () => {
  it("a press under 250 ms is a slip: turn_retract, the note, no line, no talk_turn", () => {
    const { v, wire } = setup();
    v.press();
    const id = turnId();
    tick(120);
    v.release();
    expect(wire.last("turn_retract")).toMatchObject({ turnId: id });
    expect(useVoice.getState()).toMatchObject({
      note: "tooShort",
      turn: null,
      player: null,
    });
    tick(2000);
    expect(useVoice.getState().note).toBeNull();
    expect(events("talk_turn")).toHaveLength(0);
  });

  it("sliding up and letting go cancels: turn_retract, the words struck through", () => {
    const { v, wire } = setup();
    v.press();
    const id = turnId();
    v.message(transcript(id, "あの", false, "player"));
    tick(600);
    v.slide(true);
    expect(useVoice.getState().hold?.slide).toBe(true);
    v.release();
    expect(wire.types()).toEqual(["activity_start", "turn_retract"]);
    expect(useVoice.getState().player).toMatchObject({ cancelled: true });
    expect(useVoice.getState().turn).toBeNull();
  });
});

describe("the waiting ladder (frontend-design 7.8)", () => {
  it("an aizuchi at 0.7 s that the live voice waits behind, the chips at 6 s, at 12 s retracted with the didn't-hear line", () => {
    const { v, audio, wire } = setup({ clips: true });
    v.say("この市の王は");
    const id = turnId();
    tick(AIZUCHI_MS);
    expect(audio.log.some((l) => /^clip:\/a\/\d\.ogg:hold$/.test(l))).toBe(
      true,
    );
    expect(useVoice.getState().character).toMatchObject({ source: "script" });
    tick(NO_RESPONSE_MS - AIZUCHI_MS);
    expect(v.state()).toBe("no-response");
    tick(GIVE_UP_MS - NO_RESPONSE_MS);
    expect(wire.last("turn_retract")).toMatchObject({ turnId: id });
    expect(audio.log).toContain("clip:/u/1.ogg");
    expect(events("talk_turn")[0]!.props).toMatchObject({ noResponse: true });
    expect(useVoice.getState().character?.speaker).toBe(MELOS);
  });

  it("an answer before 6 s stops the ladder", () => {
    const { v, audio, wire } = setup();
    v.say("こんにちは");
    const t = wire.last("text");
    tick(2000);
    v.binary(voiceFrame(t.turnSeq, 400));
    audio.audible(t.turnSeq);
    tick(GIVE_UP_MS);
    expect(v.state()).toBe("speaking");
    expect(wire.types()).not.toContain("turn_retract");
  });

  it("no aizuchi two turns running", () => {
    const { v, audio } = setup({ clips: true });
    v.say("一");
    tick(AIZUCHI_MS);
    v.message(settled(turnId()));
    v.say("二");
    tick(AIZUCHI_MS);
    expect(audio.log.filter((l) => l.startsWith("clip:/a/"))).toHaveLength(1);
  });
});

describe("turn_complete (frontend-design 7.5, 7.6)", () => {
  it("no voice and no words: no-response at once", () => {
    const { v, wire } = setup();
    v.say("……");
    v.message(complete(wire.last("text").turnId, false));
    expect(v.state()).toBe("no-response");
    expect(events("talk_turn")[0]!.props).toMatchObject({ noResponse: true });
    v.again();
    expect(v.state()).toBe("idle");
  });

  it("no final line 8 s after turn_complete: shown as failed", () => {
    const { v, audio, wire } = setup();
    const t = answering(v, audio, wire);
    v.message(complete(t.turnId));
    tick(CAPTION_WAIT_MS);
    expect(useVoice.getState().character).toMatchObject({
      text: null,
      final: true,
    });
  });
});

describe("retracting (frontend-design 7.5)", () => {
  it("取り消す before the character speaks: turn_retract, the line struck through", () => {
    const { v, wire } = setup();
    v.say("やっぱり");
    expect(retractKind(useVoice.getState().turn)).toBe("cancel");
    v.retract();
    expect(wire.last("turn_retract")).toMatchObject({
      turnId: wire.last("text").turnId,
    });
    expect(useVoice.getState().player).toMatchObject({ cancelled: true });
    v.message({
      type: "turn_retract_result",
      turnId: wire.last("text").turnId,
      status: "retracted",
    });
    expect(events("turn_retracted")[0]!.props).toMatchObject({
      kind: "cancel",
      result: "retracted",
    });
  });

  it("言い直す after turn_complete; too late says so in the narrator's words", () => {
    const { v, audio, wire } = setup();
    const t = answering(v, audio, wire);
    expect(retractKind(useVoice.getState().turn)).toBeNull(); // speaking, not complete
    v.message(complete(t.turnId));
    expect(retractKind(useVoice.getState().turn)).toBe("redo");
    v.retract();
    expect(audio.log).toContain("flush");
    expect(useVoice.getState().character).toMatchObject({ cut: true });
    v.message({
      type: "turn_retract_result",
      turnId: t.turnId,
      status: "too_late",
    });
    expect(useVoice.getState().narration).toContain(copy["retract.tooLate"]);
    expect(events("turn_retracted")[0]!.props).toMatchObject({
      kind: "redo",
      result: "too_late",
    });
  });

  it("a correction within the window retracts the turn and sends the text in its place; after it, a new turn", () => {
    const { v, audio, wire } = setup();
    v.press();
    const id = turnId();
    tick(800);
    v.release();
    v.message(transcript(id, "おうのこと", true, "player"));
    v.correct("王のこと", id);
    expect(wire.types().slice(-2)).toEqual(["turn_retract", "text"]);
    expect(wire.last("text")).toMatchObject({
      text: "王のこと",
      via: "correction",
      replaces: id,
    });
    expect(events("transcript_corrected")[0]!.props).toEqual({ turnId: id });

    const next = wire.last("text").turnId;
    v.binary(voiceFrame(wire.last("text").turnSeq, 200));
    audio.audible(wire.last("text").turnSeq);
    v.message(settled(next));
    v.correct("王様のこと", next);
    expect(wire.last("text")).toMatchObject({ via: "typed" });
    expect(wire.last("text")).not.toHaveProperty("replaces");
  });
});

describe("the safety card (frontend-design 12)", () => {
  it("the voice fades in 0.2 s, a held turn goes, the microphone goes; back to the line before on 物語に戻る", () => {
    const { v, audio, wire } = setup();
    useVoice.setState({
      character: {
        turnId: "turn_before",
        speaker: MELOS,
        text: "前の一言。",
        final: true,
      },
    });
    const t = answering(v, audio, wire);
    v.press(); // talking over it when the pause comes
    v.message({ type: "safety_pause" });
    expect(audio.log).toContain(`fadeOut:${FADE_MS}`);
    expect(audio.sending).toBe(false);
    expect(audio.mic).toBe(false);
    expect(useVoice.getState()).toMatchObject({ paused: true, hold: null });
    expect(v.state()).toBe("paused");
    audio.micFrame();
    expect(wire.binary).toHaveLength(0);
    v.binary(voiceFrame(t.turnSeq, 200)); // late voice: dropped
    v.press(); // the key does nothing behind the card
    expect(wire.types().filter((x) => x === "activity_start")).toHaveLength(1);

    v.clearPausedTurn(); // the card has dimmed the screen
    expect(useVoice.getState()).toMatchObject({
      turn: null,
      player: null,
      character: null,
    });
    v.resume();
    expect(wire.last("safety_resume")).toEqual({ type: "safety_resume" });
    // the line before the paused turn: the answer the player spoke over, without its 「——」
    expect(useVoice.getState().character).toMatchObject({
      turnId: t.turnId,
      text: "……なんだと。",
      cut: false,
    });
    v.message({ type: "safety_resumed" });
    expect(wire.last("focus")).toEqual({ type: "focus", character: MELOS });
    expect(useVoice.getState().session.status).toBe("preparing");
    expect(audio.log.filter((l) => l === "openMic").length).toBeGreaterThan(1);
  });

  it("returns to the character's last line, or just the name", () => {
    const { v, wire } = setup();
    useVoice.setState({
      character: {
        turnId: "turn_before",
        speaker: MELOS,
        text: "前の一言。",
        final: true,
      },
    });
    v.say("……");
    // turn_settled paused comes first (api-contract 3.12): the words stay until the screen is dark
    v.message(settled(wire.last("text").turnId, "paused"));
    v.message({ type: "safety_pause" });
    expect(useVoice.getState().player?.text).toBe("……");
    v.clearPausedTurn();
    v.resume();
    expect(useVoice.getState().character).toMatchObject({
      text: "前の一言。",
      cut: false,
    });
    expect(wire.types()).toContain("safety_resume");
  });

  it("safety_hint shows the note, not over the card", () => {
    const { v } = setup();
    v.message({ type: "safety_hint" });
    expect(useVoice.getState().hint).toBe(true);
    v.message({ type: "safety_pause" });
    expect(useVoice.getState()).toMatchObject({ hint: false, paused: true });
    v.message({ type: "safety_hint" });
    expect(useVoice.getState().hint).toBe(false);
  });
});

describe("the microphone (ux-design 7.3, 12)", () => {
  it("the first press opens the primer; refused there shows the denied sheet", async () => {
    const { v, audio, wire } = setup({ mic: "unknown" });
    expect(audio.mic).toBe(false); // not asked yet: not taken at focus
    v.press();
    expect(useVoice.getState().sheet).toBe("primer");
    expect(wire.types()).toEqual([]);
    audio.micResult = {
      ok: false,
      result: "denied",
      reason: "NotAllowedError",
    };
    v.primer("mic");
    await vi.runAllTicks();
    await Promise.resolve();
    expect(useVoice.getState()).toMatchObject({
      mic: "denied",
      sheet: "denied",
    });
    expect(v.state()).toBe("denied");
    expect(events("mic_permission")[0]!.props).toEqual({
      result: "denied",
      reason: "NotAllowedError",
      afterPrimer: true,
    });
    v.continueInText();
    expect(useVoice.getState()).toMatchObject({ sheet: null, textOpen: true });
  });

  it("allowed in the primer: ready once, the key works", async () => {
    const { v, audio } = setup({ mic: "unknown" });
    v.press();
    v.primer("mic");
    await Promise.resolve();
    expect(useVoice.getState()).toMatchObject({
      mic: "granted",
      sheet: null,
      micReady: true,
    });
    expect(events("mic_permission")[0]!.props).toEqual({
      result: "granted",
      afterPrimer: true,
    });
    expect(audio.mic).toBe(true);
    v.press();
    expect(useVoice.getState().micReady).toBe(false);
    expect(v.state()).toBe("listening");
  });

  it("文字で話す in the primer: text from now on", () => {
    const { v } = setup({ mic: "unknown" });
    v.press();
    v.primer("text");
    expect(useVoice.getState()).toMatchObject({
      mic: "text",
      sheet: null,
      textOpen: true,
    });
  });

  it("let go 2 minutes after the conversation ends", () => {
    const { v, audio } = setup();
    v.unfocused();
    tick(119_000);
    expect(audio.mic).toBe(true);
    tick(1000);
    expect(audio.mic).toBe(false);
  });
});

describe("the connection", () => {
  it("a drop ends a held turn; after the welcome turnSeq starts from 1 and an old turn's voice is dropped", () => {
    const { v, audio, wire } = setup();
    v.say("一");
    v.say("二");
    expect(wire.last("text").turnSeq).toBe(2);
    v.message(settled(wire.last("text").turnId));
    v.press();
    v.down();
    expect(useVoice.getState()).toMatchObject({ hold: null, turn: null });
    expect(audio.sending).toBe(false);
    v.connected(null);
    v.say("三");
    expect(wire.last("text").turnSeq).toBe(1);
    v.binary(voiceFrame(2, 200)); // the old connection's turn 2
    expect(audio.queuedMs(2)).toBe(0);
  });

  it("typed while down goes after the welcome", () => {
    const { v, wire } = setup();
    wire.open = false;
    v.say("届くまで待つ");
    expect(wire.sent).toHaveLength(0);
    wire.open = true;
    v.connected(null);
    expect(wire.last("text")).toMatchObject({
      text: "届くまで待つ",
      turnSeq: 1,
    });
  });

  it("a voice turn the server never got is lost after the welcome: the didn't-hear line once, nothing at 12 s", () => {
    const { v, audio, wire } = setup({ clips: true });
    v.press();
    tick(600);
    v.release(); // the line was already down: activity_start never reached the server
    v.down();
    v.connected(null);
    expect(useVoice.getState().turn).toBeNull();
    expect(audio.log.filter((l) => l === "clip:/u/1.ogg")).toHaveLength(1);
    const before = wire.sent.length;
    tick(GIVE_UP_MS);
    expect(wire.sent).toHaveLength(before); // no turn_retract, so no too_late either
    expect(useVoice.getState().narration).toEqual([]);
  });

  it("a safety pause the server still holds comes back as the card, without a fade; the words aren't sent again", () => {
    const { v, audio, wire } = setup();
    v.say("もう疲れた");
    v.down();
    v.connected(null, { safetyPause: true });
    expect(v.state()).toBe("paused");
    expect(audio.log).not.toContain(`fadeOut:${FADE_MS}`);
    expect(audio.mic).toBe(false);
    expect(wire.sent.filter((m) => m.type === "text")).toHaveLength(1);
  });

  it("too_late for our own 12 s give-up adds no narrator line (the character already said it didn't hear)", () => {
    const { v, wire } = setup({ clips: true });
    v.say("聞こえますか");
    const id = turnId();
    tick(GIVE_UP_MS);
    expect(wire.last("turn_retract")).toMatchObject({ turnId: id });
    v.message({ type: "turn_retract_result", turnId: id, status: "too_late" });
    expect(useVoice.getState().narration).toEqual([]);
  });

  it("degraded: the narrator says so once, degraded_shown, a held turn ends", () => {
    const { v, wire } = setup();
    v.press();
    tick(500);
    v.message({ type: "degraded", voice: false, reason: "budget" });
    v.message({ type: "degraded", voice: false, reason: "budget" });
    expect(useVoice.getState().narration).toEqual([copy["voice.degraded"]]);
    expect(events("degraded_shown")).toHaveLength(1);
    expect(useVoice.getState().hold).toBeNull();
    expect(wire.types()).toContain("activity_end");
    expect(v.state()).toBe("degraded");
  });
});

describe("fixed lines the server stages (api-contract 3.4, 3.14)", () => {
  const knockVoice = clip(
    "/p/knock-2.m4a",
    "もう遅い。用があるなら、明日にしてくれ。",
    3000,
  );

  it("a set piece in order: the narrator's line, then the character's recording with its words, then the next", () => {
    const { v, audio } = setup();
    v.setClips({}, { "piece.workshop-knock/2": knockVoice });
    v.setPiece(KNOCK);
    expect(useVoice.getState().narration).toEqual(["戸を叩いた。"]);
    expect(audio.log).not.toContain("clip:/p/knock-2.m4a");
    tick(STAGED_NARRATION_MS);
    expect(audio.log).toContain("clip:/p/knock-2.m4a");
    expect(useVoice.getState().character).toMatchObject({
      speaker: "char.selinuntius",
      source: "script",
    });
    tick(1000);
    expect(useVoice.getState().character?.text).toBe("もう遅い。");
    tick(1900);
    expect(useVoice.getState().narration).toHaveLength(1); // the next line waits for the voice
    tick(100);
    expect(useVoice.getState().character?.text).toBe(
      "もう遅い。用があるなら、明日にしてくれ。",
    );
    expect(useVoice.getState().narration).toEqual([
      "戸を叩いた。",
      "それきり、石を刻む音しか聞こえなかった。",
    ]);
  });

  it("no recording: the words alone at reading pace", () => {
    const { v, audio } = setup();
    v.setPiece(KNOCK);
    tick(STAGED_NARRATION_MS);
    expect(audio.log.filter((l) => l.startsWith("clip:"))).toHaveLength(0);
    expect(useVoice.getState().character?.text).toBe("");
    tick(20_000);
    expect(useVoice.getState().character?.text).toBe(
      "もう遅い。用があるなら、明日にしてくれ。",
    );
    expect(useVoice.getState().narration).toHaveLength(2);
  });

  it("waits for the character's voice now playing to end", () => {
    const { v, audio, wire } = setup();
    const t = answering(v, audio, wire);
    v.setPiece(KNOCK);
    tick(5000);
    expect(useVoice.getState().narration).toEqual([]);
    v.message(complete(t.turnId));
    audio.drain(t.turnSeq);
    tick(100);
    expect(useVoice.getState().narration).toEqual(["戸を叩いた。"]);
  });

  it("the cue: his own recording when he is here, the narrator's line when he isn't", () => {
    const { v, audio } = setup({ clips: true });
    v.cue({
      kind: "arrival_capped",
      speaker: MELOS,
      text: "……これなら、間に合う。",
    });
    expect(audio.log).toContain("clip:/c/arrival.ogg");
    expect(useVoice.getState().character).toMatchObject({ speaker: MELOS });
    tick(2100);
    v.cue({
      kind: "arrival_capped",
      speaker: null,
      text: "この足なら、陽の沈む前に着く。",
    });
    expect(useVoice.getState().narration).toEqual([
      "この足なら、陽の沈む前に着く。",
    ]);
  });

  it("the player speaks over it: the voice stops, the line shows whole, the narrator's lines left go in at once", () => {
    const { v, audio } = setup();
    v.setClips({}, { "piece.workshop-knock/2": knockVoice });
    v.setPiece(KNOCK);
    tick(STAGED_NARRATION_MS + 500);
    v.say("あの");
    expect(useVoice.getState().narration).toEqual([
      "戸を叩いた。",
      "それきり、石を刻む音しか聞こえなかった。",
    ]);
    tick(STAGED_NARRATION_MS * 3);
    expect(useVoice.getState().narration).toHaveLength(2);
    expect(audio.log.filter((l) => l === "clip:/p/knock-2.m4a")).toHaveLength(
      1,
    );
  });
});

describe("the act end's spoken plan", () => {
  it("no character: activity_start with purpose act_plan, the frames go at once, activity_end gives the turn's id", () => {
    const { v, audio, wire } = setup({ ready: false });
    usePlayer.setState({ focusCharacter: null });
    expect(v.planPress()).toBe(true);
    const start = wire.last("activity_start");
    expect(start).toMatchObject({ purpose: "act_plan" });
    expect(audio.sending).toBe(true);
    for (let i = 0; i < 3; i++) audio.micFrame();
    expect(wire.binary).toHaveLength(3); // no session_ready to wait for
    tick(800);
    expect(v.planRelease()).toBe(start.turnId);
    expect(wire.last("activity_end")).toMatchObject({ turnId: start.turnId });
    expect(audio.sending).toBe(false);
    // nothing waits for a character's answer
    tick(15_000);
    expect(useVoice.getState().turn).toBeNull();
  });

  it("a slip under 250 ms is no try: retracted, no id", () => {
    const { v, wire } = setup();
    v.planPress();
    const id = wire.last("activity_start").turnId;
    tick(100);
    expect(v.planRelease()).toBeNull();
    expect(wire.last("turn_retract")).toMatchObject({ turnId: id });
  });
});
