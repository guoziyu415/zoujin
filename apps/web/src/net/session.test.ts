import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useUi } from "../stores/ui";
import { useVoice } from "../stores/voice";
import { useWorld } from "../stores/world";
import { usePlayer } from "../stores/player";
import { peek, drain } from "../telemetry/telemetry";
import { FakeAudio, voiceFrame } from "../voice/fakeAudio";
import { Session } from "./session";
import { commit, event, FakeSocket, PID, snapshot, welcome } from "./testkit";
import { useStory } from "../stores/story";
import { openPropose } from "./story";

function open(lastSeq = 0) {
  const onEnded = vi.fn();
  const audio = new FakeAudio();
  const s = new Session(PID, { onEnded }, "ws://test/live", FakeSocket, audio);
  s.setNames({ "char.melos": "メロス", "char.old-man": "市の老爺" });
  s.start(snapshot({ lastSeq }));
  const sock = FakeSocket.last();
  sock.open();
  sock.receive(welcome(lastSeq));
  return { s, sock, onEnded, audio };
}

const texts = (sock: FakeSocket) => sock.sent.filter((m) => m.type === "text");

beforeEach(() => {
  vi.useFakeTimers();
  FakeSocket.all = [];
  drain(500);
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("Session", () => {
  it("opens on welcome and numbers the turns from 1 on each connection", () => {
    const { s, sock } = open();
    expect(useUi.getState().connection).toBe("open");
    s.focus("char.melos");
    s.say("こんにちは");
    s.say("王のこと");
    expect(texts(sock).map((m) => m.turnSeq)).toEqual([1, 2]);
    expect(texts(sock)[0]).toMatchObject({ text: "こんにちは", via: "typed" });
    expect(String(texts(sock)[0]!.turnId)).toMatch(
      /^turn_[0-7][0-9A-HJKMNP-TV-Z]{25}$/,
    );

    sock.drop();
    expect(useUi.getState().connection).toBe("reconnecting");
    vi.advanceTimersByTime(1000);
    const again = FakeSocket.last();
    again.open();
    again.receive(welcome(0, { lastTurn: lastTurnOf(texts(sock)[1]!) }));
    s.say("つづき");
    expect(texts(again).map((m) => m.turnSeq)).toEqual([1]);
    // focus again after reconnecting (api-contract 4)
    expect(again.types()).toEqual(["hello", "focus", "text"]);
    expect(
      peek()
        .map((e) => e.name)
        .filter((n) => n.startsWith("connection")),
    ).toEqual(["connection_lost", "connection_restored"]);
    // each turn the next one cut short is counted once, when it was cut (7.7)
    expect(peek().filter((e) => e.name === "talk_turn")).toHaveLength(2);
  });

  it("sends what was typed while down after the welcome, and again what the server never saw", () => {
    const { s, sock } = open();
    s.focus("char.melos");
    s.say("届かなかった"); // the socket was already dead: never reached the server
    sock.drop();
    s.say("切れている間に");
    expect(texts(sock)).toHaveLength(1);
    vi.advanceTimersByTime(1000);
    const again = FakeSocket.last();
    again.open();
    again.receive(welcome(0, { lastTurn: null }));
    expect(texts(again).map((m) => [m.text, m.turnSeq])).toEqual([
      ["届かなかった", 1],
      ["切れている間に", 2],
    ]);
    expect(texts(again)[0]!.turnId).toBe(texts(sock)[0]!.turnId);
  });

  it("doesn't send a turn again when the server has it", () => {
    const { s, sock } = open();
    s.focus("char.melos");
    s.say("届いた");
    sock.drop();
    vi.advanceTimersByTime(1000);
    const again = FakeSocket.last();
    again.open();
    again.receive(
      welcome(0, {
        lastTurn: { ...lastTurnOf(texts(sock)[0]!), status: "pending" },
      }),
    );
    expect(texts(again)).toHaveLength(0);
    expect(useVoice.getState().player?.text).toBe("届いた");
  });

  it("shows a typed turn: the player's line, the character's words with the voice, then settled", () => {
    const { s, sock, audio } = open();
    s.focus("char.melos");
    sock.receive({
      type: "session_preparing",
      character: "char.melos",
      reason: "switch",
      etaMs: 800,
    });
    expect(useVoice.getState().session.status).toBe("preparing");
    sock.receive({
      type: "session_ready",
      character: "char.melos",
      voiceAvailable: true,
    });
    expect(useVoice.getState().session.status).toBe("ready");
    s.say("この市の王は");
    const turnId = String(texts(sock)[0]!.turnId);
    expect(useVoice.getState().turn).toMatchObject({
      turnId,
      phase: "waiting",
    });
    sock.receive({
      type: "transcript",
      turnId,
      speaker: "char.melos",
      text: "……なんだと。",
      final: false,
    });
    // the words wait for the voice (frontend-design 7.5)
    expect(useVoice.getState().turn?.phase).toBe("waiting");
    expect(useVoice.getState().character).toBeNull();
    sock.receiveBinary(voiceFrame(1, 400));
    audio.audible(1);
    expect(useVoice.getState().turn?.phase).toBe("speaking");
    sock.receive({
      type: "turn_complete",
      turnId,
      audio: true,
      metrics: { serverReleaseToFirstAudioMs: 850 },
    });
    sock.receive({
      type: "transcript",
      turnId,
      speaker: "char.melos",
      text: "許しておけるものか。",
      final: true,
      source: "live",
    });
    audio.drain(1);
    sock.receive({
      type: "suggestions",
      turnId,
      character: "char.melos",
      items: [{ text: "どうするつもりですか", kind: "ask" }],
    });
    sock.receive({
      type: "turn_settled",
      turnId,
      outcome: "committed",
      eventIds: [],
      minutes: 10,
    });
    const v = useVoice.getState();
    expect(v.player).toMatchObject({ speaker: "player", text: "この市の王は" });
    expect(v.character).toMatchObject({
      speaker: "char.melos",
      text: "許しておけるものか。",
      source: "live",
    });
    expect(v.turn?.phase).toBe("settled");
    expect(v.suggestions?.items).toHaveLength(1);
  });

  it("applies a commit once: clock, events, narration and the light reactions; a resent one changes nothing", () => {
    const { sock } = open(2);
    const e = event({
      type: "action",
      actor: "char.old-man",
      forPlayer: true,
      summary: "老爺が道を教えてくれた",
    });
    const c = commit(3, 3, {
      events: [e],
      patch: { clock: { t: 1080, tLabel: "約束の日・夕方" } },
      memories: [
        {
          character: "char.melos",
          change: "added",
          memoryId: "mem_01JAAAAAAAAAAAAAAAAAAAAAAA",
          text: "王のことを教えてくれた旅の人",
          kind: "impression",
          relationLabel: "様子を見ている",
          relationLevel: 3,
        },
      ],
      narration: ["広場に、夕暮れの風が吹いた。"],
    });
    sock.receive(c);
    const w = useWorld.getState().world!;
    expect(w.lastSeq).toBe(3);
    expect(w.clock.t).toBe(1080);
    expect(w.events).toHaveLength(1);
    expect(useVoice.getState().narration).toEqual([
      "広場に、夕暮れの風が吹いた。",
    ]);
    expect(useUi.getState().toasts.map((t) => [t.head, t.body])).toEqual([
      ["メロスは覚えた", "王のことを教えてくれた旅の人"],
      ["市の老爺が、あなたのために動いた", "老爺が道を教えてくれた"],
    ]);
    // resent after a reconnect
    useUi.setState({ toasts: [] });
    sock.receive(c);
    expect(useWorld.getState().world!.events).toHaveLength(1);
    expect(useVoice.getState().narration).toHaveLength(1);
    expect(useUi.getState().toasts).toEqual([]);
  });

  it("a commit's cue plays once (a resent commit doesn't again); set_piece lines go to the voice", () => {
    const { sock } = open(2);
    const c = commit(3, 3, {
      cue: {
        kind: "arrival_capped",
        speaker: null,
        text: "この足なら、陽の沈む前に着く。",
      },
    });
    sock.receive(c);
    sock.receive(c);
    expect(useVoice.getState().narration).toEqual([
      "この足なら、陽の沈む前に着く。",
    ]);
    vi.advanceTimersByTime(5000);
    sock.receive({
      type: "set_piece",
      pieceId: "piece.workshop-knock",
      lines: [{ narration: "戸は閉ざされたままだ。" }],
    });
    expect(useVoice.getState().narration).toEqual([
      "この足なら、陽の沈む前に着く。",
      "戸は閉ざされたままだ。",
    ]);
  });

  it("fills a gap from /events and the snapshot, then applies what came meanwhile", async () => {
    const { sock } = open(2);
    const missing = [event({ seq: 3 }), event({ seq: 4 })];
    const fetch = vi.fn(async (url: string) => {
      if (url.includes("/events?afterSeq=2"))
        return new Response(JSON.stringify({ events: missing, lastSeq: 4 }), {
          status: 200,
        });
      if (url.endsWith("/snapshot"))
        return new Response(
          JSON.stringify(
            snapshot({
              lastSeq: 4,
              clock: { t: 1100, tLabel: "約束の日・夕方", deadlineT: 5460 },
            }),
          ),
          {
            status: 200,
          },
        );
      return new Response("{}", { status: 404 });
    });
    vi.stubGlobal("fetch", fetch);
    sock.receive(commit(5, 5, { narration: ["五番目"] }));
    await vi.waitFor(() => expect(useWorld.getState().world!.lastSeq).toBe(5));
    const w = useWorld.getState().world!;
    expect(w.clock.t).toBe(1100);
    expect(w.events.map((e) => e.seq)).toEqual([3, 4]);
    expect(useVoice.getState().narration).toEqual(["五番目"]);
    expect(fetch.mock.calls.map((c) => c[0])).toEqual([
      `/v1/playthroughs/${PID}/events?afterSeq=2&limit=50`,
      `/v1/playthroughs/${PID}/snapshot`,
    ]);
  });

  it("ignores and counts message types it doesn't know", () => {
    const { s, sock } = open();
    const debug = vi.spyOn(console, "debug").mockImplementation(() => {});
    sock.receive({ type: "future_feature", detail: "新しい種類のメッセージ" });
    sock.receive({ type: "future_feature" });
    sock.receive({ type: "narration", line: "広場に、夕暮れの風が吹いた。" });
    expect(s.unknown.get("future_feature")).toBe(2);
    expect(debug).toHaveBeenCalledTimes(1);
    expect(useVoice.getState().narration).toEqual([
      "広場に、夕暮れの風が吹いた。",
    ]);
  });

  it("an invalid_request with no turn of ours in flight says nothing", () => {
    const { sock } = open();
    sock.receive({
      type: "error",
      error: {
        code: "invalid_request",
        message: "うまく送れませんでした。",
        retryable: false,
        retryAfterSeconds: null,
      },
    });
    expect(useVoice.getState().narration).toEqual([]);
  });

  it("says the lost turn again on welcome, and treats invalid_request as not delivered", () => {
    const { s, sock } = open();
    s.focus("char.melos");
    s.say("聞こえますか");
    const turnId = String(texts(sock)[0]!.turnId);
    sock.receive({
      type: "error",
      error: {
        code: "invalid_request",
        message: "うまく送れませんでした。",
        retryable: false,
        retryAfterSeconds: null,
      },
    });
    expect(useVoice.getState().turn).toBeNull();
    expect(useVoice.getState().narration).toEqual([
      "もう一度、話しかけてください。",
    ]);
    sock.drop();
    vi.advanceTimersByTime(1000);
    const again = FakeSocket.last();
    again.open();
    again.receive(
      welcome(0, {
        lastTurn: {
          turnId,
          character: "char.melos",
          status: "lost",
          playerText: null,
          characterText: null,
        },
      }),
    );
    expect(useVoice.getState().narration).toEqual([
      "もう一度、話しかけてください。",
      "もう一度、話しかけてください。",
    ]);
    expect(texts(again)).toHaveLength(0);
  });

  it("hands 4001 and 4009 to the screen", () => {
    const { sock, onEnded } = open();
    sock.drop(4009);
    expect(useUi.getState().connection).toBe("taken");
    expect(onEnded).toHaveBeenCalledWith("taken");
    const second = open();
    second.sock.drop(4001);
    expect(second.onEnded).toHaveBeenCalledWith("unauthenticated");
  });

  it("focus goes out at once and survives a reconnect; unfocus clears it", () => {
    const { s, sock } = open();
    s.focus("char.old-man");
    expect(sock.sent.at(-1)).toEqual({
      type: "focus",
      character: "char.old-man",
    });
    expect(usePlayer.getState().focusCharacter).toBe("char.old-man");
    s.unfocus();
    expect(sock.sent.at(-1)).toEqual({ type: "unfocus", reason: "menu" });
    expect(usePlayer.getState().focusCharacter).toBeNull();
  });
});

function lastTurnOf(m: Record<string, unknown>) {
  return {
    turnId: String(m.turnId),
    character: "char.melos",
    status: "settled" as const,
    playerText: String(m.text),
    characterText: null,
  };
}

describe("the act end's plan said aloud (api-contract 3.11)", () => {
  it("held and let go: activity_start purpose act_plan, the page waits for that turn, the result ends it", () => {
    const { s, sock, audio } = open();
    useVoice.setState({ mic: "granted" });
    sock.receive({
      type: "act_ended",
      actId: "act.1",
      recapLines: [],
      options: [],
      freeform: { allowed: true, triesLeft: 2 },
    });
    useStory.setState({
      actEnd: openPropose(useStory.getState().actEnd!),
    });
    s.actPlanPress();
    const start = sock.sent.at(-1)!;
    expect(start).toMatchObject({
      type: "activity_start",
      purpose: "act_plan",
    });
    for (let i = 0; i < 10; i++) audio.micFrame();
    vi.advanceTimersByTime(800);
    s.actPlanRelease();
    expect(sock.sent.at(-1)).toMatchObject({ type: "activity_end" });
    expect(useStory.getState().actEnd!.phase).toEqual({
      k: "thinking",
      turnId: start.turnId,
    });
    sock.receive({
      type: "act_plan_result",
      turnId: String(start.turnId),
      accepted: false,
      narration: ["声が届かなかったようです。もう一度、聞かせてください。"],
      triesLeft: 2,
    });
    expect(useVoice.getState().turn).toBeNull();
    expect(useStory.getState().actEnd!.phase.k).not.toBe("thinking");
  });
});
