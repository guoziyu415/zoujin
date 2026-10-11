// The rain on the ground (F-11 card 5; ux/scenes/village.md 3): splash rings round the camera at the player's feet,
// and puddles that fill while it rains and dry slowly after (dark, glossy discs laid on the walkable ground by the
// pack's spots). VillageLife.tsx drives both from the weather.
import {
  AdditiveBlending,
  CircleGeometry,
  InstancedMesh,
  Matrix4,
  Mesh,
  MeshStandardMaterial,
  PlaneGeometry,
  Raycaster,
  ShaderMaterial,
  Vector3,
  type Object3D,
} from "three";

const SPLASHES = 600;
export const SPLASH_BOX = 10; // metres round the camera
const PUDDLES_PER_SPOT = 2;
const FILL_MIN = 25; // story minutes of downpour for the puddles to fill
const DRY_MIN = 180; // and to dry

export function splashMesh(): InstancedMesh {
  const mat = new ShaderMaterial({
    transparent: true,
    depthWrite: false,
    blending: AdditiveBlending,
    fog: false,
    uniforms: {
      uTime: { value: 0 },
      uAmount: { value: 0 },
      uBox: { value: SPLASH_BOX },
    },
    vertexShader: `
uniform float uTime; uniform float uAmount; uniform float uBox;
varying vec2 vUv; varying float vK; varying float vA;
void main() {
  vec4 seed = instanceMatrix[3];
  float k = fract(uTime * (1.4 + seed.w) + seed.y * 7.0);
  vK = k; vUv = uv;
  vA = step(seed.w, uAmount);
  vec3 p = vec3((seed.x - 0.5) * uBox, 0.0, (seed.z - 0.5) * uBox);
  p.xz += position.xy * (0.04 + 0.16 * k);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
}`,
    fragmentShader: `
varying vec2 vUv; varying float vK; varying float vA;
void main() {
  if (vA < 0.5) discard;
  float r = length(vUv - 0.5) * 2.0;
  float ring = smoothstep(0.7, 0.9, r) * (1.0 - smoothstep(0.9, 1.0, r));
  gl_FragColor = vec4(vec3(0.6, 0.65, 0.72), ring * (1.0 - vK) * 0.5);
}`,
  });
  const m = new InstancedMesh(new PlaneGeometry(1, 1), mat, SPLASHES);
  const mx = new Matrix4();
  for (let i = 0; i < SPLASHES; i++) {
    // as with the streaks: the translation column carries the seed (x, phase, z, share)
    mx.identity();
    mx.elements[12] = Math.random();
    mx.elements[13] = Math.random();
    mx.elements[14] = Math.random();
    mx.elements[15] = Math.random();
    m.setMatrixAt(i, mx);
  }
  m.frustumCulled = false;
  m.renderOrder = 9;
  return m;
}

// the puddles: near each spot, dropped onto the walkable ground; none where the ray finds no ground
export function puddles(
  spots: Record<string, { pos: number[] }>,
  walkable: readonly Object3D[],
): Mesh[] {
  const ray = new Raycaster();
  const down = new Vector3(0, -1, 0);
  const out: Mesh[] = [];
  let n = 0;
  for (const spot of Object.values(spots)) {
    for (let i = 0; i < PUDDLES_PER_SPOT; i++) {
      n++;
      const a = n * 2.39996; // golden angle: spread round the spot, the same each load
      const d = 1.2 + ((n * 0.618) % 1) * 2.2;
      const x = spot.pos[0]! + Math.cos(a) * d;
      const z = spot.pos[2]! + Math.sin(a) * d;
      ray.set(new Vector3(x, spot.pos[1]! + 3, z), down);
      const hit = ray.intersectObjects(walkable as Object3D[], false)[0];
      if (!hit) continue;
      const r = 0.35 + ((n * 0.37) % 1) * 0.6;
      const mesh = new Mesh(
        new CircleGeometry(1, 20),
        new MeshStandardMaterial({
          color: 0x14161a,
          roughness: 0.06,
          metalness: 0.0,
          transparent: true,
          opacity: 0,
          depthWrite: false,
          polygonOffset: true,
          polygonOffsetFactor: -2,
        }),
      );
      mesh.rotation.x = -Math.PI / 2;
      mesh.scale.set(r * (1.2 + (n % 3) * 0.2), r, 1);
      mesh.position.set(x, hit.point.y + 0.01, z);
      mesh.visible = false;
      out.push(mesh);
    }
  }
  return out;
}

// how full the puddles are: up while it rains, down slowly after (per story minute dt)
export function fill(prev: number, rain: number, dtMin: number): number {
  const up = rain > 0.3;
  const next = up
    ? prev + (rain * dtMin) / FILL_MIN
    : prev - Math.max(dtMin, 0) / DRY_MIN;
  return Math.min(1, Math.max(0, next));
}
