# JSON Schemas for the data contracts / データ契約の JSON Schema

The 39 types in `docs/data/contracts.md` 1.7, written as JSON Schema 2020-12 (C-2, owned by Data). To change a field, change contracts.md first, then this directory; the contract tests compare both sides type by type and top-level field by top-level field.

`docs/data/contracts.md` 1.7 の 39 個の型を JSON Schema 2020-12 で記述したもの（C-2、データ担当）。フィールドを変更するときは先に contracts.md を変更し、次にここを変更する。契約テストが両者を型ごと、トップレベルフィールドごとに突き合わせる。

| File / ファイル           | Main type / 主な型 | `$defs`                                                                                                                                                                               |
| ------------------------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `common.schema.json`      | —                  | `Cite`, plus shared definitions: `SchemaVersion`, `StoryTime`, `RecordedAt`, the various IDs, etc. / `Cite`、および共通定義：`SchemaVersion`、`StoryTime`、`RecordedAt`、各種 ID など |
| `playthrough.schema.json` | `Playthrough`      | `Playthrough`                                                                                                                                                                         |
| `world-model.schema.json` | `WorldModel`       | The 26 world model types / 世界モデルの 26 個の型                                                                                                                                     |
| `event.schema.json`       | `Event`            | `Event`, `Effect`, `CheckResult`                                                                                                                                                      |
| `utterance.schema.json`   | `Utterance`        | `Utterance`                                                                                                                                                                           |
| `world-state.schema.json` | `WorldState`       | `WorldState`, `RunFact`                                                                                                                                                               |
| `memory.schema.json`      | `MemoryItem`       | `MemoryItem`, `Relationship`, `Promise` (titled `StoryPromise`) / `Promise`（タイトルは `StoryPromise`）                                                                              |
| `ending.schema.json`      | `Ending`           | `Ending`, `CharacterEnding`                                                                                                                                                           |

## For writers / 書き込み側向け

This set of schemas is for strict validation by **the side that writes data**: CI validates world models and eval sets, and B-0 validates events and memories before writing to the database. Objects are always closed (`additionalProperties: false`); any extra field fails.

このスキーマ群は**データを書き込む側**が厳密に検証するためのもの。CI が世界モデルと評価セットを検証し、B-0 がデータベースへ書き込む前にイベントと記憶を検証する。オブジェクトは常に閉じており（`additionalProperties: false`）、余分なフィールドが 1 つでもあれば不合格になる。

The reading side (the frontend) does not use it at runtime to validate data sent by the server. Contracts only grow by addition: when 1.6 adds an optional field or `Activity` gains a value, old clients must not break. The frontend follows contracts.md: an unknown `Activity` is treated as `idle`, and unknown fields are ignored. The F-0 e2e validates messages sent by the mock against the schemas; that checks the mock, which is a writer, so there is no contradiction.

読み取り側（フロントエンド）は、サーバーから届いたデータをランタイムでこのスキーマにより検証しない。契約は追加のみ行う：1.6 でオプションフィールドを追加したり `Activity` に値を追加したりしても、古いクライアントがエラーになってはならない。フロントエンドは contracts.md に従う：未知の `Activity` は `idle` として扱い、未知のフィールドは無視する。F-0 の e2e はモックが送るメッセージをスキーマで検証するが、それは書き込み側であるモックを検査しているので矛盾しない。

## Conventions / 書き方

- `$id` is a relative path (`data/event.schema.json`) and every `$ref` is a relative reference; no domain names, and tests do not touch the network.
  `$id` は相対パス（`data/event.schema.json`）、`$ref` はすべて相対参照。ドメイン名は書かず、テストはネットワークに接続しない。
- Runtime IDs are a prefix plus a ULID (`ev_` plus 26 uppercase Crockford base32 characters); world model IDs are a type prefix plus a lowercase slug (`char.melos`, `exit.1.road`), and world ending IDs have no prefix (`canon-reunion`). Only `pattern` is used, never `format`.
  ランタイム ID は接頭辞に ULID を続けたもの（`ev_` に大文字 Crockford base32 の 26 文字）。世界モデルの ID は型の接頭辞に小文字のスラッグを続けたもの（`char.melos`、`exit.1.road`）。世界エンディングの ID に接頭辞はない（`canon-reunion`）。使うのは `pattern` のみで、`format` は使わない。
- Story time `t` and story minutes (`dt`, travel time, duration of situational actions) are integers; `melosMinutes` carries a sign.
  物語時間 `t` と物語内の分（`dt`、道のり、状況アクションの所要時間）は整数。`melosMinutes` は符号付き。
- Substructures do not get their own `$defs`; when the interface side needs to reuse one verbatim, use a JSON pointer reference (e.g. `ending.schema.json#/$defs/Ending/properties/card`).
  下位構造のために `$defs` を別に立てない。インターフェース側でそのまま再利用する場合は JSON ポインタ参照を使う（例：`ending.schema.json#/$defs/Ending/properties/card`）。
- `sampleLines` is `Cite & { since?, until?, when? }` in the contract; here it is written as a plain closed object, with `source` / `para` / `quote` referencing `Cite`'s fields by JSON pointer, without `allOf`.
  `sampleLines` は契約では `Cite & { since?, until?, when? }`。ここでは閉じた通常のオブジェクトとして書き、`source` / `para` / `quote` は JSON ポインタで `Cite` のフィールドを参照する。`allOf` は使わない。
- The schema only covers shape. Cross-field rules live in `build_world`, worldsim, B-0, and the ending validation: `quote` is an exact substring of the source text, events have non-decreasing `t` by `seq`, `world.outcome` equals the class determined per 2.9, and values set for variables satisfy `valueRequires` (1.6).
  Schema は形だけを扱う。フィールドをまたぐルールは `build_world`、worldsim、B-0、エンディングの検証にある：`quote` は原文の正確な部分文字列であること、イベントは `seq` 順に `t` が減少しないこと、`world.outcome` が 2.9 で判定された区分と等しいこと、変数に設定された値が `valueRequires`（1.6）を満たすこと。
- Fields required per version are written as `if` / `then`, without changing optionals in the types: when an `Ending`'s `schemaVersion` is not 1.0–1.5, `world.title`, `player.didForYou` / `youDid`, `characters`, and `card` are required (1.6, C-17). The `if` lists the old versions, so adding 1.7 later needs no change to it. Generated pydantic models ignore `if` / `then`; it is only checked when B-0 validates against the schema before writing to the database.
  バージョンごとに追加される必須項目は `if` / `then` で書き、型のオプション指定は変更しない：`Ending` の `schemaVersion` が 1.0〜1.5 でない場合、`world.title`、`player.didForYou` / `youDid`、`characters`、`card` が必須（1.6、C-17）。`if` には古いバージョンを列挙するので、今後 1.7 を追加してもここは変更不要。生成された pydantic モデルは `if` / `then` を無視し、B-0 がデータベース書き込み前に Schema で検証するときにだけチェックされる。

## Future changes / 以後の変更

1.5 is frozen; from now on only additions: new optional fields go in 1.6, 1.7, and so on, add one value to `SchemaVersion`, write one line in the contracts.md changelog, and change this directory in the same PR. Adding enum values also counts as an addition: enums the frontend renders by value (`Activity`, `MemoryItem.kind` / `via`, `StoryPromise.status`, `Event.type`, `Affordance.kind`, etc.) may gain values later, and readers must keep a default branch (an unknown `Activity` is treated as `idle`). Removing values, renaming, and tightening constraints are not additions. Changes to `packages/contracts` need review from backend, frontend, and data (dev-plan 2.3).

1.5 は凍結済みで、以後は追加のみ：新しいオプションフィールドは 1.6、1.7… で追加し、`SchemaVersion` に値を 1 つ加え、contracts.md の変更記録に 1 行書き、同じ PR でここを変更する。列挙値の追加も追加とみなす：フロントエンドが値ごとに描画する列挙（`Activity`、`MemoryItem.kind` / `via`、`StoryPromise.status`、`Event.type`、`Affordance.kind` など）には今後値が増える可能性があり、読み取り側は必ずデフォルト分岐を残す（未知の `Activity` は `idle` として扱う）。値の削除、名前の変更、制約の厳格化は追加とみなさない。`packages/contracts` の変更にはバックエンド、フロントエンド、データの 3 者のレビューが必要（dev-plan 2.3）。

Examples are in `packages/contracts/examples/`, and tests are in `packages/contracts/tests/test_data_schemas.py`.

例は `packages/contracts/examples/`、テストは `packages/contracts/tests/test_data_schemas.py` にある。
