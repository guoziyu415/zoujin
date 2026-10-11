// The 3D sandbox (?world, ?dev, the measuring page): no server, so a local world in the real stores with what the 3D
// reads; the dev panel, the measuring page and the e2e test hook change it the way the server's commits would.
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

export function startSandbox(): void {
  const player = {
    roleId: "role.traveler",
    place: "place.syracuse-square",
    spot: "plaza-southwest",
  };
  const world: WorldData = {
    playthroughId: "pt_SANDBOX",
    lastSeq: 0,
    status: "active",
    actId: "act.1",
    sceneId: "scene.syracuse-square",
    clock: { t: 1050, tLabel: "約束の日・夕方", deadlineT: 5460 },
    deadline: { shown: false },
    forecast: null,
    player,
    places: Object.fromEntries(PLACES.map((id) => [id, { enabled: true }])),
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
