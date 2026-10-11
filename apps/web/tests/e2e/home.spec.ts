// H-1 的真实页面流程：目录/存档由可控 API 返回，绝不在产品中注入示例结局。
import { expect, test } from "@playwright/test";
import {
  login,
  openFirstBook,
  resetMock,
  startStory,
  without3d,
} from "./shell";

const emptyLibrary = {
  activePlaythrough: null,
  endings: [],
  pendingEndings: [],
};

test.beforeEach(async ({ page, context }) => {
  await without3d(context);
  await resetMock(page);
});

test("a new reader selects the real book and sees an honest empty memory book", async ({
  page,
}) => {
  const writes: string[] = [];
  page.on("request", (request) => {
    if (
      ["POST", "DELETE"].includes(request.method()) &&
      /\/v1\/playthroughs/.test(request.url())
    )
      writes.push(request.url());
  });
  await page.goto("/");
  await login(page);
  await expect(
    page.getByRole("heading", { name: "あなたの書斎" }),
  ).toBeVisible();
  await page.getByRole("button", { name: /回想録.*たどり着いた結末/ }).click();
  const panel = page.getByRole("dialog", { name: "回想録" });
  await expect(panel.getByText("まだ、白いページ。")).toBeVisible();
  await expect(panel.locator("li")).toHaveCount(0);
  await panel.getByRole("button", { name: "本棚へ →" }).click();
  await expect(
    page
      .getByRole("dialog", { name: "本棚" })
      .getByRole("button", { name: "書斎に戻る" }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(panel).toHaveCount(0);
  await openFirstBook(page);
  await expect(page).toHaveURL(/\/books\/hashire-merosu$/);
  await expect(page.getByRole("heading", { name: "走れメロス" })).toBeVisible();
  await page.getByRole("button", { name: "← 書斎に戻る" }).click();
  expect(writes).toEqual([]);
});

test("returning home and resuming keeps the same run and creates or deletes nothing", async ({
  page,
}) => {
  const pid = await startStory(page);
  const writes: string[] = [];
  page.on("request", (request) => {
    if (
      ["POST", "DELETE"].includes(request.method()) &&
      /\/v1\/playthroughs/.test(request.url())
    )
      writes.push(request.url());
  });
  await page
    .getByRole("button", { name: "本をひらく（連鎖反応マップ・記憶帳）" })
    .click();
  await page.getByRole("button", { name: "書斎に戻る", exact: true }).click();
  await expect(page).toHaveURL("http://127.0.0.1:4173/");
  await page.getByRole("button", { name: /しおりの続きから/ }).click();
  await expect(page).toHaveURL(`http://127.0.0.1:4173/play/${pid}`);
  await expect(page.getByTestId("sunband")).toHaveText("約束の日・夕方");
  expect(writes).toEqual([]);
});

test("memories show only server-returned completions, with pending work labelled separately", async ({
  page,
}) => {
  await page.goto("/");
  await login(page);
  await expect(
    page.getByRole("heading", { name: "あなたの書斎" }),
  ).toBeVisible();
  await page.route("**/v1/library", (route) =>
    route.fulfill({
      json: {
        ...emptyLibrary,
        endings: [
          {
            playthroughId: "pt_01TESTDONE",
            bookId: "hashire-merosu",
            worldModelVersion: "test",
            bookTitle: "走れメロス",
            roleId: "role.traveler",
            roleName: "旅人",
            endedAt: "2026-10-12T03:00:00Z",
            endingId: "end_01TESTDONE",
            title: "テストで体験した結末",
            subtitle: "サーバーが返した記録",
          },
        ],
        pendingEndings: [
          {
            playthroughId: "pt_01TESTPENDING",
            bookId: "hashire-merosu",
            worldModelVersion: "test",
            bookTitle: "走れメロス",
            roleId: "role.traveler",
            roleName: "旅人",
            endedAt: "2026-10-12T04:00:00Z",
          },
        ],
      },
    }),
  );
  await page.reload();
  await page.getByRole("button", { name: /回想録.*たどり着いた結末/ }).click();
  const panel = page.getByRole("dialog", { name: "回想録" });
  await expect(panel.getByRole("listitem")).toHaveCount(2);
  await expect(panel.getByText("テストで体験した結末")).toBeVisible();
  await expect(panel.getByText("物語を綴じています")).toBeVisible();
  await expect(panel.getByText("まだ、白いページ。")).toHaveCount(0);
});

test("an unavailable book cannot start a run and a failed library is never presented as empty", async ({
  page,
}) => {
  await page.goto("/");
  await login(page);
  await expect(
    page.getByRole("heading", { name: "あなたの書斎" }),
  ).toBeVisible();
  await page.route("**/v1/books", (route) =>
    route.fulfill({
      json: {
        books: [
          {
            bookId: "private-second-book",
            worldModelVersion: "test",
            title: "試験用の本",
            author: "テスト",
            year: 1900,
            description: "未公開",
            availability: "unavailable",
            manifestUrl: "/v1/books/private-second-book/manifest",
          },
        ],
      },
    }),
  );
  await page.route("**/v1/library", (route) =>
    route.fulfill({
      status: 503,
      json: { error: { code: "internal", message: "failed" } },
    }),
  );
  await page.reload();
  await page.getByRole("button", { name: /本棚.*次の世界を選ぶ/ }).click();
  await expect(
    page.getByRole("button", { name: /もうしばらくお待ちください/ }),
  ).toBeDisabled();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: /回想録.*たどり着いた結末/ }).click();
  const panel = page.getByRole("dialog", { name: "回想録" });
  await expect(panel.getByRole("alert")).toBeVisible();
  await expect(panel.getByText("まだ、白いページ。")).toHaveCount(0);
});
