import type { Api } from "@zoujin/contracts";
import { describe, expect, it } from "vitest";
import { corrected, nowIndex, people, shown } from "./view";

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
