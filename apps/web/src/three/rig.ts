// Per-frame state shared by the player, the camera and the input, outside React (frontend-design 6: the render loop
// reads and writes it without re-rendering). Only place changes, near / far and the distances go to the stores.
import type { Object3D, PerspectiveCamera } from "three";
import type { NavPoint } from "./nav/navmesh";
import type { View } from "./scene/openingViews";

export type Pose = NavPoint & { yaw: number };

export const rig = {
  player: { poly: -1, x: 0, y: 0, z: 0, yaw: 0 } as Pose,
  path: [] as NavPoint[],
  // walking up to someone: face them and frame the conversation on arrival (frontend-design 8.4); someone who can't
  // be talked to is only faced
  talkTo: null as string | null,
  talking: null as string | null,
  faceTo: null as string | null,
  // camera: yaw of the view around the player (the angle down is fixed, ux-design 6.3); a sideways drag sets it, walking eases the yaw back behind the player
  cam: { yaw: 0, lastDrag: -Infinity },
  // the first screen's fixed shot (scene/openingViews.ts, world coordinates) until the player first walks or turns
  opening: null as View | null,
  // set by the test hook: a fixed camera instead of the follow rig
  fixedView: null as View | null,
  // the ending's staging (ending/Staging.tsx): its shot's camera, and the exploring layer's people and player hidden
  stage: null as View | null,
  staged: false,
  // a room's own follow distance (the castle's hall, castle.md 3.2: 5.5 m back, 2.6 m up), null = the exploring one
  follow: null as { back: number; up: number } | null,
  // a scene's own staging (castle/CastleStage.tsx, castle.md 3.2): where someone coming on or moving walks in from,
  // by which points, how fast; null = straight to the spot on the navmesh at the usual pace
  route: null as
    | ((
        id: string,
        spot: string,
        entering: boolean,
      ) => { from?: string; via?: [number, number][]; speed?: number } | null)
    | null,
  // the conversation's shot changed by the scene (castle.md 3.2: low under the king, level when crouching by the
  // hostage): the player's head height, the camera's distance behind it and height, the field of view
  shot: null as {
    headY?: number;
    back?: number;
    camY?: number;
    fov?: number;
  } | null,
  crouch: false, // the player down on one knee (the placeholder body squatted)
  // the next frame cuts the camera to its place instead of easing there (the player was put on a spot, not walked)
  cutCamera: false,
  camera: null as PerspectiveCamera | null, // CameraRig's, for the test hook
  keys: new Set<string>(),
  people: null as Object3D | null, // the scene's other people (Player.tsx)
};
