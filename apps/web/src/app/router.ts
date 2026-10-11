// A small History API router (frontend-design 5): five screens don't need a router package in the first-screen JS.
// Paths: / (home), /books/:bookId, /books/:bookId/roles, /play/:pid, /ending/:pid.
import { useSyncExternalStore } from "react";

export type Route =
  | { name: "login"; next: string }
  | { name: "home" }
  | { name: "cover"; bookId: string }
  | { name: "roles"; bookId: string }
  | { name: "play"; pid: string }
  | { name: "ending"; pid: string }
  | { name: "notFound" };

export function parse(pathname: string, search: string): Route {
  if (pathname === "/login") {
    const next = new URLSearchParams(search).get("next");
    // only our own paths: never an absolute URL or //host
    return { name: "login", next: next && /^\/(?!\/)/.test(next) ? next : "/" };
  }
  if (pathname === "/") return { name: "home" };
  // Keep existing bookmarks usable while the catalogue supplies all new links.
  if (pathname === "/roles") return { name: "roles", bookId: "hashire-merosu" };
  const book = /^\/books\/([^/]+)(\/roles)?$/.exec(pathname);
  if (book) {
    const bookId = decodeSegment(book[1]!);
    return bookId
      ? { name: book[2] ? "roles" : "cover", bookId }
      : { name: "notFound" };
  }
  const m = /^\/(play|ending)\/([^/]+)$/.exec(pathname);
  if (m) {
    const pid = decodeSegment(m[2]!);
    return pid
      ? { name: m[1] as "play" | "ending", pid }
      : { name: "notFound" };
  }
  return { name: "notFound" };
}

function decodeSegment(value: string): string | null {
  try {
    return decodeURIComponent(value);
  } catch {
    return null;
  }
}

export const bookPath = (bookId: string) =>
  `/books/${encodeURIComponent(bookId)}`;
export const rolePath = (bookId: string) => `${bookPath(bookId)}/roles`;

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
