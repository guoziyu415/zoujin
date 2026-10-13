# S1 · A walkable scene in a phone browser / 手機ブラウザで歩けるシーン

Technical validation, not production code. The goal is to answer three questions with real-device frame rates: can a 3D scene run stably in a phone browser; which fits better, WebGPU or WebGL2; and how many frames do resolution, crowd size and shadows each cost.

技術検証であり、正式なコードではない。実機のフレームレートで次の三つの問いに答えることが目的：手機ブラウザで 3D シーンが安定して動くか、WebGPU と WebGL2 のどちらが適しているか、解像度・人数・影がそれぞれどれだけフレームを消費するか。

- Test page (private claude.ai page, only zg can open it): https://claude.ai/artifact/Hy5hYj3mki7K8CriSx1W3H
  テストページ（claude.ai の非公開ページ。zg のみ開ける）：https://claude.ai/artifact/Hy5hYj3mki7K8CriSx1W3H
- Source: `index.html` (the page), `robot.glb` (character model after meshopt compression; a base64 copy is embedded in the page)
  ソース：`index.html`（ページ）、`robot.glb`（meshopt 圧縮後のキャラクターモデル。ページ内に base64 で埋め込み済み）
- Publishing: claude.ai Artifact. It is only a private test page, not a product deployment, and involves no Google Cloud, domain or secrets.
  公開方法：claude.ai Artifact。非公開のテストページにすぎず、製品のデプロイではない。Google Cloud、ドメイン、秘密情報は関与しない。

## What is on the page / ページの内容

- Scene: a procedurally generated Syracuse square (two rings of houses, a temple on the north side, a fountain, olive trees, market stalls, distant mountains), with a low evening sun and fog. Houses, trees and pillars all use InstancedMesh, one draw call per object type.
  シーン：プロシージャルに生成したシラクサの広場（二重の家並み、北側の神殿、噴水、オリーブの木、市場の屋台、遠い山々）。夕方の低い太陽と霧。家・木・柱はすべて InstancedMesh で、物件の種類ごとに draw call 1 回。
- Characters: RobotExpressive from the official three.js examples (CC0): 1 protagonist plus 0/6/12/24 passersby, each wandering the square (Idle / Walking / Wave).
  キャラクター：three.js 公式サンプルの RobotExpressive（CC0）。主人公 1 体と通行人 0/6/12/24 体が、それぞれ広場をうろつく（Idle / Walking / Wave）。
- Controls: virtual joystick at bottom left to move, drag the view to turn, WASD on desktop. Walking near a passerby shows a 「押して話す」 button; pressing it records the latency from press to on-screen feedback.
  操作：左下の仮想ジョイスティックで移動、画面ドラッグで視点回転、デスクトップでは WASD。通行人に近づくと「押して話す」ボタンが出て、押してから画面に反応が出るまでの遅延を記録する。
- Settings: GPU API (WebGPU first / WebGL2 fixed), resolution (1 / 1.5 / device max 2), crowd size, shadows.
  設定：GPU API（WebGPU 優先 / WebGL2 固定）、解像度（1 / 1.5 / 端末上限 2）、人数、影。
- Automatic measurement: the protagonist walks a fixed route automatically; each of 8 settings is measured for 12 seconds (3 seconds warm-up), recording median fps, frame time p95/p99, the share of frames over 34ms, draw calls and triangle count, and saving them to the page's database (collection `runs`), which the frontend thread reads with ArtifactData.
  自動計測：主人公が決まったルートを自動で歩き、8 種類の設定をそれぞれ 12 秒（ウォームアップ 3 秒）計測する。fps の中央値、フレーム時間 p95/p99、34ms を超えたフレームの割合、draw calls、三角形数を記録し、ページのデータベース（collection `runs`）に保存する。フロントエンドスレッドは ArtifactData で読み出す。

## Conclusions so far (headless Chromium in a container, software rendering; only function and counts matter, not frame rate) / これまでに得られた結論（コンテナ内のヘッドレス Chromium、ソフトウェアレンダリング。機能と数量のみを見て、フレームレートは見ない）

| Item / 項目 | Value / 数値 | Meaning / 意味 |
|---|---|---|
| 13 robots + shadows / ロボット 13 体 + 影 | about 330–346 draw calls / 65k triangles / 約 330–346 draw calls / 6.5 万三角形 | Very few triangles, but draw calls already exceed the phone budget, because this model consists of 13 sub-meshes and shadows draw everything again. The production character must be 1 skinned mesh with at most 2 materials. / 三角形は非常に少ないが、draw call はすでにスマホの予算を超えている。このモデルが 13 個のサブメッシュでできており、影でさらにもう一度描画するため。正式なキャラクターは蒙皮メッシュ 1 つ、マテリアル最大 2 つにすること。 |
| Model compression / モデル圧縮 | 464KB → 183KB (gltf-transform optimize + meshopt, -60%) / 464KB → 183KB（gltf-transform optimize + meshopt、-60%） | meshopt is effective for the asset pipeline. / アセットパイプラインでは meshopt が有効。 |
| Bundle size (Vite 8.3 + React 19.3 + R3F 9.8 + three 0.186.1) / バンドルサイズ（Vite 8.3 + React 19.3 + R3F 9.8 + three 0.186.1） | App shell 58KB; 3D chunk 209KB for WebGL, 349KB for WebGPU (all brotli) / アプリシェル 58KB、3D チャンク WebGL 版 209KB・WebGPU 版 349KB（いずれも brotli） | The WebGPU build costs 140KB more transfer and about 690KB more JS to parse; real devices must prove it is worth it. / WebGPU 版は転送が 140KB 多く、パースする JS も約 690KB 多い。それだけの価値があるか実機で証明する必要がある。 |

## Waiting on real devices / 実機での回答待ち

1. p95 frame time of WebGPU vs WebGL2 on iPhone (iOS 26)
   iPhone（iOS 26）での WebGPU と WebGL2 の p95 フレーム時間の比較
2. The gap between resolution 1.5 and 2 (decides the default DPR)
   解像度 1.5 と 2 の差（デフォルトの DPR を決める）
3. The gap between 24 and 12 passersby, and between shadows on and off (decides the crowd and shadow budget)
   24 人と 12 人、影ありと影なしの差（人数と影の予算を決める）
4. Latency from pressing the talk button to on-screen feedback
   話すボタンを押してから画面に反応が出るまでの遅延

## Limitations / 制限

- The Artifact page runs inside a claude.ai iframe, one extra layer compared with a real web page, so the numbers are conservative.
  Artifact のページは claude.ai の iframe 内で動くため、正式なウェブページより一段多くラップされ、数値は控えめに出る。
- Artifacts do not allow the microphone, so the voice pipeline needs a separate S2 (which requires a real web environment).
  Artifact ではマイクが許可されないため、音声経路は別途 S2 で行う（本物のウェブ環境が必要）。
- The procedurally generated scene is simpler than production art; the production scene will have more triangles and textures.
  プロシージャル生成のシーンは正式なアートより単純で、正式シーンの三角形とテクスチャはもっと多くなる。
