// The ending card's layout (S-051, ux-design 11.3, frontend-design 10.5): 1080×1350 in five bands. One pure function
// decides every block's size and lines from the text and a width measure, so the screen and the saved PNG are the
// same drawing, and the rules are unit tested: shrink first, down to 28 px, then cut with 「…」; 1–3 people, centred
// in their band when fewer than three; the illustration, title and 「原作との違い」 never move.
export const W = 1080;
export const H = 1350;
export const PAD = 64;
export const MIN_PX = 28;
export const BANDS = {
  art: 640,
  title: 160,
  people: 330,
  diff: 130,
  footer: 90,
} as const;
export const LINE = 1.4; // line height ÷ font size

export type Measure = (text: string, px: number) => number; // width in px at this size

export type Block = { px: number; lines: string[] };

// characters a line may not start with (a light kinsoku: they stay at the end of the line before)
const NO_START = new Set([
  ..."、。，．・：；？！」』）〕】ー…―ゝゞヽヾ々ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮ",
]);

// greedy wrap by character (Japanese has no spaces); a line never begins with closing punctuation
export function wrap(
  text: string,
  px: number,
  width: number,
  m: Measure,
): string[] {
  const out: string[] = [];
  let line = "";
  for (const ch of text) {
    if (line && m(line + ch, px) > width && !NO_START.has(ch)) {
      out.push(line);
      line = ch;
    } else line += ch;
  }
  if (line) out.push(line);
  // no lone 1-2 characters on the last line (「た。」): the end of the line before comes down with them
  const n = out.length;
  if (n >= 2) {
    const prev = [...out[n - 2]!];
    const last = [...out[n - 1]!];
    if (last.length <= 2 && prev.length > 3) {
      let k = 1;
      while (k < prev.length - 1 && NO_START.has(prev[prev.length - k]!)) k++;
      const moved = prev.splice(prev.length - k).join("") + last.join("");
      if (m(moved, px) <= width) {
        out[n - 2] = prev.join("");
        out[n - 1] = moved;
      }
    }
  }
  return out;
}

function cut(line: string, px: number, width: number, m: Measure): string {
  let s = [...line];
  while (s.length && m(s.join("") + "…", px) > width) s = s.slice(0, -1);
  return s.join("") + "…";
}

// the largest size in [max..MIN_PX] where the text fits in maxLines; at MIN_PX still too long: the last line cut
export function fit(
  text: string,
  maxPx: number,
  width: number,
  maxLines: number,
  m: Measure,
  minPx = MIN_PX,
): Block {
  for (let px = maxPx; px >= minPx; px -= 2) {
    const lines = wrap(text, px, width, m);
    if (lines.length <= maxLines) return { px, lines };
  }
  const lines = wrap(text, minPx, width, m).slice(0, maxLines);
  const last = lines.length - 1;
  lines[last] = cut(lines[last]!, minPx, width, m);
  return { px: minPx, lines };
}

export type CardText = {
  title: string; // ≤ 14
  subtitle: string; // ≤ 26
  people: { name: string; line: string }[]; // 1-3, ≤ 40 each
  contrast: string; // ≤ 48
  footer: string;
  diffLabel: string; // 「原作との違い」
};

export type PersonBlock = {
  name: string;
  nameW: number;
  text: Block;
  y: number;
};

export type CardLayout = {
  title: Block & { y: number };
  subtitle: Block & { y: number };
  people: PersonBlock[];
  diffLabel: Block & { y: number };
  diff: Block & { y: number };
  footer: Block & { y: number };
};

const top = {
  title: BANDS.art,
  people: BANDS.art + BANDS.title,
  diff: BANDS.art + BANDS.title + BANDS.people,
  footer: BANDS.art + BANDS.title + BANDS.people + BANDS.diff,
};

export function layoutCard(c: CardText, m: Measure): CardLayout {
  const inner = W - PAD * 2;
  const title = fit(c.title, 64, inner, 1, m);
  const subtitle = fit(c.subtitle, 34, inner, 1, m);
  const titleH = title.px * LINE + subtitle.px * LINE;
  const ty = top.title + (BANDS.title - titleH) / 2;

  // people: name, a gap, then the line wrapping in the rest; one size for all of them (30-34), two lines each
  const people = c.people.slice(0, 3);
  const nameW = Math.max(0, ...people.map((p) => m(p.name, MIN_PX))) + 24;
  const textW = inner - nameW;
  let px = 34;
  for (; px > 30; px -= 2)
    if (people.every((p) => wrap(p.line, px, textW, m).length <= 2)) break;
  const blocks = people.map((p) => ({
    name: p.name,
    nameW,
    text: fit(p.line, px, textW, 2, m),
  }));
  const gap = 18;
  const heights = blocks.map((b) => b.text.lines.length * b.text.px * LINE);
  const total =
    heights.reduce((a, b) => a + b, 0) + gap * Math.max(0, blocks.length - 1);
  let y = top.people + (BANDS.people - total) / 2; // centred in the band, whatever the count
  const placed = blocks.map((b, i) => {
    const out = { ...b, y };
    y += heights[i]! + gap;
    return out;
  });

  const diffLabel = fit(c.diffLabel, MIN_PX, 220, 1, m);
  const diff = fit(c.contrast, 30, inner - 240, 2, m);
  const diffH = diff.lines.length * diff.px * LINE;
  const footer = fit(c.footer, MIN_PX, inner, 1, m);
  return {
    title: { ...title, y: ty },
    subtitle: { ...subtitle, y: ty + title.px * LINE },
    people: placed,
    diffLabel: { ...diffLabel, y: top.diff + (BANDS.diff - diffH) / 2 },
    diff: { ...diff, y: top.diff + (BANDS.diff - diffH) / 2 },
    footer: {
      ...footer,
      y: top.footer + (BANDS.footer - footer.px * LINE) / 2,
    },
  };
}
