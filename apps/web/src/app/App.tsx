// The app shell (frontend-design 5): REST data in TanStack Query, the route picks the screen. Any 401 goes to the
// invite page and comes back to where the player was afterwards.
import { QueryClientProvider } from "@tanstack/react-query";
import { useEffect } from "react";
import { setUnauthenticatedHandler } from "../net/rest";
import { CLIENT_VERSION } from "../net/session";
import CoverScreen from "../screens/CoverScreen";
import EndingScreen from "../screens/EndingScreen";
import LoginScreen from "../screens/LoginScreen";
import PlayScreen from "../screens/PlayScreen";
import RoleScreen from "../screens/RoleScreen";
import { startTelemetry } from "../telemetry/flush";
import { track } from "../telemetry/telemetry";
import "../ui/base.css";
import { queryClient } from "./queries";
import { navigate, toLogin, useRoute } from "./router";

setUnauthenticatedHandler(() => {
  queryClient.removeQueries({ queryKey: ["me"] });
  toLogin();
});

export function App() {
  useEffect(() => {
    const ua = navigator.userAgent;
    track("app_open", {
      entry: /\bLine\//.test(ua)
        ? "line"
        : document.referrer
          ? "other"
          : "direct",
      inAppBrowser: /\bLine\/|Instagram|FBAN|FBAV/.test(ua),
    });
    return startTelemetry(CLIENT_VERSION);
  }, []);
  return (
    <QueryClientProvider client={queryClient}>
      <Screen />
    </QueryClientProvider>
  );
}

function Screen() {
  const route = useRoute();
  useEffect(() => {
    if (route.name === "notFound") navigate("/", { replace: true });
  }, [route.name]);
  switch (route.name) {
    case "login":
      return <LoginScreen next={route.next} />;
    case "cover":
      return <CoverScreen />;
    case "roles":
      return <RoleScreen />;
    case "play":
      return <PlayScreen key={route.pid} pid={route.pid} />;
    case "ending":
      return <EndingScreen />;
    default:
      return null;
  }
}
