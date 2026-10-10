// World screen acceptance (F-2 card): the first screen is S7's 西南角 composition, the shadow line climbs the castle
// wall from 18:00 to 18:55, draw calls stay in budget, the follow camera keeps UX's framing (ux-design 6.3), walking
// into the execution ground tells the store once, shutting the workshop with the player inside doesn't trap them, and
// the console stays clean. Screenshots go to test-results/shots (CI uploads them for UX).
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { PNG } from "pngjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const budgets = JSON.parse(
  fs.readFileSync(path.join(here, "../../../../assets/budgets.json"), "utf8"),
) as {
  scene: { maxDrawCalls: number };
};
const SHOTS = path.join(here, "../../test-results/shots");

type Plan = [number, number, number];
type Hook = {
  load(): { stage: string; walkableMs: number; readyMs: number; error: string };
  frame(): { calls: number; triangles: number; frames: number };
  frames(n: number): Promise<void>;
  setClock(t: number): Promise<void>;
  setView(from: Plan | null, to?: Plan, fov?: number): Promise<void>;
  player(): { place: string; walking: boolean };
  moves(): string[];
  setPlaceEnabled(place: string, on: boolean): void;
  placeAt(spot: string): Promise<void>;
  follow(towards: [number, number]): Promise<void>;
  onScreen(): { playerPx: number; aheadPx: number; horizon: number };
  walkTo(to: string | [number, number]): void;
};
declare global {
  interface Window {
    __zoujin: Hook;
  }
}

test.describe.configure({ mode: "serial" });

let page: Page;
const problems: string[] = [];

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") problems.push(`console: ${m.text()}`);
  });
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("requestfailed", (r) => problems.push(`request failed: ${r.url()}`));
  fs.mkdirSync(SHOTS, { recursive: true });
  await page.goto("/?test");
  await page.waitForFunction(
    () => ["ready", "failed"].includes(window.__zoujin?.load().stage),
    null,
    { timeout: 240_000 },
  );
});

test.afterAll(async () => {
  await page.close();
});

async function shot(name: string): Promise<PNG> {
  await page.evaluate(() => window.__zoujin.frames(3));
  const buf = await page.screenshot({ path: path.join(SHOTS, `${name}.png`) });
  return PNG.sync.read(buf);
}

// mean sRGB of a rectangle given in fractions of the image
function mean(
  png: PNG,
  x0: number,
  y0: number,
  x1: number,
  y1: number,
): [number, number, number] {
  let r = 0;
  let g = 0;
  let b = 0;
  let n = 0;
  for (let y = Math.floor(y0 * png.height); y < y1 * png.height; y += 2)
    for (let x = Math.floor(x0 * png.width); x < x1 * png.width; x += 2) {
      const i = (y * png.width + x) * 4;
      r += png.data[i]!;
      g += png.data[i + 1]!;
      b += png.data[i + 2]!;
      n++;
    }
  return [r / n, g / n, b / n];
}

const lum = ([r, g, b]: [number, number, number]) =>
  0.2126 * r + 0.7152 * g + 0.0722 * b;

test("loads the plaza", async () => {
  const info = await page.evaluate(() => window.__zoujin.load());
  expect(info.error).toBe("");
  expect(info.stage).toBe("ready");
  console.log(
    `walkable ${info.walkableMs.toFixed(0)} ms, ready ${info.readyMs.toFixed(0)} ms (software rendering)`,
  );
});

test("first screen: S7's 西南角 composition at 17:30", async () => {
  const png = await shot("first-screen-1730");
  const sky = mean(png, 0.05, 0.02, 0.45, 0.25); // upper left: blue sky
  const castle = mean(png, 0.55, 0.4, 0.95, 0.6); // right middle: the sunlit castle
  const ground = mean(png, 0.4, 0.75, 0.95, 0.95); // the plaza floor
  expect(sky[2]).toBeGreaterThan(sky[0] + 40);
  expect(castle[0]).toBeGreaterThan(castle[2] + 40);
  expect(lum(castle)).toBeGreaterThan(lum(ground));
});

test("draw calls stay in budget", async () => {
  const { calls, triangles } = await page.evaluate(() =>
    window.__zoujin.frame(),
  );
  console.log(`draw calls ${calls}, triangles ${triangles}`);
  expect(calls).toBeGreaterThan(0);
  expect(calls).toBeLessThanOrEqual(budgets.scene.maxDrawCalls);
});

test("sunset: the shadow line climbs the castle wall", async () => {
  // S7's 王城 view; the band is a stretch of wall clear of the door and the post
  await page.evaluate(() =>
    window.__zoujin.setView([-10, -6, 1.65], [20, 2, 10], 60),
  );
  const tops: number[] = [];
  for (const t of [1080, 1110, 1135]) {
    await page.evaluate((tt) => window.__zoujin.setClock(tt), t);
    const png = await shot(`sunset-${t}`);
    const row = (y: number) =>
      lum(mean(png, 60 / 390, y / png.height, 140 / 390, (y + 1) / png.height));
    let ref = 0;
    for (let y = 300; y < 340; y++) ref += row(y) / 40;
    // first row below the lit upper wall that is clearly darker (two rows, so a mortar joint doesn't count)
    let top = png.height;
    for (let y = 340; y < 700; y++)
      if (row(y) < 0.75 * ref && row(y + 4) < 0.75 * ref) {
        top = y;
        break;
      }
    tops.push(top);
  }
  console.log(`shadow line rows at 18:00 / 18:30 / 18:55: ${tops.join(" / ")}`);
  expect(tops[1]!).toBeLessThan(tops[0]! - 40);
  expect(tops[2]!).toBeLessThan(tops[1]! - 40);
  await page.evaluate(() => window.__zoujin.setView(null));
  await page.evaluate(() => window.__zoujin.setClock(1050));
});

test("follow camera: UX's framing, towards the west gate and the castle", async () => {
  // plan points: the city gate and the castle door (layout.json way.road-to-city, way.castle). ground-west looks down
  // the light corridor (ux/slice/ending-shots.md, shot 2) along its own facing; it stands south of the stake, so the
  // stake isn't behind the player and the camera keeps its distance
  const views: [string, string, [number, number], number][] = [
    ["follow-west-gate", "ground-west", [-31, 0], 1050],
    ["follow-castle", "fountain-south", [18.3, 0], 1050],
    ["follow-west-gate-1845", "ground-west", [-31, 0], 1125],
  ];
  for (const [name, spot, towards, t] of views) {
    await page.evaluate((tt) => window.__zoujin.setClock(tt), t);
    await page.evaluate((s) => window.__zoujin.placeAt(s), spot);
    await page.evaluate((to) => window.__zoujin.follow(to), towards);
    const f = await page.evaluate(() => window.__zoujin.onScreen());
    console.log(
      `${name}: player ${f.playerPx.toFixed(0)} px, 15 m on ${f.aheadPx.toFixed(0)} px, horizon at ${f.horizon.toFixed(2)}`,
    );
    expect(f.playerPx).toBeGreaterThanOrEqual(100);
    expect(f.playerPx).toBeLessThanOrEqual(130);
    expect(f.aheadPx).toBeGreaterThanOrEqual(40);
    expect(f.aheadPx).toBeLessThanOrEqual(80);
    expect(f.horizon).toBeGreaterThan(0.25);
    expect(f.horizon).toBeLessThan(0.4);
    const png = await shot(name);
    // looking along the gate street the sky shows above the roofs
    if (name === "follow-west-gate") {
      const sky = mean(png, 0.3, 0.02, 0.7, 0.12);
      expect(lum(sky)).toBeGreaterThan(lum(mean(png, 0.3, 0.8, 0.7, 0.95)));
    }
  }
  await page.evaluate(() => window.__zoujin.setClock(1050));
});

test("walking into the execution ground moves the player there", async () => {
  // a few metres from the edge, so the walk is short even at software rendering's frame rate
  await page.evaluate(() => window.__zoujin.placeAt("fountain-south"));
  expect(await page.evaluate(() => window.__zoujin.player().place)).toBe(
    "place.syracuse-square",
  );
  await page.evaluate(() => window.__zoujin.walkTo("ground-west"));
  await expect
    .poll(() => page.evaluate(() => window.__zoujin.moves()), {
      timeout: 240_000,
      intervals: [2000],
    })
    .toContain("place.execution-ground");
  await expect
    .poll(() => page.evaluate(() => window.__zoujin.player().walking), {
      timeout: 120_000,
      intervals: [1000],
    })
    .toBe(false);
  // one crossing, one move: putting the player on a spot sends none, and the walk doesn't graze the edge twice
  expect(await page.evaluate(() => window.__zoujin.moves())).toEqual([
    "place.execution-ground",
  ]);
  await shot("walked-to-execution-ground");
});

test("shutting the workshop with the player inside doesn't trap them", async () => {
  await page.evaluate(() => window.__zoujin.placeAt("workshop-yard"));
  expect(await page.evaluate(() => window.__zoujin.player().place)).toBe(
    "place.stonemason-workshop",
  );
  await page.evaluate(() =>
    window.__zoujin.setPlaceEnabled("place.stonemason-workshop", false),
  );
  await page.evaluate(() => window.__zoujin.walkTo("workshop-gate"));
  await expect
    .poll(() => page.evaluate(() => window.__zoujin.player().place), {
      timeout: 240_000,
      intervals: [2000],
    })
    .toBe("place.syracuse-square");
  await expect
    .poll(() => page.evaluate(() => window.__zoujin.player().walking), {
      timeout: 120_000,
      intervals: [1000],
    })
    .toBe(false);
  // out in the square, the shut yard keeps them out: a tap inside walks to its edge
  await page.evaluate(() => window.__zoujin.walkTo("workshop-yard"));
  await expect
    .poll(() => page.evaluate(() => window.__zoujin.player().walking), {
      timeout: 240_000,
      intervals: [1000],
    })
    .toBe(false);
  expect(await page.evaluate(() => window.__zoujin.player().place)).toBe(
    "place.syracuse-square",
  );
  await page.evaluate(() =>
    window.__zoujin.setPlaceEnabled("place.stonemason-workshop", true),
  );
});

test("no console errors", () => {
  expect(problems).toEqual([]);
});
