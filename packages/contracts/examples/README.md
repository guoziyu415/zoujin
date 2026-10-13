# Contract examples / 契約の例

```
examples/
  valid/data/<type>/*.json     valid examples, must pass / 正しい例。必ず通ること
  invalid/data/<type>/*.json   invalid examples, must fail / 誤った例。必ず通らないこと
  valid/api/…                  valid API examples (C-1); directory rules in "API" below / API の正しい例（C-1）。ディレクトリ規則は下の「API」を参照
  invalid/api/…                invalid API examples (C-1) / API の誤った例（C-1）
```

`<type>` is the name in the schema's `$defs` (`Event`, `Effect`, `Ending`…); tests use it to find the matching definition to validate against.

`<type>` はスキーマの `$defs` の名前（`Event`、`Effect`、`Ending`…）。テストはこれで対応する定義を見つけて検証する。

All valid examples (data and API) must also be parsed by the generated pydantic models and exported back identical to the original file (C-1, `tests/test_examples.py`).

すべての正しい例（データと API）は、生成された pydantic モデルでパースしてから書き出しても、元のファイルと同一でなければならない（C-1、`tests/test_examples.py`）。

## Data contracts (C-2) / データ契約（C-2）

**Valid examples**: at least 1 for each main type, 1 for each of the 8 kinds of `Effect`, plus `Promise`, `RunFact`, `Relationship` and `CharacterEnding`. `WorldModel` has no separate example; tests validate `worlds/*/*/world.json` directly.

**正しい例**：主要な型ごとに少なくとも 1 つ、`Effect` の 8 種類にそれぞれ 1 つ、さらに `Promise`、`RunFact`、`Relationship`、`CharacterEnding`。`WorldModel` には別途例を書かず、テストが `worlds/*/*/world.json` を直接検証する。

The JSON in section 6 of contracts.md was copied in as is: `Fact/fact-promise.json`, `Beat/beat-11-wedding.json`, `CausalEdge/edge-10-11.json`, `Event/say-mock-king.json`, `Event/promise-made.json`. These were filled in:

contracts.md 第 6 節の JSON はそのまま写した：`Fact/fact-promise.json`、`Beat/beat-11-wedding.json`、`CausalEdge/edge-10-11.json`、`Event/say-mock-king.json`、`Event/promise-made.json`。次の点を補った：

- IDs with ellipses (`ev_01J…`, `pt_01J…`, `turn_01J…`, `utt_01J…`, `prm_01J…`) were completed to full 26-character ULIDs; `idempotencyKey` follows.
  省略記号付きの ID（`ev_01J…`、`pt_01J…`、`turn_01J…`、`utt_01J…`、`prm_01J…`）を完全な 26 桁の ULID に補った。`idempotencyKey` もそれに合わせた。
- `"reason": null` was removed from `say-mock-king.json`: the type is `reason?: string`, which does not allow `null`. Section 6 of contracts.md dropped it in the same PR.
  `say-mock-king.json` から `"reason": null` を削除した：型は `reason?: string` で、`null` は許されない。contracts.md 第 6 節も同じ PR で削除した。
- The second event is only a fragment in the document; it was completed into a full Event: `schemaVersion: "1.1"`, `eventId`, `playthroughId`, `turnId`, `idempotencyKey`, `worldModelVersion`, `recordedAt`; the `checker` value `rules@1.1+…` became `rules@1.1+gemini-3.8-flash`.
  二つ目のイベントは文書では断片にすぎないため、完全な Event に補った：`schemaVersion: "1.1"`、`eventId`、`playthroughId`、`turnId`、`idempotencyKey`、`worldModelVersion`、`recordedAt`。`checker` の `rules@1.1+…` は `rules@1.1+gemini-3.8-flash` にした。

The Japanese in the examples uses sentences already in contracts.md and `world.json`, or neutral sentences written for the purpose; there are no real names or personal information.

例の中の日本語は、contracts.md や `world.json` にすでにある文、または中立的に自作した文を使っており、実在の人名や個人情報は含まない。

**Invalid examples**: each one changes exactly one thing in some valid example. `INVALID_BECAUSE` in `tests/test_data_schemas.py` states where each invalid example should be rejected and by which keyword; when adding one, add a line there, so it is not rejected for another reason and fails to test what was intended.

**誤った例**：それぞれ、ある正しい例の一か所だけを変えたもの。`tests/test_data_schemas.py` の `INVALID_BECAUSE` に、各誤り例がどの位置でどのキーワードにより拒否されるべきかを書いてある。新しく追加するときはそこに 1 行足すこと。別の理由で拒否されて、意図した検証ができなくなるのを防ぐ。

## API (C-1) / API（C-1）

The paths below are all under `valid/api/` and `invalid/api/`. The directory decides which schema is validated against:

以下のパスはすべて `valid/api/`、`invalid/api/` の下にある。ディレクトリによって、どのスキーマで検証するかが決まる：

| Path / パス                                                                                                                                                                  | Validated against / 検証対象                                                                                                                                                                                              |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ws/client/<type>/*.json`, `ws/server/<type>/*.json`                                                                                                                         | That one message kind, and the whole `ClientMessage` / `ServerMessage` union; the directory name is the `type` / そのメッセージ 1 種類と、`ClientMessage` / `ServerMessage` ユニオン全体。ディレクトリ名がそのまま `type` |
| `rest/<endpoint file name>/<request \| query \| params \| status code>/*.json` / `rest/<エンドポイントのファイル名>/<request \| query \| params \| ステータスコード>/*.json` | The schema named in `x-endpoint` of `schemas/api/rest/<endpoint file name>.schema.json` / `schemas/api/rest/<エンドポイントのファイル名>.schema.json` の `x-endpoint` に書かれたスキーマ                                  |
| `<file>/<$defs name>/*.json` (e.g. `error/ErrorResponse/`) / `<ファイル>/<$defs 名>/*.json`（例 `error/ErrorResponse/`）                                                     | That `$defs` entry in `schemas/api/<file>.schema.json` / `schemas/api/<ファイル>.schema.json` のその `$defs` 項目                                                                                                         |

Every WebSocket message kind, every REST status code that has a response body, and every request body has at least one valid example (tests check this). Each invalid example is wrong in exactly one place; `INVALID_BECAUSE` in `tests/test_examples.py` states where each should be rejected and by which keyword; when adding one, add a line there.

すべての WebSocket メッセージ種別、レスポンスボディを持つすべての REST ステータスコード、すべてのリクエストボディに、少なくとも 1 つの正しい例がある（テストが確認する）。誤った例は、それぞれ一か所だけ誤っている。`tests/test_examples.py` の `INVALID_BECAUSE` に、各誤り例がどの位置でどのキーワードにより拒否されるべきかを書いてある。新しく追加するときはそこに 1 行足すこと。

### Examples copied from api-contract and what was filled in / api-contract から写した例と補った点

File names with `doc-<section number>` are JSON examples copied as is from `docs/backend/api-contract.md`. The `…` in the document was filled with valid values as below; no other fields were changed.

ファイル名に `doc-<節番号>` が付いているものは、`docs/backend/api-contract.md` の JSON 例をそのまま写したもの。文書中の `…` は下記のとおり正しい値で補い、他のフィールドは変えていない。

- **IDs**: `pt_01J…`, `turn_…`, `ev_…`, `ev_A`, `ev_B`, `mem_…`, `prm_…`, `rev_…`, `end_…`, `draft_…`, `plan_…`, `u_01J…` were all completed to ULIDs of the form "prefix + `01K7AZ` + 20 digits" (e.g. `ev_01K7AZ00000000000000000041`). The `…` in `clientMsgId` became a UUID.
  **ID**：`pt_01J…`、`turn_…`、`ev_…`、`ev_A`、`ev_B`、`mem_…`、`prm_…`、`rev_…`、`end_…`、`draft_…`、`plan_…`、`u_01J…` はすべて「プレフィックス + `01K7AZ` + 20 桁の数字」の ULID に補った（例：`ev_01K7AZ00000000000000000041`）。`clientMsgId` の `…` は UUID にした。
- **2.1 manifest**: `roles[].summary` was filled with 「シラクスの市に着いたばかりの旅の者。」; the `"…"` in `prerecorded` became a full set of 3 backchannel lines (うむ。／ああ。／なるほど。), 2 "couldn't hear" lines and 1 "wait a moment" line, each with `url`, `text` and `durationMs`.
  **2.1 manifest**：`roles[].summary` に「シラクスの市に着いたばかりの旅の者。」を補った。`prerecorded` の `"…"` は、相づち 3 文（うむ。／ああ。／なるほど。）、聞き取れなかった場合 2 文、少し待ってほしい場合 1 文に補い、各文に `url`、`text`、`durationMs` を付けた。
- **2.2 start**: the `snapshot` of the 201 uses the example from 2.3.
  **2.2 開始**：201 の `snapshot` には 2.3 の例を使った。
- **2.8 ending**: `world.epilogue[].sentence` was filled with 「メロスは日没の直前に刑場へ駆け込んだ。」; `characters[0].yours[].sentence` with 「工房の火を落とさずに、メロスを待ち続けた。」; the `"…"` in `card.characterLines` became two lines (section 5 of the data contract requires 2–3 lines; the document's example has only one).
  **2.8 エンディング**：`world.epilogue[].sentence` に「メロスは日没の直前に刑場へ駆け込んだ。」、`characters[0].yours[].sentence` に「工房の火を落とさずに、メロスを待ち続けた。」を補った。`card.characterLines` の `"…"` は 2 文にした（データ契約の第 5 節は 2〜3 文を要求するが、文書の例は 1 文だけ）。
- **3.4 commit**: `events` uses the event from 2.4 (sequence number changed to 44); `patch.actions.add` was filled with one action, 「様子を見る」; `reveal.chain` uses the chain from 2.6.
  **3.4 commit**：`events` には 2.4 のイベントを使った（通し番号は 44 に変更）。`patch.actions.add` には「様子を見る」という行動を一つ補った。`reveal.chain` には 2.6 のチェーンを使った。
- **3.11 end of the act**: `act_ended.recapLines` was filled out to two lines (the text says 2–4 lines; the example has only one). The destination with `enRoute` is placed separately in `doc-3.11-en-route.json`, with the act number and `recapLines` filled in. `act_transition.snapshot` uses the snapshot from 2.3, changed to the start of the second act.
  **3.11 幕末**：`act_ended.recapLines` を 2 行に補った（本文は 2〜4 行とあるが、例は 1 行だけ）。`enRoute` を持つ行き先は `doc-3.11-en-route.json` に分けて置き、幕番号と `recapLines` は補ったもの。`act_transition.snapshot` には 2.3 のスナップショットを使い、第二幕の冒頭に変更した。
- **Section 4 welcome**, **3.13 ending presentation**, **section 5 errors**, **the remaining examples of 2.3–2.7**: only IDs were filled in.
  **第 4 節 welcome**、**3.13 エンディング演出**、**第 5 節 エラー**、**2.3〜2.7 のその他の例**：ID だけを補った。

Examples not starting with `doc-` were written by hand; their Japanese uses only sentences already in the document or neutral sentences, with no real names or personal information.

`doc-` で始まらない例は自作したもの。日本語は文書にすでにある文か中立的な文だけを使い、実在の人名や個人情報は含まない。
