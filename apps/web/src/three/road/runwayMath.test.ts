import { describe, expect, it } from "vitest";
import {
  CITY_AT_M,
  cityDistanceM,
  cityScale,
  due,
  matches,
  wrapBelt,
} from "./runwayMath";

describe("runway (F-15)", () => {
  it("picks the scrolling nodes by name, tile_* by prefix", () => {
    const scroll = ["ground", "arch", "proxy", "tile_*"];
    expect(matches("ground", scroll)).toBe(true);
    expect(matches("tile_wheat", scroll)).toBe(true);
    expect(matches("far", scroll)).toBe(false);
    expect(matches("set_feast", scroll)).toBe(false);
  });

  it("keeps the belt within one tile and counts the wraps", () => {
    expect(wrapBelt(-10, 36)).toEqual({ x: -10, wraps: 0 });
    expect(wrapBelt(-37, 36)).toEqual({ x: -1, wraps: 1 });
    expect(wrapBelt(-36, 36)).toEqual({ x: 0, wraps: 1 });
    expect(wrapBelt(2, 36)).toEqual({ x: -34, wraps: -1 });
  });

  it("brings a set piece round its minute, or from its minute on", () => {
    const feast = { atMinute: 5370 }; // 17:30 on day 3 (beat.22)
    expect(due(feast, 5360)).toBe(false);
    expect(due(feast, 5368)).toBe(true);
    expect(due(feast, 5378)).toBe(true);
    expect(due(feast, 5390)).toBe(false);
    expect(due({ fromMinute: 5390 }, 5450)).toBe(true);
    expect(due({ fromMinute: 5390 }, 5389)).toBe(false);
    expect(due({}, 5400)).toBe(false);
    expect(due(feast, undefined)).toBe(false);
  });

  it("draws the city as far as the clock says (homeward-road.md 4.2)", () => {
    expect(cityDistanceM(5390)).toBe(6000); // 17:50 on the crest
    expect(cityDistanceM(5430)).toBe(2000); // 18:30
    expect(cityDistanceM(5450)).toBe(300); // 18:50
    expect(cityDistanceM(5440)).toBeCloseTo(1150);
    // at 300 m and nearer: the true size where it stands
    expect(cityScale(300)).toBe(1);
    expect(cityScale(100)).toBe(1);
    // 2 km: the true angular size; 6 km: three times it, so the towers still read
    expect(cityScale(2000)).toBeCloseTo(CITY_AT_M / 2000);
    expect(cityScale(6000)).toBeCloseTo((CITY_AT_M / 6000) * 3);
  });
});
