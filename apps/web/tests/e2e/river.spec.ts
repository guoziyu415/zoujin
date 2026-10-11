// The road's river (F-10 card acceptance) on the test page: each act loads its own pack through scene.road-river's
// index, the shared roadside textures come from road-common, no direct sun in the valley at 05:15 but at 05:45 (the
// east ridge), draw calls in budget, a clean console. Screenshots for UX go to test-results/shots: act 4 from road-west
// looking east and south (the backlit waves), act 2 from road-east looking west (no stand-in figure: UX round 3) and
// from the deck downstream, the act 2 sky both ways (drawn as at −1.5°, or the landing moved to 04:55); act 4 also
// looking upstream at the shallows' boulders and at the willow from road-west. Skipped without a road build (assets/pipeline/road).
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { sceneDir } from "../../scene-dir";

const here = path.dirname(fileURLToPath(import.meta.url));
const budgets = JSON.parse(
  fs.readFileSync(path.join(here, "../../../../assets/budgets.json"), "utf8"),
) as { scene: { maxDrawCalls: number } };
const SHOTS = path.join(here, "../../test-results/shots");
const built = ["road-river-calm", "road-river-flood"].every((p) =>
  fs.existsSync(path.join(sceneDir(p), "nav.json")),
);

type Plan = [number, number, number];
type Hook = {
  load(): { stage: string; bytes: number; error: string };
  frame(): { calls: number; triangles: number };
  frames(n: number): Promise<void>;
  setClock(t: number): Promise<void>;
  setView(from: Plan | null, to?: Plan, fov?: number): Promise<void>;
  direct(): number;
  skyElev(deg?: number): Promise<void>;
};
type W = { __zoujin: Hook };

test.describe.configure({ mode: "serial" });
test.skip(!built, "no road build (assets/pipeline/road/build.sh)");

async function open(page: Page, act: string, t: number): Promise<string[]> {
  const problems: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") problems.push(`console: ${m.text()}`);
  });
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("requestfailed", (r) => problems.push(`request failed: ${r.url()}`));
  fs.mkdirSync(SHOTS, { recursive: true });
  await page.goto(`/?world&test&scene=road-river&act=${act}&t=${t}`);
  await page.waitForFunction(
    () =>
      ["ready", "failed"].includes(
        (window as unknown as Partial<W>).__zoujin?.load().stage ?? "",
      ),
    null,
    { timeout: 240_000 },
  );
  const info = await page.evaluate(() =>
    (window as unknown as W).__zoujin.load(),
  );
  expect(info.stage, info.error).toBe("ready");
  return problems;
}

const direct = (page: Page) =>
  page.evaluate(() => (window as unknown as W).__zoujin.direct());
const setClock = (page: Page, t: number) =>
  page.evaluate((tt) => (window as unknown as W).__zoujin.setClock(tt), t);
const skyElev = (page: Page, deg?: number) =>
  page.evaluate((d) => (window as unknown as W).__zoujin.skyElev(d), deg);

async function shot(page: Page, name: string, from: Plan, to: Plan, fov = 60) {
  await page.evaluate(
    ([f, t, v]) => (window as unknown as W).__zoujin.setView(f, t, v),
    [from, to, fov] as const,
  );
  await page.evaluate(() => (window as unknown as W).__zoujin.frames(3));
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`) });
  const { calls } = await page.evaluate(() =>
    (window as unknown as W).__zoujin.frame(),
  );
  console.log(`${name}: draw calls ${calls}`);
  expect(calls).toBeLessThanOrEqual(budgets.scene.maxDrawCalls);
}

test("act 4: the flood pack, from road-west", async ({ page }) => {
  const problems = await open(page, "act.4", 705);
  const urls = await page.evaluate(() =>
    performance.getEntriesByType("resource").map((e) => e.name),
  );
  expect(urls.some((u) => u.includes("/scenes/road-river-flood/"))).toBe(true);
  expect(urls.some((u) => u.includes("/scenes/road-river-calm/"))).toBe(false);
  expect(urls.some((u) => u.includes("/scenes/road-common/"))).toBe(true);
  // 11:45: the sun high in the south, direct light on
  expect(await direct(page)).toBeGreaterThan(1);
  await shot(page, "river-act4-east", [-15, 0, 1.65], [20, 1, 1]);
  await shot(page, "river-act4-south", [-5.8, 0.5, 1.3], [4, -40, -1.5]);
  // the shallows upstream (aff.river-shallows): slack water and the boulders' tops in a line across; the rain cloud
  await shot(page, "river-act4-north", [-6, 0.8, 1.65], [3, 16, 0.5]);
  // the willow Melos gets hold of (swim-out, beat.18), leaning out over the flood
  await shot(page, "river-act4-willow", [-16, -1, 1.65], [11, -13, 2.5], 40);
  expect(problems).toEqual([]);
});

test("act 2: the calm pack from road-east; the ridge holds the sun back", async ({
  page,
}) => {
  const problems = await open(page, "act.2", 315);
  // 05:15: the sun 2.8° up, behind the 7° ridge: no direct light; at 05:45 it has cleared it
  expect(await direct(page)).toBe(0);
  const west: [Plan, Plan] = [
    [17, -0.5, 1.65],
    [-20, 0, 1],
  ];
  await shot(page, "river-act2-west", ...west);
  // the river itself hardly shows from the landing: from the deck, downstream, the mirror and the mist on it
  await shot(page, "river-act2-bridge-south", [3, 1, 1.65], [3, -30, -2.5]);
  // the two skies for UX to choose from (F-10 card 5): drawn as at −1.5°, or the landing moved to 04:55
  await skyElev(page, -1.5);
  await shot(page, "river-act2-west-sky-minus1.5", ...west);
  await skyElev(page, undefined);
  await setClock(page, 295);
  await shot(page, "river-act2-west-0455", ...west);
  await setClock(page, 345);
  expect(await direct(page)).toBeGreaterThan(1);
  await shot(page, "river-act2-west-0545", ...west);
  expect(problems).toEqual([]);
});
