# spikes

验证阶段的代码，原样搬来，只作参考，不按产品规则检查（ruff、mypy、eslint、prettier 都排除）。

- `backend/`：后端的技术验证（有自己的 pyproject 和 uv.lock，Mac 照旧单独跑；测试依赖 Google 的库，不进 CI）。B-0 和 Live 代理从这里搬。
- `frontend/`：S1 走路测试页（T-002）、S2 语音、S7 写实广场、A-0 替身流水线的脚本。F-1、F-2 从这里搬。
