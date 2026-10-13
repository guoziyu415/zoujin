# packages/contracts

Contracts shared by frontend, backend and data. Owned by backend (api) and data; changes here need review from backend, frontend and data (dev-plan 2.3).

フロントエンド・バックエンド・データで共有する契約。バックエンド（api）とデータが担当し、ここを変更するにはバックエンド・フロントエンド・データの三者レビューが必要（dev-plan 2.3）。

- `schemas/data/`: JSON Schemas for the data contracts (C-2).
  データ契約の JSON Schema（C-2）。
- `schemas/api/`: JSON Schemas for the API (C-1), see the README there.
  API の JSON Schema（C-1）。そこの README を参照。
- `examples/`: valid examples and counterexamples, each validated by the contract tests (`examples/README.md`).
  有効な例と反例。契約テストが一つずつ検証する（`examples/README.md`）。
- `tests/`: contract tests.
  契約テスト。
  - Data (`test_data_schemas.py`): schemas are valid against the meta-schema, examples, type-by-type comparison with `docs/data/contracts.md`, objects closed, and the repo's world models and eval set validated against the schemas.
    データ（`test_data_schemas.py`）：スキーマがメタスキーマに対して有効であること、例、`docs/data/contracts.md` との型ごとの照合、オブジェクトの閉鎖、リポジトリ内の世界モデルと評価セットのスキーマ検証。
  - API (`test_schemas.py`, `test_examples.py`, `test_alignment.py`, `test_generated.py`): schemas are valid, all references resolve, comparison with the message table in `docs/backend/api-contract.md`, examples, comparison with the data contract's enums and fields, and generated types.
    API（`test_schemas.py`、`test_examples.py`、`test_alignment.py`、`test_generated.py`）：スキーマが有効であること、参照がすべて解決できること、`docs/backend/api-contract.md` のメッセージ表との照合、例、データ契約の列挙型・フィールドとの照合、生成された型。
- Generated types (do not edit by hand; CI regenerates and compares them):
  生成された型（手で編集しない。CI が再生成して比較する）：
  - TypeScript: `src/generated/`, exported by namespace from `src/index.ts`: `import type { Api, Data } from "@zoujin/contracts"`.
    TypeScript：`src/generated/`。`src/index.ts` から名前空間ごとにエクスポートする：`import type { Api, Data } from "@zoujin/contracts"`。
  - Python: `src/zoujin_contracts/generated/` (pydantic v2). WebSocket messages are parsed in one step by `type`:
    Python：`src/zoujin_contracts/generated/`（pydantic v2）。WebSocket メッセージは `type` で一度にパースする：
    `TypeAdapter(api.ClientMessage).validate_json(text)`.
  - Binary frame constants: `binary.ts`, `binary.py`.
    バイナリフレーム定数：`binary.ts`、`binary.py`。

## Commands / コマンド

```bash
uv run contracts-gen              # Regenerate all types after changing schemas/ (run pnpm install first) / schemas/ を変更したら全型を再生成（先に pnpm install）
uv run pytest packages/contracts  # Schemas, examples, comparison with data contracts, generated Python types / スキーマ、例、データ契約との照合、生成された Python 型
pnpm typecheck                    # Generated TypeScript types (incl. tests/types-check.ts) / 生成された TypeScript 型（tests/types-check.ts を含む）
```

The generation command is in `src/zoujin_contracts/codegen.py` (the TypeScript step calls `gen/json2ts.mjs`).

生成コマンドは `src/zoujin_contracts/codegen.py` にある（TypeScript の工程は `gen/json2ts.mjs` を呼ぶ）。
