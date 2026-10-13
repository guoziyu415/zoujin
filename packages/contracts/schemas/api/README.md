# JSON Schema for the API (C-1, owned by backend) / API の JSON Schema（C-1、バックエンド担当）

All transport shapes of `docs/backend/api-contract.md` v1.0. Data fields follow `schemas/data/` (C-2, owned by data); they are only referenced here.

`docs/backend/api-contract.md` v1.0 のすべての伝送形状。データフィールドは `schemas/data/`（C-2、データ担当）に従い、ここでは参照するだけ。

| File / ファイル | Contents / 内容 |
| ----------------------- | ---- |
| `common.schema.json` | Shapes shared in several places: snapshot (2.3), visible projection of events (2.4), causal chain (2.6), memories and promises (2.7, 3.4), end of act (3.11), ending presentation (3.13), resume play (section 4) / 複数箇所で共有される形状：スナップショット（2.3）、イベントの可視射影（2.4）、因果チェーン（2.6）、記憶と約束（2.7、3.4）、幕末（3.11）、結末演出（3.13）、続きからのプレイ（第 4 節） |
| `ws/client.schema.json` | The 17 message kinds of 3.2, as a whole a `oneOf` discriminated by `type` (`ClientMessage`) / 3.2 の 17 種のメッセージ。全体は `type` で区別する `oneOf`（`ClientMessage`） |
| `ws/server.schema.json` | The 30 message kinds of 3.3 (`ServerMessage`) / 3.3 の 30 種のメッセージ（`ServerMessage`） |
| `rest/*.schema.json` | One file per endpoint; `x-endpoint` records method, path, whether `Idempotency-Key` is required, path parameters, query parameters, request body and the response for each status code (`null` = no response body) / エンドポイントごとに 1 ファイル。`x-endpoint` にメソッド、パス、`Idempotency-Key` の要否、パスパラメータ、クエリパラメータ、リクエストボディ、各ステータスコードのレスポンスを記す（`null` = レスポンスボディなし） |
| `error.schema.json` | Errors of section 5 / 第 5 節のエラー |
| `telemetry.schema.json` | Request body of `POST /v1/telemetry` (data-design 9.3, fields set by data) / `POST /v1/telemetry` のリクエストボディ（data-design 9.3、フィールドはデータ側が決める） |
| `binary.json` | Binary frame constants of 3.1 (not a Schema; generates `binary.ts` / `binary.py`) / 3.1 のバイナリフレーム定数（Schema ではない。`binary.ts` / `binary.py` を生成する） |

## Conventions / 書き方

- JSON Schema 2020-12; `$id` is a path relative to `schemas/`, and `$ref` uses relative references only.
  JSON Schema 2020-12。`$id` は `schemas/` からの相対パス、`$ref` は相対参照のみを使う。
- Objects always use `additionalProperties: false` and never `allOf` (tests check this). To add fields later, change them here first.
  オブジェクトは常に `additionalProperties: false` とし、`allOf` は使わない（テストで検査する）。今後フィールドを追加するときは、まずここを変更する。
- Closing objects only constrains the writing side: messages and responses sent by the server, mocks, and messages sent by the frontend. The reading side, per api-contract section 0, ignores unknown fields, message types and enum values, and does not validate the other side's messages against the Schema at runtime (an old frontend cached by the Service Worker will connect to a new server). Generated pydantic models are `extra="forbid"`; when the server parses client messages it first strips unknown fields and then validates (B-0).
  閉じるのは書く側だけを拘束する：サーバーが送るメッセージとレスポンス、mock、フロントエンドが送るメッセージ。読む側は api-contract 第 0 節に従い、未知のフィールド、メッセージタイプ、列挙値を無視し、実行時に Schema で相手のメッセージを検証しない（Service Worker にキャッシュされた古いフロントエンドが新しいサーバーに接続するため）。生成される pydantic モデルは `extra="forbid"`。サーバーはクライアントメッセージを解析するとき、まず未知のフィールドを取り除いてから検証する（B-0）。
- Where a data type is used whole, `$ref` the `$defs` in `data/`. Where the API adds or removes fields on a data type (endings, visible projection of events, 記憶帳), write it as the API's own object, and reference the shared fields from the data side via JSON pointers; which fields were added or removed is listed in `tests/test_alignment.py`.
  データ型をそのまま使う箇所では `data/` の `$defs` を `$ref` する。API がデータ型のフィールドを加減する場合（結末、イベントの可視射影、記憶帳）は API 独自のオブジェクトとして書き、共通のフィールドは JSON ポインタでデータ側のフィールドを参照する。どのフィールドを加減したかは `tests/test_alignment.py` に列挙されている。
- Names in `$defs` are the generated type names and must not collide with those in `data/`.
  `$defs` の名前は生成される型名であり、`data/` のものと重複してはならない。
- Things that exist only in non-production environments (`hello.debug`, `fakeVoice`, `event_rejected`, `POST /v1/test/…`) are still written, with "non-production" marked in `description`.
  非本番環境にのみ存在するもの（`hello.debug`、`fakeVoice`、`event_rejected`、`POST /v1/test/…`）も同様に書き、`description` に「非生産」と記す。
- Where the document was unclear and the point was settled at the C-1 review, mark "（C-1 评审定）" (settled at C-1 review) at the end of `description`; api-contract v1.0.1 has written them into the main text.
  文書に明記がなく C-1 レビューで決めた箇所は、`description` の末尾に「（C-1 评审定）」（C-1 レビューで決定）と記す。api-contract v1.0.1 でそれらは本文に取り込まれている。

After changes, run `uv run contracts-gen` to regenerate the types, then `uv run pytest packages/contracts`.

変更後は `uv run contracts-gen` で型を再生成し、続けて `uv run pytest packages/contracts` を実行する。
