import { describe, expect, it } from "vitest";
import { phoneOf } from "./MicSheet";

describe("phoneOf", () => {
  it("tells an iPhone, an iPad on the desktop site and an Android phone apart", () => {
    expect(
      phoneOf(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
        5,
      ),
    ).toBe("ios");
    expect(
      phoneOf(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
        5,
      ),
    ).toBe("ios");
    expect(
      phoneOf(
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36",
        5,
      ),
    ).toBe("android");
  });
  it("a computer gets both", () => {
    expect(
      phoneOf(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
        0,
      ),
    ).toBeNull();
  });
});
