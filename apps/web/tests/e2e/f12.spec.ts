// F-12 against B-1's mock: the act end (exits, a plan that doesn't go, the alternative), その頃, the slice's jump
// page and the landing (act_landed when someone speaks first); then the memory book, the map and the ending.
// Screenshots for UX go to test-results/f12/. The plaza under the play screen is left out, as in f0 and f1.
import { expect, test, type Page } from "@playwright/test";
import { mock, resetMock, startStory, without3d } from "./shell";

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
  await without3d(context); // the screens over the world; the 3D under them is world.spec's and gate.spec's
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
  // the act change moves the clock by a snapshot: no 「+n時間」 (ux-design 4.5)
  await expect(page.getByTestId("sunband").locator(".delta")).toHaveCount(0);
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
  // the new act's subtitle panel starts from the landing line: the first act's last words are gone
  await expect(
    page.getByText("すまない、行かねば。", { exact: false }),
  ).toBeHidden();
  await shot(page, "landing");
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

test("memory book: tabs, sections, forgetting a promise moves the relation and the promise goes", async ({
  page,
}) => {
  await mock(page, "scenario", { name: "limits" });
  await startStory(page);
  await page.getByRole("button", { name: /^本をひらく/ }).click();
  await page.getByRole("button", { name: "記憶帳", exact: true }).click();
  const mb = page.getByRole("dialog", { name: "記憶帳" });
  await expect(mb.getByRole("tab", { name: "メロス" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(mb.getByRole("tab", { name: "市の老爺" })).toBeVisible();
  await expect(mb.getByText("メロスの力になる", { exact: true })).toBeVisible();
  await expect(mb.getByText("あなた → メロス")).toBeVisible();
  await expect(mb.getByText("王のことを、メロスに告げた")).toBeVisible();
  await shot(page, "memory-book");

  // a promise opens the map at the event that made it, like the deeds
  await mb.getByRole("button", { name: /^メロスの力になる/ }).click();
  const map = page.getByRole("dialog", { name: "連鎖反応マップ" });
  await expect(map).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(map).toBeHidden();
  await page.getByRole("button", { name: /^本をひらく/ }).click();
  await page.getByRole("button", { name: "記憶帳", exact: true }).click();
  await expect(mb).toBeVisible();

  const card = mb
    .getByRole("listitem")
    .filter({ hasText: "力になると約束してくれた旅の人" });
  await card.getByRole("button", { name: "忘れてもらう" }).click();
  await expect(
    card.getByText("メロスに、このことを忘れてもらいますか。"),
  ).toBeVisible();
  await expect(
    card.getByText("この約束も、なかったことになります。"),
  ).toBeVisible();
  await shot(page, "memory-forget");
  await card
    .getByRole("group")
    .getByRole("button", { name: "忘れてもらう" })
    .click();
  await expect(mb.getByRole("status")).toHaveText(
    "メロスは、そのことを忘れた。",
  );
  await expect(card).toBeHidden();
  await expect(mb.getByText("様子を見ている")).toBeVisible();
  await expect(mb.getByText("メロスの力になる", { exact: true })).toBeHidden(); // voided: not shown

  // the other tab; Escape closes and the menu button has the focus back
  await mb.getByRole("tab", { name: "市の老爺" }).click();
  await expect(
    mb.getByText("暗い道を、家まで送ってくれた旅の人"),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(mb).toBeHidden();
});

// the mock's opening clock (1050) is before its timeline's events: the map's 「いまここ」 belongs after the last item
// with a result (events and beats, 1170), so the clock the page starts from moves there, the time label as it is
async function clockAt(page: Page, t: number) {
  const at = (s: { clock: { t: number } }) => (s.clock.t = t);
  await page.route(/\/v1\/playthroughs(\/[^/]+\/snapshot)?$/, async (route) => {
    const res = await route.fetch();
    const body = (await res.json()) as {
      clock?: { t: number };
      snapshot?: { clock: { t: number } };
    };
    if (body.snapshot) at(body.snapshot);
    else if (body.clock) at(body as { clock: { t: number } });
    await route.fulfill({ response: res, json: body });
  });
}

test("map: the timeline by day, beats and their state, future beats as ？, filters, why", async ({
  page,
}) => {
  await mock(page, "scenario", { name: "limits" });
  await clockAt(page, 1170);
  await startStory(page);
  await page.getByRole("button", { name: /^本をひらく/ }).click();
  await page
    .getByRole("button", { name: "連鎖反応マップ", exact: true })
    .click();
  const map = page.getByRole("dialog", { name: "連鎖反応マップ" });
  await expect(map.getByRole("heading", { name: "約束の日" })).toBeVisible();
  await expect(
    map.getByRole("button", { name: /あなたは、老爺を家まで送った/ }),
  ).toBeVisible();
  await expect(
    map.getByRole("button", { name: /王の暴虐を知る/ }),
  ).toContainText("変わった");
  await expect(map.getByText("？")).toHaveCount(2);
  // 「いまここ」 after the last item with a result, before the beats still to come
  const now = map.locator(".map-now");
  await expect(now).toHaveCount(1);
  await shot(page, "map");

  await map.getByRole("button", { name: "市の老爺" }).click();
  await expect(
    map.getByRole("button", { name: /王が人を殺している/ }),
  ).toBeHidden();
  await expect(
    map.getByRole("button", { name: /老爺を家まで送った/ }),
  ).toBeVisible();
  await map.getByRole("button", { name: "市の老爺" }).click();

  await map.getByRole("button", { name: /王の暴虐を知る/ }).click();
  await map.getByRole("button", { name: "なぜこうなった？" }).click();
  const why = map.getByRole("list", { name: "なぜこうなった？" });
  await expect(why.getByRole("listitem")).toHaveCount(2);
  await expect(why).toContainText("メロスは王の暴虐を知り、激怒した");
  await shot(page, "map-why");
});

test("ending: the staging hands over to the ending page; world, you, the people; a source mark opens the map; the card draws", async ({
  page,
}) => {
  await mock(page, "scenario", { name: "ending" });
  // the telemetry batches that go out (every 10 s): ending_performed is among them once the staging has played
  const sent: { name: string; props: Record<string, unknown> }[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().endsWith("/v1/telemetry"))
      sent.push(...(r.postDataJSON() as { events: typeof sent }).events);
  });
  const pid = await startStory(page);
  // the staging: the HUD goes, only the 3D and the subtitles stay (11.1)
  await expect(page.locator(".hud-bottom")).toBeHidden({ timeout: 60_000 });
  // tap through the closing lines (each tap completes or moves on; taps within 0.5 s don't count)
  const ending = new RegExp(`/ending/${pid}$`);
  let subtitled = false;
  for (let i = 0; i < 200 && !ending.test(page.url()); i++) {
    const stage = page.locator(".end-stage");
    // a subtitle of the staging, once, for UX (the closing set pieces come with the mock of api-contract v1.0.12)
    if (!subtitled && (await stage.locator(".end-sub").count()) > 0) {
      await page.waitForTimeout(1500);
      await shot(page, "ending-subtitles").catch(() => {});
      subtitled = true;
    }
    if (await stage.isVisible().catch(() => false))
      await stage.click({ position: { x: 20, y: 20 } }).catch(() => {});
    await page.waitForTimeout(600);
  }
  await expect(page).toHaveURL(ending, { timeout: 30_000 });
  // what the staging measured, for data (data-design 9.3)
  await expect
    .poll(() => sent.find((e) => e.name === "ending_performed")?.props, {
      timeout: 15_000,
    })
    .toMatchObject({
      trigger: "story-closed",
      lines: expect.any(Number),
      taps: expect.any(Number),
      autoAdvance: expect.any(Boolean),
    });
  await expect(
    page.getByRole("heading", { name: "原作どおりの大団円" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "あなたの結末" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "登場人物の結末" }),
  ).toBeVisible();
  await expect(
    page.getByText("暗くなる道を、老爺を家まで送った"),
  ).toBeVisible();
  // the five the player didn't touch are one line until opened
  await expect(page.getByRole("heading", { name: "王" })).toBeHidden();
  // the page scrolls inside a fixed layer: a tall window to catch all of it for UX
  const size = page.viewportSize()!;
  await page.setViewportSize({ width: size.width, height: 2600 });
  await shot(page, "ending");
  await page.setViewportSize(size);

  await page.getByRole("button", { name: /\[1\]/ }).click();
  const map = page.getByRole("dialog", { name: "連鎖反応マップ" });
  await expect(map).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(map).toBeHidden();

  await page.getByRole("button", { name: "記憶帳", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "記憶帳" })).toBeVisible();
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "結末カード" }).click();
  const card = page.getByRole("img", { name: /市で待ち続けた旅人/ });
  await expect(card).toHaveAttribute("data-ready", "true");
  const png = await card.evaluate((c: HTMLCanvasElement) =>
    c.toDataURL("image/png"),
  );
  expect(png.startsWith("data:image/png;base64,")).toBe(true);
  expect(png.length).toBeGreaterThan(20_000);
  await card.screenshot({ path: "test-results/f12/ending-card.png" });
});

test("map: an event that kept a promise has the knot", async ({ page }) => {
  await mock(page, "scenario", { name: "limits" });
  await clockAt(page, 1170);
  // the mock has no kept promise: one commit, from between the page and the mock, says walking the old man home kept one
  let walkHome = "";
  await page.route(/\/timeline$/, async (route) => {
    const res = await route.fetch();
    const body = (await res.json()) as {
      days: { items: { eventId?: string; summary: string }[] }[];
    };
    walkHome =
      body.days[0]!.items.find((it) => it.summary.includes("老爺を家まで"))
        ?.eventId ?? "";
    await route.fulfill({ response: res, json: body });
  });
  let client: { send: (m: string) => void } | null = null;
  await page.routeWebSocket(/\/live$/, (ws) => {
    client = ws;
    const server = ws.connectToServer();
    ws.onMessage((m) => server.send(m));
    server.onMessage((m) => ws.send(m));
  });
  await startStory(page);
  await page.getByRole("button", { name: /^本をひらく/ }).click();
  await page
    .getByRole("button", { name: "連鎖反応マップ", exact: true })
    .click();
  const map = page.getByRole("dialog", { name: "連鎖反応マップ" });
  await expect(
    map.getByRole("button", { name: /老爺を家まで送った/ }),
  ).toBeVisible();
  expect(walkHome).not.toBe("");
  const last = Number(
    await page.locator(".world").getAttribute("data-last-seq"),
  );
  const seq = last + 1;
  client!.send(
    JSON.stringify({
      type: "commit",
      fromSeq: seq,
      seq,
      events: [
        {
          eventId: walkHome,
          seq,
          t: 1080,
          dt: 0,
          tLabel: "約束の日・日没前",
          type: "action",
          actor: "player",
          forPlayer: false,
          place: "place.syracuse-square",
          summary: "あなたは、老爺を家まで送った",
          causes: [],
          visibleEffects: [],
          promise: { promiseId: "prm_e2e_walk-home", change: "kept" },
          keyMoment: false,
          supersedes: null,
        },
      ],
      patch: {},
      memories: [],
      promises: [],
      narration: [],
      cue: null,
      reveal: null,
    }),
  );
  const node = map.getByRole("button", { name: /老爺を家まで送った/ });
  await expect(
    node.getByRole("img", { name: "約束が果たされた" }),
  ).toBeVisible();
  await shot(page, "map-kept");
  await node.screenshot({
    path: "test-results/f12/map-kept-node.png",
    scale: "device",
  });
});
