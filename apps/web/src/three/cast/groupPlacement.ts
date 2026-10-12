// Group presences intentionally have no server spot. Place their visual representative on a real nav polygon,
// keeping clear of the player and named characters, without changing the narrative group state.
import type { NavPoint } from "../nav/navmesh";
import { seedOf } from "./cast";

export type GroupCandidate = {
  key: string;
  place: string;
  at: NavPoint;
  yaw: number;
};
export const GROUP_CLEARANCE = 1.4;

export function groupPlacement(
  id: string,
  place: string,
  candidates: readonly GroupCandidate[],
  occupied: readonly Pick<NavPoint, "x" | "z">[],
  current?: GroupCandidate,
  currentOccupied = occupied,
): GroupCandidate | null {
  const clear = (candidate: GroupCandidate, points = occupied) =>
    candidate.place === place &&
    points.every(
      (point) =>
        Math.hypot(point.x - candidate.at.x, point.z - candidate.at.z) >=
        GROUP_CLEARANCE,
    );
  // Approaching the representative must not move it when the story next commits.
  // The caller excludes the player from currentOccupied, but retains NPC/crowd conflicts.
  if (current && clear(current, currentOccupied)) return current;
  return (
    [...candidates]
      .filter((candidate) => clear(candidate))
      .sort(
        (a, b) =>
          seedOf(`${id}:${a.key}`) - seedOf(`${id}:${b.key}`) ||
          a.key.localeCompare(b.key),
      )[0] ?? null
  );
}
