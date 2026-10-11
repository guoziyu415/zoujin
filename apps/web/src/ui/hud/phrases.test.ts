import { describe, expect, it } from "vitest";
import { keyFontPx, phrases } from "./phrases";

describe("the talk key's phrases", () => {
  it("breaks before content words only", () => {
    expect(phrases("指を離すと取り消します")).toEqual([
      "指を",
      "離すと",
      "取り消します",
    ]);
    expect(phrases("人に近づくと話せます")).toEqual([
      "人に",
      "近づくと",
      "話せます",
    ]);
    expect(phrases("つながり直しています")).toEqual([
      "つながり",
      "直しています",
    ]);
    expect(phrases("聞いています")).toEqual(["聞いています"]);
    expect(phrases("")).toEqual([]);
  });
  it("a phrase longer than a line breaks where its kanji give way to kana", () => {
    expect(phrases("準備しています", 6)).toEqual(["準備", "しています"]);
    expect(phrases("準備しています")).toEqual(["準備しています"]);
    expect(phrases("キャンセルされました", 6)).toEqual([
      "キャンセルされました",
    ]); // no kanji: stays whole
  });
  it("a phrase still longer than a line gets smaller type, never under 11 px", () => {
    expect(keyFontPx(phrases("聞いています", 6))).toBeUndefined();
    expect(keyFontPx(phrases("準備しています", 6))).toBeUndefined();
    expect(keyFontPx(["ひとつながりの言葉"])).toBe(11);
  });
});
