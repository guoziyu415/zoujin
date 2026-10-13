// ESLint flat config (R-0). Imported docs, data and spikes are not checked against product rules.
// ESLint flat config（R-0）。取り込んだドキュメント、データ、spikes は製品ルールでは検査しない。
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
  // Only the network layer touches WebSocket: components and the 3D layer read the store and call net/play actions (F-0, frontend-design 4)
  // WebSocket に触れるのはネットワーク層のみ：コンポーネントと 3D 層は store を読み、net/play のアクションを呼ぶ（F-0、frontend-design 4）
  {
    files: ["apps/web/src/**/*.{ts,tsx}"],
    ignores: ["apps/web/src/net/**"],
    rules: {
      "no-restricted-globals": [
        "error",
        {
          name: "WebSocket",
          message:
            "WebSocket is only used in src/net/; components call net/play actions and read the store. / WebSocket は src/net/ 内でのみ使用する。コンポーネントは net/play のアクションを呼び、store を読む。",
        },
      ],
      "no-restricted-properties": [
        "error",
        {
          object: "window",
          property: "WebSocket",
          message: "WebSocket is only used in src/net/. / WebSocket は src/net/ 内でのみ使用する。",
        },
        {
          object: "globalThis",
          property: "WebSocket",
          message: "WebSocket is only used in src/net/. / WebSocket は src/net/ 内でのみ使用する。",
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
