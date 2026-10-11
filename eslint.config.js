// ESLint flat config（R-0）。搬进来的文档、数据和 spikes 不按产品规则查。
import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      "**/node_modules/**",
      "**/dist/**",
      "**/test-results/**",
      ".venv/**",
      "spikes/**",
      "docs/**",
      "worlds/**",
      "evals/**",
      "fixtures/**",
      "packages/worldsim/reference/**",
      "packages/contracts/**/generated/**",
      "assets/**/reports/**",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["apps/web/**/*.{ts,tsx}"],
    languageOptions: { globals: globals.browser },
  },
  // 只有网络层碰 WebSocket：组件和 3D 层读 store、调 net/play 的动作（F-0，frontend-design 4）
  {
    files: ["apps/web/src/**/*.{ts,tsx}"],
    ignores: ["apps/web/src/net/**"],
    rules: {
      "no-restricted-globals": [
        "error",
        {
          name: "WebSocket",
          message:
            "WebSocket 只在 src/net/ 里用；组件调 net/play 的动作、读 store。",
        },
      ],
      "no-restricted-properties": [
        "error",
        {
          object: "window",
          property: "WebSocket",
          message: "WebSocket 只在 src/net/ 里用。",
        },
        {
          object: "globalThis",
          property: "WebSocket",
          message: "WebSocket 只在 src/net/ 里用。",
        },
      ],
    },
  },
  {
    files: [
      "assets/pipeline/**/*.mjs",
      "packages/contracts/gen/**/*.mjs",
      "apps/web/scripts/**/*.mjs",
      "apps/web/*.config.ts",
      "apps/web/scene-dir.ts",
      "apps/web/tests/e2e/**/*.ts",
      "*.js",
    ],
    languageOptions: { globals: globals.node },
  },
);
