# packages/contracts

前后端和数据共用的契约。后端（api）和数据（data）负责，改这里要后端、前端、数据三方评审（dev-plan 2.3）。

- `schemas/data/`：数据契约的 JSON Schema（C-2）。
- `schemas/api/`：接口的 JSON Schema（C-1）。
- 生成的类型：Python 在 `src/zoujin_contracts/`，TypeScript 在 `src/`。生成物不手改，CI 会重新生成并比对。
