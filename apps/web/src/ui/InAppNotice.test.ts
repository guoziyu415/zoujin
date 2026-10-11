import { describe, expect, it } from "vitest";
import { inLine } from "./InAppNotice";

describe("inLine", () => {
  it("finds LINE's browser on iOS and Android", () => {
    expect(
      inLine(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Safari Line/14.16.0",
      ),
    ).toBe(true);
    expect(
      inLine(
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/129.0.0.0 Mobile Safari/537.36 Line/14.16.0/IAB",
      ),
    ).toBe(true);
  });
  it("leaves Safari and Chrome alone", () => {
    expect(
      inLine(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
      ),
    ).toBe(false);
    expect(
      inLine(
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36",
      ),
    ).toBe(false);
  });
});
