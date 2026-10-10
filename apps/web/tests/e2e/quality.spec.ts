// Quality levels (F-2 card, F-2c): with ?quality=auto the start probe runs while the plaza loads, picks a level, the
// governor starts once the scene is ready, and quality_changed / perf_sample wait in the telemetry queue in the shape
// data-design 9.3 gives. Then the same first screen at L0, L1 and L2, and at L2 with the high tier's textures: the
// colours must not change with the level or the tier (UX art-direction 9.5; L0 turns bloom and MSAA off, L2 softens
// the shadows, the high tier swaps 11 of the plaza's textures for 2048 ones). Shots in test-results/shots/quality-*.
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { PNG } from "pngjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const SHOTS = path.join(here, "../../test-results/shots");

type Event = { name: string; clientTs: string; props: Record<string, unknown> };
type QHook = {
  load(): { stage: string; error: string };
  frames(n: number): Promise<void>;
  quality(): {
    level: string;
    applied: string;
    probe: { gpuMs: number; bound: string; reps: number } | null;
    running: boolean;
    hiReady: boolean;
    assetTier: string;
  };
  telemetry(): Event[];
  force(level: string, tier?: string): Promise<void>;
  fetchHigh(): Promise<void>;
};
const hook = (p: Page) =>
  ({
    q: () => p.evaluate(() => (window.__zoujin as unknown as QHook).quality()),
    events: () =>
      p.evaluate(() => (window.__zoujin as unknown as QHook).telemetry()),
    force: (l: string, tier?: string) =>
      p.evaluate(
        ([l, t]) => (window.__zoujin as unknown as QHook).force(l!, t),
        [l, tier] as const,
      ),
    frames: (n: number) =>
      p.evaluate((n) => (window.__zoujin as unknown as QHook).frames(n), n),
  }) as const;

test.describe.configure({ mode: "serial" });

let page: Page;
const problems: string[] = [];

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") problems.push(`console: ${m.text()}`);
  });
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  fs.mkdirSync(SHOTS, { recursive: true });
  await page.goto("/?test&quality=auto");
  await page.waitForFunction(
    () => ["ready", "failed"].includes(window.__zoujin?.load().stage),
    null,
    { timeout: 240_000 },
  );
});

test.afterAll(async () => {
  await page.close();
});

test("the probe picks the start level and the governor starts", async () => {
  const q = await hook(page).q();
  console.log(`probe ${JSON.stringify(q.probe)} -> ${q.level}`);
  expect(q.probe).not.toBeNull();
  expect(q.probe!.gpuMs).toBeGreaterThan(0);
  expect(["L0", "L1", "L2", "L3"]).toContain(q.level);
  expect(q.running).toBe(true);
  const start = (await hook(page).events()).filter(
    (e) => e.name === "quality_changed",
  );
  expect(start[0]?.props).toMatchObject({ to: q.level, reason: "start" });
  expect(start[0]?.props.from).toBeUndefined();
  const g = start[0]!.props.probeGpuMs as number;
  expect(Math.round(g * 10) / 10).toBe(g); // 0.1 ms, no finer (data-design 9.3)
  expect(start[0]!.clientTs).toMatch(/Z$/);
});

test("perf_sample every 10 s: a 9-bin histogram and the level", async () => {
  await page.waitForFunction(
    () =>
      (window.__zoujin as unknown as QHook)
        .telemetry()
        .some((e) => e.name === "perf_sample"),
    null,
    { timeout: 60_000 },
  );
  const s = (await hook(page).events()).find((e) => e.name === "perf_sample")!;
  const p = s.props as {
    frameTimeHistogram: number[];
    qualityLevel: string;
    assetTier: string;
    renderer: string;
    lowPower: boolean;
    dpr: number;
    drawCalls: number;
  };
  console.log(`perf_sample ${JSON.stringify(p)}`);
  expect(p.frameTimeHistogram).toHaveLength(9);
  expect(p.frameTimeHistogram.reduce((a, b) => a + b, 0)).toBeGreaterThan(0);
  expect(["L0", "L1", "L2", "L3"]).toContain(p.qualityLevel);
  expect(p.assetTier).toBe("standard");
  expect(p.renderer).toBe("webgl");
  expect(p.drawCalls).toBeGreaterThan(0);
});

function mean(png: PNG, x0: number, y0: number, x1: number, y1: number) {
  const c = [0, 0, 0];
  let n = 0;
  for (let y = Math.floor(y0 * png.height); y < y1 * png.height; y += 2)
    for (let x = Math.floor(x0 * png.width); x < x1 * png.width; x += 2) {
      const i = (y * png.width + x) * 4;
      for (let k = 0; k < 3; k++) c[k]! += png.data[i + k]!;
      n++;
    }
  return c.map((v) => v / n);
}

const regions: Record<string, [number, number, number, number]> = {
  sky: [0.05, 0.02, 0.45, 0.25],
  castle: [0.55, 0.4, 0.95, 0.6],
  ground: [0.4, 0.75, 0.95, 0.95],
  shade: [0.0, 0.55, 0.35, 0.75],
};
const means: Record<string, Record<string, number[]>> = {};

async function shoot(name: string, level: string, tier?: string) {
  await hook(page).force(level, tier);
  await hook(page).frames(3);
  const buf = await page.screenshot({
    path: path.join(SHOTS, `quality-${name}.png`),
  });
  const png = PNG.sync.read(buf);
  means[name] = Object.fromEntries(
    Object.entries(regions).map(([k, r]) => [k, mean(png, ...r)]),
  );
}

function expectSame(name: string, ref: string) {
  for (const k of Object.keys(regions)) {
    const d = means[name]![k]!.map((v, i) => Math.abs(v - means[ref]![k]![i]!));
    console.log(
      `${name} vs ${ref} ${k}: ${d.map((x) => x.toFixed(1)).join(" ")}`,
    );
    expect(Math.max(...d)).toBeLessThanOrEqual(6);
  }
}

test("the colours stay the same at L0, L1 and L2", async () => {
  for (const l of ["L1", "L0", "L2"]) await shoot(l, l);
  expectSame("L0", "L1");
  expectSame("L2", "L1");
});

test("the high tier's textures keep the colours at L2", async () => {
  // the game fetches them at L2 once the entry pack came in fast enough; here at once, then the same frame on each tier
  await page.evaluate(() => (window.__zoujin as unknown as QHook).fetchHigh());
  expect((await hook(page).q()).hiReady).toBe(true);
  await shoot("L2-high", "L2", "high");
  expect((await hook(page).q()).assetTier).toBe("high");
  await shoot("L2-standard", "L2", "standard");
  expectSame("L2-high", "L2-standard");
});

test("no console errors", () => {
  expect(problems).toEqual([]);
});
