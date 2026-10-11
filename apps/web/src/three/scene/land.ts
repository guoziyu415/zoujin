// The far land round the road's scenes (F-10, UX rounds 2 and 3 on the river shots): the pack's hills are one straw
// texture tiled every 12 m with the outcrop's relief, which read as desert dunes. Here, in the shader: the tiling broken
// up (a second, larger sample of the same texture blended in by a slow noise), the relief turned down, and macro colour
// by position and slope: dark scrub in patches, greener hollows, grey-beige limestone breaking through in small pieces
// on the steep parts (homeward-road.md 0.4). And the first light (act 2, 05:15): the sun is up but behind the east
// ridge, so the valley has no direct light; the tops of the far western hills catch a faint line of gold.
import {
  Color,
  Mesh,
  MeshStandardMaterial,
  ShaderChunk,
  SRGBColorSpace,
  type Material,
} from "three";
import { FOG } from "../shaderPatches";
import { kelvinRGB, sunLook } from "../sun";
import type { LoadedScene } from "./loadScene";

// how far the east ridge stands along the sun's direction (the far land's edge, assets/pipeline/road: far grid ±340 m)
const RIDGE_M = 320;

// the sun's light that the ridge holds back from the valley, for the hilltops that see over it; the lighting's
// sunGain calls glowFor with the sun where it is and what got past the ridge
const glow = { value: new Color() };
export function glowFor(elevDeg: number, gain: number): void {
  const look = sunLook(elevDeg);
  const [r, g, b] = kelvinRGB(look.kelvin);
  glow.value
    .setRGB(r, g, b, SRGBColorSpace)
    .multiplyScalar(look.intensity * (1 - gain));
}

const NOISE = /* glsl */ `
float zjHillHash( vec2 p ) { p = fract( p * vec2( 123.34, 456.21 ) ); p += dot( p, p + 45.32 ); return fract( p.x * p.y ); }
float zjHillNoise( vec2 p ) {
  vec2 i = floor( p ), f = fract( p ), u = f * f * ( 3.0 - 2.0 * f );
  return mix( mix( zjHillHash( i ), zjHillHash( i + vec2( 1.0, 0.0 ) ), u.x ), mix( zjHillHash( i + vec2( 0.0, 1.0 ) ), zjHillHash( i + vec2( 1.0, 1.0 ) ), u.x ), u.y );
}
`;

// In the shader: greener on the whole, scrub in patches; limestone in broken patches, more of it where it is steep
// (the far land's triangles are flat: the slope only moves the threshold, so no triangle shows its edges); and whether
// a point sees the sun over the east ridge (the ridge as a line RIDGE_M away along the sun's direction).
export function hills(s: LoadedScene, ridgeDeg: number | undefined): void {
  const done = new Set<Material>();
  s.root.traverse((o) => {
    if (!(o instanceof Mesh)) return;
    const m = o.material as Material;
    if (
      !(m instanceof MeshStandardMaterial) ||
      m.name !== "hill" ||
      done.has(m)
    )
      return;
    done.add(m);
    const prev = m.onBeforeCompile.bind(m);
    m.onBeforeCompile = (sh, r) => {
      prev(sh, r);
      Object.assign(sh.uniforms, {
        uGlow: glow,
        uSunDir: FOG.sunDir,
        uRidge: {
          value: [RIDGE_M, Math.tan(((ridgeDeg ?? 90) * Math.PI) / 180)],
        },
      });
      sh.vertexShader = sh.vertexShader
        .replace(
          "#include <common>",
          "#include <common>\nvarying vec3 vZjHill;",
        )
        .replace(
          "#include <project_vertex>",
          "#include <project_vertex>\nvZjHill = ( modelMatrix * vec4( transformed, 1.0 ) ).xyz;",
        );
      sh.fragmentShader = sh.fragmentShader
        .replace(
          "#include <common>",
          `#include <common>
varying vec3 vZjHill;
uniform vec3 uGlow, uSunDir;
uniform vec2 uRidge;
${NOISE}`,
        )
        .replace(
          "#include <map_fragment>",
          ShaderChunk.map_fragment.replace(
            "texture2D( map, vMapUv )",
            "mix( texture2D( map, vMapUv ), texture2D( map, vMapUv * 0.23 + vec2( 0.31, 0.17 ) ), smoothstep( 0.35, 0.65, zjHillNoise( vZjHill.xz / 40.0 ) ) )",
          ) +
            `
vec3 zjHillN = normalize( cross( dFdx( vZjHill ), dFdy( vZjHill ) ) );
zjHillN *= sign( zjHillN.y );
{
  vec2 p = vZjHill.xz;
  float big = zjHillNoise( p / 110.0 ), mid = zjHillNoise( p / 26.0 + 5.0 ), fine = zjHillNoise( p / 7.0 + 11.0 );
  float steep = 1.0 - smoothstep( 0.82, 0.96, zjHillN.y );
  diffuseColor.rgb *= mix( vec3( 1.0 ), vec3( 0.8, 0.95, 0.66 ), smoothstep( 0.35, 0.75, big ) );
  diffuseColor.rgb *= mix( vec3( 1.0 ), vec3( 0.42, 0.5, 0.32 ), smoothstep( 0.5, 0.68, mid * 0.65 + fine * 0.35 ) * 0.9 );
  float rock = zjHillNoise( p / 6.0 + 3.0 ) * 0.55 + zjHillNoise( p / 1.8 + 7.0 ) * 0.45;
  float t = 0.8 - 0.24 * steep;
  float pits = 0.6 + 0.4 * zjHillNoise( p * 1.4 + 2.0 );
  diffuseColor.rgb = mix( diffuseColor.rgb, vec3( 0.17, 0.155, 0.13 ) * pits, smoothstep( t, t + 0.05, rock ) * 0.7 );
}`,
        )
        .replace(
          "#include <normal_fragment_maps>",
          ShaderChunk.normal_fragment_maps.replace(
            "mapN.xy *= normalScale;",
            "mapN.xy *= normalScale * 0.3;",
          ),
        )
        .replace(
          "#include <emissivemap_fragment>",
          `#include <emissivemap_fragment>
{
  vec2 toSun = normalize( uSunDir.xz + 1e-5 );
  float along = dot( vZjHill.xz, toSun );
  float over = ( uRidge.x * uRidge.y - vZjHill.y ) / max( uRidge.x - along, 1.0 );
  // only the tops: the light fades in over some tens of metres above the ridge's shadow line, faint (UX round 3 ⑧)
  float lit = along > uRidge.x - 1.0 ? 1.0 : smoothstep( 0.006, 0.03, uSunDir.y / length( uSunDir.xz + 1e-5 ) - over ) * 0.4;
  totalEmissiveRadiance += diffuseColor.rgb * RECIPROCAL_PI * uGlow * max( dot( zjHillN, uSunDir ), 0.0 ) * lit;
}`,
        );
    };
    m.customProgramCacheKey = () => "zj-hill";
    m.needsUpdate = true;
  });
}
