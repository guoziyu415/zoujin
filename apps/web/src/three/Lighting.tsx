// Realtime sun with shadows + baked occlusion (in the materials) + physical sky, all following world.clock
// (F-2 range 2; frontend-design 8.5, 10.6.1). Port of S7's "只烘遮蔽" mode, the one UX reviewed (v2-sheet1).
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import {
  AdditiveBlending,
  Color,
  DirectionalLight,
  FogExp2,
  HemisphereLight,
  LinearSRGBColorSpace,
  MathUtils,
  Matrix4,
  Mesh,
  PlaneGeometry,
  PMREMGenerator,
  Scene,
  ShaderMaterial,
  SRGBColorSpace,
  Vector3,
  type WebGLRenderTarget,
} from "three";
import { Sky } from "three/examples/jsm/objects/Sky.js";
import { useWorld } from "./dev/fakeStore";
import { minuteOfDay } from "./scene/frame";
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
const SHADOW_MAP = 2048; // L1 (10.6.3); F-2c lowers it at L0

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
  texColor = max( texColor * uSkyGain, max( max( glow * uDusk, nightSky * uNightSky ), belt * uBelt ) );
  float peak = max( max( texColor.r, texColor.g ), max( texColor.b, 1e-4 ) );
  texColor *= 1.7 * ( 1.0 - exp( -peak / 1.7 ) ) / peak;
  gl_FragColor = vec4( texColor, 1.0 );`;

function makeSky(scale: number): Sky {
  const s = new Sky();
  s.scale.setScalar(scale);
  const u = s.material.uniforms;
  for (const k of ["uSkyGain", "uDusk", "uNightSky", "uBelt", "uAmber"])
    u[k] = { value: 0 };
  s.material.fragmentShader =
    "uniform float uSkyGain, uDusk, uNightSky, uBelt, uAmber;\n" +
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

export function Lighting({ sun: params }: { sun: SunParams }) {
  const { gl, scene, camera } = useThree();
  const parts = useMemo(() => {
    const sun = new DirectionalLight(0xffffff, 1);
    sun.castShadow = true;
    sun.shadow.mapSize.set(SHADOW_MAP, SHADOW_MAP);
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
    const envSky = makeSky(50);
    skyScene.add(envSky);
    return {
      sun,
      hemi,
      sky,
      envSky,
      skyScene,
      disc: makeSunDisc(),
      pmrem: new PMREMGenerator(gl),
    };
  }, [gl]);
  const envRT = useRef<WebGLRenderTarget | null>(null);
  const envTimer = useRef<number>(0);

  useEffect(() => {
    const { sun, hemi, sky, disc, pmrem } = parts;
    scene.add(sun, sun.target, hemi, sky, disc);
    scene.fog = new FogExp2(FOG.base.clone(), FOG.density);
    scene.background = null;
    return () => {
      scene.remove(sun, sun.target, hemi, sky, disc);
      scene.fog = null;
      scene.environment = null;
      envRT.current?.dispose();
      window.clearTimeout(envTimer.current);
      pmrem.dispose();
    };
  }, [parts, scene]);

  // the clock moves the sun
  useEffect(() => {
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
        envRT.current?.dispose();
        envRT.current = pmrem.fromScene(skyScene, 0, 0.1, 100);
        scene.environment = envRT.current.texture;
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
  }, [parts, params, scene]);

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
    const { sun, disc } = parts;
    const d = lightState.sunDir;
    camera.getWorldDirection(tmp.fwd);
    tmp.fwd.y = 0;
    tmp.fwd.normalize();
    tmp.centre
      .copy(camera.position)
      .addScaledVector(tmp.fwd, SHADOW_HALF * 0.55);
    tmp.centre.y = 0;
    const texel = (2 * SHADOW_HALF) / SHADOW_MAP;
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
