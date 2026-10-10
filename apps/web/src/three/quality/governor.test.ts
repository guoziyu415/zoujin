// The level rules of frontend-design 10.6.3, driven with made-up frame times (F-2 card acceptance: when and how often
// the level goes up and down).
import { describe, expect, it } from "vitest";
import { Governor, STRESS_FRAMES, type Change } from "./governor";
import { estimateMs, levelDpr, pickStartLevel, type Level } from "./levels";

const VSYNC = 1000 / 60;

function run(start: Level, gpu: (l: Level) => number | null = () => null) {
  const changes: Change[] = [];
  const g = new Governor(start, 0, (c) => changes.push(c), gpu);
  let now = 0;
  const api = {
    g,
    changes,
    get now() {
      return now;
    },
    // frames at a fixed interval (or a repeating pattern) for this many ms
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
    // a camera cut; if it starts the 2x stress, draw those frames at `stressed` ms each
    cut(stressed = VSYNC) {
      g.cut(now);
      while (g.stressing > 0) {
        now += stressed;
        g.frame(stressed, now);
      }
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
    const r = run("L1").play(20_000, VSYNC).cut();
    expect(r.g.stressing).toBe(0);
    expect(r.g.level).toBe("L1"); // only 20 s in budget: no stress yet
    r.play(10_000, VSYNC).cut(); // 30 s: the stress runs and passes
    expect(r.g.level).toBe("L1");
    r.play(2_000, VSYNC);
    expect(r.g.level).toBe("L1"); // never between cuts
    r.cut();
    expect(r.g.level).toBe("L2");
    expect(r.g.applied).toBe("L2");
    expect(r.changes.at(-1)).toEqual({ from: "L1", to: "L2", reason: "up" });
    r.cut();
    expect(r.g.level).toBe("L2"); // the next rise needs another 30 s at L2
  });

  it("does not rise when the 2x stress drops to 30 fps", () => {
    const r = run("L1")
      .play(30_000, VSYNC)
      .cut(2 * VSYNC)
      .cut();
    expect(r.g.level).toBe("L1");
  });

  it("does not count the stress frames as the level's own", () => {
    const r = run("L1")
      .play(30_000, VSYNC)
      .cut(2 * VSYNC);
    expect(r.g.stressing).toBe(0);
    r.play(10_000, VSYNC);
    expect(r.g.level).toBe("L1");
    expect(r.reasons()).toEqual(["start"]);
    expect(STRESS_FRAMES).toBe(30);
  });

  it("waits 60 s after a drop before rising again", () => {
    const r = run("L2").play(10_000, janky(25));
    expect(r.g.level).toBe("L1");
    r.play(40_000, VSYNC).cut().cut();
    expect(r.g.level).toBe("L1"); // in budget for 40 s, but the drop was 40 s ago
    r.play(15_000, VSYNC).cut().cut();
    expect(r.g.level).toBe("L1"); // 55 s
    r.play(10_000, VSYNC).cut().cut();
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
    for (let i = 0; i < 10; i++) r.play(30_000, VSYNC).cut().cut();
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
    r.play(70_000, VSYNC);
    r.g.busy = true;
    r.cut().cut();
    expect(r.g.level).toBe("L0");
    r.g.busy = false;
    r.cut().cut();
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
          .cut()
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
