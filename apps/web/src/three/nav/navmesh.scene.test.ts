// The generated plaza navmesh (needs a build: assets/pipeline/plaza/build.sh; skipped without one).
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { sceneDir } from "../../../scene-dir";
import { NavMesh, type NavData } from "./navmesh";

const dir = sceneDir("syracuse-square");
const have = fs.existsSync(path.join(dir, "nav.json"));

type Spot = { pos: [number, number, number]; place: string };

describe.skipIf(!have)("plaza navmesh", () => {
  const nav = have
    ? new NavMesh(
        JSON.parse(
          fs.readFileSync(path.join(dir, "nav.json"), "utf8"),
        ) as NavData,
      )
    : null!;
  const scene = have
    ? (JSON.parse(fs.readFileSync(path.join(dir, "scene.json"), "utf8")) as {
        playerStartSpot: string;
        spots: Record<string, Spot>;
      })
    : null!;

  it("reaches every spot from the first screen, on the ground", () => {
    const start = scene.spots[scene.playerStartSpot]!;
    const from = nav.locate(start.pos[0], start.pos[2])!;
    expect(from).not.toBeNull();
    for (const [name, s] of Object.entries(scene.spots)) {
      const to = nav.locate(s.pos[0], s.pos[2]);
      expect(to, name).not.toBeNull();
      expect(Math.abs(to!.y - s.pos[1]), name).toBeLessThan(0.3);
      expect(nav.placeOf(to!.poly), name).toBe(s.place);
      const p = nav.findPath(from, to!);
      expect(p, name).not.toBeNull();
      const len = p!.reduce(
        (acc, q, i) =>
          i ? acc + Math.hypot(q.x - p![i - 1]!.x, q.z - p![i - 1]!.z) : 0,
        0,
      );
      // never longer than walking around the whole plaza
      expect(len, name).toBeLessThan(200);
    }
  });

  it("can't get into the workshop yard while its gate is shut", () => {
    nav.setBlockedPlaces(["place.stonemason-workshop"]);
    const start = scene.spots[scene.playerStartSpot]!;
    const yard = scene.spots["workshop-yard"]!;
    expect(nav.locate(yard.pos[0], yard.pos[2])).toBeNull();
    const goal = nav.nearest(yard.pos[0], yard.pos[2])!;
    expect(nav.placeOf(goal.poly)).not.toBe("place.stonemason-workshop");
    expect(
      nav.findPath(nav.locate(start.pos[0], start.pos[2])!, goal),
    ).not.toBeNull();
    nav.setBlockedPlaces([]);
  });
});
