// The crowd's materials (F-4 range 3): the standard material, skinned in the vertex shader from the baked motion
// texture (rig.ts) with each instance's own motion, start, speed and colours; and the same skinning for its shadow.
// Per instance (InstancedBufferAttribute):
//   iClip  = (first row, frames (negative: plays once and holds the last), start, speed)   the motion now
//   iPrev  = the same for the motion before, faded out over BLEND seconds from iSwitch
//   iSkin, iCloth, iCloth2, iHair = the colours of the parts (aPart 0 skin, 1 cloth, 2 the outer piece, 3 hair; 4 the
//   eyes, all the same dark iris: UX, white eyes read as the dead)
//   iPlace = (x, y, z, yaw): where the person stands and which way they face; iScale = (breadth, height)
import {
  MeshDepthMaterial,
  MeshStandardMaterial,
  type DataTexture,
  type WebGLProgramParametersWithUniforms,
} from "three";
import { fogUniforms } from "../shaderPatches";
import { FPS } from "./rig";

export const BLEND = 0.35; // s
// a camera this close to someone (their axis, level) sees through them, faded out over the band (UX on #139: a head
// in front of the lens filled half the screen); their shadow stays
export const NEAR = [0.45, 0.75]; // m

const common = /* glsl */ `
uniform highp sampler2D uBones;
uniform float uTime;
attribute vec4 skinIndex;
attribute vec4 skinWeight;
attribute vec4 iClip;
attribute vec4 iPrev;
attribute float iSwitch;
attribute vec4 iPlace;
attribute vec2 iScale;
vec3 crowdTurn(vec3 v) {
  float c = cos(iPlace.w);
  float s = sin(iPlace.w);
  return vec3(c * v.x + s * v.z, v.y, -s * v.x + c * v.z);
}
vec3 crowdPlace(vec3 p) {
  return crowdTurn(p * vec3(iScale.x, iScale.y, iScale.x)) + iPlace.xyz;
}
mat4 crowdBone(float row, float b) {
  int x = int(b) * 4;
  int y = int(row);
  return mat4(texelFetch(uBones, ivec2(x, y), 0), texelFetch(uBones, ivec2(x + 1, y), 0),
    texelFetch(uBones, ivec2(x + 2, y), 0), texelFetch(uBones, ivec2(x + 3, y), 0));
}
float crowdRow(vec4 c) {
  float n = max(abs(c.y), 1.0);
  float f = floor(max(uTime - c.z, 0.0) * c.w * ${FPS.toFixed(1)});
  return c.x + (c.y > 0.0 ? mod(f, n) : min(f, n - 1.0));
}
mat4 crowdSkinAt(float row) {
  mat4 m = crowdBone(row, skinIndex.x) * skinWeight.x + crowdBone(row, skinIndex.y) * skinWeight.y;
  if (skinWeight.z > 0.0) m += crowdBone(row, skinIndex.z) * skinWeight.z;
  if (skinWeight.w > 0.0) m += crowdBone(row, skinIndex.w) * skinWeight.w;
  return m;
}
mat4 crowdSkin() {
  float k = clamp((uTime - iSwitch) / ${BLEND.toFixed(2)}, 0.0, 1.0);
  mat4 now = crowdSkinAt(crowdRow(iClip));
  return k >= 1.0 ? now : now * k + crowdSkinAt(crowdRow(iPrev)) * (1.0 - k);
}
`;

export type CrowdUniforms = {
  uBones: { value: DataTexture };
  uTime: { value: number };
};

function patch(
  sh: WebGLProgramParametersWithUniforms,
  u: CrowdUniforms,
  depth: boolean,
): void {
  sh.uniforms.uBones = u.uBones;
  sh.uniforms.uTime = u.uTime;
  sh.vertexShader = sh.vertexShader.replace(
    "#include <common>",
    `#include <common>\n${common}`,
  );
  if (depth) {
    sh.vertexShader = sh.vertexShader.replace(
      "#include <begin_vertex>",
      "mat4 crowdM = crowdSkin();\nvec3 transformed = crowdPlace( ( crowdM * vec4( position, 1.0 ) ).xyz );",
    );
    return;
  }
  fogUniforms(sh);
  sh.vertexShader = sh.vertexShader
    .replace(
      "#include <common>",
      "#include <common>\nattribute float aPart;\nattribute vec3 iSkin;\nattribute vec3 iCloth;\nattribute vec3 iCloth2;\nattribute vec3 iHair;\nvarying vec3 vTint;\nvarying float vNear;",
    )
    .replace(
      "#include <beginnormal_vertex>",
      "mat4 crowdM = crowdSkin();\nvec3 objectNormal = crowdTurn( normalize( mat3( crowdM ) * normal ) );\nvNear = distance( cameraPosition.xz, ( modelMatrix * vec4( iPlace.xyz, 1.0 ) ).xz );\nvTint = aPart < 0.5 ? iSkin : aPart < 1.5 ? iCloth : aPart < 2.5 ? iCloth2 : aPart < 3.5 ? iHair : vec3(0.09, 0.07, 0.06);",
    )
    .replace(
      "#include <begin_vertex>",
      "vec3 transformed = crowdPlace( ( crowdM * vec4( position, 1.0 ) ).xyz );",
    );
  sh.fragmentShader = sh.fragmentShader
    .replace(
      "#include <common>",
      "#include <common>\nvarying vec3 vTint;\nvarying float vNear;",
    )
    .replace(
      "#include <clipping_planes_fragment>",
      // screen-door fade (no sorting): fewer of a near person's pixels drawn the closer the camera is
      `#include <clipping_planes_fragment>
if ( smoothstep( ${NEAR[0]!.toFixed(2)}, ${NEAR[1]!.toFixed(2)}, vNear ) < fract( 52.9829189 * fract( dot( gl_FragCoord.xy, vec2( 0.06711056, 0.00583715 ) ) ) ) ) discard;`,
    )
    .replace("#include <color_fragment>", "diffuseColor.rgb *= vTint;");
}

export function crowdMaterials(u: CrowdUniforms): {
  material: MeshStandardMaterial;
  depth: MeshDepthMaterial;
} {
  const material = new MeshStandardMaterial({ roughness: 0.85, metalness: 0 });
  material.onBeforeCompile = (sh) => patch(sh, u, false);
  material.customProgramCacheKey = () => "crowd";
  material.userData.uniforms = u; // the bone texture is the material's to dispose
  const depth = new MeshDepthMaterial(); // as the shadow map's own (WebGLShadowMap)
  depth.onBeforeCompile = (sh) => patch(sh, u, true);
  depth.customProgramCacheKey = () => "crowd-depth";
  return { material, depth };
}
