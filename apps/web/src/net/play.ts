// The verbs the world screen's components call (frontend-design 4): they reach the open playthrough's session through
// here, never a socket. With no playthrough open they do nothing.
import type { Api } from "@zoujin/contracts";
import { Session, type SessionHooks } from "./session";

let current: Session | null = null;
let names: Record<string, string> = {}; // from the manifest; may arrive before or after the session opens

export function openPlay(
  pid: string,
  snapshot: Api.Snapshot,
  hooks: SessionHooks,
): Session {
  current?.stop();
  current = new Session(pid, hooks);
  current.setNames(names);
  current.start(snapshot);
  return current;
}

export function closePlay(): void {
  current?.stop();
  current = null;
}

export const play = {
  focus: (character: string) => current?.focus(character),
  unfocus: () => current?.unfocus("menu"),
  say: (text: string, via: Api.TextMessage["via"] = "typed") =>
    current?.say(text, via),
  examine: (target: string) => current?.examine(target),
  reconnect: () => current?.reconnect(),
  // pagehide: close the socket so the page can go into the back/forward cache (9.5)
  suspend: () => current?.suspend(),
  setNames: (n: Record<string, string>) => {
    names = n;
    current?.setNames(n);
  },
};
