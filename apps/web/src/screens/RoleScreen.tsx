// Who the player enters the town as (frontend-design 5, ux-design 3), then the start (2.2). A story already open
// (409) asks 「続きから」 or 「新しく始める」; the latter confirms in place, deletes the old one, then starts.
import type { Api } from "@zoujin/contracts";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { navigate } from "../app/router";
import { audio } from "../audio";
import { BOOK_ID, handSnapshot, manifestQuery, meQuery } from "../app/queries";
import { uuid } from "../net/ids";
import { ApiError, rest } from "../net/rest";
import { track } from "../telemetry/telemetry";
import { copy, fill } from "../ui/copy";
import { dayBand } from "./CoverScreen";

type Problem =
  | { kind: "conflict"; active: Api.ActivePlaythrough; confirming: boolean }
  | { kind: "message"; text: string };

export default function RoleScreen() {
  const qc = useQueryClient();
  const manifest = useQuery(manifestQuery);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);

  const enter = (pid: string) => navigate(`/play/${encodeURIComponent(pid)}`);

  // every way in is a tap: unlock the audio inside it (frontend-design 7.4)
  async function start(roleId: string) {
    audio.unlock();
    setBusy(true);
    setProblem(null);
    try {
      const res = await rest.createPlaythrough(
        { bookId: BOOK_ID, roleId },
        uuid(),
      );
      track("role_selected", { roleId });
      handSnapshot(res.snapshot);
      void qc.invalidateQueries({ queryKey: meQuery.queryKey });
      enter(res.playthroughId);
    } catch (err) {
      setProblem(problemOf(err));
    } finally {
      setBusy(false);
    }
  }

  async function replace(active: Api.ActivePlaythrough, roleId: string) {
    audio.unlock();
    setBusy(true);
    try {
      await rest.deletePlaythrough(active.playthroughId, uuid());
    } catch (err) {
      // already gone is what we wanted
      if (!(
        err instanceof ApiError &&
        (err.status === 404 || err.code === "not_found")
      )) {
        setBusy(false);
        setProblem(problemOf(err));
        return;
      }
    }
    await start(roleId);
  }

  const roles = manifest.data?.roles ?? [];
  return (
    <main className="screen">
      <h1 style={{ fontSize: 20 }}>{copy["role.title"]}</h1>
      <p className="note">{copy["role.lead"]}</p>
      {roles.map((r) => (
        <section className="card" key={r.roleId}>
          <strong>{r.name}</strong>
          <p className="note">{r.summary}</p>
          {problem?.kind === "conflict" ? (
            <Conflict
              problem={problem}
              busy={busy}
              onResume={() => {
                audio.unlock();
                enter(problem.active.playthroughId);
              }}
              onNew={() => setProblem({ ...problem, confirming: true })}
              onCancel={() => setProblem({ ...problem, confirming: false })}
              onConfirm={() => void replace(problem.active, r.roleId)}
            />
          ) : (
            <button
              className="primary"
              disabled={busy}
              onClick={() => void start(r.roleId)}
            >
              {fill(copy["role.start"], { role: r.name })}
            </button>
          )}
        </section>
      ))}
      {problem?.kind === "message" && (
        <p className="error" role="alert">
          {problem.text}
        </p>
      )}
    </main>
  );
}

function Conflict(p: {
  problem: Extract<Problem, { kind: "conflict" }>;
  busy: boolean;
  onResume: () => void;
  onNew: () => void;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const a = p.problem.active;
  return (
    <div
      role="alertdialog"
      aria-label={copy["start.conflict"]}
      style={{ display: "grid", gap: 12 }}
    >
      <strong>{copy["start.conflict"]}</strong>
      <p className="note">
        {fill(copy["cover.resumeMeta"], {
          role: a.roleName,
          ...dayBand(a.tLabel),
        })}
      </p>
      {p.problem.confirming ? (
        <>
          <p>{copy["start.conflict.confirm"]}</p>
          <button className="primary" disabled={p.busy} onClick={p.onConfirm}>
            {copy["start.conflict.confirmYes"]}
          </button>
          <button className="secondary" disabled={p.busy} onClick={p.onCancel}>
            {copy["common.cancel"]}
          </button>
        </>
      ) : (
        <>
          <button className="primary" onClick={p.onResume}>
            {copy["start.conflict.resume"]}
          </button>
          <button className="secondary" onClick={p.onNew}>
            {copy["start.conflict.new"]}
          </button>
        </>
      )}
    </div>
  );
}

// api-contract 5 → what the screen says; the server's message is already a short Japanese line
function problemOf(err: unknown): Problem {
  if (err instanceof ApiError) {
    if (err.code === "active_playthrough_exists" && err.body?.activePlaythrough)
      return {
        kind: "conflict",
        active: err.body.activePlaythrough,
        confirming: false,
      };
    if (err.code === "daily_limit")
      return {
        kind: "message",
        text: fill(copy["start.dailyLimit"], {
          n: Math.max(
            1,
            Math.ceil((err.body?.error.retryAfterSeconds ?? 3600) / 3600),
          ),
        }),
      };
    if (err.body) return { kind: "message", text: err.body.error.message };
  }
  return { kind: "message", text: copy["login.tooMany"] };
}
