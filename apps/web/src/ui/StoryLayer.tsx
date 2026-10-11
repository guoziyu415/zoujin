// The story's full pages over the world (frontend-design 5, 10.4): the act end, the act change, the ending's staging, and the two overlays
// the menu opens. The memory book and the map are their own chunks: nothing of them loads before they're opened.
import { lazy, Suspense } from "react";
import { useStory } from "../stores/story";
import { ActEndPage } from "./actend/ActEndPage";
import { TransitionPage } from "./actend/TransitionPage";

const MemoryBook = lazy(() => import("./memory/MemoryBook"));
const ChainMap = lazy(() => import("./map/ChainMap"));
const EndingStage = lazy(() =>
  import("./ending/stage/EndingStage").then((m) => ({
    default: m.EndingStage,
  })),
);

export function StoryLayer({
  pid,
  names,
}: {
  pid: string;
  names: Record<string, string>;
}) {
  const overlay = useStory((s) => s.overlay);
  const actEnd = useStory((s) => !!s.actEnd);
  const transition = useStory((s) => !!s.transition);
  const ending = useStory((s) => !!s.ending);
  return (
    <>
      {actEnd && <ActEndPage />}
      {transition && <TransitionPage />}
      <Suspense fallback={null}>
        {ending && <EndingStage pid={pid} names={names} />}
        {overlay?.kind === "memory" && (
          <MemoryBook pid={pid} names={names} start={overlay.character} />
        )}
        {overlay?.kind === "map" && (
          <ChainMap
            pid={pid}
            names={names}
            {...(overlay.eventId ? { eventId: overlay.eventId } : {})}
            {...(overlay.why ? { why: overlay.why } : {})}
          />
        )}
      </Suspense>
    </>
  );
}
