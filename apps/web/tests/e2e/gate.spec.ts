// The M2-0 frontend gate round (F-1 card range 9, done with F-2d): the whole way through against B-1's mock with the
// plaza under the HUD. Invite code → role → the plaza (headless Chromium, software rendering) → a tap on the ground
// walks into the stonemason's yard (move goes out, the player's place follows) → a tap on メロス sends focus at once
// and walks up to him (near on the way) → holding the talk key sends the fake microphone (a WAV made here: voiced
// syllables, not words; the mock doesn't listen to the sound) → his subtitle → the commit's light reaction and the
// clock moving on → turn_settled. A screenshot at every step, and no console errors. Software rendering draws about a
// frame a second here and a walk advances at most 50 ms a frame, so the walks are short ones: the test hook puts the
// player outside the yard gate and later by the fountain, the way world.spec.ts does.
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { mock, ORIGIN, resetMock, startStory } from "./shell";

const here = path.dirname(fileURLToPath(import.meta.url));
const SHOTS = path.join(here, "../../test-results/shots");

// 3 s of something like speech at 48 kHz: 180 ms voiced syllables (a pulse train at 120–170 Hz through two formants)
// with short gaps. Chromium loops it as the microphone.
function speechWav(file: string): void {
  const rate = 48_000;
  const n = rate * 3;
  const pcm = new Int16Array(n);
  const formants = [
    [700, 1200],
    [400, 2000],
    [550, 900],
    [300, 2300],
  ] as const;
  let phase = 0;
  for (let i = 0; i < n; i++) {
    const t = i / rate;
    const syl = Math.floor(t / 0.24);
    const inSyl = t - syl * 0.24;
    if (inSyl > 0.18) continue;
    const f0 = 120 + 50 * Math.sin(syl * 1.7);
    phase += f0 / rate;
    const [f1, f2] = formants[syl % formants.length]!;
    let v = 0;
    for (let h = 1; h * f0 < 4000; h++) {
      const f = h * f0;
      const w =
        1 / (1 + ((f - f1) / 120) ** 2) + 0.5 / (1 + ((f - f2) / 160) ** 2);
      v += w * Math.sin(2 * Math.PI * h * phase);
    }
    const env = Math.sin((Math.PI * inSyl) / 0.18);
    pcm[i] = Math.max(-32767, Math.min(32767, v * env * 6000));
  }
  const head = Buffer.alloc(44);
  head.write("RIFF", 0);
  head.writeUInt32LE(36 + n * 2, 4);
  head.write("WAVEfmt ", 8);
  head.writeUInt32LE(16, 16);
  head.writeUInt16LE(1, 20); // PCM
  head.writeUInt16LE(1, 22); // mono
  head.writeUInt32LE(rate, 24);
  head.writeUInt32LE(rate * 2, 28);
  head.writeUInt16LE(2, 32);
  head.writeUInt16LE(16, 34);
  head.write("data", 36);
  head.writeUInt32LE(n * 2, 40);
  fs.writeFileSync(file, Buffer.concat([head, Buffer.from(pcm.buffer)]));
}

// made when the file loads, before the browser starts with it
const WAV = path.join(os.tmpdir(), "zoujin-gate-voice.wav");
speechWav(WAV);

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
      `--use-file-for-fake-audio-capture=${WAV}`,
      "--autoplay-policy=no-user-gesture-required",
    ],
  },
});

// window.__zoujin is typed in world.spec.ts; the parts this check uses
type Gate = {
  load(): { stage: string; error: string };
  player(): {
    place: string | null;
    walking: boolean;
    talking: string | null;
    near: string | null;
  };
  moves(): string[];
  clock(): number | null;
  placeAt(spot: string): Promise<void>;
  follow(towards: [number, number]): Promise<void>;
  tapPoint(to: string | [number, number]): [number, number] | null;
  tapCharacter(id: string): [number, number] | null;
};
type Msg = { type: string } & Record<string, unknown>;

const problems: string[] = [];
const PACK_VERSION = "0a1b2c3d";

async function shot(page: Page, name: string) {
  await page.screenshot({ path: path.join(SHOTS, `gate-${name}.png`) });
}

test("M2-0 gate: invite → role → plaza → walk (move) → tap メロス (focus) → talk by voice → commit → settled", async ({
  page,
  context,
}) => {
  fs.mkdirSync(SHOTS, { recursive: true });
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("console", (m) => {
    if (m.type() !== "error") return;
    if (m.location().url.includes("/assets/voice/")) return; // B-6's files aren't in git (f1.spec.ts)
    if (/status of 401 /.test(m.text())) return; // before login
    problems.push(`console: ${m.text()}`);
  });
  const up: Msg[] = [];
  const down: Msg[] = [];
  const mic = new Map<number, number>();
  page.on("websocket", (ws) => {
    if (!ws.url().includes("/live")) return;
    ws.on("framesent", (f) => {
      if (typeof f.payload === "string") up.push(JSON.parse(f.payload));
      else if (f.payload[0] === 0x01) {
        const seq = f.payload.readUInt32BE(1);
        mic.set(seq, (mic.get(seq) ?? 0) + 1);
      }
    });
    ws.on("framereceived", (f) => {
      if (typeof f.payload === "string") down.push(JSON.parse(f.payload));
    });
  });
  const sent = (type: string) => up.filter((m) => m.type === type);

  await page.addInitScript(() => {
    window.__zoujinTest = true;
    // the light reactions stay 6 s; a software-rendered frame can take longer than the wait for the voice to play
    // out, so every one shown is noted here and checked afterwards
    const seen: string[] = [];
    (window as unknown as { __toasts: string[] }).__toasts = seen;
    new MutationObserver(() => {
      for (const t of document.querySelectorAll("[data-testid=toast]"))
        if (!seen.includes(t.textContent ?? "")) seen.push(t.textContent ?? "");
    }).observe(document, { childList: true, subtree: true });
  });
  await context.grantPermissions(["microphone"], { origin: ORIGIN });
  await context.clearCookies();
  await resetMock(page);
  await mock(page, "scenario", { name: "full-turn" });
  // the pack comes from the manifest's assetUrl, shaped as B-7 makes it (version first, api-contract 2.1); the
  // fixture's is a placeholder, so it's set here. Every file of the pack then loads from under that address.
  await page.route("**/v1/books/*/manifest", async (route) => {
    const res = await route.fetch();
    const doc = (await res.json()) as {
      scenes: { sceneId: string; assetUrl: string }[];
    };
    for (const s of doc.scenes)
      if (s.sceneId === "scene.syracuse-square")
        s.assetUrl = `/scenes/${PACK_VERSION}/syracuse-square/scene.json`;
    await route.fulfill({ response: res, json: doc });
  });
  const packFiles: string[] = [];
  page.on("response", (r) => {
    const p = new URL(r.url()).pathname;
    if (p.startsWith("/scenes/")) packFiles.push(`${r.status()} ${p}`);
  });

  // 1. invite code, role, into the story: the plaza loads under the HUD
  await startStory(page);
  await page.waitForFunction(
    () => window.__zoujin?.load().stage === "ready",
    null,
    { timeout: 240_000 },
  );
  expect(packFiles).toContain(
    `200 /scenes/${PACK_VERSION}/syracuse-square/scene.json`,
  );
  expect(
    packFiles.filter(
      (f) => !f.startsWith(`200 /scenes/${PACK_VERSION}/syracuse-square/`),
    ),
  ).toEqual([]);
  expect(
    await page.evaluate(
      () => (window.__zoujin as unknown as Gate).player().place,
    ),
  ).toBe("place.syracuse-square");
  await shot(page, "1-plaza");

  // 2. outside the yard gate (still the square), a tap on the ground in the yard: the player walks in and move goes
  // out once
  await page.evaluate(() =>
    (window.__zoujin as unknown as Gate).placeAt("workshop-gate"),
  );
  await page.evaluate(() =>
    (window.__zoujin as unknown as Gate).follow([-14, -19]),
  );
  const yard = await page.evaluate(() =>
    (window.__zoujin as unknown as Gate).tapPoint("workshop-yard"),
  );
  expect(yard).not.toBeNull();
  await page.mouse.click(...yard!);
  await expect
    .poll(
      () =>
        page.evaluate(
          () => (window.__zoujin as unknown as Gate).player().place,
        ),
      {
        timeout: 240_000,
      },
    )
    .toBe("place.stonemason-workshop");
  expect(sent("action")).toEqual([
    expect.objectContaining({
      kind: "move",
      target: "place.stonemason-workshop",
    }),
  ]);
  await expect
    .poll(
      () =>
        page.evaluate(
          () => (window.__zoujin as unknown as Gate).player().walking,
        ),
      {
        timeout: 120_000,
      },
    )
    .toBe(false);
  await shot(page, "2-yard");

  // 3. (the walk across the plaza, skipped) by the fountain; a tap on メロス: focus at the tap, then he is walked up to
  await page.evaluate(() =>
    (window.__zoujin as unknown as Gate).placeAt("fountain-south"),
  );
  await page.evaluate(() =>
    (window.__zoujin as unknown as Gate).follow([4.3, 7.5]),
  );
  await expect
    .poll(
      () =>
        page.evaluate(() => (window.__zoujin as unknown as Gate).player().near),
      {
        timeout: 60_000,
      },
    )
    .toBe("char.melos"); // 6 m away: near (api-contract 3.2)
  expect(sent("near").at(-1)).toEqual({
    type: "near",
    character: "char.melos",
  });
  const melos = await page.evaluate(() =>
    (window.__zoujin as unknown as Gate).tapCharacter("char.melos"),
  );
  expect(melos).not.toBeNull();
  await page.mouse.click(...melos!);
  await expect.poll(() => sent("focus").length).toBe(1);
  expect(sent("focus")[0]).toEqual({ type: "focus", character: "char.melos" });
  await expect
    .poll(
      () =>
        page.evaluate(
          () => (window.__zoujin as unknown as Gate).player().talking,
        ),
      {
        timeout: 240_000,
      },
    )
    .toBe("char.melos");
  await expect(page.locator(".world")).toHaveAttribute("data-voice", "idle");
  await shot(page, "3-melos");

  // 4. hold the talk key: the fake microphone goes up with this turn's number
  const key = page.getByTestId("talk");
  await expect(key).toBeEnabled();
  const box = (await key.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await expect(page.locator(".world")).toHaveAttribute(
    "data-voice",
    "listening",
  );
  await shot(page, "4-talking");
  await page.waitForTimeout(1500);
  await page.mouse.up();
  const start = sent("activity_start")[0]!;
  expect(start.turnSeq).toBe(1);
  expect(mic.get(1) ?? 0).toBeGreaterThanOrEqual(15);

  // 5. his words with his voice
  await expect(page.getByTestId("sub-player")).toContainText(
    "この市の王は、人を殺しているそうです。",
  );
  await expect(page.getByTestId("sub-character")).toContainText(
    "……なんだと。そんな王を、許しておけるものか。",
    { timeout: 60_000 },
  );
  await shot(page, "5-answer");

  // 6. the commit: the light reaction, the clock 10 minutes on; then turn_settled and the key is free again
  await expect(page.locator(".world")).toHaveAttribute("data-last-seq", "1", {
    timeout: 60_000,
  });
  expect(
    await page.evaluate(
      () => (window as unknown as { __toasts: string[] }).__toasts,
    ),
  ).toContainEqual(expect.stringContaining("メロスは覚えた"));
  expect(
    await page.evaluate(() => (window.__zoujin as unknown as Gate).clock()),
  ).toBe(1060);
  await shot(page, "6-commit");
  await expect
    .poll(() => down.filter((m) => m.type === "turn_settled").length)
    .toBe(1);
  await expect(page.locator(".world")).toHaveAttribute("data-voice", "idle");
  await shot(page, "7-settled");

  expect(
    await page.evaluate(() => (window.__zoujin as unknown as Gate).moves()),
    "only the walk into the yard is a move",
  ).toEqual(["place.stonemason-workshop"]);
  expect(problems).toEqual([]);
});
