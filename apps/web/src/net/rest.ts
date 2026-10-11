// REST (api-contract 1, 2): same origin, the session Cookie, JSON. Requests that change data carry
// Content-Type: application/json (the server checks it with Origin, 0) and an Idempotency-Key that stays the same
// across retries of one user action. Any 401 sends the player to the invite page (frontend-design 5).
import type { Api } from "@zoujin/contracts";

export class ApiError extends Error {
  readonly status: number;
  readonly code: Api.ErrorCode | "network";
  readonly body: Api.ErrorResponse | null;
  constructor(status: number, body: Api.ErrorResponse | null) {
    super(body?.error.message ?? `HTTP ${status}`);
    this.status = status;
    this.code = body?.error.code ?? (status === 0 ? "network" : "internal");
    this.body = body;
  }
}

let onUnauthenticated: () => void = () => {};
export function setUnauthenticatedHandler(f: () => void): void {
  onUnauthenticated = f;
}

type Options = { body?: unknown; idempotencyKey?: string; keepalive?: boolean };

async function call<T>(
  method: string,
  path: string,
  o: Options = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") headers["Content-Type"] = "application/json";
  if (o.idempotencyKey) headers["Idempotency-Key"] = o.idempotencyKey;
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      headers,
      credentials: "same-origin",
      ...(o.keepalive ? { keepalive: true } : {}),
      ...(o.body === undefined ? {} : { body: JSON.stringify(o.body) }),
    });
  } catch {
    throw new ApiError(0, null);
  }
  if (res.status === 204) return undefined as T;
  const doc: unknown = await res.json().catch(() => null);
  if (res.ok) return doc as T;
  const err = new ApiError(
    res.status,
    doc && typeof doc === "object" && "error" in doc
      ? (doc as Api.ErrorResponse)
      : null,
  );
  // a wrong invite code is a 401 too, but it isn't a lost session
  if (res.status === 401 && err.code !== "invalid_invite") onUnauthenticated();
  throw err;
}

const pt = (id: string) => `/v1/playthroughs/${encodeURIComponent(id)}`;

export const rest = {
  login: (inviteCode: string) =>
    call<Api.MeResponse>("POST", "/v1/auth/login", {
      body: { inviteCode: inviteCode.trim() } satisfies Api.LoginRequest,
    }),
  logout: () => call<void>("POST", "/v1/auth/logout", { body: {} }),
  me: () => call<Api.MeResponse>("GET", "/v1/me"),
  manifest: (bookId: string) =>
    call<Api.ManifestResponse>(
      "GET",
      `/v1/books/${encodeURIComponent(bookId)}/manifest`,
    ),
  createPlaythrough: (
    req: Api.CreatePlaythroughRequest,
    idempotencyKey: string,
  ) =>
    call<Api.CreatePlaythroughResponse>("POST", "/v1/playthroughs", {
      body: req,
      idempotencyKey,
    }),
  deletePlaythrough: (id: string, idempotencyKey: string) =>
    call<void>("DELETE", pt(id), { idempotencyKey }),
  snapshot: (id: string) => call<Api.Snapshot>("GET", `${pt(id)}/snapshot`),
  events: (id: string, afterSeq: number) =>
    call<Api.EventsResponse>(
      "GET",
      `${pt(id)}/events?afterSeq=${afterSeq}&limit=50`,
    ),
  // the chain-reaction map, why, the memory book, the ending (2.6-2.8)
  timeline: (id: string) =>
    call<Api.TimelineResponse>("GET", `${pt(id)}/timeline`),
  why: (id: string, target: string) =>
    call<Api.WhyResponse>(
      "GET",
      `${pt(id)}/why?target=${encodeURIComponent(target)}`,
    ),
  memories: (id: string) =>
    call<Api.MemoriesResponse>("GET", `${pt(id)}/memories`),
  memoryImpact: (id: string, memoryId: string) =>
    call<Api.MemoryImpactResponse>(
      "GET",
      `${pt(id)}/memories/${encodeURIComponent(memoryId)}/impact`,
    ),
  deleteMemory: (id: string, memoryId: string, idempotencyKey: string) =>
    call<Api.MemoryDeleteResponse>(
      "DELETE",
      `${pt(id)}/memories/${encodeURIComponent(memoryId)}`,
      { idempotencyKey },
    ),
  // 202 { status: "pending", etaSeconds } until the ending is written
  ending: (id: string) =>
    call<Api.EndingView | Api.EndingPending>("GET", `${pt(id)}/ending`),
  // keepalive: the page is being hidden or closed (frontend-design 11's sendBeacon, with our headers)
  telemetry: (batch: Api.TelemetryBatch, keepalive = false) =>
    call<void>("POST", "/v1/telemetry", { body: batch, keepalive }),
};
