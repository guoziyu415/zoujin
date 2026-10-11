import type { Api } from "@zoujin/contracts";
import { describe, expect, it } from "vitest";
import { afterDelete, isEmpty, meter, shownPromises } from "./view";

const melos: Api.MemoryBookCharacter = {
  character: "char.melos",
  relationLabel: "気を許している",
  relationLevel: 4,
  promises: [
    {
      promiseId: "prm_1",
      text: "力になる",
      direction: "playerToCharacter",
      status: "open",
      eventId: "ev_1",
    },
    {
      promiseId: "prm_2",
      text: "待つ",
      direction: "characterToPlayer",
      status: "voided",
      eventId: "ev_2",
    },
  ],
  didForYou: [],
  youDid: [],
  memories: [
    {
      memoryId: "mem_1",
      kind: "promise",
      text: "…",
      t: 1,
      tLabel: "約束の日・夕方",
      via: "witnessed",
      promiseId: "prm_1",
    },
  ],
};

describe("memory book", () => {
  it("never shows a voided promise; a section of only voided ones is empty", () => {
    expect(shownPromises(melos).map((p) => p.promiseId)).toEqual(["prm_1"]);
    const onlyVoided = {
      ...melos,
      promises: [melos.promises[1]!],
      memories: [],
    };
    expect(isEmpty(onlyVoided)).toBe(true);
  });

  it("five boxes, filled by the level", () => {
    expect(meter(4)).toBe("■■■■□");
    expect(meter(1)).toBe("■□□□□");
  });

  it("after a delete: memory gone, relation moved, promise voided", () => {
    const d = afterDelete(
      { characters: [melos] },
      {
        memoryId: "mem_1",
        deleted: true,
        character: "char.melos",
        relationLabel: "様子を見ている",
        relationLevel: 3,
        promiseVoided: "prm_1",
        sessionRebuilt: false,
      },
    ).characters[0]!;
    expect(d.memories).toEqual([]);
    expect(d.relationLevel).toBe(3);
    expect(shownPromises(d)).toEqual([]);
    expect(isEmpty(d)).toBe(true);
  });
});
