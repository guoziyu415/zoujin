// The private preview keeps no offline pages or scenes. Clear caches installed by old versions so every request goes back through the server's password gate.
// 非公開プレビューはオフラインのページやシーンを保持しない。旧バージョンがインストールしたキャッシュを消し、すべてのリクエストをサーバーのパスワードゲートに戻す。
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
