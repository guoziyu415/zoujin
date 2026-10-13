# R-1 Resume regression checks and real-model validation / R-1 回帰チェックの再開と実モデル検証

On 2026-10-12 the user authorized resuming the four-act story, spoiler protection, CI and staged simulation; the real-model calls of this round and the required cost are explicitly authorized. Judge calibration and pre-recorded voice listening remain on hold. The project is still private, and deployment is outside this card's scope.

2026-10-12 にユーザーが四幕のストーリー、ネタバレ防止、CI、段階的シミュレーションの再開を承認した。今回の実モデル呼び出しと必要な費用は明示的に承認されている。評価者のキャリブレーションと事前録音音声の試聴は引き続き保留。プロジェクトは引き続き非公開で、デプロイはこのカードの範囲外。

## Work and acceptance / 作業と受け入れ

1. Restore the existing isolated CI runner and the six workflows, and fix the static-check, unit-test, build and browser-check failures of the current branch. CI still disables real-model calls and does not mount local credentials.
   既存の隔離 CI ランナーと 6 つのワークフローを復旧し、現在のブランチの静的チェック、ユニットテスト、ビルド、ブラウザチェックの失敗を修正する。CI は引き続き実モデル呼び出しを無効にし、ローカルの認証情報をマウントしない。
2. Verify that the four-act cases match the currently running path; run the key flows first, then widen coverage. Report deterministic checks, model grading, skips, timeouts and infrastructure failures separately.
   四幕のケースが現在実際に動作する経路と一致することを確認する。まず主要フローを実行し、その後カバレッジを広げる。決定的チェック、モデル採点、スキップ、タイムアウト、インフラ障害は別々に報告する。
3. Re-examine historical wrong answers in spoiler protection, check coverage of the question set, and verify the current model path. Uncalibrated model grading serves only as auxiliary evidence.
   ネタバレ防止の過去の誤答を再確認し、問題セットのカバレッジを照合し、現在のモデル経路を検証する。キャリブレーション前のモデル採点は補助的な証拠にすぎない。
4. First run about 20–30 simulated games, fix the problems they expose, then run 200 games, recording ending distribution, completion rate, timeouts and actual call cost. Rule-based simulation or fake-model results must not be passed off as real-model simulation.
   まず約 20–30 局のシミュレーションを実行し、判明した問題を修正してから 200 局を実行し、結末の分布、完走率、タイムアウト、実際の呼び出しコストを記録する。ルールベースの推演や偽モデルの結果を実モデルのシミュレーションと偽ってはならない。

## Execution boundaries / 実行の境界

- The real model runs on the local machine with synthetic test inputs. Raw records, ledgers and credentials stay in a private local directory; commits keep only redacted reports and reproducible scripts.
  実モデルはローカルマシンで実行し、合成テスト入力を使う。生の記録、台帳、認証情報はローカルの非公開ディレクトリに残し、コミットには匿名化したレポートと再現可能なスクリプトだけを保存する。
- The authorized cost has no business cap; each round still uses limited cases, limited retries and timeouts, and saves the expected call volume first, so a fault cannot cause a runaway loop.
  承認された費用に業務上の上限はない。それでも各ラウンドは限定したケース、限定したリトライ、タイムアウトを使い、障害で暴走ループにならないよう、まず予想呼び出し量を保存する。
- No deployment and no anonymous entry; keep the site-wide password protection.
  デプロイしない。匿名の入口を開かない。サイト全体のパスワード保護を維持する。
- When finished, a role other than the implementer reviews the statistical method, failure handling and changes.
  完了後、実装者以外の役割が統計の方法、失敗の扱い、変更を審査する。

## Current record / 現在の記録

- At start, all six workflows were `disabled_manually` and the existing runner was `offline`; private repository properties were verified.
  開始時、6 つのワークフローはすべて `disabled_manually` で、既存のランナーは `offline` だった。プライベートリポジトリの属性は確認済み。
- The starting code is the H-1 local delivery version. Existing unit and browser results cannot substitute for this card's real-model validation.
  開始時のコードは H-1 のローカル納品版。既存のユニットテストとブラウザの結果は、このカードの実モデル検証の代わりにはならない。
- Work is on the private branch `r-1-deferred-validation`; workflows and the isolated runner have been restored. No deployment was made and no public-access permission was changed.
  作業は非公開ブランチ `r-1-deferred-validation` で行い、ワークフローと隔離ランナーは復旧済み。デプロイはせず、公開アクセス権限も変更していない。

## Fixes confirmed this round / 今回確認済みの修正

- When the real-evaluation HTTP client was reused across steps, the original entry point created a new event loop at each step, causing `Event loop is closed`. Now one game uses one loop and closes it after success or an exception. After the fix, a real exploratory game of 42 steps ended normally, all 107 calls succeeded, and the E7 deterministic check passed.
  実評価の HTTP クライアントをステップ間で再利用すると、元の入口がステップごとに新しいイベントループを作り、`Event loop is closed` が発生していた。現在は 1 局で 1 つのループを使い、成功時も例外時も終了後に閉じる。修正後、実際の探索局 42 ステップは正常に終了し、107 回の呼び出しはすべて成功し、E7 の決定的チェックに合格した。
- In the final act, waiting at a location with no further local beats was rejected repeatedly without advancing time. Now events and endings en route are settled by the official deadline, without forcing a particular ending class; the database regressions at two locations pass.
  最終幕で、後続のローカルビートがない場所で待つと、拒否が繰り返され時間が進まなかった。現在は正式な期限に従って途中のイベントと結末を精算し、特定の結末の類を強制しない。2 つの場所のデータベース回帰は合格した。
- Old location variables in model requests are projected by authoritative character locations, so the same character does not appear in two locations at once; saves are not modified, and no new variables are added for other books.
  モデルリクエスト内の古い位置変数は権威ある人物の位置で射影し直し、同じ人物が同時に 2 か所に現れないようにした。セーブデータは変更せず、他の書籍のために新しい変数は追加しない。
- The four acts and late-stage seed cases explicitly set the corresponding act. The simulated player enters from the official opening, and can use actual button IDs, confirmations, the public memory book and actual set-piece lines; every step makes a real call, and replay cannot be used silently.
  四幕と後期のシードケースは、対応する幕を明示的に設定する。シミュレーションプレイヤーは正式な開幕から入り、実際のボタン ID、確認、公開された記憶帳、実際の演出台詞を使える。各ステップで実際に呼び出しを行い、リプレイをこっそり使うことはできない。
- The evaluation report lists skipped, missing, degraded and ungraded results separately; these results no longer show the release gate as passed. The 200 games keep the original 10 personas and fixed denominator, and half-games and failure costs are also kept.
  評価レポートはスキップ、欠落、劣化、未採点を別に列挙する。これらの結果はもはやリリースゲート合格とは表示されない。200 局は元の 10 ペルソナと固定の分母を維持し、途中までの局と失敗のコストも保持する。
- For the boundaries of Live and narrative context and spoiler-protection evidence, see [Spoiler record / ネタバレ防止の記録](spoiler.md); for independent review, see [Evaluation method and cross-review / 評価方法と相互レビュー](eval-review.md).
  Live と語りのコンテキスト、ネタバレ防止の証拠の境界は [ネタバレ防止の記録](spoiler.md) を、独立レビューは [評価方法と相互レビュー](eval-review.md) を参照。

## Local validation completed / 完了したローカル検証

| Check / チェック | Result and boundary / 結果と境界 |
| --- | --- |
| Frontend browser / フロントエンドブラウザ | First round 50 of 54 passed; after fixes the 4 targeted items all passed, and after tightening the offline exemption that item passed again. Covers desktop Chrome at phone size, software 3D, a fake microphone and a mock gateway; this is not real-device or real-voice acceptance. / 初回は 54 項目中 50 が合格。修正後は 4 項目の指定実行がすべて合格し、オフライン免除を厳格化した後、その項目は再度合格した。デスクトップ Chrome のスマホサイズ、ソフトウェア 3D、偽マイク、mock ゲートウェイをカバーする。実機や実音声の受け入れと同じではない。 |
| Frontend static and build / フロントエンドの静的チェックとビルド | ESLint, Prettier, TypeScript and the production build pass. Brotli: first screen 107.7 KB / 120 KB, 3D 235.7 KB / 250 KB. / ESLint、Prettier、TypeScript、本番ビルドに合格。Brotli：最初の画面 107.7 KB / 120 KB、3D 235.7 KB / 250 KB。 |
| Python static / Python 静的チェック | Ruff and format checks pass; mypy passes on 198 files. / Ruff とフォーマットチェックに合格。mypy は 198 ファイルで合格。 |
| Current-version Python offline whole repo / 現行バージョンの Python オフライン全リポジトリ | 1,404 passed / 278 skipped, 257 seconds. Skips include cases that need a separate database and other environmental conditions; they do not count as passes. / 1,404 合格 / 278 スキップ、257 秒。スキップには別のデータベースやその他の環境条件が必要なケースが含まれ、合格には数えない。 |
| World and generated outputs / ワールドと生成物 | `check_world.sh` validated everything with no errors/warnings, rule-based simulation completed, and the regenerated committed content is consistent. This is not a real-model simulation. / `check_world.sh` はすべての検証でエラー・警告なし。ルールベースの推演は完了し、再生成後のコミット内容は一致した。実モデルのシミュレーションではない。 |
| Earlier database baseline of this round / 今回の前段のデータベースベースライン | 251 passed; 1 snapshot once failed due to concurrent metadata modification. The new snapshot passed independently, and after the current-act fix the fake raw results of the 388-run matched the snapshot; the newly added database action and wait regressions also passed separately. / 251 合格。スナップショット 1 件は並行したメタデータ変更のために一度失敗した。新しいスナップショットは単独で合格し、現在の幕の修正後、388-run の fake 生結果はスナップショットと一致した。新しく追加したデータベースのアクションと待機の回帰も別途合格した。 |

The four browser fixes were: the HUD-only test lacking a scene-ready signal, browser errors expected during the deliberate network cut, and the manifest interception not covering the world-version query. Independent review confirmed that production 3D still runs on real loading state, and that the resource-200 assertion and the reconnect-dedup assertion are kept.

ブラウザの 4 つの修正は、HUD のみのテストにシーン ready シグナルがなかったこと、意図的なネットワーク切断中のブラウザの想定エラー、manifest のインターセプトがワールドバージョンの問い合わせをカバーしていなかったことなど。独立レビューで、本番の 3D は引き続き実際の読み込み状態で動作し、リソース 200 のアサーションと再接続の重複排除のアサーションが保持されていることを確認した。

2026-10-13 stopping-point check: the 20-game plan left 15 records (10 games reached an ending, 2 hit the step limit, 3 stopped on rate limiting) and 5 games did not start; the 980 calls of the four acts and the official 200 games have not started. 497 Live spoiler-protection replies were completed, but uncalibrated automatic flags cannot be taken as the final conclusion. Four categories of CI passed, while web and assets still have failures.

2026-10-13 停止点の確認：20 局の計画では 15 件の記録が残った（10 局が結末に到達、2 局がステップ上限に到達、3 局がレート制限で停止）。5 局は未開始。四幕の 980 回と正式な 200 局は未開始。Live のネタバレ防止の返答 497 件は完了したが、キャリブレーション前の自動フラグを最終結論とすることはできない。CI は 4 種が合格、web と assets にはまだ失敗がある。

The user then explicitly asked to fix four items first: endings and unfinished flows, rate limiting and failure records, two kinds of CI, and the spoiler-protection problem. Currently only these fixes and limited targeted regressions are executed; a full run is not evidence that this fix is complete. Uncalibrated model grading, unfinished batches or local checks cannot be treated as release passes.

ユーザーはその後、まず 4 項目の修正を明示的に求めた：結末と未完了フロー、レート制限と失敗の記録、2 種類の CI、ネタバレ防止の問題。現在はこれらの修正と限定的な指定回帰だけを実行する。全量実行を今回の修正完了の証拠とはしない。キャリブレーション前のモデル採点、未完了のバッチ、ローカルチェックをリリース合格として扱ってはならない。

## Re-verification of the four fixes (2026-10-13) / 4 項目の修正の再検証（2026-10-13）

- The simulated player had misread the official set-piece lines `line / narration` as `text`, and missed the feedback when an action was rejected. The public observation is fixed, and the old observation version is separately marked as unsuitable as a sample of the new diversity; the raw files of the old 20 games are not rewritten. The new 4 games serve only as targeted regression and do not replace the originally planned failed games.
  シミュレーションプレイヤーは、正式な演出台詞 `line / narration` を `text` と誤読し、アクションが拒否されたときのフィードバックも取りこぼしていた。公開観測は修正済みで、古い観測バージョンは新しい多様性のサンプルには適さないと別途マークした。古い 20 局の生ファイルは書き換えない。新しい 4 局は指定回帰にのみ使い、元の計画で失敗した局の代わりにはしない。
- Real request failures, retry successes, terminal fallbacks and unknown information are recorded separately; missing answers are persisted synchronously. For rate limiting, the provider, status code and a safe Retry-After number are kept, and arbitrary error text is not stored. The shared stopping point blocks later calls from other workers, while the cost of in-flight requests is still kept; resuming does not reopen failed games.
  実リクエストの失敗、リトライ成功、終端のフォールバック、不明な情報は別々に記録し、欠落した回答は同期的に永続化する。レート制限ではプロバイダー、ステータスコード、安全な Retry-After の数値を保持し、任意のエラー本文は保存しない。共有停止点は他のワーカーの後続呼び出しを止めるが、処理中のリクエストの費用は保持する。再開しても失敗した局は再開されない。
- The Web CI loading error was reproduced at the same Linux checkout path: the `home` scene exclusion rule wrongly matched `/home/runner`, so the post-processing classes and the base class were split into separate chunks and failed to load. After switching to matching on the relative path within the source, the Linux and macOS main scene packs are byte-for-byte identical and the budget is unchanged; 3 path regressions, 320 frontend unit tests and static checks pass.
  Web CI の読み込み異常は、同じ Linux のチェックアウトパスで再現した：`home` シーンの除外ルールが `/home/runner` に誤ってマッチし、後処理クラスと基底クラスが別チャンクに分割されて読み込みに失敗していた。ソース内の相対パスでマッチする方式に改めた後、Linux と macOS のメインシーンパックはバイト単位で同一になり、予算も変わらない。パスの回帰 3 件、フロントエンドのユニットテスト 320 件、静的チェックに合格。
- The full local Chrome 155 browser run passed 49 items; the quality probe returned an empty measurement, with 1 failure and 4 subsequent serial cases not executed (the probe is designed to fall back to L1 after a timeout, and this time the underlying GPU timeline was not separately collected). Then, with the project-pinned Playwright Chromium 153, all 5 items of the quality group passed, without loosening assertions or extending the product timeout. The official Linux CI full-suite result is recorded separately, and the previous full run cannot be called all green.
  ローカルの Chrome 155 で全ブラウザテストを実行し 49 項目が合格。画質プローブが空の測定値を返し、1 件が失敗、後続の直列ケース 4 件は未実行（プローブはタイムアウト後に L1 に戻る設計で、今回は下層の GPU タイムラインを別途採取しなかった）。その後、プロジェクトが固定した Playwright Chromium 153 を使い、画質グループの 5 項目はすべて合格した。アサーションの緩和や製品タイムアウトの延長はしていない。正式な Linux CI の全体結果は別途記録し、前回の全体実行を全緑とは言えない。
- Current-source Python offline whole repo: 1,416 passed / 279 skipped; Ruff, format check on 252 files and mypy on 200 files pass. Targeted database and real-model results are recorded separately with the corresponding evidence.
  現行ソースの Python オフライン全リポジトリ：1,416 合格 / 279 スキップ。Ruff、252 ファイルのフォーマットチェック、200 ファイルの mypy に合格。データベースの指定実行と実モデルの結果は、対応する証拠とともに別途記録する。
- The asset fix keeps the original resolution, sampling, triangle counts and loading budgets. Only the village relight's Cycles bake is set to single-threaded to stabilize output; the crowd manifest is regenerated from the actual binaries of the pinned toolchain, and the file hash, byte count and source hash of the shared road texture are synchronized into all ten references. The official tier has been rebuilt locally: the village's standard first entry is 5.46 MB, full pack 7.01 MB / 11 MB; each crowd model has fewer than 3,500 triangles, and the combined pack is 221.3 KB / 300 KB. Independent source review and front/back image review found no new visual glitches. The official assets dual-build workflow has been dispatched with results to be recorded later; local results cannot substitute for it.
  アセットの修正は、元の解像度、サンプリング、三角面数、読み込み予算を維持する。出力を安定させるため、村の relight の Cycles ベイクを単一スレッドにしただけ。群衆のマニフェストは固定したツールチェーンの実バイナリから再生成し、共有道路テクスチャのファイルハッシュ、バイト数、ソースハッシュは 10 か所すべての参照に同期した。正式ティアはローカルで再ビルド済み：村の標準での最初の入場は 5.46 MB、全パックは 7.01 MB / 11 MB。群衆の各モデルは 3,500 三角面未満で、合算パックは 221.3 KB / 300 KB。独立したソースレビューと表裏の画像レビューで、新たな破綻は見つからなかった。正式な assets の二重ビルドワークフローは送信済みで、結果は後で記録する。ローカルの結果で代用してはならない。

Per the user's latest instruction, the official 200 games are not run for now; the full 980 calls of the four acts are not started within the current four fixes either. Judge calibration, pre-recorded voice listening and deployment remain outside this round.

ユーザーの最新の指示により、正式な 200 局は当面実行しない。四幕の 980 回の全量も、現在の 4 項目の修正の中では開始しない。評価者のキャリブレーション、事前録音音声の試聴、デプロイは引き続き今回の範囲外。

## User stopped the remaining acceptance (2026-10-13) / ユーザーが残りの受け入れを自ら停止（2026-10-13）

To submit today, the user explicitly asked to skip real games and CI and to playtest on their own instead. This section supersedes the earlier arrangement of continuing to wait; no new games, real-ending reproduction or CI will be started. Asset quality was not reduced, assertions were not loosened and failure results were not rewritten.

今日の提出のため、ユーザーは実対局と CI をスキップし、代わりに自分で試遊することを明示的に求めた。この節は上文の待機継続の取り決めに優先する：新しい局、実際の結末の再現、CI は開始しない。アセットの品質は下げておらず、アサーションも緩めておらず、失敗の結果も書き換えていない。

- Four-game targeted batch: game 1 completed; game 2 was stopped midway by the user; games 3 and 4 were not started. The shared stopping point and the raw step and call ledgers are kept. Game 1's 2 missing answers, templated ending and memory-write failure remain observed experience risks and do not disappear because verification stopped; game 2 passed the original 80-step boundary into Act 4 (100 player decisions, 99 execution steps started), with 6 missing answers in 72 persistent dialogues, and it is not claimed to be a full playthrough.
  4 局の指定バッチ：第 1 局は完了。第 2 局は途中でユーザーが停止。第 3、4 局は未開始。共有停止点と生のステップ・呼び出しの台帳は保持している。第 1 局の 2 件の回答欠落、テンプレートの結末、記憶書き込みの失敗は、観測された体験上のリスクのままであり、検証を止めたからといって消えない。第 2 局は元の 80 ステップの境界を越えて第四幕に入った（プレイヤーの決定 100、開始された実行ステップ 99）。永続的な対話 72 回のうち 6 回で回答欠落があり、完全なクリアとは主張しない。
- Python, contracts and node workflows passed on `3ee5153`. The minimal source consolidation afterwards ran only the necessary local targeted checks, and it is not claimed that the final commit re-ran all of CI.
  Python、contracts、node のワークフローは `3ee5153` で合格した。その後の最小限のソース統合では必要なローカルの指定チェックだけを実行しており、最終コミットで CI 全体を再実行したとは主張しない。
- Web: the Linux path-splitting defect is fixed; the 6 failures of the later old run were all tied to missing actual character/animation inputs. Hash verification and staging of 17 character sets, 68 GLBs and the pinned UAL inputs were added, without using placeholder models or ignoring 404s. The new run was cancelled per the user's instruction, so it cannot be said that the full browser CI passed.
  Web：Linux のパス分割の欠陥は修正済み。その後の古い実行の 6 件の失敗は、いずれも実際の人物・アニメーション入力の欠如に関連していた。17 セットの人物、68 個の GLB、固定した UAL 入力のハッシュ検証とステージングを追加し、プレースホルダーモデルや 404 の無視は使っていない。新しい実行はユーザーの指示でキャンセルしたので、完全なブラウザ CI が合格したとは言えない。
- Assets: before cancellation, the dual-build checks of river and castle passed; road-rest, plaza, village and crowd were cancelled. The local deterministic fix, official-tier build and budget evidence are kept, but cannot substitute for the cancelled full workflow.
  Assets：キャンセル前に river と castle の二重ビルドチェックは合格。road-rest、plaza、village、crowd はキャンセルした。ローカルの決定性の修正、正式ティアのビルド、予算の証拠は保持しているが、キャンセルされた完全なワークフローの代わりにはならない。
- Hygiene: the history scan reported only the fictional checkout-path fixture; it was changed to the already-allowed example path, and only the exact fingerprint of the corresponding historical commit is ignored. The post-fix run was cancelled, and it is not claimed that the final scan passed.
  Hygiene：履歴スキャンが報告したのは架空のチェックアウトパスのフィクスチャだけだった。既存で許可されている例のパスに変更し、対応する過去コミットの正確なフィンガープリントだけを無視する。修正後の実行はキャンセルしたので、最終スキャンが合格したとは主張しない。
- The three spoiler-protection v2 files are consolidated, with characters' original beliefs, tone and goals unchanged; 9 brief items and 2 replay items pass in targeted runs. The existing limited model re-verification of 15 items retains 1 pragmatic ambiguity, and it is not packaged as a full spoiler-protection release certification.
  ネタバレ防止 v2 の 3 ファイルは統合済み。人物の元の信念、口調、目標は変えていない。9 項目の brief と 2 項目の replay の指定実行に合格。既存の限定的なモデル再検証 15 件には語用論上の曖昧さが 1 件残っており、全量のネタバレ防止リリース認証としては扱わない。
- The two temporary CI runners were deregistered after going idle, and the temporary containers and volumes were deleted; the original runner and database are kept. This round's temporary static debug service has been shut down. All private results and build evidence are kept.
  2 つの一時的な CI ランナーはアイドルになった後に登録解除し、一時的なコンテナとボリュームを削除した。元のランナーとデータベースは保持している。今回の一時的な静的デバッグサービスは停止済み。すべての非公開の結果とビルドの証拠は保持している。
- The scene and character deployment packaging preflight passed; no new version was deployed, no entry opened and the default branch not modified. The formal submission additionally needs materials and a reviewer-accessible environment; see [Submission handoff / 提出の引き継ぎ](submission-handoff.md).
  シーンと人物のデプロイ用パッケージの事前チェックに合格した。新バージョンのデプロイ、入口の開放、デフォルトブランチの変更はしていない。正式な提出には、別途資料とレビュー担当者がアクセスできる環境が必要。[提出の引き継ぎ](submission-handoff.md) を参照。

### Separately authorized later deployment / 後に別途承認されたデプロイ

After the user explicitly replied "Deploy", `be03d70` was built, migrated and deployed to the existing Cloud Run gateway and narrator, and both have 100% production traffic. The candidate/production smoke tests for password, invite code, home page, scene, opening, WebSocket and anonymous-access rejection passed. The deployment hit a 404 on Cloud Run's reserved `/healthz` path, so it was changed to an empty 204 on `/health`, and the four-gate short test passed; CI and real whole-game validation were not resumed.

ユーザーが明示的に「デプロイ」と返信した後、`be03d70` をビルド、マイグレーションし、既存の Cloud Run ゲートウェイと語り手にデプロイした。両者の本番トラフィックは 100%。パスワード、招待コード、トップページ、シーン、開幕、WebSocket、匿名アクセス拒否の候補・本番スモークテストに合格した。デプロイ時に Cloud Run の予約パス `/healthz` が 404 になったため、`/health` の空 204 に変更し、4 つのゲートの短いテストに合格した。CI と実際の全局検証は再開していない。

Both cloud services are still IAM-private, the real-model configuration and the gateway password Secret were both verified, and the privacy lock is kept. The local loopback authentication proxy is only for the user's Mac to reach the actual cloud model; proxy login, resources and WebSocket were separately confirmed to pass; credentials and the proxy do not enter the repo. Access for external reviewers without a Google identity has not yet been opened, and the default branch and submission materials are still unhandled. For details see the current handoff; the historical "not deployed" stopping-point description must not be used in place of the latest status.

2 つのクラウドサービスは引き続き IAM で非公開で、実モデルの設定とゲートウェイのパスワード Secret はどちらも確認済み。プライバシーロックは維持している。ローカルのループバック認証プロキシは、ユーザーのこの Mac が実際のクラウドモデルに入るためだけのもの。プロキシのログイン、リソース、WebSocket は別途合格を確認した。認証情報とプロキシはリポジトリに入れない。Google アカウントを持たない外部レビュー担当者のアクセス方法はまだ開放しておらず、デフォルトブランチと提出資料は未処理。詳細は現在の引き継ぎを参照。以前の「未デプロイ」という過去の停止点の記述を最新の状態の代わりにしてはならない。

The user then explicitly authorized a password-protected external review entry, which has been prepared: the gateway's HTTPS password page is reachable, 17 actual content paths and unauthenticated WebSocket are all blocked; after password + invite code login works, the main account keeps the real opening, and two spare invite codes exist. The narrator remains private, all old gateway tags are cleared, and any future new candidate/switch/rollback must first restore IAM-private. 25 targeted privacy checks passed. The default branch main is aligned with the delivered code; the URL/password/Japanese review notes are stored only in a local private file; no article/image/video publication or formal submission was performed.

ユーザーはその後、パスワード付きの外部レビュー用入口を明示的に承認し、準備を済ませた：ゲートウェイの HTTPS パスワードページに到達でき、17 の実際のコンテンツパスと未認証の WebSocket はすべてブロックされる。パスワード＋招待コードでログインでき、メインアカウントは実際の開幕を維持し、予備の招待コードが 2 つある。語り手は引き続き非公開で、ゲートウェイの古いタグはすべて削除済み。今後の新しい候補・切り替え・ロールバックは、まず IAM の非公開に戻さなければならない。25 項目のプライバシーの指定チェックに合格。デフォルトブランチ main は納品コードと揃えてある。URL・パスワード・日本語のレビュー説明はローカルの非公開ファイルにのみ保存する。記事・画像・動画の公開と正式な提出は行っていない。
