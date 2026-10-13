// Private preview: old offline copies are retired; new pages and scenes must not bypass the server's password gate.
// 非公開プレビュー：古いオフラインのコピーは撤去し、新しいページとシーンはサーバーのパスワードゲートを迂回してはならない。
import { expect, test } from "@playwright/test";
import { without3d } from "./shell";

test.use({ serviceWorkers: "allow" });

test("removes legacy private caches and does not install an offline worker", async ({
  page,
  context,
}) => {
  await without3d(context);
  await page.goto("/");
  await page.evaluate(async () => {
    await (
      await caches.open("zoujin-app-old")
    ).put("/old-shell", new Response("private"));
    await (
      await caches.open("zoujin-scenes-01234567")
    ).put("/old-scene", new Response("private"));
  });
  await page.reload();
  await expect
    .poll(() =>
      page.evaluate(async () =>
        (await caches.keys()).filter((key) => key.startsWith("zoujin-")),
      ),
    )
    .toEqual([]);
  expect(
    await page.evaluate(() =>
      navigator.serviceWorker.getRegistrations().then((items) => items.length),
    ),
  ).toBe(0);
  expect(
    await page.evaluate(() => navigator.serviceWorker.controller),
  ).toBeNull();
});
