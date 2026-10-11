// Third-person camera (frontend-design 8.4, ux-design 6.3): exploring, it follows from behind and a little above at a
// fixed angle (UX: 9 m back, 3.5 m up, aimed 1.5 m above the player's feet, about 12.5° down, so the horizon sits about a
// third of the way down and the sky stays in view), sideways drags turn it, walking eases it back behind; the same angle
// but closer in landscape; pulled in when a wall is in the way; over-the-shoulder framing in a conversation. Before the
// player first walks or turns it holds the first screen's fixed shot (rig.opening) and then glides over to the follow
// view. With reduced motion (prefers-reduced-motion; F-1's 「画面の動きを減らす」 setting joins it) it cuts instead.
// Cuts and entering / leaving a conversation are the moments the quality level may change (10.6.3): it tells quality.
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import { PerspectiveCamera, Raycaster, Vector3, type Object3D } from "three";
import { reducedMotion } from "./motion";
import { quality } from "./quality/quality";
import { rig } from "./rig";
import { shoulderSide, TALK } from "./talkShot";

// exploring: metres behind and above the player's feet, vertical field of view; landscape keeps the angle, comes closer.
// Portrait at 390 x 844: a 1.7 m person about 120 px tall, someone 15 m further on about 50 px (UX: 100-130 and 40-80).
const LOOK_UP = 1.5; // aim this far above the player's feet
const FOLLOW = {
  portrait: { back: 9, up: 3.5, fov: 62 },
  landscape: { back: 7.5, up: LOOK_UP + (2 * 7.5) / 9, fov: 50 },
};
const FOLLOW_AFTER_DRAG_MS = 2500;
const GLIDE_MS = 1800; // from the first screen's shot to the follow view

export function CameraRig({ blockers }: { blockers: Object3D[] }) {
  const { camera, size } = useThree();
  const tmp = useMemo(
    () => ({
      want: new Vector3(),
      look: new Vector3(),
      head: new Vector3(),
      dir: new Vector3(),
      cur: new Vector3(),
      curLook: new Vector3(),
      ray: new Raycaster(),
      first: true,
      opening: false,
      glideUntil: 0,
      wasTalking: false,
      lastFixed: null as unknown,
    }),
    [],
  );
  useEffect(() => {
    rig.camera = camera as PerspectiveCamera;
    return () => {
      rig.camera = null;
    };
  }, [camera]);

  useFrame((_, dtRaw) => {
    const dt = Math.min(0.05, dtRaw);
    const cam = camera as PerspectiveCamera;
    const portrait = size.height >= size.width;
    const fixed = rig.fixedView ?? rig.opening;
    if (fixed !== tmp.lastFixed) {
      // a fixed shot starts or ends: the test hook's views, the first screen giving way to the follow view
      tmp.lastFixed = fixed;
      quality.cut(performance.now());
    }
    if (fixed) {
      cam.position.set(...fixed.from);
      cam.lookAt(...fixed.to);
      setFov(cam, fixed.fov);
      tmp.cur.copy(cam.position);
      tmp.curLook.set(...fixed.to);
      tmp.first = !!rig.fixedView; // the test hook's views cut back; the first screen glides
      tmp.opening = !rig.fixedView;
      return;
    }
    const still = reducedMotion();
    if (tmp.opening) {
      tmp.opening = false;
      if (still) tmp.first = true;
      else tmp.glideUntil = performance.now() + GLIDE_MS;
    }
    if (rig.cutCamera) {
      tmp.first = true; // the player was put somewhere else, not walked there
      rig.cutCamera = false;
      quality.cut(performance.now());
    }
    const gliding = performance.now() < tmp.glideUntil;
    const p = rig.player;
    tmp.head.set(p.x, p.y + 1.45, p.z);
    const talking = rig.talking
      ? rig.people?.getObjectByName(rig.talking)
      : undefined;
    if (!!talking !== tmp.wasTalking) {
      if (still) tmp.first = true;
      quality.cut(performance.now());
    }
    tmp.wasTalking = !!talking;
    let fov: number;
    if (talking) {
      // over the shoulder: the person's face in the upper third, the player's shoulder bottom left (8.4, UX)
      const face = new Vector3(
        talking.position.x,
        talking.position.y + 1.56,
        talking.position.z,
      );
      tmp.dir.subVectors(face, tmp.head).setY(0);
      const apart = tmp.dir.length();
      tmp.dir.normalize();
      const right = new Vector3(-tmp.dir.z, 0, tmp.dir.x);
      fov = portrait ? 42 : 34;
      // portrait: far enough to the side that the player's head is just out of frame and only the shoulder shows
      const side = portrait
        ? shoulderSide(apart, fov, size.width / size.height)
        : 0.55;
      tmp.want
        .copy(tmp.head)
        .addScaledVector(tmp.dir, -TALK.back)
        .addScaledVector(right, side)
        .setY(p.y + 1.62);
      tmp.look
        .copy(face)
        .addScaledVector(right, portrait ? 0 : 0.35)
        .setY(face.y - (portrait ? 0.25 : 0.1));
    } else {
      const f = portrait ? FOLLOW.portrait : FOLLOW.landscape;
      fov = f.fov;
      // ease back behind the player while walking, unless the view was just dragged
      if (
        rig.path.length &&
        performance.now() - rig.cam.lastDrag > FOLLOW_AFTER_DRAG_MS
      ) {
        const d = Math.atan2(
          Math.sin(p.yaw - rig.cam.yaw),
          Math.cos(p.yaw - rig.cam.yaw),
        );
        rig.cam.yaw += d * Math.min(1, dt * 1.2);
      }
      const fx = Math.sin(rig.cam.yaw);
      const fz = Math.cos(rig.cam.yaw);
      tmp.want.set(p.x - fx * f.back, p.y + f.up, p.z - fz * f.back);
      tmp.look.set(p.x, p.y + LOOK_UP, p.z);
      // anything between the head and the camera, even the stake: come in front of it (behind a post the player would
      // be hidden)
      tmp.dir.subVectors(tmp.want, tmp.head);
      const dist = tmp.dir.length();
      tmp.ray.set(tmp.head, tmp.dir.normalize());
      tmp.ray.far = dist;
      const hit = tmp.ray.intersectObjects(blockers, false)[0];
      if (hit)
        tmp.want
          .copy(tmp.head)
          .addScaledVector(tmp.dir, Math.max(0.6, hit.distance - 0.3));
    }
    if (tmp.first) {
      tmp.cur.copy(tmp.want);
      tmp.curLook.copy(tmp.look);
      setFov(cam, fov);
      tmp.first = false;
    } else {
      const k = 1 - Math.exp(-dt * (talking ? 4 : gliding ? 2.5 : 8));
      tmp.cur.lerp(tmp.want, k);
      tmp.curLook.lerp(tmp.look, k);
      setFov(cam, cam.fov + (fov - cam.fov) * k);
    }
    cam.position.copy(tmp.cur);
    cam.lookAt(tmp.curLook);
  }, -2);
  return null;
}

function setFov(cam: PerspectiveCamera, fov: number) {
  if (Math.abs(cam.fov - fov) < 1e-3) return;
  cam.fov = fov;
  cam.updateProjectionMatrix();
}
