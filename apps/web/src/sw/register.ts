// 私密预览不保留离线页面或场景。清理旧版本已安装的缓存，所有请求回到服务器密码门禁。
export function registerWorker(): void {
  if ("caches" in window) {
    void caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith("zoujin-"))
            .map((key) => caches.delete(key)),
        ),
      )
      .catch(() => {});
  }
  if (!("serviceWorker" in navigator)) return;
  void navigator.serviceWorker
    .getRegistrations()
    .then(async (registrations) => {
      const ours = registrations.filter((registration) => {
        const url =
          registration.active?.scriptURL ??
          registration.waiting?.scriptURL ??
          registration.installing?.scriptURL;
        return (
          url &&
          new URL(url).origin === location.origin &&
          new URL(url).pathname === `${import.meta.env.BASE_URL}sw.js`
        );
      });
      await Promise.all(ours.map((registration) => registration.unregister()));
      // Unregister leaves the current document controlled until navigation. A single reload releases it.
      if (ours.length && navigator.serviceWorker.controller) location.reload();
    })
    .catch(() => {});
}

// Compatibility for callers: no persistent scene cache while the app is private.
export function keepScenes(urls: string[]): void {
  void urls;
}
