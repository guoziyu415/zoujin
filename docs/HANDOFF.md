# 物語 (Monogatari) handoff (for the person or AI taking over) / 物語（Monogatari）引き継ぎ（引き継ぐ人または AI 向け）

Written on 2026-10-12 (Japan time). It was previously developed by multiple Claude sessions in separate roles, and is now handed to a new team. This document covers only what the takeover needs to know; for details see the documents it points to.

2026-10-12（日本時間）に作成。以前は役割別の複数の Claude セッションが開発しており、今回新しいチームに引き継ぐ。この文書は引き継ぎに必要なことだけを書く。詳細は文中で指している文書を参照。

## Submission materials and public-release authorization (latest, 2026-10-13) / 提出資料と公開の許可（2026-10-13 最新）

The user has explicitly allowed publishing the product concept, project description, architecture diagrams and demo video; the actual app continues to keep its password and invite codes, and the repository stays private. The Japanese submission description, architecture PNG/SVG, official statistics and scoring correspondence, and recording script are in [Submission materials / 提出資料](submission/README.md). Video recording and YouTube upload are the user's responsibility; no more recording or real games will be run. The formal form submission has not been verified.

ユーザーは、製品コンセプト、プロジェクト説明、アーキテクチャ図、デモ動画の公開を明示的に許可した。実際のアプリは引き続きパスワードと招待コードを維持し、リポジトリは非公開のまま。日本語の提出説明、アーキテクチャの PNG/SVG、公式の統計と採点の対応、録画スクリプトは [提出資料](submission/README.md) にある。動画の録画と YouTube へのアップロードはユーザーが担当する。これ以上録画や実対局は行わない。正式なフォームの提出は未確認。

The source of the image running in production is `31e2684`, and the default branch contains that version and the later handoff records. The deployment section and the H-1 local section below keep development history; this section and "UI adjustments after the user's playtest" are the current state. The submission materials had their routing checked against the code: Gemini Live provides character voice, and Gemini text models provide characters' text replies; Claude handles narration, extraction, checks, memory, safety and candidates. Do not write all character replies as Claude.

本番で動いているイメージのソースは `31e2684` で、デフォルトブランチにはそのバージョンと後続の引き継ぎ記録が含まれる。以下のデプロイの節と H-1 ローカルの節は開発の履歴を残したもので、この節と「ユーザーの試遊後の UI 調整」が現在の状態。提出資料はコードに基づいてルーティングを照合している：人物の音声は Gemini Live、人物のテキスト返答は Gemini のテキストモデルが提供し、Claude は語り、抽出、チェック、記憶、安全性、候補などを担当する。人物の返答をすべて Claude と書いてはならない。

## R-1 regression validation, continued (updated 2026-10-13) / R-1 回帰検証の続き（2026-10-13 更新）

The user has explicitly authorized resuming the previously deferred four-act story, spoiler protection, CI and staged simulation; real-model calls and costs fall within this round's authorization; judge calibration and pre-recorded voice listening remain on hold. The six CI workflows and the isolated local runner have been restored; the actual execution records and unfinished items are in the [R-1 task card / R-1 タスクカード](tasks/r-1/README.md). The "CI stopped" and "evals not run" in the historical snapshots below are superseded by this round's authorization. Resuming tests does not mean tests pass, nor deployment; the entry must still stay private.

ユーザーは、以前延期していた四幕のストーリー、ネタバレ防止、CI、段階的シミュレーションの再開を明示的に承認した。実モデルの呼び出しと費用は今回の承認範囲内。評価者のキャリブレーションと事前録音音声の試聴は引き続き保留。6 つの CI ワークフローと隔離されたローカルランナーは復旧済みで、実際の実行記録と未完了項目は [R-1 タスクカード](tasks/r-1/README.md) にある。以下の過去のスナップショットにある「CI 停止」「評価は実行しない」は今回の承認で置き換えられた。テストの再開はテスト合格を意味せず、デプロイでもない。入口は引き続き非公開を維持する。

The latest scope is fixing four items: endings and unfinished flows, rate limiting and failure records, web/assets CI, and spoiler protection. On 2026-10-13 the user then explicitly skipped the remaining real games and CI to playtest on their own; the current batch was stopped and queued/running CI was cancelled, so it is no longer awaited for acceptance. Completed and interrupted records are kept, and cancellation cannot count as a pass. Neither the 200 games nor the full 980 calls of the four acts were started. The code is on the private branch `r-1-deferred-validation`; the default branch was not modified, and old local results must not be written up as the new version having fully passed. For the extra materials and access gaps for today's submission, see [Submission handoff / 提出の引き継ぎ](tasks/r-1/submission-handoff.md).

最新の範囲は 4 項目の修正：結末と未完了フロー、レート制限と失敗の記録、web/assets CI、ネタバレ防止。2026-10-13 にユーザーは残りの実対局と CI をスキップし、自分で試遊することを明示的に決めた。現在のバッチは停止し、キュー中・実行中の CI はキャンセルしたので、受け入れのために待つことはない。完了した記録と中断した記録は保持し、キャンセルを合格とはできない。200 局も四幕の 980 回の全量も開始していない。コードは非公開ブランチ `r-1-deferred-validation` にある。デフォルトブランチは変更しておらず、古いローカルの結果を新バージョンが全部合格したかのように書いてはならない。今日の提出に必要な追加資料とアクセス上の不足は [提出の引き継ぎ](tasks/r-1/submission-handoff.md) を参照。

## Deployment authorized by the user (2026-10-13) / ユーザー承認によるデプロイ（2026-10-13）

After the user explicitly replied "Deploy", the fixed version was deployed to the existing Cloud Run gateway and narrator; the actual image source commit is `be03d70` (on top of `2ce6b26`, only adding the cloud health-probe path). Both services were switched to 100% production traffic, and the real text/Live configuration and the password Secret references were verified. Both candidate and production addresses passed smoke checks for password, invite code, home page, scene, opening, WebSocket, and rejection of anonymous pages/resources/API; this does not mean whole-game voice or full quality has passed.

ユーザーが明示的に「デプロイ」と返信した後、修正版を既存の Cloud Run ゲートウェイと語り手にデプロイした。実際のイメージのソースコミットは `be03d70`（`2ce6b26` の上にクラウドのヘルスプローブのパスだけを追加）。両サービスとも本番トラフィック 100% に切り替え、実際のテキスト/Live 設定とパスワード Secret の参照を確認した。候補と本番のどちらのアドレスも、パスワード、招待コード、トップページ、シーン、開幕、WebSocket、匿名のページ/リソース/API の拒否に関するスモークチェックに合格した。全局の音声や全量の品質が合格したことを意味しない。

Cloud Run reserves some paths ending in `z`, and the old `/healthz` returns 404 at the platform layer; the cloud probe now uses `/health`, which returns an empty 204, and the old path remains compatible locally. The four gate tests for this change passed; CI and batch games were not resumed.

Cloud Run は `z` で終わる一部のパスを予約しており、旧 `/healthz` はプラットフォーム層で 404 を返す。クラウドのプローブは空の 204 を返す `/health` に変更し、旧パスはローカルでは引き続き互換。この変更の 4 つのゲートテストに合格した。CI とバッチ対局は再開していない。

Cloud IAM is still private, and the privacy lock is kept. The authenticating proxy for the user's Mac to playtest listens only on loopback, with entry `http://127.0.0.1:8090`, and reaches the actual cloud services rather than a fake model. The outer local forwarding fixes the same-origin Origin and removes the Secure cookie attribute only on local HTTP redirects; production cookies in the cloud remain Secure. The password and invite codes, the proxy and the release evidence are only in the local private deployment directory and do not enter the repo. Access for external reviewers without a Google identity has not yet been opened, and the local entry cannot be treated as the contest deployment URL.

クラウドの IAM は引き続き非公開で、プライバシーロックは維持している。ユーザーのこの Mac での試遊用の認証プロキシはループバックのみをリッスンし、入口は `http://127.0.0.1:8090`。アクセス先は偽モデルではなく実際のクラウドサービス。外側のローカル転送は同一オリジンの Origin を補正し、ローカルの HTTP リダイレクトでのみ Secure cookie 属性を外す。クラウドの本番 cookie は引き続き Secure。パスワードと招待コード、プロキシ、リリースの証拠はローカルの非公開デプロイディレクトリにのみあり、リポジトリには入れない。Google アカウントを持たない外部レビュー担当者のアクセス方法はまだ開放しておらず、ローカルの入口をコンテストのデプロイ URL として扱ってはならない。

### External review entry prepared per the user's instruction / ユーザーの指示に従って準備した外部レビュー用入口

The user then explicitly asked "Set up the external review entry too, it must have a password". All temporary tags on the gateway were cleared, and only the gateway HTTPS entry with a verified password is open; the narrator service stays IAM-private. Without a Google identity or cookie, 17 paths in total, covering the actual frontend scripts, GLBs, scene entries, audio paths and API, were all blocked by the password gate, the unauthenticated WebSocket handshake was rejected, and the page showed only the password form. After the password, an invite-code login is also required, and the production cookie stays Secure/HttpOnly.

ユーザーはその後、「外部レビュー用の入口も整えてほしい。必ずパスワード付きで」と明示的に求めた。ゲートウェイの一時タグはすべて削除し、パスワードを確認済みのゲートウェイの HTTPS 入口だけを開放した。語り手サービスは IAM で非公開のまま。Google アカウントや cookie がない状態では、実際のフロントエンドのスクリプト、GLB、シーンの入口、音声パス、API を含む計 17 のパスがすべてパスワードゲートで遮断され、未認証の WebSocket ハンドシェイクは拒否され、ページにはパスワードフォームだけが表示された。パスワードの入力後はさらに招待コードでのログインが必要で、本番 cookie は Secure/HttpOnly を維持している。

The reviewer main account and two spare invite codes are ready. The main account keeps a genuinely generated opening state; external login, book catalog, progress, character resources and WebSocket startup passed, and no ending was faked. The Japanese notes and all URLs/credentials are only in the local private deployment directory. The privacy lock is kept, with a new local authorization record that allows only a verified current version; future deployment, switching or rollback must first restore IAM-private. The related 25 short tests passed, and batch games and CI were not resumed. The code was synced to the private repository's default branch main for the contest to read; publication of the notes, architecture diagrams and video, and the formal submission, have still not been done.

レビュー担当者のメインアカウントと予備の招待コード 2 つを用意した。メインアカウントは実際に生成された開幕状態を保持している。外部ログイン、書籍カタログ、進捗、人物リソース、WebSocket の起動に合格し、結末の偽造はしていない。日本語の説明とすべての URL/認証情報はローカルの非公開デプロイディレクトリにのみある。プライバシーロックは維持しており、確認済みの現行バージョンだけを許可するローカルの承認記録を新設した。今後のデプロイ、切り替え、ロールバックは、まず IAM を非公開に戻さなければならない。関連する 25 項目の短いテストに合格し、バッチ対局と CI は再開していない。コードは非公開リポジトリのデフォルトブランチ main に同期し、コンテストが読めるようにした。説明、アーキテクチャ図、動画の公開と正式な提出は依然として未実施。

### UI adjustments after the user's playtest / ユーザーの試遊後の UI 調整

The user pointed out that the dialogue blocks the scene, and then explicitly said it only needs to be collapsible by hand. `31e2684` adds 「字幕をたたむ／字幕をひらく」, which only toggles local display: it does not clear the current text, pause the sound, or trigger actions or the model; the blank area after collapsing can be clicked through to 3D. The 「原作を読んでいない方へ」 on the book-selection page can be expanded to see the opening background and the character relationships before the original's opening, without giving future beats or endings and without forcing a replay of the original plot; content is isolated by book ID.

ユーザーは会話がシーンを隠すと指摘し、その後、手動で畳めれば十分だと明示した。`31e2684` で「字幕をたたむ／字幕をひらく」を追加した。切り替えるのはローカルの表示だけで、現在の文字は消さず、音声も止めず、アクションやモデルも発動しない。畳んだ後の空白部分は 3D までクリックが通る。本選択ページの「原作を読んでいない方へ」を展開すると、開幕の背景と原作の開幕前の人物関係を見られる。未来のビートや結末は示さず、原作のストーリーの再演も強制しない。内容は書籍 ID ごとに分離している。

Type checks, lint, build and size checks passed (first screen 108.1 KB / 120, 3D 235.3 KB / 250). Local browser checks with real 3D + mock model confirmed collapse and expand on phone/desktop, text retention and click-through; the opening introduction is readable in phone portrait and landscape, with screenshots kept outside the repo. Independent review confirmed no new future information or data writes. This is UI verification, not certification of character voice quality.

型チェック、lint、ビルド、サイズチェックに合格（最初の画面 108.1 KB / 120、3D 235.3 KB / 250）。実際の 3D＋mock モデルによるローカルのブラウザチェックで、スマホ/デスクトップでの折りたたみと展開、文字の保持、クリックの透過を確認した。開幕の紹介はスマホの縦横どちらでも読め、スクリーンショットはリポジトリの外に保存している。独立レビューで、新たな未来情報やデータの書き込みがないことを確認した。これは UI の検証であり、人物の音声品質の認証ではない。

This version has been updated onto the existing service; before deployment, IAM-private was first restored and anonymous 403 actually confirmed, and after the candidate and production password/login/opening smoke tests passed the temporary tags were cleared, and only after re-verifying the 17 external content paths and the reviewer login/resources/WebSocket was the external entry restored. The original account, password, invite codes and the reviewer sample progress are kept, and CI and batch games were not resumed.

このバージョンは既存サービスに更新済み。デプロイ前にまず IAM の非公開を復元して匿名 403 を実際に確認し、候補と本番のパスワード/ログイン/開幕のスモークテストに合格した後で一時タグを削除し、外部の 17 のコンテンツパスとレビューのログイン/リソース/WebSocket を再検証してから外部の入口を復旧した。元のアカウント、パスワード、招待コード、レビュー用のサンプル進捗は保持しており、CI とバッチ対局は再開していない。

## H-1 local continuation (updated the same day) / H-1 ローカル続編（同日更新）

The user made clear the product is a multi-book platform, currently with only 《走れメロス》; a new original European-style study was added, where one picks a book from the shelf, continues server saves, and revisits endings one personally experienced. For implementation and verification see the [H-1 delivery record / H-1 納品記録](tasks/h-1/README.md). The code and generated assets are currently only on the local branch `h-1-reader-home`, not pushed and not deployed, so local results must not be taken as live.

ユーザーは、製品が複数書籍のプラットフォームであり、現在は『走れメロス』だけだと明確にした。新たにオリジナルの欧風書斎を追加し、本棚から本を選び、サーバーのセーブを続け、自分で経験した結末を見返せる。実装と検証は [H-1 納品記録](tasks/h-1/README.md) を参照。コードと生成アセットは現在ローカルブランチ `h-1-reader-home` にのみあり、プッシュもデプロイもしていないので、ローカルの結果を公開済みとして扱ってはならない。

The user required strict confidentiality. The anonymous invocation permission of the old live gateway was revoked, and anonymous pages, book catalog and character list were verified to return 403; the new local version adds a site-wide password gate, protecting static resources, API and WS. The deployment script no longer opens the service automatically and respects the local privacy lock; every deployment still needs separate authorization. The no-password live state in section 3 below and the ungenerated characters in section 4 are handoff snapshots from before this continuation, not current acceptance results.

ユーザーは厳格な秘匿を求めた。旧オンラインゲートウェイの匿名呼び出し権限を取り消し、匿名のページ、書籍カタログ、人物リストが 403 を返すことを確認した。ローカルの新バージョンはサイト全体のパスワードゲートを追加し、静的リソース、API、WS が保護される。デプロイスクリプトはサービスを自動で公開しなくなり、ローカルのプライバシーロックを尊重する。デプロイのたびに個別の承認が必要。以下の第 3 節のパスワードなしのオンライン状態と第 4 節の未生成の人物は、この続編より前の引き継ぎスナップショットであり、現在の受け入れ結果ではない。

## 1. What this is / これは何か

- **Product**: a realistic 3D multi-book platform where you enter the world of a book; currently the only open book is Osamu Dazai's 『走れメロス』. Players pick a book from their own study, walk around in a phone browser, and talk with characters in the book by Japanese voice. The Narrator Agent is the sole writer of world state, and endings have three layers. The target users are Japanese adults aged 18〜34, and the first version is only for invited people aged 18 or over.
  **製品**：書の世界に入る写実的な 3D 複数書籍プラットフォーム。現在公開している書籍は太宰治『走れメロス』のみ。プレイヤーは自分の書斎から本を選び、スマホのブラウザで歩き回り、日本語の音声で本の中の人物と会話する。語り手エージェントが世界状態の唯一の書き手で、結末は 3 層に分かれる。ターゲットは日本の 18〜34 歳の成人で、第 1 版は招待された 18 歳以上の人のみが遊べる。
- **Tech stack**: / **技術スタック**：
  - Frontend: `apps/web`, Vite, React, Three.js, mobile-first.
    フロントエンド：`apps/web`、Vite、React、Three.js、モバイルファースト。
  - Backend: `services/backend`, one Python package containing the gateway, narrator and mock. Managed with uv, the database is PostgreSQL, migrations use Alembic.
    バックエンド：`services/backend`、ゲートウェイ、語り手、mock を含む 1 つの Python パッケージ。uv で管理し、データベースは PostgreSQL、マイグレーションは Alembic を使う。
  - Models: Claude handles narration, intent extraction, rule checks, memory, safety and candidate generation; Google Gemini provides characters' text replies and Gemini Live provides characters' voice, plus pre-recorded lines and Model Armor.
    モデル：Claude が語り、意図の抽出、ルールチェック、記憶、安全性、候補生成を担当する。Google Gemini が人物のテキスト返答、Gemini Live が人物の音声を提供し、そのほかに事前録音の台詞と Model Armor を使う。
  - Deployment: GCP Cloud Run runs the gateway and narrator, Cloud SQL stores data, and secrets go in Secret Manager. Deployed with gcloud scripts, not Terraform.
    デプロイ：GCP Cloud Run でゲートウェイと語り手を動かし、Cloud SQL にデータを保存し、秘密情報は Secret Manager に置く。gcloud スクリプトでデプロイし、Terraform は使わない。
- **Repository / リポジトリ**: `guoziyu415/zoujin` (private / 非公開).

| Directory / ディレクトリ | Contents / 内容 |
| --- | --- |
| `apps/web` | Web frontend / ウェブフロントエンド |
| `services/backend` | Gateway, narrator / ゲートウェイ、語り手 |
| `packages/contracts` | JSON Schema contracts, and the generated Python and TS types / JSON Schema 契約、および生成された Python と TS の型 |
| `packages/worldsim` | World-state rules library / 世界状態のルールライブラリ |
| `worlds/hashire-merosu/` | World model; production uses `1.0.0-slice` / ワールドモデル。本番では `1.0.0-slice` を使う |
| `assets/` | Art pipeline `pipeline/`, scene layouts `scenes/<scene>/layout.json`, character manifest `cast/cast.json`, pre-recorded voice `voice/` / アートパイプライン `pipeline/`、シーンレイアウト `scenes/<シーン>/layout.json`、人物マニフェスト `cast/cast.json`、事前録音音声 `voice/` |
| `evals/` | Evaluation cases and probe questions (not run now) / 評価ケースとプローブ問題（現在は実行しない） |
| `infra/deploy/` | Deployment scripts / デプロイスクリプト |
| `docs/` | Design documents. PRD, decision records and the dev plan are in `docs/pm/`, handoff snapshots in `docs/brief/` / 設計文書。PRD、決定記録、開発計画は `docs/pm/`、引き継ぎスナップショットは `docs/brief/` |

- **Key documents**: / **主要文書**：
  - Master brief: the project shared folder `app-team/brief/handoff.md`, with a snapshot in the repo at `docs/brief/`.
    総合 brief：プロジェクト共有フォルダ `app-team/brief/handoff.md`。リポジトリにスナップショットが `docs/brief/` にある。
  - API contract: `app-team/backend/api-contract.md`.
    API 契約：`app-team/backend/api-contract.md`。
  - Data contract: `app-team/data/contracts.md`.
    データ契約：`app-team/data/contracts.md`。
  - How to add things and how to merge: `CONTRIBUTING.md`.
    追加の仕方とマージの仕方：`CONTRIBUTING.md`。
  - Deployment: `infra/deploy/README.md`.
    デプロイ：`infra/deploy/README.md`。

## 2. Build and deployment / ビルドとデプロイ

**Asset builds** (outputs do not go into git, S-075) / **アセットのビルド**（成果物は git に入れない、S-075）：

- Scenes: `assets/pipeline/{plaza,castle,road,village,crowd}/build.sh`, outputting to `assets/scenes/<scene>/build/`. `scene.json` is generated from `layout.json` and is committed to the repo.
  シーン：`assets/pipeline/{plaza,castle,road,village,crowd}/build.sh`。出力先は `assets/scenes/<シーン>/build/`。`scene.json` は `layout.json` から生成され、リポジトリにコミットされる。
- Characters: `assets/pipeline/cast/build.sh [name…]`. First set `MELOS_BLEND` (`melos_v2.blend` on the Mac) and `BPY_PYTHON` (`~/.zoujin/bpy-venv` on the Mac). Outputs to `assets/cast/build/<name>/` and also updates `assets/cast/cast.json`.
  人物：`assets/pipeline/cast/build.sh [名前…]`。先に `MELOS_BLEND`（Mac 上の `melos_v2.blend`）と `BPY_PYTHON`（Mac 上では `~/.zoujin/bpy-venv`）を設定しておく。出力先は `assets/cast/build/<名前>/` で、同時に `assets/cast/cast.json` も更新する。
- These all need Blender 5.2, bpy and MPFB 2, installed only on zg's Mac.
  これらはすべて Blender 5.2、bpy、MPFB 2 が必要で、zg の Mac にしかインストールされていない。

**Deployment** (can only be run on zg's Mac; state is in `~/.zoujin/deploy/`) / **デプロイ**（zg の Mac でのみ実行可能。状態は `~/.zoujin/deploy/` にある）：

```sh
cd ~/Developer/zoujin && git pull && infra/deploy/deploy.sh all   # setup→build→migrate→up→promote
infra/deploy/deploy.sh verify      # smoke test against production / 本番に対するスモークテスト
infra/deploy/deploy.sh invite 5    # issue 5 invite codes, written to ~/.zoujin/deploy/invites-*.txt / 招待コードを 5 個発行し ~/.zoujin/deploy/invites-*.txt に書く
infra/deploy/deploy.sh rollback    # switch back to the previous version / 1 つ前のバージョンに戻す
infra/deploy/deploy.sh check       # read-only, view current state / 読み取り専用、現状を確認
```

- `build` first runs the `infra/deploy/packs.py` preflight, comparing scene packs and character models against the manifest of the current commit. Missing or stale ones are listed with the pipeline commands to run, and then it stops. Only when something is "stale" and you are sure to deploy it as is, add `ZJ_ALLOW_STALE=1`.
  `build` はまず `infra/deploy/packs.py` の事前チェックを実行し、シーンパックと人物モデルを現在のコミットのマニフェストと比較する。欠けているもの、古いものは、実行すべきパイプラインのコマンドとともに列挙され、そこで停止する。「古い」だけで、そのままデプロイすると確信できる場合にのみ `ZJ_ALLOW_STALE=1` を付ける。
- The production address is in `~/.zoujin/deploy/url`, and the smoke account in `~/.zoujin/deploy/smoke-code`. Neither may go into the repo or be posted in chat.
  本番のアドレスは `~/.zoujin/deploy/url`、スモークテスト用アカウントは `~/.zoujin/deploy/smoke-code` にある。どちらもリポジトリに入れてはならず、チャットに貼ってもならない。
- Claude's auto mode on the Mac blocks "merging an unreviewed PR" and "deploying an unreviewed commit", so redeployment must be run by zg himself in the terminal.
  Mac 上の Claude の自動モードは「レビューしていない PR のマージ」と「レビューしていないコミットのデプロイ」をブロックするので、再デプロイは zg 自身がターミナルで実行する必要がある。

## 3. Current production state / オンラインの現状

- Production is main's `f25adea` (deployed by zg himself at 05:31 on 10-12 Japan time); login is by invite code only, with no password. Without a code you are rejected, and the narrator accepts calls only from the gateway's IAM identity.
  本番は main の `f25adea`（日本時間 10-12 05:31 に zg 自身がデプロイ）。招待コードでのみログインでき、パスワードはない。コードがなければ拒否され、語り手はゲートウェイの IAM アイデンティティからの呼び出しだけを受け付ける。
- At the first deployment the smoke test passed 14/14, and 5 invite codes were issued.
  最初のデプロイ時のスモークテストは 14/14 で合格し、招待コードを 5 個発行した。
- main is now at `a0c6a5c`, one more than production (#265), see item 3 of section 4.
  main は現在 `a0c6a5c` で、本番より #265 の 1 つ分進んでいる。第 4 節の第 3 項を参照。

## 4. Known issues and unfinished work (by priority) / 既知の問題と未完了の作業（優先度順）

1. **5 characters have no real-person model and appear as gray capsules**: the traveler (the player themselves), メロス, 市の老爺, 市の若い衆, 市の少女. Characters without a model are drawn as capsules by `apps/web/src/three/mannequin.ts`.
   **5 人の人物に実人物のモデルがなく、灰色のカプセルで表示される**：旅人（プレイヤー自身）、メロス、市の老爺、市の若い衆、市の少女。モデルのない人物は `apps/web/src/three/mannequin.ts` がカプセルとして描く。
   - **main already has 9 sets**, and production runs exactly these 9: the king, セリヌンティウス, the sister, the bridegroom, フィロストラトス, the apprentice, the shepherd boy, plus the sister's and bridegroom's wedding outfits (#237, #239, #250).
     **main にはすでに 9 セットある**。本番にデプロイされているのはまさにこの 9 セット：王、セリヌンティウス、妹、花婿、フィロストラトス、徒弟、牧童、それに妹と花婿の婚礼衣装（#237、#239、#250）。
   - **A half-finished branch** `claude/f16-characters-trl9n4` (`f070434`, not yet merged, based on the main of that time). The branch has already done:
     **途中まで進んだブランチ** `claude/f16-characters-trl9n4`（`f070434`、未マージ、当時の main がベース）。ブランチではすでに次を実施している：
     - Settings for the 5 characters: `role.traveler`, `char.melos`, the old man, the young men, the girl, written in `assets/pipeline/cast/characters.json`.
       5 人の設定：`role.traveler`、`char.melos`、老爺、若い衆、少女を `assets/pipeline/cast/characters.json` に記述。
     - New costume pieces, a hat and a belt, written in `build_cast.py`.
       新しい衣装パーツの帽子とベルトを `build_cast.py` に記述。
     - In `build.sh`, メロス is exported directly from A-0's `melos_v2.blend`.
       `build.sh` 内で、メロスは A-0 の `melos_v2.blend` から直接エクスポートする。
     - The runtime CAST has these 5 added (`apps/web/src/three/cast/cast.ts`).
       実行時の CAST にこの 5 人を追加（`apps/web/src/three/cast/cast.ts`）。
     - The ending stage `ending/Staging.tsx` was also switched to real people.
       結末ステージ `ending/Staging.tsx` も実人物に切り替えた。
     - All 291 unit tests pass, type checking passes, and the 3D main chunk is 226/250 KB.
       291 個のユニットテストはすべて合格し、型チェックも合格。3D のメインチャンクは 226/250 KB。
   - **These 5 model sets have not been generated yet**; the build stopped midway. Remaining steps:
     **この 5 セットのモデルはまだ生成されていない**。ビルドは途中で止まった。残りの手順：
     1. Generate the 5 sets at the repo root. Each takes about 20〜25 minutes, and you can run one process per person in parallel:
        `BPY_PYTHON=<python with bpy 5.2, numpy, pillow> MELOS_BLEND=<shared folder app-team/frontend/spikes/a0-melos/mac/melos_v2.blend> UAL_GLB=<anims/UAL1_Standard.glb in the same directory> bash assets/pipeline/cast/build.sh traveler melos old-man young-man maiden`
        After all finish, run `node assets/pipeline/cast/check_cast.mjs assets/cast/build assets/cast/cast.json` once more.
        リポジトリのルートでこの 5 セットを生成する。1 人あたり約 20〜25 分かかり、1 人 1 プロセスで並列に実行できる：
        `BPY_PYTHON=<bpy 5.2、numpy、pillow を含む python> MELOS_BLEND=<共有フォルダ app-team/frontend/spikes/a0-melos/mac/melos_v2.blend> UAL_GLB=<同じディレクトリの anims/UAL1_Standard.glb> bash assets/pipeline/cast/build.sh traveler melos old-man young-man maiden`
        すべて終わったら、もう一度 `node assets/pipeline/cast/check_cast.mjs assets/cast/build assets/cast/cast.json` を実行する。
     2. Commit `assets/cast/cast.json` and merge the branch into main.
        `assets/cast/cast.json` をコミットし、ブランチを main にマージする。
     3. Pack the 14 directories under `assets/cast/build/` into a tar, copy it to the Mac, and redeploy.
        `assets/cast/build/` 以下の 14 ディレクトリを tar にまとめて Mac にコピーし、再デプロイする。
   - **Notes**: / **注意**：
     - In `lod_export.py`, bpy must be imported before bmesh.
       `lod_export.py` では、bmesh より先に bpy をインポートする必要がある。
     - The traveler's hat and belt are newly written and nobody has seen the finished result; the positions may need adjusting.
       旅人の帽子とベルトは新規に書いたもので、完成品を見た人はまだいない。位置の調整が必要かもしれない。
   - **Not yet done**: / **未着手**：
     - The crowd layer has packs only for the plaza. The city's constables, bandits, the travelers' group, and crowds in other scenes have no real-person models yet.
       群衆レイヤーのパックは広場にしかない。城の警吏、山賊、旅の一団、およびほかのシーンの群衆には、まだ実人物のモデルがない。
     - The maids and constable apprentices are planned for version 2.
       侍女、警吏見習いは第 2 版に回す予定。
2. **Characters' positions overlap** (screenshot: a capsule right next to セリヌンティウス). Not fixed; below are the directions investigated:
   **人物の立ち位置が重なる**（スクリーンショット：セリヌンティウスのすぐ隣にカプセル）。未修正。以下は調べた方向：
   - **Positions are assigned by the server**: `snapshot()` in `services/backend/src/zoujin_backend/projection.py` (about lines 300〜315) calls `Scene.character_spots()` in `world.py`. The rule is that characters in order take the free spots at their own location, skipping `way.*` and `auto: false` spots, with the spot the player stands on counted as occupied. **When spots run out, the extra people overlap others on the first usable spot** (`world.py` about lines 55〜67). The frontend `apps/web/src/three/People.tsx` just draws at the spot the server gives.
     **立ち位置はサーバーが割り当てる**：`services/backend/src/zoujin_backend/projection.py` の `snapshot()`（約 300〜315 行）が `world.py` の `Scene.character_spots()` を呼ぶ。規則は、人物が順番に自分のいる場所の空いている点を取り、`way.*` と `auto: false` の点は飛ばし、プレイヤーが立っている点は占有済みとして数える。**点が足りないと、余った人は最初に使える点で他の人と重なる**（`world.py` の約 55〜67 行）。フロントエンドの `apps/web/src/three/People.tsx` はサーバーが与えた spot のとおりに描くだけ。
   - **The most likely cause is that the stonemason's workshop has too few spots**: what is read is the generated `assets/scenes/syracuse-square/scene.json`, not `layout.json`, and which place a spot belongs to is decided by the navmesh. The spots in `place.stonemason-workshop` that can be auto-assigned are only `workshop-yard` and `workshop-bench`: `workshop-gate` was judged to belong to the plaza, and `workshop-door` is `auto: false`. セリヌンティウス and フィロストラトス both start in the stonemason's workshop (`initialPlace` in `worlds/hashire-merosu/1.0.0-slice/world.json`). As soon as the player walks into the workshop they take `workshop-yard` (`startSpots`), and the other two can only squeeze onto `workshop-bench`. When beats move people such as メロス in, the same thing happens.
     **最も可能性が高い原因は石工房の点が少ないこと**：読み込まれるのは生成された `assets/scenes/syracuse-square/scene.json` で `layout.json` ではなく、ある点がどの場所に属するかは navmesh が判定する。石工房 `place.stonemason-workshop` で自動割り当てできる点は `workshop-yard` と `workshop-bench` の 2 つだけ：`workshop-gate` は広場に判定され、`workshop-door` は `auto: false`。セリヌンティウスとフィロストラトスは開始時にどちらも石工房にいる（`worlds/hashire-merosu/1.0.0-slice/world.json` の `initialPlace`）。プレイヤーが石工房に入るとすぐ `workshop-yard` を占め（`startSpots`）、残りの 2 人は `workshop-bench` に押し込まれるしかない。ビートでメロスなどが移動してきても同じことが起きる。
   - **Other possibilities**: / **ほかの可能性**：
     - (a) There is no dedup among people whose spot was specified by a beat's relocate (`fixed`); if two people are pointed at the same spot they overlap.
       (a) ビートの relocate で spot を指定された人（`fixed`）の間で重複排除がなく、2 人が同じ点を指されると重なる。
     - (b) The capsule may be the player themselves (the traveler is also a capsule); the player's position is determined by `Player.tsx` and `startSpots`, and may be very close to a character's spot.
       (b) カプセルはプレイヤー自身かもしれない（旅人もカプセル）。プレイヤーの位置は `Player.tsx` と `startSpots` で決まり、人物の点のすぐ近くになることがある。
     - (c) The spots themselves are too close, e.g. `workshop-bench` and `workshop-door` are only about 2.7 m apart.
       (c) 点同士が近すぎる。例えば `workshop-bench` と `workshop-door` は約 2.7 m しか離れていない。
     - (d) The random placement of the frontend `three/crowd/` crowd collides with the characters' spots.
       (d) フロントエンド `three/crowd/` の群衆のランダム配置が、人物の点と衝突している。
   - **How to investigate**: at the moment the problem occurs, fetch `GET /v1/playthroughs/{pid}/snapshot` and look at whether `characters[].spot` has duplicate values; this distinguishes a server assignment problem from a frontend problem. The fix is generally to add spots to the workshop in `layout.json` and rerun `plaza/build.sh` to generate `scene.json`; alternatively change the fallback of `character_spots` so the extra people stand staggered nearby.
     **調べ方**：問題が起きた瞬間に `GET /v1/playthroughs/{pid}/snapshot` を取得し、`characters[].spot` に重複した値がないかを見る。これでサーバーの割り当ての問題かフロントエンドの問題かを区別できる。修正は一般に、`layout.json` で石工房に点を追加し、`plaza/build.sh` を再実行して `scene.json` を生成する。または `character_spots` のフォールバックを変更し、余った人が近くにずれて立つようにしてもよい。
3. **`/v1/telemetry` returns 404 in production**: the fix #265 has been merged into main but not deployed. The next deployment will bring it along.
   **`/v1/telemetry` が本番で 404 を返す**：修正 #265 は main にマージ済みだが、デプロイはまだ。次回のデプロイで一緒に反映される。
4. **PR #263 is still open**: it is a backup fix for the black-screen problem (black screen after choosing a character), changing the vite castle chunk regex. The official fix #264 is already live, so #263 can be merged or closed.
   **PR #263 はまだ開いている**：黒画面の問題（人物を選んだ後の黒画面）の予備の修正で、vite の castle 分割の正規表現を変更するもの。正式な修正 #264 はすでに公開済みなので、#263 はマージしても閉じてもよい。
5. **Two tests on main were already red**: reported by data engineering at 03:18 on 10-12 (Japan time), unrelated to recent changes, and not yet fixed. Run `uv run pytest` to see which two (needs a local PostgreSQL).
   **main には元から赤いテストが 2 つある**：データエンジニアリングが 10-12 03:18（日本時間）に報告したもので、最近の変更とは無関係。まだ修正していない。`uv run pytest` を実行すればどの 2 つかわかる（ローカルの PostgreSQL が必要）。
6. **Deleted steps 14, 15, 26** (four-act evals, 200-game simulation personas, CI): how far they got and where to resume are written in the shared folder `app-team/pm/deferred-steps.md`. The self-hosted CI runner is parked on zg's Mac, and all 6 workflows are disabled.
   **削除した第 14、15、26 ステップ**（四幕評価、200 局シミュレーションのペルソナ、CI）：どこまで進み、どこから再開するかは共有フォルダ `app-team/pm/deferred-steps.md` に書いてある。CI のセルフホストランナーは zg の Mac で停止中で、6 つのワークフローはすべて disabled 状態。
7. **Not tested on a real phone after going live.**
   **公開後にスマホの実機でテストしていない。**

## 5. Project conventions / プロジェクトの約束事

- **No secrets in the repo**; addresses, passwords, invite codes, tokens and GCP project IDs also stay out. Secrets are kept in Secret Manager and the Mac keychain (`zoujin-claude`).
  **リポジトリに秘密情報を置かない**。アドレス、パスワード、招待コード、トークン、GCP プロジェクト ID も置かない。秘密情報は Secret Manager と Mac のキーチェーン（`zoujin-claude`）に置く。
- **Asset build outputs do not go into git**, including `assets/scenes/*/build/` and `assets/cast/build/`. Commit only manifests and `scene.json`. Hand-made `.blend` and `glb` go through LFS.
  **アセットのビルド成果物は git に入れない**。`assets/scenes/*/build/` や `assets/cast/build/` を含む。コミットするのはマニフェストと `scene.json` だけ。手作業の `.blend` と `glb` は LFS を使う。
- **zg's Mac disk is case-insensitive**, so don't let two filenames differ only in case. **`/bin/bash` is 3.2**, so scripts can't use constructs like `mapfile` or associative arrays.
  **zg の Mac のディスクは大文字小文字を区別しない**ので、大文字小文字だけが違う 2 つのファイル名を作らないこと。**`/bin/bash` は 3.2** なので、スクリプトで `mapfile` や連想配列のような書き方は使えない。
- The earlier process was that authors merged their own PRs after running the unit tests for their own changes, with no review (D-037) and no CI. Without CI, note that parallel PRs may collide on the Alembic migration number; before merging, check the largest migration number on main.
  以前の流れは、作者が自分の変更のユニットテストを実行したら自分で PR をマージし、レビューも CI もなし（D-037）だった。CI がないときは、並行する PR が Alembic のマイグレーション番号とぶつかることがあるので注意する。マージの前に main の最大のマイグレーション番号を確認する。
- Docs and commit messages were written in Chinese (now English and Japanese); in-game text is Japanese.
  文書とコミットメッセージは中国語で書いていた（現在は英語と日本語）。ゲーム内のテキストは日本語。
