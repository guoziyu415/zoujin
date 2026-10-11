// The river's water (F-10 card 4; ux/scenes/homeward-road.md 1.1, 1.5), replacing the placeholder material of the
// pack's water node. Everything is procedural (no textures to download):
// - calm (act 2, 05:15): a dark near-mirror with slow ripples, holding the sky where it looks up past the banks and the
//   hills (low down it mirrors them, dark), and a mist lying in the channel up to about 3.4 m (the deck is 2.2 m over
//   the water: legs in the mist on the bridge);
// - flood (act 4, 11:45): opaque mud yellow-brown, long ridges and foam streaks running downstream, silt bands drawn
//   out along the current, standing waves and foam where the flood piles up on the piles and the snag (rings round
//   the shallows' boulders), lighter slack water where the flow mask says (the upstream shallows, the drowned west
//   road), spray where it breaks on the piles; the ground at the water darker, with a fine foam line, the road damp
//   with puddles mirroring the sky (UX round 2); the distance fog a little thinner (rain-washed air).
// Positions in scene.json's water are plan coordinates (layout.json); turned into glTF here.
import {
  Color,
  DoubleSide,
  Float32BufferAttribute,
  FogExp2,
  InstancedBufferAttribute,
  InstancedBufferGeometry,
  Mesh,
  MeshStandardMaterial,
  PlaneGeometry,
  ShaderMaterial,
  Vector2,
  Vector3,
  Vector4,
  type Material,
  type Scene,
  type WebGLProgramParametersWithUniforms,
} from "three";
import { planToWorld } from "../scene/frame";
import type { LoadedScene } from "../scene/loadScene";
import type { WaterEntry } from "../scene/manifest";
import { FOG, fogUniforms } from "../shaderPatches";

const time = { value: 0 };
const tick = () => (time.value = (performance.now() / 1000) % 3600);

// value noise and the flow map (two phases half a period apart, so the advection never stretches the pattern)
const NOISE = /* glsl */ `
uniform float uTime;
uniform vec2 uFlow;
uniform float uSpeed;
uniform vec4 uSlow[2];
uniform vec3 uSplash[12];
float zjHash( vec2 p ) { p = fract( p * vec2( 123.34, 456.21 ) ); p += dot( p, p + 45.32 ); return fract( p.x * p.y ); }
float zjNoise( vec2 p ) {
  vec2 i = floor( p ), f = fract( p ), u = f * f * ( 3.0 - 2.0 * f );
  return mix( mix( zjHash( i ), zjHash( i + vec2( 1.0, 0.0 ) ), u.x ), mix( zjHash( i + vec2( 0.0, 1.0 ) ), zjHash( i + vec2( 1.0, 1.0 ) ), u.x ), u.y );
}
// 1 in the stream, about 0.25 in slack water
float zjSlack( vec2 p ) {
  float s = 1.0;
  for ( int i = 0; i < 2; i ++ ) s = min( s, mix( 0.25, 1.0, smoothstep( 0.55, 1.0, length( ( p - uSlow[ i ].xy ) / max( uSlow[ i ].zw, vec2( 1e-3 ) ) ) ) ) );
  return s;
}
vec2 zjQ( vec2 p ) { return vec2( dot( p, uFlow ), dot( p, vec2( - uFlow.y, uFlow.x ) ) ); } // along, across the flow
float zjWaves( vec2 p ) {
  vec2 q = zjQ( p );
#ifdef FLOOD
  // long ridges lying along the current with a short chop across them (UX round 2: the flood must read as running)
  return 0.36 * zjNoise( q * vec2( 0.2, 1.1 ) ) + 0.28 * zjNoise( q * vec2( 0.8, 1.7 ) + 7.1 ) + 0.2 * zjNoise( q * vec2( 1.7, 4.4 ) + 13.7 ) + 0.08 * zjNoise( q * 9.5 + 21.0 );
#else
  return 0.5 * zjNoise( q * vec2( 1.6, 2.3 ) ) + 0.35 * zjNoise( q * 4.1 + 3.3 ) + 0.15 * zjNoise( q * 9.0 + 8.8 );
#endif
}
float zjHeight( vec2 p ) {
  vec2 f = uFlow * uSpeed * zjSlack( p );
  float T = 4.0, a = fract( uTime / T ), b = fract( uTime / T + 0.5 );
  return mix( zjWaves( p - f * a * T ), zjWaves( p - f * b * T + vec2( 17.3, 9.1 ) ), abs( 1.0 - 2.0 * a ) );
}
`;

// round the piles, the snag and the shallows' boulders (uSplash: world x, z, strength): the wake downstream, 0..1, and
// the standing water, which stays where it is while the flood runs through it: a hump where the water piles up on the
// upstream side, then a fan of standing waves; round the boulders in slack water, rings instead
const WAKE = /* glsl */ `
float zjWake( vec2 p ) {
  float w = 0.0;
  for ( int i = 0; i < 12; i ++ ) {
    vec2 d = p - uSplash[ i ].xy;
    float along = dot( d, uFlow ), across = dot( d, vec2( - uFlow.y, uFlow.x ) );
    w += uSplash[ i ].z * ( exp( - dot( d, d ) / 0.5 ) + exp( - across * across / ( 0.25 + 0.08 * max( along, 0.0 ) ) ) * smoothstep( - 0.3, 0.2, along ) * exp( - max( along, 0.0 ) / 7.0 ) );
  }
  return clamp( w, 0.0, 1.0 );
}
float zjStand( vec2 p ) {
  float h = 0.0;
  for ( int i = 0; i < 12; i ++ ) {
    float k = uSplash[ i ].z;
    vec2 d = p - uSplash[ i ].xy;
    if ( k <= 0.0 || dot( d, d ) > 64.0 ) continue;
    float along = dot( d, uFlow ), across = dot( d, vec2( - uFlow.y, uFlow.x ) );
    if ( k < 0.5 ) {
      float r = length( d );
      h += 0.25 * sin( r * 13.0 - uTime * 3.0 ) * exp( - r / 0.8 ) * smoothstep( 0.25, 0.5, r );
      continue;
    }
    vec2 u = d + uFlow * 0.35;
    float fan = exp( - across * across / ( 0.1 + 0.07 * max( along, 0.0 ) ) );
    h += k * ( 0.9 * exp( - dot( u, u ) / 0.08 ) + fan * smoothstep( 0.0, 0.5, along ) * exp( - along / 2.5 ) * ( 0.5 + 0.5 * cos( along * 5.5 ) ) );
  }
  return h;
}
`;

type Opts = {
  flood: boolean;
  flow: Vector2;
  speed: number;
  slow: Vector4[];
  splash: [number, number, number][]; // world x, z, strength (≤ 12; spray only where it is 0.5 or more)
  horizonDeg: number; // the hills round the valley, seen from the water
  bank: Vector4; // world x, z of the channel's centre by the bridge, its half width, the banks' height over the water
};

function waterMaterial(o: Opts): Material {
  const mat = new MeshStandardMaterial({
    // mud: yellow-brown, apart from the scarlet of the story (UX round 2); the calm river nearly black
    color: o.flood
      ? new Color().setRGB(0.15, 0.105, 0.036)
      : new Color().setRGB(0.008, 0.012, 0.012),
    roughness: o.flood ? 0.42 : 0.05,
    metalness: 0,
    // muddy water: a dull sheen, mostly its own colour (a stronger blue sky in it turned it mauve); the calm river
    // mirrors the sky
    envMapIntensity: o.flood ? 0.22 : 1,
  });
  mat.name = "water";
  const splash = Array.from(
    { length: 12 },
    (_, i) => new Vector3(...(o.splash[i] ?? [0, 0, 0])),
  );
  mat.onBeforeCompile = (sh: WebGLProgramParametersWithUniforms) => {
    fogUniforms(sh);
    Object.assign(sh.uniforms, {
      uTime: time,
      uFlow: { value: o.flow },
      uSpeed: { value: o.speed },
      uSlow: { value: o.slow },
      uSplash: { value: splash },
      uFoam: { value: new Color().setRGB(0.6, 0.55, 0.45) },
      uHorizon: { value: o.horizonDeg },
      uBank: { value: o.bank },
    });
    const defs = o.flood ? "#define FLOOD\n" : "";
    sh.vertexShader = sh.vertexShader
      .replace(
        "#include <common>",
        `#include <common>\n${defs}${NOISE}\nvarying vec3 vZjPos;`,
      )
      .replace(
        "#include <begin_vertex>",
        `#include <begin_vertex>
vZjPos = ( modelMatrix * vec4( transformed, 1.0 ) ).xyz;
#ifdef FLOOD
// the packs quantise positions: the node's scale turns metres into the mesh's units
// (the troughs only a little under the level: the drowned flats lie just below it and would show through)
transformed.y += 0.24 * ( zjHeight( vZjPos.xz ) - 0.3 ) * zjSlack( vZjPos.xz ) / length( modelMatrix[ 1 ].xyz );
#endif`,
      );
    sh.fragmentShader = sh.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>\n${defs}${NOISE}${o.flood ? WAKE : ""}\nvarying vec3 vZjPos;\nuniform vec3 uFoam;\nuniform float uHorizon;\nuniform vec4 uBank;`,
      )
      .replace(
        "vec4 diffuseColor = vec4( diffuse, opacity );",
        `vec2 zp = vZjPos.xz;
float zh = zjHeight( zp );
float foam = 0.0;
vec3 zjCol = diffuse;
#ifdef FLOOD
float zs = zjSlack( zp );
float zst = zjStand( zp );
zh += 0.5 * zst;
{
  vec2 q = zjQ( zp );
  float adv = uTime * uSpeed;
  q.y += 1.2 * zjNoise( vec2( q.x - adv, q.y ) * 0.15 ); // the streaks wander
  // foam: streaks carried downstream, on the crests, in the wakes and on the standing waves
  float streak = zjNoise( vec2( ( q.x - adv ) * 0.3, q.y * 7.0 ) ) * zjNoise( vec2( ( q.x - adv ) * 1.6, q.y * 11.0 ) + 3.7 );
  float broken = smoothstep( 0.3, 0.7, zjNoise( zp * 2.3 - uFlow * adv ) );
  foam = smoothstep( 0.42, 0.62, streak ) * 0.4 * zs * broken;
  foam += zjWake( zp ) * broken + smoothstep( 0.45, 0.9, zst ) * ( 0.4 + 0.6 * broken );
  foam = clamp( foam, 0.0, 1.0 );
  // silt in the current, lighter and darker bands drawn out along it; the shallows lighter still (UX round 2 ⑥)
  zjCol *= mix( 0.82, 1.18, zjNoise( vec2( ( q.x - adv ) * 0.05, q.y * 0.35 ) ) );
  zjCol = mix( zjCol, zjCol * 1.7 + vec3( 0.02, 0.018, 0.008 ), ( 1.0 - zs ) / 0.75 );
}
#endif
vec3 zjN = vec3( 0.0, 1.0, 0.0 );
vec4 diffuseColor = vec4( mix( zjCol, uFoam, foam ), opacity );`,
      )
      .replace(
        "#include <roughnessmap_fragment>",
        "#include <roughnessmap_fragment>\nroughnessFactor = mix( roughnessFactor, 0.85, foam );",
      )
      .replace(
        "#include <normal_fragment_maps>",
        `#include <normal_fragment_maps>
{
#ifdef FLOOD
  float amp = 0.24 * max( zs, 0.6 ), e = 0.12;
  vec2 g = vec2( zjHeight( zp + vec2( e, 0.0 ) ) + 0.5 * zjStand( zp + vec2( e, 0.0 ) ) - zh, zjHeight( zp + vec2( 0.0, e ) ) + 0.5 * zjStand( zp + vec2( 0.0, e ) ) - zh ) * amp / e;
#else
  float amp = 0.012, e = 0.05;
  vec2 g = vec2( zjHeight( zp + vec2( e, 0.0 ) ) - zh, zjHeight( zp + vec2( 0.0, e ) ) - zh ) * amp / e;
#endif
  zjN = normalize( vec3( - g.x, 1.0, - g.y ) );
  normal = normalize( ( viewMatrix * vec4( zjN, 0.0 ) ).xyz );
}`,
      )
      // what the water mirrors low down is the banks and the hills round the valley, not the bright sky behind them
      // (UX round 2: the calm river read as a pale band, not as dark water holding the sky). The banks: the channel
      // taken as straight by the bridge, how high the bank stands seen from here in the reflected direction
      .replace(
        "#include <lights_fragment_maps>",
        `#include <lights_fragment_maps>
#if defined( RE_IndirectSpecular )
{
  vec3 zr = reflect( normalize( vZjPos - cameraPosition ), zjN );
  float el = degrees( asin( clamp( zr.y, - 1.0, 1.0 ) ) );
  vec2 perp = vec2( - uFlow.y, uFlow.x );
  float acr = dot( vZjPos.xz - uBank.xy, perp ), ra = dot( normalize( zr.xz + 1e-5 ), perp );
  float dist = max( ( ra > 0.0 ? uBank.z - acr : uBank.z + acr ) / max( abs( ra ), 0.05 ), 0.1 );
  float bank = degrees( atan( uBank.w * ( 0.8 + 0.4 * zjNoise( ( vZjPos.xz + zr.xz * dist ) * 0.7 ) ), dist ) );
  float edge = max( uHorizon * ( 0.7 + 0.6 * zjNoise( vec2( atan( zr.z, zr.x ) * 4.0, 0.5 ) ) ), bank );
  float soft = 1.0 + 30.0 * material.roughness; // a rough surface mirrors a blur
  radiance *= mix( 0.15, 1.0, smoothstep( edge - soft, edge + soft, el ) );
}
#endif`,
      );
  };
  return mat;
}

// the ground the flood is lapping at (UX on #103): darker and glossier for a few tens of centimetres above the water,
// with a broken line of fine foam at it, so the drowned west road reads as running on under the water. The rain has
// only just stopped: the road a shade darker everywhere, with puddles in its hollows holding the sky (UX round 2 ⑦)
const GROUND = new Set([
  "floor",
  "silt",
  "grass",
  "gravel",
  "bank",
  "pebbles",
  "outcrop",
]);
function wetEdge(s: LoadedScene, waterNode: string, level: number): void {
  const done = new Set<Material>();
  s.root.traverse((o) => {
    if (!(o instanceof Mesh) || o.name.startsWith(waterNode)) return;
    const m = o.material as Material;
    if (
      !(m instanceof MeshStandardMaterial) ||
      !GROUND.has(m.name) ||
      done.has(m)
    )
      return;
    done.add(m);
    const road = m.name === "floor";
    const prev = m.onBeforeCompile.bind(m);
    m.onBeforeCompile = (sh, r) => {
      prev(sh, r);
      sh.uniforms.uWetLevel = { value: level };
      sh.vertexShader = sh.vertexShader
        .replace("#include <common>", "#include <common>\nvarying vec3 vZjWet;")
        .replace(
          "#include <project_vertex>",
          "#include <project_vertex>\nvZjWet = ( modelMatrix * vec4( transformed, 1.0 ) ).xyz;",
        );
      sh.fragmentShader = sh.fragmentShader
        .replace(
          "#include <common>",
          `#include <common>
${road ? "#define ZJ_ROAD" : ""}
varying vec3 vZjWet;
uniform float uWetLevel;
float zjWetHash( vec2 p ) { p = fract( p * vec2( 123.34, 456.21 ) ); p += dot( p, p + 45.32 ); return fract( p.x * p.y ); }
float zjWetNoise( vec2 p ) {
  vec2 i = floor( p ), f = fract( p ), u = f * f * ( 3.0 - 2.0 * f );
  return mix( mix( zjWetHash( i ), zjWetHash( i + vec2( 1.0, 0.0 ) ), u.x ), mix( zjWetHash( i + vec2( 0.0, 1.0 ) ), zjWetHash( i + vec2( 1.0, 1.0 ) ), u.x ), u.y );
}`,
        )
        .replace(
          "#include <map_fragment>",
          `#include <map_fragment>
float zjAbove = vZjWet.y - uWetLevel;
float zjWet = 1.0 - smoothstep( 0.03, 0.22, zjAbove );
diffuseColor.rgb *= mix( 1.0, 0.55, zjWet );
// the foam line a few centimetres wide across the ground, however flat (on the drowned road it would spread)
float zjSlope = length( vec2( dFdx( vZjWet.y ), dFdy( vZjWet.y ) ) ) / max( length( vec2( length( dFdx( vZjWet.xz ) ), length( dFdy( vZjWet.xz ) ) ) ), 1e-4 );
float zjLine = ( 1.0 - smoothstep( 0.03, 0.08, abs( zjAbove - 0.015 ) / max( zjSlope, 0.05 ) ) ) * smoothstep( 0.4, 0.6, zjWetNoise( vZjWet.xz * 6.0 ) );
diffuseColor.rgb = mix( diffuseColor.rgb, vec3( 0.66, 0.61, 0.52 ), zjLine * 0.8 );
float zjPuddle = 0.0;
#ifdef ZJ_ROAD
// damp all over, and puddles in the ruts and hollows: dark, still, mirroring the sky
diffuseColor.rgb = mix( vec3( dot( diffuseColor.rgb, vec3( 0.3, 0.59, 0.11 ) ) ), diffuseColor.rgb, 1.3 ) * 0.5;
zjPuddle = smoothstep( 0.52, 0.57, zjWetNoise( vZjWet.xz * 0.45 ) * 0.7 + zjWetNoise( vZjWet.xz * 1.7 + 4.1 ) * 0.3 ) * ( 1.0 - zjWet );
diffuseColor.rgb *= 1.0 - 0.6 * zjPuddle;
#endif`,
        )
        .replace(
          "#include <roughnessmap_fragment>",
          `#include <roughnessmap_fragment>
roughnessFactor = mix( roughnessFactor, 0.6, zjWet * ( 1.0 - zjLine ) );
#ifdef ZJ_ROAD
roughnessFactor = mix( roughnessFactor, 0.03, zjPuddle );
#endif`,
        )
        .replace(
          "#include <normal_fragment_maps>",
          `#include <normal_fragment_maps>
#ifdef ZJ_ROAD
normal = normalize( mix( normal, normalize( ( viewMatrix * vec4( 0.0, 1.0, 0.0, 0.0 ) ).xyz ), zjPuddle ) );
#endif`,
        );
    };
    m.customProgramCacheKey = () => (road ? "zj-wet-road" : "zj-wet");
    m.needsUpdate = true;
  });
}

// spray where the flood breaks on the piles: billboards thrown up and carried downstream, one draw call
function spray(o: Opts): Mesh | null {
  const per = 28;
  const breaks = o.splash.filter((s) => s[2] >= 0.5); // the piles and the snag; the boulders sit in slack water
  const n = breaks.reduce((k, s) => k + Math.round(per * s[2]), 0);
  if (!n) return null;
  const base = new Float32Array(n * 3);
  const seed = new Float32Array(n * 4);
  let k = 0;
  let r = 0.37; // a fixed sequence, the same every time
  const rnd = () => (r = (r * 9301 + 0.49297) % 1);
  for (const [x, z, s] of breaks)
    for (let i = 0; i < Math.round(per * s); i++, k++) {
      base.set([x + (rnd() - 0.5) * 0.3, z + (rnd() - 0.5) * 0.3], 3 * k);
      seed.set([rnd(), rnd(), rnd(), s * (0.6 + 0.4 * rnd())], 4 * k);
    }
  const quad = new PlaneGeometry(1, 1);
  const g = new InstancedBufferGeometry();
  g.setIndex(quad.index);
  g.setAttribute("position", quad.getAttribute("position"));
  g.setAttribute("uv", quad.getAttribute("uv"));
  g.instanceCount = n;
  g.setAttribute("aBase", new InstancedBufferAttribute(base, 3));
  g.setAttribute("aSeed", new InstancedBufferAttribute(seed, 4));
  const m = new Mesh(
    g,
    new ShaderMaterial({
      transparent: true,
      depthWrite: false,
      uniforms: {
        uTime: time,
        uFlow: { value: o.flow },
        uLevel: { value: 0 },
        uColor: { value: new Color().setRGB(0.95, 0.92, 0.85) },
      },
      vertexShader: /* glsl */ `
attribute vec3 aBase; attribute vec4 aSeed;
uniform float uTime, uLevel; uniform vec2 uFlow;
varying float vA; varying vec2 vUv;
void main() {
  float t = fract( uTime * ( 0.7 + 0.6 * aSeed.y ) + aSeed.x );
  vec2 side = vec2( cos( aSeed.z * 6.283 ), sin( aSeed.z * 6.283 ) );
  vec3 c = vec3( aBase.x, uLevel, aBase.y ) + vec3( uFlow.x, 0.0, uFlow.y ) * t * 1.8 + vec3( side.x, 0.0, side.y ) * 0.35 * t;
  c.y += aSeed.w * 2.4 * t * ( 1.0 - t );
  vec4 mv = modelViewMatrix * vec4( c, 1.0 );
  mv.xy += position.xy * ( 0.15 + 0.5 * t ) * aSeed.w;
  gl_Position = projectionMatrix * mv;
  vA = clamp( ( 1.0 - t ) * t * 7.0, 0.0, 1.0 );
  vUv = uv;
}`,
      fragmentShader: /* glsl */ `
uniform vec3 uColor; varying float vA; varying vec2 vUv;
void main() {
  float r = length( vUv - 0.5 ) * 2.0;
  gl_FragColor = vec4( uColor, smoothstep( 1.0, 0.15, r ) * vA * 0.6 );
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`,
    }),
  );
  m.frustumCulled = false;
  m.renderOrder = 2;
  return m;
}

// the morning mist in the channel: layers over a ribbon that follows the channel, thinning upwards and near the camera,
// drifting slowly; one draw call. Each layer fades out before it meets the banks (they rise about 1.6 m per metre
// out from the water's edge), so no layer shows a hard line where it cuts into the ground.
function mist(w: WaterEntry, rot: number): Mesh | null {
  const line = w.channelPlan;
  if (!line || line.length < 2 || !w.fog) return null;
  const { heightM, edgeM } = w.fog;
  const pos: number[] = [];
  const across: number[] = []; // [metres from the centre line, half width]
  const index: number[] = [];
  line.forEach(([x, y, half], i) => {
    const a = line[Math.max(0, i - 1)]!;
    const b = line[Math.min(line.length - 1, i + 1)]!;
    const tx = b[0] - a[0];
    const ty = b[1] - a[1];
    const l = Math.hypot(tx, ty) || 1;
    const nx = ty / l; // across the channel
    const ny = -tx / l;
    for (const off of [-half - edgeM, -half, half, half + edgeM]) {
      pos.push(
        ...planToWorld(x + nx * off, y + ny * off, w.levelM + 0.05, rot),
      );
      across.push(off, half);
    }
    if (i)
      for (let j = 0; j < 3; j++) {
        const p = 4 * (i - 1) + j;
        index.push(p, p + 4, p + 1, p + 1, p + 4, p + 5);
      }
  });
  const layers = 7;
  const g = new InstancedBufferGeometry();
  g.setAttribute("position", new Float32BufferAttribute(pos, 3));
  g.setAttribute("aAcross", new Float32BufferAttribute(across, 2));
  g.setIndex(index);
  g.setAttribute(
    "aLayer",
    new InstancedBufferAttribute(
      Float32Array.from({ length: layers }, (_, i) => i / (layers - 1)),
      1,
    ),
  );
  g.instanceCount = layers;
  const colour = { value: new Color() };
  const m = new Mesh(
    g,
    new ShaderMaterial({
      transparent: true,
      depthWrite: false,
      side: DoubleSide,
      uniforms: { uTime: time, uHeight: { value: heightM }, uColor: colour },
      vertexShader: /* glsl */ `
attribute vec2 aAcross; attribute float aLayer; uniform float uHeight;
varying vec2 vAcross; varying float vLayer; varying vec3 vPos;
void main() {
  vec3 p = position; p.y += aLayer * uHeight;
  vAcross = aAcross; vLayer = aLayer; vPos = p;
  gl_Position = projectionMatrix * viewMatrix * vec4( p, 1.0 );
}`,
      fragmentShader: /* glsl */ `
uniform float uTime; uniform vec3 uColor;
uniform float uHeight;
varying vec2 vAcross; varying float vLayer; varying vec3 vPos;
float h( vec2 p ) { p = fract( p * vec2( 123.34, 456.21 ) ); p += dot( p, p + 45.32 ); return fract( p.x * p.y ); }
float n( vec2 p ) { vec2 i = floor( p ), f = fract( p ), u = f * f * ( 3.0 - 2.0 * f );
  return mix( mix( h( i ), h( i + vec2( 1.0, 0.0 ) ), u.x ), mix( h( i + vec2( 0.0, 1.0 ) ), h( i + vec2( 1.0, 1.0 ) ), u.x ), u.y ); }
void main() {
  vec2 p = vPos.xz + vec2( 0.0, vLayer * 7.0 );
  float d = n( p * 0.12 + vec2( 0.03, 0.05 ) * uTime ) * n( p * 0.37 - vec2( 0.06, 0.02 ) * uTime );
  float reach = vAcross.y + 0.2 + 0.6 * vLayer * uHeight; // where this layer would meet the bank
  float a = 0.6 * pow( 1.0 - vLayer, 0.8 ) * ( 1.0 - smoothstep( reach - 1.6, reach, abs( vAcross.x ) ) ) * ( 0.1 + 2.2 * smoothstep( 0.08, 0.5, d ) );
  a *= smoothstep( 0.8, 5.0, distance( cameraPosition, vPos ) );
  gl_FragColor = vec4( uColor, a );
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`,
    }),
  );
  m.frustumCulled = false;
  m.renderOrder = 1;
  return m;
}

// puts the water on the scene's water node; returns what takes it off again
export function attachWater(s: LoadedScene, three: Scene): () => void {
  const w = s.manifest.water!;
  const rot = s.manifest.sun.sceneRotationDeg;
  const xz = (x: number, y: number) => {
    const p = planToWorld(x, y, 0, rot);
    return [p[0], p[2]] as const;
  };
  const f = w.flowDirPlan ?? [0, -1];
  const [fx, fz] = xz(f[0], f[1]);
  const opts: Opts = {
    flood: w.kind === "flood",
    flow: new Vector2(fx, fz).normalize(),
    speed: w.speedMps ?? 0.12,
    slow: [0, 1].map((i) => {
      const e = w.slowPlan?.[i];
      if (!e) return new Vector4(1e4, 1e4, 1, 1);
      const [x, z] = xz(e[0], e[1]);
      return new Vector4(x, z, e[2], e[3]); // the river runs along plan y: the radii keep their axes at rotation 0
    }),
    splash: (w.splashPlan ?? []).map(([x, y, k]) => [...xz(x, y), k]),
    horizonDeg: w.horizonDeg ?? 4,
    bank: (() => {
      const c = w.channelPlan?.reduce((a, b) =>
        Math.abs(b[1]) < Math.abs(a[1]) ? b : a,
      );
      return c
        ? new Vector4(...xz(c[0], c[1]), c[2], w.bankM ?? 0)
        : new Vector4(0, 0, 1, 0);
    })(),
  };
  const added: Mesh[] = [];
  const node = s.root.getObjectByName(w.node);
  const mat = waterMaterial(opts);
  node?.traverse((o) => {
    if (!(o instanceof Mesh)) return;
    (o.material as Material).dispose();
    o.material = mat;
    o.receiveShadow = true;
    o.onBeforeRender = () => {
      tick();
      // rain-washed air: the distance fog a little thinner than the plaza's
      if (w.haze && three.fog instanceof FogExp2)
        three.fog.density = FOG.density * w.haze;
    };
  });
  if (opts.flood) wetEdge(s, w.node, w.levelM);
  const sp = opts.flood ? spray(opts) : null;
  if (sp) {
    (sp.material as ShaderMaterial).uniforms.uLevel!.value = w.levelM;
    added.push(sp);
  }
  const ms = mist(w, rot);
  if (ms) {
    // lit like the fog (the sky's horizon colour), brighter: morning mist over dark water
    const u = (ms.material as ShaderMaterial).uniforms.uColor!.value as Color;
    ms.onBeforeRender = () => {
      tick();
      if (three.fog) u.copy(three.fog.color).multiplyScalar(2.5);
    };
    added.push(ms);
  }
  for (const m of added) s.root.add(m);
  return () => {
    for (const m of added) {
      m.removeFromParent();
      m.geometry.dispose();
      (m.material as Material).dispose();
    }
    mat.dispose();
  };
}
