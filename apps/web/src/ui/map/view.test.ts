import type { Api } from "@zoujin/contracts";
import { describe, expect, it } from "vitest";
import {
  corrected,
  FOLD_OVER,
  foldedDays,
  nowDayOf,
  nowIndex,
  people,
  shown,
} from "./view";

const ev = (
  id: string,
  t: number,
  mine: boolean,
  knownBy: string[],
): Api.TimelineItem => ({
  kind: "event",
  eventId: id,
  t,
  tLabel: "",
  summary: id,
  place: "place.syracuse-square",
  style: mine ? "player" : "system",
  causedByPlayer: mine,
  forPlayer: false,
  knownBy,
});
const beat: Api.TimelineItem = {
  kind: "beat",
  beatId: "beat.03",
  t: 1170,
  tLabel: "",
  known: true,
  status: "canon",
};
const items = [
  ev("a", 1000, true, ["char.melos"]),
  beat,
  ev("b", 1200, false, ["char.old-man"]),
];

describe("map", () => {
  it("filters: everything; mine; by person (beats step aside)", () => {
    expect(shown(items, { character: null, mine: false })).toHaveLength(3);
    expect(
      shown(items, { character: null, mine: true }).map((i) => i.t),
    ).toEqual([1000]);
    expect(
      shown(items, { character: "char.old-man", mine: false }).map((i) => i.t),
    ).toEqual([1200]);
  });

  it("chips: whoever knows something, first seen first", () => {
    expect(people([{ day: 0, label: "", items }])).toEqual([
      "char.melos",
      "char.old-man",
    ]);
  });

  it("いまここ after the last item at or before now", () => {
    expect(nowIndex(items, 900)).toBe(-1);
    expect(nowIndex(items, 1170)).toBe(1);
    expect(nowIndex(items, 9999)).toBe(2);
  });

  it("corrections mark the event that replaced the old one", () => {
    const e = { eventId: "ev_2", supersedes: "ev_1" } as Api.VisibleEvent;
    expect([
      ...corrected([
        e,
        { eventId: "ev_3", supersedes: null } as Api.VisibleEvent,
      ]),
    ]).toEqual(["ev_2"]);
  });
});

describe("いまここ across days", () => {
  it("is in the last day with something at or before now, not the last day", () => {
    const beat = (t: number) =>
      ({
        kind: "beat",
        beatId: "b",
        t,
        tLabel: "",
        known: false,
      }) as Api.TimelineItem;
    const days = [
      { day: 1, label: "一日目", items: [beat(10), beat(20)] },
      { day: 3, label: "三日目", items: [beat(500)] },
    ];
    expect(nowDayOf(days, 30)).toBe(1);
    expect(nowDayOf(days, 5)).toBeNull();
  });
});

describe("folding the earlier days (F-17)", () => {
  const day = (n: number, k: number) => ({
    day: n,
    label: `d${n}`,
    items: Array.from({ length: k }, (_, i) =>
      ev(`ev_${n}_${i}`, n * 1440 + i, false, []),
    ),
  });
  const none = { character: null, mine: false };
  it("folds the days before now's only on a long map, keeps the target's day, not while filtering", () => {
    expect(foldedDays([day(0, 3), day(1, 3)], 1, none).size).toBe(0);
    const long = [day(0, FOLD_OVER), day(1, 2), day(2, 2), day(3, 1)];
    expect([...foldedDays(long, 2, none)]).toEqual([0, 1]);
    expect([...foldedDays(long, 2, none, "ev_1_0")]).toEqual([0]);
    expect(foldedDays(long, 2, { character: null, mine: true }).size).toBe(0);
    expect(foldedDays(long, null, none).size).toBe(0);
  });
});
