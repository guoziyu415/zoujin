// A phrase longer than its line (all hiragana: phrases.ts finds no place to break it) wraps inside itself rather than
// running out of the subtitles or the talk key (UX on #167): base.css on its own, no app, the page in Japanese as the
// app's is (p's word-break: auto-phrase works by language).
import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const css = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../src/ui/base.css",
);
const LONG = "ああもうだめだここでおわりなのかしらとおもったのでございます";

test("an over-long hiragana phrase stays inside the subtitles and the talk key", async ({
  page,
}) => {
  await page.setContent(
    `<html lang="ja"><body><div class="subs" style="width: 220px"><p><span class="phrase" id="sub">${LONG}</span></p></div>` +
      `<div class="controls"><button class="talk" style="width: 88px"><span class="phrase" id="key">${LONG}</span></button></div></body></html>`,
  );
  await page.addStyleTag({ path: css });
  for (const [id, box] of [
    ["sub", ".subs"],
    ["key", ".controls .talk"],
  ] as const) {
    const inner = await page.locator(`#${id}`).boundingBox();
    const outer = await page.locator(box).boundingBox();
    expect(inner && outer).toBeTruthy();
    expect(inner!.x + inner!.width).toBeLessThanOrEqual(
      outer!.x + outer!.width + 0.5,
    );
    expect(inner!.height).toBeGreaterThan(30); // it wrapped onto more lines
    // and no text runs out of its own box either
    const over = await page
      .locator(`#${id}`)
      .evaluate((e) => e.scrollWidth - e.clientWidth);
    expect(over).toBeLessThanOrEqual(0);
  }
});
