// Playwright for the world screen (F-2 card acceptance) and the app shell against B-1's mock (F-0): headless Chromium
// with software WebGL (SwiftShader), a phone sized portrait viewport, against `vite preview` of a build (run
// `pnpm build` first; ZOUJIN_SCENE_ROOT if the scene was built elsewhere). Software rendering draws a frame in about
// half a second, hence the long timeouts. The preview proxies /v1 and /__mock to the mock (vite.config.ts), which runs
// at half speed so a turn's steps keep their order but don't take long.
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 300_000,
  expect: { timeout: 30_000 },
  workers: 1,
  reporter: [["list"]],
  outputDir: "test-results",
  use: {
    baseURL: "http://127.0.0.1:4173",
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    launchOptions: {
      // PW_CHROMIUM: a Chromium that is already installed (the project containers); CI uses Playwright's own
      ...(process.env.PW_CHROMIUM
        ? { executablePath: process.env.PW_CHROMIUM }
        : {}),
      args: [
        "--use-angle=swiftshader",
        "--enable-unsafe-swiftshader",
        "--ignore-gpu-blocklist",
      ],
    },
  },
  webServer: [
    {
      command:
        "uv run --all-packages zoujin-mock --port 8787 --speed 0.5 --log-level warning",
      cwd: "../..",
      url: "http://127.0.0.1:8787/__mock/scenarios",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: "pnpm exec vite preview --port 4173 --strictPort",
      url: "http://127.0.0.1:4173",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
