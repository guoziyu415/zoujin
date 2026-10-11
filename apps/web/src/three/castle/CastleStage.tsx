// The castle's staging around its people (F-14; ux/scenes/castle.md 3.2, 4, 8): the routes in and out (People.tsx asks
// rig.route), the guards, courtiers and Melos's bundle, the poses (Melos bound, the meeting, the hostage's three days),
// the low shot under the king and the player kneeling by the sitting hostage (rig.shot, rig.crouch). Who is where
// comes from the server; this only stages it. Until F-16's people come in the stand-ins show the poses by squatting
// and turning; each person's `userData.pose` names the pose for the real ones' clips. Lazy, with the castle's lamps.
import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import {
  BoxGeometry,
  Group,
  Mesh,
  MeshStandardMaterial,
  type Object3D,
} from "three";
import { useWorld } from "../../stores/world";
import { makeMannequin } from "../mannequin";
import { rig } from "../rig";
import type { LoadedScene } from "../scene/loadScene";
import { fogUniforms } from "../shaderPatches";
import {
  BUNDLE,
  COURTIERS,
  DOOR_POSTS,
  DOUBT_S,
  ESCORT_POSTS,
  FRIEND,
  HALL_NIGHT,
  happenedAt,
  hostagePose,
  hostageWear,
  KING,
  meetingAt,
  MELOS,
  routeOf,
  sitting,
  STEP_POSTS,
  talkShot,
} from "./staging";

const CASTLE = "place.castle";
const GUARD_SPEED = 2.2; // m/s: the guards catch up with whoever they keep beside
const FRESH = 20; // story minutes, as in staging.ts

type Extra = { obj: Group; x: number; z: number; yaw: number };

const extra = (tone: number, x: number, z: number, yaw: number): Extra => {
  const obj = makeMannequin(tone);
  obj.position.set(x, 0, z);
  obj.rotation.y = yaw;
  return { obj, x, z, yaw };
};

const angleTo = (from: number, to: number) =>
  Math.atan2(Math.sin(to - from), Math.cos(to - from));

// a stand-in's pose: squat for sitting / kneeling, lean toward someone for the embrace, the face's height for the shot
function pose(
  o: Object3D,
  name: string,
  opts: { squat?: number; lean?: number; faceY?: number } = {},
) {
  o.userData.pose = name;
  o.scale.y = opts.squat ?? 1;
  for (const c of o.children) c.position.z = opts.lean ?? 0;
  o.userData.faceY = opts.faceY ?? 1.56 * (opts.squat ?? 1);
}

export default function CastleStage({ scene }: { scene: LoadedScene }) {
  const { manifest } = scene;
  const spot = (id: string): [number, number, number] | null => {
    const s = manifest.spots[id];
    return s ? [s.pos[0], s.pos[2], s.yaw] : null;
  };
  const cast = useMemo(() => {
    const group = new Group();
    const doors = DOOR_POSTS.map(([x, z]) => extra(0.28, x, z, -Math.PI / 2));
    const steps = STEP_POSTS.map(([x, z]) => extra(0.28, x, z, -Math.PI / 2));
    const escorts = ESCORT_POSTS.map(([x, z]) =>
      extra(0.27, x, z, Math.PI / 2),
    );
    const keeper = extra(0.27, 0, 0, 0); // walks the hostage to the column, then watches him
    const courtiers = COURTIERS.map(([x, z]) => extra(0.4, x, z, 0));
    const mat = new MeshStandardMaterial({ roughness: 0.9, color: 0x6b5a44 });
    mat.onBeforeCompile = fogUniforms;
    const bundle = new Mesh(new BoxGeometry(0.45, 0.28, 0.32), mat);
    bundle.position.set(BUNDLE[0], 0.14, BUNDLE[1]);
    bundle.castShadow = true;
    for (const e of [...doors, ...steps, ...escorts, keeper, ...courtiers])
      group.add(e.obj);
    group.add(bundle);
    return { group, doors, steps, escorts, keeper, courtiers, bundle };
  }, []);
  const st = useRef({
    melosAt: [0, 0] as [number, number],
    metAt: null as number | null, // seconds (clock) when his friend reached him
    doubtAt: null as number | null,
    doubtKnown: false,
    taken: false,
  });

  useEffect(() => {
    rig.route = (id, to, entering) => {
      const w = useWorld.getState().world;
      if (!w) return null;
      return routeOf(id, to, entering, {
        t: w.clock.t,
        led: happenedAt(w.events, "beat.04"),
        summoned: happenedAt(w.events, "beat.06"),
      });
    };
    return () => {
      rig.route = null;
      rig.shot = null;
      rig.crouch = false;
    };
  }, []);

  useFrame(({ clock }, dtRaw) => {
    const dt = Math.min(0.05, dtRaw);
    const now = clock.elapsedTime;
    const s = st.current;
    cast.group.visible = !rig.staged;
    const w = useWorld.getState().world;
    if (!w) return;
    const t = w.clock.t;
    const chars = w.characters;
    const here = (id: string) => chars[id]?.place === CASTLE;
    const get = (id: string) => rig.people?.getObjectByName(id) ?? null;
    const night = t >= HALL_NIGHT[0] && t < HALL_NIGHT[1];
    const toward = (e: Extra, x: number, z: number, yaw: number) => {
      const dx = x - e.x;
      const dz = z - e.z;
      const d = Math.hypot(dx, dz);
      const step = GUARD_SPEED * dt;
      if (d > step) {
        e.x += (dx / d) * step;
        e.z += (dz / d) * step;
        e.yaw += angleTo(e.yaw, Math.atan2(dx, dz)) * Math.min(1, dt * 6);
      } else {
        e.x = x;
        e.z = z;
        e.yaw += angleTo(e.yaw, yaw) * Math.min(1, dt * 6);
      }
      e.obj.position.set(e.x, 0, e.z);
      e.obj.rotation.y = e.yaw;
    };
    // beside / behind a walking person, in their frame: side to the right, back behind
    const beside = (o: Object3D, side: number, back: number) => {
      const y = o.rotation.y;
      return [
        o.position.x + Math.cos(y) * side - Math.sin(y) * back,
        o.position.z - Math.sin(y) * side - Math.cos(y) * back,
      ] as const;
    };

    for (const e of cast.courtiers) e.obj.visible = night;
    for (const e of cast.escorts) e.obj.visible = night;

    // Melos: led in bound between two guards, untied when his friend comes, out by his bundle
    const melos = get(MELOS);
    const friend = get(FRIEND);
    const meet = spot("selinuntius-meet");
    const atMeet =
      !!friend &&
      chars[FRIEND]?.spot === "selinuntius-meet" &&
      !!meet &&
      Math.hypot(friend.position.x - meet[0], friend.position.z - meet[1]) <
        0.3;
    if (atMeet && s.metAt === null) {
      const summoned = happenedAt(w.events, "beat.06");
      // a meeting long over before the player came in is just held
      s.metAt = summoned !== null && t - summoned <= FRESH ? now : -Infinity;
    }
    if (!atMeet && chars[FRIEND]?.spot !== "selinuntius-meet") s.metAt = null;
    const meeting = s.metAt === null ? null : meetingAt(now - s.metAt);
    if (melos) {
      const moving =
        Math.hypot(
          melos.position.x - s.melosAt[0],
          melos.position.z - s.melosAt[1],
        ) >
        0.2 * dt;
      s.melosAt = [melos.position.x, melos.position.z];
      const free = meeting !== null && meeting !== "untie";
      const leaving = !here(MELOS);
      pose(melos, free || leaving ? "stand" : "bound-front");
      if (meeting && meeting !== "held" && friend) {
        melos.rotation.y = Math.atan2(
          friend.position.x - melos.position.x,
          friend.position.z - melos.position.z,
        );
        if (meeting === "embrace")
          pose(melos, "embrace", { lean: 0.3, faceY: 1.56 });
      }
      if (night && moving && !leaving)
        cast.escorts.forEach((e, i) => {
          const [x, z] = beside(melos, i ? 0.7 : -0.7, 0.5);
          toward(e, x, z, melos.rotation.y);
        });
      else
        cast.escorts.forEach((e, i) =>
          toward(e, ESCORT_POSTS[i]![0], ESCORT_POSTS[i]![1], Math.PI / 2),
        );
      if (
        leaving &&
        Math.hypot(melos.position.x - BUNDLE[0], melos.position.z - BUNDLE[1]) <
          0.7
      )
        s.taken = true;
    } else
      cast.escorts.forEach((e, i) =>
        toward(e, ESCORT_POSTS[i]![0], ESCORT_POSTS[i]![1], Math.PI / 2),
      );
    if (here(MELOS)) s.taken = false;
    cast.bundle.visible = night && !!melos && !s.taken;

    // his friend: the meeting, then the column and the three days
    const column = spot("hostage-column");
    const keep = cast.keeper;
    let friendSits = false;
    keep.obj.visible = !!friend && here(FRIEND);
    if (friend && here(FRIEND)) {
      const fs = chars[FRIEND]?.spot;
      const atColumn =
        fs === "hostage-column" &&
        !!column &&
        Math.hypot(
          friend.position.x - column[0],
          friend.position.z - column[1],
        ) < 0.4;
      if (atColumn) {
        const doubted = happenedAt(w.events, "beat.s2");
        if (!s.doubtKnown) {
          s.doubtKnown = true;
          if (doubted !== null) s.doubtAt = -Infinity; // already over when the scene opened
        } else if (doubted !== null && s.doubtAt === null) s.doubtAt = now;
        const visitor =
          Math.hypot(rig.player.x - column[0], rig.player.z - column[1]) < 3;
        const p =
          s.doubtAt !== null && now - s.doubtAt < DOUBT_S
            ? "doubt"
            : hostagePose(t, { visitor, doubted: doubted !== null });
        friendSits = sitting(p);
        pose(friend, p, friendSits ? { squat: 0.6 } : {});
        if (p === "stand-west") friend.rotation.y = -Math.PI / 2; // the gate wall, the sun behind it
        friend.userData.wear = hostageWear(t);
        const g = spot("hostage-guard");
        if (g) toward(keep, g[0], g[1], g[2]);
      } else {
        if (meeting === "embrace") pose(friend, "embrace", { lean: 0.3 });
        else
          pose(
            friend,
            meeting === "bind" || meeting === "held" || fs === "hostage-column"
              ? "bound-front"
              : "stand",
          );
        if (meeting && meeting !== "held" && melos)
          friend.rotation.y = Math.atan2(
            melos.position.x - friend.position.x,
            melos.position.z - friend.position.z,
          );
        const [x, z] = beside(friend, 0, atMeet ? 1.2 : 1.0);
        toward(keep, x, z, friend.rotation.y);
      }
      friend.userData.wear ??= 1;
    }

    // the king sits on his throne (6.1): sitting idle / talking
    const king = get(KING);
    if (king && chars[KING]?.spot === "king-throne")
      pose(king, rig.talking === KING ? "sit-talk" : "sit", {
        squat: 0.72,
        faceY: 1.12,
      });

    // the conversation's shot and the player's knee
    const talking = rig.talking ? get(rig.talking) : null;
    const shot = talking
      ? talkShot(
          rig.talking!,
          Math.hypot(
            talking.position.x - rig.player.x,
            talking.position.z - rig.player.z,
          ),
          rig.talking === FRIEND && friendSits,
        )
      : null;
    rig.shot = shot;
    rig.crouch = !!shot?.headY;
  }, -3.5);

  return <primitive object={cast.group} />;
}
