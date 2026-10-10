// The player on the navmesh (frontend-design 8.4, 9.4): tap the ground to walk there (A* + funnel), tap a person to
// walk up to them, WASD / arrow keys to walk; height from the detail mesh; crossing into another place calls the
// store's movePlayer. Plus the scene's other people, as grey stand-ins on their spots.
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import { Group, Raycaster, Vector2, Vector3, type Object3D } from "three";
import { useWorld } from "./dev/fakeStore";
import { makeMannequin } from "./mannequin";
import { rig } from "./rig";
import { planToWorld } from "./scene/frame";
import type { LoadedScene } from "./scene/loadScene";
import { OPENING_VIEWS } from "./scene/openingViews";

const WALK = 1.5; // m/s
const RUN = 3.2;
const TURN = 8; // rad/s towards the walking direction
const TALK_GAP = 1.2; // stop this far in front of the person
const TAP_MS = 300;
const TAP_PX = 10;

const angleTo = (from: number, to: number) =>
  Math.atan2(Math.sin(to - from), Math.cos(to - from));

export function Player({ scene }: { scene: LoadedScene }) {
  const { camera, gl } = useThree();
  const { nav, manifest } = scene;
  const body = useMemo(() => makeMannequin(0.36), []);
  const people = useMemo(() => new Group(), []);
  useEffect(() => {
    rig.people = people;
    return () => {
      rig.people = null;
    };
  }, [people]);

  // start on the store's spot (or the scene's first-screen spot), with the first screen's shot if it has one; the
  // test hook can put the player on another spot ("zoujin:placeat")
  useEffect(() => {
    const placeAt = (name: string, withOpening: boolean) => {
      const spotName = manifest.spots[name] ? name : manifest.playerStartSpot;
      const spot = manifest.spots[spotName]!;
      const at =
        nav.locate(spot.pos[0], spot.pos[2]) ??
        nav.nearest(spot.pos[0], spot.pos[2]);
      if (at) Object.assign(rig.player, at, { yaw: spot.yaw });
      rig.cam.yaw = spot.yaw;
      rig.path = [];
      const v = withOpening ? OPENING_VIEWS[spotName] : undefined;
      const rot = manifest.sun.sceneRotationDeg;
      rig.opening = v
        ? {
            from: planToWorld(...v.from, rot),
            to: planToWorld(...v.to, rot),
            fov: v.fov,
          }
        : null;
      const place = at ? nav.placeOf(at.poly) : spot.place;
      if (place && place !== useWorld.getState().player.place)
        useWorld.getState().movePlayer(place);
    };
    placeAt(useWorld.getState().player.spot ?? manifest.playerStartSpot, true);
    const onPlaceAt = (e: Event) =>
      placeAt((e as CustomEvent<string>).detail, false);
    window.addEventListener("zoujin:placeat", onPlaceAt);
    return () => window.removeEventListener("zoujin:placeat", onPlaceAt);
  }, [nav, manifest]);

  // places that are shut (scene.json places[], api-contract 2.3 places.enabled) and the workshop gate
  useEffect(() => {
    const apply = (places: Record<string, { enabled: boolean }>) => {
      const shut = Object.entries(places)
        .filter(([, p]) => !p.enabled)
        .map(([id]) => id);
      nav.setBlockedPlaces(shut);
      for (const [name, n] of Object.entries(manifest.nodes)) {
        if (!n.movable || !n.place) continue;
        const node = scene.root.getObjectByName(name);
        if (!node) continue;
        node.userData.baseYaw ??= node.rotation.y;
        node.rotation.y =
          (node.userData.baseYaw as number) +
          (shut.includes(n.place)
            ? ((n.closedYawDeg ?? 90) * Math.PI) / 180
            : 0);
      }
    };
    apply(useWorld.getState().places);
    return useWorld.subscribe((s, prev) => {
      if (s.places !== prev.places) apply(s.places);
    });
  }, [nav, manifest, scene.root]);

  // the scene's other people stand on their spots (story moves come with F-0's commits, 8.6)
  useEffect(() => {
    const place = (
      chars: ReturnType<typeof useWorld.getState>["characters"],
    ) => {
      people.clear();
      for (const [id, c] of Object.entries(chars)) {
        const spot = c.spot ? manifest.spots[c.spot] : undefined;
        if (!spot || c.activity === "absent") continue;
        const m = makeMannequin(0.3);
        m.name = id;
        m.userData.character = id;
        m.position.set(...spot.pos);
        m.rotation.y = spot.yaw;
        people.add(m);
      }
    };
    place(useWorld.getState().characters);
    return useWorld.subscribe((s, prev) => {
      if (s.characters !== prev.characters) place(s.characters);
    });
  }, [people, manifest]);

  // taps and drags on the canvas
  useEffect(() => {
    const el = gl.domElement;
    const ray = new Raycaster();
    const ndc = new Vector2();
    let down: {
      id: number;
      x: number;
      y: number;
      t: number;
      lx: number;
    } | null = null;
    const walkTo = (x: number, z: number) => {
      const goal = nav.nearest(x, z);
      const from = nav.locate(
        rig.player.x,
        rig.player.z,
        rig.player.poly,
        rig.player.y,
      );
      if (!goal || !from) return false;
      const path = nav.findPath(from, goal);
      if (!path) return false;
      rig.path = path.slice(1);
      rig.opening = null;
      return true;
    };
    const tap = (cx: number, cy: number) => {
      const r = el.getBoundingClientRect();
      ndc.set(
        ((cx - r.left) / r.width) * 2 - 1,
        -((cy - r.top) / r.height) * 2 + 1,
      );
      ray.setFromCamera(ndc, camera);
      const person = ray.intersectObjects(people.children, true)[0];
      if (person) {
        let o: Object3D | null = person.object;
        while (o && !o.userData.character) o = o.parent;
        if (o) {
          const fx = Math.sin(o.rotation.y);
          const fz = Math.cos(o.rotation.y);
          rig.talking = null;
          if (
            walkTo(o.position.x + fx * TALK_GAP, o.position.z + fz * TALK_GAP)
          )
            rig.talkTo = o.userData.character as string;
          return;
        }
      }
      const hit = ray.intersectObjects(scene.walkable, false)[0];
      if (!hit) return;
      rig.talkTo = null;
      rig.talking = null;
      walkTo(hit.point.x, hit.point.z);
    };
    const onDown = (e: PointerEvent) => {
      if (down) return;
      down = {
        id: e.pointerId,
        x: e.clientX,
        y: e.clientY,
        t: performance.now(),
        lx: e.clientX,
      };
      el.setPointerCapture(e.pointerId);
    };
    const onMove = (e: PointerEvent) => {
      if (!down || e.pointerId !== down.id) return;
      const dx = e.clientX - down.lx;
      down.lx = e.clientX;
      if (Math.hypot(e.clientX - down.x, e.clientY - down.y) < TAP_PX) return;
      rig.cam.yaw -= dx * 0.006;
      rig.cam.lastDrag = performance.now();
      rig.opening = null;
    };
    const onUp = (e: PointerEvent) => {
      if (!down || e.pointerId !== down.id) return;
      const isTap =
        performance.now() - down.t < TAP_MS &&
        Math.hypot(e.clientX - down.x, e.clientY - down.y) < TAP_PX;
      down = null;
      if (isTap) tap(e.clientX, e.clientY);
    };
    const onCancel = () => (down = null);
    // the test hook's walkTo (dev/testHook.ts)
    const onWalkTo = (e: Event) => {
      const [x, , z] = (e as CustomEvent<[number, number, number]>).detail;
      rig.talkTo = null;
      rig.talking = null;
      walkTo(x, z);
    };
    window.addEventListener("zoujin:walkto", onWalkTo);
    const key = (on: boolean) => (e: KeyboardEvent) => {
      if (on) rig.keys.add(e.code);
      else rig.keys.delete(e.code);
    };
    const kd = key(true);
    const ku = key(false);
    el.addEventListener("pointerdown", onDown);
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointercancel", onCancel);
    window.addEventListener("keydown", kd);
    window.addEventListener("keyup", ku);
    return () => {
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      el.removeEventListener("pointercancel", onCancel);
      window.removeEventListener("keydown", kd);
      window.removeEventListener("keyup", ku);
      window.removeEventListener("zoujin:walkto", onWalkTo);
    };
  }, [gl, camera, nav, people, scene.walkable]);

  const tmp = useMemo(() => ({ fwd: new Vector3() }), []);
  useFrame((_, dtRaw) => {
    const dt = Math.min(0.05, dtRaw);
    const p = rig.player;
    const k = rig.keys;
    const f =
      (k.has("KeyW") || k.has("ArrowUp") ? 1 : 0) -
      (k.has("KeyS") || k.has("ArrowDown") ? 1 : 0);
    const s =
      (k.has("KeyD") || k.has("ArrowRight") ? 1 : 0) -
      (k.has("KeyA") || k.has("ArrowLeft") ? 1 : 0);
    let moving = false;
    let wantYaw = p.yaw;
    if (f || s) {
      rig.path = [];
      rig.talkTo = null;
      rig.talking = null;
      rig.opening = null;
      camera.getWorldDirection(tmp.fwd);
      tmp.fwd.y = 0;
      tmp.fwd.normalize();
      const speed =
        (k.has("ShiftLeft") || k.has("ShiftRight") ? RUN : WALK) * dt;
      const l = Math.hypot(f, s);
      // right of the view direction is (-fwd.z, fwd.x)
      const dx = ((tmp.fwd.x * f - tmp.fwd.z * s) / l) * speed;
      const dz = ((tmp.fwd.z * f + tmp.fwd.x * s) / l) * speed;
      Object.assign(p, nav.moveBy(p, dx, dz));
      wantYaw = Math.atan2(dx, dz);
      moving = true;
    } else if (rig.path.length) {
      let step = WALK * dt;
      while (step > 0 && rig.path.length) {
        const goal = rig.path[0]!;
        const dx = goal.x - p.x;
        const dz = goal.z - p.z;
        const d = Math.hypot(dx, dz);
        if (d > 1e-4) wantYaw = Math.atan2(dx, dz);
        if (d <= step) {
          step -= d;
          Object.assign(p, nav.locate(goal.x, goal.z, p.poly, p.y) ?? goal);
          rig.path.shift();
        } else {
          const nx = p.x + (dx / d) * step;
          const nz = p.z + (dz / d) * step;
          Object.assign(p, nav.locate(nx, nz, p.poly, p.y) ?? { x: nx, z: nz });
          step = 0;
        }
      }
      moving = true;
      if (!rig.path.length && rig.talkTo) {
        const o = people.getObjectByName(rig.talkTo);
        if (o) wantYaw = Math.atan2(o.position.x - p.x, o.position.z - p.z);
        rig.talking = rig.talkTo;
        rig.talkTo = null;
      }
    } else if (rig.talking) {
      const o = people.getObjectByName(rig.talking);
      if (o) wantYaw = Math.atan2(o.position.x - p.x, o.position.z - p.z);
    }
    p.yaw += angleTo(p.yaw, wantYaw) * Math.min(1, TURN * dt);
    body.position.set(p.x, p.y, p.z);
    body.rotation.y = p.yaw;
    if (moving) {
      const place = nav.placeOf(p.poly);
      const w = useWorld.getState();
      if (place && place !== w.player.place) w.movePlayer(place);
    }
  }, -3);

  return (
    <>
      <primitive object={body} />
      <primitive object={people} />
    </>
  );
}
