// The crowd (F-4 acceptance): twenty people on the execution ground at
// 18:50, seen from behind them towards the post; three draw calls more (their shadow aside, budget 8); nobody sways in
// step; どよめき from the scaffold outwards, the cheer, making way for the king; the console stays clean. Screenshots go
// to test-results/shots for UX. The bodies are MPFB's when the built scene has its crowd pack (crowd/, assets/pipeline/
// crowd/build.sh), the stand-ins otherwise.
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { sceneDir } from "../../scene-dir.ts";

const here = path.dirname(fileURLToPath(import.meta.url));
const SHOTS = path.join(here, "../../test-results/shots");
const PACK = fs.existsSync(
  path.join(sceneDir("syracuse-square"), "crowd/crowd.json"),
);

type Vec3 = [number, number, number];
type CrowdInfo = {
  count: number;
  meshes: number;
  clips: string[];
  started: Record<string, number>;
  at: [number, number][];
  pack: boolean;
};
type Hook = {
  load(): { stage: string; error: string; spots: Record<string, Vec3> };
  frame(): { calls: number; triangles: number; frames: number };
  frames(n: number): Promise<void>;
  setClock(t: number): Promise<void>;
  setWorldView(from: Vec3, to: Vec3, fov?: number): Promise<void>;
  crowd(
    verb?: "wave" | "cheer" | "part" | "show" | "hide",
    arg?: [number, number] | [number, number][],
  ): Promise<CrowdInfo | null>;
};
test.describe.configure({ mode: "serial" });

let page: Page;
const problems: string[] = [];
// a hook call with no arguments from this side: the function's source runs in the page against window.__zoujin
let call: <T>(f: (h: Hook) => T | Promise<T>) => Promise<T>;

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") problems.push(`console: ${m.text()}`);
  });
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  fs.mkdirSync(SHOTS, { recursive: true });
  await page.goto("/?world&test&crowd=20");
  await page.waitForFunction(
    () =>
      ["ready", "failed"].includes(
        (window as unknown as { __zoujin?: Hook }).__zoujin?.load().stage ?? "",
      ),
    null,
    { timeout: 240_000 },
  );
  call = <T>(f: (h: Hook) => T | Promise<T>) =>
    page.evaluate(`(${f.toString()})(window.__zoujin)`) as Promise<T>;
});

test.afterAll(async () => {
  await page.close();
});

const shot = async (name: string) => {
  await call((h) => h.frames(3));
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`) });
};

test("twenty people on the execution ground, from behind them towards the post at 18:50", async () => {
  await expect
    .poll(() => call((h) => h.crowd()), { timeout: 60_000 })
    .not.toBeNull();
  const c = (await call((h) => h.crowd()))!;
  expect(c.count).toBe(20);
  expect(c.pack).toBe(PACK);
  expect(c.meshes).toBeLessThanOrEqual(3);
  expect(c.clips.every((x) => x === "sway")).toBe(true);
  const { spots } = await call((h) => h.load());
  const post = spots["stake"]!;
  const cx = c.at.reduce((s, p) => s + p[0], 0) / c.count;
  const cz = c.at.reduce((s, p) => s + p[1], 0) / c.count;
  const [dx, dz] = [cx - post[0], cz - post[2]];
  const d = Math.hypot(dx, dz);
  const from: Vec3 = [cx + (dx / d) * 11, 4.5, cz + (dz / d) * 11]; // above and behind the back rows
  await call((h) => h.setClock(1130));
  await page.evaluate(
    ([f, t]) =>
      (window as unknown as { __zoujin: Hook }).__zoujin.setWorldView(f, t, 50),
    [from, [post[0], 1.6, post[2]] as Vec3] as const,
  );
  await shot("crowd-1850");
});

test("three draw calls more, their shadow aside (budget 8)", async () => {
  await call((h) => h.crowd("hide"));
  await call((h) => h.frames(3));
  const without = (await call((h) => h.frame())).calls;
  await call((h) => h.crowd("show"));
  await call((h) => h.frames(3));
  const withCrowd = (await call((h) => h.frame())).calls;
  console.log(`draw calls ${without} → ${withCrowd} with the crowd`);
  expect(withCrowd - without).toBeLessThanOrEqual(8);
});

test("どよめき from the scaffold outwards, the cheer, making way", async () => {
  const { spots } = await call((h) => h.load());
  const post = spots["stake"]!;
  await page.evaluate(
    (p) => (window as unknown as { __zoujin: Hook }).__zoujin.crowd("wave", p),
    [post[0], post[2]] as [number, number],
  );
  await call((h) => h.frames(2));
  await shot("crowd-stir");
  // software rendering draws about a frame a second: a whole stir can start and end between two frames, so count starts
  await expect
    .poll(async () => (await call((h) => h.crowd()))!.started.stir ?? 0, {
      timeout: 60_000,
    })
    .toBe(20);
  await call((h) => h.crowd("cheer"));
  await expect
    .poll(
      async () =>
        (await call((h) => h.crowd()))!.clips.every((x) => x === "cheer"),
      { timeout: 60_000 },
    )
    .toBe(true);
  await call((h) => h.frames(3));
  await shot("crowd-cheer");
  const king = spots["king-west"]!;
  const front = spots["stake-front"]!;
  await page.evaluate(
    (path) =>
      (window as unknown as { __zoujin: Hook }).__zoujin.crowd("part", path),
    [
      [king[0], king[2]],
      [front[0], front[2]],
    ] as [number, number][],
  );
  await call((h) => h.frames(6));
  await shot("crowd-part");
});

test("no console errors", () => {
  expect(problems).toEqual([]);
});
