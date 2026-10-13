// Retirement worker for old clients: deletes the old private caches, intercepts no requests, serves no offline pages.
// 旧クライアント向けの撤去用 worker：古い非公開キャッシュを削除し、リクエストを横取りせず、オフラインページも提供しない。
// The /sw.js address is kept so old installs can update to this version; new pages no longer register a service worker.
// /sw.js のアドレスは残し、旧インストールがこのバージョンに更新できるようにする。新しいページはもう service worker を登録しない。
type LifeEvent = Event & { waitUntil(promise: Promise<unknown>): void };
const sw = self as unknown as {
  addEventListener(
    type: "install" | "activate",
    handler: (event: LifeEvent) => void,
  ): void;
  skipWaiting(): Promise<void>;
  clients: { claim(): Promise<void> };
  registration: { unregister(): Promise<boolean> };
};
sw.addEventListener("install", (event) => event.waitUntil(sw.skipWaiting()));
sw.addEventListener("activate", (event) =>
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith("zoujin-"))
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => sw.clients.claim())
      .then(() => sw.registration.unregister()),
  ),
);
