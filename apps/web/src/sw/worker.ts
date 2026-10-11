// The service worker (frontend-design 10.2 point 5, S-024, F-19): a second visit, a page the phone recycled and an act
// change download almost nothing. Built by vite.config.ts as /sw.js on its own (nothing imported, no exports), with
// the build's list of files put in where PRECACHE says.
// - The shell and the 3D program (hashed names under /assets/, never change): stored when the worker installs, then
//   served from the store. Any other /assets/ file the page asks for (a screen's chunk, the Basis transcoder) is stored
//   the first time.
// - Scene packs at versioned addresses (/scenes/<8 hex>/…, B-7): stored the first time they are fetched, the act-end
//   page's prefetch included, one store per version. The page says which versions the book's manifest still names
//   ({ keepScenes }); the others are deleted. Unversioned /scenes/<slug>/ (the local sandbox) is never stored.
// - The page itself: from the network, the stored copy when the network fails.
// - Everything else (the API, its WebSocket, the voice files, other sites) is not touched.
// A new build installs a new worker: it takes over at once and deletes the old build's store.

type Ev = Event & {
  waitUntil(p: Promise<unknown>): void;
};
type FetchEv = Ev & {
  request: Request;
  respondWith(r: Promise<Response>): void;
};
type MessageEv = Ev & { data: unknown };
type Scope = {
  addEventListener(t: "install" | "activate", f: (e: Ev) => void): void;
  addEventListener(t: "fetch", f: (e: FetchEv) => void): void;
  addEventListener(t: "message", f: (e: MessageEv) => void): void;
  skipWaiting(): Promise<void>;
  clients: { claim(): Promise<void> };
  registration: { scope: string };
};
const sw = self as unknown as Scope;

const PRECACHE: string[] = JSON.parse("__ZOUJIN_PRECACHE__");
const BUILD = "__ZOUJIN_BUILD__";
const APP = `zoujin-app-${BUILD}`;
const SCENES = "zoujin-scenes-"; // + the pack version
const base = new URL(sw.registration.scope).pathname; // "/" or the deploy's base path
const VERSIONED = new RegExp(`^${base}scenes/([0-9a-f]{8})/`);

sw.addEventListener("install", (e) => {
  e.waitUntil(
    caches
      .open(APP)
      .then((c) => c.addAll([base, ...PRECACHE.map((f) => base + f)]))
      .then(() => sw.skipWaiting()),
  );
});

sw.addEventListener("activate", (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k.startsWith("zoujin-app-") && k !== APP)
            .map((k) => caches.delete(k)),
        ),
      )
      .then(() => sw.clients.claim()),
  );
});

// the book manifest's scene addresses: keep their versions' stores, delete the rest
sw.addEventListener("message", (e) => {
  const d = e.data as { keepScenes?: string[] } | null;
  if (!Array.isArray(d?.keepScenes)) return;
  const keep = new Set(
    d.keepScenes
      .map((u) => new URL(u, sw.registration.scope).pathname.match(VERSIONED))
      .map((m) => (m ? SCENES + m[1] : "")),
  );
  e.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k.startsWith(SCENES) && !keep.has(k))
            .map((k) => caches.delete(k)),
        ),
      ),
  );
});

// from the store, else from the network and stored (whole 200 answers only)
async function stored(store: string, req: Request): Promise<Response> {
  const c = await caches.open(store);
  const hit = await c.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.status === 200) void c.put(req, res.clone()).catch(() => {}); // a full store: just not kept
  return res;
}

async function page(req: Request): Promise<Response> {
  try {
    const res = await fetch(req);
    if (res.status === 200)
      void caches
        .open(APP)
        .then((c) => c.put(base, res.clone()))
        .catch(() => {});
    return res;
  } catch (err) {
    const hit = await caches.match(base);
    if (hit) return hit;
    throw err;
  }
}

sw.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET" || req.headers.has("range")) return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (req.mode === "navigate") return e.respondWith(page(req));
  if (url.pathname.startsWith(`${base}assets/`)) {
    if (url.pathname.startsWith(`${base}assets/voice/`)) return; // the prerecorded lines come from the API
    return e.respondWith(stored(APP, req));
  }
  const v = url.pathname.match(VERSIONED);
  if (v) return e.respondWith(stored(SCENES + v[1], req));
});
