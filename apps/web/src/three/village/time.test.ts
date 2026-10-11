import { describe, expect, it } from "vitest";
import {
  CLEAR_WINDOW,
  CLOUDS_FROM,
  RAIN_BY,
  clearSet,
  lamps,
  roomLight,
  weather,
  yard,
} from "./time";
import { inZone } from "./zones";

describe("the village's light and weather (F-11 card 5)", () => {
  it("picks the clear sky's sets by the time of day", () => {
    expect(clearSet(1440 + 600)).toEqual({ a: "day", b: "day", w: 0 }); // 一日目 10:00
    expect(clearSet(1440 + 1065).w).toBeCloseTo(0.5); // 17:45: halfway to the sunset set
    expect(clearSet(1440 + 1110).a).toBe("sunset"); // 18:30
    expect(clearSet(1440 + 1380).a).toBe("night"); // 23:00
    expect(clearSet(2880 + 300)).toMatchObject({ a: "night", b: "day" }); // 05:00, 薄明
  });

  it("closes the sky by the clock, rains on the commit or by 13:00, clears in beat.15's window", () => {
    expect(weather(CLOUDS_FROM - 1)).toEqual({ cloud: 0, rain: 0 });
    expect(weather(CLOUDS_FROM + 10).cloud).toBeCloseTo(0.5);
    expect(weather(CLOUDS_FROM + 10).rain).toBe(0); // clouds first, no rain yet
    expect(weather(CLOUDS_FROM + 10, CLOUDS_FROM + 6).rain).toBeCloseTo(0.5); // the commit came
    expect(weather(RAIN_BY + 8).rain).toBe(1); // no commit: the fallback
    expect(weather(CLEAR_WINDOW[0] + 10, null, CLEAR_WINDOW[0]).rain).toBe(0); // stopped on beat.15
    expect(weather(CLEAR_WINDOW[1] + 60)).toEqual({ cloud: 0, rain: 0 });
    expect(weather(4320 + 300).rain).toBeCloseTo(0.7); // 三日目 05:00: one step lighter
  });

  it("the house: the feast once the weather has turned, else the day's light dimmed", () => {
    expect(roomLight(2880 + 1260, { cloud: 1, rain: 1 }).set).toBe("feast");
    expect(roomLight(1440 + 660, { cloud: 0, rain: 0 })).toEqual({
      set: "day",
      dim: 1,
    });
    expect(roomLight(1440 + 1380, { cloud: 0, rain: 0 }).dim).toBeCloseTo(0.05);
  });

  it("the yard, the lamps and the door by the clock", () => {
    expect(yard(1440 + 629).altarDressed).toBe(false);
    expect(yard(1440 + 630).altarDressed).toBe(true);
    expect(yard(2880 + 360).myrtle).toBe(true);
    expect(lamps(1440 + 1380)).toEqual({
      vine: true,
      lantern: false,
      door: false,
    });
    expect(lamps(4320 + 270)).toEqual({
      vine: false,
      lantern: true,
      door: true,
    });
  });
});

describe("the house's camera zone (F-11 card 6)", () => {
  const room: [number, number][] = [
    [0, 0],
    [4, 0],
    [4, 6],
    [0, 6],
  ];
  it("takes the room's box when the pack has no zones", async () => {
    const { roomZone } = await import("./zones");
    const z = roomZone({ min: [-13.7, 0, 8.8], max: [-2.3, 4.1, 13.7] });
    expect(inZone(z.polygon, -8, 11, false)).toBe(true);
    expect(inZone(z.polygon, -8, 7, false)).toBe(false);
    expect(z.portrait.fov).toBe(70);
  });
  it("counts as in 0.5 m past the wall and as out 0.5 m past it the other way", () => {
    expect(inZone(room, 0.2, 3, false)).toBe(false); // on the threshold: still out
    expect(inZone(room, 0.6, 3, false)).toBe(true);
    expect(inZone(room, -0.2, 3, true)).toBe(true); // just outside: still in
    expect(inZone(room, -0.6, 3, true)).toBe(false);
  });
});

describe("the puddles (F-11 card 5)", () => {
  it("fill in the downpour and dry slowly after", async () => {
    const { fill } = await import("./rainGround");
    expect(fill(0, 1, 12.5)).toBeCloseTo(0.5);
    expect(fill(0.5, 1, 100)).toBe(1);
    expect(fill(1, 0, 90)).toBeCloseTo(0.5);
    expect(fill(0.1, 0, 100)).toBe(0);
  });
});
