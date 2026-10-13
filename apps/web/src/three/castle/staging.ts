// What the castle stages around its people (F-14; ux/scenes/castle.md 3.2, 4): beat.04 Melos led in between two
// guards, beat.06 his friend brought in, untied, embraced, bound, beat.07 Melos picking up his bundle and leaving fast,
// the hostage's three days at the column, the low shot under the king and the player down on one knee by the hostage
// when he sits. Pure: CastleStage.tsx moves the stand-ins by it. Positions are the scene's (x, z): z = −y of the plan.
import type { Api } from "@zoujin/contracts";

export const DAY = 1440; // story minutes; t 0 is the day of the promise (約束の日) 00:00
export const MELOS = "char.melos";
export const FRIEND = "char.selinuntius";
export const KING = "char.king";

export const BUNDLE: [number, number] = [9.6, 1.4]; // left by the foot of the steps, south side (3.2 beat.04)
export const ESCORT_POSTS: [number, number][] = [
  [5, -1.6],
  [5, 1.6],
]; // the two guards beside Melos before the king (4 `before-king`)
export const DOOR_POSTS: [number, number][] = [
  [-7, -1.5],
  [-7, 1.5],
]; // two at the great door, outside, facing the courtyard
export const STEP_POSTS: [number, number][] = [
  [11, -3],
  [11, 3],
]; // two at the steps, either side
// the courtiers (4: set dressing, not spots): about six outside the north row of columns, facing south
export const COURTIERS: [number, number][] = [
  [-1.6, -5.4],
  [0.9, -5.7],
  [3.4, -5.4],
  [5.9, -5.7],
  [8.4, -5.4],
  [10.8, -5.6],
];
// the night of the promise in the hall: Melos brought in (beat.04's earliest) until the day turns
export const HALL_NIGHT: [number, number] = [1170, DAY];

// a beat's staging plays when the scene sees it happen, not when it was long over before the player came in
const FRESH = 20; // story minutes

export function happenedAt(
  events: readonly Api.VisibleEvent[],
  beat: string,
): number | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i]!;
    if (
      e.visibleEffects.some(
        (v) => v.kind === "beat" && v.beat === beat && v.change === "happened",
      )
    )
      return e.t;
  }
  return null;
}

export type Route = {
  from?: string;
  via?: [number, number][];
  speed?: number;
};

// how someone comes on or moves in the castle (4: a start spot and a target, the way walked on the navmesh)
export function routeOf(
  id: string,
  spot: string,
  entering: boolean,
  s: { t: number; led: number | null; summoned: number | null },
): Route | null {
  const fresh = (at: number | null) => at !== null && s.t - at <= FRESH;
  if (id === MELOS && entering && spot === "before-king")
    return fresh(s.led) ? { from: "melos-led-in", speed: 1.0 } : null;
  if (id === FRIEND && entering && spot === "selinuntius-meet")
    return fresh(s.summoned) ? { from: "selinuntius-in", speed: 1.2 } : null;
  if (id === MELOS && spot.startsWith("way."))
    return { via: [BUNDLE], speed: 1.6 }; // brisk, not running
  if (id === FRIEND && spot === "hostage-column") return { speed: 1.0 };
  return null;
}

// beat.06 once his friend stands before him (3.2): the guard unties Melos, he tells it all (one line of narration), the
// friend nods and holds him, then the friend is bound. Seconds since the friend arrived.
export type Meeting = "untie" | "tell" | "embrace" | "bind" | "held";
export function meetingAt(s: number): Meeting {
  return s < 3
    ? "untie"
    : s < 6
      ? "tell"
      : s < 9
        ? "embrace"
        : s < 12
          ? "bind"
          : "held";
}

// the hostage at the column (3.2 「人質の三日」), by the story clock
export type HostagePose =
  | "sit-lean" // the first night: sitting against the column, head back on it
  | "sit"
  | "stand" // day one, someone has come
  | "sit-rain" // day two from 12:30, watching the rain
  | "stand-west" // day three from 15:30, looking at the gate wall, the sun behind it
  | "head-down"; // after the doubt (beat.s2)

export function hostagePose(
  t: number,
  o: { visitor: boolean; doubted: boolean },
): HostagePose {
  if (o.doubted) return "head-down";
  if (t < DAY + 300) return "sit-lean";
  if (t < 2 * DAY) return o.visitor ? "stand" : "sit";
  if (t < 2 * DAY + 750) return "sit";
  if (t < 3 * DAY) return "sit-rain";
  if (t < 3 * DAY + 930) return "sit";
  return "stand-west";
}

export const sitting = (p: string) => p.startsWith("sit");
// his clothes (selinuntius.md 「柱廊の三日」): level 2 from day three
export const hostageWear = (t: number): 1 | 2 => (t >= 3 * DAY ? 2 : 1);

export const DOUBT_S = 1.5; // the flash of doubt on his face (selinuntius.md acceptance check 3) before the head goes down
export const CROUCH_M = 1.5;

// the conversation's shot (3.2): under the king, a little below the eyes, looking up, tighter from far off; level and
// low beside the hostage when he sits and the player kneels
export function talkShot(
  who: string,
  distance: number,
  hostageSits: boolean,
): { headY?: number; back?: number; camY?: number; fov?: number } | null {
  if (who === KING)
    return distance > 6
      ? { back: 1.2, camY: 1.4, fov: 25 }
      : { back: 1.2, camY: 1.4 };
  if (who === FRIEND && hostageSits && distance <= CROUCH_M)
    return { headY: 0.95, camY: 1.0 };
  return null;
}
