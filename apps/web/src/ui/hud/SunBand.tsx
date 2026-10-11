// The clock band (ux-design 4.2): placeholder text of the story time; when a commit moves the clock, 「+30分」 beside it
// for 2 s. The sun-and-diamond drawing is UX's card.
import { useEffect, useRef, useState } from "react";
import { useWorld } from "../../stores/world";
import { copy, fill } from "../copy";

// an hour or more: to the nearest 30 minutes, 15 rounding up (copy-ja 3, the same as the countdown): 74 → +1時間,
// 75 → +1時間半, 105 → +2時間
export function delta(min: number): string {
  if (min < 60) return fill(copy["clock.delta.min"], { n: min });
  const halves = Math.floor((min + 15) / 30);
  return fill(
    halves % 2 ? copy["clock.delta.hoursHalf"] : copy["clock.delta.hours"],
    { n: Math.floor(halves / 2) },
  );
}

export function SunBand() {
  const clock = useWorld((s) => s.world?.clock);
  const last = useRef<number | null>(null);
  const [shown, setShown] = useState<string | null>(null);
  const t = clock?.t;
  useEffect(() => {
    if (t === undefined) return;
    const before = last.current;
    last.current = t;
    if (before === null || t <= before) return;
    setShown(delta(t - before));
    const id = setTimeout(() => setShown(null), 2000);
    return () => clearTimeout(id);
  }, [t]);
  if (!clock) return null;
  const [day = clock.tLabel, band = ""] = clock.tLabel.split("・");
  return (
    <div className="sunband" data-testid="sunband">
      {fill(copy["clock.label"], { day, band })}
      {shown && <span className="delta">{shown}</span>}
    </div>
  );
}
