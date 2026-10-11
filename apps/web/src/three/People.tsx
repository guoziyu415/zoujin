// The scene's characters (frontend-design 8.3, 8.6), grey stand-ins until A-0's people come in: standing on the spots
// the server gives (world.characters[id].place / spot / activity). A new spot is a story move: they walk there on the
// navmesh, or run when the activity says so; leaving the scene they walk to the nearest exit spot (way.*) first.
// Picked by the player they stop and face them until the conversation ends (ux-design 6.5). Crowds (group: true) are
// F-4's; "absent" isn't drawn. Moving about on the spot (8.6 表演走動) comes with the real characters' animations.
import type { Api } from "@zoujin/contracts";
import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import { Group } from "three";
import { usePlayer } from "../stores/player";
import { useWorld } from "../stores/world";
import { makeMannequin } from "./mannequin";
import type { NavPoint } from "./nav/navmesh";
import { rig } from "./rig";
import type { LoadedScene } from "./scene/loadScene";

const WALK = 1.4; // m/s
const RUN = 3.2;
const TURN = 6; // rad/s

type Person = {
  obj: Group;
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
  !c.group && c.activity !== "absent" && !!c.spot;

export function People({ scene }: { scene: LoadedScene }) {
  const { nav, manifest } = scene;
  const group = useMemo(() => new Group(), []);
  const people = useMemo(() => new Map<string, Person>(), []);

  useEffect(() => {
    rig.people = group;
    return () => {
      rig.people = null;
    };
  }, [group]);

  useEffect(() => {
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
      if (p) group.remove(p.obj);
      people.delete(id);
    };
    const walk = (p: Person, to: NavPoint, run: boolean) => {
      const path = nav.findPath(p.at, to, true);
      p.path = path ? path.slice(1) : [to];
      p.speed = run ? RUN : WALK;
    };
    const sync = (chars: Record<string, Api.CharacterPresence>) => {
      for (const c of Object.values(chars)) {
        const target = drawn(c) ? pointAt(c.spot!) : null;
        const p = people.get(c.id);
        if (!target) {
          if (p) remove(c.id);
          continue;
        }
        if (!p) {
          const obj = makeMannequin(0.3);
          obj.name = c.id;
          obj.userData.character = c.id;
          group.add(obj);
          people.set(c.id, {
            obj,
            at: target[0],
            yaw: target[1],
            spot: c.spot!,
            path: [],
            speed: WALK,
            endYaw: target[1],
            leaving: false,
          });
          continue;
        }
        p.leaving = false;
        if (p.spot === c.spot) continue;
        p.spot = c.spot!;
        p.endYaw = target[1];
        walk(p, target[0], c.activity === "run");
      }
      // left the scene (3.4: their place isn't one of this scene's): out by the nearest exit
      for (const [id, p] of people) {
        if (chars[id] || p.leaving) continue;
        let best: NavPoint | null = null;
        let bestD = Infinity;
        for (const e of manifest.exits) {
          const at = pointAt(e.spot)?.[0];
          if (!at) continue;
          const d = Math.hypot(at.x - p.at.x, at.z - p.at.z);
          if (d < bestD) [best, bestD] = [at, d];
        }
        if (!best) {
          remove(id);
          continue;
        }
        p.leaving = true;
        p.endYaw = null;
        walk(p, best, false);
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
  }, [nav, manifest, group, people]);

  useFrame((_, dtRaw) => {
    group.visible = !rig.staged; // the ending's staging plays its own people (ending/Staging.tsx)
    if (rig.staged) return;
    const dt = Math.min(0.05, dtRaw);
    const focus = usePlayer.getState().focusCharacter;
    for (const [id, p] of people) {
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
            people.delete(id);
            continue;
          }
          if (p.endYaw !== null) want = p.endYaw;
        }
      } else if (p.endYaw !== null) want = p.endYaw;
      p.yaw += angleTo(p.yaw, want) * Math.min(1, TURN * dt);
      p.obj.position.set(p.at.x, p.at.y, p.at.z);
      p.obj.rotation.y = p.yaw;
    }
  }, -4);

  return <primitive object={group} />;
}
