# A-0 Melos art pipeline pilot (frontend) / A-0 メロス アートパイプライン・パイロット（フロントエンド）

Status: **container part done (stand-in)**, waiting for the real Melos to be made on the Mac. 2026-10-10, frontend (second version of the same day: head split saves VRAM, running added, three times of day, three lines swapped to Melos's candidate voice, lip-sync timing aligned).
Card: `docs/tasks/m2-0/A-0.md`. Acceptance criteria (UX): `docs/tasks/m2-0/A-0-acceptance.md`. Basis: `docs/ux/art-direction.md` 5.1〜5.6, 9.1〜9.6; `docs/frontend/frontend-design.md` 10.6.2, 10.6.4.

状態：**コンテナ部分は完了（代役）**。Mac で本物のメロスを作るのを待っている。2026-10-10、フロントエンド（同日の第 2 版：頭部分割で VRAM を節約、走りを追加、3 つの時刻、3 つの台詞をメロス候補の声に差し替え、口パクのタイミング合わせ）。
カード：`docs/tasks/m2-0/A-0.md`。受け入れ基準（UX）：`docs/tasks/m2-0/A-0-acceptance.md`。根拠：`docs/ux/art-direction.md` 5.1〜5.6、9.1〜9.6；`docs/frontend/frontend-design.md` 10.6.2、10.6.4。

## In one sentence / 一言で

With a stand-in, the whole path of "modeling → decimating into three versions → rigging → animation → expressions and lip-sync → export and compression → phone test page" has been walked through.
The downloads of the three versions and the animations are all within budget, the dialogue version has exactly 10 draw calls; after letting only the head carry expressions, the VRAM taken by expressions dropped to one third of the original.
The real Melos has to be built on zg's Mac (the container cannot download MPFB and CC0 assets); once built, the same scripts run it all in one go.

代役を使って、「モデリング → 減面で 3 バージョン → リギング → アニメーション → 表情と口パク → エクスポートと圧縮 → スマホ用テストページ」の全工程を通した。
3 バージョンとアニメーションのダウンロードはいずれも予算内で、会話版の draw call はちょうど 10。頭だけに表情を持たせるようにしたところ、表情が占める VRAM は元の 3 分の 1 に下がった。
本物のメロスは zg の Mac で作る必要がある（コンテナでは MPFB と CC0 素材をダウンロードできない）。作成後は同じスクリプトで一度に実行する。

**The stand-in is not Melos.** It is assembled from a 2016 MakeHuman data package on npm (`makehuman-data@0.0.2`, the same hm08 body topology; file headers AGPL, clothes CC BY), used only to measure size and frame time, and does not go into the product.

**代役はメロスではない。** npm にある 2016 年の MakeHuman データ（`makehuman-data@0.0.2`、同じ hm08 人体トポロジー。ファイルヘッダーは AGPL、衣服は CC BY）で組んだもので、サイズとフレーム時間の計測にだけ使い、製品には入れない。

## Numbers (stand-in, 2026-10-10) / 数値（代役、2026-10-10）

| File / ファイル | Download / ダウンロード | Budget / 予算 | Faces / 面数 | Materials / マテリアル | Morphs / モーフ | Morphs in VRAM (three.js) / VRAM 内のモーフ（three.js） |
|---|---|---|---|---|---|---|
| Dialogue version, high-end `talk_high.glb` / 会話版 ハイエンド `talk_high.glb` | **2.19 MB** | ≤ 6.5 MB | 43.5k | 5 | 66 | 13.5 MB |
| Dialogue version, tier B `talk_std.glb` / 会話版 ティア B `talk_std.glb` | **1.36 MB** | ≤ 4 MB | 25.9k | 5 | 64 | 9.4 MB |
| Walking version `walk.glb` / 歩行版 `walk.glb` | **0.25 MB** | ≤ 0.5 MB | 8.0k | 1 | 0 | — |
| Shared animations `anims.glb` (idle, walk, run) / 共用アニメーション `anims.glb`（待機、歩き、走り） | **0.13 MB** | ≤ 0.3 MB | — | — | — | — |

- 53 bones (≤ 60). Morphs = 52 ARKit + 15 visemes (`viseme_aa` etc.; Japanese vowels あいうえお = aa / I / U / E / O); each mesh keeps only the morphs that actually move it (head 64〜66, hair cards 21, teeth 20).
  ボーン 53 本（≤ 60）。モーフ = ARKit 52 個 + 口形 15 個（`viseme_aa` など。日本語の母音あいうえお = aa / I / U / E / O）。各メッシュには実際にそれを動かすモーフだけを残す（頭 64〜66、髪カード 21、歯 20）。
- The dialogue version has 5 materials: skin, eyes, hair cards (hair + brows + lashes in one image), clothes, teeth (teeth + tongue in one image). The skin is cut into head and body meshes (same material), 6 meshes in total; eyes and teeth are inside the head and cast no shadow. So each frame has 6 + 4 shadow draws, **10 draw calls** (the card's line is ≤ 10).
  会話版のマテリアルは 5 つ：肌、目、髪カード（髪＋眉＋まつ毛を 1 枚の画像に）、衣服、歯（歯＋舌を 1 枚の画像に）。肌は頭と体の 2 つのメッシュに分ける（同じマテリアル）ので、メッシュは合計 6 つ。目と歯は頭の内側にあり、影は落とさない。したがって 1 フレームあたり 6 回＋影 4 回、**draw call は 10**（カードの基準は ≤ 10）。
- **Head split** (`split_head` in `lod_export.py`): cut horizontally at a height no morph can reach (2 cm below the chin), so only the head carries morphs and the body does not. Normals are fixed before cutting, so the cut leaves no lighting seam (not visible in screenshots). Expression VRAM: tier B 25.7 → 9.4 MB, high-end 43.8 → 13.5 MB; 4 distinct high-end characters about 54 MB (previously about 175 MB). Downloads got smaller too (high-end 2.33 → 2.19 MB, tier B 1.69 → 1.36 MB).
  **頭部分割**（`lod_export.py` の `split_head`）：どのモーフも届かない高さ（顎の 2 cm 下）で水平に切り、頭だけがモーフを持ち、体は持たない。切る前に法線を固定するので、切断面に照明の継ぎ目は出ない（スクリーンショットでは見えない）。表情の VRAM：ティア B 25.7 → 9.4 MB、ハイエンド 43.8 → 13.5 MB。異なるハイエンドキャラ 4 体で約 54 MB（以前は約 175 MB）。ダウンロードも小さくなった（ハイエンド 2.33 → 2.19 MB、ティア B 1.69 → 1.36 MB）。
- The version without morph normals: high-end 1.95 MB, tier B 1.10 MB, morph VRAM halved again (6.7 / 4.7 MB).
  モーフ法線なしのバージョン：ハイエンド 1.95 MB、ティア B 1.10 MB、モーフ VRAM はさらに半減（6.7 / 4.7 MB）。
- Fixed a bug: previously tier B's morphs were computed under "the first frame's animation pose", exaggerating mouth and brow amplitudes by about 30%; now they are computed in the rest pose, consistent with the high-end version.
  バグを 1 つ修正：以前はティア B のモーフを「最初のフレームのアニメーションポーズ」で計算していたため、口と眉の振幅が約 30% 誇張されていた。現在は静止ポーズ（rest pose）で計算し、ハイエンドと一致する。
- Sources: `lod_report.json`, `compress_report.json` (the stand-in's reports, kept in the project folder `frontend/spikes/a0-melos/reports/`, not in the repo); morph VRAM uses `assets/pipeline/morphmem.mjs` (vertices × morph count × 2 × 16 bytes).
  出典：`lod_report.json`、`compress_report.json`（代役のレポート。プロジェクトフォルダ `frontend/spikes/a0-melos/reports/` に置き、リポジトリには入れない）。モーフ VRAM は `assets/pipeline/morphmem.mjs`（頂点 × モーフ数 × 2 × 16 バイト）で計算。

**Where the stand-in's numbers are low**: the stand-in's texture sources are only 512, and the skin has no normal map. The real Melos uses MPFB's 1024〜4096 textures, and with a 2048 normal map for high-end skin (UASTC about 2.5〜3 MB), **the high-end tier is estimated at 5〜6 MB, close to the 6.5 MB line**; adding a 1024 skin normal map to the standard tier is about +0.7 MB, estimated 2.5〜3 MB. [Inference; to be measured with the real Melos]

**代役の数値が小さめな点**：代役のテクスチャ元画像は 512 しかなく、肌に法線マップがない。本物のメロスは MPFB の 1024〜4096 テクスチャを使い、ハイエンドの肌に 2048 の法線マップ（UASTC で約 2.5〜3 MB）を加えると、**ハイエンドは 5〜6 MB と見積もられ、6.5 MB のラインに近い**。標準ティアは 1024 の肌法線マップを加えて約 +0.7 MB、2.5〜3 MB と見積もる。〔推定。本物のメロスで計測するまで〕

## Test page / テストページ

A private claude.ai page (like S7, not a deployment). The link is with the frontend thread. Page source `page/index.src.html`, packed by `build/pack.py`.

非公開の claude.ai ページ（S7 と同様、デプロイではない）。リンクはフロントエンドのスレッドにある。ページのソースは `page/index.src.html`、`build/pack.py` でパックする。

- Five viewpoints: **dialogue (over-the-shoulder)**, close-up (for inspection, not a product camera), **side-by-side comparison** (split screen, tier B on the left and high-end on the right, same position and same animation), exploration (the product's follow camera, Melos running, switchable to walking), backlight (silhouette before the 18:50 sunset, 5.3).
  5 つの視点：**会話（肩越し）**、接写（検査用で、製品のカメラではない）、**並べて比較**（左右分割、左がティア B で右がハイエンド、同じ位置で同じアニメーション）、探索（製品の追従カメラ、メロスが走っている。歩きに切り替え可能）、逆光（18:50 の日没前のシルエット、5.3）。
- Three times of day (UX acceptance 1.2): 17:30 (first screen), true noon 12:00, 18:50 backlight; one tap in settings switches them, and the time slider can also be dragged.
  3 つの時刻（UX 受け入れ 1.2）：17:30（最初の画面）、真昼 12:00、18:50 逆光。設定でワンタップで切り替わり、時間バーをドラッグすることもできる。
- The character can: blink every 3〜6 seconds (15% double blinks); turn the head slightly with eyes on the player (or the camera), with small saccades every 0.6〜2.5 seconds and eyelids following the eyes; five expressions, three brow types; speak three Melos lines with the mouth following the voice; dialogue idle, walk, run. Running and walking are procedural placeholder animations with speed computed from stride so the feet do not slide; the final ones will use CC0 motion capture.
  キャラクターができること：3〜6 秒ごとの瞬き（15% は 2 連続）。頭を少し回し、目はプレイヤー（またはカメラ）を見る。0.6〜2.5 秒ごとに小さくサッカードし、まぶたが目に追従する。5 種類の表情、3 種類の眉。メロスの台詞を 3 つ話し、口が声に合わせて動く。会話の待機、歩き、走り。走りと歩きはプロシージャルなプレースホルダーのアニメーションで、速度は歩幅から計算済みなので足が滑らない。正式版は CC0 のモーションキャプチャを使う。
- The over-the-shoulder camera follows ux-design 6.3: the player's back at lower-left foreground, the other person in the upper third; camera FOV is computed automatically so that "the face (chin to hairline) takes 13.5% of screen height", and the HUD shows the measured value.
  肩越しカメラは ux-design 6.3 に従って配置する：プレイヤーの背中は左下の前景、相手は上 3 分の 1。カメラの視野角は「顔（顎から生え際）が画面高の 13.5% を占める」ように自動計算し、HUD に実測値を表示する。
- Self-test (headless Chromium in the container, software rendering): over-the-shoulder **face takes 13.6% of screen height** (spec 12〜15%); exploration camera **Melos is 83 px tall** (spec 40〜80 px; this stand-in is about 1.98 m tall, on the high side).
  セルフテスト（コンテナ内のヘッドレス Chromium、ソフトウェアレンダリング）：肩越しカメラで**顔は画面高の 13.6%**（仕様 12〜15%）。探索カメラで**メロスの高さ 83px**（仕様 40〜80px。この代役の身長は約 1.98 m で高め）。
- 7 automatic measurements: plaza + player's back / 1 tier B / 2 tier B (the card's "× 3.4 ≤ 25ms" line) / 2 tier B with a still face (measuring the cost of morphs) / 4 high-end at DPR 2 (the card's "≤ 12ms" line) / 4 high-end with opaque skin / exploration camera with 10 walking-version characters. Results are saved into the page's own `runs`, which the frontend can read directly.
  自動計測 7 項目：広場＋プレイヤーの背中 / ティア B 1 体 / ティア B 2 体（カードの「× 3.4 ≤ 25ms」の項目）/ ティア B 2 体で顔を動かさない（モーフのコストを測る）/ ハイエンド 4 体 DPR 2（カードの「≤ 12ms」の項目）/ ハイエンド 4 体で肌が不透光 / 探索カメラで歩行版 10 体。結果はページ自身の `runs` に保存され、フロントエンドが直接読める。
- Screenshots are in the project folder `frontend/spikes/a0-melos/shots/` (the stand-in's screenshots do not go into the repo). The container uses software rendering, so frame times are meaningless and must be measured on an iPhone.
  スクリーンショットはプロジェクトフォルダ `frontend/spikes/a0-melos/shots/` にある（代役のスクリーンショットはリポジトリに入れない）。コンテナはソフトウェアレンダリングなのでフレーム時間は意味がなく、iPhone で測る必要がある。

### Lip-sync / 口パク

- Voice: Gemini Live **Fenrir**, recorded at S-1 casting. On 10-10 zg decided Melos uses Fenrir (D-025); version 4 of the test page dropped "仮の声" and Puck (`pack.py` packs only Fenrir; `gen_lines.py` still generates both voices, with Puck kept for comparison). `build/gen_lines.py` makes three lines following UX's cutting method (10-10): the backchannel 「いや」 (Fenrir: own2 cut at 0.02〜0.48 s, Puck to 0.30 s, 10 ms fade-out); about 3 seconds of own2 「いや、まだ陽は沈まぬ。」; the long line uses only Melos's own lines: own2 + 0.7 s pause + own3 + 0.7 s pause + own1, about 10.7 seconds, where the pauses inherent in the sentence are exactly what lets us see whether the mouth closes. MP3 at 64 kbps (open-source Chromium cannot decode AAC); the six lines of both voices total about 0.22 MB and are used only on this page. Puck's own3 is marked "読走样" (misread) in the casting table; UX measured that the recording was not cut off, most likely the transcription did not keep up.
  声：S-1 のキャスティング時に録音した Gemini Live の **Fenrir**。10-10 に zg がメロスは Fenrir を使うと決定した（D-025）。テストページ第 4 版では「仮の声」と Puck を削除した（`pack.py` は Fenrir だけをパックする。`gen_lines.py` は引き続き 2 つの声を生成し、Puck は比較用に残す）。`build/gen_lines.py` は UX が決めた切り方（10-10）で 3 つの台詞を作る：相槌「いや」（Fenrir は own2 の 0.02〜0.48 秒を切り出し、Puck は 0.30 秒まで、10ms のフェードアウト）。約 3 秒の own2「いや、まだ陽は沈まぬ。」。長文はすべてメロス自身の台詞：own2 + 0.7 秒の間 + own3 + 0.7 秒の間 + own1、約 10.7 秒で、文中にもともとある間で口が閉じるかどうかをちょうど確認できる。MP3 は 64kbps（オープンソースの Chromium は AAC をデコードできない）。2 つの声の 6 つの台詞で合計約 0.22 MB、このページでのみ使う。Puck の own3 はキャスティング表で「読み間違い」と記されているが、UX が録音を測ったところ切れてはおらず、おそらく文字起こしが追いついていなかった。
- **Default is "volume only"** (UX acceptance 3.4, the first-version approach of frontend-design 7.3): what A-0 must answer is whether merely opening and closing on a face about 2 cm tall looks like a puppet.
  **デフォルトは「音量のみ」**（UX 受け入れ 3.4、frontend-design 7.3 の第 1 版の方法）：A-0 が答えるべきは、高さ約 2 cm の顔で開閉するだけだと人形のように見えないかどうか。
- "Vowels + volume" is for comparison only: compute MFCC every 10 ms (26 mel bands, 12 dimensions), compare against five vowel templates to get the weights of あいうえお; both templates and live features have their mean subtracted (cepstral mean normalization), similar to Unity's uLipSync. Templates come from vowels synthesized by Open JTalk (a different voice), so they are not very accurate for Fenrir / Puck. Offline tests against Open JTalk's own lines get slightly over half the vowels right (`build/lipcheck.py`). If zg feels the vowel version is clearly more natural, then frontend-design's lip-sync design will be changed (one template per Gemini voice, made offline); an M2 matter.
  「母音＋音量」は比較用のみ：10ms ごとに MFCC（26 mel バンド、12 次元）を計算し、5 つの母音テンプレートと比べてあいうえおの重みを得る。テンプレートもリアルタイム特徴量も平均を引く（ケプストラム平均正規化）。Unity の uLipSync に似ている。テンプレートは Open JTalk が合成した母音（別の声）から作ったので、Fenrir / Puck にはあまり正確ではない。Open JTalk 自身の台詞に対するオフラインテストでは、母音は半分強が合う（`build/lipcheck.py`）。zg が母音版のほうが明らかに自然だと感じたら、frontend-design の口パク設計を変更する（Gemini の声ごとにテンプレートをオフラインで 1 つ作る）。M2 の課題。
- **Timing alignment**: each line is analyzed offline when loaded (one frame every 10 ms: loudness, vowel weights). Each frame looks up the table at "the position the ear is hearing now": playback position − output latency reported by the browser, then advanced by 60 ms to offset smoothing and one frame of display. Computed this way, the mouth-to-voice offset is theoretically near 0; a manual slider (−150〜+250 ms) is for Bluetooth headphones, since browser-reported Bluetooth latency is often inaccurate. UX's line is that the mouth lags the voice by ≤ about 90 ms. The playback Worklet in the product knows the same playback position, so the approach can be carried over directly.
  **タイミング合わせ**：各台詞は読み込み時にオフラインで先に解析する（10ms ごとに 1 フレーム：音量、母音の重み）。毎フレーム「耳が今聞いている位置」で表を引く：再生位置 − ブラウザが報告する出力遅延、さらに平滑化と 1 フレームの表示を相殺するため 60ms 先行させる。この計算なら口と声のずれは理論上 0 に近い。手動スライダー（−150〜+250ms）は Bluetooth イヤホン用で、ブラウザが報告する Bluetooth の遅延はしばしば不正確。UX の基準は口が声より遅れるのが約 90ms 以下。製品の再生 Worklet も同じ再生位置を知っているので、方法はそのまま移せる。

## Three new steps in the pipeline (also needed when running the real Melos on the Mac) / パイプラインに新しく加わった 3 ステップ（Mac で本物のメロスを走らせるときも必要）

1. **Material merging** (`merge_parts` in `lod_export.py`): the color maps of hair, brows and lashes are combined into one 1024 image (tint baked directly into pixels), and teeth and tongue into one 1024×512. 8 materials → 5.
   **マテリアル統合**（`lod_export.py` の `merge_parts`）：髪、眉、まつ毛のカラーマップを 1 枚の 1024 画像に結合し（色調は直接ピクセルに焼き込む）、歯と舌を 1 枚の 1024×512 に結合する。8 マテリアル → 5。
2. **Normal map check** (`compress.mjs`): the black background outside UV islands is filled with flat normals; if the whole image's average deviates from straight-ahead by more than 10°, it is corrected automatically and `leanDeg` is recorded in the report. The stand-in's clothes normal map was tilted 34°, making every cloth triangle look angular; after correction it is normal. Export also carries tangents (meshes without normal maps have them removed by gltf-transform).
   **法線マップの検査**（`compress.mjs`）：UV アイランドの外側の黒い背景はフラットな法線で埋める。画像全体の平均が正面から 10° 以上ずれていれば自動補正し、レポートに `leanDeg` を記録する。代役の衣服の法線マップは 34° 傾いており、布の三角形ごとに角が見えていたが、補正後は正常になった。エクスポートには接線も含める（法線マップのないメッシュは gltf-transform が取り除く）。
3. **Decimation preserving expressions** (`decimate_keep_keys`): decimate first, then bind back to the original mesh with Surface Deform and compute each morph one by one, zeroing noise smaller than 0.1 mm, so that the exporter can store only the face vertices.
   **表情を保つ減面**（`decimate_keep_keys`）：先に減面し、Surface Deform で元のメッシュに結び戻してモーフを 1 つずつ計算し、0.1mm 未満のノイズをゼロにする。これでエクスポーターは顔の頂点だけを保存できる。

## Not yet solved / まだ解決していないこと

- ~~Morph VRAM~~: solved (head split, see above).
  ~~モーフの VRAM~~：解決済み（頭部分割、上記参照）。
- Exported mesh names carry Blender serial numbers (`Body.002`, `Head.001`), and the page recognizes eyes and teeth by name prefix. The formal pipeline must rename them to clean names on export.
  エクスポートされたメッシュ名に Blender の連番が付く（`Body.002`、`Head.001`）。ページは名前の先頭で目と歯を識別している。正式パイプラインではエクスポート時にきれいな名前へ変更する必要がある。
- Close-range shadows: the dialogue camera uses a 16 m shadow box (about 1.6 cm per texel at 2048). Building shadows on distant ground vanish outside the box, so the final version needs two-level shadows (F-2).
  近距離の影：会話カメラは 16m の影ボックスを使う（2048 で 1 テクセルあたり約 1.6cm）。遠くの地面の建物の影はボックスの外で消えるので、正式版では 2 段階の影が必要（F-2）。
- The stand-in is about 1.98 m tall (MakeHuman parameters run high); the real Melos should be built at 1.75〜1.80 m.
  代役の身長は約 1.98m（MakeHuman のパラメータが高め）。本物のメロスは 1.75〜1.80m で作る。

## To do on the Mac (run only after coordinating and showing zg the commands) / Mac でやること（調整のうえ zg にコマンドを見せてから実行）

1. Install MPFB 2 (Blender extensions site) and download the official CC0 system assets: skin, eyes, brows, lashes, teeth, tongue, short hair; `faceunits01` (ARKit 52) and `visemes02` (15 visemes).
   MPFB 2（Blender 拡張サイト）をインストールし、公式の CC0 システム素材をダウンロードする：肌、目、眉、まつ毛、歯、舌、短髪。`faceunits01`（ARKit 52）と `visemes02`（口形 15 個）。
2. Download CC0 animations: the free part of Quaternius Universal Animation Library (or CMU).
   CC0 のアニメーションをダウンロードする：Quaternius Universal Animation Library の無料部分（または CMU）。
3. Build Melos (in his 20s, tall, lean and muscular, tanned shepherd; exomis leaving one shoulder bare, leather sandals, ochre and undyed wool colors, short hair), rename to the object names the scripts use (Body / Eyes / Brows / Lashes / Teeth / Tongue / Hair / Tunic / EyesLow / Rig), and save as .blend.
   メロスを作る（20 代、すらりとして筋肉質、日焼けした牧人。片方の肩を出すエクソミス、革のサンダル、黄土色と無染色の羊毛の色、短髪）。スクリプトが使うオブジェクト名（Body / Eyes / Brows / Lashes / Teeth / Tongue / Hair / Tunic / EyesLow / Rig）に改名し、.blend として保存する。
4. Send the .blend and animation files back to the container: `assets/pipeline/lod_export.py` → `assets/pipeline/compress.mjs` → `build/pack.py` → update the test page.
   .blend とアニメーションファイルをコンテナに戻す：`assets/pipeline/lod_export.py` → `assets/pipeline/compress.mjs` → `build/pack.py` → テストページを更新。
5. PM decided on approach (b): open Remote Control in the frontend thread (zg allowed it on 10-10); the session on the Mac only installs MPFB, downloads assets and opens Blender inside the newly created `~/Developer/zoujin-art/`; the frontend thread drives modeling through the device connection by operating the Blender MCP on the Mac. Do not touch `~/Developer/zoujin-spike`, gcloud or credentials; show zg the list and commands before installing and downloading.
   PM は方法 (b) に決定：フロントエンドのスレッドで Remote Control を開く（zg が 10-10 に許可済み）。Mac 上のセッションは新規作成した `~/Developer/zoujin-art/` の中でだけ MPFB のインストール、素材のダウンロード、Blender の起動を行う。モデリングはフロントエンドのスレッドがデバイス接続を通じて Mac 上の Blender MCP を操作して行う。`~/Developer/zoujin-spike`、gcloud、認証情報には触れない。インストールとダウンロードの前に、リストとコマンドを zg に見せる。

## Files / ファイル

- `assets/pipeline/` (used by the real Melos and all later characters; not in this directory): `lod_export.py` (three versions + head split + export), `compress.mjs` (KTX2 + meshopt + normal check), `inspect.mjs`, `morphmem.mjs`.
  `assets/pipeline/`（本物のメロスと今後のすべてのキャラクターが使う。このディレクトリにはない）：`lod_export.py`（3 バージョン＋頭部分割＋エクスポート）、`compress.mjs`（KTX2＋meshopt＋法線検査）、`inspect.mjs`、`morphmem.mjs`。
- `build/`: `mhload.py` (reads MakeHuman data), `build_standin.py` (builds the stand-in), `anims.py` (placeholder animations: idle, walk, run), `preview.py` (Cycles preview), `gen_voice.py` (test voice for vowel templates), `gen_lines.py` (cuts three lines from casting recordings), `lipcheck.py` (offline lip-sync check), `pack.py` (packs the test page), `test_page.mjs` (headless-browser self-test).
  `build/`：`mhload.py`（MakeHuman データの読み込み）、`build_standin.py`（代役の組み立て）、`anims.py`（プレースホルダーアニメーション：待機、歩き、走り）、`preview.py`（Cycles プレビュー）、`gen_voice.py`（母音テンプレート用のテスト音声）、`gen_lines.py`（キャスティング録音から 3 つの台詞を切り出す）、`lipcheck.py`（オフライン口パク検査）、`pack.py`（テストページのパック）、`test_page.mjs`（ヘッドレスブラウザのセルフテスト）。
- `page/index.src.html`: test page source (`/*MANIFEST*/` is filled in by pack.py).
  `page/index.src.html`：テストページのソース（`/*MANIFEST*/` は pack.py が埋める）。
- Decimation and compression reports, voice metadata (`reports/`) and screenshots (`shots/`) live only in the project folder `frontend/spikes/a0-melos/`; the stand-in's generated outputs do not go into the repo.
  減面と圧縮のレポート、音声メタデータ（`reports/`）、スクリーンショット（`shots/`）はプロジェクトフォルダ `frontend/spikes/a0-melos/` にのみ置く。代役の生成物はリポジトリに入れない。

## License list (used by this page) / ライセンス一覧（このページで使うもの）

| Item / 項目 | Source / 出典 | License / ライセンス | In product? / 製品に入る？ |
|---|---|---|---|
| Stand-in body, eyes, brows, lashes, teeth, tongue, short hair / 代役の人体、目、眉、まつ毛、歯、舌、短髪 | npm `makehuman-data@0.0.2` (first 16 chars of tgz sha256 `86f5d0072e270103`) / npm `makehuman-data@0.0.2`（tgz sha256 の先頭 16 文字 `86f5d0072e270103`） | File header AGPL 3 / ファイルヘッダー AGPL 3 | No / 入らない |
| Stand-in clothes Asymmetric Tunic and Sash / 代役の衣服 Asymmetric Tunic and Sash | Same as above (MakeHuman community asset) / 同上（MakeHuman コミュニティ素材） | CC BY | No / 入らない |
| Three lines / 3 つの台詞 | S-1 casting Gemini Live recordings (Fenrir, Puck), `ux/casting-audio/` / S-1 キャスティングの Gemini Live 録音（Fenrir、Puck）、`ux/casting-audio/` | Test recordings generated by this project itself / 本プロジェクト自身が生成したテスト録音 | No (the product uses live Gemini Live) / 入らない（製品ではリアルタイムの Gemini Live） |
| Test voice for vowel templates / 母音テンプレート用のテスト音声 | Open JTalk (pyopenjtalk-plus 0.4.1, MIT) + HTS voice Mei / Open JTalk（pyopenjtalk-plus 0.4.1、MIT）＋ HTS 音声 Mei | MIT / CC BY 3.0 | No / 入らない |
| Plaza stone textures / 広場の石材テクスチャ | Crytek Sponza (via Khronos glTF Sample Assets) / Crytek Sponza（Khronos glTF Sample Assets 経由） | CC BY 3.0 | No (the final version uses CC0 scans) / 入らない（正式版は CC0 スキャンを使う） |
| three.js 0.186.1, gltf-transform, meshoptimizer, ktx2-encoder | npm / jsDelivr | MIT etc. / MIT など | Tools / ツール |
| Final Melos (to do) / 正式なメロス（未実施） | MPFB 2 system assets, Quaternius / CMU / MPFB 2 システム素材、Quaternius / CMU | CC0 | Yes / 入る |
