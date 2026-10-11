// The act end and the act change as the client keeps them (ux-design 4.4, 4.5; api-contract 3.11): pure functions
// over the act-end page's state, so the rules (which result belongs to which try, what a third try shows, the empty
// transcript that doesn't count) are unit tested without a socket. The session calls them; stores/story.ts holds
// the result.
import type { Api } from "@zoujin/contracts";

// 「声が届かなかったようです。…」: the server's line for an empty voice transcript (copy-ja actEnd.propose.notHeard)
export type ActEndPhase =
  | { k: "choose" } // the exits
  | { k: "propose"; notHeard: boolean } // the input area: 「どうしますか。」 (or the not-heard line in its place)
  // sent; waiting for act_plan_result with this id (one of the two). retracting: the spoken try taken back, waiting
  // for turn_retract_result (too late and its result comes all the same, 3.6 ⑦)
  | {
      k: "thinking";
      clientMsgId?: string;
      turnId?: string;
      retracting?: boolean;
    }
  // the narrator's answer: accepted waits for act_transition; not accepted offers the alternative
  | {
      k: "result";
      accepted: boolean;
      narration: string[];
      alternative: Api.PlanAlternative | null;
      turnId?: string; // said aloud: its words stay above the answer (4.4)
    }
  | { k: "chosen"; optionId: string }; // act_choose sent; the page waits for act_transition

export type ActEndState = {
  end: Api.ActEnd;
  phase: ActEndPhase;
  triesLeft: number;
  // the third try: only the given exits, with 「夜が更けていく。…」 (ux-design 4.4)
  giveUp: boolean;
};

export function actEnded(end: Api.ActEnd): ActEndState {
  return {
    end,
    phase: { k: "choose" },
    triesLeft: end.freeform.allowed ? end.freeform.triesLeft : 0,
    giveUp: false,
  };
}

export const canPropose = (s: ActEndState): boolean =>
  s.end.freeform.allowed && s.triesLeft > 0 && !s.giveUp;

export function openPropose(s: ActEndState): ActEndState {
  if (!canPropose(s)) return s;
  if (s.phase.k !== "choose" && s.phase.k !== "result") return s;
  return { ...s, phase: { k: "propose", notHeard: false } };
}

export function backToExits(s: ActEndState): ActEndState {
  if (s.phase.k === "thinking" || s.phase.k === "chosen") return s;
  return { ...s, phase: { k: "choose" } };
}

// typed (act_propose) or spoken (activity_start purpose act_plan, from activity_end on)
export function proposed(
  s: ActEndState,
  id: { clientMsgId: string } | { turnId: string },
): ActEndState {
  if (s.phase.k !== "propose") return s;
  return { ...s, phase: { k: "thinking", ...id } };
}

// the player pressed talk or typed again after the not-heard line: back to 「どうしますか。」
export function clearNotHeard(s: ActEndState): ActEndState {
  return s.phase.k === "propose" && s.phase.notHeard
    ? { ...s, phase: { k: "propose", notHeard: false } }
    : s;
}

// the player took the spoken try back: the page waits for turn_retract_result before it says anything
export function retracting(s: ActEndState, turnId: string): ActEndState {
  return s.phase.k === "thinking" && s.phase.turnId === turnId
    ? { ...s, phase: { ...s.phase, retracting: true } }
    : s;
}

// turn_retract_result for the spoken try (api-contract 3.6 ⑦): retracted, no result comes and no try is used, back to
// 「どうしますか。」; too late, the try was judged and its act_plan_result comes as usual, so keep waiting for it
export function retractResult(
  s: ActEndState,
  r: Api.TurnRetractResultMessage,
): ActEndState {
  const p = s.phase;
  if (p.k !== "thinking" || p.turnId !== r.turnId) return s;
  if (r.status === "retracted")
    return { ...s, phase: { k: "propose", notHeard: false } };
  return { ...s, phase: { k: "thinking", turnId: p.turnId } };
}

// the server refused the try before judging it (invalid_request: the act already closing, no tries left): the turn
// didn't happen, back to 「どうしますか。」
export function planRefused(s: ActEndState): ActEndState {
  return s.phase.k === "thinking"
    ? { ...s, phase: { k: "propose", notHeard: false } }
    : s;
}

export function planResult(
  s: ActEndState,
  r: Api.ActPlanResultMessage,
): ActEndState {
  const p = s.phase;
  if (p.k !== "thinking") return s;
  const mine = r.clientMsgId
    ? r.clientMsgId === p.clientMsgId
    : r.turnId !== undefined && r.turnId === p.turnId;
  if (!mine) return s; // a retracted turn's, or an older try's
  // an empty transcript: not a try (triesLeft unchanged, no alternative); the line shows where 「どうしますか。」 is
  if (
    !r.accepted &&
    r.turnId !== undefined &&
    !r.alternative &&
    r.triesLeft === s.triesLeft
  )
    return { ...s, phase: { k: "propose", notHeard: true } };
  return {
    ...s,
    triesLeft: r.triesLeft,
    giveUp: !r.accepted && r.triesLeft <= 0,
    phase: {
      k: "result",
      accepted: r.accepted,
      narration: r.narration,
      alternative: r.accepted ? null : (r.alternative ?? null),
      ...(r.turnId ? { turnId: r.turnId } : {}),
    },
  };
}

export function chosen(s: ActEndState, optionId: string): ActEndState {
  return { ...s, phase: { k: "chosen", optionId } };
}

// the server refused the choice (invalid_choice, api-contract 5): the page as it was, the exits again
export function choiceRefused(s: ActEndState): ActEndState {
  return s.phase.k === "chosen" ? { ...s, phase: { k: "choose" } } : s;
}

// the page is waiting for act_transition: an exit chosen, or a plan sent or accepted
export function awaitsTransition(s: ActEndState | null): boolean {
  if (!s) return false;
  const p = s.phase;
  return (
    p.k === "chosen" || p.k === "thinking" || (p.k === "result" && p.accepted)
  );
}

// after a reconnect, what to do with the act-end page from welcome.pending (3.11, 4):
// - the server still has the act end: what we sent before the drop got no answer (a plan's result isn't resent; a
//   choice that never left) — the page again from pending.actEnd, with the server's tries left; a page that shows
//   something (the exits, the input, a refused plan's alternative) stays as it is
// - the server has no act end and the page waits for the act change: keep it; act_transition comes after the resent
//   commits (v1.0.12) — not an arrival built from pending.arrival, whose actId would still be the old act's
// - otherwise the page goes
export function onWelcome(
  s: ActEndState | null,
  pending: Api.ActEnd | null | undefined,
): { keep: true } | { set: ActEndState | null } {
  if (pending) {
    if (!s || s.phase.k === "thinking" || s.phase.k === "chosen")
      return { set: actEnded(pending) };
    return { keep: true };
  }
  if (!s || awaitsTransition(s)) return { keep: true };
  return { set: null };
}

// 「あなたは、{plan}ことにした。」 comes from the server as the narration of an accepted plan; nothing to build here

// —— the act change (4.5, S-080) ——

export type TransitionStep = "sonokoro" | "jump" | "arrival";

export type TransitionState = {
  fromActId: string;
  toActId: string;
  recap: Api.RecapItem[];
  arrival: Api.Arrival | null;
  steps: TransitionStep[]; // the pages still to show, in order
};

// the slice jumps from act 1 straight to act 4 (S-050, S-080): its own page between その頃 and the landing
export const isSliceJump = (from: string, to: string): boolean =>
  from === "act.1" && to === "act.4";

export function transition(m: {
  fromActId: string;
  toActId: string;
  recap: Api.RecapItem[];
  arrival?: Api.Arrival;
}): TransitionState {
  const steps: TransitionStep[] = [];
  if (m.recap.length) steps.push("sonokoro"); // nothing to tell: no page (4.5)
  if (isSliceJump(m.fromActId, m.toActId)) steps.push("jump");
  steps.push("arrival");
  return {
    fromActId: m.fromActId,
    toActId: m.toActId,
    recap: m.recap.slice(0, 3),
    arrival: m.arrival ?? null,
    steps,
  };
}

export const nextStep = (t: TransitionState): TransitionState => ({
  ...t,
  steps: t.steps.slice(1),
});

// the exit card's second line: where + a full-width space + sub; the two halves wrap as wholes (ux-design 4.4)
export const subParts = (o: Api.ActOption): [string, string | null] => [
  o.where,
  o.sub ?? null,
];
