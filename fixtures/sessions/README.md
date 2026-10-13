# fixtures/sessions: mock session scripts / モックのセッション台本 (B-1)

`uv run zoujin-mock` (or `docker compose up mock`) replays WebSocket sessions according to the scripts here. One file per script, one step per line (JSON Lines). A script follows the playthrough, not the connection: while disconnected the script keeps advancing, `commit`s are recorded, and they are resent when the client reconnects with `hello { lastSeq }`.

`uv run zoujin-mock`（または `docker compose up mock`）は、ここにある台本に従って WebSocket セッションを再生する。1ファイルが1台本で、1行が1ステップ（JSON Lines）。台本は接続ではなく周回に付随する。切断中も台本は進み続け、`commit` は記録され、再接続時に `hello { lastSeq }` が送られると再送される。

Choosing a script: `--scenario <name>` at startup (default `tour`), or `POST /__mock/scenario {"name": "<name>"}`. After switching, newly started playthroughs use it, and a running playthrough restarts with the new script from the beginning (already sent `commit`s are kept and sequence numbers continue). `GET /__mock/scenarios` lists them all.

台本の選択：起動時の `--scenario <名前>`（デフォルトは `tour`）、または `POST /__mock/scenario {"name": "<名前>"}`。切り替え後に新しく始めた周回がそれを使い、実行中の周回は新しい台本を最初から実行する（送信済みの `commit` は残り、番号は続きから進む）。`GET /__mock/scenarios` で全件を列挙する。

The `note` on the first line of each script says what the player should do. Input outside the script is ignored by the mock, with one line logged in the terminal.

各台本の1行目の `note` に、プレイヤーがすることが書いてある。台本にない入力は mock が無視し、ターミナルに1行記録する。

## Scripts / 台本

The 11 kinds in api-contract section 7, the 5 edge cases from the B-1 card, plus one "future message" and the fixed set piece of v1.0.4. The "Character" column is the character to `focus` first.

api-contract 第7節の11種、B-1 カードの5つのエッジケース、さらに「未来のメッセージ」と v1.0.4 の固定演出を加えたもの。「人物」欄は先に `focus` する人物。

| Script / 台本 | Situation / 状況 | Character / 人物 | What the player does / プレイヤーがすること |
|---|---|---|---|
| `full-turn` | A full turn: event, memory, key moment (`reveal` with a causal chain) / 1ターン丸ごと：出来事、記憶、重要な瞬間（因果連鎖つきの `reveal`） | メロス | Say or send one line of text / 一言話すか、文字を一つ送る |
| `small-talk` | Chit-chat: only a `commit` carrying the clock, `turn_settled` is `no_change` / 雑談：時計だけを載せた `commit`、`turn_settled` は `no_change` | 市の老爺 | Say one line / 一言話す |
| `interrupt` | Interruption: `interrupted`, the remaining audio is not sent / 割り込み：`interrupted`、残りの音声は送らない | メロス | Say one line; while he speaks for 6 seconds, press talk again or send text / 一言話す。彼が話している6秒の間にもう一度話すボタンを押すか文字を送る |
| `retract` | Retraction (`retracted`, `too_late`) and recognition correction / 取り消し（`retracted`、`too_late`）と認識の訂正 | 市の老爺 | Within about 4 seconds after the character's answer in turn 1, 「言い直す」; retract again after turn 2 is settled; in turn 3 the caption recognition is wrong, `turn_retract` plus `text { via: "correction" }` / 第1ターンの人物の返答から約4秒以内に「言い直す」。第2ターンが判定済みになった後でもう一度取り消す。第3ターンは字幕の認識が間違っており、`turn_retract` に `text { via: "correction" }` を加える |
| `confirm` | Intent confirmation: answer by button, timeout / 意図の確認：ボタンで回答、タイムアウト | メロス | Say two lines; the original turn first does `commit` (10 minutes) and `turn_settled`, then asks back and pushes `confirm`. The 1st time the character's answer is the question; press the button (waits indefinitely), answering "yes" first pushes the draft's `commit` and then `confirm_closed`; the 2nd time the server starts a turn (`turn_started reason: confirm`) and asks again, no answer is given, and after 30 seconds it times out and only `confirm_closed` is pushed / 二言話す。元のターンがまず `commit`（10分）と `turn_settled` を行い、続いて聞き返して `confirm` を送る。1回目は人物の返答自体が聞き返しで、ボタンを押す（待ち続ける）。「はい」と答えるとまず下書きの `commit` を送り、次に `confirm_closed`。2回目はサーバーがターンを開始し（`turn_started reason: confirm`）再度尋ねる。答えずにいると30秒後にタイムアウトし、`confirm_closed` だけを送る |
| `approach` | A character walks over, followed by an action / 人物が歩み寄り、続いて動作 | 市の老爺 | After receiving `approach`, send `approach_arrived` (or `approach_dismiss`); reply once he speaks; then click the action 「家まで送る」 / `approach` を受け取ったら `approach_arrived`（または `approach_dismiss`）を送る。彼が口を開いたら一言返す。続いて動作「家まで送る」を押す |
| `act-end` | End of act: a `leaving` turn, `act_ended` (destinations carry the subtitle `where`, `sub`), stating a plan, `act_transition` (with landing `arrival`) / 幕末：`leaving` のターン、`act_ended`（行き先に副題 `where`、`sub` を付ける）、意向を話す、`act_transition`（着地 `arrival` つき） | — | You can `act_choose` directly; or first `act_propose` or use voice (`activity_start purpose: "act_plan"`), and after getting a not-viable result and alternative destinations, `act_choose` or state the plan again: the 2nd time it works out (`accepted: true`), immediately followed by `commit` and `act_transition`, landing the same as 「市に残る」. Choosing 「老爺の家に身を寄せる」 makes the landing carry an `opener`: after the landing line is displayed, send `act_landed`, and 老爺 speaks first (`turn_started reason: arrival`) / 直接 `act_choose` してもよい。または先に `act_propose` するか音声（`activity_start purpose: "act_plan"`）を使い、不成立と代替の行き先を受け取った後で `act_choose` するか、もう一度意向を話す。2回目は成立し（`accepted: true`）、直後に `commit` と `act_transition` が来て、着地点は「市に残る」と同じになる。「老爺の家に身を寄せる」を選ぶと着地に `opener` が付く。着地の行を表示し終えたら `act_landed` を送り、老爺が先に口を開く（`turn_started reason: arrival`） |
| `set-piece` | Fixed set piece (3.14): `action_result` carries `setPiece` without `narration`, immediately followed by `set_piece`; the mock's manifest has no recording, only captions are shown / 固定演出（3.14）：`action_result` に `setPiece` を付け `narration` は付けず、直後に `set_piece`。mock の manifest には録音がなく、字幕だけを出す | — | Wait for the mock to add 「戸を叩く」 (`obj.workshop-door`), then click it (`action kind: examine`); click once more to go back to a normal `narration` / mock が「戸を叩く」（`obj.workshop-door`）を追加するのを待って押す（`action kind: examine`）。もう一度押すと通常の `narration` に戻る |
| `goaway` | After `goaway`, closes with 1012; settles during the disconnect; resent on reconnect / `goaway` の後に 1012 で閉じ、切断中に判定が済み、再接続時に再送される | 市の老爺 | Say one line; after it is closed, reconnect per section 4 / 一言話す。閉じられたら第4節に従って再接続する |
| `other-tab` | 4009 | 市の老爺 | Open another connection on the same playthrough; the old one closes with 4009; say one line on the new connection / 同じ周回でもう一つ接続を開くと、古い方が 4009 で閉じられる。新しい接続で一言話す |
| `safety` | `safety_hint`; then `safety_pause` → `safety_resumed` / `safety_hint`、続いて `safety_pause` → `safety_resumed` | 市の老爺 | Say two lines; on the out-of-character card choose 「物語に戻る」 (`safety_resume`) / 二言話す。物語の外に出るカードで「物語に戻る」（`safety_resume`）を選ぶ |
| `ending` | Ending: `cue`, the execution-ground beats, `ending_started`, immediately followed by the closing fixed set pieces (S-087: four `set_piece`s, `piece.storm-in`, `piece.embrace`, `piece.king-asks`, `piece.scarlet-cloak`), and about 4 seconds later `ending_ready` / 結末：`cue`、刑場のビート、`ending_started`、直後に幕を閉じる固定演出（S-087：`set_piece` 4件、`piece.storm-in`、`piece.embrace`、`piece.king-asks`、`piece.scarlet-cloak`）、約4秒後に `ending_ready` | — | Nothing to do; `GET …/ending` returns 202 before, 200 after / 何もしなくてよい。`GET …/ending` は前は 202、後は 200 を返す |
| `late-transcript` | The character's final text arrives later than `turn_complete` (backfilled transcription, `source: "fallback"`) / 人物の確定テキストが `turn_complete` より遅れる（文字起こしの補完、`source: "fallback"`） | 市の老爺 | Say one line / 一言話す |
| `transcript-failed` | The backfilled transcription also fails: `{final: true, text: null, source: "fallback"}` / 補完の文字起こしも失敗：`{final: true, text: null, source: "fallback"}` | 市の老爺 | Say one line / 一言話す |
| `no-audio` | The character makes no sound: `turn_complete { audio: false }`, `no_response` / 人物が声を出さない：`turn_complete { audio: false }`、`no_response` | 市の老爺 | Say one line / 一言話す |
| `degraded` | Degraded to text answers (`session_ready.voiceAvailable: false`) / 文字での回答に縮退（`session_ready.voiceAvailable: false`） | 市の老爺 | Send one line of text / 文字を一つ送る |
| `limits` | 5 minutes of voice left today / 今日の音声が残り5分 | — | Nothing to do / 何もしなくてよい |
| `future-message` | A `type` not in the Schema, followed by a line of narration / スキーマにない `type` が一つ、その後にナレーションが一行 | — | Nothing to do (the frontend should ignore messages it does not recognize) / 何もしなくてよい（フロントエンドは未知のメッセージを無視すべき） |
| `tour` | Tour: everything above except `other-tab`, chained into one playthrough in the order `full-turn`, `small-talk`, `approach`, `set-piece`, `confirm`, `interrupt`, `retract`, `late-transcript`, `transcript-failed`, `no-audio`, `safety`, `goaway`, `limits`, `future-message`, `act-end`, `degraded`, `ending` / ツアー：上記から `other-tab` を除く全部を、`full-turn`、`small-talk`、`approach`、`set-piece`、`confirm`、`interrupt`、`retract`、`late-transcript`、`transcript-failed`、`no-audio`、`safety`、`goaway`、`limits`、`future-message`、`act-end`、`degraded`、`ending` の順に一つの周回につなげたもの | | Follow each segment / 各区間に従う |

Replies the mock makes by itself, not driven by scripts (`services/backend/src/zoujin_backend/mock/ws.py`): `hello` → `welcome` and resent `commit`s; when `lastSeq` is no later than the most recent act transition and there has been no commit since, that `act_transition` is pushed again (with `act_plan_result` when the plan worked out, api-contract section 4, v1.0.12); `ping` → `pong`; `near`, `focus` → `session_preparing` / `session_ready` (warm-up 800 ms, rebuild 1 second, the first after a reconnect is `reconnect`); `turn_retract` → `turn_retract_result` (a retraction before settlement also pushes `turn_settled retracted` and rebuilds the session); `activity_start` or `text` received while the character is sending audio → `interrupted`; a message that does not match the Schema → `error invalid_request`; `act_choose` choosing a destination not in this act end → `error invalid_choice`; a `confirm_answer` that does not match the current confirmation (arriving after the timeout) is ignored.

台本に頼らず mock が自分で返すもの（`services/backend/src/zoujin_backend/mock/ws.py`）：`hello` → `welcome` と再送する `commit`。`lastSeq` が直近の幕切り替え以前で、その後に提出がない場合は、その `act_transition` を再度送る（意向が成立した場合は `act_plan_result` も一緒に。api-contract 第4節、v1.0.12）。`ping` → `pong`。`near`、`focus` → `session_preparing` / `session_ready`（ウォームアップ 800 ms、再構築 1秒、再接続後の最初は `reconnect`）。`turn_retract` → `turn_retract_result`（判定前の取り消しでは `turn_settled retracted` も送り、セッションを再構築する）。人物が音声を送っている間に `activity_start` または `text` を受け取ると `interrupted`。スキーマに合わないメッセージ → `error invalid_request`。`act_choose` がこの幕末にない行き先を選んだ場合 → `error invalid_choice`。現在の確認に対応しない `confirm_answer`（タイムアウト後に届いたもの）は無視する。

## Line format / 一行の書き方

```json
{"on": "activity_end", "delayMs": 120, "send": {"type": "narration", "line": "日が傾いてきた。"}}
```

| Key / キー | Meaning / 意味 |
|---|---|
| `on` | First wait for one of these message types from the frontend (a string or an array; `"turn"` = `activity_end` or `text`). The message received is called the "trigger message"; the lines from this one to the next line with `on` form a group / まずフロントエンドからこれらのメッセージのどれかが来るのを待つ（文字列または配列。`"turn"` = `activity_end` または `text`）。受け取ったものを「トリガーメッセージ」と呼び、この行から次の `on` 付きの行までが一つのグループ |
| `timeoutMs` | Used with `on`: if nothing arrives after this long, the group starts with `{"type": "timeout"}` / `on` と併用：この時間待っても来なければ、`{"type": "timeout"}` でグループを開始する |
| `if` | `{variable: value or list of values}`; the line runs only if all are satisfied (a line with `on` does not wait if unsatisfied). See the placeholders below for variables / `{変数: 値または値のリスト}`。すべて満たしたときだけこの行を実行する（`on` 付きの行は満たさなければ待たない）。変数は下のプレースホルダーを参照 |
| `when` | `voice` or `text`: runs only if this group was triggered by voice or by text / `voice` または `text`：このグループが音声起点か文字起点かで、一致するときだけ実行する |
| `delayMs` | How long to wait before doing it (multiplied by `--speed`) / 実行前に待つ時間（`--speed` を掛ける） |
| `newServerTurn` | The server starts a turn: allocates a new `turnId` and a `turnSeq` with the top bit 1 (3.1); afterwards `{{turnId}}` and `{{turnSeq}}` in this group refer to it / サーバーがターンを開始する：新しい `turnId` と最上位ビットが 1 の `turnSeq` を割り当てる（3.1）。以後このグループの `{{turnId}}`、`{{turnSeq}}` はそれを指す |
| `send` | Send one server message. Before sending it is constructed with the types generated by `packages/contracts` and validated against the Schema; if it fails, it is not sent and an error is reported in the terminal / サーバーメッセージを一つ送る。送信前に `packages/contracts` が生成した型で構築し、スキーマで検証する。通らなければ送らずにターミナルへエラーを出す |
| `unchecked` | Used with `send`: skip the self-check. Only `future-message` uses it / `send` と併用：自己検査を省略する。`future-message` だけが使う |
| `hidden` | Used with `send` (`commit`): how many events in this commit are invisible to the player; they take up `seq` but are not pushed (3.4). If omitted: a commit with no visible events counts as 1 / `send`（`commit`）と併用：この提出のうちプレイヤーに見えない出来事の数。`seq` は消費するが送信しない（3.4）。省略時：見える出来事がない提出は1件として数える |
| `audio` | `{"seconds": 2.4, "chunkMs": 40}`: sends synthesized 24 kHz character audio under this group's `turnSeq` (3.1); stops if interrupted, retracted, or disconnected / `{"seconds": 2.4, "chunkMs": 40}`：このグループの `turnSeq` で合成した 24 kHz の人物音声を送る（3.1）。割り込み、取り消し、切断で止まる |
| `close` | `{"code": 1012, "reason": "…"}`: close the current connection / 現在の接続を閉じる |
| `set` | `{name: value}`: script variables, read afterwards with `{{var.name}}` and `if` / 台本変数。以後 `{{var.名前}}` と `if` で読む |
| `include` | Insert another script verbatim here (this line may contain only `include` and `note`) / 別の台本をそのままここに挿入する（この行には `include` と `note` しか書けない） |
| `note` | A description, not read by the mock / 説明。mock は読まない |

A line does only one thing (one of `send`, `audio`, `close`, `set`, `include`). Once the turn that holds this group's trigger message is retracted, the remaining lines of this group are not run (3.6).

1行がすることは一つだけ（`send`、`audio`、`close`、`set`、`include` のどれか）。このグループのトリガーメッセージが属するターンが取り消された後は、このグループの残りの行は実行しない（3.6）。

**Placeholders** `{{name}}`, `{{name|default}}`: when the whole string is a single placeholder it is replaced by the raw value (number, `null`); when embedded in a string it is replaced by text.

**プレースホルダー** `{{名前}}`、`{{名前|デフォルト値}}`：文字列全体が一つのプレースホルダーのときは元の値（数値、`null`）に置き換え、文字列に埋め込まれているときは文字に置き換える。

| Name / 名前 | Value / 値 |
|---|---|
| `turnId`, `turnSeq` | This group's turn: sent by the frontend, or allocated by `newServerTurn` / このグループのターン：フロントエンドが送ったもの、または `newServerTurn` が割り当てたもの |
| `playerTurnId` | The most recent turn started by the player (after a turn the server inserted, use it to attribute `commit` and `turn_settled` back to the player's turn) / 直近でプレイヤーが開始したターン（サーバーが挟んだターンの後で、`commit` と `turn_settled` をプレイヤーのターンに戻して記録するのに使う） |
| `serverTurnId`, `serverTurnSeq` | The most recent turn started by the server / 直近でサーバーが開始したターン |
| `interrupted` | Whether this group's turn was interrupted by the player (`true` / `false`) / このグループのターンがプレイヤーに割り込まれたかどうか（`true` / `false`） |
| `trigger.<field>` | A field of the trigger message, e.g. `trigger.optionId`, `trigger.clientMsgId`, `trigger.type` / トリガーメッセージのフィールド。例：`trigger.optionId`、`trigger.clientMsgId`、`trigger.type` |
| `var.<name>` | A variable set by `set` / `set` で設定した変数 |
| `id:<prefix>:<name>` | The runtime ID corresponding to this name in this playthrough (`ev`, `mem`, `prm`, `rev`, `draft`, `plan`, `end`…), generated on first use and unchanged afterwards; the REST fixed data uses the same names, so event IDs in `/memories` and `/ending` match the pushed ones. Regenerated when the script is rerun / この周回でこの名前に対応する実行時 ID（`ev`、`mem`、`prm`、`rev`、`draft`、`plan`、`end`…）。初めて使うときに生成し、以後は変わらない。REST の固定データも同じ名前を使うので、`/memories`、`/ending` の出来事 ID は送信済みのものと一致する。台本を再実行すると再生成される |
| `playthroughId`, `roleId`, `lastSeq` | This playthrough's / この周回のもの |
| `t`, `tLabel` | The current story time and its wording / 現在の物語内の時刻とその表現 |
| `t+N`, `tLabel+N` | N minutes later (wording computed from the world model's `clock.labels`). Scripts do not hardcode times, so scripts chain together within the tour / N分後（表現はワールドモデルの `clock.labels` から計算）。台本は時刻を固定しないので、ツアーの中で前後の台本がつながる |

**Filled in by the mock on the fly**: the `fromSeq`, `seq` of `commit` and each event's `seq`; event steps in `reveal.chain` with no `seq` written (looked up by event ID); `playthroughId`, `lastSeq`, `status`, `pending`, `voice` of `act_transition.snapshot`.

**mock が実行時に埋めるもの**：`commit` の `fromSeq`、`seq` と各出来事の `seq`。`reveal.chain` で `seq` が書かれていない出来事ステップ（出来事 ID で探す）。`act_transition.snapshot` の `playthroughId`、`lastSeq`、`status`、`pending`、`voice`。

## Timing / 時間

By default it waits per `delayMs`, preserving realistic intervals (the narrator commits about 3.7 seconds after `turn_complete`, candidate utterances about 1 second). `--speed 0` does not wait at all, for CI; `--speed 2` is twice as slow.

デフォルトでは `delayMs` どおりに待ち、現実的な間隔を保つ（語り手は `turn_complete` の約3.7秒後に提出し、候補の発話は約1秒）。`--speed 0` はまったく待たず、CI 用。`--speed 2` は2倍遅くなる。

Under `--speed 0`, timing-dependent cases take a different path: the character's audio is sent all at once, so interruption cannot happen (no `interrupted`), 「言い直す」 is too late (replies `too_late`), the 2nd confirmation times out immediately, and `GET …/ending` is directly 200. The script still runs to the end and every message still passes the Schema. To walk through these cases with real timing in tests, use a small multiplier (the B-1 tests use `--speed 0.04`).

`--speed 0` では、タイミングに依存するケースは別の経路を通る。人物の音声は一瞬で送り終わるので割り込みは間に合わず（`interrupted` は出ない）、「言い直す」も間に合わず（`too_late` を返す）、2回目の確認はすぐにタイムアウトし、`GET …/ending` は最初から 200 になる。台本は最後まで進み、すべてのメッセージはスキーマを通る。テストでこれらのケースを実際のタイミングで通すには、小さい倍率を使う（B-1 のテストは `--speed 0.04`）。

## Japanese in the scripts / 台本の中の日本語

It is all written for the mock, or follows sentences already in api-contract and ux-design; it contains no words actually spoken by real people, real names, or personal information. Times and arrival estimates are only illustrative; the mock does not compute schedules.

すべて mock のために書いたもの、または api-contract と ux-design に既にある文に従ったもの。実在の人が話した言葉、実名、個人情報は含まない。時刻と到着の見込みは例示にすぎず、mock はスケジュールを計算しない。
