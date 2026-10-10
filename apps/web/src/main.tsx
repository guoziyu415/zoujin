// Front-end entry. F-2b only mounts the world screen; F-0 brings Vite's router, the cover and the role pick
// (frontend-design 5). The 3D screen is its own chunk, so the shell stays small (10.1).
import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";

const WorldScreen = lazy(() => import("./screens/WorldScreen"));

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Suspense fallback={null}>
      <WorldScreen />
    </Suspense>
  </StrictMode>,
);
