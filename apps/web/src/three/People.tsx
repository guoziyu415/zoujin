// The scene's characters (frontend-design 8.3, 8.6), the realistic ones where F-16 built them (cast/CastBody.ts: grey
// stand-ins until their files arrive, and for everyone not built yet): standing on the spots
// the server gives (world.characters[id].place / spot / activity). A new spot is a story move: they walk there on the
// navmesh, or run when the activity says so; leaving the scene they walk to the nearest exit spot (way.*) first.
// Picked by the player they stop and face them until the conversation ends (ux-design 6.5). Named groups with a
// cast pack have a visible representative; the narrative state still describes the full group. Other crowds stay
// in F-4; "absent" isn't drawn. Moving about on the spot uses the real characters' animations.
import type { Api } from "@zoujin/contracts";
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import { Group } from "three";
import { flags } from "../app/flags";
import { usePlayer } from "../stores/player";
import { useWorld } from "../stores/world";
import { levels } from "../audio/engine";
import { useQuality } from "./quality/quality";
import { castName } from "./cast/cast";
import { groupPlacement, type GroupCandidate } from "./cast/groupPlacement";
import { crowdCount } from "./crowd/presence";
import { scatter } from "./crowd/scatter";
import { crowdSpec } from "./crowd/zone";
import type { CastBody } from "./cast/CastBody";
import { makeMannequin } from "./mannequin";
import type { NavPoint } from "./nav/navmesh";
import { rig } from "./rig";
import type { LoadedScene } from "./scene/loadScene";

const WALK = 1.4; // m/s
const RUN = 3.2;
const TURN = 6; // rad/s

type Person = {
  obj: Group;
  body: CastBody | null; // the realistic body (F-16), once its code has loaded
  at: NavPoint;
  yaw: number;
  spot: string;
  path: NavPoint[];
  speed: number;
  endYaw: number | null; // the spot's facing, once they get there
  leaving: boolean; // walking out of the scene: gone at the end of the path
};

const angleTo = (from: number, to: number) =>
  Math.atan2(Math.sin(to - from), Math.cos(to - from));

const drawn = (c: Api.CharacterPresence) =>
  c.activity !== "absent" && (c.group ? castName(c.id) !== null : !!c.spot);

export function People({ scene }: { scene: LoadedScene }) {
  const { nav, manifest } = scene;
  const gl = useThree((s) => s.gl);
  const group = useMemo(() => new Group(), []);
  const people = useMemo(() => new Map<string, Person>(), []);

  useEffect(() => {
    rig.people = group;
    return () => {
      rig.people = null;
    };
  }, [group]);

  useEffect(() => {
    const noRoom = new Set<string>();
    const pointAt = (spot: string): [NavPoint, number] | null => {
      const s = manifest.spots[spot];
      if (!s) return null;
      const at = nav.locate(s.pos[0], s.pos[2], s.poly, s.pos[1], true) ?? {
        poly: s.poly,
        x: s.pos[0],
        y: s.pos[1],
        z: s.pos[2],
      };
      return [at, s.yaw];
    };
    const remove = (id: string) => {
      const p = people.get(id);
      if (p) {
        group.remove(p.obj);
        p.body?.dispose();
      }
      people.delete(id);
    };
    const walk = (
      p: Person,
      id: string,
      spot: string,
      to: NavPoint,
      run: boolean,
      entering = false,
    ) => {
      const r = rig.route?.(id, spot, entering);
      p.path = [];
      let from = p.at;
      const goals = (r?.via ?? []).map(([x, z]) =>
        nav.locate(x, z, from.poly, from.y, true),
      );
      for (const goal of [...goals, to]) {
        if (!goal) continue;
        const path = nav.findPath(from, goal, true);
        p.path.push(...(path ? path.slice(1) : [goal]));
        from = goal;
      }
      p.speed = r?.speed ?? (id === "char.old-man" ? 0.65 : run ? RUN : WALK);
    };
    const sync = (chars: Record<string, Api.CharacterPresence>) => {
      const stableOccupied: Pick<NavPoint, "x" | "z">[] = [];
      for (const c of Object.values(chars)) {
        if (!c.group && c.spot && c.activity !== "absent") {
          const at = pointAt(c.spot)?.[0];
          if (at) stableOccupied.push(at);
          const actual = people.get(c.id)?.at;
          if (actual) stableOccupied.push(actual);
        }
      }
      // Reserve exactly the seeded F-4 crowd positions before its async mesh pack
      // finishes loading. During ending choreography People is hidden as a whole.
      const count = crowdCount(chars, flags.crowd);
      const spec = count > 0 ? crowdSpec(scene, count) : null;
      if (spec)
        for (const [x, z] of scatter(spec.zone, spec.count, spec))
          stableOccupied.push({ x, z });
      const occupied: Pick<NavPoint, "x" | "z">[] = [
        ...stableOccupied,
        rig.player,
      ];
      const playerSpot = useWorld.getState().world?.player.spot;
      if (playerSpot) {
        const at = pointAt(playerSpot)?.[0];
        if (at) occupied.push(at);
      }
      const candidates: GroupCandidate[] = nav.data.polys.map(
        (vertices, poly) => {
          const x =
            vertices.reduce((sum, i) => sum + nav.data.verts[i * 3]!, 0) /
            vertices.length;
          const z =
            vertices.reduce((sum, i) => sum + nav.data.verts[i * 3 + 2]!, 0) /
            vertices.length;
          return {
            key: `group-poly:${poly}`,
            place: nav.placeOf(poly),
            at: { poly, x, z, y: nav.heightAt(poly, x, z) },
            yaw: 0,
          };
        },
      );
      const grouped = new Map<string, GroupCandidate>();
      for (const c of Object.values(chars)
        .filter((c) => c.group && drawn(c))
        .sort((a, b) => a.id.localeCompare(b.id))) {
        const previous = people.get(c.id);
        const chosen = groupPlacement(
          c.id,
          c.place,
          candidates,
          occupied,
          previous
            ? {
                key: previous.spot,
                place: nav.placeOf(previous.at.poly),
                at: previous.at,
                yaw: previous.yaw,
              }
            : undefined,
          stableOccupied,
        );
        if (chosen) {
          grouped.set(c.id, chosen);
          occupied.push(chosen.at);
          stableOccupied.push(chosen.at);
          noRoom.delete(c.id);
        } else if (!noRoom.has(c.id)) {
          noRoom.add(c.id);
          console.warn(
            `No clear nav point for group representative ${c.id} in ${c.place}`,
          );
        }
      }
      for (const c of Object.values(chars)) {
        const representative = grouped.get(c.id);
        const spot = representative?.key ?? c.spot;
        const target: [NavPoint, number] | null = !drawn(c)
          ? null
          : representative
            ? [representative.at, representative.yaw]
            : c.spot
              ? pointAt(c.spot)
              : null;
        const p = people.get(c.id);
        if (!target) {
          if (p) remove(c.id);
          continue;
        }
        if (!p) {
          const obj = new Group();
          const stand = makeMannequin(0.3);
          obj.add(stand);
          obj.name = c.id;
          obj.userData.character = c.id;
          group.add(obj);
          // a staged entrance (castle.md 4): they come on at its start spot and walk to theirs
          const from = c.group
            ? undefined
            : rig.route?.(c.id, spot!, true)?.from;
          const start = from ? pointAt(from) : null;
          const np: Person = {
            obj,
            body: null,
            at: (start ?? target)[0],
            yaw: (start ?? target)[1],
            spot: spot!,
            path: [],
            speed: WALK,
            endYaw: target[1],
            leaving: false,
          };
          people.set(c.id, np);
          if (start) walk(np, c.id, spot!, target[0], false, true);
          const name = castName(c.id);
          if (name)
            void import("./cast/CastBody").then(({ CastBody }) => {
              if (people.get(c.id) !== np) return;
              np.body = new CastBody(
                gl,
                name,
                c.id,
                obj,
                stand,
                () => useQuality.getState().assetTier === "high",
              );
            });
          continue;
        }
        p.leaving = false;
        if (p.spot === spot) continue;
        p.spot = spot!;
        p.endYaw = target[1];
        walk(p, c.id, spot!, target[0], c.activity === "run");
      }
      // left the scene (3.4: their place isn't one of this scene's): out by the nearest exit
      for (const [id, p] of people) {
        if (chars[id] || p.leaving) continue;
        let best: NavPoint | null = null;
        let bestSpot = "";
        let bestD = Infinity;
        for (const e of manifest.exits) {
          const at = pointAt(e.spot)?.[0];
          if (!at) continue;
          const d = Math.hypot(at.x - p.at.x, at.z - p.at.z);
          if (d < bestD) [best, bestSpot, bestD] = [at, e.spot, d];
        }
        if (!best) {
          remove(id);
          continue;
        }
        p.leaving = true;
        p.endYaw = null;
        walk(p, id, bestSpot, best, false);
      }
    };
    sync(useWorld.getState().world?.characters ?? {});
    const off = useWorld.subscribe((s, prev) => {
      const chars = s.world?.characters;
      if (chars && chars !== prev.world?.characters) sync(chars);
    });
    return () => {
      off();
      for (const id of [...people.keys()]) remove(id);
    };
  }, [scene, nav, manifest, group, people, gl]);

  useFrame((_, dtRaw) => {
    group.visible = !rig.staged; // the ending's staging plays its own people (ending/Staging.tsx)
    if (rig.staged) return;
    const dt = Math.min(0.05, dtRaw);
    const focus = usePlayer.getState().focusCharacter;
    for (const [id, p] of people) {
      const was = p.at;
      let want = p.yaw;
      if (id === focus || id === rig.talkTo || id === rig.talking) {
        // the player's picked them: stop where they are and face the player
        want = Math.atan2(rig.player.x - p.at.x, rig.player.z - p.at.z);
      } else if (p.path.length) {
        let step = p.speed * dt;
        while (step > 0 && p.path.length) {
          const goal = p.path[0]!;
          const dx = goal.x - p.at.x;
          const dz = goal.z - p.at.z;
          const d = Math.hypot(dx, dz);
          if (d > 1e-4) want = Math.atan2(dx, dz);
          if (d <= step) {
            step -= d;
            p.at = goal;
            p.path.shift();
          } else {
            const x = p.at.x + (dx / d) * step;
            const z = p.at.z + (dz / d) * step;
            p.at = nav.locate(x, z, p.at.poly, p.at.y, true) ?? {
              ...p.at,
              x,
              z,
            };
            step = 0;
          }
        }
        if (!p.path.length) {
          if (p.leaving) {
            group.remove(p.obj);
            p.body?.dispose();
            people.delete(id);
            continue;
          }
          if (p.endYaw !== null) want = p.endYaw;
        }
      } else if (p.endYaw !== null) want = p.endYaw;
      p.yaw += angleTo(p.yaw, want) * Math.min(1, TURN * dt);
      p.obj.position.set(p.at.x, p.at.y, p.at.z);
      p.obj.rotation.y = p.yaw;
      const talking = id === rig.talking;
      if (p.body) {
        p.body.setTalking(talking || id === rig.talkTo);
        const speed =
          dt > 0 ? Math.hypot(p.at.x - was.x, p.at.z - was.z) / dt : 0;
        p.body.update(dt, speed, talking ? levels.mouth : 0);
      }
    }
  }, -4);

  return <primitive object={group} />;
}
