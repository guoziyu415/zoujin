// How many of the crowd stand on the execution ground (F-4): while the world model has the crowd there (char.crowd, a
// group with no spot: api-contract 3.1; beat.s1 brings it), else none. ?crowd=N overrides it for testing. Apart from
// CrowdLayer so the world chunk can ask without loading the crowd's.
import type { Api } from "@zoujin/contracts";

export const CROWD = {
  id: "char.crowd",
  place: "place.execution-ground",
  count: 24,
};

export function crowdCount(
  characters: Record<string, Api.CharacterPresence> | undefined,
  override = 0,
): number {
  if (override > 0) return override;
  const c = characters?.[CROWD.id];
  return c?.place === CROWD.place && c.activity !== "absent" ? CROWD.count : 0;
}
