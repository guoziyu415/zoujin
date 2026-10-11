import type { Api } from "@zoujin/contracts";
import { describe, expect, it } from "vitest";
import {
  actEnded,
  backToExits,
  awaitsTransition,
  canPropose,
  choiceRefused,
  chosen,
  clearNotHeard,
  onWelcome,
  openPropose,
  planResult,
  proposeRetracted,
  proposed,
  transition,
} from "./story";

const end: Api.ActEnd = {
  actId: "act.1",
  recapLines: [],
  options: [
    {
      optionId: "exit.1.city",
      label: "市に残り、メロスの帰りを待つ",
      sceneId: "scene.syracuse-square",
      tLabel: "三日目・夕方",
      where: "刑場・三日目の夕方",
      sub: "西の門が見える所で",
      with: [],
      because: null,
    },
  ],
  freeform: { allowed: true, triesLeft: 2 },
};

const alt: Api.PlanAlternative = {
  optionId: "plan_01",
  label: "市に残る",
  sceneId: "scene.syracuse-square",
  tLabel: "三日目・夕方",
};

const result = (
  r: Partial<Api.ActPlanResultMessage>,
): Api.ActPlanResultMessage => ({
  type: "act_plan_result",
  accepted: false,
  narration: ["……"],
  triesLeft: 1,
  ...r,
});

const typed = () => proposed(openPropose(actEnded(end)), { clientMsgId: "c1" });

describe("act end", () => {
  it("starts on the exits; freeform off means no proposing", () => {
    const a = actEnded(end);
    expect(a.phase).toEqual({ k: "choose" });
    expect(canPropose(a)).toBe(true);
    const off = actEnded({
      ...end,
      freeform: { allowed: false, triesLeft: 0 },
    });
    expect(canPropose(off)).toBe(false);
    expect(openPropose(off)).toBe(off);
  });

  it("matches a typed result by clientMsgId and ignores others", () => {
    const a = typed();
    expect(planResult(a, result({ clientMsgId: "other" }))).toBe(a);
    const r = planResult(a, result({ clientMsgId: "c1", alternative: alt }));
    expect(r.phase).toMatchObject({
      k: "result",
      accepted: false,
      alternative: alt,
    });
    expect(r.triesLeft).toBe(1);
    expect(r.giveUp).toBe(false);
  });

  it("matches a spoken result by turnId", () => {
    const a = proposed(openPropose(actEnded(end)), { turnId: "t1" });
    expect(planResult(a, result({ turnId: "t0" }))).toBe(a);
    expect(
      planResult(a, result({ turnId: "t1", accepted: true })).phase,
    ).toMatchObject({
      k: "result",
      accepted: true,
      alternative: null,
    });
  });

  it("an empty transcript isn't a try: back to the input with the not-heard line", () => {
    const a = proposed(openPropose(actEnded(end)), { turnId: "t1" });
    const r = planResult(a, result({ turnId: "t1", triesLeft: 2 }));
    expect(r.phase).toEqual({ k: "propose", notHeard: true });
    expect(r.triesLeft).toBe(2);
    expect(clearNotHeard(r).phase).toEqual({ k: "propose", notHeard: false });
  });

  it("a retracted spoken try comes back to the input, unused", () => {
    const a = proposed(openPropose(actEnded(end)), { turnId: "t1" });
    expect(proposeRetracted(a, "t1").phase).toEqual({
      k: "propose",
      notHeard: false,
    });
    expect(proposeRetracted(a, "t2")).toBe(a);
  });

  it("the last try used: only the given exits, with the give-up line", () => {
    const a = planResult(
      typed(),
      result({ clientMsgId: "c1", triesLeft: 0, alternative: alt }),
    );
    expect(a.giveUp).toBe(true);
    expect(canPropose(a)).toBe(false);
    expect(backToExits(a).phase).toEqual({ k: "choose" });
  });

  it("chosen: back does nothing", () => {
    const a = chosen(actEnded(end), "exit.1.city");
    expect(backToExits(a)).toBe(a);
  });
});

describe("act change", () => {
  it("その頃 only with something to tell; the slice's jump page between act 1 and 4", () => {
    expect(
      transition({ fromActId: "act.1", toActId: "act.4", recap: [] }).steps,
    ).toEqual(["jump", "arrival"]);
    const t = transition({
      fromActId: "act.2",
      toActId: "act.3",
      recap: [1, 2, 3, 4].map((n) => ({ eventId: `ev_${n}`, line: "…" })),
      arrival: { line: "…", opener: "char.old-man" },
    });
    expect(t.steps).toEqual(["sonokoro", "arrival"]);
    expect(t.recap).toHaveLength(3);
    expect(t.arrival?.opener).toBe("char.old-man");
  });
});

describe("the act end across a drop and a refusal (3.11, 4, v1.0.12)", () => {
  const thinking = proposed(openPropose(actEnded(end)), { clientMsgId: "c1" });
  const picked = chosen(actEnded(end), "exit.1.city");
  const later = { ...end, freeform: { allowed: true, triesLeft: 1 } };

  it("invalid_choice: from the chosen exit back to the exits", () => {
    expect(choiceRefused(picked).phase).toEqual({ k: "choose" });
    expect(choiceRefused(thinking)).toBe(thinking);
  });

  it("waits for act_transition after a choice, a plan sent, or a plan accepted", () => {
    expect(awaitsTransition(picked)).toBe(true);
    expect(awaitsTransition(thinking)).toBe(true);
    const ok = planResult(thinking, {
      type: "act_plan_result",
      clientMsgId: "c1",
      accepted: true,
      narration: ["あなたは、市に残ることにした。"],
      alternative: null,
      triesLeft: 1,
    } as unknown as Api.ActPlanResultMessage);
    expect(awaitsTransition(ok)).toBe(true);
    expect(awaitsTransition(actEnded(end))).toBe(false);
    expect(awaitsTransition(null)).toBe(false);
  });

  it("the server still has the act end: a sent plan or choice starts over with its tries left", () => {
    const r = onWelcome(thinking, later);
    expect(r).toEqual({ set: actEnded(later) });
    expect(onWelcome(picked, later)).toEqual({ set: actEnded(later) });
    expect(onWelcome(actEnded(end), later)).toEqual({ keep: true });
    expect(onWelcome(null, later)).toEqual({ set: actEnded(later) });
  });

  it("the server has moved on: a waiting page stays for the resent act_transition; any other goes", () => {
    expect(onWelcome(picked, undefined)).toEqual({ keep: true });
    expect(onWelcome(thinking, undefined)).toEqual({ keep: true });
    expect(onWelcome(actEnded(end), undefined)).toEqual({ set: null });
    expect(onWelcome(null, undefined)).toEqual({ keep: true });
  });
});
