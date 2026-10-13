# H-1: the protagonist's study and the multi-book entrance / H-1：主人公の書斎と複数の本の入口

## Experience conventions / 体験の約束事

- zoujin is the entrance into multiple books; 『走れメロス』 is just the one currently open. The catalog only shows books the server explicitly publishes; while there is no content for a second book, we do not fake titles, covers or playtest entrances.
  zoujin は複数の本に入るための入口で、『走れメロス』は現在公開している 1 冊にすぎない。カタログにはサーバーが明示的に公開した本だけを表示し、2 冊目のコンテンツがない間は、偽の書名、表紙、試遊の入口を作らない。
- The home belongs to the reader, not to the timeline of any one book. The study does not connect to the story WebSocket, does not request voice permission, does not advance the clock and does not create an experience.
  家は読者のものであり、どれか 1 冊の本の時間軸には属さない。書斎は物語の WebSocket に接続せず、音声の権限を求めず、時計を進めず、体験を作成しない。
- The space leads the home page. At the top, the brand and a short welcome; at the bottom, two equivalent entrances, 「本棚」 and 「回想録」. When an experience is in progress, 「しおりの続きから」 shows the real identity and time from the server.
  トップページは空間が主役。上部にブランドと短い歓迎の言葉、下部に同等の入口が 2 つ、「本棚」と「回想録」。進行中の体験があるときは、サーバー上の実際の身元と時刻を示す「しおりの続きから」を表示する。
- The art is carried by a separate original European-style study scene: tall windows, wooden bookcases, plaster walls, brass lamps, physical books and a memory book. It follows the existing art-direction's realistic lighting, shadow colors, restrained palette and phone budget, while its layout and geometry do not copy the in-book scenes.
  美術は独立したオリジナルのヨーロッパ風の書斎のシーンが担う：高窓、木の本棚、漆喰の壁、真鍮のランプ、実体のある本と回想録。既存の art-direction の写実的な光、暗部の色、抑えた配色、スマホの予算に倣い、レイアウトとジオメトリは本の中のシーンを流用しない。

## Operation paths / 操作の流れ

1. Site password → existing invite-code account → study; the study's 3D chunk is not loaded until account authentication passes.
   サイトのパスワード → 既存の招待コードのアカウント → 書斎。アカウント認証を通過するまで書斎の 3D chunk は読み込まない。
2. 本棚 → the corresponding `/books/:bookId` cover → the `/books/:bookId/roles` identity → a game is created only after the user clicks.
   本棚 → 対応する `/books/:bookId` の表紙 → `/books/:bookId/roles` の身元 → ユーザーがクリックして初めて局を作成する。
3. Experience in progress → story menu 「書斎に戻る」 → the study's 「しおりの続きから」 returns to the same `playthroughId`. Going back only tears down the connection and sends no create or delete request.
   進行中の体験 → 物語のメニューの「書斎に戻る」 → 書斎の「しおりの続きから」で同じ `playthroughId` に戻る。戻るときは接続を解除するだけで、作成や削除のリクエストは送らない。
4. 回想録 → real endings stored in the database → the original full ending page (world, self, characters, ending card and causality graph) → study.
   回想録 → データベースに保存された実際のエンディング → 元の完全なエンディングのページ（世界、自分、登場人物、エンディングカード、因果関係図）→ 書斎。
5. A record that has ended but whose epilogue is not yet stored is shown separately as 「物語を綴じています」; opening it reuses the existing idempotent generation task; it must not be shown as an already completed ending.
   終了しているがエピローグがまだ保存されていない記録は「物語を綴じています」として別に表示し、開くと既存の冪等な生成タスクを再利用する。完了済みのエンディングとして表示してはならない。
6. Each account still has only one experience in progress; a conflict when starting a new one keeps using the explicit two-step delete confirmation, and games are not deleted automatically because of switching books or going home.
   1 アカウントの進行中の体験は引き続き 1 つだけ。新たに始める際の衝突には、引き続き明示的な 2 段階の削除確認を使い、本を替えたり家に帰ったりしたことで局を自動削除しない。

## Phone and accessibility / スマホとアクセシビリティ

- Clicking objects in the home is equivalent to the DOM buttons; users limited in vision, keyboard or WebGL can complete all book selection, continuing and recollection operations.
  家の中のオブジェクトのクリックは DOM ボタンと同等。視覚、キーボード、WebGL に制約のあるユーザーも、本の選択、続き、回想の操作をすべて完了できる。
- The catalog and recollections use native `<dialog>`; when opened, focus moves into the panel, the background cannot be operated, Escape closes it and restores focus; when switching from an empty memory book to the bookshelf, focus moves to the new panel's close button.
  カタログと回想にはネイティブの `<dialog>` を使う。開くとフォーカスはパネルに入り、背景は操作できず、Escape で閉じてフォーカスを戻す。空の回想録から本棚に切り替えたときは、新しいパネルの閉じるボタンにフォーカスを移す。
- On phones it is a bottom panel, at most 78dvh; on wide screens it is a 430px panel on the right, leaving the room visible. Minimum button height is 44px, with the safe area and landscape taken into account.
  スマホでは下部のパネルで、最大 78dvh。ワイド画面では右側の 430px のパネルで、部屋が見えるように残す。ボタンの最小の高さは 44px で、safe area と横向きを考慮する。
- reduced-motion stops UI animations; 3D handles the reduced-motion preference and page hiding on its own.
  reduced-motion では UI のアニメーションを止める。3D は動きを減らす設定とページの非表示を独立して処理する。
- Network failures are clearly distinguished from empty records, with a retry offered; unopened books have the enter button disabled, and an unknown book URL gives a way back.
  ネットワークの失敗と空の記録を明確に区別し、再試行を用意する。未公開の本は入るボタンを無効にし、不明な本の URL には戻る道筋を示す。

## Data and privacy / データとプライバシー

- The bookshelf uses only `/v1/books`; progress and endings use only `/v1/library`. The client is not given all preset endings, and localStorage is not used to guess completion.
  本棚は `/v1/books` だけを使い、進捗とエンディングは `/v1/library` だけを使う。クライアントにすべての既定のエンディングを渡さず、localStorage で完了状況を推測しない。
- The manifest is located from the save's `bookId` + `worldModelVersion`, and the identity comes from the server record; if an old version's resources are unavailable, it fails explicitly rather than silently switching to the new version. The old `/roles` link serves only as a Melos compatibility entrance.
  manifest はセーブの `bookId` + `worldModelVersion` から特定し、身元はサーバーの記録から取る。旧バージョンのリソースが使えないときは明示的に失敗し、黙って新バージョンに切り替えない。旧 `/roles` リンクはメロス用の互換の入口としてだけ使う。
- When the account switches or becomes invalid, React Query, in-memory story state, the ending screen, handoff snapshots and the old telemetry queue (including late retries) are cleared, so content from the previous invite code does not linger.
  アカウントの切り替え時や無効化時には、React Query、メモリ上の物語の状態、エンディングの画面、引き継ぎのスナップショット、古いテレメトリーのキュー（遅れて届くリトライを含む）を消去し、前の招待コードの内容が残らないようにする。
- An expired site password's `X-Site-Access: required` makes the whole page jump straight to the server's password page instead of getting stuck in an invite-code retry loop. When WS is refused before accept, the browser usually reports 1006; an abnormal disconnect triggers a single-concurrency `/v1/me` probe rate-limited to once per 30 seconds, so that the same REST gate recovery path takes effect.
  サイトのパスワードが失効したときの `X-Site-Access: required` では、ページ全体をそのままサーバーのパスワードページに移動させ、招待コードのリトライのループに陥らないようにする。WS が accept の前に拒否されると、ブラウザは通常 1006 を報告する。異常な切断では、同時実行 1 つ・30 秒に 1 回に制限した `/v1/me` の探査を発動し、同じ REST のゲートからの復帰経路が働くようにする。
- The offline SW is disabled; old `zoujin-*` caches and old workers are cleaned up. The unregistering worker does not intercept requests. The server must still cover HTML, JS, GLB, sound, API and WS and return private/no-store.
  オフラインの SW は停止し、古い `zoujin-*` キャッシュと古い worker を片付ける。登録解除用の worker はリクエストを横取りしない。サーバーは引き続き HTML、JS、GLB、音声、API、WS を覆い、private/no-store を返す必要がある。
- Local development listens only on 127.0.0.1; there is no deployment, public link or third-party asset upload.
  ローカル開発は 127.0.0.1 だけをリッスンする。デプロイ、公開リンク、サードパーティのアセットのアップロードはない。

## Verification record / 検証記録

- TypeScript type check passed.
  TypeScript の型チェックに合格した。
- Frontend unit tests: 317 passed; after adding the real local scene assets, the 17 scene checks that were previously skipped also ran.
  フロントエンドの単体テスト：317 件合格。実際のシーンのアセットをローカルに追加した後、以前スキップしていた 17 件のシーンのチェックも実行した。
- Build passed; first-screen JS 107.6 KB brotli (budget 120), world chunk 235.6 KB (budget 250). The study is a separate chunk and is not statically merged into the first screen.
  ビルドに合格。最初の画面の JS は 107.6 KB brotli（予算 120）、世界の chunk は 235.6 KB（予算 250）。書斎は独立した chunk で、最初の画面に静的に組み込んでいない。
- Chrome browser flows: 12/12 passed (empty bookshelf state, unopened book, real history/generating state, going home and continuing the same game with zero creates/deletes, invite code and 401 recovery, the existing two-step conflict confirmation, recovery from disconnect events, cleanup of the old offline cache). At first Playwright's bundled Chromium was missing, so the run was then completed with a temporary test profile of the local Chrome.
  Chrome ブラウザでのフロー：12/12 合格（本棚の空の状態、未公開の本、実際の履歴/生成中の状態、家に帰って同じ局を続けて作成/削除がゼロ、招待コードと 401 からの復帰、既存の衝突時の 2 段階確認、切断イベントからの復帰、古いオフラインキャッシュの片付け）。当初は Playwright 同梱の Chromium がなかったので、ローカルの Chrome の一時的なテスト用 profile で完了させた。
- Bare scene / integrated study / bookshelf / memory book were each screenshotted and reviewed on a 390×844 phone and a 1440×960 desktop, 8 images in total, stored outside the repo in `~/.zoujin/qa/h1-home/review-*.png`. The canvas fills the screen with no DPR black borders, and the pages have no JS exceptions; the images use the projection from the local test directory and are not uploaded.
  390×844 のスマホと 1440×960 のデスクトップで、素のシーン/統合した書斎/本棚/回想録をそれぞれスクリーンショットで確認した。計 8 枚で、リポジトリの外の `~/.zoujin/qa/h1-home/review-*.png` に保存している。キャンバスは画面を満たし、DPR による黒い縁はなく、ページに JS の例外もない。画像はローカルのテストディレクトリの投影を使い、アップロードしない。
- The first independent art review raised insufficient window light/contact shadows and wood grain that repeats in a procedural-looking way; the next three rounds of adjustments and results are below. These screenshots do not stand for the final art/performance acceptance check on a real phone. The problem of the phone welcome subtitle sitting on the bright eave line was solved by hiding the subtitle, keeping the main title.
  1 回目の独立した美術レビューで、窓の光と接触影の不足、木目の繰り返しがプロシージャル的に見えるという問題が挙がった。その後 3 回の調整と結果は下記のとおり。これらのスクリーンショットは、実機のスマホでの最終的な美術/性能の受け入れ確認を表すものではない。スマホで歓迎のサブタイトルが明るい軒のラインに重なる問題は、サブタイトルを隠して解決し、メインタイトルは残した。
- Cross-review: the backend history SQL first restricts by owner and active/ended state and then joins; records still being generated do not pass for completed ones; GET ending only wakes the existing queue task. The risk of the history manifest using the latest version was found, and both backend and frontend now read by the actual save version.
  クロスレビュー：バックエンドの履歴の SQL は先に owner と active/ended の状態で絞り込んでから join する。生成中の記録が完了を装うことはない。GET ending は既存のキューのタスクを起こすだけ。履歴の manifest が最新バージョンを使うリスクが見つかり、バックエンドとフロントエンドの両方で実際のセーブのバージョンで読むように変えた。
- The in-book scene build has been copied into this working tree for local integration; passing the resource checks does not mean visual acceptance of the whole book. Real-phone frame rate and real voice are not claimed as done in this card.
  本の中のシーンの build はローカルでの統合のためにこの作業ツリーにコピーした。リソースのチェックに合格しても、本全体の見た目の受け入れ確認にはならない。実機のスマホのフレームレートと実際の音声は、このカードでは完了と主張しない。

## Second cross-review round / 2 回目のクロスレビュー

- After adding fine bevels on the furniture and contact shadows, `review2-{phone,desktop}-{integrated,books}.png` were re-captured. Phone DPR=2 with an internal render ratio of 1.5: a 585×1266 canvas covering CSS 390×844; desktop 1440×960. All fill the screen with no JS exceptions.
  家具の細かい面取りと接触影を追加した後、`review2-{phone,desktop}-{integrated,books}.png` を撮り直した。スマホは DPR=2、内部のレンダリング比 1.5：585×1266 のキャンバスが CSS の 390×844 を覆う。デスクトップは 1440×960。いずれも画面を満たし、JS の例外はない。
- The dedicated dependencies for AO and RoomEnvironment/RoundedBox stay in the study's lazy chunk; in round two the world main chunk is 234.5 KB brotli, so the new home's art dependencies are not passed on to the in-book scenes.
  AO と RoomEnvironment/RoundedBox の専用の依存は書斎の lazy chunk に留めた。2 回目の世界のメインの chunk は 234.5 KB brotli で、新しい家の美術の依存を本の中のシーンに押し付けていない。
- In the round-two images the bookcases still lacked side light, so the scene owner was given concrete light-placement suggestions (light traveling toward the back wall, so the main view does not rely on ambient light alone for long). Art adjustments continue to be accepted by the scene owner.
  2 回目の画像では本棚にまだ横からの光が足りなかったので、シーンの担当者に具体的なライトの位置を提案した（光を奥の壁へ向かわせ、メインの見た目が長く環境光だけに頼らないようにする）。美術の調整は引き続きシーンの担当者が受け入れ確認する。

## Third round and final code review / 3 回目と最終的なコードレビュー

- `review3-{phone,desktop}-integrated.png`: after the window-light adjustment, the bookcases, walls and chair show clear side light and cast shadows, and the wood-grain contrast is lower; the integrated page fills the screen, buttons are readable, and there are no new blockers. The view outside the window and the regularity of the book spines can still be refined later; this round's scope is not expanded.
  `review3-{phone,desktop}-integrated.png`：窓の光を調整した後、本棚、壁、椅子に明確な横からの光と影が出て、木目のコントラストは下がった。統合したページは画面を満たし、ボタンは読め、新たな阻害要因はない。窓の外と本の背の規則的な感じは今後さらに磨けるが、今回の範囲は広げない。
- After batching vertices with color preserved, the first complete frame on local Chrome on a 390×844 phone (internal 585×1266) is 94 draw calls / 235,382 triangles, and on a 1440×960 desktop 96 / 235,510, including shadows, AO and post-processing. The phone main scene drawn alone is 20 / 62,776; observing at rest for 0.5–1 seconds shows no extra GPU draws. This fits the existing per-frame budget of 120 draw calls and 300k visible triangles; it does not replace real-device frame times.
  色を保持したまま頂点をバッチ化した後、ローカルの Chrome で 390×844 のスマホ（内部 585×1266）の最初の完全なフレームは 94 draw calls / 235,382 triangles、1440×960 のデスクトップでは 96 / 235,510 で、影、AO、ポストプロセスを含む。スマホのメインシーンを単独で描画すると 20 / 62,776。静止状態を 0.5–1 秒観測しても追加の GPU の描画はない。既存のフレームあたり 120 draw calls と可視三角形 300k の予算に収まる。実機のフレーム時間の代わりにはならない。
- Release of geometry/textures/materials/post-processing on study resize, the reduced-motion preference and normal unmount has been reviewed independently; initialization errors go through the same reverse-order cleanup, the two materials that GTAOPass missed were added, and unmount actively releases the WebGL context. Character crowd representatives now avoid the real crowd starting positions, the player approaching does not make them move away automatically at the next state update, and they are hidden during ending set pieces to avoid drawing the same character twice.
  書斎のサイズ変更、動きを減らす設定、通常のアンマウントでのジオメトリ/テクスチャ/マテリアル/ポストプロセスの解放は独立してレビューした。初期化の例外は同じ逆順の後始末を通り、GTAOPass が漏らしていた 2 つのマテリアルを補い、アンマウント時には WebGL の context を能動的に解放する。登場人物の群衆の代表は実際の crowd の初期位置を避け、プレイヤーが近づいても次の状態更新で自動的に移動することはなく、エンディングの演出中は隠して同じ登場人物を二重に描かないようにした。
- The default page title was changed to `zoujin`. Clearing the account cache, the old SW and CacheStorage only affects the browser; it does not call the create/delete game endpoints, and does not delete server progress or endings.
  デフォルトのページタイトルを `zoujin` に変えた。アカウントのキャッシュ、古い SW、CacheStorage の片付けはブラウザにしか影響せず、局の作成/削除のインターフェースは呼ばず、サーバーの進捗とエンディングも削除しない。
- The final `final-{phone,desktop}-integrated.png` come from the real gateway + production build at 127.0.0.1:8091, going through the site password and invite code and reading real progress from the local database, with no endpoint injection. Neither has a pageerror, the title is correct, and keyboard focus across panels is correct; after deliberately triggering context loss, the DOM bookshelf can still be opened. When known to be offline, no authentication probe is sent; a handshake failure after the network recovers rechecks the gate.
  最終的な `final-{phone,desktop}-integrated.png` は 127.0.0.1:8091 の実際の gateway + production build から取ったもので、サイトのパスワードと招待コードを通り、ローカルのデータベースの実際の進捗を読み、インターフェースの注入はしていない。どちらも pageerror はなく、タイトルは正しく、パネルをまたぐキーボードのフォーカスも正しい。context loss を意図的に発生させた後も DOM の本棚は開ける。オフラインがわかっているときは認証の探査を送らず、ネットワークが復旧した後のハンドシェイクの失敗ではゲートを再確認する。
