// Light reactions (ux-design 8.2): from the top, two at a time, the rest as 「ほか{n}件」; polite for screen readers.
import { useUi } from "../../stores/ui";
import { copy, fill } from "../copy";

export function WorldReactionToast() {
  const toasts = useUi((s) => s.toasts);
  const more = useUi((s) => s.moreToasts);
  return (
    <div className="toasts" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.tone}`} data-testid="toast">
          <div>{t.head}</div>
          {t.body && <div className="body">{t.body}</div>}
        </div>
      ))}
      {more > 0 && (
        <div className="toast-more">
          {fill(copy["toast.more"], { n: more })}
        </div>
      )}
    </div>
  );
}
