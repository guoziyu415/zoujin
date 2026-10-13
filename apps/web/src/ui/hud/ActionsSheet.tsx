import type { Api } from "@zoujin/contracts";
import { useState } from "react";
import { play } from "../../net/play";
import { selectCovered, useStory } from "../../stores/story";
import { useUi } from "../../stores/ui";
import { useVoice } from "../../stores/voice";
import { useWorld } from "../../stores/world";
import { copy, fill } from "../copy";

type Choice = {
  request: Pick<Api.ActionMessage, "kind" | "target" | "actionId" | "params">;
  label: string;
  minutes?: number;
};

// The choices are the server's current affordances and exits, not predicted story outcomes.
export function ActionsSheet({ names }: { names: Record<string, string> }) {
  const open = useUi((s) => s.overlay === "actions");
  const connection = useUi((s) => s.connection);
  const pending = useUi((s) => s.worldAction?.status === "pending");
  const world = useWorld((s) => s.world);
  const turn = useVoice((s) => s.turn);
  const hold = useVoice((s) => s.hold);
  const paused = useVoice((s) => s.paused);
  const covered = useStory((s) => selectCovered(s) || !!s.ending);
  const [choice, setChoice] = useState<Choice | null>(null);
  const [sendFailed, setSendFailed] = useState(false);
  if (!open || covered) return null;

  const close = () => {
    setChoice(null);
    setSendFailed(false);
    useUi.setState({ overlay: null });
  };
  const talking =
    !!turn &&
    (turn.phase === "listening" ||
      turn.phase === "waiting" ||
      turn.phase === "speaking" ||
      (turn.kind !== "server" && turn.phase !== "settled"));
  const ready =
    connection === "open" &&
    !pending &&
    !talking &&
    !hold &&
    !(turn?.audio && !turn.ended) &&
    !paused &&
    !world?.pending.confirm &&
    !world?.pending.reveal &&
    !world?.pending.safetyPause &&
    world?.status === "active";
  const actions = world?.actions ?? [];
  const exits = (world?.interactables ?? []).filter((i) => i.kind === "go");
  const stillAvailable =
    choice?.request.kind === "wait" && !choice.request.actionId
      ? true
      : choice?.request.actionId
        ? actions.some(
            (a) => a.enabled && a.actionId === choice.request.actionId,
          )
        : exits.some((i) => i.enabled && i.id === choice?.request.target);
  const minutes = (n: number) => fill(copy["action.minutes"], { n });

  return (
    <div
      className="sheet action-sheet"
      role="dialog"
      aria-modal="true"
      aria-labelledby="actions-title"
    >
      <div className="action-sheet-heading">
        <h2 id="actions-title">{copy["action.title"]}</h2>
        <button onClick={close}>{copy["common.close"]}</button>
      </div>
      {choice ? (
        <div className="action-confirm">
          <h3>{choice.label}</h3>
          {choice.minutes !== undefined && <p>{minutes(choice.minutes)}</p>}
          <p>
            {choice.request.kind === "wait"
              ? copy["action.waitNote"]
              : copy["action.checkNote"]}
          </p>
          {!stillAvailable && <p>{copy["action.changed"]}</p>}
          {!ready && <p>{copy["action.busy"]}</p>}
          {sendFailed && <p role="alert">{copy["action.notSent"]}</p>}
          <div className="action-sheet-buttons">
            <button
              className="primary"
              disabled={!ready || !stillAvailable}
              onClick={() => {
                if (play.act(choice.request, choice.label)) close();
                else setSendFailed(true);
              }}
            >
              {choice.request.kind === "wait"
                ? copy["action.waitConfirm"]
                : copy["action.do"]}
            </button>
            <button
              onClick={() => {
                setChoice(null);
                setSendFailed(false);
              }}
            >
              {copy["action.back"]}
            </button>
          </div>
        </div>
      ) : (
        <>
          <p className="action-guide">{copy["action.guide"]}</p>
          <h3>{copy["action.here"]}</h3>
          {!actions.length && <p>{copy["action.none"]}</p>}
          <ul>
            {actions.map((a) => (
              <li key={a.actionId}>
                <div>
                  {a.target && (
                    <span className="action-target">
                      {names[a.target] ?? a.target}
                    </span>
                  )}
                  <span>{a.label}</span>
                  <small>{minutes(a.estimatedMinutes)}</small>
                </div>
                <button
                  disabled={!a.enabled || !ready}
                  onClick={() =>
                    setChoice({
                      request: {
                        actionId: a.actionId,
                        kind: a.kind,
                        ...(a.target ? { target: a.target } : {}),
                      },
                      label: a.label,
                      minutes: a.estimatedMinutes,
                    })
                  }
                >
                  {copy["action.choose"]}
                </button>
              </li>
            ))}
          </ul>
          {!!exits.length && (
            <>
              <h3>{copy["action.destinations"]}</h3>
              <ul>
                {exits.map((i) => (
                  <li key={i.id}>
                    <div>
                      <span>{i.label}</span>
                      <small>{minutes(i.estimatedMinutes)}</small>
                    </div>
                    <button
                      disabled={!i.enabled || !ready}
                      onClick={() =>
                        setChoice({
                          request: { kind: "go", target: i.id },
                          label: i.label,
                          minutes: i.estimatedMinutes,
                        })
                      }
                    >
                      {copy["action.headTo"]}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
          <h3>{copy["action.waitTitle"]}</h3>
          <p>{copy["action.timeGuide"]}</p>
          <button
            disabled={!ready}
            onClick={() =>
              setChoice({
                request: { kind: "wait" },
                label: copy["action.wait"],
              })
            }
          >
            {copy["action.wait"]}
          </button>
          {!ready && <p role="status">{copy["action.busy"]}</p>}
        </>
      )}
    </div>
  );
}
