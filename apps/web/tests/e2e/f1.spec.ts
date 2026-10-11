// The voice against B-1's mock (F-1 card): Chromium's fake microphone and the mock's synthetic voice. A turn by voice
// (the primer first, frames going up with the turn's number), interrupting (the voice silent within 50 ms of the
// press), 取り消す and the waiting ladder, 言い直す, too late and a correction, the safety note and card, degraded,
// and a refused microphone. The prerecorded lines the manifest names aren't there yet (B-6 files are not in git): their
// 404s are expected.
import { expect, test, type Page, type WebSocketRoute } from "@playwright/test";
import {
  login,
  mock,
  ORIGIN,
  resetMock,
  startStory,
  talkTo,
  without3d,
} from "./shell";

const BASE_ARGS = [
  "--use-angle=swiftshader",
  "--enable-unsafe-swiftshader",
  "--ignore-gpu-blocklist",
];
// Chromium's fake microphone (a tone) and its prompt answered yes; sound may start without a tap
test.use({
  launchOptions: {
    ...(process.env.PW_CHROMIUM
      ? { executablePath: process.env.PW_CHROMIUM }
      : {}),
    args: [
      ...BASE_ARGS,
      "--use-fake-device-for-media-stream",
      "--use-fake-ui-for-media-stream",
      "--autoplay-policy=no-user-gesture-required",
    ],
  },
});

type Up = { type: string } & Record<string, unknown>;

declare global {
  interface Window {
    __zoujinTest?: boolean;
    __zoujinAudio?: { lastFlushMs: number | null };
  }
}

const problems: string[] = [];

// what goes over the playthrough's socket: the JSON messages each way and how many microphone frames, per turnSeq
function watch(page: Page) {
  const up = {
    json: [] as Up[],
    down: [] as Up[],
    mic: new Map<number, number>(),
  };
  page.on("websocket", (ws) => {
    if (!ws.url().includes("/live")) return;
    ws.on("framesent", (f) => {
      if (typeof f.payload === "string") up.json.push(JSON.parse(f.payload));
      else if (f.payload[0] === 0x01) {
        const seq = f.payload.readUInt32BE(1);
        up.mic.set(seq, (up.mic.get(seq) ?? 0) + 1);
      }
    });
    ws.on("framereceived", (f) => {
      if (typeof f.payload === "string") up.down.push(JSON.parse(f.payload));
    });
  });
  return up;
}

const sent = (up: { json: Up[] }, type: string) =>
  up.json.filter((m) => m.type === type);

// the finger on the talk key; the returned function lifts it
async function press(page: Page): Promise<() => Promise<void>> {
  const key = page.getByTestId("talk");
  await expect(key).toBeEnabled();
  const box = (await key.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  return () => page.mouse.up();
}

async function hold(page: Page, ms: number) {
  const lift = await press(page);
  await page.waitForTimeout(ms);
  await lift();
}

const flushMs = (page: Page) =>
  page.evaluate(() => window.__zoujinAudio!.lastFlushMs);

const voice = (page: Page) => page.locator(".world");

// with the fake prompt Chromium says the microphone is allowed from the start; a player's first visit says "prompt"
// (and deny: they then say no in the browser's prompt)
async function firstVisit(page: Page, deny = false) {
  await page.addInitScript((deny) => {
    const query = navigator.permissions.query.bind(navigator.permissions);
    navigator.permissions.query = (d) =>
      d.name === ("microphone" as PermissionName)
        ? Promise.resolve({ state: "prompt" } as PermissionStatus)
        : query(d);
    if (deny)
      navigator.mediaDevices.getUserMedia = () =>
        Promise.reject(
          new DOMException("Permission denied", "NotAllowedError"),
        );
  }, deny);
}

test.beforeEach(async ({ page, context }) => {
  problems.length = 0;
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("console", (m) => {
    if (m.type() !== "error") return;
    const voiceFile = m.location().url.includes("/assets/voice/");
    if (
      voiceFile ||
      /WebSocket connection to .* failed|status of 401 /.test(m.text())
    )
      return;
    problems.push(`console: ${m.text()}`);
  });
  await page.addInitScript(() => {
    window.__zoujinTest = true;
  });
  await without3d(context);
  await context.clearCookies();
  await resetMock(page);
});

test.afterEach(() => {
  expect(problems).toEqual([]);
});

test.describe("with a microphone", () => {
  test("a voice turn: the primer once, frames up with the turn's number, the answer's words with its voice", async ({
    page,
  }) => {
    const up = watch(page);
    await firstVisit(page);
    await mock(page, "scenario", { name: "full-turn" });
    await startStory(page);
    await talkTo(page, "メロス");
    await expect(voice(page)).toHaveAttribute("data-voice", "mic-unknown");

    // the first press opens the primer and doesn't record
    await hold(page, 300);
    const primer = page.getByRole("dialog", { name: "声で話しかけますか" });
    await expect(primer).toBeVisible();
    expect(sent(up, "activity_start")).toHaveLength(0);
    await primer.getByRole("button", { name: "マイクを使う" }).click();
    await expect(
      page.getByText("準備ができました。ボタンを押しながら、話してください。"),
    ).toBeVisible();
    await expect(voice(page)).toHaveAttribute("data-voice", "idle");

    await hold(page, 1500);
    await expect(page.getByTestId("sub-player")).toContainText(
      "この市の王は、人を殺しているそうです。",
    );
    const start = sent(up, "activity_start")[0]!;
    expect(start.turnSeq).toBe(1);
    expect(sent(up, "activity_end")[0]).toMatchObject({
      turnId: start.turnId,
      turnSeq: 1,
    });
    // 1.5 s of 40 ms frames, all with this turn's number, none after the release
    expect(up.mic.get(1) ?? 0).toBeGreaterThanOrEqual(20);
    expect(up.mic.get(1) ?? 0).toBeLessThanOrEqual(45);

    await expect(voice(page)).toHaveAttribute("data-voice", "speaking");
    await expect(page.getByTestId("sub-character")).toContainText(
      "……なんだと。そんな王を、許しておけるものか。",
    );
    await expect(voice(page)).toHaveAttribute("data-voice", "idle");
    await expect(
      page.getByRole("button", { name: "どうするつもりですか" }),
    ).toBeVisible();
    await expect(page.locator(".world")).toHaveAttribute("data-last-seq", "1");
  });

  test("interrupting while the server still sends: silent within 50 ms of the press, the line breaks with 「——」", async ({
    page,
    context,
  }) => {
    await context.grantPermissions(["microphone"], { origin: ORIGIN });
    const up = watch(page);
    await mock(page, "scenario", { name: "interrupt" });
    await startStory(page);
    await talkTo(page, "メロス");
    await expect(voice(page)).toHaveAttribute("data-voice", "idle"); // allowed already: no primer
    await hold(page, 1200);
    await expect(voice(page)).toHaveAttribute("data-voice", "speaking");
    await expect(page.getByTestId("sub-character")).toContainText("いかにも");

    const lift = await press(page); // over the character
    await expect(voice(page)).toHaveAttribute("data-voice", "listening");
    await expect.poll(() => flushMs(page)).not.toBeNull();
    expect((await flushMs(page))!).toBeLessThanOrEqual(50);
    await expect(page.getByTestId("sub-character")).toContainText(/——$/);
    // the server was still sending: it confirms the interruption and stops
    await expect
      .poll(() => up.down.filter((m) => m.type === "interrupted").length)
      .toBe(1);
    await page.waitForTimeout(1000);
    await lift();
    await expect(page.getByTestId("sub-player")).toContainText(
      "待ってください。",
    );
    await expect(page.getByTestId("sub-character")).toContainText(
      "……なんだ。言いたいことがあるなら、言え。",
    );
    expect(sent(up, "activity_start").map((m) => m.turnSeq)).toEqual([1, 2]);
  });

  test("interrupting after the server finished while the phone still plays: the same", async ({
    page,
    context,
  }) => {
    await context.grantPermissions(["microphone"], { origin: ORIGIN });
    const up = watch(page);
    await mock(page, "scenario", { name: "full-turn" });
    await startStory(page);
    await talkTo(page, "メロス");
    await expect(voice(page)).toHaveAttribute("data-voice", "idle");
    await hold(page, 1000);
    // turn_complete is in (言い直す shows from then) and the voice still plays
    await expect(page.getByRole("button", { name: "言い直す" })).toBeVisible();
    await expect(voice(page)).toHaveAttribute("data-voice", "speaking");
    expect(up.down.some((m) => m.type === "turn_complete")).toBe(true);

    const lift = await press(page);
    await expect.poll(() => flushMs(page)).not.toBeNull();
    expect((await flushMs(page))!).toBeLessThanOrEqual(50);
    await expect(page.getByTestId("sub-character")).toContainText(/——$/);
    await lift();
    expect(up.down.filter((m) => m.type === "interrupted")).toHaveLength(0);
  });

  test("the safety card while the key is held: the frames stop, nothing more goes, back to talking", async ({
    page,
    context,
  }) => {
    await context.grantPermissions(["microphone"], { origin: ORIGIN });
    const up = watch(page);
    // the mock pauses only after a turn; here the pause comes mid-press, from between the page and the mock
    let client: WebSocketRoute | null = null;
    await page.routeWebSocket(/\/live$/, (ws) => {
      client = ws;
      const server = ws.connectToServer();
      ws.onMessage((m) => {
        if (typeof m === "string" && m.includes('"safety_resume"'))
          ws.send(JSON.stringify({ type: "safety_resumed" }));
        else server.send(m);
      });
      server.onMessage((m) => ws.send(m));
    });
    await mock(page, "scenario", { name: "limits" });
    await startStory(page);
    await talkTo(page, "メロス");
    await expect(voice(page)).toHaveAttribute("data-voice", "idle");

    const lift = await press(page);
    await expect(voice(page)).toHaveAttribute("data-voice", "listening");
    await page.waitForTimeout(600);
    client!.send(JSON.stringify({ type: "safety_pause" }));
    const card = page.getByRole("dialog", {
      name: "いま、つらい気持ちを抱えていませんか。",
    });
    await expect(card).toBeVisible();
    const frames = up.mic.get(1) ?? 0;
    expect(frames).toBeGreaterThan(5);
    await page.waitForTimeout(600);
    await lift();
    expect(up.mic.get(1) ?? 0).toBe(frames);
    expect(sent(up, "activity_end")).toHaveLength(0);
    await expect(page.getByTestId("talk")).toBeDisabled();

    await card.getByRole("button", { name: "物語に戻る" }).click();
    await expect(card).toHaveCount(0);
    await expect.poll(() => sent(up, "focus").length).toBe(2);
    await expect(voice(page)).toHaveAttribute("data-voice", "idle");
    await hold(page, 800); // a new turn, a new number
    await expect
      .poll(() => sent(up, "activity_start").map((m) => m.turnSeq))
      .toEqual([1, 2]);
  });

  test("after a drop the key comes back ready", async ({ page, context }) => {
    await context.grantPermissions(["microphone"], { origin: ORIGIN });
    await mock(page, "scenario", { name: "full-turn" });
    await startStory(page);
    await talkTo(page, "メロス");
    await expect(voice(page)).toHaveAttribute("data-voice", "idle");
    await context.setOffline(true);
    await mock(page, "drop");
    await expect(page.getByTestId("talk")).toHaveText("つながり直しています");
    await expect(page.getByTestId("talk")).toBeDisabled();
    await context.setOffline(false);
    await expect(voice(page)).toHaveAttribute("data-voice", "idle", {
      timeout: 15_000,
    });
    await expect(page.getByTestId("talk")).toHaveText("押して話す");
  });

  test("言い直す in time; too late says so; tapping my own words corrects them", async ({
    page,
    context,
  }) => {
    await context.grantPermissions(["microphone"], { origin: ORIGIN });
    // between the page and the mock: hold the server's turn_settled back when asked (the retract and the settle cross)
    const up: Up[] = [];
    let holdSettled = false;
    const held: string[] = [];
    let client: WebSocketRoute | null = null;
    await page.routeWebSocket(/\/live$/, (ws) => {
      client = ws;
      const server = ws.connectToServer();
      ws.onMessage((m) => {
        if (typeof m === "string") up.push(JSON.parse(m));
        server.send(m);
      });
      server.onMessage((m) => {
        if (
          holdSettled &&
          typeof m === "string" &&
          m.includes('"turn_settled"')
        )
          held.push(m);
        else ws.send(m);
      });
    });
    await mock(page, "scenario", { name: "retract" });
    await startStory(page);
    await talkTo(page, "市の老爺");
    await expect(voice(page)).toHaveAttribute("data-voice", "idle");

    // 1. 言い直す while the answer can still be taken back
    await hold(page, 1000);
    const redo = page.getByRole("button", { name: "言い直す" });
    await redo.click();
    await expect(page.getByTestId("sub-player").locator("s")).toContainText(
      "王様のことを、聞いてもいいですか。",
    );
    await expect(page.getByTestId("sub-character")).toHaveCount(0);
    await expect(voice(page)).toHaveAttribute("data-voice", "idle");

    // 2. the turn was already settled when 言い直す went: the narrator says so
    holdSettled = true;
    await hold(page, 1000);
    await expect(redo).toBeVisible();
    await expect.poll(() => held.length).toBe(1);
    await redo.click();
    await expect(page.getByTestId("narration")).toHaveText(
      "……もう伝わってしまった。",
    );
    holdSettled = false;
    for (const m of held.splice(0)) client!.send(m);
    await expect(voice(page)).toHaveAttribute("data-voice", "idle");

    // 3. the words were heard wrong: tap them, fix them, send
    await hold(page, 1000);
    const mine = page.getByTestId("sub-player").getByRole("button");
    await expect(mine).toHaveText("往生は、どっちですか。");
    await mine.click();
    const field = page.getByLabel("言いたいことを書く");
    await expect(field).toHaveValue("往生は、どっちですか。");
    await field.fill("王城は、どっちですか。");
    await page.getByRole("button", { name: "送る" }).click();
    await expect(page.getByTestId("sub-character")).toContainText(
      "王城なら、あの坂の上じゃ。",
    );
    const third = up.filter((m) => m.type === "activity_start")[2]!;
    const retracts = up.filter((m) => m.type === "turn_retract");
    expect(retracts.at(-1)).toMatchObject({ turnId: third.turnId });
    expect(up.filter((m) => m.type === "text").at(-1)).toMatchObject({
      text: "王城は、どっちですか。",
      via: "correction",
      replaces: third.turnId,
    });
  });

  test("safety: the quiet note while the character goes on, then the card, then back to the story", async ({
    page,
    context,
  }) => {
    await context.grantPermissions(["microphone"], { origin: ORIGIN });
    const up = watch(page);
    await mock(page, "scenario", { name: "safety" });
    await startStory(page);
    await talkTo(page, "市の老爺");
    await expect(voice(page)).toHaveAttribute("data-voice", "idle");

    // the note: no pause, the old man finishes his line
    await hold(page, 1000);
    const note = page.getByRole("status").filter({
      hasText: "つらいときは、話を聞いてくれる窓口があります。",
    });
    await expect(note).toBeVisible();
    await expect(page.getByTestId("sub-character")).toContainText(
      "……疲れたかね。少し、そこの石に腰を下ろしなされ。",
    );
    await note.getByRole("button", { name: /窓口を見る/ }).click();
    const panel = page.getByRole("dialog", { name: "話を聞いてくれる窓口" });
    await expect(panel).toBeVisible();
    await expect(panel.getByRole("link", { name: "電話する" })).toHaveAttribute(
      "href",
      "tel:0120061338",
    );
    await expect(panel.getByText("0120-061-338")).toBeVisible();
    await panel.getByRole("button", { name: "物語に戻る" }).click();
    await expect(panel).toHaveCount(0);
    await expect(note).toHaveCount(0);
    await expect(page.getByTestId("sub-character")).toContainText(
      "腰を下ろしなされ。",
    );
    await expect(voice(page)).toHaveAttribute("data-voice", "idle");

    // the card: the lines go in the dark, the focus is on the card, nothing behind it takes a tap
    await hold(page, 1000);
    const card = page.getByRole("dialog", {
      name: "いま、つらい気持ちを抱えていませんか。",
    });
    await expect(card).toBeVisible();
    await expect(card).toBeFocused();
    await expect(voice(page)).toHaveAttribute("data-voice", "paused");
    await expect(page.getByTestId("sub-player")).toHaveCount(0);
    await expect(page.getByTestId("sub-character")).toHaveCount(0);
    await expect(card.getByRole("link")).toHaveCount(3);
    await card.getByRole("button", { name: "物語に戻る" }).click();
    await expect(card).toHaveCount(0);
    expect(sent(up, "safety_resume")).toHaveLength(1);
    // safety_resumed → focus again → the session is rebuilt
    await expect.poll(() => sent(up, "focus").length).toBe(2);
    await expect(voice(page)).toHaveAttribute("data-voice", "idle");
    await expect(
      page.getByTestId("sub-character").getByText("……疲れたかね。", {
        exact: false,
      }),
    ).toBeVisible();
  });
});

test.describe("by text", () => {
  test("取り消す before an answer; the chips at 6 s; given up at 12 s", async ({
    page,
  }) => {
    const up = watch(page);
    await mock(page, "scenario", { name: "limits" }); // never answers a turn
    await startStory(page);
    await talkTo(page, "メロス");
    const say = async (text: string) => {
      await page.getByRole("button", { name: "文字で話す" }).click();
      await page.getByLabel("言いたいことを書く").fill(text);
      await page.getByRole("button", { name: "送る" }).click();
    };

    await say("やっぱり");
    await page.getByRole("button", { name: "取り消す" }).click();
    await expect(page.getByTestId("sub-player").locator("s")).toHaveText(
      "やっぱり",
    );
    expect(sent(up, "turn_retract")[0]).toMatchObject({
      turnId: sent(up, "text")[0]!.turnId,
    });

    await say("聞こえますか");
    const sentAt = Date.now();
    await expect(
      page.getByRole("button", { name: "もう一度話す" }),
    ).toBeVisible({ timeout: 8000 });
    expect(Date.now() - sentAt).toBeGreaterThanOrEqual(5500);
    await expect(
      page.getByRole("button", { name: "文字で送る" }),
    ).toBeVisible();
    await expect
      .poll(() => sent(up, "turn_retract").length, { timeout: 10_000 })
      .toBe(2);
    expect(Date.now() - sentAt).toBeGreaterThanOrEqual(11_500);
    expect(sent(up, "turn_retract")[1]).toMatchObject({
      turnId: sent(up, "text")[1]!.turnId,
    });
  });

  test("degraded: the narrator says so, the text field takes the key's place, the answer comes in words", async ({
    page,
  }) => {
    await mock(page, "scenario", { name: "degraded" });
    await startStory(page);
    await talkTo(page, "市の老爺");
    await expect(page.getByTestId("narration")).toHaveText(
      "ここからは文字でお話しください。人物のことばは字幕で表示します。",
    );
    await expect(voice(page)).toHaveAttribute("data-voice", "degraded");
    await expect(page.getByTestId("talk")).toHaveCount(0);
    await page.getByLabel("言いたいことを書く").fill("どこへ行けば？");
    await page.getByRole("button", { name: "送る" }).click();
    await expect(page.getByTestId("sub-character")).toContainText(
      "……日が沈む前に、刑場へ行ってみなされ。",
    );
    await expect(
      page.getByRole("button", { name: "刑場で何が？" }),
    ).toBeVisible();
  });
});

test.describe("a refused microphone", () => {
  test("the sheet says text goes all the way; text it is", async ({ page }) => {
    await firstVisit(page, true);
    await mock(page, "scenario", { name: "full-turn" });
    await startStory(page);
    await talkTo(page, "メロス");
    await hold(page, 300);
    await page.getByRole("button", { name: "マイクを使う" }).click();
    const sheet = page.getByRole("alertdialog");
    await expect(sheet).toContainText(
      "マイクが使えません。文字で話しても、物語は最後まで進みます。",
    );
    await sheet.getByRole("button", { name: "設定のしかた" }).click();
    await expect(sheet).toContainText("Android");
    await sheet.getByRole("button", { name: "文字で続ける" }).click();
    await expect(sheet).toHaveCount(0);
    await expect(voice(page)).toHaveAttribute("data-voice", "denied");
    await page.getByLabel("言いたいことを書く").fill("こんにちは");
    await page.getByRole("button", { name: "送る" }).click();
    await expect(page.getByTestId("sub-character")).toContainText(
      "許しておけるものか。",
    );
  });
});

test.describe("LINE's browser", () => {
  test.use({
    userAgent:
      "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Safari Line/14.16.0",
  });
  test("the cover says the voice may not work here; このまま文字で遊ぶ starts with the keyboard", async ({
    page,
  }) => {
    await mock(page, "scenario", { name: "full-turn" });
    await page.goto("/");
    await login(page);
    const note = page.getByRole("note");
    await expect(note).toHaveText(
      /LINEの中のブラウザでは、声で話せないことがあります。/,
    );
    await note.getByRole("button", { name: "このまま文字で遊ぶ" }).click();
    await expect(note).toHaveCount(0);
    await page.getByRole("button", { name: "書をひらく" }).click();
    await page.getByRole("button", { name: "旅人として、はじめる" }).click();
    await expect(page.getByText("人に近づくと話せます")).toBeVisible();
    await talkTo(page, "メロス");
    await expect(page.getByTestId("talk")).toHaveCount(0);
    await page.getByLabel("言いたいことを書く").fill("こんにちは");
    await page.getByRole("button", { name: "送る" }).click();
    await expect(page.getByTestId("sub-character")).toContainText(
      "許しておけるものか。",
    );
    // the choice stays on this device: the next visit has no note
    await page.goto("/");
    await expect(page.getByRole("button", { name: "続きから" })).toBeVisible();
    await expect(page.getByRole("note")).toHaveCount(0);
  });
});

test.describe("text from the start", () => {
  // the player chose 文字で話す before (kept on this device): the text field takes the key's place
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() =>
      localStorage.setItem("zj.voice", JSON.stringify({ text: true })),
    );
  });
  const say = async (page: Page, text: string) => {
    await page.getByLabel("言いたいことを書く").fill(text);
    await page.getByRole("button", { name: "送る" }).click();
  };

  test.describe("landscape", () => {
    test.use({ viewport: { width: 844, height: 390 } });
    test("the quiet note shows beside the text field", async ({ page }) => {
      await mock(page, "scenario", { name: "safety" });
      await startStory(page);
      await talkTo(page, "市の老爺");
      await expect(page.getByTestId("talk")).toHaveCount(0);
      await say(page, "もう、ここで終わりにしたい。");
      const note = page
        .getByRole("status")
        .filter({ hasText: "つらいときの相談窓口" });
      await expect(note).toBeVisible();
      await note.getByRole("button", { name: "つらいときの相談窓口" }).click();
      await expect(
        page.getByRole("dialog", { name: "話を聞いてくれる窓口" }),
      ).toBeVisible();
    });
  });

  test("the safety card is still there after a reload, and 物語に戻る still works", async ({
    page,
  }) => {
    await mock(page, "scenario", { name: "safety" });
    await startStory(page);
    await talkTo(page, "市の老爺");
    await say(page, "もう、ここで終わりにしたい。");
    await expect(page.getByTestId("sub-character")).toContainText(
      "腰を下ろしなされ。",
    );
    await say(page, "もう、ここで終わりにしたい。");
    const card = page.getByRole("dialog", {
      name: "いま、つらい気持ちを抱えていませんか。",
    });
    await expect(card).toBeVisible();

    await page.reload(); // the welcome says the pause still holds
    await expect(card).toBeVisible();
    await expect(voice(page)).toHaveAttribute("data-voice", "paused");
    await card.getByRole("button", { name: "物語に戻る" }).click();
    await expect(card).toHaveCount(0);
    await expect(page.getByText("人に近づくと話せます")).toBeVisible();
  });
});
