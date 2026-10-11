// The book's cover (frontend-design 5, ux-design 2, 3): 「書をひらく」, or 「続きから」 when a story is open (S-024) with a
// quiet 「新しく始める」 under it (another role: the start asks before the open story is deleted). Not read: try again.
// F-1 unlocks audio in this tap; F-2d starts downloading the 3D chunk here.
import { useQuery } from "@tanstack/react-query";
import { navigate } from "../app/router";
import { meQuery } from "../app/queries";
import { track } from "../telemetry/telemetry";
import { copy, fill } from "../ui/copy";
import { ReadFailed, readFailed } from "../ui/ReadFailed";

// 「約束の日・夕方」 → day 約束の日, band 夕方
export function dayBand(tLabel: string): { day: string; band: string } {
  const [day = tLabel, band = ""] = tLabel.split("・");
  return { day, band };
}

export default function CoverScreen() {
  const me = useQuery(meQuery);
  const active = me.data?.activePlaythrough ?? null;
  return (
    <main className="screen">
      <h1>{copy["cover.title"]}</h1>
      <p>{copy["cover.tagline"]}</p>
      <p className="note">
        {copy["cover.note.violence"]}
        <br />
        {copy["cover.note.ai"]}
        <br />
        {copy["cover.note.earphones"]}
      </p>
      {me.isSuccess &&
        (active ? (
          <>
            <button
              className="primary"
              onClick={() => {
                track("continue_started", {
                  awayMs: Math.max(
                    0,
                    Date.now() - Date.parse(active.updatedAt),
                  ),
                });
                navigate(`/play/${encodeURIComponent(active.playthroughId)}`);
              }}
            >
              {copy["cover.resume"]}
            </button>
            <p className="note">
              {fill(copy["cover.resumeMeta"], {
                role: active.roleName,
                ...dayBand(active.tLabel),
              })}
            </p>
            <button className="quiet" onClick={() => navigate("/roles")}>
              {copy["cover.new"]}
            </button>
          </>
        ) : (
          <button className="primary" onClick={() => navigate("/roles")}>
            {copy["cover.open"]}
          </button>
        ))}
      {readFailed(me) && <ReadFailed onRetry={() => void me.refetch()} />}
    </main>
  );
}
