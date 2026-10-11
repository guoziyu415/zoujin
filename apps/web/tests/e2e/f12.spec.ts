// F-12 against B-1's mock: the act end (exits, a plan that doesn't go, the alternative), その頃, the slice's jump
// page and the landing (act_landed when someone speaks first); then the memory book, the map and the ending.
// Screenshots for UX go to test-results/f12/.
import { expect, test, type Page } from "@playwright/test";
import { mock, resetMock, startStory } from "./shell";

const problems: string[] = [];

test.beforeEach(async ({ page, context }) => {
  problems.length = 0;
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("console", (m) => {
    const voiceFile = m.location().url.includes("/assets/voice/");
    if (
      m.type() === "error" &&
      !voiceFile &&
      !/WebSocket connection to .* failed|status of (401|409) /.test(m.text())
    )
      problems.push(`console: ${m.text()}`);
  });
  await context.clearCookies();
  await resetMock(page);
});

test.afterEach(() => {
  expect(problems).toEqual([]);
});

const shot = (page: Page, name: string) =>
  page.screenshot({ path: `test-results/f12/${name}.png`, fullPage: true });

async function toActEnd(page: Page) {
  await mock(page, "scenario", { name: "act-end" });
  await startStory(page);
  const pageEl = page.getByRole("dialog", { name: "第一幕　約束の日　おわり" });
  await expect(pageEl).toBeVisible({ timeout: 60_000 });
  return pageEl;
}

test("act end: a plan that doesn't go, then the alternative; その頃, the jump page, the landing line", async ({
  page,
}) => {
  const ae = await toActEnd(page);
  await expect(ae.getByText("三日のあいだ、あなたは──")).toBeVisible();
  const city = ae.getByRole("button", { name: /市に残り、メロスの帰りを待つ/ });
  await expect(city).toContainText("刑場・三日目の夕方");
  await expect(city).toContainText("西の門が見える所で");
  await ae.getByText("この幕であなたが動かしたこと（2）").click();
  await expect(ae.getByText("あなたは、老爺を家まで送った。")).toBeVisible();
  await shot(page, "act-end");

  await ae.getByRole("button", { name: /ほかの考えがある/ }).click();
  await expect(ae.getByText("どうしますか。")).toBeVisible();
  await ae.getByLabel("どうしますか。").fill("夜明けを待って、村へ向かいたい");
  await ae.getByRole("button", { name: "伝える" }).click();
  await expect(
    ae.getByText("メロスの姿は、もう夜の向こうに消えていた。"),
  ).toBeVisible();
  await shot(page, "act-end-plan-refused");
  await ae.getByRole("button", { name: "そうする" }).click();

  const sk = page.getByRole("dialog", { name: "その頃──" });
  await expect(sk).toBeVisible();
  await expect(
    sk.getByText("セリヌンティウスは、黙って縄を打たれた。"),
  ).toBeVisible();
  await shot(page, "sonokoro");
  await sk.getByRole("button", { name: "つづける" }).click();

  const jump = page.getByRole("dialog", { name: "第四幕　三日目" });
  await expect(jump).toBeVisible();
  await jump.click({ position: { x: 20, y: 400 } }); // a tap shows the rest at once
  await expect(
    jump.getByText("夕方になった。メロスは、まだ帰らない。"),
  ).toBeVisible();
  await shot(page, "jump");
  await jump.getByRole("button", { name: "つづける" }).click();

  await expect(jump).toBeHidden();
  await expect(
    page.getByText("刑場の西のはずれ。", { exact: false }),
  ).toBeVisible();
  await expect(page.getByTestId("sunband")).toHaveText("三日目・夕方");
});

test("act end: the old man's exit lands with him speaking first (act_landed)", async ({
  page,
}) => {
  const ae = await toActEnd(page);
  await ae.getByRole("button", { name: /老爺の家に身を寄せる/ }).click();
  await expect(
    ae.getByRole("button", { name: /老爺の家に身を寄せる/ }),
  ).toHaveAttribute("aria-pressed", "true");
  await page
    .getByRole("dialog", { name: "その頃──" })
    .getByRole("button", { name: "つづける" })
    .click();
  await page
    .getByRole("dialog", { name: "第四幕　三日目" })
    .getByRole("button", { name: "つづける" })
    .click();
  await expect(
    page.getByText("いまは二人で、刑場の前に立っている。", { exact: false }),
  ).toBeVisible();
  // the mock only lets the old man speak after act_landed
  await expect(
    page.getByText("あの若いのは、まだ見えぬ。", { exact: false }),
  ).toBeVisible({
    timeout: 30_000,
  });
});
