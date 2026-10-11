// The ending's staging in 3D (F-13; ux-design 11.1, project folder ux/slice/ending-shots.md): while the story has an
// ending, this takes the camera and the people from the exploring layer and plays the shots the subtitles cut to
// (ui/ending/stage/bridge.ts): the camera of each shot, everyone's walk (script.ts), the crowd's cues (F-4), the rope,
// the torches; it tells the subtitles when a shot's action is done and draws the ending card's picture. Stand-in people
// until A-0's characters come in: only where they are and which way they face. Its own chunk, loaded with the ending.
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import {
  CylinderGeometry,
  Group,
  Mesh,
  MeshBasicMaterial,
  PerspectiveCamera,
  PointLight,
  SphereGeometry,
  Vector3,
} from "three";
import { useStory } from "../../stores/story";
import { useWorld } from "../../stores/world";
import { setStageBridge, type StageBridge } from "../../ui/ending/stage/bridge";
import { makeMannequin } from "../mannequin";
import { reducedMotion } from "../motion";
import { makePost } from "../post";
import { lightState } from "../Lighting";
import { rig } from "../rig";
import type { LoadedScene } from "../scene/loadScene";
import type { View as WorldView } from "../scene/openingViews";
import { stagePlan, type StagePlan } from "./plan";
import {
  blocking,
  type ActorId,
  type Camera,
  type Cue,
  type Frame,
  type Mark,
  type Move,
  shotScript,
  shotSeconds,
  stageFrame,
  toMark,
  toWorld,
} from "./script";

const TURN = 5; // rad/s
const CARD = { w: 1080, h: 640 }; // the ending card's picture (S-055)
const CAPTURE_TIMEOUT_MS = 3000;
// torches lit at shot 5 (火把点起来): around the platform and at the crowd's edges, as marks
const TORCHES: Mark[] = [
  [-1.6, 2.0, 2.3],
  [-1.6, -2.0, 2.3],
  [3.8, 3.6, 2.2],
  [3.8, -3.9, 2.2],
];
const TORCH_CANDELA = 12;
const POST_TOP: Mark = [-0.6, 0, 6.0]; // the rope runs from the post's top down to the one hoisted

type Actor = {
  obj: Group;
  at: Mark;
  path: Mark[];
  speed: number;
  face: Move["face"] | null;
  yaw: number;
};

const TONES: Record<ActorId, number> = {
  melos: 0.42,
  hostage: 0.38,
  king: 0.26,
  maiden: 0.5,
  oldMan: 0.34,
  player: 0.36,
  executioner: 0.22,
  guardN: 0.24,
  guardS: 0.24,
};

const angleTo = (from: number, to: number) =>
  Math.atan2(Math.sin(to - from), Math.cos(to - from));

export default function Staging({ scene }: { scene: LoadedScene }) {
  const { gl, scene: three } = useThree();
  const frame = useMemo(
    () => stageFrame(scene.manifest.spots),
    [scene.manifest.spots],
  );
  const group = useMemo(() => new Group(), []);
  const stage = useMemo(
    () => ({
      t: 0,
      paused: false,
      plan: null as StagePlan | null,
      playerMark: null as Mark | null,
      actors: new Map<ActorId, Actor>(),
      shot: 0,
      shotEnds: 0, // stage time the current shot's action is done
      reported: true,
      listeners: new Set<(n: number) => void>(),
      view: null as WorldView | null, // the camera of the shot (rig.stage); a follow shot moves it in place
      camera: null as Camera | null,
      captures: [] as {
        n: number;
        done: (b: ImageBitmap | null) => void;
      }[],
      torches: [] as { light: PointLight; flame: Mesh }[],
      rope: null as Mesh | null,
      ropeOn: false,
      crowd: null as Promise<CrowdVerbs | null> | null,
    }),
    [],
  );

  useEffect(() => {
    if (!frame) return;
    three.add(group);
    rig.staged = true;
    rig.path = [];
    rig.talkTo = rig.talking = rig.faceTo = null;

    // what this playthrough stages, again whenever more of the closing set pieces arrive
    const replan = () => {
      const e = useStory.getState().ending;
      const w = useWorld.getState().world;
      if (!e) return;
      const playerSpot = w?.player.spot ?? null;
      const ps = playerSpot ? scene.manifest.spots[playerSpot]?.pos : null;
      stage.playerMark = ps ? toMark(frame, ps) : null;
      stage.plan = stagePlan({
        staging: e.staging,
        pieces: e.lines.flatMap((l) => (l.pieceId ? [l.pieceId] : [])),
        playerSpot,
        oldManSpot: w?.characters["char.old-man"]?.spot ?? null,
      });
    };
    replan();
    const offStory = useStory.subscribe((s, prev) => {
      if (s.ending?.lines !== prev.ending?.lines) replan();
    });

    // everyone where they stand when the staging starts
    const plan = stage.plan!;
    for (const [id, at] of Object.entries(blocking(plan, stage.playerMark)) as [
      ActorId,
      Mark,
    ][]) {
      const obj = makeMannequin(TONES[id]);
      obj.name = `stage:${id}`;
      group.add(obj);
      const yaw = yawTowards(frame, at, [0, 0, at[2]]); // facing the post
      stage.actors.set(id, { obj, at, path: [], speed: 1, face: null, yaw });
    }

    // the torches are there from the start, dark, so lighting them doesn't recompile the scene's shaders
    const flameGeo = new SphereGeometry(0.09, 10, 8);
    const flameMat = new MeshBasicMaterial({ color: 0xffb060 });
    for (const m of TORCHES) {
      const [x, y, z] = toWorld(frame, m);
      const light = new PointLight(0xff9a4a, 0, 12, 2);
      light.position.set(x, y + 0.15, z);
      const flame = new Mesh(flameGeo, flameMat);
      flame.position.set(x, y, z);
      flame.visible = false;
      group.add(light, flame);
      stage.torches.push({ light, flame });
    }
    const rope = new Mesh(
      new CylinderGeometry(0.012, 0.012, 1, 5),
      new MeshBasicMaterial({ color: 0x3a2e22 }),
    );
    rope.visible = false;
    group.add(rope);
    stage.rope = rope;

    stage.crowd = import("../crowd/CrowdLayer").then((m) =>
      crowdVerbs(m.whenCrowd(), frame),
    );

    const bridge: StageBridge = {
      shot: (n) => startShot(n),
      onShotDone: (f) => {
        stage.listeners.add(f);
        return () => stage.listeners.delete(f);
      },
      captureFrame: () =>
        new Promise((done) => {
          const req = { n: stage.shot, done };
          stage.captures.push(req);
          setTimeout(() => {
            const i = stage.captures.indexOf(req);
            if (i >= 0) {
              stage.captures.splice(i, 1);
              done(null);
            }
          }, CAPTURE_TIMEOUT_MS);
        }),
      pause: (on) => {
        stage.paused = on;
      },
    };

    // a shot starts: whoever was still on the way gets there at once (a tap cuts ahead), then this shot's moves and
    // cues, its camera, and when its action will be done
    function startShot(n: number) {
      const p = stage.plan;
      if (!p || !frame) return;
      const s = shotScript(n, p, stage.playerMark);
      if (!s) return;
      for (const a of stage.actors.values()) {
        if (a.path.length) a.at = a.path.at(-1)!;
        a.path = [];
        faceNow(a);
      }
      const at = Object.fromEntries(
        [...stage.actors].map(([id, a]) => [id, a.at]),
      );
      for (const m of s.moves) {
        const a = stage.actors.get(m.actor);
        if (!a) continue;
        a.path = m.path.slice();
        a.speed = m.speed;
        a.face = m.face ?? null;
      }
      for (const c of s.cues) cue(c);
      stage.camera = s.camera;
      stage.view = viewOf(s.camera);
      rig.stage = stage.view;
      stage.shot = n;
      stage.shotEnds = stage.t + shotSeconds(s, at);
      stage.reported = false;
    }

    function viewOf(c: Camera): WorldView {
      // a follow shot holds still with reduced motion, or when its actor isn't on the ground in this ending
      const still =
        "follow" in c
          ? reducedMotion() || !stage.actors.has(c.follow)
            ? c.still
            : null
          : c;
      if (still)
        return {
          from: toWorld(frame!, still.from),
          to: toWorld(frame!, still.to),
          fov: still.fov,
        };
      return { from: [0, 0, 0], to: [0, 0, 1], fov: c.fov }; // placed every frame behind the actor (useFrame)
    }

    function cue(c: Cue) {
      if (c.k === "torches")
        for (const t of stage.torches) {
          t.light.intensity = c.on ? TORCH_CANDELA : 0;
          t.flame.visible = c.on;
        }
      else if (c.k === "rope") stage.ropeOn = c.on;
      else void stage.crowd?.then((v) => v?.[c.k](c as never));
    }

    function faceNow(a: Actor) {
      const to = targetOf(a.face ?? null);
      if (to && frame) a.yaw = yawTowards(frame, a.at, to);
    }

    // the first shot is on as soon as the staging starts (a too-late ending may never cut to one)
    startShot(1);
    setStageBridge(bridge);
    return () => {
      offStory();
      setStageBridge(null);
      rig.stage = null;
      rig.staged = false;
      three.remove(group);
      stage.actors.clear();
      stage.torches = [];
      for (const c of stage.captures) c.done(null);
      stage.captures = [];
    };

    function targetOf(f: Move["face"] | null): Mark | null {
      if (!f) return null;
      if (Array.isArray(f)) return f;
      return stage.actors.get(f)?.at ?? null;
    }
  }, [frame, group, scene, stage, three]);

  // a picture for the card: the same camera, drawn through its own post chain at 1080×640
  const capture = useMemo(() => {
    let post: ReturnType<typeof makePost> | null = null;
    const cam = new PerspectiveCamera(40, CARD.w / CARD.h, 0.1, 2000);
    return {
      draw(view: WorldView): Promise<ImageBitmap | null> {
        cam.position.set(...view.from);
        cam.lookAt(...view.to);
        cam.fov = view.fov;
        cam.updateProjectionMatrix();
        post ??= makePost(gl, three, cam);
        post.setSize(CARD.w, CARD.h, 1);
        post.composer.renderToScreen = false;
        post.out.uniforms.uNight!.value = lightState.night;
        post.composer.render();
        const rt = post.composer.readBuffer;
        const px = new Uint8Array(CARD.w * CARD.h * 4);
        gl.readRenderTargetPixels(rt, 0, 0, CARD.w, CARD.h, px);
        gl.setRenderTarget(null);
        const flipped = new Uint8ClampedArray(px.length);
        const row = CARD.w * 4;
        for (let y = 0; y < CARD.h; y++)
          flipped.set(
            px.subarray((CARD.h - 1 - y) * row, (CARD.h - y) * row),
            y * row,
          );
        return createImageBitmap(new ImageData(flipped, CARD.w, CARD.h));
      },
      dispose: () => post?.dispose(),
    };
  }, [gl, three]);
  useEffect(() => () => capture.dispose(), [capture]);

  const tmp = useMemo(() => ({ v: new Vector3() }), []);

  useFrame((_, dtRaw) => {
    if (!frame || stage.paused) return;
    const dt = Math.min(0.05, dtRaw);
    stage.t += dt;

    for (const a of stage.actors.values()) {
      const next = a.path[0];
      if (next) {
        const d = Math.hypot(
          next[0] - a.at[0],
          next[1] - a.at[1],
          next[2] - a.at[2],
        );
        const step = a.speed * dt;
        if (Math.hypot(next[0] - a.at[0], next[1] - a.at[1]) > 0.05)
          a.yaw = turn(a.yaw, yawTowards(frame, a.at, next), dt);
        if (d <= step) {
          a.at = next;
          a.path.shift();
        } else {
          const k = step / d;
          a.at = [
            a.at[0] + (next[0] - a.at[0]) * k,
            a.at[1] + (next[1] - a.at[1]) * k,
            a.at[2] + (next[2] - a.at[2]) * k,
          ];
        }
      } else if (a.face) {
        const to = Array.isArray(a.face)
          ? a.face
          : stage.actors.get(a.face)?.at;
        if (to && Math.hypot(to[0] - a.at[0], to[1] - a.at[1]) > 0.05)
          a.yaw = turn(a.yaw, yawTowards(frame, a.at, to), dt);
      }
      const [x, y, z] = toWorld(frame, a.at);
      a.obj.position.set(x, y, z);
      a.obj.rotation.y = a.yaw;
    }

    // the rope from the post's top to the hoisted one's raised hands
    const host = stage.actors.get("hostage");
    if (stage.rope) {
      stage.rope.visible = stage.ropeOn && !!host;
      if (host && stage.ropeOn) {
        const from = toWorld(frame, POST_TOP);
        const hands = toWorld(frame, [
          host.at[0],
          host.at[1],
          host.at[2] + 1.9,
        ]);
        tmp.v.set(hands[0] - from[0], hands[1] - from[1], hands[2] - from[2]);
        const len = tmp.v.length();
        stage.rope.position.set(
          (from[0] + hands[0]) / 2,
          (from[1] + hands[1]) / 2,
          (from[2] + hands[2]) / 2,
        );
        stage.rope.scale.set(1, Math.max(0.01, len), 1);
        stage.rope.quaternion.setFromUnitVectors(
          new Vector3(0, 1, 0),
          tmp.v.normalize(),
        );
      }
    }

    // a following shot keeps the camera behind its actor (the same view object: no cut, CameraRig)
    const c = stage.camera;
    if (c && "follow" in c && stage.view && !reducedMotion()) {
      const a = stage.actors.get(c.follow);
      if (a) {
        const at: Mark = [a.at[0] + c.back[0], a.at[1] + c.back[1], c.back[2]];
        const to: Mark = [a.at[0] + c.look[0], a.at[1] + c.look[1], c.look[2]];
        stage.view.from = toWorld(frame, at);
        stage.view.to = toWorld(frame, to);
      }
    }

    const done =
      stage.t >= stage.shotEnds &&
      [...stage.actors.values()].every((a) => !a.path.length);
    if (done && !stage.reported) {
      stage.reported = true;
      for (const f of stage.listeners) f(stage.shot);
    }
    if (done && stage.captures.length && stage.view) {
      const mine = stage.captures.filter((r) => r.n === stage.shot);
      stage.captures = stage.captures.filter((r) => r.n !== stage.shot);
      if (mine.length) {
        const view = stage.view;
        capture
          .draw(view)
          .catch(() => null)
          .then((b) => mine.forEach((r) => r.done(b)));
      }
    }
  });

  return null;
}

// the crowd's verbs in the stage's marks (F-4: Crowd.wave / cheer / part / settle take world x, z)
type CrowdVerbs = {
  part: (c: Extract<Cue, { k: "part" }>) => void;
  wave: (c: Extract<Cue, { k: "wave" }>) => void;
  cheer: (c: Extract<Cue, { k: "cheer" }>) => void;
  settle: () => void;
};

async function crowdVerbs(
  crowd: Promise<{
    part: (path: [number, number][], width?: number, speed?: number) => void;
    wave: (from: [number, number], speed?: number) => void;
    cheer: (seconds?: number) => void;
    settle: () => void;
  }>,
  f: Frame,
): Promise<CrowdVerbs> {
  const c = await crowd;
  const xz = (m: Mark): [number, number] => {
    const [x, , z] = toWorld(f, m);
    return [x, z];
  };
  return {
    part: (q) => c.part(q.path.map(xz), q.width, q.speed),
    wave: (q) => c.wave(xz(q.from)),
    cheer: (q) => c.cheer(q.seconds),
    settle: () => c.settle(),
  };
}

// world yaw (a model's front is +Z, scene/frame.ts yawOf) from one mark towards another
function yawTowards(f: Frame, from: Mark, to: Mark): number {
  const a = toWorld(f, from);
  const b = toWorld(f, to);
  return Math.atan2(b[0] - a[0], b[2] - a[2]);
}

function turn(yaw: number, want: number, dt: number): number {
  const d = angleTo(yaw, want);
  const s = TURN * dt;
  return Math.abs(d) <= s ? want : yaw + Math.sign(d) * s;
}
