import { describe, expect, it } from "vitest";
import { NavMesh, type NavData } from "./navmesh";

// An L of three 2 m squares (x, z): A = (0..2, 0..2), B = (2..4, 0..2), C = (2..4, 2..4).
// C is a ramp up to 1 m at z = 4 and belongs to another place, like the stonemason's yard.
//
//   z=4   7 ---- 6
//         |  C   |
//   z=2 3 2 ---- 5
//       | A |  B |
//   z=0 0 1 ---- 4
function lShape(): NavData {
  const v = [
    [0, 0, 0],
    [2, 0, 0],
    [2, 0, 2],
    [0, 0, 2],
    [4, 0, 0],
    [4, 0, 2],
    [4, 1, 4],
    [2, 1, 4],
  ];
  const tri = (...ids: number[]) => ids.flatMap((i) => v[i]!);
  return {
    version: 1,
    agent: { radius: 0.3, height: 1.8, climb: 0.4, slopeDeg: 40 },
    cellSize: 0.15,
    places: ["place.square", "place.yard"],
    verts: v.flat(),
    polys: [
      [0, 1, 2, 3],
      [1, 4, 5, 2],
      [2, 5, 6, 7],
    ],
    neis: [
      [-1, 1, -1, -1],
      [-1, -1, 2, 0],
      [1, -1, -1, -1],
    ],
    place: [0, 0, 1],
    detail: {
      tris: [
        ...tri(0, 1, 2),
        ...tri(0, 2, 3),
        ...tri(1, 4, 5),
        ...tri(1, 5, 2),
        ...tri(2, 5, 6),
        ...tri(2, 6, 7),
      ],
      polyTris: [
        [0, 2],
        [2, 2],
        [4, 2],
      ],
    },
  };
}

const xz = (p: { x: number; z: number }) => [+p.x.toFixed(3), +p.z.toFixed(3)];

describe("NavMesh", () => {
  it("finds the polygon and the ground height", () => {
    const nav = new NavMesh(lShape());
    expect(nav.locate(1, 1)?.poly).toBe(0);
    expect(nav.locate(3, 1)?.poly).toBe(1);
    expect(nav.locate(3, 3)?.poly).toBe(2);
    expect(nav.locate(1, 3)).toBeNull();
    expect(nav.locate(3, 3)?.y).toBeCloseTo(0.5, 5);
    expect(nav.placeOf(2)).toBe("place.yard");
  });

  it("walks straight when it can", () => {
    const nav = new NavMesh(lShape());
    const path = nav.findPath(nav.locate(0.5, 1)!, nav.locate(3.5, 1)!)!;
    expect(path.map(xz)).toEqual([
      [0.5, 1],
      [3.5, 1],
    ]);
  });

  it("turns at the inside corner of the L", () => {
    const nav = new NavMesh(lShape());
    const path = nav.findPath(nav.locate(0.5, 0.5)!, nav.locate(3, 3.5)!)!;
    expect(path.map(xz)).toEqual([
      [0.5, 0.5],
      [2, 2],
      [3, 3.5],
    ]);
    expect(path[2]!.y).toBeCloseTo(0.75, 5);
  });

  it("keeps out of a place whose gate is shut", () => {
    const nav = new NavMesh(lShape());
    nav.setBlockedPlaces(["place.yard"]);
    expect(nav.locate(3, 3)).toBeNull();
    const a = nav.locate(0.5, 0.5)!;
    // a tap inside the yard walks to the nearest open point instead
    const goal = nav.nearest(3, 3)!;
    expect(goal.poly).toBe(1);
    expect(goal.z).toBeLessThanOrEqual(2);
    expect(nav.findPath(a, goal)).not.toBeNull();
    nav.setBlockedPlaces([]);
    expect(nav.locate(3, 3)?.poly).toBe(2);
  });

  it("lets the player out of a place shut while they are in it, then keeps them out", () => {
    const nav = new NavMesh(lShape());
    nav.setBlockedPlaces(["place.yard"]);
    nav.setPlayerPlace("place.yard");
    const inYard = nav.locate(3, 3.5)!;
    expect(inYard.poly).toBe(2);
    const out = nav.findPath(inYard, nav.locate(0.5, 0.5)!);
    expect(out).not.toBeNull();
    expect(nav.moveBy(inYard, 0, -0.4).z).toBeCloseTo(3.1, 5);
    // stepped out into the square: the yard is shut to them now
    nav.setPlayerPlace("place.square");
    expect(nav.locate(3, 3.5)).toBeNull();
    expect(nav.moveBy(nav.locate(3, 1.9)!, 0, 0.4).z).toBeLessThanOrEqual(2);
  });

  it("slides along a wall instead of stopping dead", () => {
    const nav = new NavMesh(lShape());
    const from = nav.locate(1, 0.5)!;
    // down and to the right: the wall at z = 0 stops the z part, the x part goes on
    const to = nav.moveBy(from, 0.4, -0.8);
    expect(to.x).toBeGreaterThan(1.3);
    expect(to.z).toBeGreaterThan(0);
    // straight into the wall: no movement
    const stuck = nav.moveBy(from, 0, -0.8);
    expect(xz(stuck)).toEqual([1, 0.5]);
  });
});
