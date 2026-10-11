import type { Api } from "@zoujin/contracts";
import { describe, expect, it } from "vitest";
import { keptPromises, voidedPromises } from "./view";

const ev = (
  eventId: string,
  promise: Api.VisibleEvent["promise"],
): Api.VisibleEvent => ({ eventId, promise }) as Api.VisibleEvent;

describe("the knot on the map", () => {
  it("marks events that kept a promise, not the one that made it", () => {
    const events = [
      ev("e1", { promiseId: "promise.a", change: "made" }),
      ev("e2", { promiseId: "promise.a", change: "kept" }),
      ev("e3", null),
    ];
    expect([...keptPromises(events)]).toEqual(["e2"]);
  });

  it("a promise voided since loses its knot; the event stays", () => {
    const events = [
      ev("e2", { promiseId: "promise.a", change: "kept" }),
      ev("e4", { promiseId: "promise.a", change: "voided" }),
    ];
    expect(keptPromises(events, voidedPromises(events)).size).toBe(0);
    expect(keptPromises(events, new Set(["promise.b"])).has("e2")).toBe(true);
  });
});
