// ESLint flat config（R-0）。搬进来的文档、数据和 spikes 不按产品规则查。
import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      "**/node_modules/**",
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
  {
    files: [
      "assets/pipeline/**/*.mjs",
      "packages/contracts/gen/**/*.mjs",
      "*.js",
    ],
    languageOptions: { globals: globals.node },
  },
);
