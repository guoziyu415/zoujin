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

// events this page saw corrected (a correction carries supersedes, 2.4): the map marks them 「修正」 (8.5)
export const corrected = (events: Api.VisibleEvent[]): Set<string> =>
  new Set(events.filter((e) => e.supersedes).map((e) => e.eventId));

export const itemId = (it: Api.TimelineItem): string =>
  it.kind === "event" ? it.eventId : it.beatId;
