// Japanese text broken only between phrases (UX R1): 指を離すと / 取り消します, never 準備していま / す; the talk key,
// the subtitles. A phrase starts at each word that begins with a kanji or katakana; the words after it (particles,
// endings) stay with it. word-break: auto-phrase does this in Chrome but not in Safari, hence by hand.
const SEGMENTER =
  typeof Intl.Segmenter === "function"
    ? new Intl.Segmenter("ja", { granularity: "word" })
    : null;
const CONTENT = /^[\p{Script=Han}\p{Script=Katakana}]/u;
// without Intl.Segmenter (Safari before 14.1, Firefox before 125): runs of kanji / katakana and of everything else
// (no dictionary there: a compound verb breaks in two, 取り / 消します; the kana after a kanji stay with it)
const RUNS =
  /[\p{Script=Han}\p{Script=Katakana}ー]+|[^\p{Script=Han}\p{Script=Katakana}ー]+/gu;

function words(text: string): string[] {
  return SEGMENTER
    ? [...SEGMENTER.segment(text)].map((s) => s.segment)
    : (text.match(RUNS) ?? []);
}
const KANJI = /\p{Script=Han}/u;
const KANA = /\p{Script=Hiragana}/u;

// max: a phrase longer than this is broken once more where its kanji give way to kana (準備 / しています)
export function phrases(text: string, max = Infinity): string[] {
  const out: string[] = [];
  for (const segment of words(text)) {
    if (!out.length || CONTENT.test(segment)) out.push(segment);
    else out[out.length - 1] += segment;
  }
  return out.flatMap((p) => {
    const c = [...p];
    if (c.length <= max) return [p];
    const at = c.findIndex(
      (ch, i) => i > 0 && KANA.test(ch) && KANJI.test(c[i - 1]!),
    );
    return at > 0 ? [c.slice(0, at).join(""), c.slice(at).join("")] : [p];
  });
}

// a line inside the key holds six characters at its 12 px (base.css .controls .talk); a longer phrase gets smaller
// type, never under 11 px (UX on #146: 10 px is too small)
export const KEY_LINE = 6;
const KEY_MIN_PX = 11;
export function keyFontPx(parts: string[]): number | undefined {
  const n = Math.max(0, ...parts.map((p) => [...p].length));
  return n > KEY_LINE
    ? Math.max(KEY_MIN_PX, Math.floor((12 * KEY_LINE) / n))
    : undefined;
}
