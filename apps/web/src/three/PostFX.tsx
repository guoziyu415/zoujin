// Draws the frame through the post-processing chain (post.ts) and takes over R3F's render (useFrame priority 1).
// Follows the quality level: bloom and MSAA off at L0 (10.6.3), changed at a cut with the rest of `applied`; the pixel
// ratio comes from the canvas. Every frame it tells the quality governor the interval and whether the camera moved,
// and draws twice during its stress check (or N times on the measuring page).
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import { Quaternion, Vector3 } from "three";
import { lightState } from "./Lighting";
import { makePost } from "./post";
import { SETTINGS } from "./quality/levels";
import { quality, useQuality } from "./quality/quality";

export const frameStats = { calls: 0, triangles: 0, frames: 0, reps: 1 };
// where the camera was last frame: the governor's stress waits for a still picture
const last = { pos: new Vector3(Infinity, 0, 0), quat: new Quaternion() };

export function PostFX() {
  const { gl, scene, camera, size } = useThree();
  const dpr = useThree((s) => s.viewport.dpr);
  const applied = useQuality((s) => s.applied);
  const post = useMemo(() => makePost(gl, scene, camera), [gl, scene, camera]);

  useEffect(() => {
    post.setSize(size.width, size.height, dpr);
  }, [post, size, dpr]);
  useEffect(() => {
    post.bloom.enabled = SETTINGS[applied].bloom;
    post.setMsaa(SETTINGS[applied].msaa);
  }, [post, applied]);
  useEffect(() => () => post.dispose(), [post]);

  useFrame(() => {
    post.out.uniforms.uNight!.value = lightState.night;
    gl.toneMappingExposure = lightState.exposure * lightState.faceExposure;
    // under half a millimetre and a hundredth of a degree: the follow camera's easing has settled
    const still =
      camera.position.distanceToSquared(last.pos) < 2.5e-7 &&
      Math.abs(camera.quaternion.dot(last.quat)) > 1 - 1e-8;
    last.pos.copy(camera.position);
    last.quat.copy(camera.quaternion);
    const reps = quality.frame(performance.now(), frameStats.calls, dpr, still);
    gl.info.autoReset = false;
    gl.info.reset();
    post.composer.render();
    frameStats.calls = gl.info.render.calls;
    frameStats.triangles = gl.info.render.triangles;
    for (let k = 1; k < reps; k++) post.composer.render();
    frameStats.reps = reps;
    frameStats.frames++;
  }, 1);
  return null;
}
