// A small History API router (frontend-design 5): five screens don't need a router package in the first-screen JS.
// Paths: /login?next=, / (cover), /roles, /play/:pid, /ending/:pid. The host serves index.html for all of them.
import { useSyncExternalStore } from "react";

export type Route =
  | { name: "login"; next: string }
  | { name: "cover" }
  | { name: "roles" }
  | { name: "play"; pid: string }
  | { name: "ending"; pid: string }
  | { name: "notFound" };

export function parse(pathname: string, search: string): Route {
  if (pathname === "/login") {
    const next = new URLSearchParams(search).get("next");
    // only our own paths: never an absolute URL or //host
    return { name: "login", next: next && /^\/(?!\/)/.test(next) ? next : "/" };
  }
  if (pathname === "/") return { name: "cover" };
  if (pathname === "/roles") return { name: "roles" };
  const m = /^\/(play|ending)\/([^/]+)$/.exec(pathname);
  if (m)
    return { name: m[1] as "play" | "ending", pid: decodeURIComponent(m[2]!) };
  return { name: "notFound" };
}

const CHANGE = "zj:navigate";
let current =
  typeof location === "undefined" ? "/" : location.pathname + location.search;

function subscribe(f: () => void): () => void {
  const on = () => {
    current = location.pathname + location.search;
    f();
  };
  window.addEventListener("popstate", on);
  window.addEventListener(CHANGE, on);
  return () => {
    window.removeEventListener("popstate", on);
    window.removeEventListener(CHANGE, on);
  };
}

export function navigate(to: string, o: { replace?: boolean } = {}): void {
  if (to === location.pathname + location.search) return;
  if (o.replace) history.replaceState(null, "", to);
  else history.pushState(null, "", to);
  window.dispatchEvent(new Event(CHANGE));
}

// back to the invite page, remembering where the player was (any 401, WebSocket 4001)
export function toLogin(): void {
  const here = location.pathname + location.search;
  if (location.pathname === "/login") return;
  navigate(`/login?next=${encodeURIComponent(here)}`, { replace: true });
}

export function useRoute(): Route {
  const url = useSyncExternalStore(subscribe, () => current);
  const q = url.indexOf("?");
  return parse(q < 0 ? url : url.slice(0, q), q < 0 ? "" : url.slice(q));
}
