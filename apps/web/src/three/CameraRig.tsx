// Third-person camera (frontend-design 8.4, ux-design 6.3): exploring, it follows from behind and above at a fixed
// angle (UX prototype: about 13.5 m back and 7.6 m up), sideways drags turn it, walking eases it back behind; further
// back in portrait; pulled in when a wall is in the way; over-the-shoulder framing in a conversation. Before the player
// first walks or turns it holds the first screen's fixed shot (rig.opening) and then glides over to the follow view.
import { useFrame, useThree } from "@react-three/fiber";
import { useMemo } from "react";
import { PerspectiveCamera, Raycaster, Vector3, type Object3D } from "three";
import { rig } from "./rig";

// exploring: metres behind and above the player's feet, vertical field of view; landscape keeps the angle, comes closer
const FOLLOW = {
  portrait: { back: 13.5, up: 7.6, fov: 60 },
  landscape: { back: 10.8, up: 6.1, fov: 50 },
};
const LOOK_UP = 1.0; // aim at the player's waist,
const LOOK_AHEAD = 1.5; // a little in front, so more of the way ahead is in view
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
    }),
    [],
  );

  useFrame((_, dtRaw) => {
    const dt = Math.min(0.05, dtRaw);
    const cam = camera as PerspectiveCamera;
    const portrait = size.height >= size.width;
    const fixed = rig.fixedView ?? rig.opening;
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
    if (tmp.opening) {
      tmp.opening = false;
      tmp.glideUntil = performance.now() + GLIDE_MS;
    }
    const gliding = performance.now() < tmp.glideUntil;
    const p = rig.player;
    tmp.head.set(p.x, p.y + 1.45, p.z);
    const talking = rig.talking
      ? rig.people?.getObjectByName(rig.talking)
      : undefined;
    let fov: number;
    if (talking) {
      // over the shoulder: the person's face in the upper third, the player's shoulder bottom left (8.4, UX)
      const face = new Vector3(
        talking.position.x,
        talking.position.y + 1.56,
        talking.position.z,
      );
      tmp.dir.subVectors(face, tmp.head).setY(0).normalize();
      const right = new Vector3(-tmp.dir.z, 0, tmp.dir.x);
      tmp.want
        .copy(tmp.head)
        .addScaledVector(tmp.dir, -1.1)
        .addScaledVector(right, portrait ? 0.35 : 0.55)
        .setY(p.y + 1.62);
      tmp.look
        .copy(face)
        .addScaledVector(right, portrait ? 0 : 0.35)
        .setY(face.y - (portrait ? 0.25 : 0.1));
      fov = portrait ? 42 : 34;
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
      tmp.look.set(p.x + fx * LOOK_AHEAD, p.y + LOOK_UP, p.z + fz * LOOK_AHEAD);
      // a wall between the head and the camera: come in front of it
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
