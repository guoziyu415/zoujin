// Per-frame state shared by the player, the camera and the input, outside React (frontend-design 6: the render loop
// reads and writes it without re-rendering). Only place changes go to the store.
import type { Object3D, PerspectiveCamera } from "three";
import type { NavPoint } from "./nav/navmesh";
import type { View } from "./scene/openingViews";

export type Pose = NavPoint & { yaw: number };

export const rig = {
  player: { poly: -1, x: 0, y: 0, z: 0, yaw: 0 } as Pose,
  path: [] as NavPoint[],
  // walking up to someone: face them and frame the conversation on arrival (frontend-design 8.4)
  talkTo: null as string | null,
  talking: null as string | null,
  // camera: yaw of the view around the player (the angle down is fixed, ux-design 6.3); a sideways drag sets it, walking eases the yaw back behind the player
  cam: { yaw: 0, lastDrag: -Infinity },
  // the first screen's fixed shot (scene/openingViews.ts, world coordinates) until the player first walks or turns
  opening: null as View | null,
  // set by the test hook: a fixed camera instead of the follow rig
  fixedView: null as View | null,
  // the next frame cuts the camera to its place instead of easing there (the player was put on a spot, not walked)
  cutCamera: false,
  camera: null as PerspectiveCamera | null, // CameraRig's, for the test hook
  keys: new Set<string>(),
  people: null as Object3D | null, // the scene's other people (Player.tsx)
};
