// App shell acceptance against B-1's mock (F-0 card): the invite code, a 401 back to the invite page, the 409 at the
// start, one typed turn (subtitles, a light reaction, the clock moving), five seconds offline with the commit
// resent once and only once, and a message type this client doesn't know. Every test starts from a reset mock.
import { expect, test, type Page } from "@playwright/test";
import {
  login,
  mock,
  ORIGIN,
  PT,
  resetMock,
  startStory,
  talkTo,
} from "./shell";

async function sayToMelos(page: Page, text: string) {
  await talkTo(page, "メロス");
  await page.getByRole("button", { name: "文字で話す" }).click();
  await page.getByLabel("言いたいことを書く").fill(text);
  await page.getByRole("button", { name: "送る" }).click();
}

const problems: string[] = [];
// HTTP errors the browser logs on its own and the flow expects: the 401 before login, the 409 at the start, and the
// prerecorded lines the manifest names (preloaded on focus, F-1) while B-6's files aren't in git
let expectedStatus = ["401", "409"];

test.beforeEach(async ({ page, context }) => {
  problems.length = 0;
  expectedStatus = ["401", "409"];
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("console", (m) => {
    const expected = new RegExp(
      `WebSocket connection to .* failed|status of (${expectedStatus.join("|")}) `,
    );
    const voiceFile = m.location().url.includes("/assets/voice/");
    if (m.type() === "error" && !voiceFile && !expected.test(m.text()))
      problems.push(`console: ${m.text()}`);
  });
  await context.clearCookies();
  await resetMock(page);
});

test.afterEach(() => {
  expect(problems).toEqual([]);
});

test("invite code: a wrong one says so, the right one opens the cover", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login\?next=%2F$/);
  await page.getByLabel("招待コード").fill("nope");
  await page.getByRole("button", { name: "すすむ" }).click();
  await expect(page.getByRole("alert")).toHaveText("招待コードが違うようです");
  await login(page);
  await expect(page).toHaveURL(`${ORIGIN}/`);
  await expect(page.getByRole("heading", { name: "走れメロス" })).toBeVisible();
  await expect(page.getByRole("button", { name: "書をひらく" })).toBeVisible();
});

test("a 401 goes back to the invite page and, after it, back to the story", async ({
  page,
}) => {
  const pid = await startStory(page);
  const back = `${ORIGIN}/login?next=${encodeURIComponent(`/play/${pid}`)}`;

  // WebSocket: 4001 on the open story
  await mock(page, "expire-session");
  await expect(page).toHaveURL(back);

  // REST: the snapshot when the story page opens
  await page.goto(`/play/${pid}`);
  await expect(page).toHaveURL(back);
  // after the code, the page asks for that story again (the mock gives a new login a new owner, so it then answers
  // 403 and the page goes to the cover; the real backend keeps the player)
  expectedStatus = ["401", "403"];
  const again = page.waitForRequest((r) =>
    r.url().endsWith(`/v1/playthroughs/${pid}/snapshot`),
  );
  await login(page);
  await again;
  await expect(page).toHaveURL(`${ORIGIN}/`);
});

test("starting while a story is open (409): continue it, or delete it and start anew", async ({
  page,
}) => {
  await page.goto("/");
  await login(page);
  await page.getByRole("button", { name: "書をひらく" }).click();
  // another tab started one meanwhile
  const made = await page.request.post("/v1/playthroughs", {
    data: { bookId: "hashire-merosu", roleId: "role.traveler" },
    headers: { Origin: ORIGIN, "Idempotency-Key": crypto.randomUUID() },
  });
  expect(made.status()).toBe(201);
  const old = ((await made.json()) as { playthroughId: string }).playthroughId;

  await page.getByRole("button", { name: "旅人として、はじめる" }).click();
  const dialog = page.getByRole("alertdialog");
  await expect(dialog).toContainText("続きの物語があります");
  await expect(dialog).toContainText("旅人として・約束の日の夕方");
  await dialog.getByRole("button", { name: "新しく始める" }).click();
  await expect(dialog).toContainText(
    "いまの物語は消えます。新しく始めますか。",
  );
  await dialog.getByRole("button", { name: "やめる" }).click();
  await dialog.getByRole("button", { name: "新しく始める" }).click();
  await dialog.getByRole("button", { name: "新しく始める" }).click();
  await expect(page).toHaveURL(PT);
  const fresh = PT.exec(page.url())![1]!;
  expect(fresh).not.toBe(old);
  const gone = await page.request.get(`/v1/playthroughs/${old}/snapshot`);
  expect([200, 404]).toContain(gone.status());
  if (gone.status() === 200)
    expect(((await gone.json()) as { status: string }).status).toBe("deleted");

  // and 「続きから」 goes into the open one
  await page.goto("/roles");
  await page.getByRole("button", { name: "旅人として、はじめる" }).click();
  await page
    .getByRole("alertdialog")
    .getByRole("button", { name: "続きから" })
    .click();
  await expect(page).toHaveURL(`${ORIGIN}/play/${fresh}`);
});

test("one typed turn: subtitles, a light reaction, the clock moves", async ({
  page,
}) => {
  await mock(page, "scenario", { name: "full-turn" });
  await startStory(page);
  await sayToMelos(page, "この市の王は、人を殺しているそうです。");
  await expect(page.getByTestId("sub-player")).toContainText(
    "この市の王は、人を殺しているそうです。",
  );
  await expect(page.getByTestId("sub-character")).toContainText("メロス");
  await expect(page.getByTestId("sub-character")).toContainText(
    "……なんだと。そんな王を、許しておけるものか。",
  );
  await expect(
    page.getByRole("button", { name: "どうするつもりですか" }),
  ).toBeVisible();
  await expect(
    page.getByTestId("toast").filter({ hasText: "メロスは覚えた" }),
  ).toContainText("王のことを教えてくれた旅の人");
  await expect(page.getByTestId("sunband")).toContainText("+10分");
  await expect(page.locator(".world")).toHaveAttribute("data-last-seq", "1");
  // the mock checks what we send against the schema: nothing came back as invalid_request
  await expect(page.getByTestId("narration")).toHaveCount(0);
});

test("five seconds offline: the commit made meanwhile arrives once, nothing is lost or doubled", async ({
  page,
  context,
}) => {
  await mock(page, "scenario", { name: "full-turn" });
  await startStory(page);
  await sayToMelos(page, "この市の王は、人を殺しているそうです。");
  await expect(page.getByTestId("sub-character")).toContainText(
    "許しておけるものか。",
  );
  await expect(page.locator(".world")).toHaveAttribute("data-last-seq", "0");

  // the network goes; the mock's script goes on and records the commit
  await context.setOffline(true);
  await mock(page, "drop");
  await expect(page.getByText("つながり直しています").first()).toBeVisible();
  await page.waitForTimeout(5000);
  await expect(page.locator(".world")).toHaveAttribute("data-last-seq", "0");
  await context.setOffline(false);

  // back: hello { lastSeq: 0 } and the mock resends seq 1
  await expect(page.locator(".world")).toHaveAttribute("data-last-seq", "1", {
    timeout: 15_000,
  });
  await expect(page.locator(".world")).toHaveAttribute("data-events", "1");
  await expect(
    page.getByTestId("toast").filter({ hasText: "メロスは覚えた" }),
  ).toHaveCount(1);
  await expect(page.getByText("人に近づくと話せます")).toHaveCount(0); // still talking to メロス

  // once more: nothing new to resend, nothing applied twice
  await mock(page, "drop");
  await expect(page.getByText("つながり直しています").first()).toBeVisible();
  // back to where a turn can start (the text field closed after sending; the key is the way in, F-1)
  await expect(page.getByTestId("talk")).toHaveAttribute(
    "data-state",
    "mic-unknown",
    { timeout: 15_000 },
  );
  await expect(page.locator(".world")).toHaveAttribute("data-last-seq", "1");
  await expect(page.locator(".world")).toHaveAttribute("data-events", "1");
});

test("a message type this client doesn't know is ignored and the connection goes on", async ({
  page,
}) => {
  const debug: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "debug") debug.push(m.text());
  });
  await mock(page, "scenario", { name: "future-message" });
  await startStory(page);
  await expect(page.getByTestId("narration")).toHaveText(
    "広場に、夕暮れの風が吹いた。",
  );
  expect(debug).toContain("[net] ignored unknown message type future_feature");
  await expect(page.getByText("人に近づくと話せます")).toBeVisible();
});
