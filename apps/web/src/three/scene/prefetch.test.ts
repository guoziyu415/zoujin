import { afterEach, describe, expect, it, vi } from "vitest";
import { forget, prefetch } from "./prefetch";

const B = "http://localhost/scenes/0a1b2c3d/";
const files = (pack: string) => ({
  files: [
    { path: "geo.glb", pack: "entry" },
    { path: "tex/hi/floor_base.ktx2", pack: "hi" },
    { path: "tex/std/road_base.ktx2", pack: "entry", shared: "road-common" },
    { path: `tex/std/${pack}_base.ktx2`, pack: "entry" },
  ],
});
const SITE: Record<string, unknown> = {
  [`${B}road-river/index.json`]: {
    packs: [
      { pack: "road-river-calm", act: "act.2" },
      { pack: "road-river-flood", act: "act.4" },
    ],
  },
  [`${B}road-river-calm/scene.json`]: files("calm"),
  [`${B}road-river-flood/scene.json`]: files("flood"),
  [`${B}syracuse-square/scene.json`]: files("square"),
};

function serve(): string[] {
  const got: string[] = [];
  vi.stubGlobal("fetch", (url: string) => {
    got.push(url);
    const body = SITE[url];
    return Promise.resolve(
      url.endsWith(".json")
        ? new Response(JSON.stringify(body), { status: body ? 200 : 404 })
        : new Response("x"),
    );
  });
  return got;
}

afterEach(() => {
  vi.unstubAllGlobals();
  forget();
});

describe("prefetch", () => {
  it("fetches the act's pack: its manifest and entry files, the shared ones from their own pack, not the high tier", async () => {
    const got = serve();
    await prefetch(`${B}road-river/index.json`, "act.4");
    expect(got).toEqual([
      `${B}road-river/index.json`,
      `${B}road-river-flood/scene.json`,
      `${B}road-river-flood/geo.glb`,
      `${B}road-common/tex/std/road_base.ktx2`,
      `${B}road-river-flood/tex/std/flood_base.ktx2`,
    ]);
  });

  it("without the act fetches only the shared files; a file is not asked for twice", async () => {
    const got = serve();
    await prefetch(`${B}road-river/index.json`);
    expect(got.filter((u) => !u.endsWith(".json"))).toEqual([
      `${B}road-common/tex/std/road_base.ktx2`,
    ]);
    await prefetch(`${B}road-river/index.json`, "act.2");
    expect(got.filter((u) => !u.endsWith(".json"))).toEqual([
      `${B}road-common/tex/std/road_base.ktx2`,
      `${B}road-river-calm/geo.glb`,
      `${B}road-river-calm/tex/std/calm_base.ktx2`,
    ]);
  });

  it("a scene in one pack is fetched from its scene.json", async () => {
    const got = serve();
    await prefetch(`${B}syracuse-square/scene.json`);
    expect(got).toContain(`${B}syracuse-square/geo.glb`);
    expect(got).toContain(`${B}road-common/tex/std/road_base.ktx2`);
  });
});
