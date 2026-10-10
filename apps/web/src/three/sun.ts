// The sun is the clock (art-direction 3.1). Same formula as the bake and the sky (assets/pipeline/plaza/sunpos.py):
// latitude 37°, declination +19°, solar noon 12:00, so it sets at about 19:00; plan −x is the gate street (azimuth 294°).
import { planToWorld, type Vec3 } from "./scene/frame";

export type SunParams = {
  latitudeDeg: number;
  declinationDeg: number;
  solarNoonMinute: number;
  gateStreetAzimuthDeg: number;
  sceneRotationDeg: number;
};

export type SunPosition = { dir: Vec3; elevDeg: number; azimuthDeg: number };

const D = Math.PI / 180;

export function sunAt(minute: number, p: SunParams): SunPosition {
  const phi = p.latitudeDeg * D;
  const dec = p.declinationDeg * D;
  const H = 15 * ((minute - p.solarNoonMinute) / 60) * D;
  const se =
    Math.sin(phi) * Math.sin(dec) + Math.cos(phi) * Math.cos(dec) * Math.cos(H);
  const e = Math.asin(se);
  const ca =
    (Math.sin(dec) - se * Math.sin(phi)) / (Math.cos(e) * Math.cos(phi));
  let A = Math.acos(Math.min(1, Math.max(-1, ca)));
  if (H > 0) A = 2 * Math.PI - A;
  const d = A - p.gateStreetAzimuthDeg * D;
  const [x, y, z] = planToWorld(
    -Math.cos(e) * Math.cos(d),
    Math.cos(e) * Math.sin(d),
    Math.sin(e),
    p.sceneRotationDeg,
  );
  const l = Math.hypot(x, y, z);
  return { dir: [x / l, y / l, z / l], elevDeg: e / D, azimuthDeg: A / D };
}

// blackbody colour (Tanner Helland's fit) in sRGB 0..1, brightest channel = 1
export function kelvinRGB(K: number): Vec3 {
  const t = K / 100;
  const r = t <= 66 ? 255 : 329.698727446 * Math.pow(t - 60, -0.1332047592);
  const g =
    t <= 66
      ? 99.4708025861 * Math.log(t) - 161.1195681661
      : 288.1221695283 * Math.pow(t - 60, -0.0755148492);
  const b =
    t >= 66
      ? 255
      : t <= 19
        ? 0
        : 138.5177312231 * Math.log(t - 10) - 305.0447927307;
  const c = (v: number) => Math.min(255, Math.max(0, v)) / 255;
  return [c(r), c(g), c(b)];
}

// direct sunlight: about 2000K on the horizon, 4000K at 35°, near white (5500K) at midday
export const sunKelvin = (e: number): number =>
  e >= 35
    ? Math.min(5500, 4000 + (e - 35) * 60)
    : 2000 + 2000 * Math.pow(Math.max(0, e) / 35, 0.6);

const smoothstep = (x: number, a: number, b: number) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const clamp01 = (v: number) => Math.min(1, Math.max(0, v));

// Everything the lights, the sky and the grade read from the sun's height. Numbers from S7 (spikes/frontend/s7-realism,
// the "只烘遮蔽" mode that UX looked at); kept in one pure function so the shadow-line test and the page agree.
export type SunLook = {
  intensity: number; // directional light, before the exposure
  kelvin: number;
  discGain: number; // the drawn sun disc fades as it touches the horizon
  skyGain: number; // Sky.js forward scattering held down near a low sun
  dusk: number; // afterglow on the sunset side, 3° above to 2° below the horizon
  nightSky: number;
  belt: number; // the pink band opposite the sun around sunset
  amber: number; // sky around a low sun turns amber instead of white haze
  night: number; // "day for night" (art-direction 3.2)
  hemi: number; // hemisphere fill once the sun is down
  exposure: number;
  fogSun: number; // how much the fog warms towards the sun
};

export const SUN_E = 6.0;

export function sunLook(elevDeg: number): SunLook {
  const e = elevDeg;
  const k = clamp01((e + 0.5) / 3); // direct light goes as the disc touches the horizon
  const night = clamp01((-e - 1) / 8);
  const dusk = clamp01((3 - e) / 5) * (1 - night);
  // a camera stops down in the midday sun and opens up as the light goes; Neutral tone mapping has no lifted toe
  const exposure = lerp(1.1, 0.66, smoothstep(e, 8, 50)) * (1 + 0.75 * night);
  return {
    intensity: SUN_E * k * lerp(0.6, 1.0, smoothstep(e, 2, 35)),
    kelvin: sunKelvin(e),
    discGain: k,
    skyGain: lerp(0.62, 0.4, smoothstep(e, 10, 45)),
    dusk: clamp01((2 - e) / 3) * (1 - night),
    nightSky: clamp01((-e - 2) / 6),
    belt: (1 - smoothstep(e, 2, 9)) * smoothstep(e, -7, -2),
    amber: 1 - smoothstep(e, 3, 28),
    night,
    hemi: Math.max(night * 0.9, dusk * 0.8),
    exposure,
    fogSun: 1.4 * clamp01((e + 4) / 8),
  };
}
