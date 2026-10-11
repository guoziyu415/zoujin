// 私密预览：旧离线副本撤销，新页面与场景不得绕过服务端密码门禁。
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
