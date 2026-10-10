// Front-end entry. F-2b only mounts the world screen; F-0 brings Vite's router, the cover and the role pick
// (frontend-design 5). The 3D screen is its own chunk, so the shell stays small (10.1).
import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";

const WorldScreen = lazy(() => import("./screens/WorldScreen"));
// the team's measuring page (F-2 range 6): ?measure, or the private page measure_artifact.mjs packs sets the flag
const MeasureScreen = lazy(() => import("./screens/MeasureScreen"));
const measure =
  new URLSearchParams(location.search).has("measure") ||
  (window as { __ZOUJIN_MEASURE?: boolean }).__ZOUJIN_MEASURE === true;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Suspense fallback={null}>
      {measure ? <MeasureScreen /> : <WorldScreen />}
    </Suspense>
  </StrictMode>,
);
