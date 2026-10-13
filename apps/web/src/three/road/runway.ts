// The road's run segments (F-15, ux/scenes/homeward-road.md 4, 5): the treadmill. A run pack's tile repeats every
// tileLengthM along plan +x (assets/pipeline/road/build_road_run.py); here its scrolling nodes are laid end to end and
// moved back under the runners, who run on the spot at the tile's run-* spots. The far land stays put. Set pieces
// (set_* nodes: the field road's feast, brook, tombs, gate; the night road's spring and pass top) come in on the tile
// ahead when the clock reaches them and go once they are behind; the city's far silhouette grows as the distance
// left shrinks. playRun() plays a short segment between two stops, a tap skips it (homeward-road.md, rules for walking 2, 10).
// Lives in scene/extra.ts's lazy chunk.
import { Group, type Object3D, type Scene } from "three";
import { useWorld } from "../../stores/world";
import { reducedMotion } from "../motion";
import type { LoadedScene } from "../scene/loadScene";
import type { RunwayEntry } from "../scene/manifest";
import {
  CITY_AT_M,
  cityDistanceM,
  cityScale,
  due,
  matches,
  wrapBelt,
} from "./runwayMath";

// Melos's run (A-0: 4.9 m/s at 164 steps a minute)
export const RUN_MPS = 4.9;
// how far ahead a set piece comes in (beyond the fog's thick part, so it does not pop) and where it goes
const AHEAD_M = 60;
const BEHIND_M = 40;

// what the page may set: the speed of the road under the runners (reduced motion stands it still) and the clock that
// brings the set pieces (undefined: the world's clock)
export const runway = {
  speedMps: undefined as number | undefined, // undefined = the pack's own (layout runway.speedMps) or RUN_MPS
  minute: undefined as number | undefined,
};
const minuteNow = (): number | undefined =>
  runway.minute ?? useWorld.getState().world?.clock.t;

// ---------------------------------------------------------------- the treadmill on a loaded run pack

type Piece = { node: Object3D; at?: number; from?: number; on: boolean };

export function attachRunway(s: LoadedScene): () => void {
  const r = s.manifest.runway as RunwayEntry;
  const L = r.tileLengthM;
  const belt = new Group();
  belt.name = "runway";
  const pieces = new Map<string, Piece>();
  const tile: Object3D[] = [];
  for (const o of [...s.root.children]) {
    if (o.name.startsWith("set_")) {
      const key = o.name.slice(4);
      const p = r.setPieces?.[key];
      o.visible = false;
      if (key === "city") continue; // stays in the root, moved by the clock
      pieces.set(key, {
        node: o,
        ...(p?.atMinute !== undefined ? { at: p.atMinute } : {}),
        ...(p?.fromMinute !== undefined ? { from: p.fromMinute } : {}),
        on: false,
      });
      belt.add(o);
    } else if (matches(o.name, r.scroll)) tile.push(o);
  }
  // copies of the tile: one behind, three ahead (the default camera rides beside and behind the runners)
  for (let k = -1; k <= 3; k++)
    for (const o of tile) {
      const c = k === 0 ? o : o.clone();
      c.position.x = o.position.x + k * L;
      belt.add(c);
    }
  s.root.add(belt);
  const city = s.root.getObjectByName("set_city") ?? null;

  const speed = () =>
    reducedMotion() ? 0 : (runway.speedMps ?? r.speedMps ?? RUN_MPS);
  let last = performance.now();
  let raf = 0;
  const tick = () => {
    const now = performance.now();
    const dt = Math.min(0.1, (now - last) / 1000);
    last = now;
    const w = wrapBelt(belt.position.x - speed() * dt, L);
    const minute = minuteNow();
    belt.position.x = w.x;
    for (const p of pieces.values()) {
      // the belt moved back a tile: what stands on it keeps its place in the world
      if (w.wraps) p.node.position.x -= w.wraps * L;
      const want = due({ atMinute: p.at, fromMinute: p.from }, minute);
      if (want && !p.on) {
        // in on the first tile start beyond AHEAD_M, in the belt's frame
        p.node.position.x = Math.ceil((AHEAD_M - belt.position.x) / L) * L;
        p.node.visible = p.on = true;
      }
      if (!want) p.on = false;
      if (p.node.visible && p.node.position.x + belt.position.x < -BEHIND_M)
        p.node.visible = false;
    }
    if (city) {
      const d = minute === undefined ? Infinity : cityDistanceM(minute);
      city.visible = due({ fromMinute: r.setPieces?.city?.fromMinute }, minute);
      if (city.visible) {
        city.position.x = CITY_AT_M;
        city.scale.setScalar(cityScale(d));
      }
    }
    raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);
  return () => {
    cancelAnimationFrame(raf);
    s.root.remove(belt);
  };
}

// a short segment between two stops: shown on top of the current scene (hidden meanwhile) with its run-player spot
// at `anchor`; a tap (or reduced motion) ends it at once. The 3D layer only reads the store (frontend-design 4): the
// caller moves the clock, so the sun and the time label go from the leaving time to the arriving time, by
// onProgress (0..1, every frame), and applies the held commit once this resolves (homeward-road.md 10).
export async function playRun(opts: {
  base: string; // the destination scene's folder (manifest.ts sceneBase): the run pack is its sibling
  pack: string; // road-run-r1, -r2, -r2s, -r3
  seconds?: number; // 15 to 25 (homeward-road.md 5)
  three: Scene;
  hide?: Object3D | null; // the stop being left
  anchor?: [number, number, number];
  onBytes?: (n: number) => void;
  onProgress?: (f: number) => void;
}): Promise<void> {
  const { load, dispose } = await import("../scene/extra");
  const base = opts.base.replace(/[^/]+\/$/, `${opts.pack}/`);
  const s = await load(base, undefined, opts.onBytes ?? (() => {}), opts.three);
  const spot = s.manifest.spots["run-player"]?.pos ?? [0, 0, 0];
  if (opts.anchor)
    s.root.position.set(
      opts.anchor[0] - spot[0],
      opts.anchor[1] - spot[1],
      opts.anchor[2] - spot[2],
    );
  if (opts.hide) opts.hide.visible = false;
  opts.three.add(s.root);
  const ms = (opts.seconds ?? 20) * 1000;
  await new Promise<void>((done) => {
    let raf = 0;
    const finish = () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointerdown", finish);
      opts.onProgress?.(1);
      done();
    };
    if (reducedMotion()) return finish();
    window.addEventListener("pointerdown", finish, { once: true });
    const t0 = performance.now();
    const step = () => {
      const f = Math.min(1, (performance.now() - t0) / ms);
      opts.onProgress?.(f);
      if (f < 1) raf = requestAnimationFrame(step);
      else finish();
    };
    step();
  });
  opts.three.remove(s.root);
  if (opts.hide) opts.hide.visible = true;
  dispose(s);
}
