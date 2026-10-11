// The player on the navmesh (frontend-design 8.4, 9.4): tap the ground to walk there (A* + funnel), tap a person to
// walk up to them (a talkable one: focus goes at the tap, api-contract 3.2), WASD / arrow keys to walk; height from the
// detail mesh. Crossing into another place of the scene sends move (3.8); the closest talkable character within 8 m
// gets near, 12 m away far; walking off from the one in the conversation ends it (unfocus walk_away). Where the server
// puts the player (the snapshot, a commit's patch.player, a refused move) they stand, without walking.
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import { Group, Raycaster, Vector2, Vector3, type Object3D } from "three";
import { play } from "../net/play";
import { usePlayer } from "../stores/player";
import { useWorld } from "../stores/world";
import { castName } from "./cast/cast";
import type { CastBody } from "./cast/CastBody";
import { makeMannequin } from "./mannequin";
import { useQuality } from "./quality/quality";
import { NEAR_M, pickNear } from "./nearby";
import { rig } from "./rig";
import { planToWorld } from "./scene/frame";
import type { LoadedScene } from "./scene/loadScene";
import { OPENING_VIEWS } from "./scene/openingViews";

const WALK = 1.5; // m/s
const RUN = 3.2;
const TURN = 8; // rad/s towards the walking direction
const TALK_GAP = 1.2; // stop this far from the person, on the player's side
const TAP_MS = 300;
const TAP_PX = 10;
const LOOK_MS = 250; // how often near / far and the distances are worked out

const angleTo = (from: number, to: number) =>
  Math.atan2(Math.sin(to - from), Math.cos(to - from));

const personAt = (o: Object3D | null): string | null => {
  while (o && !o.userData.character) o = o.parent;
  return (o?.userData.character as string | undefined) ?? null;
};

export function Player({ scene }: { scene: LoadedScene }) {
  const { camera, gl } = useThree();
  const { nav, manifest } = scene;
  // the player's role in its realistic body where F-16 built one (the apprentice, the shepherd boy), else the stand-in
  const stand = useMemo(() => makeMannequin(0.36), []);
  const body = useMemo(() => {
    const g = new Group();
    g.add(stand);
    return g;
  }, [stand]);
  const cast = useMemo(
    () => ({ body: null as CastBody | null, x: 0, z: 0 }),
    [],
  );
  const roleId = useWorld((s) => s.world?.player.roleId ?? null);
  useEffect(() => {
    const name = roleId ? castName(roleId) : null;
    if (!name || !roleId) return;
    let live = true;
    void import("./cast/CastBody").then(({ CastBody }) => {
      if (!live) return;
      cast.body = new CastBody(
        gl,
        name,
        roleId,
        body,
        stand,
        () => useQuality.getState().assetTier === "high",
      );
    });
    return () => {
      live = false;
      cast.body?.dispose();
      cast.body = null;
      if (stand.parent !== body) body.add(stand);
    };
  }, [roleId, gl, body, stand, cast]);

  // the walk to a point / a person, shared by taps, 「近くの人」, the focus and the test hook
  const go = useMemo(() => {
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
    const stopTalking = () => {
      rig.talkTo = null;
      rig.talking = null;
      rig.faceTo = null;
    };
    // up to TALK_GAP from them on the player's side; they stop and turn to the player (People.tsx)
    const toPerson = (id: string, talk: boolean) => {
      const o = rig.people?.getObjectByName(id);
      if (!o) return false;
      stopTalking();
      const dx = rig.player.x - o.position.x;
      const dz = rig.player.z - o.position.z;
      const d = Math.hypot(dx, dz);
      if (d > TALK_GAP + 0.3) {
        const k = TALK_GAP / d;
        if (!walkTo(o.position.x + dx * k, o.position.z + dz * k)) return false;
      } else rig.path = [];
      if (talk) rig.talkTo = id;
      else rig.faceTo = id;
      return true;
    };
    return { walkTo, toPerson, stopTalking };
  }, [nav]);

  // where the server put the player: a spot (with the first screen's shot the first time), or anywhere in a place as
  // near as possible (a refused move). Not a move (api-contract 3.8). The test hook puts them on spots too.
  useEffect(() => {
    const stand = (
      at: { poly: number; x: number; y: number; z: number },
      yaw: number,
    ) => {
      Object.assign(rig.player, at, { yaw });
      rig.path = [];
      rig.cutCamera = true;
      go.stopTalking();
      const place = nav.placeOf(at.poly);
      nav.setPlayerPlace(place);
      if (place && place !== usePlayer.getState().place)
        usePlayer.setState({ place });
    };
    const placeAt = (name: string, place?: string, withOpening = false) => {
      const spotName = manifest.spots[name]
        ? name
        : ((place && manifest.startSpots?.[place]) ?? manifest.playerStartSpot);
      const spot = manifest.spots[spotName]!;
      const at =
        nav.locate(spot.pos[0], spot.pos[2]) ??
        nav.nearest(spot.pos[0], spot.pos[2]);
      if (!at) return;
      rig.cam.yaw = spot.yaw;
      const v = withOpening ? OPENING_VIEWS[spotName] : undefined;
      const rot = manifest.sun.sceneRotationDeg;
      rig.opening = v
        ? {
            from: planToWorld(...v.from, rot),
            to: planToWorld(...v.to, rot),
            fov: v.fov,
          }
        : null;
      stand(at, spot.yaw);
    };
    const placeIn = (place: string) => {
      nav.setPlayerPlace(place); // open to them even if it has just shut
      const at = nav.nearest(rig.player.x, rig.player.z, place);
      if (at) stand(at, rig.player.yaw);
      else placeAt("", place);
    };
    const first = usePlayer.getState().placed;
    let n = first?.n ?? 0;
    placeAt(
      first?.spot ??
        useWorld.getState().world?.player.spot ??
        manifest.playerStartSpot,
      first?.place,
      true,
    );
    const off = usePlayer.subscribe((s) => {
      const p = s.placed;
      if (!p || p.n === n) return;
      n = p.n;
      if (p.spot) placeAt(p.spot, p.place);
      else placeIn(p.place);
    });
    const onPlaceAt = (e: Event) => placeAt((e as CustomEvent<string>).detail);
    window.addEventListener("zoujin:placeat", onPlaceAt);
    return () => {
      off();
      window.removeEventListener("zoujin:placeat", onPlaceAt);
    };
  }, [nav, manifest, go]);

  // places that are shut (scene.json places[], api-contract 2.3 places.enabled) and the workshop gate
  useEffect(() => {
    const apply = (places: Record<string, { enabled: boolean }>) => {
      const shut = Object.entries(places)
        .filter(([, p]) => !p.enabled)
        .map(([id]) => id);
      nav.setBlockedPlaces(shut);
      // a walk planned into a place that just shut stops where it is (the player's own place stays open, navmesh.ts)
      if (rig.path.some((pt) => !nav.isOpen(pt.poly))) {
        rig.path = [];
        rig.talkTo = null;
      }
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
    apply(useWorld.getState().world?.places ?? {});
    return useWorld.subscribe((s, prev) => {
      const places = s.world?.places;
      if (places && places !== prev.world?.places) apply(places);
    });
  }, [nav, manifest, scene.root]);

  // someone picked in 「近くの人」 (focus from the HUD): walk up to them; the conversation ended: stop framing it.
  // A thing picked there: walk to its spot.
  useEffect(
    () =>
      usePlayer.subscribe((s, prev) => {
        if (s.focusCharacter !== prev.focusCharacter) {
          const id = s.focusCharacter;
          if (!id) go.stopTalking();
          else if (rig.talkTo !== id && rig.talking !== id)
            go.toPerson(id, true);
        }
        if (s.goal && s.goal !== prev.goal) {
          const spot = manifest.spots[s.goal.spot];
          if (spot) {
            go.stopTalking();
            go.walkTo(spot.pos[0], spot.pos[2]);
          }
        }
      }),
    [go, manifest],
  );

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
    const tap = (cx: number, cy: number) => {
      const r = el.getBoundingClientRect();
      ndc.set(
        ((cx - r.left) / r.width) * 2 - 1,
        -((cy - r.top) / r.height) * 2 + 1,
      );
      ray.setFromCamera(ndc, camera);
      const hitPerson = rig.people
        ? ray.intersectObjects(rig.people.children, true)[0]
        : undefined;
      const id = personAt(hitPerson?.object ?? null);
      if (id) {
        const talkable =
          useWorld.getState().world?.characters[id]?.talkable ?? false;
        // focus at the tap, not on arrival: the server starts their session while the player walks (3.2)
        if (go.toPerson(id, talkable) && talkable)
          if (usePlayer.getState().focusCharacter !== id) play.focus(id);
        return;
      }
      const hit = ray.intersectObjects(scene.walkable, false)[0];
      if (!hit) return;
      go.stopTalking();
      go.walkTo(hit.point.x, hit.point.z);
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
      go.stopTalking();
      go.walkTo(x, z);
    };
    window.addEventListener("zoujin:walkto", onWalkTo);
    const key = (on: boolean) => (e: KeyboardEvent) => {
      // the space bar is the talk key's (ux-design 6.2); typing into the text field doesn't walk
      if (e.target instanceof HTMLInputElement) return;
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
  }, [gl, camera, go, scene.walkable]);

  // near / far, the distances for 「近くの人」, walking off from the conversation: a few times a second
  const look = useMemo(
    () => ({
      at: 0,
      near: null as string | null,
      dist: {} as Record<string, number>,
    }),
    [],
  );
  useEffect(
    () => () => {
      if (look.near) play.far(look.near);
      look.near = null;
    },
    [look],
  );
  const lookAround = (now: number) => {
    if (now - look.at < LOOK_MS) return;
    look.at = now;
    const chars = useWorld.getState().world?.characters ?? {};
    const p = rig.player;
    const all: Record<string, number> = {};
    const talkable: Record<string, number> = {};
    for (const o of rig.people?.children ?? []) {
      const id = personAt(o);
      if (!id) continue;
      const d = Math.hypot(o.position.x - p.x, o.position.z - p.z);
      all[id] = d;
      if (chars[id]?.talkable) talkable[id] = d;
    }
    const next = pickNear(look.near, talkable);
    if (next !== look.near) {
      if (look.near) play.far(look.near);
      if (next) play.near(next);
      look.near = next;
    }
    const whole = Object.fromEntries(
      Object.entries(all).map(([id, d]) => [id, Math.round(d)]),
    );
    const before = usePlayer.getState().distances;
    if (
      Object.keys(whole).length !== Object.keys(before).length ||
      Object.entries(whole).some(([id, d]) => before[id] !== d)
    )
      usePlayer.setState({ distances: whole });
    // the player walked off from the one they were talking to (not on their way to them)
    const focus = usePlayer.getState().focusCharacter;
    const d = focus ? all[focus] : undefined;
    if (focus && d !== undefined && d > NEAR_M && rig.talkTo !== focus)
      play.walkAway();
  };

  const tmp = useMemo(() => ({ fwd: new Vector3() }), []);
  useFrame((_, dtRaw) => {
    body.visible = !rig.staged; // in the ending the staging stands the player (ending/Staging.tsx)
    if (rig.staged) return;
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
    const faceOf = (id: string | null) => {
      const o = id ? rig.people?.getObjectByName(id) : undefined;
      if (o) wantYaw = Math.atan2(o.position.x - p.x, o.position.z - p.z);
    };
    if (f || s) {
      rig.path = [];
      go.stopTalking();
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
        faceOf(rig.talkTo);
        rig.talking = rig.talkTo;
        rig.talkTo = null;
      }
    } else if (rig.talking ?? rig.faceTo) {
      faceOf(rig.talking ?? rig.faceTo);
    } else if (rig.talkTo) {
      // already standing next to them when picked
      rig.talking = rig.talkTo;
      rig.talkTo = null;
    }
    p.yaw += angleTo(p.yaw, wantYaw) * Math.min(1, TURN * dt);
    body.position.set(p.x, p.y, p.z);
    body.rotation.y = p.yaw;
    if (cast.body) {
      const v = dt > 0 ? Math.hypot(p.x - cast.x, p.z - cast.z) / dt : 0;
      cast.body.update(dt, v, 0);
    }
    cast.x = p.x;
    cast.z = p.z;
    if (moving) {
      const place = nav.placeOf(p.poly);
      nav.setPlayerPlace(place);
      if (place && place !== usePlayer.getState().place) play.move(place);
    }
    lookAround(performance.now());
  }, -3);

  return <primitive object={body} />;
}
