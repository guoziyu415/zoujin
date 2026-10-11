// The server-owned library is the authority for a playthrough's book and role after a reload.
import type { Api } from "@zoujin/contracts";

export function libraryEntry(
  library: Api.LibraryResponse | undefined,
  pid: string,
) {
  if (library?.activePlaythrough?.playthroughId === pid)
    return library.activePlaythrough;
  return (
    library?.endings.find((entry) => entry.playthroughId === pid) ??
    library?.pendingEndings.find((entry) => entry.playthroughId === pid)
  );
}
