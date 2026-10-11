import { describe, expect, it } from "vitest";
import {
  BANDS,
  fit,
  layoutCard,
  MIN_PX,
  PAD,
  W,
  wrap,
  type Measure,
} from "./layout";

const m: Measure = (t, px) => [...t].length * px; // full-width characters: one em each
const inner = W - PAD * 2; // 952

const card = (n: number, line = "あ".repeat(40)) => ({
  title: "市で待ち続けた旅人",
  subtitle: "市に残り、刑場でメロスの到着を見届けた",
  people: Array.from({ length: n }, (_, i) => ({
    name: ["メロス", "市の老爺", "セリヌンティウス"][i]!,
    line,
  })),
  contrast: "原作では日没に間に合った。あなたの世界では、陽が先に沈んだ。",
  footer: "太宰治『走れメロス』より・旅人として",
  diffLabel: "原作との違い",
});

describe("ending card layout (S-051)", () => {
  it("a 14-character title at 64 px, a 26-character subtitle at 34 px, both one line", () => {
    const l = layoutCard(
      { ...card(1), title: "あ".repeat(14), subtitle: "い".repeat(26) },
      m,
    );
    expect(l.title).toMatchObject({ px: 64, lines: ["あ".repeat(14)] });
    expect(l.subtitle.px).toBe(34);
    expect(l.subtitle.lines).toHaveLength(1);
  });

  it("too long: shrinks to 28 px first, then cuts with …", () => {
    const b = fit("あ".repeat(40), 64, inner, 1, m);
    expect(b.px).toBeLessThan(64);
    expect(b.px).toBeGreaterThanOrEqual(MIN_PX);
    const c = fit("あ".repeat(60), 64, inner, 1, m);
    expect(c.px).toBe(MIN_PX);
    expect(c.lines[0]!.endsWith("…")).toBe(true);
    expect(m(c.lines[0]!, MIN_PX)).toBeLessThanOrEqual(inner);
  });

  it("people: 40 characters in two lines; fewer than three are centred in the band", () => {
    const three = layoutCard(card(3), m);
    expect(three.people).toHaveLength(3);
    for (const p of three.people)
      expect(p.text.lines.length).toBeLessThanOrEqual(2);
    const one = layoutCard(card(1), m);
    const band = { top: BANDS.art + BANDS.title, h: BANDS.people };
    const p = one.people[0]!;
    const h = p.text.lines.length * p.text.px * 1.4;
    expect(Math.abs(p.y - band.top - (band.h - h) / 2)).toBeLessThan(1);
    // the other bands don't move
    expect(one.diff.y).toBe(three.diff.y);
    expect(one.title.y).toBe(three.title.y);
  });

  it("everything at 28 px or more", () => {
    const l = layoutCard(card(3, "い".repeat(80)), m);
    const all = [
      l.title,
      l.subtitle,
      l.diff,
      l.diffLabel,
      l.footer,
      ...l.people.map((p) => p.text),
    ];
    for (const b of all) expect(b.px).toBeGreaterThanOrEqual(MIN_PX);
  });

  it("a line doesn't start with 。 or 、", () => {
    const lines = wrap("ああああ。いい", 10, 40, m);
    expect(lines[1]!.startsWith("。")).toBe(false);
  });

  it("no lone 「た。」 on the last line: the line before gives its last character", () => {
    // 4 characters a line: 「あいうえ」「おかきく」「た。」 → 「あいうえ」「おかき」「くた。」
    expect(wrap("あいうえおかきくた。", 10, 40, m)).toEqual([
      "あいうえ",
      "おかき",
      "くた。",
    ]);
    // the character that comes down never leaves a 、 to start the line
    expect(wrap("あいうえおかき、た。", 10, 40, m)).toEqual([
      "あいうえ",
      "おか",
      "き、た。",
    ]);
  });
});
