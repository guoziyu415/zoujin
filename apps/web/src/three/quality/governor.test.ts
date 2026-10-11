// The level rules of frontend-design 10.6.3, driven with made-up frame times (F-2 card acceptance: when and how often
// the level goes up and down).
import { describe, expect, it } from "vitest";
import { Governor, STILL_FRAMES, STRESS_FRAMES, type Change } from "./governor";
import {
  estimateMs,
  levelDpr,
  pickStartLevel,
  SETTINGS,
  type Level,
} from "./levels";

const VSYNC = 1000 / 60;

function run(start: Level, gpu: (l: Level) => number | null = () => null) {
  const changes: Change[] = [];
  const g = new Governor(start, 0, (c) => changes.push(c), gpu);
  let now = 0;
  const api = {
    g,
    changes,
    stressFrames: 0, // frames drawn twice so far
    get now() {
      return now;
    },
    // frames at a fixed interval (or a repeating pattern) for this many ms, the camera moving
    play(ms: number, interval: number | number[]) {
      const seq = Array.isArray(interval) ? interval : [interval];
      const end = now + ms;
      for (let i = 0; now < end; i++) {
        const dt = seq[i % seq.length]!;
        now += dt;
        g.frame(dt, now);
      }
      return api;
    },
    // the camera still for this many ms at 60 fps; if the 2x stress starts, its frames take `stressed` ms each
    hold(ms = 1000, stressed = VSYNC) {
      const end = now + ms;
      while (now < end) {
        const dt = g.stressing > 0 ? stressed : VSYNC;
        if (g.stressing > 0) api.stressFrames++;
        now += dt;
        g.frame(dt, now, true);
      }
      return api;
    },
    cut() {
      g.cut(now);
      return api;
    },
    reasons: () => changes.map((c) => c.reason),
  };
  return api;
}

// 95 % of frames at 60 fps and every tenth one long: p95 is the long one
const janky = (long: number) => [...Array(9).fill(VSYNC), long];

describe("quality governor", () => {
  it("starts with a start event and stays put at a steady 60 fps", () => {
    const r = run("L1").play(120_000, VSYNC);
    expect(r.changes).toEqual([{ to: "L1", reason: "start" }]);
    expect(r.g.level).toBe("L1");
  });

  it("drops after two checks in a row over budget; only the pixel ratio at once", () => {
    const r = run("L1").play(5_000, janky(50));
    expect(r.g.level).toBe("L1"); // one check over is not enough
    r.play(5_000, janky(50));
    expect(r.g.level).toBe("L0");
    expect(r.changes.at(-1)).toEqual({ from: "L1", to: "L0", reason: "down" });
    expect(r.g.applied).toBe("L1"); // shadows, bloom and the rest wait for a cut
    r.cut();
    expect(r.g.applied).toBe("L0");
  });

  it("does not drop when the checks over budget are not in a row", () => {
    const r = run("L2")
      .play(5_000, janky(34))
      .play(5_000, VSYNC)
      .play(5_000, janky(34))
      .play(5_000, VSYNC);
    expect(r.g.level).toBe("L2");
  });

  it("holds L2 to 20 ms and L1 to 34 ms", () => {
    // a frame of two refreshes now and then: over L2's budget, within L1's
    const r = run("L2").play(10_000, janky(2 * VSYNC));
    expect(r.g.level).toBe("L1");
    r.play(60_000, janky(2 * VSYNC));
    expect(r.g.level).toBe("L1");
  });

  it("rises only at a cut, after 30 s in budget and a 2x stress at about 60 fps, one level at the next cut", () => {
    const r = run("L1").play(20_000, VSYNC).hold();
    expect(r.stressFrames).toBe(0); // only 21 s in budget: no stress yet
    r.play(10_000, VSYNC).cut();
    expect(r.g.level).toBe("L1"); // 31 s, but the camera was moving: no stress, no rise
    r.hold(); // still: the stress runs and passes
    expect(r.stressFrames).toBe(STRESS_FRAMES + 1);
    expect(r.g.level).toBe("L1");
    r.play(2_000, VSYNC);
    expect(r.g.level).toBe("L1"); // never between cuts
    r.cut();
    expect(r.g.level).toBe("L2");
    expect(r.g.applied).toBe("L2");
    expect(r.changes.at(-1)).toEqual({ from: "L1", to: "L2", reason: "up" });
    r.hold().cut();
    expect(r.g.level).toBe("L2"); // the next rise needs another 30 s at L2
  });

  it("stresses only once the camera has been still a few frames, and stops when it moves", () => {
    const r = run("L1").play(30_000, VSYNC);
    r.hold(((STILL_FRAMES - 1) * VSYNC) | 0);
    expect(r.g.stressing).toBe(0); // the camera just stopped: not yet
    r.hold(10 * VSYNC);
    expect(r.g.stressing).toBeGreaterThan(0);
    r.play(VSYNC, VSYNC); // the player walks off: the stress stops, and it isn't a failure
    expect(r.g.stressing).toBe(0);
    r.cut();
    expect(r.g.level).toBe("L1");
    r.hold().cut();
    expect(r.g.level).toBe("L2");
  });

  it("does not rise when the 2x stress drops to 30 fps, and waits longer after each failure", () => {
    const r = run("L1")
      .play(30_000, VSYNC)
      .hold(1500, 2 * VSYNC)
      .cut();
    expect(r.g.level).toBe("L1");
    expect(r.stressFrames).toBe(STRESS_FRAMES + 1);
    r.hold(20_000).cut(); // not again at once: 30 s in budget first, then 60 s after one failure
    expect(r.stressFrames).toBe(STRESS_FRAMES + 1);
    r.play(40_000, VSYNC)
      .hold(1500, 2 * VSYNC)
      .cut(); // 61 s: the second try, failed too
    expect(r.stressFrames).toBe(2 * (STRESS_FRAMES + 1));
    r.play(100_000, VSYNC).hold().cut(); // 101 s: under the 120 s after two failures
    expect(r.stressFrames).toBe(2 * (STRESS_FRAMES + 1));
    r.play(20_000, VSYNC).hold().cut(); // 122 s, passes
    expect(r.g.level).toBe("L2");
  });

  it("does not count the stress frames as the level's own", () => {
    const r = run("L1")
      .play(30_000, VSYNC)
      .hold(1500, 2 * VSYNC);
    expect(r.g.stressing).toBe(0);
    r.play(10_000, VSYNC);
    expect(r.g.level).toBe("L1");
    expect(r.reasons()).toEqual(["start"]);
    expect(STRESS_FRAMES).toBe(30);
  });

  it("waits 5 minutes after a drop before rising again", () => {
    const r = run("L2").play(10_000, janky(25));
    expect(r.g.level).toBe("L1");
    r.play(60_000, VSYNC).hold().cut();
    expect(r.g.level).toBe("L1"); // in budget for a minute, but the drop was a minute ago
    r.play(220_000, VSYNC).hold().cut();
    expect(r.g.level).toBe("L1"); // 4 min 42 s
    r.play(20_000, VSYNC).hold().cut();
    expect(r.g.level).toBe("L2");
  });

  it("locks the ceiling after two drops", () => {
    const r = run("L3").play(10_000, janky(25));
    expect(r.g.level).toBe("L2");
    r.play(10_000, janky(25));
    expect(r.g.level).toBe("L1");
    expect(r.reasons()).toEqual(["start", "down", "down", "locked"]);
    expect(r.changes.at(-1)).toEqual({
      from: "L1",
      to: "L1",
      reason: "locked",
    });
    for (let i = 0; i < 10; i++) r.play(30_000, VSYNC).hold().cut();
    expect(r.g.level).toBe("L1");
    r.play(10_000, janky(50));
    expect(r.g.level).toBe("L0"); // dropping is still allowed
  });

  it("neither rises nor applies a drop's settings while busy", () => {
    const r = run("L1").play(10_000, janky(50));
    expect(r.g.level).toBe("L0");
    r.g.busy = true;
    r.cut();
    expect(r.g.applied).toBe("L1");
    r.g.busy = false;
    r.cut();
    expect(r.g.applied).toBe("L0");
    r.play(310_000, VSYNC);
    r.g.busy = true;
    r.hold().cut();
    expect(r.stressFrames).toBe(0); // no stress mid-line either
    expect(r.g.level).toBe("L0");
    r.g.busy = false;
    r.hold().cut();
    expect(r.g.level).toBe("L1");
  });

  it("never goes below L0", () => {
    const r = run("L0").play(60_000, 200);
    expect(r.reasons()).toEqual(["start"]);
  });

  it("ignores the gap when the page comes back from the background", () => {
    const r = run("L2").play(4_000, VSYNC);
    r.g.frame(30_000, r.now + 30_000);
    r.play(4_000, VSYNC).play(4_000, VSYNC);
    expect(r.g.level).toBe("L2");
  });

  describe("low-power mode (Safari locked at 30 fps)", () => {
    it("holds every level to the 30 fps budget and stops rising when the GPU has room", () => {
      const r = run("L2", () => 3).play(30_000, 2 * VSYNC);
      expect(r.g.lowPower).toBe(true);
      expect(r.g.level).toBe("L2");
      expect(r.reasons()).toEqual(["start", "lowPower"]);
      for (let i = 0; i < 4; i++)
        r.play(30_000, 2 * VSYNC)
          .hold()
          .cut();
      expect(r.g.level).toBe("L2");
      // plugged in: back at 60 fps, the normal budgets again
      r.play(10_000, VSYNC);
      expect(r.g.lowPower).toBe(false);
    });

    it("treats a steady 33 ms as a slow GPU when the probe says so, or without a probe", () => {
      expect(run("L2", () => 30).play(10_000, 2 * VSYNC).g.level).toBe("L1");
      expect(run("L2").play(10_000, 2 * VSYNC).g.level).toBe("L1");
    });
  });
});

describe("start level from the probe", () => {
  it("starts at L1 without a measurement", () => {
    expect(pickStartLevel(null, 3)).toBe("L1");
  });

  it("scales the probe by the number of pixels", () => {
    expect(levelDpr("L3", 3)).toBe(3);
    expect(levelDpr("L1", 1)).toBe(1);
    expect(estimateMs(2, "L2", 3)).toBeCloseTo(2 * (2 / 1.5) ** 2);
    expect(estimateMs(2, "L3", 3)).toBeCloseTo(2 * 4);
  });

  it("picks the highest level that fits: L1 within 25 ms, L2 and L3 within 12 ms", () => {
    // S7 b7 on zg's phone (2.6 ms) and the same scaled to an iPhone 12 (x 3.4, frontend-design 10.6.5)
    expect(pickStartLevel(2.6, 3)).toBe("L3");
    expect(pickStartLevel(2.6 * 3.4, 3)).toBe("L1");
    expect(pickStartLevel(5, 3)).toBe("L2");
    expect(pickStartLevel(26, 3)).toBe("L0");
    // a 1x screen draws every level at the same size
    expect(pickStartLevel(11, 1)).toBe("L3");
  });
});

// Heat (frontend-design 10.6.4, S-014): 20 minutes of play while the phone warms up and its GPU slows down. A made-up
// phone: one frame's GPU time at L1 `l1Ms` cold, times the pixels of each level, times `heat` (1 cold, rising to
// `hot` over the first 15 minutes, as a phone throttles), plus a little jitter every tenth frame; the screen shows
// whole 60 Hz refreshes. The player walks 18 s, stands 2 s (the camera still), then a cut, over and over. What must
// hold: the level settles instead of going up and down, and the last 5 minutes keep the level's budget.
describe("quality governor, 20 minutes warming up", () => {
  const MIN = 60_000;
  function warm(l1Ms: number, hot: number, dpr = 3) {
    const ms = (l: Level, t: number) => {
      const heat = 1 + (hot - 1) * Math.min(1, t / (15 * MIN));
      const px = (levelDpr(l, dpr) / levelDpr("L1", dpr)) ** 2;
      return l1Ms * px * heat;
    };
    const shown = (gpu: number) => Math.ceil(gpu / VSYNC - 1e-9) * VSYNC;
    const start = pickStartLevel(l1Ms, dpr);
    const changes: Change[] = [];
    const g = new Governor(
      start,
      0,
      (c) => changes.push(c),
      (l) => ms(l, 0),
    );
    const late: number[] = [];
    let now = 0;
    let i = 0;
    const frame = (still: boolean) => {
      const jitter = ++i % 10 === 0 ? 4 : 0;
      const gpu = ms(g.level, now) * (g.stressing > 0 ? 2 : 1) + jitter;
      const dt = shown(gpu);
      now += dt;
      if (now > 15 * MIN && g.stressing === 0) late.push(dt);
      g.frame(dt, now, still);
    };
    while (now < 20 * MIN) {
      const walk = now + 18_000;
      while (now < walk) frame(false);
      const stand = now + 2_000;
      while (now < stand) frame(true);
      g.cut(now);
    }
    late.sort((a, b) => a - b);
    const p95 = late[Math.floor(0.95 * late.length)]!;
    const moves = changes.filter(
      (c) => c.reason === "down" || c.reason === "up",
    );
    return { start, g, changes, moves, p95 };
  }

  it("a strong phone starts high, steps down once as it warms and stays there", () => {
    const r = warm(5, 2.2);
    expect(r.start).toBe("L2");
    expect(r.moves).toEqual([{ from: "L2", to: "L1", reason: "down" }]);
    expect(r.p95).toBeLessThanOrEqual(SETTINGS.L1.budgetMs);
  });

  it("a baseline phone holds the standard tier until the heat is too much, then the fallback, never back up", () => {
    const mild = warm(9, 2.2);
    expect(mild.start).toBe("L1");
    expect(mild.moves).toEqual([]);
    expect(mild.p95).toBeLessThanOrEqual(SETTINGS.L1.budgetMs);
    const hot = warm(12, 3);
    expect(hot.moves).toEqual([{ from: "L1", to: "L0", reason: "down" }]);
    expect(hot.p95).toBeLessThanOrEqual(SETTINGS.L0.budgetMs);
  });

  it("a phone with room to rise goes up while cold, and after warming comes down at most twice and locks", () => {
    const r = warm(3.5, 2.5, 3);
    const ups = r.moves.filter((c) => c.reason === "up");
    const downs = r.moves.filter((c) => c.reason === "down");
    expect(ups.length).toBeLessThanOrEqual(1);
    expect(downs.length).toBeLessThanOrEqual(2);
    // every rise comes before every drop: nothing goes back up once the heat has pushed it down
    const firstDown = r.moves.findIndex((c) => c.reason === "down");
    if (firstDown >= 0)
      expect(r.moves.slice(firstDown).every((c) => c.reason === "down")).toBe(
        true,
      );
    expect(r.p95).toBeLessThanOrEqual(SETTINGS[r.g.level].budgetMs);
  });
});
