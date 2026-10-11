// Global shader chunk patches, imported once before anything compiles (from S7, spikes/frontend/s7-realism README):
// - fog takes the sky's horizon colour and warms towards the sun;
// - a sun glint on the near-mirror water can exceed half-float range (Inf, and the bloom spreads it over the whole
//   frame); even below that a few very hot pixels feed the bloom more than the whole sky does. Highlights stay well
//   above white.
// - a lamp-lit room (the castle's throne hall, F-14): inside HALL's box the sky's light (hemisphere, environment) is
//   taken out and the room's own light put in: the baked lamps (ZJ_LAMP, the scene's materials) or a warm fill
//   (people). The live sun and its shadows stay, so what comes in through the door is the real sun. Off (HALL.on 0)
//   everywhere else.
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

export const HALL = {
  on: { value: 0 },
  min: { value: new Vector3() },
  max: { value: new Vector3() },
  fill: { value: new Color(0, 0, 0) }, // irradiance for what has no baked lamp light (people)
  lampOut: { value: 0 }, // the lamps' share outside the room (braziers lit at night)
};

const HALL_PARS = `
 uniform float zjHallOn;
 uniform vec3 zjHallMin;
 uniform vec3 zjHallMax;
 uniform vec3 zjHallFill;
 uniform float zjLampOut;
 #ifdef ZJ_LAMP
 uniform sampler2D zjLampMap;
 uniform float zjLampK;
 #endif`;

const HALL_LIGHT = `
#if defined( USE_FOG ) && defined( RE_IndirectDiffuse )
{
 vec3 zjW = vFogDir + cameraPosition;
 vec3 zjE = smoothstep( zjHallMin - 0.15, zjHallMin + 0.15, zjW ) * ( 1.0 - smoothstep( zjHallMax - 0.15, zjHallMax + 0.15, zjW ) );
 float zjIn = zjE.x * zjE.y * zjE.z * zjHallOn;
 irradiance *= 1.0 - zjIn;
 iblIrradiance *= 1.0 - zjIn;
 #if defined( RE_IndirectSpecular )
 radiance *= 1.0 - 0.9 * zjIn;
 #endif
 #if defined( ZJ_LAMP ) && defined( USE_AOMAP )
 irradiance += texture2D( zjLampMap, vAoMapUv ).rgb * zjLampK * max( zjIn, zjLampOut );
 #else
 irradiance += zjHallFill * zjIn;
 #endif
}
#endif
`;

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
    "varying float vFogDepth;\n varying vec3 vFogDir;\n uniform vec3 fogSunDir;\n uniform vec3 fogSunColor;" +
      HALL_PARS,
  );
  ShaderChunk.lights_fragment_end =
    HALL_LIGHT + ShaderChunk.lights_fragment_end;
  ShaderChunk.fog_fragment = ShaderChunk.fog_fragment.replace(
    "gl_FragColor.rgb = mix( gl_FragColor.rgb, fogColor, fogFactor );",
    "float fogSun = pow( max( dot( normalize( vFogDir ), fogSunDir ), 0.0 ), 5.0 );\n gl_FragColor.rgb = mix( gl_FragColor.rgb, mix( fogColor, fogSunColor, fogSun ), fogFactor );",
  );
  ShaderChunk.opaque_fragment = ShaderChunk.opaque_fragment.replace(
    "gl_FragColor = vec4( outgoingLight, diffuseColor.a );",
    `gl_FragColor = vec4( min( outgoingLight, vec3( ${HOT_MAX.toFixed(1)} ) ), diffuseColor.a );`,
  );
}

// every material that draws with fog binds the extra uniforms (the sun in the fog, the lamp-lit room)
export function fogUniforms(sh: WebGLProgramParametersWithUniforms): void {
  sh.uniforms.fogSunDir = FOG.sunDir;
  sh.uniforms.fogSunColor = FOG.sunColor;
  sh.uniforms.zjHallOn = HALL.on;
  sh.uniforms.zjHallMin = HALL.min;
  sh.uniforms.zjHallMax = HALL.max;
  sh.uniforms.zjHallFill = HALL.fill;
  sh.uniforms.zjLampOut = HALL.lampOut;
}
