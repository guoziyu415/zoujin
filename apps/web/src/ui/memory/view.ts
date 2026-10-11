// What the memory book shows of the server's four sections (ux-design 10.1): voided promises never (a deleted promise
// leaves no trace), an empty section not at all, the relation as five boxes.
import type { Api } from "@zoujin/contracts";

export const shownPromises = (c: Api.MemoryBookCharacter): Api.PromiseView[] =>
  c.promises.filter((p) => p.status !== "voided");

export const isEmpty = (c: Api.MemoryBookCharacter): boolean =>
  !shownPromises(c).length &&
  !c.didForYou.length &&
  !c.youDid.length &&
  !c.memories.length;

export const meter = (level: number): string =>
  "■".repeat(level) + "□".repeat(Math.max(0, 5 - level));

// the book after a delete: the memory gone, the relation moved, its promise voided (2.7's response)
export function afterDelete(
  doc: Api.MemoriesResponse,
  r: Api.MemoryDeleteResponse,
): Api.MemoriesResponse {
  return {
    characters: doc.characters.map((c) =>
      c.character !== r.character
        ? c
        : {
            ...c,
            relationLabel: r.relationLabel,
            relationLevel: r.relationLevel,
            memories: c.memories.filter((m) => m.memoryId !== r.memoryId),
            promises: c.promises.map((p) =>
              p.promiseId === r.promiseVoided
                ? { ...p, status: "voided" as const }
                : p,
            ),
          },
    ),
  };
}

export const memoriesKey = (pid: string) => ["memories", pid] as const;

// promises forgotten with their memory (10.2), as far as this page knows: the map takes the knot off them
export const voidedIn = (d: Api.MemoriesResponse | undefined): Set<string> =>
  new Set(
    (d?.characters ?? []).flatMap((c) =>
      c.promises.filter((p) => p.status === "voided").map((p) => p.promiseId),
    ),
  );
