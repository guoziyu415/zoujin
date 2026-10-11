// F-13: the ending's staging in 3D in the sandbox (?world: the slice's plaza, no server). The ending as B-9 leaves it
// for the longest one (Melos made it, the king changed his mind), every shot in order, a screenshot of each for UX,
// and the card's picture at 1080×640. Needs the built plaza (assets/pipeline/plaza/build.sh), like world.spec.
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const SHOTS = path.join(here, "../../test-results/shots");

type Hook = {
  load(): { stage: string; error: string };
  frames(n: number): Promise<void>;
  setClock(t: number): Promise<void>;
  crowd(): Promise<{ count: number } | null>;
  ending(staging: unknown, pieces: string[]): Promise<void>;
  endingShot(n: number): Promise<number>;
  endingCard(): Promise<{ width: number; height: number; png: string } | null>;
};
const hook = (page: Page) =>
  page.evaluateHandle(() => (window as unknown as { __zoujin: Hook }).__zoujin);

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
  await page.goto("/?world&test&crowd=20");
  await page.waitForFunction(
    () =>
      ["ready", "failed"].includes(
        (window as unknown as { __zoujin?: Hook }).__zoujin?.load().stage ?? "",
      ),
    null,
    { timeout: 240_000 },
  );
});

test.afterAll(() => {
  expect(problems).toEqual([]);
});

test("the longest ending, shot by shot, and the card's picture", async () => {
  // software rendering takes about a minute a shot: eleven shots and the card don't fit the 5-minute default
  test.setTimeout(15 * 60_000);
  const h = await hook(page);
  expect(await h.evaluate((z) => z.load().stage)).toBe("ready");
  await h.evaluate((z) => z.setClock(2 * 1440 + 18 * 60 + 40)); // 三日目 18:40, the sun low in the west
  await h.evaluate((z) =>
    z.ending(
      {
        place: "place.execution-ground",
        characters: [
          { id: "char.selinuntius", state: "freed" },
          { id: "char.melos", state: "arriving" },
          { id: "char.king", state: "approaching" },
          { id: "char.old-man", state: "in-crowd" },
          { id: "char.maiden", state: "in-crowd" },
          { id: "player", state: "in-crowd" },
        ],
      },
      [
        "piece.crowd-makes-way",
        "piece.embrace",
        "piece.king-asks",
        "piece.scarlet-cloak",
      ],
    ),
  );
  // (how long each shot takes is the unit tests' (script.test.ts): software rendering here runs the stage slow)
  for (let n = 1; n <= 11; n++) {
    await h.evaluate((z, n) => z.endingShot(n), n);
    await page.screenshot({ path: path.join(SHOTS, `ending-${n}.png`) });
  }
  // the card takes shot 6: cut back to it, then the picture
  await h.evaluate((z) => z.endingShot(6));
  const card = await h.evaluate((z) => z.endingCard());
  expect(card).not.toBeNull();
  expect([card!.width, card!.height]).toEqual([1080, 640]);
  fs.writeFileSync(
    path.join(SHOTS, "ending-card.png"),
    Buffer.from(card!.png.split(",")[1]!, "base64"),
  );
});
