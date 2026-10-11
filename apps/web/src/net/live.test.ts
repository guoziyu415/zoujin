import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BACKOFF_MS, Live, PING_MS, type LiveEvents } from "./live";
import { FakeSocket } from "./testkit";

function setup(lastSeq = 0) {
  const ev = {
    lastSeq: () => lastSeq,
    onMessage: vi.fn(),
    onOpen: vi.fn(),
    onDown: vi.fn(),
    onEnded: vi.fn(),
  } satisfies LiveEvents;
  const live = new Live(
    "ws://test/v1/playthroughs/p/live",
    "web-test",
    ev,
    FakeSocket,
  );
  live.connect();
  return { live, ev };
}

beforeEach(() => {
  vi.useFakeTimers();
  FakeSocket.all = [];
});
afterEach(() => vi.useRealTimers());

describe("Live", () => {
  it("says hello with lastSeq first, then pings every 20 s", () => {
    setup(12);
    const s = FakeSocket.last();
    s.open();
    expect(s.sent[0]).toEqual({
      type: "hello",
      lastSeq: 12,
      clientVersion: "web-test",
    });
    vi.advanceTimersByTime(PING_MS * 2);
    expect(s.types()).toEqual(["hello", "ping", "ping"]);
  });

  it("backs off 1, 2, 4, 8, 8 s while it can't connect, and starts over after a good open", () => {
    const { ev } = setup();
    const waits: number[] = [];
    for (let i = 0; i < 5; i++) {
      const before = FakeSocket.all.length;
      FakeSocket.last().drop();
      let waited = 0;
      while (FakeSocket.all.length === before) {
        vi.advanceTimersByTime(500);
        waited += 500;
      }
      waits.push(waited);
    }
    expect(waits).toEqual([...BACKOFF_MS, 8000]);
    expect(ev.onDown).toHaveBeenCalledTimes(5);
    FakeSocket.last().open();
    FakeSocket.last().drop();
    vi.advanceTimersByTime(BACKOFF_MS[0]!);
    expect(FakeSocket.all.length).toBe(7);
  });

  it.each([
    [4001, "unauthenticated"],
    [4009, "taken"],
    [4003, "gone"],
    [4004, "gone"],
  ])("close %i ends the connection (%s) without retrying", (code, why) => {
    const { ev } = setup();
    FakeSocket.last().open();
    FakeSocket.last().drop(code);
    vi.advanceTimersByTime(60_000);
    expect(ev.onEnded).toHaveBeenCalledWith(why);
    expect(FakeSocket.all.length).toBe(1);
  });

  it("reconnects at once on 1012 and after 8 s on 4290", () => {
    setup();
    FakeSocket.last().open();
    FakeSocket.last().drop(1012);
    vi.advanceTimersByTime(0);
    expect(FakeSocket.all.length).toBe(2);
    FakeSocket.last().open();
    FakeSocket.last().drop(4290);
    vi.advanceTimersByTime(7999);
    expect(FakeSocket.all.length).toBe(2);
    vi.advanceTimersByTime(1);
    expect(FakeSocket.all.length).toBe(3);
  });

  it("reconnects once after goaway's delay, even when the server closes with 1012 first", () => {
    const { ev } = setup();
    const s = FakeSocket.last();
    s.open();
    s.receive({ type: "goaway", reason: "deploy", reconnectAfterMs: 1000 });
    expect(ev.onMessage).toHaveBeenCalledWith(
      expect.objectContaining({ type: "goaway" }),
    );
    vi.advanceTimersByTime(300);
    s.drop(1012);
    vi.advanceTimersByTime(699);
    expect(FakeSocket.all.length).toBe(1);
    vi.advanceTimersByTime(1);
    expect(FakeSocket.all.length).toBe(2);
    vi.advanceTimersByTime(10_000);
    expect(FakeSocket.all.length).toBe(2);
  });

  it("ignores frames that aren't JSON objects with a type", () => {
    const { ev } = setup();
    const s = FakeSocket.last();
    s.open();
    s.receive("not json");
    s.receive({ no: "type" });
    s.receive([1, 2]);
    expect(ev.onMessage).not.toHaveBeenCalled();
  });

  it("close() stops for good; retryNow() comes back", () => {
    const { live } = setup();
    FakeSocket.last().open();
    live.close();
    expect(FakeSocket.last().closedWith).toBe(1000);
    vi.advanceTimersByTime(60_000);
    expect(FakeSocket.all.length).toBe(1);
    live.retryNow();
    expect(FakeSocket.all.length).toBe(2);
  });
});
