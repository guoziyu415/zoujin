// Front-end entry (frontend-design 5): the app shell with its router. The 3D screen is its own chunk, so the shell
// stays small (10.1). ?test / ?dev keep F-2's 3D sandbox (the fake store, the dev panel, the e2e test hook) until
// F-2d puts the plaza under the world screen; ?measure is the team's measuring page.
import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app/App";

const WorldScreen = lazy(() => import("./screens/WorldScreen"));
// the team's measuring page (F-2 range 6): ?measure, or the private page measure_artifact.mjs packs sets the flag
const MeasureScreen = lazy(() => import("./screens/MeasureScreen"));
const params = new URLSearchParams(location.search);
const measure =
  params.has("measure") ||
  (window as { __ZOUJIN_MEASURE?: boolean }).__ZOUJIN_MEASURE === true;
const sandbox = params.has("test") || params.has("dev");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Suspense fallback={null}>
      {measure ? <MeasureScreen /> : sandbox ? <WorldScreen /> : <App />}
    </Suspense>
  </StrictMode>,
);
