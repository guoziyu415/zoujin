// The one WebSocket of a playthrough (api-contract 3, 4): hello { lastSeq } first, ping every 20 s, and when it drops
// a reconnect after 1, 2, 4, 8 s (8 s from then on). The close codes decide what happens: 4001 back to the invite
// page, 4009 another tab took the story, 4003 / 4004 the story is gone, 1012 reconnect at once; goaway reconnects
// after the delay it gives. Only this file and the session touch the socket (frontend-design 4).
import type { Api } from "@zoujin/contracts";

export const BACKOFF_MS = [1000, 2000, 4000, 8000];
export const PING_MS = 20_000;

export type Ended = "unauthenticated" | "taken" | "gone";

export type LiveEvents = {
  lastSeq: () => number; // what to put in hello
  onMessage: (m: { type: string } & Record<string, unknown>) => void;
  onBinary?: (data: ArrayBuffer) => void; // character audio (F-1)
  onOpen: () => void; // hello sent (the welcome comes as a message)
  onDown: (reason: string) => void; // dropped, will retry
  onEnded: (why: Ended) => void; // won't retry until asked
};

type Socket = Pick<WebSocket, "send" | "close" | "binaryType"> & {
  readyState: number;
  onopen: ((e: Event) => void) | null;
  onclose: ((e: CloseEvent) => void) | null;
  onmessage: ((e: MessageEvent) => void) | null;
  onerror: ((e: Event) => void) | null;
};
type SocketCtor = new (url: string) => Socket;

export class Live {
  private ws: Socket | null = null;
  private attempt = 0;
  private retryTimer: ReturnType<typeof setTimeout> | undefined;
  private pingTimer: ReturnType<typeof setInterval> | undefined;
  private stopped = false;

  constructor(
    private readonly url: string,
    private readonly clientVersion: string,
    private readonly on: LiveEvents,
    private readonly Ctor: SocketCtor = WebSocket as unknown as SocketCtor,
  ) {}

  get open(): boolean {
    return this.ws?.readyState === 1;
  }

  connect(): void {
    this.stopped = false;
    clearTimeout(this.retryTimer);
    this.retryTimer = undefined;
    // replacing a socket: drop its handlers first so its close isn't taken for this connection's
    const old = this.ws;
    this.ws = null;
    if (old) {
      old.onclose = old.onmessage = old.onopen = null;
      old.close();
    }
    const ws = new this.Ctor(this.url);
    ws.binaryType = "arraybuffer";
    this.ws = ws;
    ws.onopen = () => {
      this.attempt = 0;
      this.raw({
        type: "hello",
        lastSeq: this.on.lastSeq(),
        clientVersion: this.clientVersion,
      });
      clearInterval(this.pingTimer);
      this.pingTimer = setInterval(() => this.raw({ type: "ping" }), PING_MS);
      this.on.onOpen();
    };
    ws.onmessage = (e) => {
      if (typeof e.data !== "string") {
        this.on.onBinary?.(e.data as ArrayBuffer);
        return;
      }
      let m: unknown;
      try {
        m = JSON.parse(e.data);
      } catch {
        return;
      }
      if (
        !m ||
        typeof m !== "object" ||
        typeof (m as { type?: unknown }).type !== "string"
      )
        return;
      const msg = m as { type: string } & Record<string, unknown>;
      if (msg.type === "goaway") {
        // the server closes within ~10 s anyway; reconnect on our side after the delay it asks for
        this.retry(Number(msg.reconnectAfterMs) || 0);
      }
      this.on.onMessage(msg);
    };
    ws.onclose = (e) => {
      if (this.ws !== ws) return; // an old socket we replaced
      clearInterval(this.pingTimer);
      this.ws = null;
      if (this.stopped) return;
      switch (e.code) {
        case 4001:
          this.stopped = true;
          return this.on.onEnded("unauthenticated");
        case 4009:
          this.stopped = true;
          return this.on.onEnded("taken");
        case 4003:
        case 4004:
          this.stopped = true;
          return this.on.onEnded("gone");
      }
      this.on.onDown(`close ${e.code}`);
      if (this.retryTimer !== undefined) return; // goaway already scheduled one
      if (e.code === 1012) return this.retry(0);
      const wait =
        e.code === 4290
          ? BACKOFF_MS[BACKOFF_MS.length - 1]!
          : BACKOFF_MS[Math.min(this.attempt, BACKOFF_MS.length - 1)]!;
      this.attempt++;
      this.retry(wait);
    };
    ws.onerror = () => {}; // a close follows
  }

  private retry(ms: number): void {
    clearTimeout(this.retryTimer);
    this.retryTimer = setTimeout(() => {
      this.retryTimer = undefined;
      if (!this.stopped) this.connect();
    }, ms);
  }

  // the banner's 「もう一度つなぐ」, coming back to the page, 「この画面で続ける」 after 4009: try now
  retryNow(): void {
    this.attempt = 0;
    this.connect();
  }

  send(m: Api.ClientMessage): boolean {
    return this.raw(m);
  }

  sendBinary(data: ArrayBuffer): boolean {
    if (!this.open) return false;
    this.ws!.send(data);
    return true;
  }

  private raw(m: Api.ClientMessage): boolean {
    if (!this.open) return false;
    this.ws!.send(JSON.stringify(m));
    return true;
  }

  // leaving for good (pagehide, the screen unmounts): close and don't come back
  close(): void {
    this.stopped = true;
    clearTimeout(this.retryTimer);
    this.retryTimer = undefined;
    clearInterval(this.pingTimer);
    const ws = this.ws;
    this.ws = null;
    ws?.close(1000);
  }
}
