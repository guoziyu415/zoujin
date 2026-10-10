// Bloom, grade and vignette after Neutral tone mapping, MSAA 4x on a half-float target (frontend-design 10.6.1-10.6.2;
// S7). Takes over R3F's render (useFrame priority 1). F-2c turns bloom and MSAA off at L0 (10.6.3).
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import {
  HalfFloatType,
  NeutralToneMapping,
  Vector2,
  WebGLRenderTarget,
} from "three";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { ShaderPass } from "three/examples/jsm/postprocessing/ShaderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { lightState } from "./Lighting";

const GradeShader = {
  uniforms: {
    tDiffuse: { value: null },
    uVig: { value: 0.32 },
    uWarm: { value: 0.06 },
    uContrast: { value: 1.06 },
    uNight: { value: 0 },
    uSat: { value: 1.12 },
  },
  vertexShader:
    "varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }",
  fragmentShader: `uniform sampler2D tDiffuse; uniform float uVig, uWarm, uContrast, uNight, uSat; varying vec2 vUv;
    void main(){ vec4 c = texture2D(tDiffuse, vUv); vec3 col = c.rgb;
      float l = dot(col, vec3(0.2126,0.7152,0.0722));
      col = max(mix(vec3(l), col, uSat), 0.0);
      col = mix(col, col * vec3(1.0 + uWarm, 1.0, 1.0 - uWarm), smoothstep(0.35, 0.9, l));
      col = mix(col, col * vec3(1.0 - uWarm*0.6, 1.0, 1.0 + uWarm), 1.0 - smoothstep(0.05, 0.35, l));
      col = mix(col, vec3(dot(col, vec3(0.2126,0.7152,0.0722))) * vec3(0.62, 0.78, 1.18), uNight * 0.7);
      col = (col - 0.5) * uContrast + 0.5;
      vec2 d = vUv - 0.5; col *= 1.0 - uVig * dot(d, d) * 2.2;
      gl_FragColor = vec4(clamp(col, 0.0, 1.0), c.a); }`,
};

export const frameStats = { calls: 0, triangles: 0, frames: 0 };

export function PostFX() {
  const { gl, scene, camera, size } = useThree();
  const { composer, grade, bloom } = useMemo(() => {
    gl.toneMapping = NeutralToneMapping;
    const rt = new WebGLRenderTarget(1, 1, { type: HalfFloatType, samples: 4 });
    const composer = new EffectComposer(gl, rt);
    composer.addPass(new RenderPass(scene, camera));
    const bloom = new UnrealBloomPass(new Vector2(256, 256), 0.3, 0.2, 3.0);
    composer.addPass(bloom);
    composer.addPass(new OutputPass());
    const grade = new ShaderPass(GradeShader);
    composer.addPass(grade);
    return { composer, grade, bloom };
  }, [gl, scene, camera]);

  useEffect(() => {
    composer.setPixelRatio(gl.getPixelRatio());
    composer.setSize(size.width, size.height);
    bloom.resolution.set(size.width / 2, size.height / 2);
  }, [composer, bloom, gl, size]);
  useEffect(() => () => composer.dispose(), [composer]);

  useFrame(() => {
    grade.uniforms.uNight!.value = lightState.night;
    gl.toneMappingExposure = lightState.exposure * lightState.faceExposure;
    gl.info.autoReset = false;
    gl.info.reset();
    composer.render();
    frameStats.calls = gl.info.render.calls;
    frameStats.triangles = gl.info.render.triangles;
    frameStats.frames++;
  }, 1);
  return null;
}
