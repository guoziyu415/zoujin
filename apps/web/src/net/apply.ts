// What the server says about the world, turned into the client's world data (frontend-design 6, 9.2): a snapshot
// replaces it, a commit patches it in one go. Pure functions, so the ordering rules are unit tested without a socket.
import type { Api } from "@zoujin/contracts";

export type WorldData = {
  playthroughId: string;
  lastSeq: number;
  status: Api.Snapshot["status"];
  actId: string;
  sceneId: string;
  clock: Api.SnapshotClock;
  deadline: Api.Deadline;
  forecast: Api.Forecast | null;
  player: Api.PlayerPosition;
  // the places of this scene; a character whose place is not one of them has left the scene (api-contract 3.4)
  places: Record<string, { enabled: boolean; reason?: string }>;
  characters: Record<string, Api.CharacterPresence>;
  interactables: Api.Interactable[];
  actions: Api.SituationalAction[];
  pending: Api.Pending;
  voice: Api.Voice;
  // the player-visible events this page has seen, oldest first (2.4); a correction replaces the one it supersedes
  events: Api.VisibleEvent[];
};

const byId = <T extends { id: string }>(xs: T[]): Record<string, T> =>
  Object.fromEntries(xs.map((x) => [x.id, x]));

const access = (p: Api.PlaceAccess): { enabled: boolean; reason?: string } =>
  p.reason === undefined
    ? { enabled: p.enabled }
    : { enabled: p.enabled, reason: p.reason };

export function fromSnapshot(
  s: Api.Snapshot,
  events: Api.VisibleEvent[] = [],
): WorldData {
  return {
    playthroughId: s.playthroughId,
    lastSeq: s.lastSeq,
    status: s.status,
    actId: s.actId,
    sceneId: s.sceneId,
    clock: s.clock,
    deadline: s.deadline,
    forecast: s.forecast,
    player: s.player,
    places: Object.fromEntries(s.places.map((p) => [p.id, access(p)])),
    characters: byId(s.characters),
    interactables: s.interactables,
    actions: s.actions,
    pending: s.pending,
    voice: s.voice,
    events,
  };
}

// add, or replace the ones whose id is already there; then drop the removed ids
function addRemove<T>(
  list: T[],
  key: (x: T) => string,
  p: { add?: T[]; remove?: string[] } | undefined,
): T[] {
  if (!p) return list;
  const added = new Map((p.add ?? []).map((x) => [key(x), x]));
  const gone = new Set(p.remove ?? []);
  const out = list
    .map((x) => added.get(key(x)) ?? x)
    .filter((x) => !gone.has(key(x)));
  const have = new Set(list.map(key));
  for (const [k, x] of added) if (!have.has(k) && !gone.has(k)) out.push(x);
  return out;
}

// copy the fields a patch gives, leaving out the ones it doesn't (exactOptionalPropertyTypes)
function merge<T extends object>(base: T, patch: Partial<T>): T {
  const out = { ...base };
  for (const [k, v] of Object.entries(patch))
    if (v !== undefined) (out as Record<string, unknown>)[k] = v;
  return out;
}

export function applyPatch(w: WorldData, p: Api.SnapshotPatch): WorldData {
  const places = { ...w.places };
  for (const pl of p.places ?? []) places[pl.id] = access(pl);
  const characters = { ...w.characters };
  for (const c of p.characters ?? []) {
    const { id, ...rest } = c;
    const before = characters[id];
    const next = before
      ? merge(before, rest)
      : // entering the scene: the patch carries the whole presence (3.4)
        merge<Api.CharacterPresence>(
          { id, place: "", activity: "idle", talkable: false },
          rest,
        );
    if (next.place in places) characters[id] = next;
    else delete characters[id];
  }
  return {
    ...w,
    clock: p.clock ? merge(w.clock, p.clock) : w.clock,
    deadline: p.deadline ?? w.deadline,
    forecast: p.forecast === undefined ? w.forecast : p.forecast,
    player: p.player ? merge(w.player, p.player) : w.player,
    places,
    characters,
    actions: addRemove(w.actions, (a) => a.actionId, p.actions),
    interactables: addRemove(w.interactables, (i) => i.id, p.interactables),
  };
}

// events seen again (a commit resent after a reconnect, a page of /events) are skipped by eventId; a correction
// takes the place of the event it supersedes (2.4)
export function addEvents(
  list: Api.VisibleEvent[],
  more: Api.VisibleEvent[],
): Api.VisibleEvent[] {
  const seen = new Set(list.map((e) => e.eventId));
  let out = list;
  for (const e of more) {
    if (seen.has(e.eventId)) continue;
    seen.add(e.eventId);
    out =
      e.supersedes && out.some((x) => x.eventId === e.supersedes)
        ? out.map((x) => (x.eventId === e.supersedes ? e : x))
        : [...out, e];
  }
  return out;
}

export type CommitResult =
  | { kind: "applied"; world: WorldData }
  // already applied (resent after a reconnect): nothing to do, nothing to show again
  | { kind: "seen" }
  // fromSeq doesn't follow our lastSeq: fetch the missing events, then the snapshot (3.4)
  | { kind: "gap" };

export function applyCommit(w: WorldData, c: Api.CommitMessage): CommitResult {
  if (c.seq <= w.lastSeq) return { kind: "seen" };
  if (c.fromSeq !== w.lastSeq + 1) return { kind: "gap" };
  const world = applyPatch(w, c.patch);
  return {
    kind: "applied",
    world: { ...world, lastSeq: c.seq, events: addEvents(w.events, c.events) },
  };
}
