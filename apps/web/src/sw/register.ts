// The page's side of the service worker (worker.ts): registered once the page has loaded, in a production build only.
// Playwright blocks service workers except in sw.spec.ts (playwright.config.ts): the other checks watch the network.

const on = import.meta.env.PROD && "serviceWorker" in navigator;

export function registerWorker(): void {
  if (!on) return;
  const go = () =>
    void navigator.serviceWorker
      .register(`${import.meta.env.BASE_URL}sw.js`)
      .catch(() => {}); // private mode or blocked storage: the page works without it
  if (document.readyState === "complete") go();
  else addEventListener("load", go, { once: true });
}

// the scene addresses the book's manifest names: the worker keeps their packs and deletes older versions
export function keepScenes(urls: string[]): void {
  if (!on) return;
  void navigator.serviceWorker.ready
    .then((r) => r.active?.postMessage({ keepScenes: urls }))
    .catch(() => {});
}
