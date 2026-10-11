// The sky over the flood (act 4, 11:45; UX round 2 ②): the storm has passed, cumulus breaking up with bright edges
// where the sun catches them, and to the north, over the mountains upstream where the rain still falls, a layered dark
// bank whose upper edge the sun lights. Drawn on a dome round the camera behind everything (the land hides its foot),
// one draw call, procedural (no textures); the pack's grey rain-cloud cards, which read as one more mountain or a
// smudge, are hidden.
import {
  BackSide,
  Color,
  Mesh,
  MeshStandardMaterial,
  ShaderMaterial,
  SphereGeometry,
  Vector2,
  type Camera,
  type Material,
} from "three";
import { FOG } from "../shaderPatches";
import { planToWorld } from "./frame";
import type { LoadedScene } from "./loadScene";

const R = 1000; // inside the camera's far plane (1500), past the far land (±340 m)

const time = { value: 0 };

// The fragment shader: the cloud layer seen in perspective (flattening towards the horizon); the broken cumulus,
// billowed (folded noise on the finer octaves), sharp-edged, a little warped; in shadow where the cloud gets thicker
// towards the sun and on its underside (towards the horizon in this projection), thin edges facing the sun shine; the
// bank over the mountains upstream, low to the north: billowed in the sky's own angles (not the cumulus' perspective
// plane, which smears into streaks that low; UX round 3 ③), its lumpy top lit by the sun, darker below; all of it
// into the haze at the horizon. (No comments inside the shader strings: they ship in the 3D chunk.)

export function clouds(s: LoadedScene): (() => void) | null {
  const cards: Mesh[] = [];
  s.root.traverse((o) => {
    if (
      o instanceof Mesh &&
      o.material instanceof MeshStandardMaterial &&
      o.material.name === "raincloud"
    )
      cards.push(o);
  });
  if (!cards.length) return null; // only the packs with weather (the flood) have them
  for (const c of cards) c.visible = false;
  const n = planToWorld(0, 1, 0, s.manifest.sun.sceneRotationDeg);
  const sun = { value: new Color() };
  const amb = { value: new Color() };
  const m = new Mesh(
    new SphereGeometry(R, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2 + 0.05),
    new ShaderMaterial({
      side: BackSide,
      transparent: true,
      depthWrite: false,
      fog: false,
      uniforms: {
        uTime: time,
        uSunDir: FOG.sunDir,
        uSun: sun,
        uAmb: amb,
        uNorth: { value: new Vector2(n[0], n[2]).normalize() },
      },
      vertexShader: /* glsl */ `
varying vec3 vDir;
void main() {
  vDir = position;
  gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
}`,
      fragmentShader: /* glsl */ `
uniform float uTime;
uniform vec3 uSunDir, uSun, uAmb;
uniform vec2 uNorth;
varying vec3 vDir;
float h1( vec2 p ) { p = fract( p * vec2( 123.34, 456.21 ) ); p += dot( p, p + 45.32 ); return fract( p.x * p.y ); }
float n1( vec2 p ) {
  vec2 i = floor( p ), f = fract( p ), u = f * f * ( 3.0 - 2.0 * f );
  return mix( mix( h1( i ), h1( i + vec2( 1.0, 0.0 ) ), u.x ), mix( h1( i + vec2( 0.0, 1.0 ) ), h1( i + vec2( 1.0, 1.0 ) ), u.x ), u.y );
}
float fbm( vec2 p ) {
  float a = 0.5, s = 0.0;
  for ( int i = 0; i < 5; i ++ ) { s += a * n1( p ); p = p * 2.03 + vec2( 1.7, 9.2 ); a *= 0.5; }
  return s;
}
void main() {
  vec3 d = normalize( vDir );
  float h = max( d.y, 0.0 );
  vec2 p = d.xz / ( h + 0.1 ) * 0.9 + vec2( uTime * 0.006, uTime * 0.002 );
  vec2 toSun = normalize( uSunDir.xz + 1e-5 );
  vec2 w = p + 0.35 * vec2( n1( p * 1.3 ), n1( p * 1.3 + 4.4 ) );
  float c = 0.65 * fbm( w ) + 0.35 * ( 1.0 - abs( 2.0 * fbm( w * 2.7 + 2.1 ) - 1.0 ) );
  float cover = 0.6;
  float a = smoothstep( cover, cover + 0.06, c );
  vec2 down = normalize( d.xz + 1e-5 ) * 0.1;
  float shade = clamp( ( fbm( w + toSun * 0.15 ) - fbm( w ) ) * 6.0 + 0.4 + ( fbm( w - down ) - fbm( w + down ) ) * 3.0, 0.0, 1.0 );
  float core = smoothstep( cover + 0.04, cover + 0.3, c );
  vec3 col = mix( uSun, uAmb, clamp( shade * 0.7 + core * 0.3, 0.0, 1.0 ) );
  vec2 dn = normalize( d.xz + 1e-5 );
  float north = smoothstep( 0.35, 0.9, dot( dn, uNorth ) );
  float az = atan( dot( dn, vec2( - uNorth.y, uNorth.x ) ), dot( dn, uNorth ) );
  vec2 g = vec2( az, h ) * 9.0 + vec2( uTime * 0.004, 0.0 );
  float lump = fbm( g );
  float top = 0.24 + 0.06 * n1( vec2( az * 3.0, 1.3 ) ) + 0.09 * ( lump - 0.5 ) - 0.08 * ( 1.0 - north );
  float bank = north * smoothstep( top + 0.012, top - 0.012, h );
  float bill = fbm( g * 2.1 + 3.1 );
  vec3 dark = uAmb * ( 0.26 + 0.22 * bill + 0.22 * smoothstep( 0.0, top, h ) );
  float rim = smoothstep( top - 0.08, top - 0.004, h ) * ( 0.45 + 0.55 * bill );
  vec3 bankCol = mix( dark, uSun * 0.8, rim * rim );
  col = mix( col, bankCol, bank );
  a = max( a, bank * 0.97 );
  a *= smoothstep( - 0.005, 0.05, d.y );
  gl_FragColor = vec4( col, a );
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`,
    }),
  );
  m.name = "clouds";
  m.frustumCulled = false;
  m.renderOrder = -1;
  m.onBeforeRender = (_r, _s, cam: Camera) => {
    time.value = (performance.now() / 1000) % 3600;
    m.position.copy(cam.position);
    m.updateMatrixWorld();
    // sunlit cloud tops, and the light under them: the sky's own colour, from the fog's
    // (the sun's colour taken most of the way to white: at noon a cloud top is white, not the sun's warm tint)
    const f = FOG.sunColor.value;
    const l = 0.2126 * f.r + 0.7152 * f.g + 0.0722 * f.b;
    sun.value.setRGB(l, l, l).lerp(f, 0.25).multiplyScalar(1.25);
    amb.value.setRGB(0.5, 0.55, 0.64).multiplyScalar(l);
  };
  s.root.add(m);
  return () => {
    m.removeFromParent();
    m.geometry.dispose();
    (m.material as Material).dispose();
  };
}
