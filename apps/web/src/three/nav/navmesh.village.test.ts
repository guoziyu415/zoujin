// The generated navmesh of the village (F-11; needs a build: assets/pipeline/village/build.sh; skipped without one).
// Plan (x, y) of layout.json is glTF (x, -z) there: rotation 0.
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { sceneDir } from "../../../scene-dir";
import { NavMesh, type NavData } from "./navmesh";

type Spot = { pos: [number, number, number]; place: string };
type Scene = { spots: Record<string, Spot> };

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

const village = load("village");

describe.skipIf(!village)("village", () => {
  const walk = (a: string, b: string) => {
    const { nav, scene } = village!;
    const p = scene.spots[a]!.pos;
    const q = scene.spots[b]!.pos;
    const from = nav.locate(p[0], p[2]);
    const to = nav.locate(q[0], q[2]);
    return from && to ? nav.findPath(from, to) : null;
  };

  // the card's acceptance: from the shepherd boy's start to the pasture, the yard, the bed in the house, the groom's
  // table and the threshing floor
  it.each([
    "sister-sheep",
    "yard-fig",
    "melos-altar",
    "melos-sleep",
    "melos-hut",
    "groom-table",
    "well-side",
    "way.east",
  ])("walks from field-edge to %s", (to) => {
    expect(walk("field-edge", to)).not.toBeNull();
  });

  it("goes up onto the threshing floor", () => {
    const { nav } = village!;
    const from = nav.locate(24, 1.5);
    const to = nav.locate(-26, 10); // plan (-26, -10), the floor's middle
    expect(from && to && nav.findPath(from, to)).toBeTruthy();
  });

  it("has no ground inside the wheat or the vineyard", () => {
    const { nav } = village!;
    for (const [x, y] of [
      [25, -18],
      [-26, -21],
      [-25, 22.5],
    ] as const)
      expect(nav.locate(x, -y), `${x}, ${y}`).toBeNull();
  });
});
