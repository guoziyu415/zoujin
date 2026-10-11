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
  it("a phrase longer than a line gets smaller type", () => {
    expect(keyFontPx(phrases("聞いています"))).toBeUndefined();
    expect(keyFontPx(phrases("準備しています"))).toBe(10);
  });
});
