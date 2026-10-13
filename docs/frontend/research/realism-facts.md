# Realism route fact check (物語 (Monogatari) / frontend) / 写実路線のファクトチェック（物語 / フロントエンド）

Research date 2026-10-06. Tags: 〔official〕 official docs, source code, vendors; 〔third-party〕 community, media, papers, agency blogs; 〔estimate〕 worked out in this document. Data that could not be found is marked "not found". "Source code" means the npm packages I downloaded: three@0.186.1 and @sparkjsdev/spark@2.3.1.

調査日 2026-10-06。タグ：〔公式〕公式ドキュメント、ソースコード、ベンダー。〔第三者〕コミュニティ、メディア、論文、代理店のブログ。〔推定〕この文書での推算。見つからなかったデータは「見つからず」と書く。「ソースコード」は私がダウンロードした npm パッケージ three@0.186.1 と @sparkjsdev/spark@2.3.1 を指す。

## A. Gaussian splatting (GS) in mobile browsers / モバイルブラウザでのガウシアンスプラッティング（GS）

### A1 Spark (sparkjsdev/spark) / A1 Spark（sparkjsdev/spark）
- Version: latest is 2.3.1 (npm, 2026-10-01). 2.0.0 (2026-04-14) introduced LoD; 2.2.0 (2026-09-11) supports three r186+ with sorting about 20% faster; 2.3.0 (2026-09-29) added on-demand rendering. https://registry.npmjs.org/@sparkjsdev/spark ; https://github.com/sparkjsdev/spark/releases/tag/v2.2.0 〔official〕
  バージョン：最新は 2.3.1（npm、2026-10-01）。2.0.0（2026-04-14）で LoD を導入。2.2.0（2026-09-11）で three r186+ に対応し、ソートが約 20% 高速化。2.3.0（2026-09-29）でオンデマンド描画を追加。https://registry.npmjs.org/@sparkjsdev/spark ；https://github.com/sparkjsdev/spark/releases/tag/v2.2.0 〔公式〕
- Formats: PLY (including compressed PLY), SPZ, SPLAT, KSPLAT, SOG; from 2.0 also the streamable .RAD (64K splats per chunk, columnar + Gzip, random access, shows a coarse 64K version first). https://github.com/sparkjsdev/spark ; https://www.worldlabs.ai/blog/spark-2.0 (2026-04-14) 〔official〕
  フォーマット：PLY（圧縮 PLY を含む）、SPZ、SPLAT、KSPLAT、SOG。2.0 からストリーミング可能な .RAD を追加（1 チャンク 64K splat、列指向 + Gzip、ランダムアクセス可、最初に 64K の粗い版を表示）。https://github.com/sparkjsdev/spark ；https://www.worldlabs.ai/blog/spark-2.0（2026-04-14）〔公式〕
- Compositing with three meshes: splats are drawn in the transparent pass by default; depthTest=true (correctly occluded by opaque meshes), depthWrite=false (the official docs say turning it on looks bad). The docs say nothing about casting/receiving shadows or about lighting. https://sparkjs.dev/docs/spark-renderer/ 〔official〕
  three のメッシュとの合成：splat はデフォルトで透明パスで描画。depthTest=true（不透明メッシュに正しく遮蔽される）、depthWrite=false（公式によればオンにすると見た目が悪い）。ドキュメントには影の投影/受影も、ライティングの影響についても記述がない。https://sparkjs.dev/docs/spark-renderer/ 〔公式〕
- Default LoD budget (source `defaultSplatTarget`): iOS 1.5M, Android 1M, Vision Pro 750K, Quest 500K, desktop 2.5M. Note: the 2026-04 blog says "500K on phones"; the current source code is authoritative. https://sparkjs.dev/docs/lod-getting-started/ 〔official〕
  LoD のデフォルト予算（ソースの defaultSplatTarget）：iOS 1.5M、Android 1M、Vision Pro 750K、Quest 500K、デスクトップ 2.5M。注意：2026-04 のブログは「スマホ 500K」と書いているが、現行のソースコードを正とする。https://sparkjs.dev/docs/lod-getting-started/ 〔公式〕
- Paged GPU memory pool (source): on iOS the default is 96 pages × 65,536 = 6.29M splats at 16 B each, about **96 MiB GPU**, plus an equally large Uint32Array on the JS side (about 96 MiB). Desktop uses 256 pages, about 256 MiB. It can be reduced with maxPagedSplats. 〔official source code; MiB conversion 〔estimate〕〕
  ページング方式の VRAM プール（ソース）：iOS のデフォルトは 96 ページ × 65,536 = 6.29M splat、1 個 16 B で約 **96 MiB GPU**。JS 側にも同じ大きさの Uint32Array（約 96 MiB）がある。デスクトップは 256 ページで約 256 MiB。maxPagedSplats で小さくできる。〔公式ソースコード。MiB 換算は〔推定〕〕
- Storage per splat: PackedSplats 16 B; SH1 adds +8 B, SH2 +16 B, SH3 +16 B, at most 56 B with all of them. https://sparkjs.dev/docs/packed-splats/ 〔official〕
  splat あたりの容量：PackedSplats 16 B。SH1 で +8 B、SH2 で +16 B、SH3 で +16 B、すべて付けると最大 56 B。https://sparkjs.dev/docs/packed-splats/ 〔公式〕
- Performance guide: 1–3M splats on iPhone; from about 1M the CPU (transforms and sorting) becomes the bottleneck; turn off WebGLRenderer's antialias (MSAA does nothing for splats and is expensive). No fps table. https://sparkjs.dev/docs/performance/ 〔official〕
  パフォーマンスガイド：iPhone で 1–3M splat。約 1M から CPU（変換とソート）がボトルネックになる。WebGLRenderer の antialias はオフにする（MSAA は splat に効果がなく、コストが大きい）。fps の表はない。https://sparkjs.dev/docs/performance/ 〔公式〕
- three.js built-in GS: r186 (2026-09-08) added a GaussianSplat object, plus PLY/SPLAT/KSPLAT/SPZ loaders and a glTF extension. GPU counting sort; works only with WebGPURenderer (forceWebGL also works), not with WebGLRenderer; the comments call it a "minimal renderer", with no LoD and no streaming. Source examples/jsm/objects/GaussianSplat.js 〔official〕
  three.js 標準の GS：r186（2026-09-08）で GaussianSplat オブジェクトを追加し、PLY/SPLAT/KSPLAT/SPZ のローダーと glTF 拡張も加わった。GPU のカウンティングソート。WebGPURenderer でのみ動作（forceWebGL も可）、WebGLRenderer では不可。コメントでは自ら「minimal renderer」と称し、LoD もストリーミング読み込みもない。ソース examples/jsm/objects/GaussianSplat.js 〔公式〕

### A2 Measured performance / A2 実測性能
- WebSplatter paper (2026-02-03): iPhone 15 Pro Max Safari, bicycle scene with 1,063,091 splats. antimatter15/splat (WebGL) 50.5 ms (about 20 fps), web-splat (WebGPU) 45.7 ms, WebSplatter 38.5 ms (about 26 fps). Resolution not stated. https://arxiv.org/html/2602.03207v1 〔third-party: paper〕
  WebSplatter 論文（2026-02-03）：iPhone 15 Pro Max の Safari、bicycle シーン 1,063,091 splat。antimatter15/splat（WebGL）50.5 ms（約 20 fps）、web-splat（WebGPU）45.7 ms、WebSplatter 38.5 ms（約 26 fps）。解像度の記載なし。https://arxiv.org/html/2602.03207v1 〔第三者・論文〕
- Babylon.js (2026-02-16~19): GS at 30–40 fps on iPhone 15 Pro and iPhone SE2; 60 fps after turning off MSAA and using FXAA instead (splat count not given). The team's explanation: high DPI plus heavy blended overdraw is more than MSAA bandwidth can handle. https://forum.babylonjs.com/t/gaussian-splat-low-performance-on-ios-devices-vs-android/62455 〔third-party, with replies from official team members〕
  Babylon.js（2026-02-16~19）：iPhone 15 Pro と iPhone SE2 で GS は 30–40 fps。MSAA を切って FXAA にすると 60 fps（splat 数の記載なし）。チームの説明：高 DPI に大量のブレンドのオーバードローが加わり、MSAA の帯域が持たない。https://forum.babylonjs.com/t/gaussian-splat-low-performance-on-ios-devices-vs-android/62455 〔第三者、公式メンバーの返信を含む〕
- PlayCanvas: the global splat budget defaults to 1M; recommended 1M on mobile and 3M+ on desktop; fill rate is the main bottleneck. https://developer.playcanvas.com/user-manual/gaussian-splatting/building/performance 〔official〕. SuperSplat: on desktop "about 4M at high frame rates" (2026-03-11). https://blog.playcanvas.com/new-in-supersplat-walk-mode-streamed-lod-and-easy-upload 〔official〕
  PlayCanvas：グローバルな splat 予算はデフォルト 1M。推奨はモバイル 1M、デスクトップ 3M+。フィルレートが主なボトルネック。https://developer.playcanvas.com/user-manual/gaussian-splatting/building/performance 〔公式〕。SuperSplat：デスクトップで「約 4M を高フレームレートで」（2026-03-11）。https://blog.playcanvas.com/new-in-supersplat-walk-mode-streamed-lod-and-easy-upload 〔公式〕
- Utsubo guide (2026-09-24): for mobile, 200–500K splats at 30–45 fps, with 15–30 MB files on mobile. https://www.utsubo.com/blog/gaussian-splatting-guide 〔third-party〕
  Utsubo のガイド（2026-09-24）：モバイルは 200–500K splat、30–45 fps、モバイル向けファイルは 15–30 MB を推奨。https://www.utsubo.com/blog/gaussian-splatting-guide 〔第三者〕
- Public GS fps data for iPhone 12/13/14: not found.
  iPhone 12/13/14 の GS の fps の公開データ：見つからず。

### A3 File size / A3 ファイルサイズ
- Raw PLY (SH3): 62 float32 = 248 B/splat (PlayCanvas leaves out normals and counts 232 B), about 250 MB per million. SH0 is about 56–68 B/splat 〔estimate, 14–17 floats〕. https://blog.playcanvas.com/compressing-gaussian-splats/ (2023-12-05) 〔official〕
  生の PLY（SH3）：float32 が 62 個 = 248 B/splat（PlayCanvas は法線を数えず 232 B とする）、100 万あたり約 250 MB。SH0 は約 56–68 B/splat〔推定、float 14–17 個〕。https://blog.playcanvas.com/compressing-gaussian-splats/（2023-12-05）〔公式〕
- PlayCanvas compressed PLY: 16 B/splat (SH dropped). Same source 〔official〕
  PlayCanvas の圧縮 PLY：16 B/splat（SH を捨てる）。出典は同上〔公式〕
- SPZ (Niantic, MIT, v4 uses ZSTD): about 10× smaller than PLY. https://github.com/nianticlabs/spz 〔official〕. Worked out from the spec: about 64 B for SH3 and about 20 B/splat for SH0 (before entropy coding) 〔estimate〕
  SPZ（Niantic、MIT、v4 は ZSTD）：PLY の約 1/10。https://github.com/nianticlabs/spz 〔公式〕。仕様からの推算：SH3 で約 64 B、SH0 で約 20 B/splat（エントロピー圧縮前）〔推定〕
- SOG (PlayCanvas, WebP textures): about 15–20× smaller than PLY. Example: a church with 4M splats, PLY about 1 GB → 55 MB (about 14 B/splat). https://developer.playcanvas.com/user-manual/gaussian-splatting/formats/sog/ ; https://blog.playcanvas.com/playcanvas-adopts-sogs-for-20x-3dgs-compression (2025-05-15) 〔official〕
  SOG（PlayCanvas、WebP テクスチャ）：PLY の約 1/15–1/20。例：教会 4M splat、PLY 約 1 GB → 55 MB（約 14 B/splat）。https://developer.playcanvas.com/user-manual/gaussian-splatting/formats/sog/ ；https://blog.playcanvas.com/playcanvas-adopts-sogs-for-20x-3dgs-compression（2025-05-15）〔公式〕
- Scene scale: the real-world captures in the original 3DGS paper have 1–5M Gaussians; average size 734 MB for Mip-NeRF360 and 411 MB for Tanks&Temples. https://arxiv.org/pdf/2308.04079 (2023) 〔third-party: paper〕
  シーンの規模：3DGS 原論文の実写シーンは 1–5M Gaussians。平均サイズは Mip-NeRF360 が 734 MB、Tanks&Temples が 411 MB。https://arxiv.org/pdf/2308.04079（2023）〔第三者・論文〕
- World Labs Marble (AI-generated worlds): can export about 2M or about 500K splats (SPZ/PLY) and a collision mesh of 100–200K triangles; export requires the paid Standard plan, and commercial rights come with the Pro plan. https://docs.worldlabs.ai/marble/export/specs ; https://docs.worldlabs.ai/marble/export/gaussian-splat 〔official〕
  World Labs Marble（AI 生成の世界）：約 2M または約 500K splat（SPZ/PLY）と 10–20 万三角形のコリジョンメッシュをエクスポートできる。エクスポートには有料の Standard プランが必要で、商用権は Pro プラン。https://docs.worldlabs.ai/marble/export/specs ；https://docs.worldlabs.ai/marble/export/gaussian-splat 〔公式〕
- Square/street scale: no single authoritative number. Estimated 2–6M splats, SOG about 30–85 MB, SPZ (SH3) about 50–150 MB; compressed to a mobile version of 0.5–1M splats, SOG is about 7–14 MB 〔estimate〕.
  広場/街路の規模：権威ある単一の数字はない。推定 2–6M splat、SOG で約 30–85 MB、SPZ（SH3）で約 50–150 MB。モバイル版の 0.5–1M splat まで落とすと SOG で約 7–14 MB〔推定〕。

### A4 Limitations / A4 制約
- Lighting is baked into the trained result and does not respond to dynamic lights; as of 2026 the mainstream plugins still have no correct splat shadows; splats have no collision of their own. https://www.strayspark.studio/blog/gaussian-splatting-unreal-engine-5-capture-to-game-pipeline (2026-04-17) 〔third-party〕
  ライティングは学習結果に焼き込まれており、動的ライトに反応しない。2026 年時点でも主要プラグインに正しい splat の影はない。splat 自体にはコリジョンがない。https://www.strayspark.studio/blog/gaussian-splatting-unreal-engine-5-capture-to-game-pipeline（2026-04-17）〔第三者〕
- PlayCanvas turning a splat into a game (2026-04-22): voxelize with splat-transform, then generate a .collision.glb with marching cubes for collision; the character samples a "brightness grid" of about 40 KB to match the environment's light and shade; no dynamic shadows. https://blog.playcanvas.com/turning-a-gaussian-splat-into-a-videogame/ 〔official〕
  PlayCanvas が splat をゲームにした例（2026-04-22）：splat-transform でボクセル化し、marching cubes で .collision.glb を生成してコリジョンにする。キャラクターは約 40 KB の「明るさグリッド」をサンプリングして環境の明暗に合わせる。動的な影はない。https://blog.playcanvas.com/turning-a-gaussian-splat-into-a-videogame/ 〔公式〕
- Relighting: Niantic Spatial (2026-09) offers offline batch relighting (dawn, rain, fog, etc.), only to approved partners, not as a self-serve API; flat surfaces, sharp corners and glass come out poorly. https://radiancefields.com/niantic-spatial-launches-gaussian-splat-relighting (2026-09-19) 〔third-party report〕
  リライティング：Niantic Spatial（2026-09）はオフラインの一括リライティング（夜明け、雨、霧など）を提供するが、審査を通ったパートナーのみで、セルフサービスの API ではない。平面、鋭い角、ガラスの結果はよくない。https://radiancefields.com/niantic-spatial-launches-gaussian-splat-relighting（2026-09-19）〔第三者の報道〕
- Spark SplatEdit: can apply MULTIPLY/ADD to colors inside SDF regions to imitate "simple lights" (this is color grading, not physical relighting). https://sparkjs.dev/docs/splat-editing/ 〔official〕
  Spark SplatEdit：SDF 領域内の色に MULTIPLY/ADD をかけて「簡単なライト」を模擬できる（これはカラーグレーディングであり、物理的なリライティングではない）。https://sparkjs.dev/docs/splat-editing/ 〔公式〕
- Sorting and overdraw: every frame all splats must be sorted by depth (PlayCanvas docs); Spark sorts on the CPU in a worker. Splats are all translucent blending, and Apple GPU HSR cannot cull overlapping fragments (see the Apple note in C1), so overdraw is high. 〔official〕
  ソートとオーバードロー：毎フレームすべての splat を深度でソートする必要がある（PlayCanvas のドキュメント）。Spark は worker 内で CPU ソートする。splat はすべて半透明ブレンドで、Apple GPU の HSR は重なったフラグメントを除去できない（C1 の Apple の説明を参照）ため、オーバードローが多い。〔公式〕
- GPU memory: Spark without SH is about 16 MB per million, with SH3 about 56 MB per million, plus sort and index buffers 〔official figures + estimate〕.
  GPU メモリ：Spark は SH なしで 100 万あたり約 16 MB、SH3 付きで 100 万あたり約 56 MB、これにソートとインデックスのバッファが加わる〔公式の数字 + 推定〕。

### A5 Is "evening → sunset → night over three days" realistic with GS? / A5 「三日間の夕方→日没→夜」は GS で現実的か
- Assessment 〔estimate〕: every time of day needs its own capture/generation and its own download (3–4 sets); global color grading or SplatEdit can approximate it, but lanterns and firelight at night cannot light the splats; characters' shadows on splat ground need separate fake shadows (blobs or decals). If day–night change is central to the narrative, GS as the main environment is high-risk; it suits distant views for a single time of day or backgrounds for "famous scenes".
  判断〔推定〕：時間帯ごとに別々に撮影/生成し、別々にダウンロードする必要がある（3–4 セット）。全体のカラーグレーディングや SplatEdit で近似もできるが、夜の提灯や火の光で splat を照らすことはできない。splat の地面に落ちるキャラクターの影は別途フェイクシャドウ（blob やデカール）で作る必要がある。昼夜の変化が物語の核心なら、GS をメイン環境にするのはリスクが高い。単一の時間帯の遠景や「名場面」の背景に向いている。

## B. Realistic rendering with three.js (mobile) / B. three.js による写実レンダリング（モバイル）

### B1 Material cost / B1 マテリアルのコスト
- Source comments: Standard is "somewhat more computationally expensive" than Lambert/Phong; Physical has a "higher performance cost, per pixel", each effect is off by default, and each one turned on adds its own cost. three r186 src/materials 〔official〕
  ソースのコメント：Standard は Lambert/Phong より「somewhat more computationally expensive」。Physical は「higher performance cost, per pixel」で、各効果はデフォルトでオフ、1 つオンにするごとにコストが増える。three r186 src/materials 〔公式〕
- Transmission: needs an extra full-scene RT render (MSAA samples ≥ 4); the resolution can be lowered with renderer.transmissionResolutionScale. three r186 WebGLRenderer.js 〔official〕
  Transmission：シーン全体の RT をもう 1 枚描画する必要がある（MSAA samples ≥ 4）。renderer.transmissionResolutionScale で解像度を下げられる。three r186 WebGLRenderer.js 〔公式〕
- Forum: with no Physical features turned on it costs the same as Standard; clearcoat and sheen are "relatively cheap", transmission "relatively expensive"; on phones even full-screen Standard may be too expensive. https://discourse.threejs.org/t/meshphysicalmaterial-can-i-measure-how-much-more-expensive-it-is/60398 (2024-01-17) 〔third-party〕
  フォーラム：Physical の機能をオンにしなければ Standard と同じコスト。clearcoat と sheen は「比較的安い」、transmission は「比較的高い」。スマホでは全画面の Standard でも高すぎる可能性がある。https://discourse.threejs.org/t/meshphysicalmaterial-can-i-measure-how-much-more-expensive-it-is/60398（2024-01-17）〔第三者〕
- Material benchmarks in ms on phones: not found.
  スマホでの ms 単位のマテリアルのベンチマーク：見つからず。

### B2 IBL / HDR / B2 IBL / HDR
- PMREM size (source): cubeSize = equirectangular width / 4; the RT is 3·cubeSize × 4·cubeSize, RGBA HalfFloat (8 B/px), with 2 of them during generation (including ping-pong). About 25 MB each for a 2k HDR, about 6.3 MB each for a 1k HDR 〔source + estimate〕.
  PMREM のサイズ（ソース）：cubeSize = 正距円筒図の幅 / 4。RT は 3·cubeSize × 4·cubeSize、RGBA HalfFloat（8 B/px）で、生成時は 2 枚（ping-pong を含む）。2k の HDR で 1 枚約 25 MB、1k の HDR で 1 枚約 6.3 MB〔ソース + 推定〕。
- PMREM generation time on phones: no measurements found.
  スマホでの PMREM の生成時間：実測は見つからず。
- HDR files: Poly Haven venice_sunset .hdr 1k 1.44 MB, 2k 5.72 MB, 4k 22.8 MB; 2k .exr 4.76 MB. https://api.polyhaven.com/files/venice_sunset 〔official〕
  HDR ファイル：Poly Haven の venice_sunset .hdr は 1k 1.44 MB、2k 5.72 MB、4k 22.8 MB。2k の .exr は 4.76 MB。https://api.polyhaven.com/files/venice_sunset 〔公式〕
- Ultra HDR (JPEG with a gain map): example 1.5 MB .hdr → 122 KB (about 12×). https://discourse.threejs.org/t/ultrahdr-three/60548 (2024-01-21) 〔third-party〕. three has a built-in UltraHDRLoader, HalfFloatType by default. https://threejs.org/docs/pages/UltraHDRLoader.html 〔official〕
  Ultra HDR（gain map 付きの JPEG）：例として 1.5 MB の .hdr → 122 KB（約 1/12）。https://discourse.threejs.org/t/ultrahdr-three/60548（2024-01-21）〔第三者〕。three には UltraHDRLoader が組み込まれており、デフォルトは HalfFloatType。https://threejs.org/docs/pages/UltraHDRLoader.html 〔公式〕
- Needle FastHDR (prefiltered KTX2): claims that generating PMREM from a 4k EXR peaks at >250 MB; its approach saves 95% of GPU memory and loads in 1.4 s, versus 8.5 s for EXR. https://cloud.needle.tools/articles/fasthdr-environment-maps 〔third-party: vendor's own claim〕
  Needle FastHDR（プリフィルタ済みの KTX2）：4k の EXR から PMREM を生成するとピークが >250 MB になると主張。同社の方式は GPU メモリを 95% 節約し、読み込みは 1.4 s（EXR は 8.5 s）。https://cloud.needle.tools/articles/fasthdr-environment-maps 〔第三者・ベンダーの自己申告〕

### B3 Baked lighting / B3 ベイクドライティング
- lightMap and aoMap pick their UV set with texture.channel (0=uv, 1=uv1…); the docs state "a second set of UVs is required"; lightMaps are usually linear color space, floating point (.exr/.hdr). three r186 MeshStandardMaterial.js, Texture.js 〔official〕
  lightMap と aoMap は texture.channel で UV を選ぶ（0=uv、1=uv1…）。ドキュメントには「2 つ目の UV セットが必要」と明記。lightMap は通常リニア色空間の浮動小数点（.exr/.hdr）。three r186 MeshStandardMaterial.js、Texture.js 〔公式〕
- Tools: Blender Cycles Bake; three ships ProgressiveLightMap (WebGL) and ProgressiveLightMapGPU (WebGPU), which can accumulate in the browser. 〔official〕
  ツール：Blender Cycles Bake。three には ProgressiveLightMap（WebGL）と ProgressiveLightMapGPU（WebGPU）があり、ブラウザ内で蓄積できる。〔公式〕
- Case study: a Half-Life-style scene with fully baked shadows, a 512² texture atlas at 235 KB and a 512² shadow atlas at 9.8 KB, 60 fps on iPhone and Android. https://discourse.threejs.org/t/half-life-inspired-scene-and-how-i-made-it-happen/20115 (2020-10-25) 〔third-party〕
  事例：Half-Life 風のシーンで影はすべてベイク、テクスチャアトラス 512² が 235 KB、影のアトラス 512² が 9.8 KB で、iPhone と Android で 60 fps。https://discourse.threejs.org/t/half-life-inspired-scene-and-how-i-made-it-happen/20115（2020-10-25）〔第三者〕
- Real-time shadows: shadow maps of 512–1024 recommended on mobile. https://www.utsubo.com/blog/threejs-best-practices-100-tips (2026-09-11) 〔third-party〕
  リアルタイムの影：モバイルではシャドウマップ 512–1024 を推奨。https://www.utsubo.com/blog/threejs-best-practices-100-tips（2026-09-11）〔第三者〕

### B4 KTX2 and GPU memory / B4 KTX2 と VRAM
- Uncompressed RGBA8: 1024² = 4 MiB (5.3 MiB with mips); 2048² = 16 MiB (21.3 MiB with mips) 〔estimate: 4 B/px × 4/3〕.
  非圧縮 RGBA8：1024² = 4 MiB（mip 込みで 5.3 MiB）、2048² = 16 MiB（mip 込みで 21.3 MiB）〔推定：4 B/px × 4/3〕。
- KTX2Loader on iPhone (r186 source): UASTC transcodes to ASTC 4×4 (1 B/px: 1024² 1.33 MiB, 2048² 5.3 MiB, with mips); ETC1S transcodes to ETC2 RGB (0.5 B/px: 1024² 0.67 MiB, 2048² 2.7 MiB), or to ETC2 RGBA (1 B/px) when there is alpha. 〔source + estimate〕
  iPhone での KTX2Loader（r186 のソース）：UASTC は ASTC 4×4 に変換（1 B/px：mip 込みで 1024² 1.33 MiB、2048² 5.3 MiB）。ETC1S は ETC2 RGB に変換（0.5 B/px：1024² 0.67 MiB、2048² 2.7 MiB）、アルファがあると ETC2 RGBA（1 B/px）。〔ソース + 推定〕
- File size: ETC1S about 0.3–3 bpp; UASTC is 8 bpp in GPU memory and only gets small with RDO+zstd; the new XUASTC is about 1.15–3.5 bpp (typically 2.25). https://github.com/BinomialLLC/basis_universal (v2.5) 〔official〕
  ファイルサイズ：ETC1S は約 0.3–3 bpp。UASTC は VRAM 上で 8 bpp で、RDO+zstd を使って初めて小さくなる。新しい XUASTC は約 1.15–3.5 bpp（典型値 2.25）。https://github.com/BinomialLLC/basis_universal（v2.5）〔公式〕
- Usage: UASTC for high-detail textures such as normals and ORM, ETC1S for large flat-color areas and basecolor; 2048² at most. Example: StainedGlassLamp file 13→10 MB, GPU 96→21 MB. https://github.com/KhronosGroup/3D-Formats-Guidelines/blob/main/KTXArtistGuide.md 〔official〕
  使い分け：UASTC は法線や ORM のような高精細テクスチャに、ETC1S は大きな色面と basecolor に。最大 2048²。例：StainedGlassLamp はファイル 13→10 MB、GPU 96→21 MB。https://github.com/KhronosGroup/3D-Formats-Guidelines/blob/main/KTXArtistGuide.md 〔公式〕
- Support: the WebGL2 ASTC extension is at 99.94% on iOS. https://web3dsurvey.com/webgl2/extensions/WEBGL_compressed_texture_astc 〔third-party〕. ETC2 is a core WebGL2 format anyway.
  対応率：iOS での WebGL2 の ASTC 拡張は 99.94%。https://web3dsurvey.com/webgl2/extensions/WEBGL_compressed_texture_astc 〔第三者〕。ETC2 はもともと WebGL2 のコアフォーマット。

### B5 Tone mapping / B5 トーンマッピング
- r186 has ACESFilmic, AgX (an implementation based on Filament/Blender, Rec.2020 primaries) and Neutral (Khronos PBR Neutral). three r186 constants.js 〔official〕
  r186 には ACESFilmic、AgX（Filament/Blender に基づく実装、Rec.2020 の原色）、Neutral（Khronos PBR Neutral）がある。three r186 constants.js 〔公式〕
- ACES: bright colors are noticeably desaturated and hues shift; some vivid colors (bright yellow, bright green, bright blue) cannot be output. Neutral: under neutral light it keeps baseColor's hue and saturation, desaturating highlights instead. https://modelviewer.dev/examples/tone-mapping 〔official: Google model-viewer〕
  ACES：明るい色は目に見えて彩度が落ち、色相もずれる。一部の鮮やかな色（明るい黄、明るい緑、明るい青）は出力できない。Neutral：ニュートラルな光の下では baseColor の色相と彩度を保ち、ハイライトは彩度を落として処理する。https://modelviewer.dev/examples/tone-mapping 〔公式・Google model-viewer〕
- AgX: handles overexposed areas better, bright colors "go toward white the way a real camera does" (Blender 4.0, 2023-11). https://developer.blender.org/docs/release_notes/4.0/color_management/ 〔official〕
  AgX：露出オーバーの領域の扱いがよく、明るい色が「本物のカメラのように白へ向かう」（Blender 4.0、2023-11）。https://developer.blender.org/docs/release_notes/4.0/color_management/ 〔公式〕

### B6 Post-processing / B6 ポストプロセス
- Measured ms for bloom, SMAA, SSAO, DOF and LUT on iPhone: no reliable data found.
  iPhone での bloom、SMAA、SSAO、DOF、LUT の実測 ms：信頼できるデータは見つからず。
- N8AO: 2–4× faster at half resolution; depth-aware upsampling costs a fixed ~1 ms; on mobile the Performance preset is recommended (8 AO samples, 4 denoise samples). https://github.com/N8python/n8ao 〔official: author〕
  N8AO：半解像度で 2–4 倍速い。深度を考慮したアップサンプリングは固定で約 1 ms。モバイルでは Performance プリセット（AO サンプル 8、デノイズサンプル 4）を推奨。https://github.com/N8python/n8ao 〔公式・作者〕
- Fill rate: the iPhone 12 screen is 2532×1170 (about 2.96 MP) 〔official https://support.apple.com/en-us/111876 〕; with DPR capped at 2 it is about 1.3 MP, 56% fewer pixels for every full-screen pass 〔estimate〕.
  フィルレート：iPhone 12 の画面は 2532×1170（約 2.96 MP）〔公式 https://support.apple.com/en-us/111876 〕。DPR を 2 に制限すると約 1.3 MP で、全画面パスごとにピクセルが 56% 減る〔推定〕。
- MSAA is expensive at high DPI with heavy blending (see Babylon in A2); Utsubo recommends turning off MSAA on mobile, running post-processing at half resolution and merging passes. 〔third-party〕
  高 DPI で大量のブレンドがあると MSAA は高コスト（A2 の Babylon を参照）。Utsubo はモバイルでは MSAA をオフ、ポストプロセスを半解像度、パスを統合することを推奨。〔第三者〕
- WebGPURenderer: r183 (2026-02-18) renamed PostProcessing to RenderPipeline. https://app.cinevva.com/news/2026-03-18-threejs-r183-render-pipeline 〔third-party〕. The TSL nodes shipped with r186 include Bloom, GTAO, SSAO, SSGI, SSR, DepthOfField, SMAA, FXAA, TRAA, TAAU, FSR1, Lut3D, SSS (screen-space shadows) and more. Source examples/jsm/tsl/display/ 〔official〕
  WebGPURenderer：r183（2026-02-18）で PostProcessing が RenderPipeline に改名された。https://app.cinevva.com/news/2026-03-18-threejs-r183-render-pipeline 〔第三者〕。r186 標準の TSL ノードには Bloom、GTAO、SSAO、SSGI、SSR、DepthOfField、SMAA、FXAA、TRAA、TAAU、FSR1、Lut3D、SSS（スクリーンスペースシャドウ）などがある。ソース examples/jsm/tsl/display/ 〔公式〕
- Safari 26 (2025-09-15) enables WebGPU by default on iOS. https://webkit.org/blog/17333/webkit-features-in-safari-26-0/ 〔official〕. On 2026-06-07, 79% of iPhones were running iOS 26. https://macrumors.com/2026/06/09/ios-26-adoption-stats-wwdc/ 〔third-party, citing Apple〕
  Safari 26（2025-09-15）で iOS の WebGPU がデフォルトで有効になった。https://webkit.org/blog/17333/webkit-features-in-safari-26-0/ 〔公式〕。2026-06-07 時点で iPhone の 79% が iOS 26。https://macrumors.com/2026/06/09/ios-26-adoption-stats-wwdc/ 〔第三者による Apple の引用〕

### B7 Budgets of real sites / B7 実際のサイトの予算
- Utsubo (2026-09-11): on mobile about 100 draw calls, <100K vertices; textures ≤2048; DPR ≤2; a 4096² RGBA texture is about 64 MiB (85 MiB with mips). https://www.utsubo.com/blog/threejs-best-practices-100-tips 〔third-party〕
  Utsubo（2026-09-11）：モバイルでドローコール約 100、頂点 <10 万。テクスチャ ≤2048。DPR ≤2。4096² の RGBA は約 64 MiB（mip 込みで 85 MiB）。https://www.utsubo.com/blog/threejs-best-practices-100-tips 〔第三者〕
- Codrops SINGULARITY (2025-02-11): 27 meshes, 40K triangles, 2.1 MB of assets in total; DPR capped at 1.5 on mobile. https://tympanus.net/codrops/2025/02/11/building-efficient-three-js-scenes-optimize-performance-while-maintaining-quality/ 〔third-party〕
  Codrops SINGULARITY（2025-02-11）：メッシュ 27 個、4 万三角形、アセット合計 2.1 MB。モバイルの DPR 上限は 1.5。https://tympanus.net/codrops/2025/02/11/building-efficient-three-js-scenes-optimize-performance-while-maintaining-quality/ 〔第三者〕
- iOS crash case: stable after the model was reduced from 18 MB/190K faces to 1.29 MB/45K faces. https://forum.babylonjs.com/t/ios-crashing-issue-severe/32981 (2022-08) 〔third-party〕
  iOS のクラッシュ事例：モデルを 18 MB/19 万面から 1.29 MB/4.5 万面に減らしたら安定した。https://forum.babylonjs.com/t/ios-crashing-issue-severe/32981（2022-08）〔第三者〕
- A public breakdown of "a realistic three.js site + a full phone budget": not found.
  「写実的な three.js サイト + スマホ向けの完全な予算」の公開された内訳：見つからず。

## C. Realistic characters / C. 写実的なキャラクター

### C1 Budget / C1 予算
- Official MetaHuman LODs: head vertices LOD0 24,000 → LOD3 2,500; body LOD0 30,500 → LOD3 1,507; head joints 713 (LOD0) → 26 (LOD7); the 669 blendshapes exist only at LOD0; LOD3 recommended on mobile, textures ≤2048, hair as hair cards. https://dev.epicgames.com/documentation/metahuman/platform-support-and-lod-specifications-for-metahumans?lang=en-US 〔official〕
  MetaHuman 公式の LOD：頭部の頂点 LOD0 24,000 → LOD3 2,500。体 LOD0 30,500 → LOD3 1,507。頭部のジョイント 713（LOD0）→ 26（LOD7）。669 個の blendshape は LOD0 のみ。モバイルは LOD3、テクスチャ ≤2048、髪はヘアカード（cards）を推奨。https://dev.epicgames.com/documentation/metahuman/platform-support-and-lod-specifications-for-metahumans?lang=en-US 〔公式〕
- Ready Player Me Hero Character spec (service shut down, for reference only): ≤30,000 triangles, textures ≤1024², ≤2 MB per texture, ≤10 MB total, ≤4 bone weights per vertex, supports ARKit and Oculus visemes. https://docs.readyplayer.me/asset-creation-guide/reference/hero-character 〔official〕
  Ready Player Me の Hero Character 仕様（サービス終了済み、参考のみ）：≤30,000 三角形、テクスチャ ≤1024²、1 枚 ≤2 MB、合計 ≤10 MB、頂点あたりのボーンウェイト ≤4、ARKit と Oculus の visemes に対応。https://docs.readyplayer.me/asset-creation-guide/reference/hero-character 〔公式〕
- Face: ARKit's 52 blendshapes plus Oculus's 15 visemes (TalkingHead requires both). https://github.com/met4citizen/TalkingHead 〔third-party: open source〕
  顔：ARKit の 52 個の blendshape と Oculus の 15 個の viseme（TalkingHead は両方を必要とする）。https://github.com/met4citizen/TalkingHead 〔第三者・オープンソース〕
- Hair and alpha: the draw order Apple recommends for its GPUs is opaque → alpha test/discard → translucent; blending or discard forces an HSR flush and adds overdraw. https://developer.apple.com/videos/play/wwdc2020/10602/ (WWDC20) 〔official〕
  髪とアルファ：Apple の GPU で推奨される描画順は 不透明 → アルファテスト/discard → 半透明。ブレンドや discard は HSR のフラッシュを強いてオーバードローを増やす。https://developer.apple.com/videos/play/wwdc2020/10602/（WWDC20）〔公式〕
- Recommendation for this project: near-photoreal (short of pore level) main characters at 20–40K triangles, 4–5 materials (skin, eyes, hair, clothes, teeth/tongue), 1024–2048 KTX2 textures, about 60–70 bones plus 52 blendshapes 〔estimate〕.
  このプロジェクトへの提案：実写に近い（毛穴レベルまではいかない）主要キャラクターは 2–4 万三角形、マテリアル 4–5 個（肌、目、髪、服、歯と舌）、テクスチャは 1024–2048 の KTX2、ボーン約 60–70 本と blendshape 52 個〔推定〕。

### C2 Production pipeline / C2 制作パイプライン
- Ready Player Me: Netflix announced the acquisition on 2025-12-19; the service shut down on 2026-01-31 and the API and SDK no longer work. https://ryanschultz.com/tag/ready-player-me/ ; https://genies.com/blog/ready-player-me-shutdown 〔third-party〕
  Ready Player Me：Netflix が 2025-12-19 に買収を発表し、2026-01-31 にサービス終了、API と SDK は使えなくなった。https://ryanschultz.com/tag/ready-player-me/ ；https://genies.com/blog/ready-player-me-shutdown 〔第三者〕
- MetaHuman: since 2025-06-04 it can be used in any engine/DCC (including commercially), subject to the UE EULA; free for annual revenue under US$1M; must not be used to train AI. https://www.cgchannel.com/2025/06/you-can-now-sell-metahumans-or-use-them-in-unity-or-godot/ 〔third-party〕; "can be used with any engine": https://www.metahuman.com/en-US/license 〔official〕. Web/three.js is not mentioned separately; there is no official glTF export, so it has to be converted via UE/Blender; mobile LOD3 has no blendshapes 〔estimate〕.
  MetaHuman：2025-06-04 から任意のエンジン/DCC で使える（商用を含む）。UE EULA に従う。年間売上 100 万ドル未満は無料。AI の学習に使ってはならない。https://www.cgchannel.com/2025/06/you-can-now-sell-metahumans-or-use-them-in-unity-or-godot/ 〔第三者〕。「can be used with any engine」：https://www.metahuman.com/en-US/license 〔公式〕。Web/three.js については個別の言及がない。公式の glTF エクスポートはなく、UE/Blender 経由で変換する必要がある。モバイルの LOD3 には blendshape がない〔推定〕。
- MPFB/MakeHuman: the core assets (base mesh, targets, skins) are CC0 and can be used commercially in closed source; third-party assets are a separate matter; the GPL on the plugin code does not bind exported models. https://static.makehumancommunity.org/mpfb/faq/use_in_closed_source.html 〔official〕
  MPFB/MakeHuman：コアアセット（base mesh、targets、skins）は CC0 で、クローズドソースでの商用利用が可能。サードパーティのアセットは別扱い。プラグインのコードの GPL はエクスポートしたモデルを拘束しない。https://static.makehumancommunity.org/mpfb/faq/use_in_closed_source.html 〔公式〕
- Character Creator (Reallusion): content needs an Export License to be exported; "may not be publicly downloaded or used". This is a post from around 2015, so confirm with Reallusion before publishing on the web. https://forum.reallusion.com/PrintTopic335621.aspx 〔official forum〕
  Character Creator（Reallusion）：エクスポートするにはコンテンツに Export License が必要。「公開ダウンロードや公開利用は不可」。約 2015 年の投稿なので、Web で公開する前に Reallusion に確認すること。https://forum.reallusion.com/PrintTopic335621.aspx 〔公式フォーラム〕
- Avaturn: delivers GLB to three.js through an iframe; the T2 head type supports ARKit blendshapes and visemes; TalkingHead says it is free for non-commercial use. https://docs.avaturn.me/docs/integration/bodies/ 〔official〕
  Avaturn：iframe 経由で three.js に GLB を出力する。T2 の頭部タイプは ARKit の blendshape と visemes に対応。TalkingHead によれば非商用は無料。https://docs.avaturn.me/docs/integration/bodies/ 〔公式〕
- VRoid: anime style, does not meet the realism requirement.
  VRoid：アニメ調で、写実の要件に合わない。

### C3 Skin / C3 肌
- three has no dedicated skin SSS: WebGL has the SubsurfaceScatteringShader example and WebGPU has MeshSSSNodeMaterial, both being Barré-Brisebois's (GDC 2011) "translucency" approximation, which adds a few ALU instructions per direct light and no extra pass. three r186 source 〔official〕. Cost in ms: not found.
  three には肌専用の SSS がない。WebGL には SubsurfaceScatteringShader のサンプル、WebGPU には MeshSSSNodeMaterial があり、どちらも Barré-Brisebois（GDC 2011）の「透過光」近似で、直接光 1 つにつき ALU 演算が数命令増えるだけでパスは増えない。three r186 のソース〔公式〕。ms 単位のコスト：見つからず。
- Screen-space separable SSS: not built into three (not found in the source) 〔official〕.
  スクリーンスペースの分離可能 SSS：three には組み込まれていない（ソースに見当たらない）〔公式〕。

### C4 Lip sync / C4 口パク
- Audio-driven: HeadAudio (MIT) uses MFCC plus Gaussian prototype classification and outputs 15 Oculus visemes, about 50 ms end to end, <0.1 ms per block, model about 14 kB. https://github.com/kyr0/HeadAudio 〔third-party: open source〕
  音声駆動：HeadAudio（MIT）は MFCC とガウスのプロトタイプ分類で Oculus の viseme 15 個を出力する。エンドツーエンドで約 50 ms、ブロックあたり <0.1 ms、モデルは約 14 kB。https://github.com/kyr0/HeadAudio 〔第三者・オープンソース〕
- wawa-lipsync (MIT): outputs visemes in real time using the Web Audio AnalyserNode. https://cdn.jsdelivr.net/npm/wawa-lipsync@0.0.2/README.md 〔third-party〕
  wawa-lipsync（MIT）：Web Audio の AnalyserNode を使ってリアルタイムに viseme を出力する。https://cdn.jsdelivr.net/npm/wawa-lipsync@0.0.2/README.md 〔第三者〕
- Driven by text timestamps: TalkingHead maps word-level timestamps to visemes. 〔third-party〕
  テキストのタイムスタンプ駆動：TalkingHead は単語単位のタイムスタンプを viseme に対応付ける。〔第三者〕
- Driving the jaw from amplitude only: cheapest, but only opens and closes; for Japanese, the aa/E/I/O/U visemes for the five vowels cover most mouth shapes 〔estimate〕.
  振幅だけで顎を動かす：最も安いが、開閉しかできない。日本語は 5 つの母音に aa/E/I/O/U の viseme を使えば口の形の大部分をカバーできる〔推定〕。

## D. Mobile Safari constraints / D. モバイル Safari の制約

### D1 GPU and memory / D1 GPU とメモリ
- Geekbench 6 Metal scores: iPhone 12 (A14, 4-core GPU) 12,405; 13: 14,568; 13 Pro: 17,047; 14: 16,320; 15: 18,430; 15 Pro: 22,838; 16: 25,930; 17: 35,291. The iPhone 13 is about 1.17× the 12, the 15 about 1.5×, the 15 Pro about 1.8×. https://browser.geekbench.com/ios-benchmarks (accessed 2026-10) 〔third-party〕
  Geekbench 6 の Metal スコア：iPhone 12（A14、4 コア GPU）12,405、13：14,568、13 Pro：17,047、14：16,320、15：18,430、15 Pro：22,838、16：25,930、17：35,291。iPhone 13 は 12 の約 1.17 倍、15 は約 1.5 倍、15 Pro は約 1.8 倍。https://browser.geekbench.com/ios-benchmarks（2026-10 アクセス）〔第三者〕
- Safari memory limit: Apple publishes no number. Community evidence: a Babylon core member said a tab at about 1.2 GB is "already very close to the limit" (2022) https://forum.babylonjs.com/t/ios-crashing-issue-severe/32981 〔third-party〕; a Unity user crashed at around 880 MB on an iPhone 11 (2024-11) https://discussions.unity.com/t/webgl-ios-unity-sometimes-reloads-after-startup/1541942 〔third-party〕; WebKit bug 300782 (2025-10-15): texture-heavy WebGL pages reload in a loop under memory pressure, and JS gets no OOM error. https://bugs.webkit.org/show_bug.cgi?id=300782 〔official bug tracker〕
  Safari のメモリ上限：Apple は数字を公開していない。コミュニティの証拠：Babylon のコアメンバーが、タブが約 1.2 GB で「すでに上限にかなり近い」と述べた（2022）https://forum.babylonjs.com/t/ios-crashing-issue-severe/32981 〔第三者〕。Unity ユーザーが iPhone 11 で約 880 MB 前後でクラッシュ（2024-11）https://discussions.unity.com/t/webgl-ios-unity-sometimes-reloads-after-startup/1541942 〔第三者〕。WebKit bug 300782（2025-10-15）：テクスチャの多い WebGL ページがメモリ逼迫時にリロードを繰り返し、JS は OOM エラーを受け取れない。https://bugs.webkit.org/show_bug.cgi?id=300782 〔公式バグトラッカー〕
- Recommendation: keep JS plus GPU within about 500 MB in total 〔estimate〕.
  提案：JS と GPU の合計を約 500 MB 以内に抑える〔推定〕。

### D2 Mobile network speed in Japan / D2 日本のモバイル通信速度
- Ookla: median mobile download in Japan 51.95 Mbps (2025-01, 4G and 5G combined). https://datareportal.com/reports/digital-2025-japan 〔third-party, citing Ookla〕
  Ookla：日本のモバイルのダウンロード中央値は 51.95 Mbps（2025-01、4G と 5G を含む）。https://datareportal.com/reports/digital-2025-japan 〔第三者による Ookla の引用〕
- Opensignal (2026-01~03): overall download SoftBank 65.1, au 60.7, docomo 55.7, 楽天 39.6 Mbps; 123–159 Mbps when connected to 5G. https://insights.opensignal.com/reports/2026/04/japan/mobile-network-experience 〔third-party〕
  Opensignal（2026-01~03）：全体のダウンロードは SoftBank 65.1、au 60.7、docomo 55.7、楽天 39.6 Mbps。5G 接続時は 123–159 Mbps。https://insights.opensignal.com/reports/2026/04/japan/mobile-network-experience 〔第三者〕
- Median for 4G only: not found (neither source breaks it out).
  4G のみの中央値：見つからず（どちらも個別に出していない）。
- Download times 〔estimate, excluding TLS, latency and decoding〕: at 50 Mbps, 4 MB 0.64 s / 10 MB 1.6 s / 20 MB 3.2 s; at a conservative 10 Mbps (weak 4G), 3.2 s / 8 s / 16 s.
  ダウンロード時間〔推定、TLS、遅延、デコードを除く〕：50 Mbps なら 4 MB 0.64 s / 10 MB 1.6 s / 20 MB 3.2 s。保守的に 10 Mbps（弱い 4G）なら 3.2 s / 8 s / 16 s。

## What this means for us / 私たちにとっての意味
1. Using GS as the main environment conflicts with the lighting narrative of "evening → sunset → night over three days": lighting is baked into the splats, there is no self-serve real-time relighting, every time of day needs a full set of data (downloads ×3–4), and character shadows and collision need separate proxy meshes. Recommendation: use GS at most for single-time-of-day distant views or famous scenes, and use meshes plus baked lighting for the main environment.
   GS をメイン環境にすると、「三日間の夕方→日没→夜」というライティングの物語と衝突する。ライティングは splat に焼き込まれ、セルフサービスで使えるリアルタイムのリライティングはない。時間帯ごとに 1 セット丸ごとのデータが必要（ダウンロード ×3–4）で、キャラクターの影とコリジョンも別途プロキシメッシュが要る。GS は単一の時間帯の遠景や名場面にとどめ、メイン環境はメッシュとベイクドライティングにすることを提案する。
2. If we try GS: design for 0.5–1M splats on iPhone. The iPhone 15 Pro Max measured only 20–26 fps with 1.06M splats, and the iPhone 12 can only be lower. Compressed to SOG/SPZ each scene is about 7–14 MB; Spark's default paging pool on iOS is about 96 MiB GPU plus 96 MiB JS and needs to be reduced.
   GS を試すなら：iPhone では 0.5–1M splat で設計する。iPhone 15 Pro Max で 1.06M splat を動かした実測は 20–26 fps しかなく、iPhone 12 ではさらに低くなる。SOG/SPZ に圧縮すると 1 シーン約 7–14 MB。iOS での Spark のデフォルトのページングプールは約 96 MiB GPU + 96 MiB JS なので、小さくする必要がある。
3. The most cost-effective sources of realism: baked lightmaps/AO, good IBL, AgX or Neutral tone mapping, a color-grading LUT. Not transmission (an extra full-scene RT), screen-space AO or SSR.
   写実感を最も安く得られる手段：ベイクした lightmap/AO、良い IBL、AgX または Neutral のトーンマッピング、カラーグレーディングの LUT。transmission（シーン全体の RT が 1 枚増える）、スクリーンスペース AO、SSR には頼らない。
4. Approach to time-of-day change 〔estimate〕: one set of baked lightmaps per time of day (about 5.3 MiB of GPU memory per 2048² ASTC map), plus one environment map (an Ultra HDR JPG is only around a hundred KB), blending when the time of day switches.
   時間変化のやり方〔推定〕：時間帯ごとにベイクした lightmap を 1 セット（2048² の ASTC で 1 枚約 5.3 MiB の VRAM）と環境マップ 1 枚（Ultra HDR の JPG なら 100 KB 程度）を用意し、時間帯を切り替えるときにブレンドする。
5. Use KTX2 for all textures: UASTC for normals/ORM (1 B/px on iPhone), ETC1S for basecolor (0.5 B/px), saving 4–8× GPU memory compared with uncompressed RGBA8.
   テクスチャはすべて KTX2：法線/ORM には UASTC（iPhone で 1 B/px）、basecolor には ETC1S（0.5 B/px）。非圧縮 RGBA8 より VRAM を 1/4–1/8 に減らせる。
6. Memory red line: iOS has no official limit; community evidence is crashes or reloads at about 0.9–1.2 GB. Our own budget: JS plus GPU ≤500 MB, textures per scene ≤200 MB 〔estimate〕.
   メモリのレッドライン：iOS には公式の上限がなく、コミュニティの証拠では約 0.9–1.2 GB でクラッシュまたはリロードする。独自の予算：JS + GPU ≤500 MB、1 シーンのテクスチャ ≤200 MB〔推定〕。
7. Use the iPhone 12 as the GPU baseline (its Metal score is about 2/3 of the iPhone 15's): DPR capped at 2 (can be adjusted dynamically between 1.5 and 2), MSAA off, post-processing merged into 1–2 passes (bloom + LUT + FXAA/SMAA), baked AO.
   iPhone 12 を GPU のベースラインにする（Metal スコアは iPhone 15 の約 2/3）：DPR の上限は 2（1.5–2 の間で動的に調整可）、MSAA はオフ、ポストプロセスは 1–2 パスに統合（bloom + LUT + FXAA/SMAA）、AO はベイクしたものを使う。
8. Characters: near-photoreal main characters at 20–40K triangles, 4–5 materials, 1024–2048 KTX2, ARKit's 52 blendshapes plus 15 visemes; hair as alpha-tested hair cards, sorted "opaque → alpha test → translucent"; skin with the translucency approximation. RPM has shut down; MPFB (CC0) has the cleanest license; MetaHuman's license is usable, but we would have to convert to glTF ourselves, and LOD3 has no blendshapes.
   キャラクター：実写に近い主要キャラクターは 2–4 万三角形、マテリアル 4–5 個、1024–2048 の KTX2、ARKit の blendshape 52 個と viseme 15 個。髪はアルファテストのヘアカードで、「不透明 → アルファテスト → 半透明」の順に並べる。肌は透過光の近似。RPM はサービス終了。ライセンスが最もクリーンなのは MPFB（CC0）。MetaHuman もライセンス上は使えるが、glTF への変換は自前で、LOD3 には blendshape がない。
9. Lip sync: for Japanese we can use audio-driven visemes (HeadAudio, about 50 ms latency) or pre-generated timestamps; both look more natural than amplitude alone, at negligible cost.
   口パク：日本語では音声駆動の viseme（HeadAudio、遅延約 50 ms）か、事前に生成したタイムスタンプが使える。振幅だけより自然で、コストは無視できる。
10. Downloads: the median mobile speed in Japan is 50–65 Mbps (including 5G), so 10 MB takes about 1.6 s, and on weak 4G (10 Mbps) about 8 s; ≤10 MB for the first screen and ≤20 MB of streamed loading per chapter are reasonable targets 〔estimate〕. WebGPU is available on iOS 26 (79% of iPhones), but a WebGL2 fallback must be kept; three's built-in GS only supports WebGPURenderer.
    ダウンロード：日本のモバイルの中央値は 50–65 Mbps（5G を含む）で、10 MB は約 1.6 s、弱い 4G（10 Mbps）では約 8 s。最初の画面は ≤10 MB、章ごとのストリーミング読み込みは ≤20 MB が妥当な目標〔推定〕。iOS 26 では WebGPU が使える（iPhone の 79%）が、WebGL2 のフォールバックは必ず残す。three 標準の GS は WebGPURenderer にしか対応していない。

## 3DMark (for scaling zg's phone to an iPhone 12, added 2026-10-06) / 3DMark（zg のスマホの数字を iPhone 12 に換算するため、2026-10-06 追記）

- Wild Life Extreme: iPhone 12 scores 2131 (stress-test stability 74%); iPhone 15 Pro Max 3570; iPhone 16 Pro Max 4264. The 16 Pro Max is about 2.0× the 12. UL's official database: https://benchmarks.ul.com/hardware/phone/Apple+iPhone+12+review , https://benchmarks.ul.com/en/hardware/phone/Apple+iPhone+16+Pro+Max+review , https://benchmarks.ul.com/en/hardware/phone/Apple+iPhone+15+Pro+Max+review 〔third-party: UL〕
  Wild Life Extreme：iPhone 12 が 2131 点（ストレステストの安定度 74%）、iPhone 15 Pro Max が 3570 点、iPhone 16 Pro Max が 4264 点。16 Pro Max は 12 の約 2.0 倍。UL 公式データベース：https://benchmarks.ul.com/hardware/phone/Apple+iPhone+12+review 、https://benchmarks.ul.com/en/hardware/phone/Apple+iPhone+16+Pro+Max+review 、https://benchmarks.ul.com/en/hardware/phone/Apple+iPhone+15+Pro+Max+review 〔第三者：UL〕
- ~~iOS 18.7 + a 440×956 pt screen can only be an iPhone 16 Pro Max~~ (wrong, corrected 2026-10-06): zg's phone is an iPhone 17 Pro Max (zg said so). From iOS 26, Safari's UA freezes the OS version at the last iOS 18 version number, so 18_x in the UA does not mean iOS 18: https://51degrees.com/blog/apple-ios26-safari26-user-agent-string-device-detection 〔third-party〕
  ~~iOS 18.7 + 440×956 pt の画面は iPhone 16 Pro Max しかありえない~~（誤り、2026-10-06 訂正）：zg のスマホは iPhone 17 Pro Max（zg 本人の話）。iOS 26 から Safari の UA は OS のバージョンを iOS 18 の最後のバージョン番号に固定するので、UA の 18_x は iOS 18 であることを意味しない：https://51degrees.com/blog/apple-ios26-safari26-user-agent-string-device-detection 〔第三者〕
- iPhone 17 Pro Max: Wild Life Extreme 5405, Steel Nomad Light 2463 (stability 76%): https://benchmarks.ul.com/en/hardware/phone/Apple+iPhone+17+Pro+Max+review 〔third-party: UL〕. About 2.5× the iPhone 12; adding the iPhone 12's throttling factor of 1.35 → a derived factor of 3.4. GSMArena measured 6010 for the 17 Pro Max (a different method; we use UL's).
  iPhone 17 Pro Max：Wild Life Extreme 5405 点、Steel Nomad Light 2463 点（安定度 76%）：https://benchmarks.ul.com/en/hardware/phone/Apple+iPhone+17+Pro+Max+review 〔第三者：UL〕。iPhone 12 の約 2.5 倍で、iPhone 12 のサーマルスロットリング 1.35 を加味すると推算係数は 3.4。GSMArena は 17 Pro Max で 6010 点を計測（測定方法が異なるので UL の値を採用）。
- On iPhone, `gl.finish()` does not wait for the GPU: in S7's first measurement, even a configuration that was dropping frames measured only 3ms 〔measured〕.
  iPhone では `gl.finish()` が GPU を待たない：S7 の最初の実測では、フレーム落ちしている構成でも 3ms しか測れなかった〔実測〕。
