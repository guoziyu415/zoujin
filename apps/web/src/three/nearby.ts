// Who `near` is for (api-contract 3.2, frontend review 7): only the closest talkable character, from 8 m; they keep it
// until 12 m away, unless someone else inside 8 m is clearly closer (2 m), so two people side by side don't flicker.
export const NEAR_M = 8;
export const FAR_M = 12;
const SWITCH_M = 2;

export function pickNear(
  current: string | null,
  dist: Record<string, number>,
): string | null {
  let best: string | null = null;
  let bestD = Infinity;
  for (const [id, d] of Object.entries(dist))
    if (d < bestD) [best, bestD] = [id, d];
  const held = current === null ? undefined : dist[current];
  if (held !== undefined && held <= FAR_M)
    return bestD <= NEAR_M && bestD < held - SWITCH_M ? best : current;
  return bestD <= NEAR_M ? best : null;
}
