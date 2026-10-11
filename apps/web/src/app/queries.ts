// REST data as TanStack Query keeps it (frontend-design 6): who the player is and the book's manifest.
import { QueryClient } from "@tanstack/react-query";
import { ApiError, rest } from "../net/rest";

export const BOOK_ID = "hashire-merosu"; // legacy links and sandbox only

export const booksQuery = { queryKey: ["books"], queryFn: rest.books } as const;
export const libraryQuery = {
  queryKey: ["library"],
  queryFn: rest.library,
} as const;
export const manifestFor = (bookId: string, worldModelVersion?: string) => ({
  queryKey: ["manifest", bookId, worldModelVersion ?? "current"],
  queryFn: () => rest.manifest(bookId, worldModelVersion),
  staleTime: Infinity,
});

export const meQuery = { queryKey: ["me"], queryFn: rest.me } as const;

// long-cached on the server too (2.1)
export const manifestQuery = manifestFor(BOOK_ID);

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // a 4xx won't change on retry; the network and 5xx get two more tries
      retry: (n, err) =>
        n < 2 &&
        !(err instanceof ApiError && err.status >= 400 && err.status < 500),
      refetchOnWindowFocus: false,
    },
  },
});

// the snapshot POST /playthroughs returned, for the world screen to start from without a GET
const handoff = new Map<string, import("@zoujin/contracts").Api.Snapshot>();
export const clearSnapshots = () => handoff.clear();
export const handSnapshot = (s: import("@zoujin/contracts").Api.Snapshot) =>
  handoff.set(s.playthroughId, s);
export function takeSnapshot(pid: string) {
  const s = handoff.get(pid);
  handoff.delete(pid);
  return s;
}
