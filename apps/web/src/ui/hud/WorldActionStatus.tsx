import { openOverlay } from "../../stores/story";
import { useUi } from "../../stores/ui";
import { copy, fill } from "../copy";
import { useState } from "react";

// Retained feedback uses the actual action_result. No successful outcome is guessed from a click.
export function WorldActionStatus() {
  const action = useUi((s) => s.worldAction);
  const [hiddenUnknown, setHiddenUnknown] = useState<string | null>(null);
  if (
    !action ||
    (action.status === "unknown" && action.clientMsgId === hiddenUnknown)
  )
    return null;
  const pending = action.status === "pending";
  const unknown = action.status === "unknown";
  return (
    <details className="world-action-status" key={action.clientMsgId}>
      <summary>
        <span role="status">
          {action.label} — {copy[`action.status.${action.status}`]}
        </span>
        {action.minutes !== undefined && (
          <span> · {fill(copy["action.elapsed"], { n: action.minutes })}</span>
        )}
      </summary>
      {action.narration && <p>{action.narration}</p>}
      {unknown && <p>{copy["action.unknownNote"]}</p>}
      {!pending && (
        <div className="action-sheet-buttons">
          <button onClick={() => openOverlay({ kind: "map" })}>
            {copy["menu.map"]}
          </button>
          <button onClick={() => openOverlay({ kind: "memory" })}>
            {copy["menu.memory"]}
          </button>
          <button
            onClick={() =>
              unknown
                ? setHiddenUnknown(action.clientMsgId)
                : useUi.setState({ worldAction: null })
            }
          >
            {unknown ? copy["action.acknowledge"] : copy["common.close"]}
          </button>
        </div>
      )}
    </details>
  );
}
