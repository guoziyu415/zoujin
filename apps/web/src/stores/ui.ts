// The UI store (frontend-design 6): the connection as the banner shows it, the light reactions, the resume gate.
import { create } from "zustand";

export type Connection =
  | "idle" // no playthrough open
  | "connecting" // first connect
  | "open" // welcome received
  | "reconnecting" // dropped, retrying with backoff (api-contract 4)
  | "taken" // 4009: the same story is open in another tab (9.1)
  | "gone"; // 4003 / 4004: not this player's, or deleted

export type Toast = {
  id: number;
  head: string; // 「メロスは覚えた」「物語が動いた」 (copy-ja 5)
  body?: string;
  tone: "memory" | "event";
};

type UiStore = {
  connection: Connection;
  downSince: number | null; // when the socket dropped (performance.now()); the banner escalates after 15 s
  toasts: Toast[]; // at most two on screen; the rest count as 「ほか{n}件」
  moreToasts: number;
  resumeGate: boolean; // back from the background: one tap resumes audio (9.5)
  overlay: "nearby" | null;
};

export const useUi = create<UiStore>()(() => ({
  connection: "idle",
  downSince: null,
  toasts: [],
  moreToasts: 0,
  resumeGate: false,
  overlay: null,
}));

export const TOASTS_SHOWN = 2;
const TOAST_MS = 6000; // ux-design 8.2
let toastId = 0;

// one commit's reactions arrive together: two show, the others are counted (ux-design 8.2)
export function showToasts(list: Omit<Toast, "id">[]): void {
  if (!list.length) return;
  const shown = list
    .slice(0, TOASTS_SHOWN)
    .map((t) => ({ ...t, id: ++toastId }));
  useUi.setState({ toasts: shown, moreToasts: list.length - shown.length });
  const ids = new Set(shown.map((t) => t.id));
  setTimeout(() => {
    useUi.setState((s) =>
      s.toasts.some((t) => ids.has(t.id)) ? { toasts: [], moreToasts: 0 } : s,
    );
  }, TOAST_MS);
}
