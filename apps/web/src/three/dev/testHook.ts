// window.__zoujin with ?test: what the Playwright checks drive and read (apps/web/tests/e2e). Not loaded otherwise.
import { Vector3 } from "three";
import { peek } from "../../telemetry/telemetry";
import { lighting } from "../Lighting";
import { frameStats } from "../PostFX";
import type { Level } from "../quality/levels";
import { quality, useQuality, type AssetTier } from "../quality/quality";
import { rig } from "../rig";
import { planToWorld, type Vec3 } from "../scene/frame";
import { highTier, loadInfo } from "../World";
import { play } from "../../net/play";
import { usePlayer } from "../../stores/player";
import { useWorld } from "../../stores/world";
import { sandbox, type SandboxCharacter } from "./sandbox";

type Plan = [number, number, number]; // layout.json plan x, y and height

const nextFrames = (n: number) =>
  new Promise<void>((resolve) => {
    const until = frameStats.frames + n;
    const tick = () =>
      frameStats.frames >= until ? resolve() : requestAnimationFrame(tick);
    tick();
  });

// project a world point into the canvas, in CSS pixels of the page (for real taps, page.mouse.click)
function toPage(v: Vector3): [number, number] | null {
  const cam = rig.camera;
  const canvas = document.querySelector("canvas");
  if (!cam || !canvas) return null;
  const r = canvas.getBoundingClientRect();
  const p = v.clone().project(cam);
  if (p.z > 1 || Math.abs(p.x) > 1 || Math.abs(p.y) > 1) return null;
  return [
    r.left + ((p.x + 1) / 2) * r.width,
    r.top + ((1 - p.y) / 2) * r.height,
  ];
}

export function installTestHook(): void {
  // every move the 3D sends (play.move), in order: the checks read it with or without a story open
  const moves: string[] = [];
  const move = play.move;
  play.move = (place: string) => {
    moves.push(place);
    move(place);
  };
  const rot = () => loadInfo.sceneRotationDeg;
  const toWorld = ([x, y, h]: Plan): Vec3 => planToWorld(x, y, h, rot());
  Object.assign(window, {
    __zoujin: {
      load: () => ({ ...loadInfo }),
      frame: () => ({ ...frameStats }),
      frames: nextFrames,
      setClock: async (t: number) => {
        sandbox.setClock(t);
        lighting.settle();
        await nextFrames(2);
      },
      // a fixed camera in plan coordinates (layout.json), e.g. S7's views; null goes back to the follow camera
      setView: async (from: Plan | null, to?: Plan, fov = 60) => {
        rig.fixedView =
          from && to ? { from: toWorld(from), to: toWorld(to), fov } : null;
        await nextFrames(2);
      },
      // the same in glTF world coordinates (scene.json spots)
      setWorldView: async (from: Vec3, to: Vec3, fov = 60) => {
        rig.fixedView = { from, to, fov };
        await nextFrames(2);
      },
      // the crowd (?crowd=N, F-4): what it is doing, and the staging's verbs
      crowd: async (
        verb?: "wave" | "cheer" | "part" | "show" | "hide",
        arg?: [number, number] | [number, number][],
      ) => {
        const { crowdRef } = await import("../crowd/CrowdLayer");
        const c = crowdRef.current;
        if (!c) return null;
        if (verb === "wave") c.wave(arg as [number, number]);
        if (verb === "cheer") c.cheer();
        if (verb === "part") c.part(arg as [number, number][]);
        if (verb === "show" || verb === "hide") c.visible = verb === "show";
        return {
          count: c.people.length,
          meshes: c.meshes.filter(Boolean).length,
          clips: c.clips(),
          started: { ...c.started },
          at: c.people.map((p) => p.at),
          pack: c.fromPack,
        };
      },
      player: () => ({
        ...rig.player,
        place: usePlayer.getState().place,
        walking: rig.path.length > 0,
        talking: rig.talking,
        near: usePlayer.getState().nearCharacter,
      }),
      moves: () => [...moves],
      clock: () => useWorld.getState().world?.clock.t ?? null,
      setPlaceEnabled: (place: string, on: boolean) =>
        sandbox.setPlaceEnabled(place, on),
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
      // the scene's other people, in the sandbox (a story has them from the snapshot and the commits)
      setCharacters: async (chars: Record<string, SandboxCharacter>) => {
        sandbox.setCharacters(chars);
        await nextFrames(2);
      },
      // where on the page to tap for a spot / plan point on the ground, or a character (their chest)
      tapPoint: (to: string | [number, number]) => {
        const at =
          typeof to === "string"
            ? loadInfo.spots[to]
            : toWorld([to[0], to[1], 0]);
        return at ? toPage(new Vector3(...at)) : null;
      },
      tapCharacter: (id: string) => {
        const o = rig.people?.getObjectByName(id);
        return o ? toPage(o.position.clone().setY(o.position.y + 1.2)) : null;
      },
      // is any of a 1.7 m person standing on this spot inside the current camera's view
      inView: (spot: string) => {
        const cam = rig.camera;
        const at = loadInfo.spots[spot];
        if (!cam || !at) return null;
        return [0, 0.85, 1.7].some((up) => {
          const v = new Vector3(at[0], at[1] + up, at[2]).project(cam);
          return Math.abs(v.x) <= 1 && Math.abs(v.y) <= 1 && v.z < 1;
        });
      },
      // walk as if the ground there had been tapped (Player.tsx does the same on a tap): a spot name or plan x, y
      // the quality level, the probe's result and the telemetry waiting to be sent
      quality: () => ({
        ...useQuality.getState(),
        probe: quality.probe,
        running: !!quality.governor,
      }),
      telemetry: () => peek().map((e) => ({ ...e })),
      force: async (level: Level, tier?: AssetTier) => {
        quality.force(level, tier);
        await nextFrames(4);
      },
      fetchHigh: () => highTier.fetch(),
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
