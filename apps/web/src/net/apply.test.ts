import { describe, expect, it } from "vitest";
import { addEvents, applyCommit, applyPatch, fromSnapshot } from "./apply";
import { commit, event, snapshot } from "./testkit";

describe("applyPatch", () => {
  it("merges a character, adds one entering with the defaults, drops one leaving the scene", () => {
    const w = fromSnapshot(snapshot());
    const next = applyPatch(w, {
      characters: [
        { id: "char.melos", activity: "idle" },
        { id: "char.king", place: "place.stonemason-workshop" },
        { id: "char.old-man", place: "place.castle" },
      ],
    });
    expect(next.characters["char.melos"]).toMatchObject({
      spot: "fountain-east",
      activity: "idle",
      talkable: true,
    });
    expect(next.characters["char.king"]).toEqual({
      id: "char.king",
      place: "place.stonemason-workshop",
      activity: "idle",
      talkable: false,
    });
    expect(next.characters["char.old-man"]).toBeUndefined();
    expect(w.characters["char.old-man"]).toBeDefined(); // not mutated
  });

  it("merges the clock, replaces the deadline, adds and removes actions", () => {
    const w = fromSnapshot(
      snapshot({
        actions: [
          {
            actionId: "act_wait_square",
            kind: "wait",
            label: "時を進める",
            estimatedMinutes: 30,
            melos: null,
            melosMinutes: null,
            melosInTime: null,
            enabled: true,
          },
        ],
      }),
    );
    const next = applyPatch(w, {
      clock: { t: 1080, tLabel: "約束の日・夕方" },
      deadline: { shown: true, line: "日没までに", sunsetT: 1140 } as never,
      actions: { remove: ["act_wait_square"] },
    });
    expect(next.clock).toEqual({
      t: 1080,
      tLabel: "約束の日・夕方",
      deadlineT: 5460,
    });
    expect(next.deadline).toMatchObject({ shown: true });
    expect(next.actions).toEqual([]);
  });
});

describe("addEvents", () => {
  it("skips events it has seen and puts a correction in the place of what it supersedes", () => {
    const a = event();
    const b = event();
    const fix = event({
      type: "correction",
      supersedes: a.eventId,
      summary: "言い直した",
    });
    const list = addEvents(addEvents([], [a, b]), [b, fix]);
    expect(list.map((e) => e.eventId)).toEqual([fix.eventId, b.eventId]);
  });
});

describe("applyCommit", () => {
  const w = fromSnapshot(snapshot({ lastSeq: 4 }));

  it("applies the next range and moves lastSeq", () => {
    const e = event();
    const r = applyCommit(
      w,
      commit(5, 6, {
        events: [e],
        patch: { clock: { t: 1060, tLabel: "約束の日・夕方" } },
      }),
    );
    expect(r.kind).toBe("applied");
    if (r.kind !== "applied") return;
    expect(r.world.lastSeq).toBe(6);
    expect(r.world.clock.t).toBe(1060);
    expect(r.world.events).toEqual([e]);
  });

  it("says seen for a commit resent after a reconnect", () => {
    expect(applyCommit(w, commit(3, 4)).kind).toBe("seen");
    expect(applyCommit(w, commit(1, 2)).kind).toBe("seen");
  });

  it("says gap when the range doesn't follow", () => {
    expect(applyCommit(w, commit(7, 8)).kind).toBe("gap");
  });
});
