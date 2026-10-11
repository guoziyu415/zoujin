// The round talk key's label, broken only between phrases (UX R1): 指を離すと / 取り消します, never 準備していま / す. A
// phrase starts at each word that begins with a kanji or katakana; the words after it (particles, endings) stay with
// it. word-break: auto-phrase does this in Chrome but not in Safari, hence by hand.
const SEGMENTER = new Intl.Segmenter("ja", { granularity: "word" });
const CONTENT = /^[\p{Script=Han}\p{Script=Katakana}]/u;

export function phrases(label: string): string[] {
  const out: string[] = [];
  for (const { segment } of SEGMENTER.segment(label)) {
    if (!out.length || CONTENT.test(segment)) out.push(segment);
    else out[out.length - 1] += segment;
  }
  return out;
}

// a line inside the key holds six characters at its 12 px (base.css .controls .talk); a longer phrase gets smaller type
export const KEY_LINE = 6;
export function keyFontPx(parts: string[]): number | undefined {
  const n = Math.max(0, ...parts.map((p) => [...p].length));
  return n > KEY_LINE ? Math.floor((12 * KEY_LINE) / n) : undefined;
}
