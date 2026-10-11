// Realtime sun with shadows + baked occlusion (in the materials) + physical sky, all following world.clock
// (F-2 range 2; frontend-design 8.5, 10.6.1). Port of S7's "只烘遮蔽" mode, the one UX reviewed (v2-sheet1).
// The environment light has the plaza floor under the horizon and a skylight-coloured sky (A-0 round 5, below).
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import {
  AdditiveBlending,
  CircleGeometry,
  Color,
  DirectionalLight,
  FogExp2,
  HemisphereLight,
  LinearSRGBColorSpace,
  MathUtils,
  Matrix4,
  Mesh,
  MeshStandardMaterial,
  type Object3D,
  OrthographicCamera,
  PlaneGeometry,
  PMREMGenerator,
  Raycaster,
  Scene,
  ShaderMaterial,
  SRGBColorSpace,
  Vector3,
  type WebGLRenderTarget,
} from "three";
import { Sky } from "three/examples/jsm/objects/Sky.js";
import { useWorld } from "./dev/fakeStore";
import type { NavData } from "./nav/navmesh";
import { SETTINGS } from "./quality/levels";
import { useQuality } from "./quality/quality";
import { minuteOfDay } from "./scene/frame";
import type { SceneManifest } from "./scene/manifest";
import { FOG } from "./shaderPatches";
import { kelvinRGB, sunAt, sunLook, type SunParams } from "./sun";

// read by the post-processing every frame (grade's day-for-night, exposure)
export const lightState = {
  night: 0,
  exposure: 1,
  faceExposure: 1,
  sunDir: new Vector3(0, 1, 0),
  sunUp: true,
};

// the test hook regenerates the environment at once instead of after the debounce
export const lighting = { settle: () => {} };

const SHADOW_HALF = 36; // metres either side of the shadow box (S7)

function endFade(r: {
  current: { from: WebGLRenderTarget; mix: WebGLRenderTarget } | null;
}) {
  r.current?.from.dispose();
  r.current?.mix.dispose();
  r.current = null;
}

// Sky.js goes black as soon as the sun is down and its forward scattering near a low sun runs far above the baked sky:
// afterglow on the sunset side, a dark blue night, an amber low sun, the pink belt, a soft knee on the brightest channel
const SKY_PATCH = `
  float up = max( direction.y, 0.0 );
  float side = dot( normalize( direction.xz + 1e-5 ), normalize( vSunDirection.xz + 1e-5 ) ) * 0.5 + 0.5;
  vec3 glow = mix( vec3( 0.0 ), vec3( 0.55, 0.22, 0.08 ), pow( side, 3.0 ) ) * exp( -up * 9.0 ) + vec3( 0.05, 0.07, 0.14 ) * ( 1.0 - up * 0.6 );
  vec3 nightSky = vec3( 0.012, 0.02, 0.05 ) * ( 1.0 - up * 0.5 );
  float nearSun = pow( max( dot( direction, vSunDirection ), 0.0 ), 12.0 );
  texColor *= mix( vec3( 1.0 ), vec3( 1.0, 0.66, 0.38 ), clamp( pow( side, 6.0 ) * exp( -up * 2.5 ) + nearSun * 0.6, 0.0, 1.0 ) * uAmber );
  float anti = pow( 1.0 - side, 2.0 );
  vec3 belt = vec3( 0.55, 0.27, 0.33 ) * exp( -pow( ( up - 0.09 ) / 0.06, 2.0 ) ) * anti + vec3( 0.15, 0.2, 0.38 ) * ( 1.0 - up * 0.45 );
  vec3 sl = texColor * uSkyGain;
  vec3 dusk = max( max( glow * uDusk, nightSky * uNightSky ), belt * uBelt );
  texColor = max( sl, dusk );
  float peak = max( max( texColor.r, texColor.g ), max( texColor.b, 1e-4 ) );
  // the knee from the colour before the locus move, so the light keeps its brightness
  if ( uEnvLocus > 0.5 ) texColor = max( toLocus( sl ), dusk );
  texColor *= 1.7 * ( 1.0 - exp( -peak / 1.7 ) ) / peak;
  gl_FragColor = vec4( texColor, 1.0 );`;

// The sky that lights the scene (not the one you see) is real skylight: each colour moved onto the blackbody locus, no
// bluer than 10000 K. Sky.js is cyan, off the locus (green over red up to 2.2 at the zenith at 17:30, where skylight
// never passes 1.46), so in shade the pale wool and the limestone came out green-grey (A-0, UX rounds 5 and 6; a
// constant tint fixed one direction only). Green over red as a function of blue over red, a fit to Planck's law
// through the CIE 1931 observer from 5000 K up (linear sRGB); only cool colours move. Same brightness; the glow, the
// night sky and the dusk belt keep their colours.
const SKYLIGHT_LOCUS = `
vec3 toLocus( vec3 c ) {
  float r = max( c.r, 1e-5 );
  float b = min( c.b, r * 1.64 );
  float L = log( max( b, 1e-5 ) / r );
  float gr = exp( ( -0.0147 * L + 0.377 ) * L - 0.0532 );
  vec3 o = vec3( c.r, mix( c.g, min( c.g, r * gr ), smoothstep( 0.0, 0.3, L ) ), b );
  vec3 w = vec3( 0.2126, 0.7152, 0.0722 );
  return o * ( dot( c, w ) / max( dot( o, w ), 1e-6 ) );
}
`;

function makeSky(scale: number, locus = false): Sky {
  const s = new Sky();
  s.scale.setScalar(scale);
  const u = s.material.uniforms;
  for (const k of ["uSkyGain", "uDusk", "uNightSky", "uBelt", "uAmber"])
    u[k] = { value: 0 };
  u.uEnvLocus = { value: locus ? 1 : 0 };
  s.material.fragmentShader =
    "uniform float uSkyGain, uDusk, uNightSky, uBelt, uAmber, uEnvLocus;\n" +
    SKYLIGHT_LOCUS +
    s.material.fragmentShader.replace(
      "gl_FragColor = vec4( texColor, 1.0 );",
      SKY_PATCH,
    );
  u.turbidity!.value = 4.5;
  u.rayleigh!.value = 2.2;
  u.mieCoefficient!.value = 0.0028;
  u.mieDirectionalG!.value = 0.8;
  if (u.showSunDisc) u.showSunDisc.value = 0; // its 760x peak blew out the bloom; the disc below is drawn instead
  if (u.cloudCoverage) u.cloudCoverage.value = 0;
  return s;
}

function makeSunDisc(): Mesh {
  const m = new Mesh(
    new PlaneGeometry(1, 1),
    new ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: AdditiveBlending,
      fog: false,
      toneMapped: true,
      uniforms: {
        uColor: { value: new Color(1, 0.72, 0.42) },
        uGain: { value: 1 },
      },
      vertexShader:
        "varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
      fragmentShader:
        "uniform vec3 uColor; uniform float uGain; varying vec2 vUv; void main(){ float r = length(vUv - 0.5) * 2.0; float core = (1.0 - smoothstep(0.14, 0.17, r)) * 40.0; float halo = exp(-r * 7.0) * 2.0; gl_FragColor = vec4(min(uColor * (core + halo) * uGain, vec3(60.0)), 1.0); }",
    }),
  );
  m.frustumCulled = false;
  m.renderOrder = -1;
  return m;
}

// regenerating the environment light costs a few ms: at most every 250 ms while the clock moves
const ENV_EVERY_MS = 250;

// The environment has the plaza floor under the horizon (A-0, UX round 5; art-direction 3.2: faces are filled by the
// warm light the sunlit limestone throws back): with the sky alone, whatever was in shade was lit by blue only. A disc
// of the floor's colour lit by the sun, as much of it as reaches the walkable ground (rays to the sun against the
// shadow caster), and by the sky. The whole plaza's share, not the ground round the player: the environment lights
// every face in the scene, so it follows the clock only, not the player's steps (UX on #69). When the plaza is in shade
// (17:30) the bounce stays weak and cool. The sky alone is rendered first to light the disc, then sky and disc together
// make the environment.
const GROUND_DROP = 1.2; // the disc this far under the environment's centre: a person's middle above the floor
// The disc leaves out the light the sunlit walls throw back (the castle's front at 17:30). This stands in for it: at
// noon the plaza comes back to the brightness UX approved, and the shade at 17:30 stays a little darker than before.
const ENV_GAIN = 1.3;
const LIT_POINTS = 32;
const LIT_EVERY = MathUtils.degToRad(1); // the share is cast again once the sun has moved this far (it costs ~15 ms)
const FADE_MS = 1000; // a new environment fades in over this (UX on #69)

// the floor's albedo: its base texture's mean colour (scene.json keeps it) times the material colour, linear
export function groundAlbedo(m: SceneManifest): Color {
  const e = m.materials.floor;
  const mean = e?.base ? m.textures[e.base]?.std.mean : undefined;
  const c = new Color().setRGB(
    (mean?.[0] ?? 128) / 255,
    (mean?.[1] ?? 128) / 255,
    (mean?.[2] ?? 128) / 255,
    SRGBColorSpace,
  );
  return e ? c.multiply(new Color().setRGB(...e.color)) : c;
}

// points spread evenly by area over the navmesh's ground triangles (a quasi-random sequence, the same every time)
export function walkPoints(nav: NavData, n = LIT_POINTS): Vector3[] {
  const t = nav.detail.tris;
  const area: number[] = [];
  let sum = 0;
  for (let i = 0; i < t.length; i += 9) {
    const ux = t[i + 3]! - t[i]!;
    const uz = t[i + 5]! - t[i + 2]!;
    const vx = t[i + 6]! - t[i]!;
    const vz = t[i + 8]! - t[i + 2]!;
    area.push((sum += Math.abs(ux * vz - uz * vx)));
  }
  const pts: Vector3[] = [];
  for (let k = 0, j = 0; k < n && sum > 0; k++) {
    while (area[j]! < ((k + 0.5) / n) * sum) j++;
    let a = (k * 0.7548777) % 1;
    let b = (k * 0.5698403) % 1;
    if (a + b > 1) [a, b] = [1 - a, 1 - b];
    const i = 9 * j;
    pts.push(
      new Vector3(
        t[i]! + a * (t[i + 3]! - t[i]!) + b * (t[i + 6]! - t[i]!),
        t[i + 1]! +
          a * (t[i + 4]! - t[i + 1]!) +
          b * (t[i + 7]! - t[i + 1]!) +
          0.03,
        t[i + 2]! + a * (t[i + 5]! - t[i + 2]!) + b * (t[i + 8]! - t[i + 2]!),
      ),
    );
  }
  return pts;
}

const ray = new Raycaster();

// how much of the walkable ground the sun reaches
function litShare(blockers: Object3D[], pts: Vector3[]) {
  const d = lightState.sunDir;
  if (d.y < 0.005 || !blockers.length || !pts.length) return 0;
  let lit = 0;
  ray.far = 300;
  for (const p of pts) {
    ray.set(p, d);
    if (!ray.intersectObjects(blockers, false).length) lit++;
  }
  return lit / pts.length;
}

// the fade between two environments: both are PMREM targets of one size, so a texel-by-texel mix is exact
function makeFade() {
  const mat = new ShaderMaterial({
    uniforms: { a: { value: null }, b: { value: null }, k: { value: 0 } },
    vertexShader: "void main(){ gl_Position = vec4(position.xy, 0.0, 1.0); }",
    fragmentShader:
      "uniform sampler2D a, b; uniform float k; void main(){ ivec2 p = ivec2(gl_FragCoord.xy); gl_FragColor = mix(texelFetch(a, p, 0), texelFetch(b, p, 0), k); }",
    depthTest: false,
    depthWrite: false,
  });
  const quad = new Mesh(new PlaneGeometry(2, 2), mat);
  quad.frustumCulled = false;
  return { mat, scene: new Scene().add(quad), cam: new OrthographicCamera() };
}

export function Lighting({
  sun: params,
  ground,
  blockers,
  nav,
}: {
  sun: SunParams;
  ground: Color;
  blockers: Object3D[];
  nav: NavData;
}) {
  const { gl, scene, camera } = useThree();
  const parts = useMemo(() => {
    const sun = new DirectionalLight(0xffffff, 1);
    sun.castShadow = true;
    const q = SETTINGS[useQuality.getState().applied]; // the effect below follows later changes
    sun.shadow.mapSize.set(q.shadowMap, q.shadowMap);
    sun.shadow.radius = q.shadowRadius;
    sun.shadow.bias = -0.0004;
    sun.shadow.normalBias = 0.05;
    const c = sun.shadow.camera;
    c.left = -SHADOW_HALF;
    c.right = SHADOW_HALF;
    c.top = SHADOW_HALF;
    c.bottom = -SHADOW_HALF;
    c.near = 1;
    c.far = 220;
    c.updateProjectionMatrix();
    const hemi = new HemisphereLight(0xbcd0ff, 0x8a7560, 0);
    const sky = makeSky(4000);
    const skyScene = new Scene();
    const envSky = makeSky(50, true);
    const floor = new Mesh(
      new CircleGeometry(40, 48).rotateX(-Math.PI / 2),
      new MeshStandardMaterial({ roughness: 1, metalness: 0 }),
    );
    floor.position.y = -GROUND_DROP;
    const floorSun = new DirectionalLight(0xffffff, 1);
    skyScene.add(envSky, floor, floorSun, floorSun.target);
    return {
      sun,
      hemi,
      sky,
      envSky,
      skyScene,
      floor,
      floorSun,
      disc: makeSunDisc(),
      pmrem: new PMREMGenerator(gl),
      pmremSky: new PMREMGenerator(gl), // the sky alone, small: it only lights the disc
      fade: makeFade(),
    };
  }, [gl]);
  const applied = useQuality((s) => s.applied);
  const envRT = useRef<WebGLRenderTarget | null>(null);
  const envTimer = useRef<number>(0);
  // fading in envRT: the one it replaces, the mix shown meanwhile, when it started
  const fading = useRef<{
    from: WebGLRenderTarget;
    mix: WebGLRenderTarget;
    start: number;
  } | null>(null);
  const points = useMemo(() => walkPoints(nav), [nav]);

  useEffect(() => {
    (parts.floor.material as MeshStandardMaterial).color.copy(ground);
  }, [parts, ground]);

  useEffect(() => {
    const { sun, hemi, sky, disc, pmrem, pmremSky, floor, fade } = parts;
    scene.add(sun, sun.target, hemi, sky, disc);
    scene.fog = new FogExp2(FOG.base.clone(), FOG.density);
    scene.background = null;
    scene.environmentIntensity = ENV_GAIN;
    return () => {
      scene.remove(sun, sun.target, hemi, sky, disc);
      scene.fog = null;
      scene.environment = null;
      scene.environmentIntensity = 1;
      envRT.current?.dispose();
      endFade(fading);
      window.clearTimeout(envTimer.current);
      pmrem.dispose();
      pmremSky.dispose();
      floor.geometry.dispose();
      (floor.material as MeshStandardMaterial).dispose();
      fade.mat.dispose();
    };
  }, [parts, scene]);

  // the quality level (10.6.3): 1024 at L0, 2048 above; soft edges (a wider PCF radius) at L2 / L3
  useEffect(() => {
    const { shadow } = parts.sun;
    const s = SETTINGS[applied];
    if (shadow.mapSize.x !== s.shadowMap) {
      shadow.mapSize.set(s.shadowMap, s.shadowMap);
      shadow.map?.dispose();
      shadow.map = null; // made again at the new size on the next frame
    }
    shadow.radius = s.shadowRadius;
  }, [parts, applied]);

  // the clock moves the sun
  useEffect(() => {
    const cast = { dir: new Vector3(), lit: -1 };
    const apply = (t: number, immediate: boolean) => {
      const { sun, hemi, sky, envSky, skyScene, disc, pmrem } = parts;
      const pos = sunAt(minuteOfDay(t), params);
      const look = sunLook(pos.elevDeg);
      lightState.sunDir.set(...pos.dir);
      lightState.night = look.night;
      lightState.exposure = look.exposure;
      lightState.sunUp = pos.dir[1] > -0.02;
      FOG.sunDir.value.copy(lightState.sunDir);
      for (const s of [sky, envSky]) {
        const u = s.material.uniforms;
        u.sunPosition!.value.copy(lightState.sunDir);
        u.uSkyGain!.value = look.skyGain;
        u.uDusk!.value = look.dusk;
        u.uNightSky!.value = look.nightSky;
        u.uBelt!.value = look.belt;
        u.uAmber!.value = look.amber;
      }
      const [r, g, b] = kelvinRGB(look.kelvin);
      sun.color.setRGB(r, g, b, SRGBColorSpace);
      sun.intensity = look.intensity;
      const [dr, dg, db] = kelvinRGB(look.kelvin + 300);
      (disc.material as ShaderMaterial).uniforms.uColor!.value.setRGB(
        dr,
        dg,
        db,
        SRGBColorSpace,
      );
      (disc.material as ShaderMaterial).uniforms.uGain!.value = look.discGain;
      const dusk =
        MathUtils.clamp((3 - pos.elevDeg) / 5, 0, 1) * (1 - look.night);
      hemi.color.setRGB(
        0.45 + 0.3 * dusk,
        0.55 + 0.1 * dusk,
        0.9 - 0.15 * dusk,
        LinearSRGBColorSpace,
      );
      hemi.groundColor.setRGB(0.12, 0.1, 0.08, LinearSRGBColorSpace);
      hemi.intensity = look.hemi;
      if (scene.fog)
        scene.fog.color.copy(FOG.base).multiplyScalar(1 - 0.85 * look.night);
      FOG.sunColor.value.copy(sun.color).multiplyScalar(look.fogSun);
      const env = () => {
        const { floor, floorSun, pmremSky } = parts;
        // one fade at a time: a change meanwhile waits for it (the test hook's settle doesn't)
        if (fading.current && !immediate) {
          envTimer.current = window.setTimeout(env, ENV_EVERY_MS);
          return;
        }
        endFade(fading);
        if (cast.lit < 0 || cast.dir.angleTo(lightState.sunDir) > LIT_EVERY) {
          cast.lit = litShare(blockers, points);
          cast.dir.copy(lightState.sunDir);
        }
        const lit = cast.lit;
        floor.visible = false;
        skyScene.environment = null;
        const skyOnly = pmremSky.fromScene(skyScene, 0, 0.1, 100, { size: 32 });
        floor.visible = true;
        skyScene.environment = skyOnly.texture;
        floorSun.color.copy(sun.color);
        floorSun.intensity = sun.intensity * lit;
        floorSun.position.copy(lightState.sunDir);
        floorSun.target.position.set(0, 0, 0);
        floorSun.target.updateMatrixWorld();
        const old = envRT.current;
        envRT.current = pmrem.fromScene(skyScene, 0, 0.1, 100);
        skyOnly.dispose();
        if (old && !immediate) {
          const mix = envRT.current.clone();
          fading.current = { from: old, mix, start: performance.now() };
          scene.environment = mix.texture; // drawn from the next frame on
        } else {
          old?.dispose();
          scene.environment = envRT.current.texture;
        }
      };
      window.clearTimeout(envTimer.current);
      if (immediate) env();
      else envTimer.current = window.setTimeout(env, ENV_EVERY_MS);
    };
    apply(useWorld.getState().clock.t, true);
    lighting.settle = () => apply(useWorld.getState().clock.t, true);
    return useWorld.subscribe((s, prev) => {
      if (s.clock.t !== prev.clock.t) apply(s.clock.t, false);
    });
  }, [parts, params, scene, blockers, points]);

  // shadow box and the sun disc follow the camera; snapped to shadow texels so the edges don't crawl
  const tmp = useMemo(
    () => ({
      fwd: new Vector3(),
      centre: new Vector3(),
      rot: new Matrix4(),
      inv: new Matrix4(),
      o: new Vector3(),
      up: new Vector3(0, 1, 0),
    }),
    [],
  );
  useFrame(() => {
    const { sun, disc, fade } = parts;
    const d = lightState.sunDir;
    const f = fading.current;
    if (f && envRT.current) {
      const k = Math.min(1, (performance.now() - f.start) / FADE_MS);
      const u = fade.mat.uniforms;
      u.a!.value = f.from.texture;
      u.b!.value = envRT.current.texture;
      u.k!.value = k;
      const was = gl.getRenderTarget();
      gl.setRenderTarget(f.mix);
      gl.render(fade.scene, fade.cam);
      gl.setRenderTarget(was);
      if (k >= 1) {
        scene.environment = envRT.current.texture;
        endFade(fading);
      }
    }
    camera.getWorldDirection(tmp.fwd);
    tmp.fwd.y = 0;
    tmp.fwd.normalize();
    tmp.centre
      .copy(camera.position)
      .addScaledVector(tmp.fwd, SHADOW_HALF * 0.55);
    tmp.centre.y = 0;
    const texel = (2 * SHADOW_HALF) / sun.shadow.mapSize.x;
    tmp.rot.lookAt(tmp.o, tmp.fwd.copy(d).negate(), tmp.up);
    tmp.inv.copy(tmp.rot).invert();
    tmp.centre.applyMatrix4(tmp.inv);
    tmp.centre.x = Math.round(tmp.centre.x / texel) * texel;
    tmp.centre.y = Math.round(tmp.centre.y / texel) * texel;
    tmp.centre.applyMatrix4(tmp.rot);
    sun.target.position.copy(tmp.centre);
    sun.position.copy(tmp.centre).addScaledVector(d, 120);
    sun.target.updateMatrixWorld();
    const D = 1200; // glow radius about 4°, the disc about 0.7°
    disc.visible = lightState.sunUp;
    disc.position.copy(camera.position).addScaledVector(d, D);
    disc.scale.setScalar(2 * D * Math.tan(MathUtils.degToRad(4)));
    disc.lookAt(camera.position);
    // looking into a sun that is still up: stop down a little (adapts over about a second)
    camera.getWorldDirection(tmp.fwd);
    const face = lightState.sunUp
      ? 1 -
        0.4 *
          MathUtils.smoothstep(tmp.fwd.dot(d), 0.4, 0.95) *
          MathUtils.clamp(d.y * 20 + 0.5, 0, 1)
      : 1;
    lightState.faceExposure += (face - lightState.faceExposure) * 0.05;
  }, -1);
  return null;
}
