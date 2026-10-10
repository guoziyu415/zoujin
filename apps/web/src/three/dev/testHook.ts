// window.__zoujin with ?test: what the Playwright checks drive and read (apps/web/tests/e2e). Not loaded otherwise.
import { lighting } from "../Lighting";
import { frameStats } from "../PostFX";
import { rig } from "../rig";
import { planToWorld, type Vec3 } from "../scene/frame";
import { loadInfo } from "../World";
import { useWorld } from "./fakeStore";

type Plan = [number, number, number]; // layout.json plan x, y and height

const nextFrames = (n: number) =>
  new Promise<void>((resolve) => {
    const until = frameStats.frames + n;
    const tick = () =>
      frameStats.frames >= until ? resolve() : requestAnimationFrame(tick);
    tick();
  });

export function installTestHook(): void {
  const rot = () => loadInfo.sceneRotationDeg;
  const toWorld = ([x, y, h]: Plan): Vec3 => planToWorld(x, y, h, rot());
  Object.assign(window, {
    __zoujin: {
      load: () => ({ ...loadInfo }),
      frame: () => ({ ...frameStats }),
      frames: nextFrames,
      setClock: async (t: number) => {
        useWorld.getState().setClock(t);
        lighting.settle();
        await nextFrames(2);
      },
      // a fixed camera in plan coordinates (layout.json), e.g. S7's views; null goes back to the follow camera
      setView: async (from: Plan | null, to?: Plan, fov = 60) => {
        rig.fixedView =
          from && to ? { from: toWorld(from), to: toWorld(to), fov } : null;
        await nextFrames(2);
      },
      player: () => ({
        ...rig.player,
        place: useWorld.getState().player.place,
        walking: rig.path.length > 0,
      }),
      moves: () => [...useWorld.getState().moves],
      setPlaceEnabled: (place: string, on: boolean) =>
        useWorld.getState().setPlaceEnabled(place, on),
      // put the player on one of the scene's spots (no walking, no first-screen shot)
      placeAt: async (spot: string) => {
        window.dispatchEvent(
          new CustomEvent("zoujin:placeat", { detail: spot }),
        );
        await nextFrames(2);
      },
      // walk as if the ground there had been tapped (Player.tsx does the same on a tap): a spot name or plan x, y
      walkTo: (to: string | [number, number]) => {
        const at =
          typeof to === "string"
            ? loadInfo.spots[to]
            : toWorld([to[0], to[1], 0]);
        if (at)
          window.dispatchEvent(
            new CustomEvent("zoujin:walkto", { detail: at }),
          );
      },
    },
  });
}
