# Village pipeline (F-11) / 村のパイプライン（F-11）

Follows the approach of the road (`../road/README.md`, `../plaza/README.md`: only the manifest goes into the repo, assets are generated on site, and two generations are byte-for-byte identical). The plaza's sky, bake, encode, pack and check scripts are called directly and switch scenes via environment variables; the Blender helpers, placeholder textures and the key table of the roadside shared pack are in `../common/`, shared with the road.

道（`../road/README.md`、`../plaza/README.md`）のやり方に倣う：マニフェストだけをリポジトリに入れ、現場で生成し、2 回の生成はバイト単位で一致する。広場の空、ベイク、エンコード、パック、チェックのスクリプトは直接呼び出し、環境変数でシーンを切り替える。Blender の補助ツール、プレースホルダーテクスチャ、道端共有パックのキー表は `../common/` にあり、道と共有する。

```
assets/pipeline/village/build.sh [final|draft] [out_dir]
```

One command produces: / 1 つのコマンドで次を出力する：

- `village` (`scene.village`, the shepherd's first screen): all geometry outside the houses, navigation (including the floor inside the houses), and the sunny-daytime lighting set (day 1, 10:00, sun at 116°, 58° high). The first entry into the scene downloads only this pack and the `road-common` files it uses.
  `village`（`scene.village`、牧童の最初の画面）：家の外のすべてのジオメトリ、ナビゲーション（家の中の床を含む）、晴れた昼の光一式（一日目 10:00、太陽 116°、高度 58°）。最初の入場ではこのパックと、それが使う `road-common` ファイルだけをダウンロードする。
- `road-common`: the roadside keys the village uses (dirt road, hay, outcrop, bark, poplar, holm oak, distant mountains, wheat) moved into the shared pack (`../common/roadside.mjs`), the same bytes as the river's; the wheat was added by the village.
  `road-common`：村が使う道端のキー（土の道、干し草、露頭、樹皮、ポプラ、ホルムオーク、遠山、麦）を共有パック（`../common/roadside.mjs`）に移したもの。川と同じバイト列。麦は村で追加された。

| Variable / 変数 | Village / 村 |
| -------------------- | --------------------- |
| `SCENE_STEM` | `village` |
| `SCENE_ROT_DEG` | 0 |
| `SCENE_MINUS_X_AZ` | 270 (+x faces east) / 270（+x が東向き） |
| `PLAZA_BAKE_MINUTE` | 600 (10:00) |
| `BAKE_SUN_E`, `_RGB` | 6, color of the sun at 58° elevation / 6、高度 58° の太陽の色 |
| `BAKE_RES` | 1024 |

Steps: textures (`../common/road_tex.py`) → scene (`build_village.py`) → sky → bake → **instancing** (`merge_inst.mjs`) → encode → pack → re-encode leaf textures at small size → move shared textures → 18:30 sky → **re-bake** (`relight.py`: sunset, night, rain) → **light sub-packs** (`pack_sub.mjs`) → check (`../plaza/check_scene.mjs`, then `check_village.mjs`: shared files, draw calls, instanced nodes).

手順：テクスチャ（`../common/road_tex.py`）→ シーン（`build_village.py`）→ 空 → ベイク → **インスタンス化**（`merge_inst.mjs`）→ エンコード → パック → 葉テクスチャを小サイズで再エンコード → 共有テクスチャを移動 → 18:30 の空 → **再ベイク**（`relight.py`：日没、夜、雨）→ **光のサブパック**（`pack_sub.mjs`）→ チェック（`../plaza/check_scene.mjs`、続けて `check_village.mjs`：共有ファイル、draw call、インスタンス化ノード）。

**Instancing** (card item 3): wheat, wheat sheaves, grapevines and sheep each get one draw call. `build_village.py` exports each thing's prototype as `<stem>_proto.glb` (each at the origin), and writes each copy's position, orientation and size into `<stem>_inst.json`; during baking the copies stand in the `inst` collection as linked duplicates and serve only as occluders (the ground gets their shadows and occlusion) and are not baked themselves. After baking, `merge_inst.mjs` adds the prototypes to `<stem>_raw.glb`, one node per kind carrying `EXT_mesh_gpu_instancing` (recognized by three.js's GLTFLoader as an `InstancedMesh`); each copy gets a slight color variation by hash (`_COLOR_0`), and the same input produces the same bytes.

**インスタンス化**（カード第 3 項）：麦、麦束、ブドウの蔓、羊は、それぞれ 1 つの draw call にする。`build_village.py` は各オブジェクトの原型を `<stem>_proto.glb`（それぞれ原点に配置）として書き出し、各コピーの位置、向き、大きさを `<stem>_inst.json` に書く。ベイク時、コピーはリンク複製として `inst` コレクションに置かれ、遮蔽としてのみ機能し（地面にその影と遮蔽が落ちる）、自身はベイクしない。`merge_inst.mjs` はベイクの後で原型を `<stem>_raw.glb` に追加する。種類ごとに `EXT_mesh_gpu_instancing` を持つノード 1 つ（three.js の GLTFLoader が `InstancedMesh` として認識する）で、各コピーにはハッシュで少しの色の変化（`_COLOR_0`）を与える。同じ入力からは同じバイト列が出る。

**Light sub-packs** (card item 1): after the village is baked, `relight.py` opens the baked `<stem>_baked.blend` (the lightmap UVs are already fixed), changes the light and bakes `ground` and `arch` again, and `pack_sub.mjs` packs them. The manifest is called `pack.json` (the backend reads `assets/scenes/*/scene.json` as the layout) and sits next to the village directory:

**光のサブパック**（カード第 1 項）：村のベイク後、`relight.py` がベイク済みの `<stem>_baked.blend`（ライトマップの UV は確定済み）を開き、光を変えて `ground` と `arch` をもう一度ベイクし、`pack_sub.mjs` がパックする。マニフェストは `pack.json` と呼び（バックエンドは `assets/scenes/*/scene.json` をレイアウトとして読む）、村のディレクトリの隣に置く：

| Sub-pack / サブパック | Light / 光 | Limit / 上限 |
| ---------------------- | ---------------------------------------------------------------------- | ---- |
| `village-light-sunset` | 18:30, the plaza's `sky.py` paints the 18:30 sky, sun at 6, warm color / 18:30、広場の `sky.py` が 18:30 の空を描く、太陽 6、暖色 | 2 MB |
| `village-light-night` | Starry sky (uniform dark-blue skylight), with an oil lamp under the bridegroom's house's grape arbor baked in / 星空（均一な暗い青の天空光）、花婿の家のブドウ棚の下の油灯を 1 つベイクに含める | 2 MB |
| `village-light-rain` | Overcast sky of a downpour (CIE overcast skylight distribution, no sun); rainy night and day-3 twilight are dimmed by the page / 豪雨の曇天（CIE 曇天の天空光分布、太陽なし）。雨の夜と三日目の薄明はページ側で暗くする | 2 MB |

- Only indirect light is carried (full light minus the sun's direct light; the lamp's direct light stays in), AO comes from the village pack, and the sun is still drawn in real time. The positions of the sky, sun and lamp are written into the manifest, and the page places dynamic lights accordingly.
  間接光のみを持つ（全光から太陽の直射を引いたもの。灯の直射は残す）。AO は村のパックのものを使い、太陽は従来どおりリアルタイムで描く。空、太陽、灯の位置はマニフェストに書き、ページがそれに従って動的ライトを置く。
- Re-baking is fixed to a single CPU thread; multithreaded Cycles produces run-to-run differences in the small amount of indirect-light sampling on buildings at sunset, which would change the compressed files and the manifest. Resolution, sample count, lights and budget stay at the original standard, and the dual build must still be byte-for-byte identical.
  再ベイクは CPU スレッド 1 つに固定する。Cycles のマルチスレッドは、日没時の建物の少量の間接光サンプリングで実行ごとの差異を生み、圧縮後のファイルとマニフェストを変えてしまう。解像度、サンプル数、ライト、予算は元の基準を維持し、二重ビルドは引き続きバイト単位の一致を要求する。
- The indoor sub-pack `village-interior` has its own pipeline (`interior/build.sh`).
  屋内のサブパック `village-interior` は独自のパイプライン（`interior/build.sh`）を持つ。
- `village/scene.json` gains `subPacks` (all sub-packs; the indoor one follows the `pack.json` it has in the repo), `subPackBytes`, and `lightSets` copied from the layout (which light set to use outdoors and indoors for each time period, interpolated by time of day between the two sets; after the weather turns, rain and banquet are used).
  `village/scene.json` に `subPacks`（全サブパック。屋内のものはリポジトリ内の `pack.json` に従う）、`subPackBytes`、およびレイアウトから写した `lightSets`（各時間帯に屋外と屋内で使う光のセット。2 つのセットの間は時刻で補間する。天気が崩れた後は雨と宴席を使う）が加わる。
- `check_village.mjs` checks: the sub-packs' files and sha256, each one's limit, that lightmap sizes match the village, that the lights referenced by `lightSets` all exist, the draw calls after adding the interior, and that the whole village (standard tier, shared files used, all sub-packs) is ≤ 11 MB; the high-end tier is counted separately.
  `check_village.mjs` が検査するもの：サブパックのファイルと sha256、それぞれの上限、ライトマップのサイズが村と一致していること、`lightSets` が参照する光がすべて存在すること、屋内を加えた後の draw call、村全体（標準ティア、使用する共有ファイル、全サブパック）が ≤ 11 MB であること。ハイエンドティアは別に数える。

The textures are all placeholders for now; CC0 scans go through the first frontend thread's asset workflow and are regenerated by placing them in the `ROAD_SCANS` directory.

テクスチャは現在すべてプレースホルダー。CC0 スキャンは最初のフロントエンドスレッドのアセットフローを経由し、`ROAD_SCANS` ディレクトリに置いて再生成する。
