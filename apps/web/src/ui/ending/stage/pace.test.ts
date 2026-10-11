import { describe, expect, it } from "vitest";
import {
  addLines,
  holdMs,
  initPace,
  insertLine,
  pause,
  performed,
  resume,
  shotDone,
  tap,
  tick,
  visibleText,
  type Effect,
  type Pace,
  type StageLine,
} from "./pace";

const narr = (text: string, shot: number | null = null): StageLine => ({
  text,
  speaker: null,
  clipMs: null,
  shot,
});
const voiced = (
  text: string,
  ms: number,
  shot: number | null = null,
): StageLine => ({
  text,
  speaker: "char.melos",
  clipMs: ms,
  shot,
});

// run ticks every 100 ms up to `to`, collecting effects
function run(p: Pace, from: number, to: number): [Pace, Effect[]] {
  const all: Effect[] = [];
  let s = p;
  for (let t = from; t <= to; t += 100) {
    const [n, fx] = tick(s, t);
    s = n;
    all.push(...fx);
  }
  return [s, all];
}

describe("hold times", () => {
  it("narration: chars ÷ 7 s, at least 1.5 s; recorded: the voice + 0.5 s", () => {
    expect(holdMs(narr("間に合った。"))).toBe(1500); // 6 chars < 10.5
    expect(holdMs(narr("あ".repeat(28)))).toBe(4000);
    expect(holdMs(voiced("待て。", 2400))).toBe(2900);
    // a character's line without its recording counts like narration
    expect(holdMs({ ...voiced("あ".repeat(14), 0), clipMs: null })).toBe(2000);
  });
});

describe("moving on by itself", () => {
  it("shows the first line at once, the next when the time is up, never a gap", () => {
    let [p, fx] = addLines(
      initPace(true),
      [narr("一"), narr("あ".repeat(14))],
      0,
    );
    expect(fx).toContainEqual({ k: "show", i: 0 });
    [p] = run(p, 100, 1400);
    expect(p.i).toBe(0);
    [p, fx] = run(p, 1500, 1500);
    expect(fx).toContainEqual({ k: "show", i: 1 });
    [p, fx] = run(p, 1600, 3500);
    expect(fx).toContainEqual({ k: "drained" });
    expect(p.i).toBe(1); // the last line stays
  });

  it("the first line of a new shot also waits for the shot's action", () => {
    let [p, fx] = addLines(initPace(true), [narr("一", 1), narr("二", 2)], 0);
    expect(fx).toContainEqual({ k: "shot", n: 1 });
    [p] = run(p, 100, 3000);
    expect(p.i).toBe(0); // time is up, shot 1 still going
    p = shotDone(p, 1);
    [, fx] = tick(p, 3100);
    expect(fx).toEqual(
      expect.arrayContaining([
        { k: "shot", n: 2 },
        { k: "show", i: 1 },
      ]),
    );
  });

  it("a line in the same shot doesn't wait for the action", () => {
    let [p] = addLines(initPace(true), [narr("一", 2), narr("二", 2)], 0);
    [p] = run(p, 100, 1500);
    expect(p.i).toBe(1);
  });

  it("a cut in the middle of a line (shot 7 → 8)", () => {
    const l: StageLine = {
      ...narr("あ".repeat(28), 7),
      midShot: { at: 0.5, shot: 8 },
    };
    const [p0] = addLines(initPace(true), [l], 0);
    const [p, fx] = run(p0, 100, 2000);
    expect(fx).toContainEqual({ k: "shot", n: 8 });
    expect(p.shot).toBe(8);
  });

  it("auto off: every line waits for a tap", () => {
    let [p] = addLines(initPace(false), [narr("一"), narr("二")], 0);
    [p] = run(p, 100, 10_000);
    expect(p.i).toBe(0);
    [p] = tap(p, 10_100);
    expect(p.i).toBe(1);
  });

  it("lines that come after the last one had its time show at once", () => {
    let [p] = addLines(initPace(true), [narr("一")], 0);
    [p] = run(p, 100, 2000);
    expect(p.drained).toBe(true);
    const [q, fx] = addLines(p, [narr("二")], 2100);
    expect(fx).toContainEqual({ k: "show", i: 1 });
    expect(q.drained).toBe(false);
  });
});

describe("taps", () => {
  it("whole line: a tap moves on; taps within 0.5 s of it appearing don't count", () => {
    let [p] = addLines(initPace(true), [narr("一"), narr("二"), narr("三")], 0);
    [p] = tap(p, 300);
    expect(p.i).toBe(0);
    [p] = tap(p, 600);
    expect(p.i).toBe(1);
    [p] = tap(p, 900); // 0.3 s after line 2 came: a double tap, ignored
    expect(p.i).toBe(1);
    expect(p.taps).toBe(1);
  });

  it("recorded line: first tap completes it (voice goes on), second fades the voice and moves on", () => {
    let [p, fx] = addLines(
      initPace(true),
      [voiced("待て。その人を殺してはならぬ。", 3000), voiced("二", 1000)],
      0,
    );
    expect(fx).toContainEqual({ k: "play", i: 0 });
    expect(visibleText(p, 1000).length).toBeLessThan(15);
    [p, fx] = tap(p, 1000);
    expect(p.whole).toBe(true);
    expect(fx).toEqual([]);
    [p] = tap(p, 1300); // within 0.5 s of completing
    expect(p.i).toBe(0);
    [p, fx] = tap(p, 1600);
    expect(fx).toEqual(
      expect.arrayContaining([{ k: "fade" }, { k: "show", i: 1 }]),
    );
    expect(fx).not.toContainEqual({ k: "play", i: 1 }); // after the fade
    [, fx] = tick(p, 1850);
    expect(fx).toContainEqual({ k: "play", i: 1 });
  });

  it("a recorded line that is whole after its voice: a tap moves on without a fade", () => {
    let [p] = addLines(initPace(true), [voiced("一", 1000), narr("二")], 0);
    [p] = run(p, 100, 1200);
    expect(p.whole).toBe(true);
    const [q, fx] = tap(p, 1300);
    expect(q.i).toBe(1);
    expect(fx).not.toContainEqual({ k: "fade" });
  });

  it("a tap cuts to the next shot without waiting for the action", () => {
    const [p] = addLines(initPace(true), [narr("一", 1), narr("二", 2)], 0);
    const [q, fx] = tap(p, 800);
    expect(q.i).toBe(1);
    expect(fx).toContainEqual({ k: "shot", n: 2 });
  });
});

describe("pause", () => {
  it("the clock stops in the background; the tap that brings it back doesn't count", () => {
    let [p] = addLines(initPace(true), [narr("一"), narr("二")], 0);
    p = pause(p, 1000);
    [p] = run(p, 1100, 9000);
    expect(p.i).toBe(0);
    p = resume(p, 9000);
    [p] = tap(p, 9100);
    expect(p.i).toBe(0);
    [p] = run(p, 9100, 9400);
    expect(p.i).toBe(0); // 1.0 s shown before + 0.4 s after
    [p] = run(p, 9500, 9500);
    expect(p.i).toBe(1);
  });
});

describe("what the staging measured", () => {
  it("play time without the pauses, the taps that did something, the lines", () => {
    let [p] = addLines(
      initPace(true),
      [narr("一"), narr("二"), narr("三")],
      1000,
    );
    [p] = tap(p, 1200); // within the guard: not a tap
    [p] = tap(p, 1600);
    p = pause(p, 2000);
    p = resume(p, 7000);
    [p] = run(p, 7100, 9000);
    expect(performed(p, 9000)).toEqual({
      playMs: 3000,
      pausedMs: 5000,
      taps: 1,
      lines: 3,
    });
  });

  it("no lines, nothing to send", () => {
    expect(performed(initPace(true), 5000)).toBeNull();
  });

  it("the action's narration goes before the first set-piece line, or next when that has played", () => {
    const piece = (text: string, n: number): StageLine => ({
      ...narr(text, 1),
      key: `piece.curtain/${n}`,
    });
    const act = narr("あなたは待った");
    // not started: before the curtain
    let [p] = addLines(initPace(true), [], 0);
    p = { ...p, lines: [piece("幕一", 1), piece("幕二", 2)] };
    [p] = insertLine(p, act, 0);
    expect(p.lines.map((l) => l.text)).toEqual([
      "あなたは待った",
      "幕一",
      "幕二",
    ]);
    // the curtain's first line on screen: right after it
    let [q] = addLines(initPace(true), [piece("幕一", 1), piece("幕二", 2)], 0);
    expect(q.i).toBe(0);
    [q] = insertLine(q, act, 100);
    expect(q.lines.map((l) => l.text)).toEqual([
      "幕一",
      "あなたは待った",
      "幕二",
    ]);
    expect(q.i).toBe(0);
  });
});
