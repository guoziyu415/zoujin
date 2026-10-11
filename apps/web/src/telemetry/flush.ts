// Sending the telemetry queue (frontend-design 11): batches of up to 50 every 10 s while there is something to send,
// and whatever is left when the page is hidden (keepalive fetch, our sendBeacon). A batch that fails goes back to the
// queue; telemetry never shows the player an error.
import type { Api } from "@zoujin/contracts";
import { rest } from "../net/rest";
import { drain, peek, requeue } from "./telemetry";

const EVERY_MS = 10_000;
const BATCH = 50;

// screen size class, not the model: iOS doesn't tell the model (frontend-design 11)
export function common(appVersion: string): Api.TelemetryCommon {
  const ua = navigator.userAgent;
  const os = /iPhone|iPad|iPod/.test(ua)
    ? "ios"
    : /Android/.test(ua)
      ? "android"
      : /Mac OS X/.test(ua)
        ? "macos"
        : /Windows/.test(ua)
          ? "windows"
          : "other";
  const browser = /\bLine\//.test(ua)
    ? "line"
    : /Instagram/.test(ua)
      ? "instagram"
      : /FBAN|FBAV/.test(ua)
        ? "facebook"
        : /CriOS|Chrome\//.test(ua)
          ? "chrome"
          : /FxiOS|Firefox\//.test(ua)
            ? "firefox"
            : /Safari\//.test(ua)
              ? "safari"
              : "other";
  const dpr = Math.round(window.devicePixelRatio * 10) / 10;
  return {
    deviceClass: `${os}-${screen.width}x${screen.height}@${dpr}`,
    os,
    browser,
    appVersion,
  };
}

let sending = false;

async function send(c: Api.TelemetryCommon, keepalive: boolean): Promise<void> {
  if (sending && !keepalive) return;
  sending = true;
  try {
    while (peek().length) {
      const events = drain(BATCH);
      try {
        await rest.telemetry({ common: c, events }, keepalive);
      } catch {
        requeue(events);
        return;
      }
    }
  } finally {
    sending = false;
  }
}

export function startTelemetry(appVersion: string): () => void {
  const c = common(appVersion);
  const timer = setInterval(() => void send(c, false), EVERY_MS);
  const hidden = () => {
    if (document.visibilityState === "hidden") void send(c, true);
  };
  document.addEventListener("visibilitychange", hidden);
  window.addEventListener("pagehide", hidden);
  return () => {
    clearInterval(timer);
    document.removeEventListener("visibilitychange", hidden);
    window.removeEventListener("pagehide", hidden);
  };
}
