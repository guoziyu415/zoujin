// Test helpers for the network layer (unit tests only; nothing in the app imports this): a socket the test drives and
// a snapshot shaped like B-1's.
import type { Api } from "@zoujin/contracts";

export class FakeSocket {
  static all: FakeSocket[] = [];
  static last(): FakeSocket {
    return FakeSocket.all[FakeSocket.all.length - 1]!;
  }
  readyState = 0;
  binaryType: BinaryType = "blob";
  sent: Record<string, unknown>[] = [];
  binary: ArrayBuffer[] = []; // microphone frames
  closedWith: number | null = null;
  onopen: ((e: Event) => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;

  constructor(readonly url: string) {
    FakeSocket.all.push(this);
  }
  send(d: string | ArrayBuffer): void {
    if (typeof d === "string")
      this.sent.push(JSON.parse(d) as Record<string, unknown>);
    else this.binary.push(d);
  }
  close(code = 1000): void {
    if (this.readyState === 3) return;
    this.readyState = 3;
    this.closedWith = code;
    this.onclose?.({ code } as CloseEvent);
  }
  // the server's side
  open(): void {
    this.readyState = 1;
    this.onopen?.(new Event("open"));
  }
  receive(m: unknown): void {
    this.onmessage?.({
      data: typeof m === "string" ? m : JSON.stringify(m),
    } as MessageEvent);
  }
  receiveBinary(buf: ArrayBuffer): void {
    this.onmessage?.({ data: buf } as MessageEvent);
  }
  drop(code = 1006): void {
    this.readyState = 3;
    this.onclose?.({ code } as CloseEvent);
  }
  types(): string[] {
    return this.sent.map((m) => String(m.type));
  }
}

export const PID = "pt_01JAAAAAAAAAAAAAAAAAAAAAAA";

export function snapshot(over: Partial<Api.Snapshot> = {}): Api.Snapshot {
  return {
    playthroughId: PID,
    lastSeq: 0,
    status: "active",
    actId: "act.1",
    sceneId: "scene.syracuse-square",
    clock: { t: 1050, tLabel: "約束の日・夕方", deadlineT: 5460 },
    deadline: { shown: false },
    forecast: null,
    player: {
      roleId: "role.traveler",
      place: "place.syracuse-square",
      spot: "plaza-southwest",
    },
    places: [
      { id: "place.syracuse-square", enabled: true },
      { id: "place.stonemason-workshop", enabled: true },
    ],
    characters: [
      {
        id: "char.old-man",
        place: "place.syracuse-square",
        spot: "market-west",
        activity: "idle",
        talkable: true,
      },
      {
        id: "char.melos",
        place: "place.syracuse-square",
        spot: "fountain-east",
        activity: "walk",
        talkable: true,
      },
    ],
    interactables: [],
    actions: [],
    pending: {
      reveal: null,
      confirm: null,
      actEnd: null,
      safetyPause: false,
      approach: null,
    },
    voice: { enabled: true, degraded: false, minutesLeftToday: 52 },
    ...over,
  };
}

let n = 0;
export function event(over: Partial<Api.VisibleEvent> = {}): Api.VisibleEvent {
  n++;
  return {
    eventId: `ev_01JAAAAAAAAAAAAAAAAAAAA${String(n).padStart(3, "0")}`,
    seq: n,
    t: 1060,
    dt: 10,
    tLabel: "約束の日・夕方",
    type: "say",
    actor: "player",
    forPlayer: false,
    place: "place.syracuse-square",
    summary: "あなたがメロスに話した",
    causes: [],
    visibleEffects: [],
    promise: null,
    keyMoment: false,
    supersedes: null,
    ...over,
  };
}

export function commit(
  fromSeq: number,
  seq: number,
  over: Partial<Api.CommitMessage> = {},
): Api.CommitMessage {
  return {
    type: "commit",
    fromSeq,
    seq,
    events: [],
    patch: {},
    memories: [],
    promises: [],
    narration: [],
    cue: null,
    reveal: null,
    ...over,
  };
}

export function welcome(
  lastSeq: number,
  over: Partial<Api.WelcomeMessage> = {},
): Api.WelcomeMessage {
  return {
    type: "welcome",
    lastSeq,
    voice: { enabled: true, degraded: false, minutesLeftToday: 52 },
    lastTurn: null,
    pending: {
      reveal: null,
      confirm: null,
      actEnd: null,
      safetyPause: false,
      approach: null,
    },
    ...over,
  };
}
