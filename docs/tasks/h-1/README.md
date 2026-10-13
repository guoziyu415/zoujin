# H-1: The reader's home, the multi-book platform and private access / H-1：読者の家、マルチブックプラットフォーム、非公開アクセス

## User requirements / ユーザー要件

Keep the quality of the existing models, characters and scenes. Currently only one book is playable, but the product supports multiple books. From an original European-style study, the reader picks a book, continues real progress, and looks back at endings they experienced themselves. The content must not be public, and the pages must have a password. Development and cross-review run in parallel.

既存のモデル、人物、シーンの品質を保つ。現在遊べる本は 1 冊だけだが、プロダクトは複数の本に対応する。読者はオリジナルのヨーロッパ風書斎から本を選び、実際の進行を続け、自分で体験したエンディングを振り返る。コンテンツは公開してはならず、ページにはパスワードが必要。開発と相互レビューは並行して進める。

## Division of work / 実装の分担

1. Backend / data: an explicit publication catalog, restoring saves by book and world version, per-account real-ending projection, and an outermost site password.
   バックエンド / データ：明示的な公開カタログ、本と世界バージョンごとのセーブ復元、アカウントごとに分離した実エンディングの射影、最外層のサイト・パスワード。
2. Frontend / UX: the study entrance, bookshelf and memory book, returning home and continuing the same playthrough, error recovery, keyboard and phone layout.
   フロントエンド / UX：書斎の入口、本棚と回想録、帰宅と同じプレイの再開、エラーからの復帰、キーボードと手機のレイアウト。
3. Characters: fill in missing characters and representative crowd models, check the old models' default expressions, costumes and motions, and wire them into the scenes.
   人物：欠けている人物と群衆の代表モデルを補い、旧モデルの表情の初期値、衣装、動作を点検してシーンに接続する。
4. Scene / integration: modeling the original study, materials, lighting, the phone draw budget, plus real browser flows and independent review.
   シーン / 統合：オリジナル書斎のモデリング、マテリアル、照明、手機の描画予算、そして実際のブラウザフローと独立した確認。

Each area reviews the others' interfaces, permissions, character placement and visual results directly. See the [backend record](backend.md), [UX record](ux.md) and [characters record](characters.md) for details.

各分野は、互いのインターフェース、権限、人物の立ち位置、見た目の結果を直接レビューする。詳細は [バックエンド記録](backend.md)、[UX 記録](ux.md)、[人物記録](characters.md) を参照。

## Design of the home / 家の設計

The home belongs to the reader and is independent of the in-book era and the story clock. The room has European plaster walls, dark green wainscoting, arched tall windows, a wooden floor, bookcases, a desk, a reading chair, a fireplace and a physical memory book; the geometry, surface textures and wall paintings are all original procedural assets made for this task. Only the quality standard of existing scenes is referenced; their layout is not reused.

家は読者のものであり、本の中の時代や物語の時計とは独立している。部屋はヨーロッパ風の漆喰の壁、深緑の腰壁、アーチ型の高窓、木の床、本棚、机、読書用の椅子、暖炉、実体のある回想録でできている。形状、表面テクスチャ、壁の絵はすべて今回オリジナルにプロシージャルで作ったアセットである。既存シーンの品質基準だけを参考にし、そのレイアウトは流用しない。

Window light and furniture shadows come from real light sources, and contact shadows use half-resolution AO. The color difference between book spines and the floor is kept as vertex data, and each shares a material to be batched. The study is lazy-loaded separately; after it comes to rest, GPU frames are not redrawn repeatedly, and drawing resumes only when the camera moves, which reduces cutting the camera directly under the reduced-motion preference.

窓の光と家具の影は実際の光源で生成し、接触影には半解像度の AO を使う。本の背とフロアの色の違いは頂点データとして保持し、それぞれマテリアルを共有してバッチ化する。書斎は独立して遅延読み込みされる。静止した後は GPU フレームを繰り返し描画せず、カメラが動いたときだけ描画を再開する。動きを減らす設定のとき、カメラを直接切り替える場面を減らす。

The bookshelf and memory book can both be operated from objects in the space or from equivalent DOM buttons; even if WebGL is unavailable, you can choose a book, resume progress and read endings. The study itself does not open a story connection, does not ask for microphone permission, does not advance the story and does not create a save.

本棚と回想録は、空間内のオブジェクトからも同等の DOM ボタンからも操作できる。WebGL が使えなくても、本の選択、進行の再開、エンディングの閲覧ができる。書斎自体は物語の接続を作らず、マイクの権限を求めず、物語を進めず、セーブも作らない。

## Local check entry point / ローカル確認の入口

```sh
pnpm --filter @zoujin/web build
uv run python infra/deploy/local-preview.py
```

The script starts a password-protected real gateway and a fake-model narrative service, listening only on `127.0.0.1`. It uses a separate local database; the password and local invitation code are written to `~/.zoujin/local-previews/h-1/credentials.json` (0600) and never enter source code, logs or URLs. No fictional user endings are seeded. After stopping, real local playthrough progress is kept.

スクリプトは、パスワードで保護された本物のゲートウェイと偽モデルの物語サービスを起動し、`127.0.0.1` のみで待ち受ける。独立したローカルデータベースを使う。パスワードとローカル招待コードは `~/.zoujin/local-previews/h-1/credentials.json`（0600）に書かれ、ソースコード、ログ、URL には入らない。架空のユーザーのエンディングは投入しない。停止後も、実際のローカルプレイの進行は残る。

## Confidentiality and release boundary / 機密保持と公開の境界

- The site password covers HTML, scripts, scenes, characters, audio, REST and WebSocket; the account invitation code still governs inner save permissions.
  サイト・パスワードは HTML、スクリプト、シーン、人物、音声、REST、WebSocket を覆う。アカウントの招待コードは引き続き内側のセーブ権限を担う。
- In production, access is closed when the password is missing; when the password is invalid, the gate is returned; old offline caches and the Service Worker are retired.
  本番ではパスワードがない場合にアクセスを閉じる。パスワードが無効な場合はゲートを返す。古いオフラインキャッシュと Service Worker は廃止する。
- At the user's request, anonymous invocation permission on the old live gateway was revoked; a re-check shows anonymous pages, the catalog and the character manifest all return 403. This new version was not deployed, and anonymous IAM permission was not reopened.
  ユーザーの要望により、旧オンラインゲートウェイの匿名呼び出し権限を取り消した。再確認で、匿名のページ、カタログ、人物一覧がいずれも 403 を返すことを確認した。今回の新バージョンはデプロイしておらず、匿名 IAM 権限も再度開放していない。
- The deployment script no longer makes the service public automatically; each deployment still requires the user's separate authorization per repository convention.
  デプロイスクリプトはサービスを自動的に公開しなくなった。各デプロイは引き続きリポジトリの規約に従い、ユーザーから個別に許可を得る。
- Screenshots, Blender intermediate files, model outputs and test credentials stay local; no external assets are uploaded and no public previews are made.
  スクリーンショット、Blender の中間ファイル、モデルの生成物、テスト用の認証情報はローカルに残す。外部アセットのアップロードも公開プレビューも行わない。

## Acceptance boundary / 検収の境界

Browser screenshots, automated flows, resource checks and build results are recorded separately; none can replace iPhone 12 real-device frame rates, the actual voice model experience, or the user's final art acceptance. Currently only 『走れメロス』, which has been truly completed, is open; no second book or unexperienced endings are invented.

ブラウザのスクリーンショット、自動化フロー、リソース確認、ビルド結果はそれぞれ別に記録し、iPhone 12 実機のフレームレート、実際の音声モデルでの体験、ユーザーによる最終的なアート検収の代わりにはならない。現在公開しているのは、実際に制作を終えた『走れメロス』だけで、2 冊目の本や未体験のエンディングを捏造しない。

## Integration verification record / 統合検証の記録

- Real local gateway + PostgreSQL: password → invitation code → study → empty memory book → bookshelf → characters → act 1 → back to the study → continue, restoring the original `playthroughId`. Character and scene resources load from the official static routes, and a missing local scene pack configuration that was found was fixed; the preview uses a fake model and does not pose as a real-model evaluation.
  本物のローカルゲートウェイ + PostgreSQL：パスワード → 招待コード → 書斎 → 空の回想録 → 本棚 → 人物 → 第一幕 → 書斎に戻る → 続きから、で元の `playthroughId` が復元される。人物とシーンのリソースは正式な静的ルートから読み込まれ、見つかったローカルのシーンパック設定の漏れは修正した。プレビューは偽モデルを使っており、本物のモデルでの評価を装うものではない。
- After the final character update, the protected gateway was restarted and the original playthrough was again continued from the study, the actual square and traveler model were loaded and the study was returned to, with no new browser errors. Anonymous requests for pages, character models and APIs are rejected by the gate; after the password, models are readable and no-store, and the account API still requires an invitation code.
  最終的な人物の更新後に保護されたゲートウェイを再起動し、再び書斎から元のプレイを続け、実際の広場と旅人のモデルを読み込み、書斎に戻った。ブラウザに新たなエラーはなかった。匿名のリクエストによるページ、人物モデル、API はゲートに拒否される。パスワードを通過するとモデルは読め、no-store になっており、アカウント API には引き続き招待コードが必要。
- Desktop and phone images were independently reviewed: slanted window-pane shadows, furniture contact shadows, wood grain, canvas size and button visibility passed. The final integration screenshots are in the local QA directory and do not enter the repository.
  デスクトップと手機の画面を独立して確認した。窓枠の斜めの影、家具の接触影、木目、キャンバスのサイズ、ボタンの見え方は合格。最終的な統合スクリーンショットはローカルの QA ディレクトリにあり、リポジトリには入れない。
- Chrome full frame (with shadows, AO, post-processing): phone 94 calls / 235382 triangles, desktop 96 / 235510; the main scene alone 20 calls / 62776 triangles. Within 500–1000ms after coming to rest, no extra GL draws were measured. This meets the existing per-frame budget of 120 calls / 300k triangles and does not represent the actual frame rate of a baseline phone.
  Chrome のフルフレーム（影、AO、ポストプロセス込み）：手機 94 calls / 235382 triangles、デスクトップ 96 / 235510。メインシーン単独では 20 calls / 62776 triangles。静止後の 500〜1000ms の間に、余分な GL 描画は計測されなかった。既存のフレームあたり 120 calls / 300k triangles の予算を満たすが、最低ラインの手機での実際のフレームレートを示すものではない。
- The room textures total 5, and geometry attributes are about 6.36 MiB; the study and the in-book world are split into chunks. Closing the room explicitly releases the GL context, and DOM operation still works if initialization fails or the context is lost.
  部屋のテクスチャは計 5 枚、ジオメトリ attribute は約 6.36 MiB。書斎と本の中の世界はチャンクを分けている。部屋を閉じると GL コンテキストを明示的に解放し、初期化に失敗した場合やコンテキストが失われた場合でも DOM 操作は使える。
- `check_world.sh`: 24 playthroughs each for the full version / slice, and the evaluation outputs consistent, with 0 errors and 0 warnings.
  `check_world.sh`：完全版 / スライスそれぞれ 24 回の推演と評価生成物が一致し、エラー 0、警告 0。
- Backend final full regression: 635 passed; the deployment privacy control flow: another 15 passed; frontend 317 unit tests and 12 browser flows passed; contracts 507 passed, 6 skipped under existing conditions. Whole-repo mypy passed on 193 files.
  バックエンドの最終的な完全回帰テスト 635 件が成功。デプロイのプライバシー制御フローは別に 15 件が成功。フロントエンドの単体テスト 317 件とブラウザフロー 12 件が成功。契約テスト 507 件が成功、6 件は既存の条件でスキップ。リポジトリ全体の mypy は 193 ファイルが成功。
- The final production build passed: home page JS 107.6 KB brotli / 120 KB, 3D main chunk 235.4 KB / 250 KB. 17 character sets, 68 GLBs and 119 final screenshots; actual file hashes, triangle counts and dist all match; the packaging preflight for all scenes and characters passed. See the characters record for details.
  最終的な本番ビルドは成功。トップページの JS は 107.6 KB brotli / 120 KB、3D メインチャンクは 235.4 KB / 250 KB。人物 17 セット、GLB 68 個、最終スクリーンショット 119 枚で、実際のファイルハッシュ、三角形数、dist はすべて一致する。全シーンと人物のデプロイ用パッケージの事前確認も成功。詳細は人物記録を参照。
- The whole-repo Node check found two pre-existing issues from before this work: unused variables in two village scripts and old asset formatting. The whole-repo Ruff also reports 65 pre-existing style warnings in evals/acts and worldsim tests. The Blender pipeline is not included in whole-repo Ruff under the existing configuration, and checking it explicitly would also report old style issues. Existing pipeline input hashes were not changed just to clear unrelated warnings, so this delivery cannot be called whole-repo CI green. The changed frontend files individually passed lint / format / typecheck, and 154 backend files passed Ruff checks and format verification.
  リポジトリ全体の Node チェックで、今回より前からある二つの問題が見つかった：二つの村スクリプトの unused-variable と、古いアセットの整形。リポジトリ全体の Ruff でも、evals/acts と worldsim テストに既存のスタイル警告が 65 件ある。Blender パイプラインは既存の設定ではリポジトリ全体の Ruff の対象外で、明示的に検査すると古いスタイルの問題が報告される。無関係な警告を片付けるためだけに既存のパイプライン入力ハッシュは変更しておらず、この納品を「リポジトリ全体の CI がすべて成功」とは言えない。変更したフロントエンドのファイルは単体で lint / format / typecheck に成功し、バックエンド 154 ファイルは Ruff の検査とフォーマット検証に成功した。
