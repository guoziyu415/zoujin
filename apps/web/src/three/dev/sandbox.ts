// The 3D sandbox (?world, ?dev, the measuring page): no server, so a local world in the real stores with what the 3D
// reads; the dev panel, the measuring page and the e2e test hook change it the way the server's commits would.
// ?scene=road-river&act=act.4&t=705 opens another scene than the plaza, in that act, at that time (F-10's test page).
import type { Api } from "@zoujin/contracts";
import type { WorldData } from "../../net/apply";
import { placePlayer } from "../../stores/player";
import { setWorld, useWorld } from "../../stores/world";

export type SandboxCharacter = Omit<
  Api.CharacterPresence,
  "id" | "talkable"
> & {
  talkable?: boolean;
};

const PLACES = [
  "place.syracuse-square",
  "place.stonemason-workshop",
  "place.execution-ground",
];

// a scene whose player lands somewhere else than the plaza's corner, and the clock it opens on unless ?t says
const LANDING: Record<string, { place: string; spot: string; t: number }> = {
  // the night of the promise, 20:30 (beat.05, F-14)
  "castle-throne": { place: "place.castle", spot: "gate-in", t: 1230 },
};

export function startSandbox(): void {
  const q = new URLSearchParams(location.search);
  const scene = q.get("scene");
  const landing = scene ? LANDING[scene] : undefined;
  const player = {
    roleId: "role.traveler",
    place: landing?.place ?? "place.syracuse-square",
    spot: landing?.spot ?? "plaza-southwest",
  };
  const world: WorldData = {
    playthroughId: "pt_SANDBOX",
    lastSeq: 0,
    status: "active",
    actId: q.get("act") ?? "act.1",
    sceneId: scene ? `scene.${scene}` : "scene.syracuse-square",
    clock: {
      t: Number(q.get("t") ?? landing?.t ?? 1050),
      tLabel: "約束の日・夕方",
      deadlineT: 5460,
    },
    deadline: { shown: false },
    forecast: null,
    player,
    places: Object.fromEntries(
      [...PLACES, ...(landing ? [landing.place] : [])].map((id) => [
        id,
        { enabled: true },
      ]),
    ),
    characters: {},
    interactables: [],
    actions: [],
    pending: {
      reveal: null,
      confirm: null,
      actEnd: null,
      safetyPause: false,
      approach: null,
    },
    voice: { enabled: true, degraded: false, minutesLeftToday: 60 },
    events: [],
  };
  setWorld(world);
  placePlayer(player.place, player.spot);
}

function edit(f: (w: WorldData) => WorldData): void {
  const w = useWorld.getState().world;
  if (w) setWorld(f(w));
}

export const sandbox = {
  setClock: (t: number) => edit((w) => ({ ...w, clock: { ...w.clock, t } })),
  setPlaceEnabled: (place: string, enabled: boolean) =>
    edit((w) => ({ ...w, places: { ...w.places, [place]: { enabled } } })),
  setCharacters: (chars: Record<string, SandboxCharacter>) =>
    edit((w) => ({
      ...w,
      characters: Object.fromEntries(
        Object.entries(chars).map(([id, c]) => [
          id,
          { talkable: true, ...c, id },
        ]),
      ),
    })),
};
