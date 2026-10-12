import { describe, expect, it } from "vitest";
import { groupPlacement, type GroupCandidate } from "./groupPlacement";

const candidate = (
  key: string,
  x: number,
  place = "place.castle",
): GroupCandidate => ({
  key,
  place,
  at: { x, y: 0, z: 0, poly: 0 },
  yaw: 0,
});

describe("named group placement", () => {
  const points = [
    candidate("a", 0),
    candidate("b", 3),
    candidate("wrong-place", 7, "place.square"),
  ];
  it("stays in its place and clear of the player or fixed NPC", () => {
    expect(
      groupPlacement("char.guards", "place.castle", points, [{ x: 0.8, z: 0 }])
        ?.key,
    ).toBe("b");
  });
  it("keeps an existing safe position and is deterministic without one", () => {
    expect(
      groupPlacement("char.guards", "place.castle", points, [], points[1])?.key,
    ).toBe("b");
    expect(groupPlacement("char.guards", "place.castle", points, [])).toEqual(
      groupPlacement("char.guards", "place.castle", [...points].reverse(), []),
    );
  });
  it("hides a representative instead of overlapping when no space remains", () => {
    expect(
      groupPlacement("char.guards", "place.castle", points, [
        { x: 0, z: 0 },
        { x: 3, z: 0 },
      ]),
    ).toBeNull();
  });
  it("does not move an existing representative when the player approaches", () => {
    expect(
      groupPlacement(
        "char.guards",
        "place.castle",
        points,
        [{ x: 3.1, z: 0 }],
        points[1],
        [],
      ),
    ).toBe(points[1]);
    // A real NPC/crowd occupation still forces a new clear location.
    expect(
      groupPlacement(
        "char.guards",
        "place.castle",
        points,
        [{ x: 3.1, z: 0 }],
        points[1],
        [{ x: 3.1, z: 0 }],
      )?.key,
    ).toBe("a");
  });
});
