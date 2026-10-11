import type { Api } from "@zoujin/contracts";
import { describe, expect, it } from "vitest";
import {
  DAY,
  happenedAt,
  hostagePose,
  hostageWear,
  meetingAt,
  routeOf,
  talkShot,
} from "./staging";

const beat = (b: string, t: number) =>
  ({
    t,
    visibleEffects: [{ kind: "beat", beat: b, change: "happened", label: "" }],
  }) as unknown as Api.VisibleEvent;

describe("castle staging", () => {
  it("finds when a beat happened, the latest one", () => {
    const ev = [beat("beat.04", 1200), beat("beat.05", 1230)];
    expect(happenedAt(ev, "beat.04")).toBe(1200);
    expect(happenedAt(ev, "beat.06")).toBeNull();
  });

  it("leads Melos in only when he was just brought, and sends him out by his bundle", () => {
    const s = { t: 1205, led: 1200, summoned: null };
    expect(routeOf("char.melos", "before-king", true, s)).toEqual({
      from: "melos-led-in",
      speed: 1.0,
    });
    expect(
      routeOf("char.melos", "before-king", true, { ...s, t: 1300 }),
    ).toBeNull();
    expect(routeOf("char.melos", "way.plaza", false, s)?.via).toEqual([
      [9.6, 1.4],
    ]);
    expect(
      routeOf("char.selinuntius", "selinuntius-meet", true, {
        t: 1415,
        led: 1200,
        summoned: 1410,
      })?.from,
    ).toBe("selinuntius-in");
  });

  it("plays the meeting in order", () => {
    expect([0, 4, 7, 10, 20].map(meetingAt)).toEqual([
      "untie",
      "tell",
      "embrace",
      "bind",
      "held",
    ]);
  });

  it("keeps the hostage's pose table", () => {
    const o = { visitor: false, doubted: false };
    expect(hostagePose(1430, o)).toBe("sit-lean");
    expect(hostagePose(DAY + 600, o)).toBe("sit");
    expect(hostagePose(DAY + 600, { ...o, visitor: true })).toBe("stand");
    expect(hostagePose(2 * DAY + 800, o)).toBe("sit-rain");
    expect(hostagePose(3 * DAY + 600, o)).toBe("sit");
    expect(hostagePose(3 * DAY + 940, o)).toBe("stand-west");
    expect(hostagePose(3 * DAY + 960, { ...o, doubted: true })).toBe(
      "head-down",
    );
    expect(hostageWear(2 * DAY + 100)).toBe(1);
    expect(hostageWear(3 * DAY)).toBe(2);
  });

  it("frames the king from below and kneels by the sitting hostage", () => {
    expect(talkShot("char.king", 4, false)).toEqual({ back: 1.2, camY: 1.4 });
    expect(talkShot("char.king", 7, false)?.fov).toBe(25);
    expect(talkShot("char.selinuntius", 1.35, true)?.headY).toBe(0.95);
    expect(talkShot("char.selinuntius", 1.35, false)).toBeNull();
    expect(talkShot("char.selinuntius", 2, true)).toBeNull();
  });
});
