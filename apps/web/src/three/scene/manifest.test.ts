import { describe, expect, it } from "vitest";
import { sceneBase } from "./manifest";

describe("where a scene's pack is (B-7, api-contract 2.1)", () => {
  it("the manifest's versioned address, version first: the pack's folder under it", () => {
    expect(
      sceneBase("scene.syracuse-square", [
        {
          sceneId: "scene.syracuse-square",
          assetUrl: "/scenes/0a1b2c3d/syracuse-square/scene.json",
        },
      ]),
    ).toBe("/scenes/0a1b2c3d/syracuse-square/");
  });

  it("the old shape (version after the folder), a placeholder or no entry: the unversioned folder", () => {
    for (const assetUrl of [
      "/scenes/syracuse-square/0a1b2c3d/scene.json",
      "/assets/scenes/syracuse-square.0001.glb",
    ])
      expect(
        sceneBase("scene.syracuse-square", [
          { sceneId: "scene.syracuse-square", assetUrl },
        ]),
      ).toBe("/scenes/syracuse-square/");
    expect(sceneBase("scene.syracuse-square")).toBe("/scenes/syracuse-square/");
  });
});
