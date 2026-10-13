import { describe, expect, it } from "vitest";
import { isWorldModule } from "../world-chunk";

describe("world chunk placement is independent of the checkout directory", () => {
  it.each([
    "/home/runner/actions-runner/_work/app/app",
    "/Users/example/home/app",
    "C:\\home\\runner\\app",
  ])("keeps post-processing with its base classes under %s", (root) => {
    expect(isWorldModule(`${root}/apps/web/src/three/post.ts`)).toBe(true);
    expect(
      isWorldModule(
        `${root}/node_modules/three/examples/jsm/postprocessing/OutputPass.js`,
      ),
    ).toBe(true);
    expect(isWorldModule(`${root}/apps/web/src/three/ending/Guard.tsx`)).toBe(
      true,
    );
    expect(isWorldModule(`${root}/apps/web/src/three/home/HomeScene.tsx`)).toBe(
      false,
    );
    expect(isWorldModule(`${root}/apps/web/src/three/cast/CastBody.ts`)).toBe(
      false,
    );
    expect(isWorldModule(`${root}/apps/web/src/three/quality/probe.ts`)).toBe(
      false,
    );
  });
});
