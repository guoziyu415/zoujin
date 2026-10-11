// The clock band (ux-design 4.2): placeholder text of the story time; when a commit moves the clock, 「+30分」 beside it
// for 2 s. The sun-and-diamond drawing is UX's card.
import { useEffect, useRef, useState } from "react";
import { useWorld } from "../../stores/world";
import { copy, fill } from "../copy";

export function delta(min: number): string {
  if (min < 60) return fill(copy["clock.delta.min"], { n: min });
  const h = Math.floor(min / 60);
  const rest = min - h * 60;
  return fill(
    rest >= 30 ? copy["clock.delta.hoursHalf"] : copy["clock.delta.hours"],
    { n: h },
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
