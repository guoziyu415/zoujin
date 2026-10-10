# packages/contracts

前后端和数据共用的契约。后端（api）和数据（data）负责，改这里要后端、前端、数据三方评审（dev-plan 2.3）。

- `schemas/data/`：数据契约的 JSON Schema（C-2）。
- `schemas/api/`：接口的 JSON Schema（C-1），见那里的 README。
- `examples/`：合法例子和反例，契约测试逐个校验（`examples/README.md`）。
- `tests/`：契约测试。
  - 数据（`test_data_schemas.py`）：Schema 对元 Schema 合法、例子、和 `docs/data/contracts.md` 逐个类型对照、对象关死、仓库里的世界模型和评测集按 Schema 校验。
  - 接口（`test_schemas.py`、`test_examples.py`、`test_alignment.py`、`test_generated.py`）：Schema 合法、引用都能解析、和 `docs/backend/api-contract.md` 的消息表对照、例子、和数据契约的枚举和字段对照、生成的类型。
- 生成的类型（不手改，CI 会重新生成并比对）：
  - TypeScript：`src/generated/`，从 `src/index.ts` 按命名空间导出：`import type { Api, Data } from "@zoujin/contracts"`。
  - Python：`src/zoujin_contracts/generated/`（pydantic v2）。WebSocket 消息按 `type` 一次解析：
    `TypeAdapter(api.ClientMessage).validate_json(text)`。
  - 二进制帧常量：`binary.ts`、`binary.py`。

## 命令

```bash
uv run contracts-gen              # 改了 schemas/ 以后重新生成全部类型（要先 pnpm install）
uv run pytest packages/contracts  # Schema、例子、和数据契约的对照、生成的 Python 类型
pnpm typecheck                    # 生成的 TypeScript 类型（含 tests/types-check.ts）
```

生成命令在 `src/zoujin_contracts/codegen.py`（TypeScript 那一步调 `gen/json2ts.mjs`）。
