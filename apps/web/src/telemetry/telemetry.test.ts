import { afterEach, expect, it } from "vitest";
import {
  clearTelemetry,
  drain,
  peek,
  requeue,
  setTelemetryContext,
  telemetryGeneration,
  track,
} from "./telemetry";

afterEach(clearTelemetry);

it("account changes drop both queued events and delayed retries from the previous account", () => {
  setTelemetryContext({ playthroughId: "pt_PREVIOUS", t: 30 });
  track("app_open", { entry: "direct", inAppBrowser: false });
  const previous = telemetryGeneration();
  const inFlight = drain();
  track("app_open", { entry: "direct", inAppBrowser: false });
  clearTelemetry();
  requeue(inFlight, previous);
  expect(peek()).toEqual([]);
  track("app_open", { entry: "direct", inAppBrowser: false });
  expect(peek()).toHaveLength(1);
  expect(peek()[0]).not.toHaveProperty("playthroughId");
});
