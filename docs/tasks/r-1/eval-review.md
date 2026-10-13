# R-1 eval criteria and cross-review / R-1 評価の基準とクロスレビュー

## Actual coverage boundary / 実際のカバー範囲

- The existing four-act question sets are seeds 100 cases / 388 runs, act 2 37 / 141, act 3 58 / 238 and act 4 53 / 213, for a total of 248 cases / 980 runs, of which 31 cases use whole-game personas. Count by each case's `runs`, not just the number of JSONL lines.
  既存の四幕の問題セットは seeds 100 ケース / 388 回、第 2 幕 37 / 141、第 3 幕 58 / 238、第 4 幕 53 / 213 で、計 248 ケース / 980 回。そのうち 31 ケースは 1 局全体のペルソナを使う。各ケースの `runs` で数え、JSONL の行数だけを数えてはならない。
- The scenario simulation in `check_world.sh` is a deterministic world-rule check, not a game simulated with actual models.
  `check_world.sh` のシナリオシミュレーションは決定論的な世界ルールのチェックであり、実際のモデルによるシミュレーション対局ではない。
- `eval_api` reuses the production narrator, storage and projection; character dialogue goes through the Google text stand-in. A case's `voice` tag does not turn that entry point into a Live voice acceptance check. Anti-spoiler is handled separately by `s3_runtime`, which calls the production Live transport and brief.
  `eval_api` は本番のナレーター、ストレージ、投影を再利用する。登場人物のセリフは Google テキストの代用品を通る。ケースの `voice` タグがあっても、この入口が Live 音声の受け入れ確認になるわけではない。ネタバレ防止は別途 `s3_runtime` が本番の Live transport と brief を呼び出す。
- The `silence` entry point is not implemented yet, so the related cases must be recorded as skipped. Judge calibration remains on hold; the pass rate of deterministic checks cannot stand in for the full E1–E8 model scoring threshold.
  `silence` の入口はまだ実装していないので、関連するケースはスキップとして記録しなければならない。審査員のキャリブレーションは引き続き保留。決定論的チェックの合格率を完全な E1–E8 のモデル採点の閾値の代わりにすることはできない。

## Eval problems already fixed / 修正済みの評価の問題

- The report keeps the pass rate of results already judged, but the threshold must not show as passed in deterministic mode, or when there are skips, missing or duplicate runs, a partial case selection, or missing required scores. Each case explicitly declares its expected number of scorings; cases that never needed a judge may declare 0; a scoring requirement was not imposed on every case. Any deterministic check failure still blocks the threshold from passing outright.
  レポートは判定済みの結果の合格率を残すが、決定論モード、スキップ、欠落や重複した実行、ケースの一部選択、必要な採点の欠落があるときは、閾値を合格と表示してはならない。各ケースは期待する採点回数を明示的に宣言し、もともと judge が不要なケースは 0 と宣言できる。すべてのケースに採点要件を課したわけではない。決定論的チェックの失敗は、いずれも引き続き直ちに閾値の合格を阻む。
- The live AI player makes a new call at every step, and only replay mode reads replays; `freshCalls`, `replayHits` and `bad` are recorded separately, so that old choices or degraded bad output are not counted as new valid samples.
  live の AI プレイヤーはステップごとに新しい呼び出しを行い、replay モードだけがリプレイを読む。`freshCalls`、`replayHits`、`bad` を別々に記録し、古い選択や悪い出力の劣化を新しい有効なサンプルとして数えないようにする。
- The player can answer intent confirmations, read the public projection of the production memory book, and delete memories by public ID; it does not use hidden state or event sources from the inspection API. Deletion still calls the production transaction and checks that the memory belongs to this game.
  プレイヤーは意図の確認に答えられ、本番の記憶帳の公開投影を読み、公開 ID で記憶を削除できる。検査用インターフェースの隠れた状態やイベントのソースは使わない。削除は引き続き本番のトランザクションを呼び出し、このゲームに属することをチェックする。
- The player only hears the set-piece lines actually pushed in this turn, and does not fill in content from the list of future set pieces. The statistics keep the actual action counts and the full ending signatures, so that limited batches can check distribution and persona behavior.
  プレイヤーが聞くのはこのターンで実際にプッシュされた固定演出のセリフだけで、未来の演出リストで内容を補わない。統計には実際のアクション数とエンディングの完全な署名を残し、限られたバッチで分布とペルソナの振る舞いを確認できるようにする。
- The public `actionId` of a context button is now passed all the way from the snapshot to the production narrator. Previously only kind / target were passed, which lost the item semantics carried by the button, so legitimate actions such as handing over water were wrongly rejected; now the player does not have to guess the internal `params.item`.
  状況ボタンの公開 `actionId` を、スナップショットから本番のナレーターまでそのまま渡すようにした。以前は kind / target だけを渡していたので、ボタンが持つアイテムの意味が失われ、水を渡すなどの正当な操作が誤って拒否されていた。今はプレイヤーが内部の `params.item` を推測する必要はない。
- The batch-implementation thread received and fixed review comments about resumes mixing in model configuration, source changes and the key order of signature objects; the anti-spoiler thread received review comments about building the judge context from the same state, execution fingerprints, and flagging costs when usage is missing.
  バッチ実装のスレッドは、再開時にモデル設定やソースの変更が混入する点、署名オブジェクトのキーの順序などについてのレビュー意見を受け取り、修正した。ネタバレ防止のスレッドは、同じ状態から judge のコンテキストを組み立てる点、実行のフィンガープリント、usage が欠けたときの費用のマークについてのレビュー意見を受け取った。

## Layered criteria for request failures, product degradation and diversity / リクエストの失敗、製品の劣化、多様性の階層的な基準

This section first re-checks the existing specifications, and after the stop point the following criteria are implemented; the original ledger is not retroactively rewritten. The original 20-game sample and the later fixed 200-game plan both keep all records; bad games must not be excluded, failed games must not be replaced, and favorable results must not be cherry-picked to refill the denominator.

この節ではまず既存の仕様を再確認し、停止点の後に以下の基準で実装する。元の台帳を遡って書き換えることはしない。元の 20 局のサンプルとその後の固定 200 局の計画は、どちらもすべての記録を残す。悪い局を除外したり、失敗した局を差し替えたり、有利な結果を選んで分母を埋め直したりしてはならない。

- The ending-diversity requirement of [S-061](../../pm/decisions.md) is 20 games for each of 10 fixed personas, 200 games in total; the most common baseline category ≤ 60%, ≥ 8 signatures, and all 5 baseline categories reached. It does not require zero errors on every vendor request. The share of generated endings is also listed separately per [data-design 9.1](../../data/data-design.md).
  [S-061](../../pm/decisions.md) のエンディングの多様性の要件は、固定の 10 ペルソナ各 20 局、計 200 局。最も多いベースライン分類の割合 ≤ 60%、署名 ≥ 8 種類、ベースラインの 5 分類すべてに到達。ベンダーへの各リクエストでエラーがゼロであることは求めていない。生成エンディングの割合も [data-design 9.1](../../data/data-design.md) に従って別に示す。
- S-065 explicitly allows one retry after a call fails, and only takes the product fallback if it fails again. S-019 and data-design 9.1 additionally set a target of < 2% degraded games, with template endings counted separately. When all 200 games have started and are fully measured, strictly less than 2% means at most 3 games; when measurement is incomplete, unknowns cannot be treated as zero.
  S-065 は呼び出しの失敗後に 1 回のリトライを明示的に認め、再び失敗した場合にだけ製品のフォールバックに進む。S-019 と data-design 9.1 はさらに、劣化した局の割合の目標を < 2% とし、テンプレートのエンディングは別に数える。200 局がすべて開始し完全に計測された場合、2% 未満とは最大 3 局を意味する。計測が完全でない場合、不明をゼロとして扱ってはならない。
- data-design 7.3's "no score if more than 5% time out" refers to the time limit for a whole eval case or whole game, not to a single 15-second model request. If whole-game retries are run separately, each attempt must keep its mapping to the original planned sample, and the first timeout must not be deleted; batches under freeze do not get extra automatic reruns added on the fly.
  data-design 7.3 の「タイムアウトの割合が 5% を超えたらスコアを出さない」は、評価のケース全体・1 局全体の制限時間を対象とするもので、1 回の 15 秒のモデルリクエストのことではない。1 局全体のリトライを別途行う場合は、各試行と元の計画サンプルとの対応を残し、最初のタイムアウトを削除してはならない。凍結中のバッチに自動再実行を臨時に追加しない。
- `characterTextMissing` in the same section lists the missing-answer rate separately; for that turn no scoring that depends on the original words is done (persona, spoilers, tone and so on), while the deterministic checks of world, events and memory are still run. More than 5% missing answers is reported as an infrastructure problem. Both the number of speaking attempts and the number of turns that should have been answered must be kept; turns in which a safety card pauses character answers by design are listed separately and do not masquerade as missing answers or successful model answers.
  同じ節の `characterTextMissing` は無回答率を別に示す。そのターンでは、人物設定、ネタバレ、口調など原文に依存する採点は行わず、世界、イベント、記憶の決定論的チェックは引き続き実行する。無回答が 5% を超えたらインフラの問題として報告する。発話の試行回数と本来回答すべきターン数の両方を残す。安全カードが設計どおり登場人物の回答を一時停止したターンは別に示し、無回答やモデルの回答成功を装わせない。

| Actual situation / 実際の状況 | Handling of samples and metrics / サンプルと指標の扱い |
|---|---|
| The vendor's original request fails and the second attempt gets a valid answer / ベンダーへの元のリクエストが失敗し、2 回目で適格な回答を得た | Keep the failed request, latency and retry cost; this is a successful recovery, and the product cannot be deemed degraded just because the first attempt failed / 失敗したリクエスト、遅延、リトライの費用を残す。回復の成功であり、初回の失敗だけで製品が劣化したとは認定できない |
| After two failures: missing answer, only the clock advancing, a fixed fallback, or a template ending / 2 回失敗した後の無回答、時計だけを進める、固定のフォールバック、テンプレートのエンディング | A real product fallback, counted in the corresponding degradation / missing-answer metrics; if the game really completes with a signature, it stays in the fixed plan's ending statistics / 実際の製品のフォールバックであり、対応する劣化・無回答の指標に数える。実際に完了して署名がある場合は、固定計画のエンディング統計に引き続き残す |
| Normal set pieces and scripted lines / 通常の固定演出、台本のセリフ | Designed content, not infrastructure degradation; it also cannot pass content scoring as a generative-model answer / 設計上の内容であり、インフラの劣化には数えない。生成モデルの回答として内容の採点を通すこともできない |
| The rules rewrite an action that does not hold, downgrade it to a small effect, or refuse it / ルールが成立しないアクションを書き換える、小さな影響に格下げする、拒否する | A story-rule decision; `candidates_downgraded` is not the same as service degradation after a vendor failure / 物語のルールによる判定。`candidates_downgraded` はベンダーの失敗後のサービスの劣化とは別物 |
| After bad AI-player output: automatic waiting, other substitute choices, or reading old replays / AI プレイヤーの悪い出力の後の自動的な待機、別の代替選択、古いリプレイの読み込み | The experimental persona was altered; keep the original record and mark it invalid; it cannot be certified as a complete fresh persona sample for the 200 games / 実験のペルソナが変わってしまったので、元の記録を残して無効とマークする。200 局の完全な新鮮なペルソナのサンプルとは認定できない |
| Unfinished, over the step limit, whole-game timeout, missing signature, or inconsistent sources / 未完了、ステップ上限超過、1 局全体のタイムアウト、署名の欠落、ソースの不一致 | Keep the completion rate and failure classification; the diversity-completeness threshold must not show as passed, and missing samples cannot be used to pull down the share of the largest category / 完了率と失敗の分類を残す。多様性の完全性の閾値を合格と表示してはならず、欠落したサンプルで最大分類の割合を下げてはならない |

The batch's first version recorded any request `error / timeout / bad-output` as `provider-degradation`, and also made all 200 games being `clean` a precondition for diversity, mixing request reliability, product degradation and sample validity. The original diagnosis is kept; later interpretation should be split into `measurementCompleteness`, `productDegradation` and `requestRetries`. A complete real sample can yield a diversity conclusion while the degradation rate or the deterministic quality threshold fails; passing diversity cannot cover other failures, and still less does it mean the not-yet-calibrated model content scoring has passed.

バッチの初版は、リクエストの `error / timeout / bad-output` をすべて `provider-degradation` として記録し、さらに 200 局すべてが `clean` であることを多様性の前提にしており、リクエストの信頼性、製品の劣化、サンプルの有効性を混同していた。元の診断は残す。以後の解釈は `measurementCompleteness`、`productDegradation`、`requestRetries` に分けるべき。完全な実サンプルから多様性の結論を得つつ、劣化率や決定論的な品質の閾値では不合格ということもありうる。多様性の合格で他の失敗を覆い隠すことはできず、まだキャリブレーションしていないモデルの内容の採点が合格したことを意味するものでもない。

### Measurement fields after the stop point (implemented; old evidence is not backfilled) / 停止点の後の計測フィールド（実施済み、旧証拠は遡って埋めない）

- On the player side, count speaking attempts, safety pauses, turns that should be answered, explicit missing-answer markers and unreported missing markers from the actual `Played.steps/results`, and verify that the number of steps matches the number of results. A missing field is unknown and cannot be treated as no missing answer. `freshCalls / replayHits / bad` are verified together with the step count for fresh-persona completeness.
  プレイヤー側では、実際の `Played.steps/results` から発話の試行、安全のための一時停止、回答すべきターン数、明示的な無回答マーク、マークが欠けた未報告数を集計し、ステップ数と結果の件数が一致することを検証する。フィールドの欠落は不明であり、無回答がないとはみなせない。`freshCalls / replayHits / bad` はステップ数と合わせて、新鮮なペルソナの完全性を検証する。
- On the backend side, read the real diagnostics such as `budget_tier`, `degraded_at / degraded_reason`, `turns_timed_out` and `ending_template`, then aggregate them per batch; ending signatures still use the production persisted results. The existing `sim_stats` does not keep per-turn `characterTextMissing`, so for old batches the raw evidence has to be checked, and it cannot be fabricated as zero.
  バックエンド側では、実際の `budget_tier`、`degraded_at / degraded_reason`、`turns_timed_out`、`ending_template` などの診断を読み、バッチで集計する。エンディングの署名は引き続き本番の永続化された結果を使う。既存の `sim_stats` はターンごとの `characterTextMissing` を残さないので、旧バッチは元の証拠を調べる必要があり、ゼロとしてでっち上げてはならない。
- The request-level failure rate keeps every ledger row; the number of successful retries must have evidence linking it to a request or turn. The current ledger has no logical request ID, so recovery cannot be inferred merely from adjacent calls of the same kind. When no link can be made, report unknown. `utterances.source=fallback` in the current gateway means audio transcription filled in afterwards, not the fixed character-line fallback, and cannot be used directly to count service degradation.
  リクエスト単位の失敗率は台帳のすべての行を残す。成功したリトライの数には、リクエストやターンとの関連の証拠が必要。現在の台帳には論理的なリクエスト ID がないので、隣り合う同種の呼び出しだけから回復したと推定してはならない。関連づけられない場合は不明と報告する。現在のゲートウェイでの `utterances.source=fallback` は音声の文字起こしの補完を意味し、登場人物の固定セリフへのフォールバックとは別物なので、サービスの劣化を数えるのにそのまま使ってはならない。
- This round found that the missing-answer marker returned by `eval_api` was not synced to `turns.character_text_missing`, so a false value in the old database field cannot prove that the turn had an answer. This was fixed at the stop point with a database regression added; the old database field is not retroactively fabricated, and old batches stay frozen.
  今回、`eval_api` が返す無回答マークが `turns.character_text_missing` に同期されていないことがわかった。したがって旧データベースのフィールドが false でも、そのターンに回答があった証明にはならない。停止点で修正し、データベースの回帰テストを追加した。旧データベースのフィールドを遡ってでっち上げることはせず、旧バッチは凍結したまま。

## Verification / 検証

- Targeted report, player, check and runner tests: 86 passed; full offline eval tests: 127 passed, 1 database snapshot skipped.
  対象を絞ったレポート、プレイヤー、チェック、ランナーのテスト：86 件合格。評価全体のオフラインテスト：127 件合格、データベースのスナップショット 1 件スキップ。
- In the independent PostgreSQL regression, 97 B3 / B4 / B13 tests passed, covering the confirmation projection, public memory deletion and cross-game refusal, and set-piece line projection. It was first found that a change to the persistent event loop had deleted the old test helper `_run`; the implementation thread has restored compatibility.
  独立した PostgreSQL の回帰テストで、B3 / B4 / B13 の 97 件に合格し、確認の投影、公開記憶の削除と他の局からの拒否、演出のセリフの投影をカバーした。当初、永続的なイベントループの変更で古いテストのヘルパー関数 `_run` が削除されていたことがわかり、実装スレッドが互換性を復元した。
- The new database regression for the water-handing button passed on its own: taking the public button and submitting `actionId` directly, without adding the internal item parameter, gives the production `done / aid.melos.water / 15min`.
  新たに追加した水を渡すボタンのデータベース回帰テストは単独で合格した：公開ボタンを取ってそのまま `actionId` を送信し、内部のアイテムのパラメータを補わずに、本番どおりの `done / aid.melos.water / 15min` を得た。
- All the original results of the fake report's existing 100 cases / 388 runs match the original snapshot; after updating the summary and the plan-coverage metadata, the actual database snapshot regression also passed on its own. The execution thread then fixed the act that late checkpoints belong to and regenerated the question set; the new snapshot was verified separately by that thread, and the earlier pass conclusion is not carried over.
  fake レポートの既存の 100 ケース / 388 回の元の結果はすべて元のスナップショットと一致した。集計と計画のカバレッジのメタデータを更新した後、実際のデータベースのスナップショットの回帰テストも単独で合格した。その後、実行スレッドが後半の checkpoint が属する幕を修正して問題セットを再生成した。新しいスナップショットはそのスレッドが別途検証しており、以前の合格の結論は引き継がない。
- Ruff checks and format checks on the related 11 files and mypy on 17 files passed. The review thread made no actual model calls, deployments or credential changes.
  関連する 11 ファイルの Ruff チェックとフォーマットチェック、17 ファイルの mypy に合格した。レビューのスレッドは実際のモデル呼び出し、デプロイ、認証情報の変更を行っていない。

The results of the real four acts and of the 20–30 / 200 games, the model call ledger and the final acceptance are provided by the limited batch execution records; this file does not replace that run evidence.

実際の四幕と 20–30 / 200 局の結果、モデル呼び出しの台帳、最終的な受け入れ確認は、限定的なバッチの実行記録が提供する。このファイルはそれらの実行の証拠に代わるものではない。


## October 13 fixes for items 1 and 2 / 10 月 13 日の第 1、2 項目の修正

- The real simulated-player observation defect has been located: production set-piece lines use `line` / `narration`, but the runner wrongly read `text`, so lines were projected as empty brackets. Now the content actually delivered is read according to the contract, and every set piece in the full world model is used to verify that each line enters the player's observation, without adding any future events. The existing `refused` flag has also been added to the real model's observation; previously only the fake player read it. The public observation version was bumped to `player-3`.
  実際のシミュレーションのプレイヤーの観測の欠陥を特定した：本番の固定演出のセリフは `line` / `narration` を使うが、ランナーは誤って `text` を読んでいたため、セリフが空の括弧として投影されていた。現在は契約どおりに実際に届いた内容を読み、完全な世界モデルのすべての固定演出で、各セリフがプレイヤーの観測に入ることを検証している。未来のイベントは一切追加していない。既存の `refused` フラグも実モデルの観測に加えた。以前は偽プレイヤーだけがこれを読んでいた。公開の観測バージョンは `player-3` に上げた。
- In the original 12 completed execution samples, 10 endings were all canon-reunion (2 signatures); this only shows that the old sample results were concentrated, and neither proves that branching is broken nor certifies diversity. The original hostage-substitute persona repeatedly tried the 王城 entrance that production R7 refuses, compounded by the observation defect that lost the fixed refusal line; the fix neither loosens identity permissions nor dictates the ending.
  元の完了した実行サンプル 12 件のうち、10 件のエンディングはすべて canon-reunion（署名 2 種類）。これは旧サンプルの結果が偏っていたことを示すだけで、分岐が壊れていることの証明にも、多様性の認定にもならない。元の人質の身代わりのペルソナは本番の R7 が拒否する王城の入口を何度も試み、それに固定の拒否セリフが失われる観測の欠陥が重なっていた。修正では身元の権限を緩めず、エンディングも指定しない。
- The two unfinished games were confirmed to have hit the eval's 80-step limit: the troublemaker spoke 64 times and ended in act 3 at t=3825; the memory deleter spoke 41 times and deleted 34 times, ending in act 2 at t=1755. The max-steps failure records are kept. The runner adds an explicit finite `--max-steps`, included in the batch fingerprint; targeted regressions with a higher limit get separate evidence and cannot pass for retests under the same limit.
  未完了の 2 局は評価の 80 ステップの上限に当たったと確認した：かき回し役は 64 回発話し、第 3 幕の t=3825 で終了。記憶削除役は 41 回発話し 34 回削除して、第 2 幕の t=1755 で終了。max-steps の失敗記録は残す。ランナーには明示的で有限な `--max-steps` を追加し、バッチのフィンガープリントに含めた。より高い上限での対象を絞った回帰テストは別に証拠を作り、同じ上限での再テストとは偽らない。
- All three stops were Google reply rate limits; the old client did not save the quota sub-category, so the specific quota cause cannot be asserted after the fact. S-079's stop on the first 429 / 529 stays unchanged: an atomic persistent stop point was added, explicitly resuming only units not yet started, and the restart command will not silently go past the rate limit and continue; already-paid failed games are not reopened automatically. Only the vendor, the HTTP status code and the numeric Retry-After are recorded; the raw error response is not saved.
  3 回の停止はいずれも Google reply のレート制限だった。旧クライアントはクォータの細分類を保存しておらず、具体的な上限の原因を事後に断定できない。S-079 の最初の 429 / 529 での停止は変えない：アトミックで永続的な停止点を追加し、未開始の単位だけを明示的に再開するようにした。再起動コマンドがレート制限を黙って越えて続行することはない。費用を支払い済みの失敗した局は自動で再開しない。記録するのはベンダー、HTTP ステータスコード、数値の Retry-After だけで、元のエラーレスポンスは保存しない。
- A new eval-only Pipeline final-state observer collects the attempt sequence for each actual logical call, so successful retries and two failures can be clearly told apart, while the production time limits, retry counts and model inputs are unchanged. Missing answers are written to turns.character_text_missing; per-turn statistics separate speaking, safety pauses, missing answers, missing fields and mismatched result counts. Budget tier, ending template, timed-out turns, memory and safety failures are read from persisted metrics. Not all output-sanitizing fallbacks are covered yet, so zero known failures is still unknown, and we do not claim zero degradation.
  評価専用の Pipeline の終了状態のオブザーバーを新設し、実際の論理呼び出しごとに attempt の列を集めることで、成功したリトライと 2 回の失敗を明確に区別できるようにした。本番の制限時間、リトライ回数、モデルの入力は変えていない。無回答は turns.character_text_missing に書き込む。ターンごとの統計は、発話、安全のための一時停止、無回答、フィールドの欠落、結果の件数の不一致を分けて示す。予算の段階、エンディングのテンプレート、タイムアウトしたターン、記憶と安全の失敗は永続化された指標から読む。出力のサニタイズによるフォールバックはまだすべてをカバーしていないので、既知の失敗ゼロは依然として unknown であり、劣化ゼロとは主張しない。
- The original 20 games' summary, report and unit evidence were not rewritten; summary-v2 / report-v2 were saved separately, keeping the original issues and splitting request failures from product fallbacks. The old public observation version is marked as an invalid measurement, and the 10 actual endings are still kept as they were. When a successful retry lacks logical-link evidence, it is not inferred backwards.
  元の 20 局の summary、report、単位ごとの証拠は書き換えていない。summary-v2 / report-v2 を別に保存し、元の issues を残したうえでリクエストの失敗と製品のフォールバックを分けた。旧公開の観測バージョンは無効な計測とマークし、10 件の実際のエンディングは元のまま残す。成功したリトライに論理的な関連の証拠がない場合は逆算しない。
- Offline eval / LLM tests: 145 passed, 1 database snapshot skipped; the new full-world set-piece contract coverage also passed. 54 targeted non-replay database tests passed, including the new missing-answer persistence; the old b9 replay only synced the corrected authoritative character location (var.melos.location in two world requests), and the targeted replay tests passed. The fixtures affected by the reply prompt update are waiting to be regenerated together once the prompt is stable.
  オフラインの評価 / LLM テスト：145 件合格、データベースのスナップショット 1 件スキップ。新たな完全な世界の固定演出の契約カバレッジも合格した。データベースの非リプレイの対象テスト 54 件に合格し、新たな無回答の永続化もその中に含まれる。旧 b9 のリプレイは修正済みの正となる登場人物の位置（world リクエスト 2 件の var.melos.location）だけを同期し、対象を絞ったリプレイテストは合格した。reply プロンプトの更新後の fixture は、プロンプトが安定してからまとめて再生成する予定。

The results of the targeted real-model regressions are still to be written; the formal 200 games and the four-act 980 runs were not started this round.

対象を絞った実モデルの回帰テストの結果はまだ記入していない。正式な 200 局と四幕の 980 回は今回開始していない。

### Known quality risks from the limited re-check / 限定的な再確認で判明している品質リスク

Of the 10 real endings in the original smoke20, read-only queries of the persisted metrics showed that 5 used templates. Templates are a definite product fallback and cannot be omitted just because the ending classification is valid; the old `character_text_missing=false` cannot serve as evidence of no missing answers because of the persistence defect above. The supplementary metrics are saved as separate private evidence and do not overwrite the old report, unit results or cost ledger.

元の smoke20 の実際のエンディング 10 件は、永続化された指標を読み取り専用で照会したところ、5 件がテンプレートを使っていた。テンプレートは確定した製品のフォールバックであり、エンディングの分類が有効だからといって省いてはならない。旧 `character_text_missing=false` は上記の永続化の欠陥のため、無回答がない証拠にはならない。補足の指標は非公開の証拠として別に保存し、旧レポート、単位ごとの結果、費用の台帳は上書きしない。

These old model requests did not have text replay enabled; the worker's narrator trace stayed only in memory and in INFO logs that were not enabled, and the database saves only the final ending and the template marker. So the specific content-refusal rules cannot be recovered after the fact and must be recorded as unknown; we cannot infer from a successful transmission that a particular filter misfired. The first targeted sample after the fix also triggered a template, with 2 real missing answers out of 29 replies; one more case where the first request failed and the retry succeeded is listed separately. The new measurements reveal the product fallback; they do not prove these quality risks have gone away.

これらの旧モデルのリクエストではテキストのリプレイが有効になっておらず、worker のナレーターの trace はメモリと有効化されていない INFO ログにしか残らず、データベースには最終的なエンディングとテンプレートのマークしか保存されていない。したがって具体的な内容の拒否ルールは事後に復元できず、不明と書かなければならない。送信が成功したことから、ある特定のフィルタの誤判定だと推定することはできない。修正後最初の対象サンプルも同様にテンプレートを発動し、29 回の応答のうち 2 回で実際に無回答があった。ほかに初回のリクエストが失敗しリトライで成功した 1 件を別に示した。新しい計測は製品のフォールバックを明らかにしたが、これらの品質リスクがなくなったことは証明していない。

The targeted regressions of the 4 original personas do not replace the original 20 games and do not count toward the new fixed 200 games. The original hostage-substitute and wedding-delay personas keep 80 steps; the original troublemaker and memory-deleter personas explicitly use 160 steps to diagnose the original step limit, with an extra 30-minute game limit, and results with a higher step count are not called a same-conditions comparison. All failures, costs and the original player replays are kept. The formal 200-game diversity threshold and the 980-run four-act quality threshold remain unverified.

元の 4 ペルソナの対象を絞った回帰テストは、元の 20 局を置き換えず、新たな固定 200 局にも数えない。元の人質の身代わりと婚礼引き延ばしのペルソナは 80 ステップのまま。元のかき回し役と記憶削除役のペルソナは元のステップ上限を診断するために明示的に 160 ステップを使い、さらに 1 局 30 分の制限を設けた。ステップ数の多い結果を同条件での比較とは呼ばない。すべての失敗、費用、元のプレイヤーのリプレイは残す。正式な 200 局の多様性と 980 回の四幕の品質の閾値は依然として未検証。

### Ending this round's real calls per the user's instruction / ユーザーの指示による今回の実呼び出しの終了

The user then explicitly skipped the remaining real games and CI. This round immediately wrote a shared stop point, letting in-flight calls settle and then blocking the next call; the controller and workers have exited, with no new games or ending-reproduction calls. In practice only 1 game was completed, 1 game was deliberately interrupted, and the other 2 games were not started:

ユーザーはその後、残りの実対局と CI のスキップを明示した。今回は直ちに共有の停止点を書き込み、実行中の呼び出しは精算させたうえで次の呼び出しを止めた。コントローラーと worker は終了しており、新しい局やエンディングの再現の呼び出しはない。実際に完了したのは 1 局だけで、1 局は意図的に中断し、残りの 2 局は未開始：

| Persona / ペルソナ | Facts this round / 今回の事実 | Quality boundary / 品質の境界 |
|---|---|---|
| Hostage substitute / 人質の身代わり | Ended naturally after 62 steps; canon-reunion; all fresh player calls / 62 ステップで自然に終了。canon-reunion。プレイヤーの呼び出しはすべて新鮮 | 2 missing answers out of 29 that should have been answered, plus 1 recovered by retry; the ending was a template, with 1 memory failure. Cannot be called a quality pass / 回答すべき 29 回のうち 2 回が無回答、ほかに 1 回はリトライで回復。エンディングはテンプレートで、記憶の失敗が 1 回。品質の合格とは言えない |
| Troublemaker / かき回し役 | When the user stopped it, 100 player decisions had been recorded and 99 execution steps started; persisted state had reached act 4 at t=4935 / ユーザーが停止した時点で、プレイヤーの決定 100 件を記録し、実行ステップ 99 件を開始済み。永続化された状態は第 4 幕の t=4935 に到達 | Of 72 talk turns, 6 missing answers were persisted; all 21 request timeouts are kept. Because the user interrupted it, there is no ending result; it counts neither as a product failure nor as a pass / talk の 72 ターンのうち、永続記録上の無回答は 6 回。リクエストのタイムアウト 21 回はすべて残す。ユーザーが中断したのでエンディングの結果はなく、製品の失敗にも合格にも数えない |
| Wedding delay, memory deleter / 婚礼引き延ばし、記憶削除 | Not started / 未開始 | Not verified / 未検証 |

The estimated costs of the two games are about $2.71 and $4.72 respectively, and the full private ledger is kept. The partial state and execution classification at the user's stop point are saved separately in `user-stop.json`, without rewriting the original records that were already complete. The limited ending reproduction prepared earlier only ran an unpaid input preflight and was not executed after the user cancelled; the original template-failure rule is still unknown.

2 局の推定費用はそれぞれ約 $2.71、$4.72 で、完全な非公開の台帳を残している。ユーザーの停止点での部分的な状態と実行の分類は `user-stop.json` に別に保存し、すでに完了していた元の記録は書き換えていない。以前に準備していた限定的なエンディングの再現は、費用のかからない入力のプリフライトだけを行い、ユーザーのキャンセル後は実行していない。元のテンプレート失敗のルールは依然として不明。

Two definite observability fixes have been added: the source fingerprint includes the original and per-act persona JSON; the eval diagnostics separately save the rule name, attempt count and status for ending / ending-check / ending.done, excluding the original words, prompts and model IDs. Old samples are not backfilled. The final necessary 15 short unit tests, the related Ruff, and mypy on 3 production source files passed; no new full CI or real batch was dispatched.

確定した観測の修正を 2 つ加えた：ソースのフィンガープリントに元の persona JSON と幕ごとの persona JSON を含めた。評価の diagnostics には ending / ending-check / ending.done のルール名、試行回数、状態を別に保存し、原文、プロンプト、モデル ID は除外した。旧サンプルを遡って埋めることはしない。最後に必要な短い単体テスト 15 件、関連する Ruff、本番のソースファイル 3 つの mypy に合格した。新たな完全な CI や実バッチは投入していない。

So the runner and traceability defects of items 1 and 2 have been fixed, and the causes and shortcomings of the old samples are clearly kept; real character missing answers, the template ratio and the fixed 200-game distribution are still quality items that have failed or are unverified, and the user's cancelled measurement must not be written up as these product quality problems having been fixed.

したがって第 1、2 項目のランナーとトレーサビリティの欠陥は修正済みで、旧サンプルの原因と不足は明確に残している。実際の登場人物の無回答、テンプレートの割合、固定 200 局の分布は、依然として不合格または未検証の品質項目であり、ユーザーがキャンセルした計測を、これらの製品の品質問題を直し終えたと書いてはならない。
