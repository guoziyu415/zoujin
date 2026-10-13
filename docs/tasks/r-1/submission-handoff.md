# Handoff for today's submission (2026-10-13) / 本日の提出の引き継ぎ（2026-10-13）

This file is an internal preparation checklist, not proof that anything has been submitted, deployed, or passed full acceptance. The user's latest decision is to skip the remaining real games and CI and playtest on their own. What was actually completed, what the user interrupted, and what was not run are kept separately in [R-1](README.md), the [eval record / 評価記録](eval-review.md) and the [anti-spoiler record / ネタバレ防止記録](spoiler.md).

このファイルは内部の準備チェックリストであり、提出済み・デプロイ済み・全量の受け入れ確認合格を証明するものではない。ユーザーの最新の決定は、残りの実対局と CI をスキップし、自分で試遊すること。実際に完了したもの、ユーザーが中断したもの、未実行のものは、それぞれ [R-1](README.md)、[評価記録](eval-review.md)、[ネタバレ防止記録](spoiler.md) に残している。

## Official requirements and confidentiality boundary / 公式要件と秘密保持の境界

On 2026-10-13 we checked the [official page of the 5th Agentic AI Hackathon with Google Cloud / 第 5 回 Agentic AI Hackathon with Google Cloud 公式ページ](https://zenn.dev/hackathons/google-cloud-japan-ai-hackathon-vol5). The deadline is 2026-10-15; a private GitHub repository is allowed, and judging uses the default branch. Required: a deployment URL, a project description, an architecture diagram image, and a YouTube demo video of about three minutes. If authentication is needed, a test account must be provided that needs no social login or email receipt, and visible sample data must be prepared.

2026-10-13 に [第 5 回 Agentic AI Hackathon with Google Cloud 公式ページ](https://zenn.dev/hackathons/google-cloud-japan-ai-hackathon-vol5) を確認した。締め切りは 2026-10-15。非公開の GitHub リポジトリも可で、審査はデフォルトブランチを使う。提出が必要なのは、デプロイ URL、プロジェクト説明、アーキテクチャ図の画像、約 3 分の YouTube デモ動画。認証が必要な場合は、ソーシャルログインやメール受信が不要なテストアカウントを用意し、見られるサンプルデータを準備する必要がある。

Official notes: after the deadline, project-page content such as the project description, architecture diagram and demo video becomes public; the repository and deployment URL are for judges only. The user has explicitly allowed the product concept, project description, architecture diagram and demo video to be public; the actual app still requires a password, and credentials remain private. The default branch state and an accessible deployment must be kept until December 1. The latest [submission materials / 提出資料](../../submission/README.md) supersede the original "description/architecture still to be prepared" state below; video recording and upload are the user's responsibility.

公式の説明：締め切り後、プロジェクト説明、アーキテクチャ図、デモ動画などのプロジェクトページの内容は公開される。リポジトリとデプロイ URL は審査用のみ。ユーザーは、製品コンセプト、プロジェクト説明、アーキテクチャ図、デモ動画の公開を明示的に許可した。実際のアプリには引き続きパスワードが必要で、認証情報は公開しない。デフォルトブランチの状態とアクセス可能なデプロイは 12 月 1 日まで維持する必要がある。最新の [提出資料](../../submission/README.md) が、下記の当初の「説明・アーキテクチャは準備中」という状態に取って代わる。動画の録画とアップロードはユーザーが担当する。

## What can be handed over now / 現時点で引き継げる内容

- The fix code is synced to the private default branch `main`, and the working branch `r-1-deferred-validation` is kept. On 2026-10-14 the action-entry version `182c8b0` was deployed to the two existing Cloud Run services, with 100% production traffic. Candidate and production smoke tests, the password gate, reviewer login, existing progress and WebSocket startup passed; the live UI was confirmed to show 「行動・移動」, destinations and 「時間を進めて待つ」. 29 session unit tests, type checks, targeted lint, build and bundle checks passed; the full CI and real games were not rerun.
  修正コードは非公開のデフォルトブランチ `main` に同期し、作業ブランチ `r-1-deferred-validation` は残している。2026-10-14 にアクション入口のバージョン `182c8b0` を既存の 2 つの Cloud Run サービスにデプロイし、本番トラフィックは 100%。候補と本番のスモークテスト、パスワードゲート、レビュアーのログイン、既存の進捗、WebSocket の起動に合格した。本番 UI で「行動・移動」、行き先、「時間を進めて待つ」を確認した。セッションの単体テスト 29 件、型チェック、対象を絞った lint、ビルド、バンドルチェックに合格。完全な CI と実対局は再実行していない。
- The new entry uses the server's currently available actions and location exits directly, and before running an action it shows how much story time will be spent; the result shows whether it was actually completed, refused or partly completed. Waiting advances story time; walking within the same scene or waiting in real time does not. After a disconnect, unconfirmed actions are not retried automatically, and the story or save is not forcibly rewritten.
  新しい入口はサーバーの現在利用可能なアクションと場所の出口をそのまま使い、実行前に消費する物語時間を表示する。結果には、実際に完了・拒否・一部完了のどれだったかを表示する。待つと物語時間が進むが、同じシーン内を歩いたり現実で待ったりしても進まない。切断後の未確認アクションは自動で再試行せず、ストーリーやセーブを強制的に書き換えない。
- Already in place: an original study, a multi-book catalog, continuing the same game, recollection of endings actually reached, 17 character sets, and a site-wide password gate. Only one book is actually open right now; do not advertise a second book as finished.
  すでにあるもの：オリジナルの書斎、複数の本のカタログ、同じゲームの続き、実際に到達したエンディングの回想、登場人物 17 セット、サイト全体のパスワードゲート。現在実際に公開している本は 1 冊だけで、2 冊目が完成したと宣伝してはならない。
- The local deployment packaging preflight for scenes and characters passed. Build inputs and local generated files are kept; CI cancelled by the user does not count as passing.
  シーンと登場人物のローカルでのデプロイ用パッケージングのプリフライトに合格した。ビルド入力とローカルの生成物は残している。ユーザーがキャンセルした CI は合格とみなさない。
- The startup script for the [local preview / ローカルプレビュー](../../../infra/deploy/README.md) is `uv run python infra/deploy/local-preview.py`; it listens only locally and includes the site password and a separate database. **This script uses a fake model and is only suitable for UI/flow checks; it cannot be treated as a real AI game.** The script writes credentials to a local private file; they are not listed here.
  [ローカルプレビュー](../../../infra/deploy/README.md) の起動スクリプトは `uv run python infra/deploy/local-preview.py` で、ローカルのみをリッスンし、サイトのパスワードと独立したデータベースを含む。**このスクリプトは偽モデルを使うので、UI やフローの確認にしか向かず、実際の AI 対局とはみなせない。** 認証情報はスクリプトがローカルの非公開ファイルに書き込み、ここには載せない。
- The user then explicitly authorized the external review entry. The gateway currently allows HTTPS to reach the password page; the actual content is still protected by the site-wide password, and progress/API additionally require an invite code; the narrator is IAM-private. Reviewers need no Google login; the main account has real opening progress, and there are two spare accounts. The deployment URL and the Japanese 「動作確認の方法」 are only in a local private file and do not go into the public description.
  ユーザーはその後、外部レビュー用の入口を明示的に承認した。現在ゲートウェイは HTTPS でパスワードページまで到達できるが、実際のコンテンツは引き続きサイト全体のパスワードで保護され、進捗と API にはさらに招待コードが必要。ナレーターは IAM で非公開。レビュアーは Google ログイン不要で、メインアカウントには実際の開幕の進捗があり、予備アカウントが 2 つある。デプロイ URL と日本語の「動作確認の方法」はローカルの非公開ファイルにのみあり、公開の説明には入れない。

## Specific gaps before the formal submission / 正式提出前の具体的な不足

1. Done: the final Japanese description, short summary, architecture PNG/SVG, Agency for Cultural Affairs and UNESCO materials, scoring correspondence, and recording script. The old Firestore, Memory Bank, ADK and Veo plan in the existing `docs/brief/handoff.md` must not be submitted; this architecture was checked against the actual routing: character voice and text replies are provided by Google Gemini, and narration and other processing by Claude.
   完了：最終的な日本語の説明、短い概要、アーキテクチャの PNG/SVG、文化庁と UNESCO の資料、採点との対応、録画スクリプト。既存の `docs/brief/handoff.md` にある Firestore、Memory Bank、ADK、Veo の旧案は提出してはならない。今回のアーキテクチャは実際のルーティングと照合済みで、登場人物の音声とテキストの返答は Google Gemini が、語りなどの処理は Claude が提供する。
2. For the user to complete: the actual demo cut of about three minutes and a public YouTube link. After the user explicitly took over video recording and upload, the main thread stopped recording. The separate account had earlier recorded only one real text proposal and the 老爺 refusing it; do not describe that as him being sent home or an agreement being made. Fake-model footage must not be presented as actual AI replies, and do not claim that 200 games were verified.
   ユーザーが行う：約 3 分の実際のデモ完成版と公開 YouTube リンク。ユーザーが動画の録画とアップロードを明示的に引き取った後、メインスレッドは録画を止めた。以前、別アカウントで録れたのは実際のテキストでの提案と老爺の拒否の 1 回だけで、それを家まで送り届けたとか約束が成立したとか言ってはならない。偽モデルの画面を実際の AI の返答として扱ってはならず、200 局が検証済みとも主張しない。
3. Done: reviewer password, main invite code, two spare invite codes, a real opening state, and Japanese operating instructions. The recollection log shows only endings actually reached; no sample ending is faked at present.
   完了：レビュアー用パスワード、メインの招待コード、予備の招待コード 2 つ、実際の開幕状態、日本語の操作説明。回想録には実際に到達したエンディングだけを表示し、現時点で例示用のエンディングは偽造していない。
4. Done: the external entry. Without a Google identity, the password page, password refusal on 17 actual resource/API paths, invite-code login, actual progress and WebSocket startup all passed; historical temporary addresses were cleared, and the narrator service stays private.
   完了：外部の入口。Google アカウントなしの状態で、パスワードページ、実際のリソース/API の 17 パスでのパスワード拒否、招待コードでのログイン、実際の進捗、WebSocket の起動にすべて合格した。過去の一時アドレスは削除し、ナレーターサービスは非公開のまま。
5. Done: the default branch main is aligned with the delivered code. After submission, its state must be kept until December 1 as the contest requires; further development must use other branches and must not overwrite the judging baseline.
   完了：デフォルトブランチ main を納品コードに揃えた。提出後はコンテストの要件どおり 12 月 1 日まで状態を維持する必要がある。開発を続ける場合は別ブランチを使い、審査のベースラインを上書きしてはならない。

Judge calibration, pre-recorded voice listening, the 200 games and the four-act 980-call test remain on hold by the user's decision; they are not prerequisites for continuing development today.

審査員のキャリブレーション、事前収録音声の試聴、200 局、四幕 980 回のテストは、ユーザーの決定により引き続き保留。本日開発を続けるための前提条件ではない。

The public materials were scanned item by item for the existing URLs, passwords, main/spare invite codes and local identity paths; they contain no secrets. Whether registration, repository connection and the formal form submission are finally done still has to be checked in the contest dashboard; finished materials do not mean the submission has been made.

公開資料は、既存の URL、パスワード、メイン・予備の招待コード、ローカルの ID パスを 1 項目ずつスキャンし、秘密が含まれていないことを確認した。登録、リポジトリの接続、正式なフォームの提出が最終的に済んだかどうかは、引き続きコンテストの管理画面で確認する必要がある。資料が完成しても、提出済みということにはならない。
