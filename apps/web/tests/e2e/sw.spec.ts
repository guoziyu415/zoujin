// The service worker (F-19, frontend-design 10.2 point 5): the first visit installs it and stores the shell and the 3D
// program; the next visit takes them from the store, and so does a page opened with no network. A scene pack at a
// versioned address is stored the first time it is fetched; the versions the book's manifest no longer names go.
import { expect, test, type Page } from "@playwright/test";

test.use({ serviceWorkers: "allow" });

const VERSION = "0a1b2c3d";
const SCENE = `/scenes/${VERSION}/syracuse-square/scene.json`;

const controlled = (page: Page) =>
  page.waitForFunction(() => !!navigator.serviceWorker.controller, null, {
    timeout: 30_000,
  });

const stores = (page: Page) =>
  page.evaluate(async () => {
    const out: Record<string, string[]> = {};
    for (const k of await caches.keys())
      out[k] = (await (await caches.open(k)).keys()).map(
        (r) => new URL(r.url).pathname,
      );
    return out;
  });

test("stores the shell and the 3D program, then serves them; scene packs by version", async ({
  page,
  context,
}) => {
  await page.goto("/");
  await controlled(page);
  const first = await stores(page);
  const app = Object.keys(first).filter((k) => k.startsWith("zoujin-app-"));
  expect(app).toHaveLength(1);
  const files = first[app[0]!]!;
  expect(files).toContain("/");
  expect(files.some((f) => /^\/assets\/index-.*\.js$/.test(f))).toBe(true);
  expect(files.some((f) => /^\/assets\/WorldScreen-.*\.js$/.test(f))).toBe(
    true,
  );

  // the next visit: its program from the store (the page itself comes from the network while there is one)
  const fromStore: string[] = [];
  const fromNet: string[] = [];
  page.on("response", (r) => {
    const p = new URL(r.url()).pathname;
    if (p.startsWith("/assets/"))
      (r.fromServiceWorker() ? fromStore : fromNet).push(p);
  });
  await page.reload();
  await expect(page.locator("#root")).not.toBeEmpty();
  expect(fromStore.filter((p) => p.endsWith(".js")).length).toBeGreaterThan(0);
  expect(fromNet).toEqual([]);

  // with no network the page still opens
  await context.setOffline(true);
  await page.reload();
  await expect(page.locator("#root")).not.toBeEmpty();
  await context.setOffline(false);

  // a versioned scene file: stored the first time, its version's store kept while the manifest names it
  expect(
    await page.evaluate((u) => fetch(u).then((r) => r.status), SCENE),
  ).toBe(200);
  await expect
    .poll(async () => (await stores(page))[`zoujin-scenes-${VERSION}`])
    .toEqual([SCENE]);
  // unversioned (the local sandbox's address) is never stored
  await page.evaluate(() => fetch("/scenes/syracuse-square/scene.json"));
  const keep = (urls: string[]) =>
    page.evaluate(
      (urls) =>
        navigator.serviceWorker.ready.then((r) =>
          r.active!.postMessage({ keepScenes: urls }),
        ),
      urls,
    );
  await keep([SCENE]);
  await page.waitForTimeout(500);
  expect(Object.keys(await stores(page)).sort()).toEqual(
    [app[0]!, `zoujin-scenes-${VERSION}`].sort(),
  );
  // a new book version: the old pack's store goes
  await keep([`/scenes/ffffffff/syracuse-square/scene.json`]);
  await expect
    .poll(async () => Object.keys(await stores(page)))
    .toEqual([app[0]!]);
});
