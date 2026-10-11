// 旧客户端的撤销 worker：删除旧私密缓存、不拦截请求、不提供离线页面。
// 保留 /sw.js 地址，旧安装可更新到这个版本；新页面不再注册 service worker。
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
