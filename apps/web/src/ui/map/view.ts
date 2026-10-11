// The chain-reaction map's rules (ux-design 9.1): the filters, the corrected marks, where 「いまここ」 goes.
import type { Api } from "@zoujin/contracts";

export type Filter = { character: string | null; mine: boolean };

export function shown(
  items: Api.TimelineItem[],
  f: Filter,
): Api.TimelineItem[] {
  if (!f.character && !f.mine) return items;
  return items.filter((it) => {
    if (it.kind !== "event") return false; // filtering by people or by the player: the beats step aside
    if (f.mine && !it.causedByPlayer) return false;
    if (f.character && !it.knownBy.includes(f.character)) return false;
    return true;
  });
}

// the people the chips offer: whoever knows of something on the map, in first-seen order
export function people(days: Api.TimelineResponse["days"]): string[] {
  const out: string[] = [];
  for (const d of days)
    for (const it of d.items)
      if (it.kind === "event")
        for (const c of it.knownBy) if (!out.includes(c)) out.push(c);
  return out;
}

// 「いまここ」 goes after the last item at or before now; -1 = before everything
export function nowIndex(items: Api.TimelineItem[], t: number): number {
  let at = -1;
  items.forEach((it, i) => {
    if (it.t <= t) at = i;
  });
  return at;
}

// the day 「いまここ」 is in: the last one with an item at or before now (null: none)
export function nowDayOf(
  days: Api.TimelineResponse["days"],
  t: number,
): number | null {
  let at: number | null = null;
  for (const d of days) if (d.items.some((it) => it.t <= t)) at = d.day;
  return at;
}

// events this page saw corrected (a correction carries supersedes, 2.4): the map marks them 「修正」 (8.5)
export const corrected = (events: Api.VisibleEvent[]): Set<string> =>
  new Set(events.filter((e) => e.supersedes).map((e) => e.eventId));

export const itemId = (it: Api.TimelineItem): string =>
  it.kind === "event" ? it.eventId : it.beatId;

// events that kept a promise get the knot (ux-design 6.3); one whose promise was voided since (its memory forgotten,
// 10.2) keeps its place on the map but loses the knot
export function keptPromises(
  events: Api.VisibleEvent[],
  voided: ReadonlySet<string> = new Set(),
): Set<string> {
  const out = new Set<string>();
  for (const e of events)
    if (e.promise?.change === "kept" && !voided.has(e.promise.promiseId))
      out.add(e.eventId);
  return out;
}

// promises voided by a later event (the forgetting sends one)
export const voidedPromises = (events: Api.VisibleEvent[]): Set<string> =>
  new Set(
    events.flatMap((e) =>
      e.promise?.change === "voided" ? [e.promise.promiseId] : [],
    ),
  );

// the whole game's map is long (F-17): with more than FOLD_OVER items, the days before 「いまここ」's day start folded
// (a tap opens one), except the day of the event it was opened for; a filter shows everything it keeps
export const FOLD_OVER = 24;

export function foldedDays(
  days: Api.TimelineResponse["days"],
  nowDay: number | null,
  f: Filter,
  eventId?: string,
): Set<number> {
  const out = new Set<number>();
  const total = days.reduce((n, d) => n + d.items.length, 0);
  if (f.character || f.mine || nowDay === null || total <= FOLD_OVER)
    return out;
  for (const d of days)
    if (
      d.day < nowDay &&
      !d.items.some((it) => it.kind === "event" && it.eventId === eventId)
    )
      out.add(d.day);
  return out;
}
