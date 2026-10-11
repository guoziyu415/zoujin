// The ending's shots on the execution ground (F-13; project folder ux/slice/ending-shots.md, the shot table): for each
// of the 11 shots, the camera, who goes where and the crowd's and the lights' cues. Written in the stage's own frame so
// nothing is tied to the scene's rotation: a mark is [a, b, h], a metres from the post towards the west gate (the
// light corridor, art-direction 4.1), b metres to the king's side of that line (north), h metres up. The 3D layer
// (Staging.tsx) turns marks into world positions with the scene's spots. Pure, so the timing is tested.
import type { Vec3 } from "../scene/frame";
import type { StagePlan } from "./plan";

export type Mark = [number, number, number];
type Flat = [number, number];

export type ActorId =
  | "melos"
  | "hostage"
  | "king"
  | "maiden"
  | "oldMan"
  | "player"
  | "executioner"
  | "guardN"
  | "guardS";

// the stage's frame from the scene's spots (world positions, +Y up): origin at `stake`, a towards `gate-inside`, b
// towards `king-west`'s side
export type Frame = { o: Flat; u: Flat; v: Flat };

type Spots = Record<string, { pos: Vec3 } | undefined>;

export function stageFrame(spots: Spots): Frame | null {
  const post = spots["stake"]?.pos;
  const gate = spots["gate-inside"]?.pos;
  const king = spots["king-west"]?.pos;
  if (!post || !gate) return null;
  const len = Math.hypot(gate[0] - post[0], gate[2] - post[2]);
  if (len < 1) return null;
  const u: Flat = [(gate[0] - post[0]) / len, (gate[2] - post[2]) / len];
  let v: Flat = [-u[1], u[0]];
  if (king && (king[0] - post[0]) * v[0] + (king[2] - post[2]) * v[1] < 0)
    v = [u[1], -u[0]];
  return { o: [post[0], post[2]], u, v };
}

export const toWorld = (f: Frame, [a, b, h]: Mark): Vec3 => [
  f.o[0] + a * f.u[0] + b * f.v[0],
  h,
  f.o[1] + a * f.u[1] + b * f.v[1],
];

export function toMark(f: Frame, p: Vec3): Mark {
  const dx = p[0] - f.o[0];
  const dz = p[2] - f.o[1];
  return [dx * f.u[0] + dz * f.u[1], dx * f.v[0] + dz * f.v[1], p[1]];
}

// —— where things are (plan coordinates of build_plaza.py / layout.json turned into marks: the post's spot `stake` is
// at plan x 10.4, the gate street runs to −x) ——
export const PLATFORM = 1.2; // the platform's top
export const GATE: Mark = [41.4, 0, 0]; // gate-inside, plan x −31
export const STEPS: Mark = [2.2, 0, 0]; // foot of the three steps, plan x 8.2
const AT_FEET: Mark = [0.15, 0.35, PLATFORM];
const POST_FEET: Mark = [-0.35, 0, PLATFORM]; // the one tied up, feet on the platform before the hoist
export const HOISTED = 2.6; // feet this high at the end of the hoist (釣り上げられてゆく)
const KING_WEST: Mark = [7.4, 2, 0];
const KING_STEPS: Mark = [-3.6, -5, 0.76]; // castle-steps, plan (14.3, −5): `present` king
const KING_BELOW: Mark = [2.9, 0.9, 0]; // under the platform's west edge, looking up (shot 9)
const CROWD_FRONT: Mark = [1.8, 1.6, 0]; // the maiden, front row by the platform's north-west corner
const MAIDEN_OFFER: Mark = [1.0, 0.75, 0];
const OLD_MAN_SIDE: Mark = [2.7, -1, 0]; // stake-front-side, beside a player at stake-front
const OLD_MAN_EDGE: Mark = [4.6, -3.3, 0]; // the crowd's south edge: in shots 1 and 3 from behind the crowd

export const RUN = 6.5; // m/s, ran to exhaustion, not a sprint (ending-shots.md, frontend 10-10)
const PUSH = 3.0; // through a crowd that doesn't make way (掻きわけ)
const CLIMB = 1.6;
const KING_WALK = 1.1;
const MAIDEN_WALK = 1.0;
const SHOT2_END = 20; // a where shot 2's run hands over to shot 3 (the crowd starts about here)

// where everyone stands when the staging starts (before shot 1)
export function blocking(
  p: StagePlan,
  playerMark: Mark | null,
): Partial<Record<ActorId, Mark>> {
  const b: Partial<Record<ActorId, Mark>> = {
    executioner: [-0.9, 1.0, PLATFORM],
    guardN: [-1.2, 2.3, 0],
    guardS: [-1.2, -2.3, 0],
  };
  if (p.hostage) b.hostage = p.madeIt ? [-0.3, -0.7, PLATFORM] : POST_FEET;
  if (p.melos) b.melos = GATE;
  if (p.king === "approaching") b.king = KING_WEST;
  else if (p.king === "present") b.king = KING_STEPS;
  if (p.maiden) b.maiden = CROWD_FRONT;
  if (p.oldMan)
    b.oldMan = p.oldMan === "by-player" ? OLD_MAN_SIDE : OLD_MAN_EDGE;
  if (p.player && playerMark) b.player = playerMark;
  return b;
}

export type Move = {
  actor: ActorId;
  path: Mark[]; // from where they are, through these
  speed: number;
  face?: ActorId | Mark; // once there (else: the way they walked)
};

export type Cue =
  | { k: "part"; path: Mark[]; width: number; speed?: number }
  | { k: "wave"; from: Mark }
  | { k: "cheer"; seconds: number }
  | { k: "settle" }
  | { k: "torches"; on: boolean }
  | { k: "rope"; on: boolean };

export type View = { from: Mark; to: Mark; fov: number };
export type Camera =
  | View
  | {
      follow: ActorId;
      back: Mark; // camera = the actor + this (a, b offsets; h absolute)
      look: Mark; // aimed at the actor + this
      fov: number;
      still: View; // with reduced motion: a fixed camera instead
    };

export type ShotScript = {
  camera: Camera;
  moves: Move[];
  cues: Cue[];
  hold: number; // seconds the shot's action takes at least (a pose held, the hoist)
};

const shift = ([a, b, h]: Mark, da: number, db = 0, hh = h): Mark => [
  a + da,
  b + db,
  hh,
];

export function shotScript(
  n: number,
  p: StagePlan,
  playerMark: Mark | null,
): ShotScript | null {
  switch (n) {
    case 1:
      // far: from the gate's side down the light corridor at the post, the crowd's backs to us; the hoist
      return {
        camera: { from: [26, -1.8, 2.4], to: [-0.4, 0, 4.2], fov: 38 },
        moves: p.onPost
          ? [
              {
                actor: "hostage",
                path: [[POST_FEET[0], 0, HOISTED]],
                speed: (HOISTED - PLATFORM) / 5,
                face: [10, 0, 0],
              },
            ]
          : [],
        cues: [{ k: "rope", on: !!p.onPost }],
        hold: 3,
      };
    case 2: {
      // far: from the post's side at the gate, Melos in the gateway ahead of his shadow; from behind the player
      // when they waited at ground-west, and then he runs past them
      const camera: View =
        p.behindPlayer && playerMark
          ? {
              from: shift(playerMark, -2.6, 0.4, 1.75),
              to: [GATE[0], 0, 1.8],
              fov: 34,
            }
          : { from: [2.5, 1.4, 3.2], to: [GATE[0], 0, 1.8], fov: 34 };
      if (!p.melos) return { camera, moves: [], cues: [], hold: 3 };
      const moves: Move[] = p.madeIt
        ? [
            {
              actor: "melos",
              path: [STEPS, [1.0, 0.3, PLATFORM], AT_FEET],
              speed: RUN,
              face: "hostage",
            },
          ]
        : [{ actor: "melos", path: [[SHOT2_END, 0, 0]], speed: RUN }];
      return { camera, moves, cues: [], hold: 1.5 };
    }
    case 3: {
      // following behind Melos into the crowd: it makes way (the woman's shout) or he pushes through
      const path: Mark[] = [STEPS];
      return {
        camera: {
          follow: "melos",
          back: [4.5, 0.8, 2.3],
          look: [-6, 0, 1.4],
          fov: 44,
          still: { from: [16, -2.2, 2.6], to: [3, 0, 1.6], fov: 44 },
        },
        moves: [{ actor: "melos", path, speed: p.crowdMakesWay ? RUN : PUSH }],
        cues: [
          p.crowdMakesWay
            ? { k: "part", path: [[SHOT2_END, 0, 0], STEPS], width: 2.2 }
            : {
                k: "part",
                path: [[SHOT2_END, 0, 0], STEPS],
                width: 1.0,
                speed: PUSH,
              },
        ],
        hold: 1,
      };
    }
    case 4:
      // the platform and the lower half of the post: up the steps, he clasps his friend's feet
      return {
        camera: { from: [4.6, -2.6, 1.9], to: [0, 0, 2.0], fov: 42 },
        moves: [
          {
            actor: "melos",
            path: [[1.0, 0.3, PLATFORM], AT_FEET],
            speed: CLIMB,
            face: "hostage",
          },
        ],
        cues: [],
        hold: 3,
      };
    case 5:
      // middle distance: the crowd stirs (どよめき), the rope is loosed, torches are lit
      return {
        camera: { from: [8.5, 4.8, 3.0], to: [1.2, 0, 2.2], fov: 46 },
        moves: p.onPost
          ? [
              {
                actor: "hostage",
                path: [POST_FEET],
                speed: (HOISTED - PLATFORM) / 2.5,
              },
            ]
          : [],
        cues: [
          { k: "wave", from: [0, 0, 0] },
          { k: "rope", on: false },
          { k: "torches", on: true },
        ],
        hold: 3,
      };
    case 6:
      // the two on the platform, side on, low and a little up, against the bright west sky: silhouettes
      return {
        camera: { from: [-2.4, -4.2, 1.05], to: [0.2, 0.3, 2.3], fov: 36 },
        moves: [
          {
            actor: "hostage",
            path: [[0.15, -0.25, PLATFORM]],
            speed: 0.8,
            face: "melos",
          },
          {
            actor: "melos",
            path: [[0.2, 0.35, PLATFORM]],
            speed: 0.8,
            face: "hostage",
          },
        ],
        cues: [],
        hold: 4,
      };
    case 7:
      // the king behind the crowd on the west side, higher than everyone, against the west sky
      return {
        camera: {
          from: [2.0, 5.0, 2.1],
          to: shift(p.king === "present" ? KING_STEPS : KING_WEST, 0, 0, 1.75),
          fov: 36,
        },
        moves: [],
        cues: [{ k: "settle" }],
        hold: 2,
      };
    case 8:
      // following the king as he walks quietly up to the two, the crowd making way for him
      return {
        camera: {
          follow: "king",
          back: [3.0, 1.2, 2.2],
          look: [-4, 0, 1.5],
          fov: 42,
          still: { from: [10, 4, 2.6], to: [3, 0.9, 1.5], fov: 42 },
        },
        moves:
          p.king === "approaching"
            ? [
                {
                  actor: "king",
                  path: [KING_BELOW],
                  speed: KING_WALK,
                  face: [0, 0.3, 2.4],
                },
              ]
            : [],
        cues:
          p.king === "approaching"
            ? [
                {
                  k: "part",
                  path: [KING_WEST, KING_BELOW],
                  width: 1.6,
                  speed: KING_WALK,
                },
              ]
            : [],
        hold: 1,
      };
    case 9:
      // the three: from behind the two on the platform down at the king, his back to the west sky
      return {
        camera: {
          from: [-1.2, 0.4, 2.9],
          to: shift(KING_BELOW, 0, 0, 1.6),
          fov: 40,
        },
        moves: [],
        cues: [],
        hold: 2,
      };
    case 10:
      // far, high: the crowd cheers by torchlight (万歳)
      return {
        camera: { from: [-1.5, -6.5, 5.0], to: [8, 1, 1.2], fov: 50 },
        moves: [],
        cues: [{ k: "cheer", seconds: 8 }],
        hold: 3,
      };
    case 11:
      // from behind Melos: the maiden steps out of the front row and holds up the scarlet cloak
      return {
        camera: { from: [-1.8, -0.6, 2.6], to: [2.0, 1.4, 1.4], fov: 44 },
        moves: p.maiden
          ? [
              {
                actor: "maiden",
                path: [MAIDEN_OFFER],
                speed: MAIDEN_WALK,
                face: "melos",
              },
            ]
          : [],
        cues: [{ k: "settle" }],
        hold: 3,
      };
    default:
      return null;
  }
}

const dist = (a: Mark, b: Mark) =>
  Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);

export function pathLength(from: Mark, path: Mark[]): number {
  let len = 0;
  let at = from;
  for (const m of path) {
    len += dist(at, m);
    at = m;
  }
  return len;
}

// how long a shot's action takes from where everyone stands: the longest walk, or the hold
export function shotSeconds(
  s: ShotScript,
  at: Partial<Record<ActorId, Mark>>,
): number {
  let t = s.hold;
  for (const m of s.moves) {
    const from = at[m.actor];
    if (from) t = Math.max(t, pathLength(from, m.path) / m.speed);
  }
  return t;
}

// where everyone ends up after a shot (for the next shot's timing and a cut that skips ahead)
export function after(
  s: ShotScript,
  at: Partial<Record<ActorId, Mark>>,
): Partial<Record<ActorId, Mark>> {
  const next = { ...at };
  for (const m of s.moves)
    if (next[m.actor] && m.path.length) next[m.actor] = m.path.at(-1)!;
  return next;
}
