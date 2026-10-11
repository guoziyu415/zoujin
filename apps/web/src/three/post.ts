// The post-processing chain (frontend-design 10.6.1-10.6.3; S7): the scene into a half-float target with MSAA 4x,
// bloom, then one pass that does Neutral tone mapping, sRGB and the grade and vignette together. L0 turns bloom and
// MSAA off; the last pass is the same at every level, so the colours don't change with the level. Used by PostFX
// for the screen and by the start probe for its off-screen test scene.
import {
  HalfFloatType,
  NeutralToneMapping,
  Vector2,
  WebGLRenderTarget,
  type Camera,
  type Scene,
  type WebGLRenderer,
} from "three";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { OutputShader } from "three/examples/jsm/shaders/OutputShader.js";

// day-for-night after sunset, a little warmth in the highlights and cool in the shadows, contrast, saturation, vignette;
// on the sRGB values, as the separate pass after OutputPass did before. The shadows cool towards blue with red and
// green down together: red alone turned pale colours green in shade (A-0, UX round 6).
// The night's blue is the sky's light (art-direction 3.2; UX on PR #53): a fire and what it lights stay warm. The
// tint lets go by how much warmth a pixel has, r - b itself: a fire adds that, the night sky can't, even to warm
// colours (skin, ochre, terracotta, 緋 stay under 0.28 by sky light alone; a ratio to luminance blew them up in the
// dark). Pale stone in a fire's dim outer ring gets little r - b, so it also counts when warm for its brightness and
// not dark; and anything bright (a flame's core). Only deep in the night, so the afterglow and the pink belt at dusk
// grade as before. On the way from warm to night it goes grey first and then blue, not through purple (UX on #54)
const GRADE_UNIFORMS = "uniform float uVig, uWarm, uContrast, uNight, uSat;\n";
const GRADE = `
  { vec3 col = gl_FragColor.rgb;
    float l = dot(col, vec3(0.2126,0.7152,0.0722));
    col = max(mix(vec3(l), col, uSat), 0.0);
    col = mix(col, col * vec3(1.0 + uWarm, 1.0, 1.0 - uWarm), smoothstep(0.35, 0.9, l));
    col = mix(col, col * vec3(1.0 - uWarm*0.3, 1.0 - uWarm*0.3, 1.0 + uWarm), 1.0 - smoothstep(0.05, 0.35, l));
    l = dot(col, vec3(0.2126,0.7152,0.0722));
    float w = col.r - col.b;
    float lit = max(max(smoothstep(0.3, 0.45, w), smoothstep(0.1, 0.5, w / (l + 0.03)) * smoothstep(0.35, 0.5, l)),
                    smoothstep(0.5, 0.9, l));
    float k = lit * smoothstep(0.4, 0.9, uNight);
    col = mix(col, vec3(l) * mix(vec3(1.0), vec3(0.62, 0.78, 1.18), (1.0 - k) / (1.0 + k)), uNight * 0.7 * (1.0 - k * k));
    col = (col - 0.5) * uContrast + 0.5;
    vec2 d = vUv - 0.5; col *= 1.0 - uVig * dot(d, d) * 2.2;
    gl_FragColor = vec4(clamp(col, 0.0, 1.0), gl_FragColor.a); }
`;

class OutputGradePass extends OutputPass {
  constructor() {
    super();
    Object.assign(this.uniforms, {
      uVig: { value: 0.32 },
      uWarm: { value: 0.06 },
      uContrast: { value: 1.06 },
      uNight: { value: 0 },
      uSat: { value: 1.12 },
    });
    const src = OutputShader.fragmentShader;
    const end = src.lastIndexOf("}");
    this.material.fragmentShader = src
      .slice(0, end)
      .replace("varying vec2 vUv;", GRADE_UNIFORMS + "varying vec2 vUv;")
      .concat(GRADE, "}");
    this.material.needsUpdate = true;
  }
}

export type Post = {
  composer: EffectComposer;
  bloom: UnrealBloomPass;
  out: OutputGradePass;
  setMsaa: (samples: number) => void;
  setSize: (w: number, h: number, dpr: number) => void;
  dispose: () => void;
};

export function makePost(
  gl: WebGLRenderer,
  scene: Scene,
  camera: Camera,
  { msaa = 4, bloom = true } = {},
): Post {
  gl.toneMapping = NeutralToneMapping;
  const rt = new WebGLRenderTarget(1, 1, {
    type: HalfFloatType,
    samples: msaa,
  });
  const composer = new EffectComposer(gl, rt);
  composer.addPass(new RenderPass(scene, camera));
  const bloomPass = new UnrealBloomPass(new Vector2(256, 256), 0.3, 0.2, 3.0);
  bloomPass.enabled = bloom;
  composer.addPass(bloomPass);
  const out = new OutputGradePass();
  composer.addPass(out);
  return {
    composer,
    bloom: bloomPass,
    out,
    setMsaa: (samples) => {
      for (const t of [composer.renderTarget1, composer.renderTarget2]) {
        if (t.samples === samples) continue;
        t.samples = samples;
        t.dispose(); // rebuilt with the new sample count on next use
      }
    },
    setSize: (w, h, dpr) => {
      composer.setPixelRatio(dpr);
      composer.setSize(w, h);
      bloomPass.resolution.set(w / 2, h / 2);
    },
    dispose: () => {
      composer.dispose();
      bloomPass.dispose();
      out.dispose();
    },
  };
}
