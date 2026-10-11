// The generated navmeshes of the road's river (F-10; needs a build: assets/pipeline/road/build.sh; skipped without
// one). Plan (x, y) of layout.json is glTF (x, -z) there: rotation 0.
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { sceneDir } from "../../../scene-dir";
import { NavMesh, type NavData } from "./navmesh";

type Spot = { pos: [number, number, number]; place: string };
type Scene = { playerStartSpot: string; spots: Record<string, Spot> };

function load(pack: string): { nav: NavMesh; scene: Scene } | null {
  const dir = sceneDir(pack);
  if (!fs.existsSync(path.join(dir, "nav.json"))) return null;
  const read = (f: string): unknown =>
    JSON.parse(fs.readFileSync(path.join(dir, f), "utf8"));
  return {
    nav: new NavMesh(read("nav.json") as NavData),
    scene: read("scene.json") as Scene,
  };
}

const walk = (nav: NavMesh, a: Spot, b: Spot) => {
  const from = nav.locate(a.pos[0], a.pos[2]);
  const to = nav.locate(b.pos[0], b.pos[2]);
  return from && to ? nav.findPath(from, to) : null;
};

const calm = load("road-river-calm");
const flood = load("road-river-flood");

describe.skipIf(!calm)("river, act 2 (calm)", () => {
  it("crosses the bridge from the east landing to the west road", () => {
    const { nav, scene } = calm!;
    const p = walk(nav, scene.spots["road-east"]!, scene.spots["road-west"]!);
    expect(p).not.toBeNull();
    // straight over the deck: about the 33 m between the landings, and never off the deck (plan |y| < 1.1) above
    // the channel
    const len = p!.reduce(
      (acc, q, i) =>
        i ? acc + Math.hypot(q.x - p![i - 1]!.x, q.z - p![i - 1]!.z) : 0,
      0,
    );
    expect(len).toBeLessThan(40);
    for (const q of p!.filter((q) => q.x > -1 && q.x < 7))
      expect(Math.abs(q.z)).toBeLessThan(1.1);
  });

  it("goes down to the water where Melos washes", () => {
    const { nav, scene } = calm!;
    expect(
      walk(nav, scene.spots["road-east"]!, scene.spots["melos-wash"]!),
    ).not.toBeNull();
  });

  it("has no ground in the channel", () => {
    expect(calm!.nav.locate(2.5, 4)).toBeNull();
    expect(calm!.nav.locate(2.5, -6)).toBeNull();
  });
});

describe.skipIf(!flood)("river, act 4 (flood)", () => {
  it("walks from the west landing to the bridgehead, on the drowned road", () => {
    const { nav, scene } = flood!;
    expect(
      walk(nav, scene.spots["road-west"]!, scene.spots["melos-bridgehead"]!),
    ).not.toBeNull();
  });

  it("can't go into the river (plan x > -5)", () => {
    const { nav, scene } = flood!;
    for (const [x, y] of [
      [-3, 0],
      [3, 0],
      [3, 12],
      [8, -10],
    ] as const)
      expect(nav.locate(x, -y), `${x}, ${y}`).toBeNull();
    // and the far bank is not reachable on foot: the crossing is a set piece
    expect(
      walk(nav, scene.spots["road-west"]!, scene.spots["far-bank"]!),
    ).toBeNull();
  });
});
