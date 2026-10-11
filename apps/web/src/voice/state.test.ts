// One test per row of frontend-design 7.6 (and the rows the HUD adds): which state wins when several facts hold.
import { describe, expect, it } from "vitest";
import type { Turn } from "../stores/voice";
import { canPress, voiceState, type Facts } from "./state";

const base: Facts = {
  connection: "open",
  resumeGate: false,
  paused: false,
  degraded: false,
  mic: "granted",
  sheet: null,
  focus: "char.melos",
  session: "ready",
  holding: false,
  turn: null,
};
const turn = (over: Partial<Turn>): Turn => ({
  turnId: "turn_x",
  turnSeq: 1,
  kind: "voice",
  phase: "waiting",
  ...over,
});
const s = (over: Partial<Facts>) => voiceState({ ...base, ...over });

describe("voiceState", () => {
  it("idle: talking to someone, the session ready, nothing going on", () => {
    expect(s({})).toBe("idle");
    expect(s({ turn: turn({ phase: "settled" }) })).toBe("idle");
    expect(s({ turn: turn({ phase: "done", ended: true }) })).toBe("idle");
  });
  it("mic-unknown: not asked yet (the first press opens the primer)", () => {
    expect(s({ mic: "unknown" })).toBe("mic-unknown");
  });
  it("primer: the half page is up", () => {
    expect(s({ mic: "unknown", sheet: "primer" })).toBe("primer");
  });
  it("denied / unavailable: the microphone can't be used", () => {
    expect(s({ mic: "denied", sheet: "denied" })).toBe("denied");
    expect(s({ mic: "unavailable" })).toBe("unavailable");
  });
  it("preparing: the session with this character isn't ready", () => {
    expect(s({ session: "preparing" })).toBe("preparing");
    expect(s({ session: "none" })).toBe("preparing");
  });
  it("listening: the key is down, whatever the turn was doing", () => {
    expect(s({ holding: true, turn: turn({ phase: "speaking" }) })).toBe(
      "listening",
    );
    expect(s({ holding: true, session: "preparing" })).toBe("listening");
  });
  it("thinking: sent, no voice yet", () => {
    expect(s({ turn: turn({ phase: "waiting" }) })).toBe("thinking");
  });
  it("speaking: the character is audible, or done but still playing", () => {
    expect(s({ turn: turn({ phase: "speaking" }) })).toBe("speaking");
    expect(s({ turn: turn({ phase: "done" }) })).toBe("speaking");
  });
  it("no-response: the chips stay, even once settled", () => {
    expect(s({ turn: turn({ noResponse: true }) })).toBe("no-response");
    expect(s({ turn: turn({ phase: "settled", noResponse: true }) })).toBe(
      "no-response",
    );
  });
  it("degraded: text only, over the microphone's state", () => {
    expect(s({ degraded: true, mic: "unknown" })).toBe("degraded");
  });
  it("paused: the safety card, over everything but the connection", () => {
    expect(s({ paused: true, holding: true, degraded: true })).toBe("paused");
  });
  it("reconnecting: the socket is down, first of all", () => {
    expect(s({ connection: "reconnecting", paused: true })).toBe(
      "reconnecting",
    );
    expect(s({ connection: "connecting" })).toBe("reconnecting");
  });
  it("suspended: back from the background, waiting for the tap", () => {
    expect(s({ resumeGate: true, holding: true })).toBe("suspended");
  });
  it("away: nobody to talk to", () => {
    expect(s({ focus: null })).toBe("away");
    expect(s({ focus: null, mic: "denied" })).toBe("denied");
  });
});

describe("canPress", () => {
  it("can start a turn over a thinking or speaking character, not over a card or a sheet", () => {
    for (const ok of [
      "idle",
      "mic-unknown",
      "preparing",
      "thinking",
      "speaking",
      "no-response",
    ] as const)
      expect(canPress(ok)).toBe(true);
    for (const no of [
      "primer",
      "denied",
      "unavailable",
      "listening",
      "degraded",
      "paused",
      "reconnecting",
      "suspended",
      "away",
    ] as const)
      expect(canPress(no)).toBe(false);
  });
});
