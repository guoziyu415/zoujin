// The crowd's materials (F-4 range 3): the standard material, skinned in the vertex shader from the baked motion
// texture (rig.ts) with each instance's own motion, start, speed and colours; and the same skinning for its shadow.
// Per instance (InstancedBufferAttribute):
//   iClip  = (first row, frames (negative: plays once and holds the last), start, speed)   the motion now
//   iPrev  = the same for the motion before, faded out over BLEND seconds from iSwitch
//   iSkin, iCloth, iCloth2 = the colours of the three parts (bodies.ts aPart 0, 1, 2)
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
  return crowdBone(row, skinIndex.x) * skinWeight.x + crowdBone(row, skinIndex.y) * skinWeight.y;
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
      "#include <common>\nattribute float aPart;\nattribute vec3 iSkin;\nattribute vec3 iCloth;\nattribute vec3 iCloth2;\nvarying vec3 vTint;",
    )
    .replace(
      "#include <beginnormal_vertex>",
      "mat4 crowdM = crowdSkin();\nvec3 objectNormal = crowdTurn( normalize( mat3( crowdM ) * normal ) );\nvTint = aPart < 0.5 ? iSkin : aPart < 1.5 ? iCloth : iCloth2;",
    )
    .replace(
      "#include <begin_vertex>",
      "vec3 transformed = crowdPlace( ( crowdM * vec4( position, 1.0 ) ).xyz );",
    );
  sh.fragmentShader = sh.fragmentShader
    .replace("#include <common>", "#include <common>\nvarying vec3 vTint;")
    .replace("#include <color_fragment>", "diffuseColor.rgb *= vTint;");
}

export function crowdMaterials(u: CrowdUniforms): {
  material: MeshStandardMaterial;
  depth: MeshDepthMaterial;
} {
  const material = new MeshStandardMaterial({ roughness: 0.85, metalness: 0 });
  material.onBeforeCompile = (sh) => patch(sh, u, false);
  material.customProgramCacheKey = () => "crowd";
  const depth = new MeshDepthMaterial(); // as the shadow map's own (WebGLShadowMap)
  depth.onBeforeCompile = (sh) => patch(sh, u, true);
  depth.customProgramCacheKey = () => "crowd-depth";
  return { material, depth };
}
