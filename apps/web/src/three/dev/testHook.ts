// window.__zoujin with ?test: what the Playwright checks drive and read (apps/web/tests/e2e). Not loaded otherwise.
import { Vector3 } from "three";
import { peek } from "../../telemetry/telemetry";
import { lighting } from "../Lighting";
import { frameStats } from "../PostFX";
import type { Level } from "../quality/levels";
import { quality, useQuality } from "../quality/quality";
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
      // turn the follow camera towards a plan point (as a sideways drag would) and cut to it
      follow: async (towards: [number, number]) => {
        const [x, , z] = toWorld([towards[0], towards[1], 0]);
        rig.cam.yaw = Math.atan2(x - rig.player.x, z - rig.player.z);
        rig.cam.lastDrag = performance.now();
        rig.opening = null;
        rig.fixedView = null;
        rig.cutCamera = true;
        await nextFrames(3);
      },
      // the follow camera's framing in CSS pixels: a 1.7 m person at the player and 15 m further on, and the horizon
      onScreen: () => {
        const cam = rig.camera;
        if (!cam) return null;
        const h = document.querySelector("canvas")?.clientHeight ?? innerHeight;
        const y = (v: Vector3) => ((1 - v.clone().project(cam).y) / 2) * h;
        const tall = (v: Vector3) => y(v) - y(v.clone().setY(v.y + 1.7));
        const p = rig.player;
        const fwd = cam.getWorldDirection(new Vector3()).setY(0).normalize();
        const feet = new Vector3(p.x, p.y, p.z);
        return {
          playerPx: tall(feet),
          aheadPx: tall(feet.clone().addScaledVector(fwd, 15)),
          horizon: y(cam.position.clone().addScaledVector(fwd, 1e5)) / h,
        };
      },
      // walk as if the ground there had been tapped (Player.tsx does the same on a tap): a spot name or plan x, y
      // the quality level, the probe's result and the telemetry waiting to be sent
      quality: () => ({
        ...useQuality.getState(),
        probe: quality.probe,
        running: !!quality.governor,
      }),
      telemetry: () => peek().map((e) => ({ ...e })),
      force: async (level: Level) => {
        quality.force(level);
        await nextFrames(4);
      },
      cut: async () => {
        quality.cut(performance.now());
        await nextFrames(2);
      },
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
