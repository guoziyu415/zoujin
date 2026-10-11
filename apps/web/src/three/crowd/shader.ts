// The crowd's materials (F-4 range 3): the standard material, skinned in the vertex shader from the baked motion
// texture (rig.ts) with each instance's own motion, start, speed and colours; and the same skinning for its shadow.
// Per instance (InstancedBufferAttribute):
//   iClip  = (first row, frames (negative: plays once and holds the last), start, speed)   the motion now
//   iPrev  = the same for the motion before, faded out over BLEND seconds from iSwitch
//   iSkin, iCloth, iCloth2, iHair = the colours of the parts (aPart 0 skin, 1 cloth, 2 the outer piece, 3 hair; 4 the
//   eyes: half the skin's colour, as EYE_SHADE in build_crowd.py; white eyes read as the dead, black ones as sharp
//   slits: UX; 5 the men's beard: iFace.x of the way from the skin to the hair)
//   iPlace = (x, y, z, yaw): where the person stands and which way they face
//   iScale = (breadth, height, the outer piece, what they carry): the outer piece 0 none (the executioner, bareheaded),
//   1 as built, 2 the working man's cap drawn up into the guards' cone helmet (uCap: its centre, rim and height);
//   carried 1 the spear (parts 6, 7), 2 the bundle (8), anything else folded away (props.ts)
// The cloth has no texture to download (the pack has no UVs): the fragment shader gives it its weave and wear from the
// rest position, each person's own (offset by where they stand): long streaks up and down where it hangs, a coarser
// mottle, and darker towards the hem where the dust is (UX on #156: flat colour; card: texture)
//   iFace = (beard, the head's width, its depth): the head scaled round its joint (uHead); with the beards, faces that
//   differ (UX: all the faces the same). One attribute for the three: WebGL gives a vertex 16 at least, and no more
import {
  MeshDepthMaterial,
  MeshStandardMaterial,
  type DataTexture,
  type Vector4,
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
uniform vec4 uHead;
uniform vec4 uCap;
attribute float aPart;
attribute vec4 skinIndex;
attribute vec4 skinWeight;
attribute vec4 iClip;
attribute vec4 iPrev;
attribute float iSwitch;
attribute vec4 iPlace;
attribute vec4 iScale;
attribute vec3 iFace;
bool crowdGone() {
  if (aPart > 1.5 && aPart < 2.5) return iScale.z < 0.5;
  if (aPart > 5.5 && aPart < 7.5) return abs(iScale.w - 1.0) > 0.5;
  if (aPart > 7.5) return abs(iScale.w - 2.0) > 0.5;
  return false;
}
vec3 crowdShape(vec3 p) {
  if (crowdGone()) return uHead.xyz;
  if (aPart > 1.5 && aPart < 2.5 && iScale.z > 1.5) {
    float h = max(p.y - uCap.y, 0.0);
    float k = clamp(h / uCap.w, 0.0, 1.0);
    p.xz = uCap.xz + (p.xz - uCap.xz) * (1.06 - 0.7 * k * k);
    p.y = uCap.y + h * 2.4;
  }
  return p;
}
vec3 crowdHead(vec3 p) {
  vec4 on = vec4(equal(skinIndex, vec4(uHead.w)));
  float w = dot(on, skinWeight);
  return uHead.xyz + (p - uHead.xyz) * mix(vec3(1.0), vec3(iFace.y, 1.0, iFace.z), w);
}
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

// value noise, then the cloth's shade at a rest position: 0.8-1.15 from the weave and wear, a fifth darker at the hem
const cloth = /* glsl */ `
float crowdHash(vec3 p) {
  return fract(sin(dot(p, vec3(12.9898, 78.233, 37.719))) * 43758.5453);
}
float crowdNoise(vec3 p) {
  vec3 i = floor(p);
  vec3 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(crowdHash(i), crowdHash(i + vec3(1, 0, 0)), f.x),
                 mix(crowdHash(i + vec3(0, 1, 0)), crowdHash(i + vec3(1, 1, 0)), f.x), f.y),
             mix(mix(crowdHash(i + vec3(0, 0, 1)), crowdHash(i + vec3(1, 0, 1)), f.x),
                 mix(crowdHash(i + vec3(0, 1, 1)), crowdHash(i + vec3(1, 1, 1)), f.x), f.y), f.z);
}
float crowdCloth(vec3 q) {
  float n = 0.6 * crowdNoise(q * vec3(10.0, 1.2, 10.0)) + 0.4 * crowdNoise(q * 5.0);
  float hem = smoothstep(0.6, 0.05, q.y);
  return (0.8 + 0.35 * n) * (1.0 - 0.18 * hem);
}
`;

export type CrowdUniforms = {
  uBones: { value: DataTexture };
  uTime: { value: number };
  uHead: { value: Vector4 }; // the head joint at rest (x, y, z) and the head bone's index
  uCap: { value: Vector4 }; // the outer piece's centre x, its lowest y, centre z, its height (the cap's, for the helmet)
};

function patch(
  sh: WebGLProgramParametersWithUniforms,
  u: CrowdUniforms,
  depth: boolean,
): void {
  sh.uniforms.uBones = u.uBones;
  sh.uniforms.uTime = u.uTime;
  sh.uniforms.uHead = u.uHead;
  sh.uniforms.uCap = u.uCap;
  sh.vertexShader = sh.vertexShader.replace(
    "#include <common>",
    `#include <common>\n${common}`,
  );
  if (depth) {
    sh.vertexShader = sh.vertexShader.replace(
      "#include <begin_vertex>",
      "mat4 crowdM = crowdSkin();\nvec3 transformed = crowdPlace( ( crowdM * vec4( crowdHead( crowdShape( position ) ), 1.0 ) ).xyz );",
    );
    return;
  }
  fogUniforms(sh);
  sh.vertexShader = sh.vertexShader
    .replace(
      "#include <common>",
      "#include <common>\nattribute vec3 iSkin;\nattribute vec3 iCloth;\nattribute vec3 iCloth2;\nattribute vec3 iHair;\nvarying vec3 vTint;\nvarying float vNear;\nvarying vec4 vCloth;",
    )
    .replace(
      "#include <beginnormal_vertex>",
      "mat4 crowdM = crowdSkin();\nvec3 objectNormal = crowdTurn( normalize( mat3( crowdM ) * normal ) );\nvNear = distance( cameraPosition.xz, ( modelMatrix * vec4( iPlace.xyz, 1.0 ) ).xz );\nvCloth = vec4( position + vec3( iPlace.x * 3.1, 0.0, iPlace.z * 2.7 ), ( aPart > 0.5 && aPart < 2.5 ) || aPart > 7.5 ? 1.0 : 0.0 );\nvTint = aPart < 0.5 ? iSkin : aPart < 1.5 ? iCloth : aPart < 2.5 ? iCloth2 : aPart < 3.5 ? iHair : aPart < 4.5 ? iSkin * 0.5 : aPart < 5.5 ? mix( iSkin, iHair, iFace.x ) : aPart < 6.5 ? vec3( 0.16, 0.1, 0.06 ) : aPart < 7.5 ? vec3( 0.05, 0.05, 0.05 ) : iCloth * 0.85;",
    )
    .replace(
      "#include <begin_vertex>",
      "vec3 transformed = crowdPlace( ( crowdM * vec4( crowdHead( crowdShape( position ) ), 1.0 ) ).xyz );",
    );
  sh.fragmentShader = sh.fragmentShader
    .replace(
      "#include <common>",
      `#include <common>\nvarying vec3 vTint;\nvarying float vNear;\nvarying vec4 vCloth;\n${cloth}`,
    )
    .replace(
      "#include <clipping_planes_fragment>",
      // screen-door fade (no sorting): fewer of a near person's pixels drawn the closer the camera is
      `#include <clipping_planes_fragment>
if ( smoothstep( ${NEAR[0]!.toFixed(2)}, ${NEAR[1]!.toFixed(2)}, vNear ) < fract( 52.9829189 * fract( dot( gl_FragCoord.xy, vec2( 0.06711056, 0.00583715 ) ) ) ) ) discard;`,
    )
    .replace(
      "#include <color_fragment>",
      "diffuseColor.rgb *= vTint;\nif ( vCloth.w > 0.5 ) diffuseColor.rgb *= crowdCloth( vCloth.xyz );",
    );
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
