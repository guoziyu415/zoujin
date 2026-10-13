# H-1 filling in characters and fixing models / H-1 登場人物の補充とモデルの修正

## Asset scope / アセットの範囲

The existing MPFB body, facial expressions, skin materials, skeleton and three-tier LOD pipeline are reused. New characters are distinguished by build, age, hair, clothing and props; gray stand-ins or scene screenshots do not count as a finished model.

既存の MPFB の身体、表情、肌のマテリアル、スケルトン、3 段階の LOD のパイプラインをそのまま使う。新しい登場人物は体型、年齢、髪、衣装、小道具で区別し、灰色の代役やシーンのスクリーンショットをモデルの完成とはみなさない。

| Asset / アセット | Character / identity / 登場人物 / 身元 | This change / 今回の内容 |
| --- | --- | --- |
| king | King / 王 | Rebuilt; neutral expression and clothing topology fixed / 再構築し、ニュートラルな表情と衣装のトポロジーを修正 |
| selinuntius | Selinuntius / セリヌンティウス | Rebuilt; neutral expression and clothing topology fixed / 再構築し、ニュートラルな表情と衣装のトポロジーを修正 |
| sister / sister-wedding | Sister, everyday / wedding / 妹、普段 / 婚礼 | Both sets kept and rebuilt / 2 セットとも残して再構築 |
| groom / groom-wedding | Groom, everyday / wedding / 花婿、普段 / 婚礼 | Both sets kept and rebuilt / 2 セットとも残して再構築 |
| philostratus | Philostratus / フィロストラトス | Rebuilt; neutral expression and clothing topology fixed / 再構築し、ニュートラルな表情と衣装のトポロジーを修正 |
| apprentice | Apprentice / 弟子 | Rebuilt; neutral expression and clothing topology fixed / 再構築し、ニュートラルな表情と衣装のトポロジーを修正 |
| shepherd-boy | Shepherd boy / 羊飼いの少年 | Rebuilt, keeping the shepherd's crook and the original identity / 再構築し、牧杖と元の身元を維持 |
| traveler | Traveler / 旅人 | Hat, water bag, shoulder strap, red sash, a bundle of white cloth in the crook of the arm / 帽子、水袋、肩紐、赤い腰帯、腕に抱えた白い布の束 |
| melos | Melos / メロス | Reuses the fixed A-0 body and expression source; the short tunic, travel gear and materials were rebuilt and then wired in / 固定の A-0 の身体と表情のソースをそのまま使い、短い衣、旅装、マテリアルを再構築してから接続 |
| old-man | Old man / 老人 | White hair and beard, long robe, hood, walking stick, stooped posture and shorter stride / 白髪とひげ、長衣、フード、杖、前かがみの姿勢と短めの歩幅 |
| young-man | Young man / 若者 | Separate build, face and short robe / 独自の体型、顔、短い衣 |
| maiden | Maiden / 娘 | Separate build, face, long robe and headscarf / 独自の体型、顔、長衣、頭巾 |
| guards | Guard crowd / 衛兵の群衆 | Representative model with helmet and spear / 兜と長槍を持つ代表モデル |
| bandits | Bandit crowd / 山賊の群衆 | Representative model with head wrap, face cloth and weapon / 頭巾、覆面の布、武器を持つ代表モデル |
| travelers | Traveler crowd / 旅人の群衆 | Representative model with travel gear, bundle and walking stick / 旅装、包み、杖を持つ代表モデル |

17 sets in total, each containing `walk.glb`, `talk_std.glb`, `talk_high.glb` and `anims.glb`. The named crowd representatives only add visible bodies and do not change the server's crowd headcount or narration state; the existing large-scale crowds and ending crowd set pieces still go through the F-4 pipeline, and we do not claim to have added full crowd choreography.

計 17 セットで、各セットに `walk.glb`、`talk_std.glb`、`talk_high.glb`、`anims.glb` を含む。名前付きの群衆の代表は見える身体を増やすだけで、サーバー側の群衆の人数やナレーションの状態は変えない。既存の大規模な群衆とエンディングの群衆の演出は引き続き F-4 パイプラインを通り、群衆の振り付けを完全に追加したとは主張しない。

## Fixes and runtime integration / 修正と実行時の接続

- The old export kept the activation values from when shape keys were transferred, so several expressions were layered at once. Exports now all reset these to zero, runtime initialization zeroes them again, and the checker rejects non-neutral default weights; mouth shapes and blinking are still controlled by the original drivers.
  旧エクスポートは shape key を転送したときの有効値を残しており、複数の表情が同時に重なっていた。エクスポートでは一律にゼロに戻し、実行時の初期化でも再びゼロにし、チェッカーはニュートラルでないデフォルトのウェイトを拒否する。口の形とまばたきは引き続き元のドライバーが制御する。
- The upper and lower pieces of clothing are now stitched in the adjacency order of the real boundaries, so they no longer connect to the wrong vertices by sorting on angle. After triangulation, normals are unified, and closed edges are asserted to have consistent direction, fixing the diagonal tear on the back and faces disappearing from behind.
  衣装の上下のパーツは、実際の境界の隣接順に縫い合わせるように変え、角度で並べて誤った頂点につながることを防いだ。三角形分割の後に法線の向きを揃え、閉じた辺の向きが一致することをアサートして、背中の斜めの裂け目と裏面の消失を直した。
- Skirt hems and layered long robes use consistent waist and leg weights, and the lower part of a long robe follows the calf; weights are no longer transferred separately from the nearest skin alone. The arm poses of the traveler holding the cloth bundle and the old man holding his stick are handled in the exported animation.
  スカートの裾と重ね着した長衣は腰と脚のウェイトを揃え、長衣の下部はふくらはぎに追従する。最も近い肌だけからそれぞれウェイトを転送することはやめた。布の束を持つ旅人と杖を持つ老人の腕のポーズは、エクスポートしたアニメーションで処理する。
- The final browser review additionally fixed the groom's short cape overlapping the inner clothing and skin poking through under the shepherd boy's short robe. The clothing and eye materials of Melos's original prefab file failed the check, so he goes through the same full rebuild process, keeping the lean build, wool short tunic, sandals and travel gear, and the prototype is no longer exported directly.
  最終的なブラウザでの再確認で、さらに花婿の短いケープと内側の衣服の重なり、羊飼いの少年の短い衣の下から肌がはみ出る問題を直した。メロスの元のプレハブファイルの衣服と目のマテリアルはチェックに通らなかったので、同じ完全な再構築の手順に切り替え、細身で長身、羊毛の短い衣、サンダル、旅装の設定を保ち、プロトタイプをそのままエクスポートすることはやめた。
- Belts and clothing use consistent waist binding with a smaller static gap, so the belt does not float when the torso leans forward. The guards' helmets are now domed; the bandits' face cloth is built as its own continuous surface and does not inherit the hole of the human mouth.
  腰帯と衣服は腰のバインドを揃え、静的な隙間を小さくして、上体が前に傾いたときに腰帯が浮かないようにした。衛兵の兜は丸い頂部に変えた。山賊の覆面の布は独立した連続曲面として作り、人体の口の穴を引き継がない。
- Facial detail is kept; when the high tier is over budget, only overly dense clothing topology is simplified. Walking, normal dialogue and high-tier dialogue keep their original separate budgets.
  顔のディテールは残す。高品質の段階が予算を超えたときは、密すぎる衣装のトポロジーだけを簡略化する。歩行、通常の会話、高品質の会話は引き続き元の独立した予算を使う。
- Crowd representatives pick positions from the real nav polygons of their location, avoiding the player's and ordinary NPCs' current and target points, existing crowd representatives and the F-4 crowds. The safety gap is 1.4 m; if there is no position the representative is not shown rather than stacked on someone else; the player approaching does not make a representative teleport. During ending set pieces, the exploration-layer characters are hidden as a whole.
  群衆の代表は所属する場所の実際の nav polygon から位置を選び、プレイヤーと通常の NPC の現在地点と目標地点、既存の群衆の代表、F-4 の群衆を避ける。安全な間隔は 1.4 メートル。位置がなければ表示せず、他の人に重ねない。プレイヤーが近づいても代表が瞬間移動することはない。エンディングの演出中は探索レイヤーの登場人物をまとめて隠す。
- The production frontend's static character directory publishes only the four kinds of runtime GLB; build reports, raw GLBs, Blender files and QA images cannot be read through the static character path; the asset manifest is used for build and deployment validation.
  本番のフロントエンドの登場人物の静的ディレクトリが公開するのは 4 種類の実行時 GLB だけで、ビルドレポート、元の GLB、Blender ファイル、QA 画像は登場人物の静的パスからは読めない。アセットの一覧はビルドとデプロイの検証に使う。

## Reproducible build and local evidence / 再現可能なビルドとローカルの証拠

Fully rebuild with `assets/pipeline/cast/build.sh`; set `MELOS_BLEND`, `UAL_GLB`, `BPY_PYTHON` and `CAST_QA_DIR` (see the script for their meanings and the fixed input hashes). Blender is bpy 5.2, and MPFB and the animation library use the existing pinned versions and sources. The input models live in the project's shared materials at `frontend/spikes/a0-melos/mac/` and do not go into Git.

`assets/pipeline/cast/build.sh` で完全に再構築する。`MELOS_BLEND`、`UAL_GLB`、`BPY_PYTHON`、`CAST_QA_DIR` を設定する（意味と固定の入力の hash はスクリプトを参照）。Blender は bpy 5.2 で、MPFB とアニメーションライブラリは既存の固定バージョンとソースを使う。入力モデルはプロジェクトの共有資料の `frontend/spikes/a0-melos/mac/` にあり、Git には入れない。

The final source files and uncompressed intermediates are kept locally in `~/.zoujin/qa/h1-cast/release-source/`; the runtime assets are in `assets/cast/build/`. `cast.json` stores each tier's bytes, triangles, animations and SHA-256. After the rebuild finishes, run:

最終的なソースファイルと圧縮前の中間ファイルはローカルの `~/.zoujin/qa/h1-cast/release-source/` に保存し、実行時のアセットは `assets/cast/build/` にある。`cast.json` は各段階のバイト数、三角形、アニメーション、SHA-256 を記録する。再構築が終わったら次を実行する：

```sh
node assets/pipeline/cast/check_cast.mjs assets/cast/build assets/cast/cast.json --require-all
CAST_QA_BROWSER_DIR="$HOME/.zoujin/qa/h1-cast/release-browser" node assets/pipeline/cast/qa_browser.mjs
```

The browser check only starts a loopback server with a random password, actually decodes the compressed GLBs, and captures for each set the front, the back, two walking phases, walking at a front diagonal, the walking LOD from behind, and high-tier dialogue. It does not upload assets or screenshots. Static-angle checks are not the same as frame-by-frame cloth simulation or real-device frame-rate verification.

ブラウザのチェックはランダムなパスワード付きのループバックのサーバーだけを起動し、圧縮された GLB を実際にデコードして、各セットの正面、背面、歩行の 2 つの位相、斜め前方の歩行、歩行 LOD の背面、高品質の会話を撮影する。アセットやスクリーンショットはアップロードしない。静的な角度のチェックは、フレームごとの布のシミュレーションや実機でのフレームレートの検証と同じではない。

Final check: 17 sets, 68 GLBs, 119 fresh browser screenshots; all source files kept. Reading the GLB accessors independently to check triangle counts, default expression weights, SHA-256 and the web dist bytes found everything consistent. Non-runtime files in the web character directory: 0. Maximums: walking 8000 triangles / 310172 bytes, normal dialogue 26612 / 2155508, high-tier dialogue 39989 / 2559724, animations 246284 bytes; all within the existing budgets. The evidence is recorded locally in `release-verification.json` and not uploaded.

最終チェック：17 セット、68 個の GLB、ブラウザの新しいスクリーンショット 119 枚。ソースファイルはすべて残している。GLB の accessor を独立して読み、三角形の数、デフォルトの表情のウェイト、SHA-256、ウェブの dist のバイト数を照合し、すべて一致した。ウェブの登場人物ディレクトリにある実行時以外のファイルは 0。最大値：歩行 8000 三角形 / 310172 バイト、通常の会話 26612 / 2155508、高品質の会話 39989 / 2559724、アニメーション 246284 バイト。いずれも既存の予算内。証拠はローカルの `release-verification.json` に記録し、アップロードしない。

## Cross-review / クロスレビュー

The frontend's independent review found and asked us to fix: wrong bridging caused by the ordering of clothing boundary loops, inconsistent triangle winding, crowd representatives moving as the player approached, and overlap with the F-4 crowds. The overall coordinator's visual review asked us to fix the traveler's cloak unfolding into rigid sheets, hair poking through the hat crown, and the back hem not matching the leg binding. After the fixes, the whole set was rebuilt together; mid-way screenshots or the old model manifest must not pass for the final result.

フロントエンドの独立したレビューで見つかり修正を求められたもの：衣服の境界ループの並び順による誤ったブリッジ、三角形の巻き順の不一致、プレイヤーが近づくと群衆の代表が位置を変えること、F-4 の群衆との重なり。全体の調整役による画面のレビューでは、旅人のマントが硬い板状に広がること、帽子の頂部から髪がはみ出ること、後ろの裾と脚のバインドが合っていないことの修正を求められた。修正後にまとめて全セットを再構築した。途中のスクリーンショットや古いモデルの一覧を最終結果と偽ってはならない。
