// The start probe (frontend-design 10.6.3 point 1): while the first scene downloads, draw a fixed test scene off screen
// with S7 b7's kind of cost (PBR with colour, normal, roughness and baked occlusion maps, the physical sky, fog, the
// realtime sun's 2048 shadow, then bloom, MSAA and the grade) at L1's pixel ratio, and find one frame's GPU time by
// S7's stress method: draw the same frame N times per frame until the interval reaches 45 ms; then g ~ T / N. The
// interval snaps to whole refreshes, so the truth is between (T - 16.7) / N and T / N; take the middle. About half a
// second; nothing is shown.
import {
  BoxGeometry,
  Color,
  DataTexture,
  DirectionalLight,
  FogExp2,
  HemisphereLight,
  Mesh,
  MeshStandardMaterial,
  NoColorSpace,
  PerspectiveCamera,
  PlaneGeometry,
  PMREMGenerator,
  RepeatWrapping,
  RGBAFormat,
  Scene,
  SRGBColorSpace,
  type BufferGeometry,
  type WebGLRenderer,
} from "three";
import { Sky } from "three/examples/jsm/objects/Sky.js";
import { makePost, type Post } from "../post";

export type ProbeResult = {
  gpuMs: number; // one frame of the test scene at L1's pixel ratio
  lo: number;
  hi: number;
  reps: number; // N at the last step
  intervalMs: number; // T at the last step
  // gpu: the GPU set the pace; cpu: submitting N draws took most of the interval, so gpuMs is too high; under: still
  // at 60 fps with the most draws, gpuMs is an upper bound
  bound: "gpu" | "cpu" | "under";
  ms: number; // how long the probe took
};

const VSYNC = 1000 / 60;
const TARGET_MS = 45;
const MAX_REPS = 64;
const FRAMES_PER_STEP = 4; // measured intervals per step, after one to settle
const MAX_PROBE_MS = 1500; // measuring, after the first frames settled
const GIVE_UP_MS = 10_000; // never settled (a hidden tab, a stalled GPU): no result, start at L1

// a seeded value-noise texture, so every phone draws the same test scene
function noiseTexture(
  size: number,
  seed: number,
  fill: (n: number, x: number, y: number) => [number, number, number],
  srgb: boolean,
): DataTexture {
  let s = seed >>> 0;
  const rnd = () =>
    ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32) as number;
  const g = 32;
  const grid = Array.from({ length: g * g }, rnd);
  const data = new Uint8Array(size * size * 4);
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      const fx = (x / size) * g;
      const fy = (y / size) * g;
      const x0 = Math.floor(fx) % g;
      const y0 = Math.floor(fy) % g;
      const tx = fx - Math.floor(fx);
      const ty = fy - Math.floor(fy);
      const v = (i: number, j: number) =>
        grid[((y0 + j) % g) * g + ((x0 + i) % g)]!;
      const n =
        (v(0, 0) * (1 - tx) + v(1, 0) * tx) * (1 - ty) +
        (v(0, 1) * (1 - tx) + v(1, 1) * tx) * ty;
      const [r, gg, b] = fill(n * 0.8 + rnd() * 0.2, x, y);
      const o = (y * size + x) * 4;
      data[o] = r;
      data[o + 1] = gg;
      data[o + 2] = b;
      data[o + 3] = 255;
    }
  const t = new DataTexture(data, size, size, RGBAFormat);
  t.colorSpace = srgb ? SRGBColorSpace : NoColorSpace;
  t.wrapS = t.wrapT = RepeatWrapping;
  t.generateMipmaps = true;
  t.anisotropy = 4;
  t.needsUpdate = true;
  return t;
}

type TestScene = {
  scene: Scene;
  camera: PerspectiveCamera;
  dispose: () => void;
};

// a street of stone blocks seen from eye level, the sky above, the sun low and to the side (most pixels are lit,
// textured, shadowed stone, like the plaza's first screen)
function testScene(gl: WebGLRenderer, aspect: number): TestScene {
  const scene = new Scene();
  const base = noiseTexture(
    1024,
    1,
    (n) => [150 + 70 * n, 125 + 60 * n, 95 + 45 * n],
    true,
  );
  const nrm = noiseTexture(
    512,
    2,
    (n, x, y) => [
      128 + 60 * Math.sin(x * 0.2 + n * 6),
      128 + 60 * Math.cos(y * 0.2 + n * 6),
      230,
    ],
    false,
  );
  const mr = noiseTexture(512, 3, (n) => [255, 180 + 70 * n, 0], false);
  const ao = noiseTexture(
    1024,
    4,
    (n) => [150 + 105 * n, 150 + 105 * n, 150 + 105 * n],
    false,
  );
  ao.channel = 1;
  const mat = () => {
    const m = new MeshStandardMaterial({
      map: base,
      normalMap: nrm,
      roughnessMap: mr,
      metalnessMap: mr,
      aoMap: ao,
      roughness: 1,
      metalness: 0,
    });
    m.normalScale.set(1, -1);
    return m;
  };
  const withUv1 = (g: BufferGeometry) => {
    g.setAttribute("uv1", g.getAttribute("uv")!);
    return g;
  };
  const geoms: BufferGeometry[] = [];
  const mats: MeshStandardMaterial[] = [];
  const ground = new Mesh(withUv1(new PlaneGeometry(120, 120)), mat());
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  geoms.push(ground.geometry);
  mats.push(ground.material);
  const box = withUv1(new BoxGeometry(6, 9, 6));
  geoms.push(box);
  scene.add(ground);
  for (let i = 0; i < 12; i++) {
    const m = new Mesh(box, mat());
    mats.push(m.material);
    m.position.set(i % 2 ? 7 : -7, 4.5, -i * 4 - 2);
    m.castShadow = m.receiveShadow = true;
    scene.add(m);
  }
  const sun = new DirectionalLight(new Color(1, 0.8, 0.6), 3);
  sun.position.set(-40, 18, -10);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, {
    left: -36,
    right: 36,
    top: 36,
    bottom: -36,
    near: 1,
    far: 150,
  });
  sun.shadow.camera.updateProjectionMatrix();
  scene.add(sun, new HemisphereLight(0xbcd0ff, 0x8a7560, 0.6));
  const sky = new Sky();
  sky.scale.setScalar(1000);
  sky.material.uniforms.sunPosition!.value.set(-0.9, 0.25, -0.2);
  scene.add(sky);
  const pmrem = new PMREMGenerator(gl);
  const envScene = new Scene();
  const envSky = new Sky();
  envSky.scale.setScalar(50);
  envSky.material.uniforms.sunPosition!.value.set(-0.9, 0.25, -0.2);
  envScene.add(envSky);
  const env = pmrem.fromScene(envScene, 0, 0.1, 100);
  scene.environment = env.texture;
  scene.fog = new FogExp2(0xc8b8a0, 0.004);
  const camera = new PerspectiveCamera(60, aspect, 0.1, 1500);
  camera.position.set(0, 1.7, 12);
  camera.lookAt(0, 3.5, -30);
  return {
    scene,
    camera,
    dispose: () => {
      for (const t of [base, nrm, mr, ao]) t.dispose();
      for (const g of geoms) g.dispose();
      for (const m of mats) m.dispose();
      sky.geometry.dispose();
      sky.material.dispose();
      envSky.geometry.dispose();
      envSky.material.dispose();
      env.dispose();
      pmrem.dispose();
      sun.shadow.map?.dispose();
    },
  };
}

// mean interval without the slowest and fastest (S7's trimmed mean, with few samples)
const trimmed = (a: number[]) => {
  const s = [...a].sort((x, y) => x - y);
  const m = s.length > 3 ? s.slice(1, -1) : s;
  return m.reduce((x, y) => x + y, 0) / Math.max(1, m.length);
};

// one step per animation frame; call frame() from the render loop until it returns a result
export class Probe {
  private t: TestScene;
  private post: Post;
  private reps = 1;
  private intervals: number[] = [];
  private cpu: number[] = [];
  private settle = 3; // the first frames compile shaders and upload textures
  private last = -1;
  private started = -1; // the first frame
  private t0 = -1; // the first measured interval
  result: ProbeResult | null = null;
  done = false;

  constructor(
    private readonly gl: WebGLRenderer,
    width: number,
    height: number,
    pixelRatio: number,
  ) {
    this.t = testScene(gl, width / height);
    this.post = makePost(gl, this.t.scene, this.t.camera);
    this.post.composer.renderToScreen = false;
    this.post.setSize(width, height, pixelRatio);
  }

  frame(now: number): void {
    if (this.done) return;
    if (this.started < 0) this.started = now;
    const gl = this.gl;
    const target = gl.getRenderTarget();
    const autoReset = gl.info.autoReset;
    const c0 = performance.now();
    for (let k = 0; k < this.reps; k++) this.post.composer.render();
    const cpuPer = (performance.now() - c0) / this.reps;
    gl.setRenderTarget(target);
    gl.info.autoReset = autoReset;
    if (this.last >= 0) {
      if (this.settle > 0) this.settle--;
      else {
        if (this.t0 < 0) this.t0 = this.last;
        this.intervals.push(now - this.last);
        this.cpu.push(cpuPer);
      }
    }
    this.last = now;
    const n = this.intervals.length;
    // a slow device is already far past the target at one draw: two intervals are enough to say so
    if (
      n >= FRAMES_PER_STEP ||
      (n >= 2 && trimmed(this.intervals) >= 2 * TARGET_MS)
    )
      this.step(now);
    else if (this.t0 >= 0 && now - this.t0 > MAX_PROBE_MS)
      this.finish(
        now,
        n ? { T: trimmed(this.intervals), cpu: trimmed(this.cpu) } : null,
      );
    else if (now - this.started > GIVE_UP_MS) this.finish(now, null);
  }

  private step(now: number): void {
    const T = trimmed(this.intervals);
    const cpu = trimmed(this.cpu);
    this.intervals = [];
    this.cpu = [];
    if (
      T >= TARGET_MS ||
      this.reps >= MAX_REPS ||
      now - this.t0 > MAX_PROBE_MS
    ) {
      this.finish(now, { T, cpu });
      return;
    }
    // jump close to the 45 ms target in one go, at least doubling
    this.reps = Math.min(
      MAX_REPS,
      Math.max(
        this.reps * 2,
        Math.ceil((this.reps * (TARGET_MS + 10)) / Math.max(T, 1)),
      ),
    );
    this.settle = 1;
  }

  // unmounted before it finished
  abort(): void {
    if (this.done) return;
    this.done = true;
    this.post.dispose();
    this.t.dispose();
  }

  private finish(now: number, m: { T: number; cpu: number } | null): void {
    this.done = true;
    if (m) {
      const n = this.reps;
      const hi = m.T / n;
      const lo = Math.max(0, m.T - VSYNC) / n;
      const under = m.T < VSYNC * 1.25;
      this.result = {
        gpuMs: under ? hi : (hi + lo) / 2,
        lo,
        hi,
        reps: n,
        intervalMs: m.T,
        bound: under ? "under" : m.cpu * n >= 0.8 * m.T ? "cpu" : "gpu",
        ms: Math.round(now - this.started),
      };
    }
    this.post.dispose();
    this.t.dispose();
  }
}
