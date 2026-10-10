// Global shader chunk patches, imported once before anything compiles (from S7, spikes/frontend/s7-realism README):
// - fog takes the sky's horizon colour and warms towards the sun;
// - a sun glint on the near-mirror water can exceed half-float range (Inf, and the bloom spreads it over the whole
//   frame); even below that a few very hot pixels feed the bloom more than the whole sky does. Highlights stay well
//   above white.
import {
  Color,
  LinearSRGBColorSpace,
  ShaderChunk,
  Vector3,
  type WebGLProgramParametersWithUniforms,
} from "three";

export const HOT_MAX = 48.0;

export const FOG = {
  base: new Color().setRGB(0.31, 0.27, 0.25, LinearSRGBColorSpace),
  density: 0.0014,
  sunDir: { value: new Vector3(0, 1, 0) },
  sunColor: { value: new Color().setRGB(1.7, 1.02, 0.5, LinearSRGBColorSpace) },
};

let done = false;

export function patchShaderChunks(): void {
  if (done) return;
  done = true;
  ShaderChunk.fog_pars_vertex =
    "#ifdef USE_FOG\n varying float vFogDepth;\n varying vec3 vFogDir;\n#endif";
  ShaderChunk.fog_vertex =
    "#ifdef USE_FOG\n vFogDepth = - mvPosition.z;\n vFogDir = ( modelMatrix * vec4( transformed, 1.0 ) ).xyz - cameraPosition;\n#endif";
  ShaderChunk.fog_pars_fragment = ShaderChunk.fog_pars_fragment.replace(
    "varying float vFogDepth;",
    "varying float vFogDepth;\n varying vec3 vFogDir;\n uniform vec3 fogSunDir;\n uniform vec3 fogSunColor;",
  );
  ShaderChunk.fog_fragment = ShaderChunk.fog_fragment.replace(
    "gl_FragColor.rgb = mix( gl_FragColor.rgb, fogColor, fogFactor );",
    "float fogSun = pow( max( dot( normalize( vFogDir ), fogSunDir ), 0.0 ), 5.0 );\n gl_FragColor.rgb = mix( gl_FragColor.rgb, mix( fogColor, fogSunColor, fogSun ), fogFactor );",
  );
  ShaderChunk.opaque_fragment = ShaderChunk.opaque_fragment.replace(
    "gl_FragColor = vec4( outgoingLight, diffuseColor.a );",
    `gl_FragColor = vec4( min( outgoingLight, vec3( ${HOT_MAX.toFixed(1)} ) ), diffuseColor.a );`,
  );
}

// every material that draws with fog binds the two extra uniforms
export function fogUniforms(sh: WebGLProgramParametersWithUniforms): void {
  sh.uniforms.fogSunDir = FOG.sunDir;
  sh.uniforms.fogSunColor = FOG.sunColor;
}
