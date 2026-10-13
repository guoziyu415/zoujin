# fixtures/mock/rest: mock REST fixtures (B-1) / mock の REST 固定データ（B-1）

The mock REST (`services/backend/src/zoujin_backend/mock/rest.py`) replies with the data here, validated against `packages/contracts/schemas/api/rest/` before sending; if it fails, it returns 500 and reports the error in the terminal. The content is the same playthrough as the walkthrough in `fixtures/sessions/`: what the traveler tells King メロス, helping 老爺 push the cart, promising to be メロス's helper, and staying in the city until sunset on the third day.

mock の REST（`services/backend/src/zoujin_backend/mock/rest.py`）はここのデータを返す。送出前に `packages/contracts/schemas/api/rest/` で検証し、通らなければ 500 を返してターミナルにエラーを出す。内容は `fixtures/sessions/` のウォークスルーと同じ一局：旅人がメロス王に告げたこと、老爺の荷車を押す手伝い、メロスの助っ人になる約束、三日目の日没まで市に残ること。

| File / ファイル | Endpoint (api-contract) / エンドポイント（api-contract） | What the mock additionally does / mock が別途行うこと |
|---|---|---|
| `me.json` | `GET /v1/me`, login response (1, 2.0) / `GET /v1/me`、ログインのレスポンス（1、2.0） | `activePlaythrough` and remaining voice minutes are filled in from the playthrough of this Cookie / `activePlaythrough` と残り音声分数はこの Cookie の局から実行時に埋める |
| `snapshot.json` | Snapshot at playthrough start (2.2, 2.3) / 開局時のスナップショット（2.2、2.3） | Later snapshots = this plus the `commit.patch` and `act_transition` pushed so far; `lastSeq`, `pending`, `voice` are filled in live / 以降のスナップショット = これに送出済みの `commit.patch` と `act_transition` を加えたもの。`lastSeq`、`pending`、`voice` は実行時に埋める |
| `timeline.json` | `GET …/timeline` (2.5) | `lastSeq` is filled in live / `lastSeq` は実行時に埋める |
| `why.json` | `GET …/why` (2.6) | `target` follows the query; events pushed in this playthrough, with `seq` replaced by the real value / `target` は query に従う。この局で送出済みのイベント、`seq` は実際の値に置換 |
| `memories.json` | `GET …/memories` (2.7) | Deleted memories are removed; if a memory of a promise is deleted, that promise becomes `voided`, and the relationship follows the response at deletion time / 削除済みの記憶は除く。約束の記憶を削除すると、その約束は `voided` になり、関係は削除時のレスポンスに従う |
| `memory-impact.json` | `GET …/memories/{memoryId}/impact` (2.7) | Keyed by memory name; unknown memories return 404 / 記憶の名前をキーとする。未知の記憶は 404 |
| `memory-delete.json` | `DELETE …/memories/{memoryId}` (2.7) | Same as above; deleting an already-deleted one returns 404; rebuilds that character's session (`session_preparing reason: rebuild`) / 同上。削除済みを再削除すると 404。その人物のセッションを再構築する（`session_preparing reason: rebuild`） |
| `ending.json` | `GET …/ending` (2.8) | 404 before the ending sequence starts, 202 before `ending_ready`, 200 after / 結末演出の開始前は 404、`ending_ready` 前は 202、その後は 200 |

The manifest (2.1) also does not rely on fixtures: it uses the same generator as the production gateway (`services/backend/src/zoujin_backend/manifest.py`, B-7), generated live from the slice's world model, the voice manifest in `assets/voice` (without it, no pre-recorded lines are included) and the scene packages in `assets/scenes`, with the same response headers (`ETag`, 304).

manifest（2.1）も固定データに頼らない。正式ゲートウェイと同じジェネレーター（`services/backend/src/zoujin_backend/manifest.py`、B-7）で、スライスの世界モデル、`assets/voice` の音声マニフェスト（なければ収録済みの台詞は含めない）、`assets/scenes` のシーンパッケージから実行時に生成し、レスポンスヘッダー（`ETag`、304）も同じ。

Not fixture-based: `POST /v1/auth/login` (accepts only the invite code `mock`; returns 429 after 5 consecutive failures), `logout`, `POST /v1/playthroughs` (one in-progress playthrough per Cookie; starting another returns 409), `events` (events from the `commit`s pushed so far), `DELETE /v1/playthroughs/{id}` (open connections are closed with 4004), `telemetry` (validated then discarded), `POST /v1/test/playthroughs/{id}/advance` (pushes a `commit` carrying only the clock).

固定データに頼らないもの：`POST /v1/auth/login`（招待コード `mock` のみ受け付け、5 回連続で間違えると 429）、`logout`、`POST /v1/playthroughs`（Cookie ごとに進行中の局は一つ、再度開くと 409）、`events`（送出済みの `commit` 内のイベント）、`DELETE /v1/playthroughs/{id}`（開いている接続は 4004 で閉じる）、`telemetry`（検証後に破棄）、`POST /v1/test/playthroughs/{id}/advance`（時計だけを載せた `commit` を送出）。

Placeholders are the same as in the scenarios: `{{id:<prefix>:<name>}}` is the runtime ID for that name in this playthrough, shared with the scenarios, so the event IDs referenced by `/memories` and `/ending` are the ones pushed. `{{playthroughId}}`, `{{userRef}}`, `{{memoryId}}` are filled in by the mock.

プレースホルダーはシナリオと同じ：`{{id:<prefix>:<name>}}` はこの局におけるその名前の実行時 ID で、シナリオと共用する。そのため `/memories`、`/ending` が参照するイベント ID は送出済みのものになる。`{{playthroughId}}`、`{{userRef}}`、`{{memoryId}}` は mock が埋める。

## Control endpoints (mock only, not in the contract) / 制御インターフェース（mock 専用、契約には含めない）

| Endpoint / エンドポイント | What it does / 内容 |
|---|---|
| `GET /__mock/scenarios` | The current scenario and all scenario names / 現在のシナリオと全シナリオ名 |
| `POST /__mock/scenario {"name": …}` | Switch scenario (see `fixtures/sessions/README.md`) / シナリオを切り替える（`fixtures/sessions/README.md` を参照） |
| `POST /__mock/expire-session` | Invalidate the current Cookie: afterwards REST returns 401 and WebSocket closes with 4001 (open ones are closed too) / 現在の Cookie を失効させる：以降 REST は 401、WebSocket は 4001 で閉じる（開いているものも閉じる） |
| `POST /__mock/drop` | Disconnect the current Cookie's connection without sending `goaway` or a close frame (the client sees 1006), simulating a network drop / 現在の Cookie の接続を `goaway` も close フレームもなしで切断する（クライアントには 1006 と見える）。ネットワーク切断の模擬 |
| `POST /__mock/reset` | Clear all sessions and playthroughs (used at the start of each end-to-end test case) / 全セッションと局をクリアする（エンドツーエンドテストの各ケース冒頭で使う） |
