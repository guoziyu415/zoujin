// F-12's act end with the voice: the plan said aloud (ux-design 4.4, api-contract 3.11) against B-1's mock, with
// Chromium's fake microphone (a tone) and its prompt answered yes, as in f1. Screenshots go to test-results/f12/.
import { expect, test, type Page } from "@playwright/test";
import { mock, ORIGIN, resetMock, startStory, without3d } from "./shell";

test.use({
  launchOptions: {
    ...(process.env.PW_CHROMIUM
      ? { executablePath: process.env.PW_CHROMIUM }
      : {}),
    args: [
      "--use-angle=swiftshader",
      "--enable-unsafe-swiftshader",
      "--ignore-gpu-blocklist",
      "--use-fake-device-for-media-stream",
      "--use-fake-ui-for-media-stream",
      "--autoplay-policy=no-user-gesture-required",
    ],
  },
});

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
  await without3d(context); // the act-end page over the world, as in f12.spec
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

test("act end: the plan said aloud goes with its turn's id; the result answers it", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["microphone"], { origin: ORIGIN });
  const ae = await toActEnd(page);
  await ae.getByRole("button", { name: /ほかの考えがある/ }).click();
  const key = ae.getByTestId("plan-talk");
  await expect(key).toBeVisible();
  await shot(page, "act-end-propose-voice");
  const box = (await key.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await expect(key).toHaveAttribute("aria-pressed", "true");
  // the words as they are heard, under 「どうしますか。」
  await expect(ae.getByText("夜明けを待って、", { exact: true })).toBeVisible();
  await shot(page, "act-end-plan-heard");
  await page.mouse.up();
  // let go: fixed in 「」 and kept above the answer, to compare
  await expect(
    ae.getByText("「夜明けを待って、村へ向かいたい。」"),
  ).toBeVisible();
  await expect(
    ae.getByText("メロスの姿は、もう夜の向こうに消えていた。"),
  ).toBeVisible();
  await expect(ae.getByRole("button", { name: "そうする" })).toBeVisible();
  await shot(page, "act-end-plan-voice");
});
