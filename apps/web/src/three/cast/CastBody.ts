// One character's body in the 3D layer (F-16), in its own chunk (the 3D chunk is at its budget; People.tsx and
// Player.tsx import it when a built character shows up): the person's Group holds the grey stand-in until the walking
// version and clips arrive, then the realistic one, playing idle / walk / run by its ground speed. In a conversation it
// swaps to the talking version (talk_std, or talk_high on the high asset tier, frontend-design 10.6.2) and moves the
// mouth with the voice and blinks. Files that fail to load leave the stand-in; nothing throws into the frame loop.
import {
  AnimationMixer,
  Group,
  Mesh,
  type AnimationAction,
  type AnimationClip,
  type Object3D,
  type WebGLRenderer,
} from "three";
import {
  GLTFLoader,
  type GLTF,
} from "three/examples/jsm/loaders/GLTFLoader.js";
import { KTX2Loader } from "three/examples/jsm/loaders/KTX2Loader.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { clone } from "three/examples/jsm/utils/SkeletonUtils.js";
import { fogUniforms } from "../shaderPatches";
import {
  blinkAt,
  castUrl,
  clipRate,
  gaitWeights,
  mouthWeights,
  seedOf,
  type CastFile,
} from "./cast";

let loader: GLTFLoader | null = null;
const cache = new Map<string, Promise<GLTF>>();

function gltfLoader(renderer: WebGLRenderer): GLTFLoader {
  if (!loader) {
    const ktx2 = new KTX2Loader().detectSupport(renderer);
    loader = new GLTFLoader()
      .setMeshoptDecoder(MeshoptDecoder)
      .setKTX2Loader(ktx2);
  }
  return loader;
}

function load(
  renderer: WebGLRenderer,
  name: string,
  file: CastFile,
): Promise<GLTF> {
  const url = castUrl(name, file);
  let p = cache.get(url);
  if (!p) {
    p = gltfLoader(renderer).loadAsync(url);
    cache.set(url, p);
    p.catch(() => cache.delete(url));
  }
  return p;
}

function prepare(root: Object3D): Mesh[] {
  const morphs: Mesh[] = [];
  root.traverse((o) => {
    if (!(o instanceof Mesh)) return;
    o.castShadow = true;
    o.receiveShadow = true;
    o.frustumCulled = false; // skinned: the bind-pose bounds don't follow the clips
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    for (const m of mats) m.onBeforeCompile = fogUniforms;
    if (o.morphTargetDictionary) {
      // Earlier exports retained the values used while transferring all shape keys.
      // Start from a neutral face before the voice/blink driver touches individual keys.
      o.morphTargetInfluences?.fill(0);
      morphs.push(o);
    }
  });
  return morphs;
}

type Version = {
  root: Object3D;
  mixer: AnimationMixer;
  actions: Record<string, AnimationAction>;
  morphs: Mesh[];
};

export class CastBody {
  private walk: Version | null = null;
  private talk: Version | null = null;
  private clips: AnimationClip[] | null = null;
  private talkWanted = false;
  private t = 0;
  private seed: number;

  /** group: the person's container, which holds the stand-in until the realistic body arrives. */
  constructor(
    private renderer: WebGLRenderer,
    private name: string,
    id: string,
    private group: Group,
    private stand: Object3D,
    private high = () => false,
  ) {
    this.seed = seedOf(id);
    void this.loadWalk(name);
  }

  private async loadWalk(name: string): Promise<void> {
    try {
      const [walk, anims] = await Promise.all([
        load(this.renderer, name, "walk"),
        load(this.renderer, name, "anims"),
      ]);
      this.clips = anims.animations;
      this.walk = this.version(walk);
      this.group.remove(this.stand);
      this.group.add(this.walk.root);
      if (this.talkWanted) void this.loadTalk();
    } catch {
      // no pack for this character (not built, offline): the stand-in stays
    }
  }

  private version(g: GLTF): Version {
    const root = clone(g.scene);
    const morphs = prepare(root);
    const mixer = new AnimationMixer(root);
    const actions: Record<string, AnimationAction> = {};
    for (const c of this.clips ?? []) {
      const a = mixer.clipAction(c);
      a.enabled = true;
      a.setEffectiveWeight(c.name === "idle" ? 1 : 0);
      a.play();
      actions[c.name] = a;
    }
    return { root, mixer, actions, morphs };
  }

  private async loadTalk(): Promise<void> {
    if (this.talk || !this.clips) return;
    try {
      const g = await load(
        this.renderer,
        this.name,
        this.high() ? "talk_high" : "talk_std",
      );
      this.talk = this.version(g);
      this.show();
    } catch {
      // keep the walking version
    }
  }

  private show(): void {
    const want = this.talkWanted && this.talk ? this.talk : this.walk;
    if (!want) return;
    for (const v of [this.walk, this.talk])
      if (v && v !== want) this.group.remove(v.root);
    if (want.root.parent !== this.group) this.group.add(want.root);
  }

  /** In a conversation: the talking version (loaded the first time it's needed). */
  setTalking(on: boolean): void {
    if (on === this.talkWanted) return;
    this.talkWanted = on;
    if (on && !this.talk) void this.loadTalk();
    this.show();
  }

  /** Every frame: the ground speed (m/s), and the voice's level while this person speaks (else 0). */
  update(dt: number, speed: number, voice: number): void {
    this.t += dt;
    const v = this.talkWanted && this.talk ? this.talk : this.walk;
    if (!v) return;
    const g = gaitWeights(speed);
    const stride = this.name === "old-man" ? 0.55 : 1;
    const a = v.actions;
    if (a.idle) a.idle.setEffectiveWeight(g.idle);
    if (a.talk && a.idle && voice > 0) {
      a.talk.setEffectiveWeight(g.idle * 0.7);
      a.idle.setEffectiveWeight(g.idle * 0.3);
    } else if (a.talk) a.talk.setEffectiveWeight(0);
    if (a.walk)
      a.walk
        .setEffectiveWeight(g.walk)
        .setEffectiveTimeScale(clipRate("walk", Math.max(speed, 0.5), stride));
    if (a.run)
      a.run
        .setEffectiveWeight(g.run)
        .setEffectiveTimeScale(clipRate("run", Math.max(speed, 2), stride));
    if (a.sprint) a.sprint.setEffectiveWeight(0);
    v.mixer.update(dt);
    if (!v.morphs.length) return;
    const mouth = voice > 0 ? mouthWeights(voice, this.t) : null;
    const blink = blinkAt(this.t, this.seed);
    for (const m of v.morphs) {
      const dict = m.morphTargetDictionary!;
      const inf = m.morphTargetInfluences!;
      const set = (k: string, x: number) => {
        const i = dict[k];
        if (i !== undefined) inf[i] = x;
      };
      for (const k of ["jawOpen", "viseme_aa", "viseme_O", "viseme_E"])
        set(k, mouth?.[k] ?? 0);
      set("eyeBlinkLeft", blink);
      set("eyeBlinkRight", blink);
    }
  }

  dispose(): void {
    for (const v of [this.walk, this.talk]) {
      v?.mixer.stopAllAction();
      if (v) this.group.remove(v.root);
    }
  }
}
