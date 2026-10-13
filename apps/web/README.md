# apps/web

Web frontend (React + three.js, mobile browser first). Owned by Frontend. For the design see `docs/frontend/frontend-design.md`; for task cards see `docs/tasks/m2-0/F-0.md` and `F-2.md`.

ウェブフロントエンド（React + three.js、モバイルブラウザ優先）。フロントエンド担当。設計は `docs/frontend/frontend-design.md`、タスクカードは `docs/tasks/m2-0/F-0.md`、`F-2.md` を参照。

There are two parts at present:

現在は 2 つの部分がある。

- **Shell (F-0) and voice (F-1)**: invite code → cover → pick a role → the world screen HUD (subtitles, clock bar, 近くの人, text input, talk button, light feedback, disconnect banner, 「タップして続ける」 on return), running a full round of conversation against the B-1 mock. Styling is placeholder; finalizing visuals and copy is UX's card.
  **シェル (F-0) と音声 (F-1)**：招待コード → カバー → 身分選択 → 世界画面の HUD（字幕、時計バー、近くの人、テキスト入力、話すボタン、軽いフィードバック、切断バナー、戻ってきたときの「タップして続ける」）。B-1 のモックを相手に会話を 1 ラウンド最後まで通す。スタイルは仮のもので、ビジュアルと文言の確定は UX のカード。
- **3D plaza (F-2b, F-2c, F-2d)**: beneath the world screen is the realistic Syracuse plaza (the first screen is the S7 southwest-corner composition), reading the same store as the HUD: tap the ground to walk there, tap a person to walk up to them and start a conversation, drag to rotate the camera; the sun and shadows follow the world clock; characters stand at the location points the server names and walk over when the location point changes. Moving between places sends `move`; approaching a character sends `near` and moving away sends `far`; moving away from the character currently speaking ends the conversation.
  **3D 広場 (F-2b、F-2c、F-2d)**：世界画面の下にはリアルなシラクサの広場がある（最初の画面は S7 の南西の角の構図）。HUD と同じ store を読む。地面をタップしてそこへ歩く、人をタップしてその人のそばまで歩いて会話を始める、ドラッグでカメラを回す。太陽と影は世界の時計に合わせて動き、人物はサーバーが指定した位置点に立ち、位置点が変わると歩いて移動する。地点をまたぐと `move`、人物に近づくと `near`、遠ざかると `far` を送り、話している相手から離れると会話が終わる。

## Running it / 起動方法

Generated scene output is not in the repo; generate the plaza once first (`assets/pipeline/plaza/README.md`), which by default writes to `assets/scenes/syracuse-square/build/`:

シーンの生成物はリポジトリに入れない。まず広場を一度生成する（`assets/pipeline/plaza/README.md`）。既定では `assets/scenes/syracuse-square/build/` に書き出される。

```sh
pnpm assets:plaza draft            # draft-quality lightmaps, a few minutes; the full quality takes no argument, about half an hour / ドラフト品質のライトマップ、数分。本番品質は引数なしで約 30 分
pnpm --filter @zoujin/web dev      # http://127.0.0.1:5173/
```

If the scene is in another directory, set `ZOUJIN_SCENE_ROOT=<directory>` (reads `<directory>/syracuse-square/`).

シーンが別のディレクトリにある場合は `ZOUJIN_SCENE_ROOT=<ディレクトリ>` を設定する（`<ディレクトリ>/syracuse-square/` を読む）。

The shell needs the API: the dev server and `vite preview` proxy `/v1` (including WebSocket), `/__mock`, and `/assets/voice` to `ZOUJIN_API` (default `http://127.0.0.1:8787`, the B-1 mock). Start the mock at the repo root; the invite code is `mock`:

シェルには API が必要：開発サーバーと `vite preview` は `/v1`（WebSocket を含む）、`/__mock`、`/assets/voice` を `ZOUJIN_API`（既定は `http://127.0.0.1:8787`、B-1 のモック）に転送する。リポジトリのルートでモックを起動する。招待コードは `mock`：

```sh
uv run --all-packages zoujin-mock --scenario full-turn   # one full round of conversation; scripts are in fixtures/sessions/ / 会話 1 ラウンド分。台本は fixtures/sessions/ にある
```

With no parameters it is the shell (routes: `/login`, `/`, `/roles`, `/play/<session>`, `/ending/<session>`).

パラメータなしだとシェル（ルート：`/login`、`/`、`/roles`、`/play/<局>`、`/ending/<局>`）。

- `?world`: the 3D plaza only, no API; the world is a local copy (`src/three/dev/sandbox.ts`).
  `?world`：3D 広場のみで API なし。世界はローカルのもの（`src/three/dev/sandbox.ts`）。
- `?dev`: same as above plus a panel: drag the clock, play through a sunset (18:00 → 19:10), toggle the stonemason's workshop, see frame time and draw calls. For the team, not for players.
  `?dev`：上と同じで、さらにパネルが付く：時計をドラッグ、日没を一通り再生（18:00 → 19:10）、石工の作業場の開閉、フレーム時間と draw call の表示。チーム用で、プレイヤー向けではない。
- `?test`: attaches `window.__zoujin` (`src/three/dev/testHook.ts`), which Playwright uses to set the clock, place fixed camera positions, make the player walk somewhere, and find where the ground or a person can be clicked. Quality is pinned at L1 so every frame looks the same; `?test&quality=auto` runs the starting-tier self-test and tier changes like a real player. Used together with `?world` it is the plaza only; used alone it enters the shell and attaches when the world screen is reached (Playwright can also set `window.__zoujinTest = true` before page scripts). For checks that test only the HUD, set `window.__zoujinNo3d = true` so the world screen does not load 3D.
  `?test`：`window.__zoujin`（`src/three/dev/testHook.ts`）を取り付ける。Playwright が時計の設定、固定カメラ位置の配置、プレイヤーの移動、地面や人物をクリックできる場所の検索に使う。画質は L1 に固定され、毎回同じ画になる。`?test&quality=auto` はプレイヤーと同じように開始ティアの自己測定とティアの昇降を行う。`?world` と併用すると広場のみ。単独で使うとシェルに入り、世界画面に着いたときに取り付けられる（Playwright はページのスクリプトより前に `window.__zoujinTest = true` を設定してもよい）。HUD だけを検査する場合は `window.__zoujinNo3d = true` を設定すると、世界画面は 3D を読み込まない。
- `?quality=L0` to `L3`: pins one quality level, with no self-test and no tier changes.
  `?quality=L0`〜`L3`：画質を 1 段階に固定し、自己測定も昇降もしない。
- `?crowd=20`: puts 20 crowd members at the execution ground (F-4, `src/three/crowd/`), used together with `?world`. Until the ending presentation is wired in, only this switch loads the crowd chunk.
  `?crowd=20`：刑場に群衆 20 人を立たせる（F-4、`src/three/crowd/`）。`?world` と併用する。エンディング演出がつながるまでは、このスイッチだけが群衆のチャンクを読み込む。
- `?measure`: the measurement page (see "Quality" below).
  `?measure`：計測ページ（下の「画質」を参照）。

Controls: tap the ground to walk, tap a person to walk up to them (a person who can talk also starts a conversation); drag horizontally to rotate the camera; on desktop, WASD / arrow keys to walk, hold Shift to run.

操作：地面をタップして歩く、人をタップしてその人のそばまで歩く（話せる人とは同時に会話が始まる）。横方向のドラッグでカメラを回す。デスクトップでは WASD / 矢印キーで歩き、Shift を押しながらで走る。

## Quality (F-2c, frontend-design 10.6.3) / 画質（F-2c、frontend-design 10.6.3）

Four levels: L0 fallback (resolution 1.25, bloom and MSAA off, shadows 1024), L1 standard (1.5, everything on, shadows 2048), L2 high (2, soft shadows, 2048 maps in the background), L3 highest (device native, up to 3). Color grading and vignette are done in the same pass at every level, so colors do not change when the level changes.

4 段階：L0 フォールバック（解像度 1.25、ブルームと MSAA オフ、シャドウ 1024）、L1 標準（1.5、すべてオン、シャドウ 2048）、L2 高（2、ソフトシャドウ、バックグラウンドで 2048 マップ）、L3 最高（デバイスネイティブ、最大 3）。カラーグレーディングとビネットはどの段階でも同じパスで行うので、段階を変えても色は変わらない。

- Starting tier: on entry, a fixed test scene (PBR, sky, fog, 2048 shadows, bloom, MSAA) is drawn off-screen, and one frame's GPU time is measured using S7's stress method and extrapolated by pixel ratio to each level; the highest level with "L1 ≤ 25 ms, L2 / L3 ≤ 12 ms" is chosen; if it cannot be measured, start at L1 (`src/three/quality/probe.ts`, `levels.ts`).
  開始ティア：入場時に固定のテストシーン（PBR、空、霧、2048 シャドウ、ブルーム、MSAA）を画面外に描き、S7 の負荷方式で 1 フレームの GPU 時間を測り、ピクセル比で各段階に換算する。「L1 ≤ 25 ms、L2 / L3 ≤ 12 ms」を満たす最高の段階を選ぶ。測定できなければ L1 から始める（`src/three/quality/probe.ts`、`levels.ts`）。
- Tier changes (`governor.ts`, unit tests feed fake frame times): every 5 seconds look at p95; two consecutive readings over this level's budget (L0 / L1 34 ms, L2 / L3 20 ms, matching the telemetry histogram boundaries) drop one level; resolution changes immediately and the rest waits for the next camera cut. Upgrades happen only at camera cuts and when entering or leaving a conversation: if this level has stayed within budget for 30 seconds, 60 seconds have passed since the last downgrade, and a 2x stress of 30 frames still holds about 60 frames, upgrade one level at the next cut. The stress test runs only while the picture is still (camera has not moved for 10 frames: after a hard cut and before the player moves; not during camera pushes and the first screen's slide, and not when busy), stops as soon as the camera moves, and that attempt does not count; if it fails, the 30 seconds must be accumulated again, and after repeated failures wait 60, 120, 240 seconds (UX's review of F-2c: phones that cannot pass the stress test must not let players see that second at 30 fps). Two downgrades in a run lock the ceiling. Low-power mode (Safari locks to 30 fps and the self-test says the GPU is idle) is computed against the 30 fps budget and never upgrades.
  ティアの昇降（`governor.ts`、単体テストは偽のフレーム時間を与える）：5 秒ごとに p95 を見て、このレベルの予算（L0 / L1 は 34 ms、L2 / L3 は 20 ms、テレメトリのヒストグラムの境界と一致）を 2 回連続で超えたら 1 段下げる。解像度はすぐ変わり、残りは次のカメラ切り替えまで待つ。昇格はカメラ切り替え時と会話の出入りのときだけ：このレベルで 30 秒間予算内に収まり、降格から 60 秒経ち、さらに 2 倍の負荷をかけても 30 フレームで約 60 フレームを保てていれば、次の切り替えで 1 段上げる。負荷テストは画面が動かないときだけ行う（カメラが 10 フレーム動いていない：ハードカット後でプレイヤーがまだ歩いていないとき。カメラのプッシュや最初の画面のスライド中、忙しいときは行わない）。カメラが動いたらすぐ止め、その回は数えない。失敗した場合は 30 秒を貯め直し、失敗が続くたびに 60、120、240 秒待つ（UX による F-2c のレビュー：負荷テストを通れない端末で、プレイヤーにその 1 秒の 30 フレームを見せてはならない）。1 局で 2 回降格したら上限をロックする。低電力モード（Safari が 30 フレームに固定され、自己測定では GPU がとても空いている）は 30 フレームの予算で計算し、昇格しない。
- Telemetry (`src/telemetry/telemetry.ts` queues first, F-0's network layer sends in batches): `quality_changed` (the starting level carries `probeGpuMs`; going to L2 / L3 carries `assetMbps`; the `lowPower` and `locked` cases do not change level, with `from` = `to`), and one `perf_sample` every 10 seconds (9-bin histogram).
  テレメトリ（`src/telemetry/telemetry.ts` がまずキューに入れ、F-0 のネットワーク層がバッチ送信）：`quality_changed`（開始レベルは `probeGpuMs` 付き、L2 / L3 への移行は `assetMbps` 付き。`lowPower` と `locked` はレベルを変えず `from` = `to`）、10 秒ごとに `perf_sample` を 1 件（9 区分のヒストグラム）。

**Measurement page**: `?measure`, or publish it as a private claude.ai page and open it on a phone (no deployment needed). It first shows the entry self-test result and the tier it chose; after tapping 「開始計測」 ("Start measuring"), each level walks S7's route for 6.5 seconds recording frame time, then stops at S7's stress camera position and draws the same frame 2, 4, 8…32 times to compute one frame's GPU time. Then it takes bloom comparison shots (UX's review of F-2c): two each for L0 and L1, looking toward the gate at 18:45 along the line where the sun sets into the west gate, and at a fire at night (the plaza has no fire yet, so the measurement page uses a glowing sphere with a warm point light as a stand-in). Finally it gives one table, four images, and a block of JSON. In a private claude.ai page there is an extra 「保存結果」 ("Save results") button: images are saved to the page's assets, and the numbers and image IDs go to the page's db (`runs/<id>`), which the frontend reads directly, so no copying is needed; outside a private page, copy the JSON as before. `?measure&looks` only takes the images, without timing (for checking camera positions). Publish as a private page:

**計測ページ**：`?measure`、または claude.ai の非公開ページとして公開してスマートフォンで開く（デプロイ不要）。まず入場時の自己測定の結果と選ばれたティアを表示する。「開始計測」をタップすると、各レベルが S7 のルートを 6.5 秒歩いてフレーム時間を記録し、その後 S7 の負荷カメラ位置に止まって同じフレームを 2、4、8…32 回描き、1 フレームの GPU 時間を算出する。続いてブルームの比較画像を撮る（UX による F-2c のレビュー）：L0 と L1 で各 2 枚、18:45 に太陽が西門に沈む線上から門の方を見たものと、夜の火の光（広場にはまだ火がないので、計測ページでは光る小球と暖色の点光源を代役に置く）。最後に表 1 つ、画像 4 枚、JSON 1 ブロックを出す。claude.ai の非公開ページ内では「保存結果」ボタンが増える：画像はページの assets に、数値と画像の番号はページの db（`runs/<id>`）に保存され、フロントエンドが直接読むのでコピーは不要。非公開ページの外ではこれまでどおり JSON をコピーする。`?measure&looks` は画像だけを撮り、計時はしない（カメラ位置の確認用）。非公開ページとして公開する手順：

```sh
ZOUJIN_SCENE_ROOT=<scene directory / シーンのディレクトリ> pnpm --filter @zoujin/web exec vite build --base ./ --outDir <temp directory / 一時ディレクトリ>/dist
node apps/web/scripts/measure_artifact.mjs <temp directory / 一時ディレクトリ>/dist <temp directory / 一時ディレクトリ>/page   # then publish page/index.html along with the other files / その後 page/index.html を他のファイルと一緒に公開する
```

Page hosting accepts only common web file types, so `.glb`, `.ktx2`, and `.wasm` are embedded as base64 in the script and handed to the loader by a small fetch shim; load times on this page include decoding, so look only at frame time and GPU time. To use 「保存結果」, declare the `db` and `assets` capabilities for the page when publishing.

ページのホスティングは一般的なウェブのファイル種別しか受け付けないので、`.glb`、`.ktx2`、`.wasm` は base64 でスクリプト内に置き、小さな fetch シムでローダーに渡す。このページの読み込み時間にはデコードが含まれるので、フレーム時間と GPU 時間だけを見ること。「保存結果」を使うには、公開時にページに `db` と `assets` の 2 つの機能を宣言する。

## Checks / 検査

```sh
pnpm --filter @zoujin/web test          # unit tests (network layer, nav mesh, sun, tier changes, histogram); when scene output exists, also checks that every location point is reachable / 単体テスト（ネットワーク層、ナビメッシュ、太陽、ティアの昇降、ヒストグラム）。シーン生成物があるときは、すべての位置点に到達できることも検査する
pnpm --filter @zoujin/web build
pnpm --filter @zoujin/web check:bundle  # shell ≤ 120 KB, 3D chunk ≤ 250 KB (brotli, assets/budgets.json) / シェル ≤ 120 KB、3D チャンク ≤ 250 KB（brotli、assets/budgets.json）
pnpm --filter @zoujin/web e2e           # build first; starts mock and preview itself; headless Chromium + software rendering, screenshots in test-results/shots/ / 先に build。モックとプレビューは自分で起動する。ヘッドレス Chromium + ソフトウェアレンダリング、スクリーンショットは test-results/shots/
```

`f0.spec.ts` checks the F-0 card's acceptance against the mock: invite code, 401 returning to the invite code page (both WebSocket 4001 and REST are checked), 409 on opening (続きから / 新しく始める), one text round (subtitles, light feedback, clock +10 minutes), reconnecting after a 5-second network drop (a commit decided during the drop is resent once, not duplicated or lost), and unknown message types do not raise errors. Each test first does `POST /__mock/reset`. Components not touching WebSocket directly is checked by ESLint (`no-restricted-globals`, only `src/net/` may use it).

`f0.spec.ts` はモックを相手に F-0 カードの受け入れ条件を検査する：招待コード、401 で招待コードページに戻ること（WebSocket 4001 と REST の両方）、開局時の 409（続きから / 新しく始める）、テキスト 1 ラウンド（字幕、軽いフィードバック、時計 +10分）、5 秒の切断後の再接続（切断中に確定した commit は 1 回だけ再送され、重複も欠落もない）、未知のメッセージ種別でエラーにならないこと。各テストは最初に `POST /__mock/reset` を呼ぶ。コンポーネントが WebSocket に直接触れないことは ESLint が検査する（`no-restricted-globals`、`src/net/` だけが使える）。

The e2e also checks F-2 card acceptance (`world.spec.ts`) and quality (`quality.spec.ts`: the self-test picked a tier, tier changes work, the telemetry shape is right, and the average color difference over several regions of the first screen across L0 / L1 / L2 is ≤ 6/255). `world.spec.ts` checks that: the first screen matches the S7 first-screen composition; the shadow line on the royal city wall moves up as the clock goes from 18:00 to 18:55; draw calls stay within budget; the follow camera framing matches UX's numbers (character height, horizon position); the store receives exactly one move when walking into the execution ground; the workshop can be walked out of even if it is closed while the player is still inside; and there are no console errors. On machines that already have Chromium installed, point to it with `PW_CHROMIUM=<path>` to avoid downloading again. CI (`.github/workflows/web.yml`) generates the plaza at draft quality and caches it, and uploads screenshots as artifacts.

e2e は F-2 カードの受け入れ条件（`world.spec.ts`）と画質（`quality.spec.ts`：自己測定がティアを選んだこと、ティアの昇降が働き始めること、テレメトリの形が正しいこと、L0 / L1 / L2 の最初の画面のいくつかの領域の平均色差が ≤ 6/255）も検査する。`world.spec.ts` が検査するのは次のとおり：最初の画面が S7 の最初の画面の構図と一致すること、時計が 18:00 から 18:55 に進むと王城の壁の影の線が上へ動くこと、draw call が予算内であること、追従カメラのフレーミングが UX の数値（人物の高さ、地平線の位置）に合うこと、刑場に入るとき store が移動をちょうど 1 回受け取ること、プレイヤーが中にいる間に作業場が閉まっても歩いて出られること、コンソールにエラーがないこと。すでに Chromium が入っているマシンでは `PW_CHROMIUM=<パス>` で指定すればダウンロードし直す必要はない。CI（`.github/workflows/web.yml`）はドラフト品質で広場を生成してキャッシュし、スクリーンショットを成果物としてアップロードする。

## Where the code is / コードの場所

- `src/app/`: shell, routing (History API, no router package), TanStack Query REST data.
  `src/app/`：シェル、ルーティング（History API、ルーターパッケージは使わない）、TanStack Query の REST データ。
- `src/net/`: REST (`rest.ts`), one WebSocket per session (`live.ts`: hello, ping, backoff reconnect, close codes), writing messages into the store (`session.ts`: commits applied and deduplicated by sequence number, missing numbers re-fetched, a round not delivered before disconnect resent, light feedback), and actions that components call (`play.ts`).
  `src/net/`：REST（`rest.ts`）、1 局につき 1 本の WebSocket（`live.ts`：hello、ping、バックオフ再接続、クローズコード）、メッセージの store への書き込み（`session.ts`：commit を番号順に適用して重複排除、欠番の再取得、切断前に届かなかった 1 ラウンドの再送、軽いフィードバック）、コンポーネントが呼ぶアクション（`play.ts`）。
- `src/stores/`: zustand world / player / voice / ui (frontend-design section 6).
  `src/stores/`：zustand の world / player / voice / ui（frontend-design 第 6 節）。
- `src/screens/`: login, cover, role selection, world, ending (placeholder); `src/ui/hud/`: the world screen HUD; `src/ui/copy.ts`: the Japanese copy in use (keyed per `docs/ux/copy-ja.md`).
  `src/screens/`：ログイン、カバー、身分選択、世界、エンディング（仮）。`src/ui/hud/`：世界画面の HUD。`src/ui/copy.ts`：使用する日本語文言（`docs/ux/copy-ja.md` のキーに従う）。
- `src/telemetry/`: queueing (`telemetry.ts`) and batch sending (`flush.ts`, every 10 seconds, keepalive when the page is hidden).
  `src/telemetry/`：キュー（`telemetry.ts`）とバッチ送信（`flush.ts`、10 秒ごと、ページが非表示のときは keepalive）。
- `src/screens/WorldScreen.tsx`: the 3D plaza (a separate chunk, keeping the shell small).
  `src/screens/WorldScreen.tsx`：3D 広場（独立したチャンクで、シェルを小さく保つ）。
- `src/three/World.tsx`: loads the scene in two steps (walkable geometry first, textures and occlusion later), then lighting, player, camera, post-processing.
  `src/three/World.tsx`：シーンを 2 段階で読み込み（歩ける形状が先、テクスチャと遮蔽があと）、その後にライト、プレイヤー、カメラ、ポストプロセスを設定する。
- `src/three/scene/`: scene manifest, loading, conversion between plane coordinates and glTF coordinates, first-screen camera position.
  `src/three/scene/`：シーンのマニフェスト、読み込み、平面座標と glTF 座標の換算、最初の画面のカメラ位置。
- `src/three/nav/navmesh.ts`: reads `nav.json`; A* plus path straightening, ground snapping, wall sliding.
  `src/three/nav/navmesh.ts`：`nav.json` を読み、A* と経路の直線化、接地、壁沿いのスライドを行う。
- `src/three/Lighting.tsx`, `sun.ts`, `shaderPatches.ts`, `PostFX.tsx`: S7's "bake only occlusion" lighting (real-time sun and shadows, physical sky, fog) and post-processing.
  `src/three/Lighting.tsx`、`sun.ts`、`shaderPatches.ts`、`PostFX.tsx`：S7 の「遮蔽だけをベイク」するライティング（リアルタイムの太陽と影、物理ベースの空、霧）とポストプロセス。
- `src/three/quality/`: the four quality levels, starting-tier self-test, tier changes, frame-time histogram; `src/three/post.ts`: the post-processing chain (shared by PostFX and the self-test); `src/screens/MeasureScreen.tsx`: the measurement page.
  `src/three/quality/`：画質 4 段階、開始ティアの自己測定、ティアの昇降、フレーム時間のヒストグラム。`src/three/post.ts`：ポストプロセスのチェーン（PostFX と自己測定が共用）。`src/screens/MeasureScreen.tsx`：計測ページ。
- `src/three/Player.tsx`, `CameraRig.tsx`, `rig.ts`: the player, the camera (the fixed camera position of the first screen; after the player first moves or rotates the camera it slides to UX's follow camera: 9 m behind, 3.5 m high, looking down about 12.5°; over-the-shoulder during conversation; hard cut when reduced motion is on), and the per-frame state they share.
  `src/three/Player.tsx`、`CameraRig.tsx`、`rig.ts`：プレイヤー、カメラ（最初の画面の固定カメラ位置。プレイヤーが初めて歩くかカメラを回すと UX の追従カメラへスライドする：後方 9 m、高さ 3.5 m、約 12.5° 見下ろし。会話中は肩越し。モーション低減時はハードカット）と、それらが共有するフレームごとの状態。
