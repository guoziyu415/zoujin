# Asset pipeline for the Syracuse plaza (F-2) / シラクサ広場のアセットパイプライン（F-2）

Moved over from the S7 realism prototype (`spikes/frontend/s7-realism/`); generates all scene resources for `scene.syracuse-square`. One command:

S7 のリアル版プロトタイプ（`spikes/frontend/s7-realism/`）から移したもので、`scene.syracuse-square` のシーンリソースをすべて生成する。コマンドは 1 つ：

```bash
BPY_PYTHON=<Python 3.13 with bpy 5.2, numpy, pillow installed / bpy 5.2、numpy、pillow を入れた Python 3.13> pnpm assets:plaza          # full quality, about 30-40 minutes on 4 cores / 本番品質、4 コアで約 30〜40 分
BPY_PYTHON=... bash assets/pipeline/plaza/build.sh draft /tmp/plaza               # draft quality, used by CI / ドラフト品質（CI で使用）
```

Python dependencies: direct dependencies are in `requirements.in`; `requirements.txt` is the version with indirect dependencies too, locked with hashes (`uv venv --python 3.13 && uv pip install -r requirements.txt`; after changing `requirements.in`, regenerate with the command on its second line). Node dependencies are in `assets/pipeline/package.json`. Generation itself needs no network and costs nothing.

Python 依存関係：直接の依存関係は `requirements.in` に書き、`requirements.txt` は間接依存も含めて hash 付きで固定したバージョン（`uv venv --python 3.13 && uv pip install -r requirements.txt`。`requirements.in` を変更したら、その 2 行目のコマンドで再生成する）。Node の依存関係は `assets/pipeline/package.json` にある。生成そのものにネットワークは不要で、費用もかからない。

## Steps / ステップ

| Step / ステップ | Script / スクリプト | What it does / 内容 |
| --- | --- | --- |
| Textures / テクスチャ | `placeholder_tex.py` | Color, normal, and roughness maps for each material. If the `PLAZA_SCANS` directory has scanned materials they are used; otherwise placeholders are generated from a fixed seed (colors per UX art-direction 4.2). Sources are recorded in `tex/sources.json`. / 各マテリアルの色、法線、粗さのマップ。`PLAZA_SCANS` ディレクトリにスキャンしたマテリアルがあればそれを使い、なければ固定シードでプレースホルダーを生成する（色は UX art-direction 4.2 に従う）。出所は `tex/sources.json` に記録する。 |
| Scene / シーン | `build_plaza.py` | Lays out the plaza in Blender per art-direction 4.1: the gate street faces 294°, the royal castle and tower are to the east, the temple to the north; an empty corridor of light runs from the gate to the pillar (the fountain is north of it); the pillar stands on the stake platform; stalls, the old man's house (south S2, door facing the plaza), and the stonemason's yard in the southwest corner (`place.stonemason-workshop`). The yard gate is a separate node, so the page can close it. / Blender で art-direction 4.1 に従って広場を配置する：城門通りは 294° を向き、王城と塔は東、神殿は北。城門から柱まで光の空き回廊を 1 本残す（噴水はその北）。柱は磔台の上に立つ。屋台、老人の家（南の S2、扉は広場向き）、南西の角の石工の庭（`place.stonemason-workshop`）。庭の門は独立したノードで、ページ側から閉められる。 |
| Sky / 空 | `sky.py` | Blender's physical sky; baking and the page use the same sun formula (`sunpos.py`: latitude 37°N, declination +19°, solar noon 12:00). / Blender の物理ベースの空。ベイクとページは同じ太陽の式を使う（`sunpos.py`：北緯 37°、赤緯 +19°、正午 12:00）。 |
| Baking / ベイク | `bake.py` | Lightmaps for ground and buildings: occlusion, direct sun, total lighting, for one time slot at 18:30. / 地面と建物のライトマップ：遮蔽、太陽の直射、全光照を、18:30 の 1 時間帯分。 |
| Encoding / エンコード | `encode.py` | Float lightmaps → 8-bit PNG (indirect light = total − direct), recording the brightness factor K. / 浮動小数点のライトマップ → 8 ビット PNG（間接光 = 全光照 − 直射）。輝度係数 K を記録する。 |
| Packing / パック | `pack_scene.mjs` | Geometry (meshopt), two tiers of KTX2 textures, KTX2 lightmaps, the nav mesh (`nav.mjs`, recast), and writes `scene.json`. / ジオメトリ（meshopt）、2 ティアの KTX2 テクスチャ、KTX2 ライトマップ、ナビメッシュ（`nav.mjs`、recast）をパックし、`scene.json` を書く。 |
| Checks / 検査 | `check_scene.mjs` | Download budget, texture VRAM, average color of both tiers, `scene.json` consistent with `layout.json`, and consistent with the world models that use this scene (places, `sceneRef`, exit adjacency). In CI the node workflow checks the manifest in the repo (no generation; also runs when `world.json` changes), and the assets workflow checks the freshly generated one. / ダウンロード予算、テクスチャの VRAM、2 ティアの平均色、`scene.json` と `layout.json` の一致、このシーンを使う世界モデルとの一致（地点、`sceneRef`、出口の隣接）。CI では node ワークフローがリポジトリ内のマニフェストを検査し（生成はしない。`world.json` が変わったときも実行）、assets ワークフローがその場で生成したものを検査する。 |

There is also `preview.py`: renders a few Cycles preview images from `plaza_raw.blend` for viewing, not part of the pipeline.

ほかに `preview.py` がある：`plaza_raw.blend` から Cycles のプレビュー画像を数枚レンダリングして見るもので、パイプラインには含まれない。

## Output (`assets/scenes/syracuse-square/`) / 出力（`assets/scenes/syracuse-square/`）

- `layout.json` (handwritten): walkable areas, place boundaries, location points (api-contract's `spot`), the starting point of each place (`startSpots`), exits. Plane coordinates, the same system as `build_plaza.py`.
  `layout.json`（手書き）：歩ける領域、地点の境界、位置点（api-contract の `spot`）、各地点の開始位置（`startSpots`）、出口。平面座標で、`build_plaza.py` と同じ体系。
- `scene.json` (generated, in the repo): everything the page needs, with coordinates converted to glTF (meters, +Y up). Each `spots` entry has `pos`, `yaw` (rotation about +Y turning the model's +Z toward the facing direction), and `place`; those used only for designated positions also get `auto: false`; `startSpots` is the starting point of each place: a role that opens in this place stands there. When a character has no `spot` written, they stand at the first free location point in this place's order in `layout.json`, except `way.*` and `auto: false` ones; a spot where the player stands counts as taken; characters with `group: true` (crowds, officers and the like) do not occupy location points. `playerStartSpot` is the starting point of the default place, and is also the first screen. `files` lists each file's size and sha256, and `pack` is `entry` (entry pack, downloaded before walking is possible) or `hi` (high tier, downloaded in the background). `inputs` records which inputs the manifest was generated from: sha256 of `layout.json` and each script, the source of each texture (scanned maps carry sha256), tool versions, and environment variables the scripts read.
  `scene.json`（生成物、リポジトリに入れる）：ページが必要とする情報すべて。座標は glTF（メートル、+Y が上）に換算済み。`spots` の各項目には `pos`、`yaw`（+Y 軸まわりにモデルの +Z を向きの方向へ回す）、`place` があり、演出で指定された立ち位置専用のものには `auto: false` が付く。`startSpots` は各地点の開始位置で、この地点で開局する身分はそこに立つ。人物に `spot` が書かれていない場合は、`layout.json` にあるこの地点の位置点の順で最初の空いているところに立つ（`way.*` と `auto: false` は除く）。プレイヤーが立っている位置は占有済みとして数え、`group: true` の人物（群衆、役人など）は位置点を占有しない。`playerStartSpot` は既定の地点の開始位置であり、最初の画面でもある。`files` は各ファイルのサイズと sha256 を列挙し、`pack` は `entry`（入場パック、歩けるようになる前にダウンロード完了）か `hi`（高ティア、バックグラウンドでダウンロード）。`inputs` はこのマニフェストがどの入力から生成されたかを記録する：`layout.json` と各スクリプトの sha256、各テクスチャの出所（スキャン画像は sha256 付き）、ツールのバージョン、スクリプトが読む環境変数。
- `build/` (generated, not in the repo for now, see below): `geo.glb`, `nav.json`, `tex/std/`, `tex/hi/`, `lm/`.
  `build/`（生成物、当面リポジトリには入れない。下記参照）：`geo.glb`、`nav.json`、`tex/std/`、`tex/hi/`、`lm/`。

Places and exits:

地点と出口：

| Place / exit / 地点・出口 | Where / 場所 |
| --- | --- |
| `place.syracuse-square` | Default: the plaza, the gate street, the temple porch; starting point `plaza-southwest` / 既定：広場、城門通り、神殿の前廊。開始位置は `plaza-southwest` |
| `place.stonemason-workshop` | The yard in the southwest corner; the door in the north wall is the only entrance; starting point `workshop-yard` / 南西の角の庭。北の壁の扉が唯一の入口。開始位置は `workshop-yard` |
| `place.execution-ground` | The stake platform, pillar, and steps before the royal castle gate, plus the stretch of light corridor in front of the platform (where the crowd stands with their backs to the gate, facing the pillar); the two western corners are cut off, and the fountain and `plaza-east` stay in the plaza (S-050: the same plaza becomes the execution ground on the third day); starting point `stake-front` / 王城の門前の磔台、柱、階段に、磔台の前の光の回廊の一区間（群衆が城門に背を向けて柱の方を向いて立つ場所）を加えたもの。西の 2 つの角は切り落とし、噴水と `plaza-east` は広場に残す（S-050：同じ広場が 3 日目に刑場になる）。開始位置は `stake-front` |
| Exit `place.road-to-city` | Location point `way.road-to-city`, outside the city gate / 位置点 `way.road-to-city`、城門の外 |
| Exit `place.castle` | Location point `way.castle`, the gate at the top of the steps / 位置点 `way.castle`、階段の上の城門 |

There are 38 location points, with names and descriptions in `layout.json`. Two are on the stake platform: `stake` (the person hung up with their back to the pillar) and `scaffold` (where one climbs onto the platform and can reach his feet); `old-man-house` is in front of the old man's house door. Five are designated for staging only (`auto: false`): `stake`, `scaffold`, `king-west` (the west end of the execution ground, behind the crowd, where the king stands first), `stake-front-side` (beside `stake-front`; where the old man stands when the player stands at `stake-front`), and `crowd-front` (front row of the crowd, northwest corner of the platform, the girl holding the cloak). Location points leading to other scenes are named `way.<place>`, not `exit.` (that is the world model `ExitId`, the destinations at the end of the story). Backend and Data use only these names in `characters[].spot` and `player.spot`; to add a new location point, change `layout.json` and regenerate.

位置点は 38 個あり、名前と説明は `layout.json` にある。磔台の上には 2 つある：`stake`（柱を背に吊り上げられた人）と `scaffold`（台に登って彼の足に手が届く場所）。`old-man-house` は老人の家の扉の前。演出のみの指定（`auto: false`）が 5 つある：`stake`、`scaffold`、`king-west`（刑場の西端、群衆の後ろ。王が最初に立つ場所）、`stake-front-side`（`stake-front` の隣。プレイヤーが `stake-front` に立つとき老人が立つ場所）、`crowd-front`（群衆の最前列、磔台の北西の角。マントを持つ少女）。他のシーンに通じる位置点は `way.<地点>` と名付け、`exit.` は使わない（それは世界モデルの `ExitId` で、幕末の行き先）。バックエンドとデータは `characters[].spot` と `player.spot` でこれらの名前だけを使う。新しい位置点を追加するときは `layout.json` を変更して再生成する。

## Two texture tiers (frontend-design 10.6.2, art-direction 9.3) / 2 ティアのテクスチャ（frontend-design 10.6.2、art-direction 9.3）

- Standard tier: color 1024 (ETC1S), normal and roughness 512 (normal UASTC).
  標準ティア：色 1024（ETC1S）、法線と粗さ 512（法線は UASTC）。
- The high tier is downloaded separately: color 2048 and normal 1024 for the flagstone ground, royal castle cut-stone walls, ordinary stone (steps), plaster walls, doors and shutters, and clay tiles.
  高ティアは別途ダウンロード：石畳の地面、王城の切り石の壁、普通の石材（階段）、漆喰の壁、扉と鎧戸、陶製の瓦の色は 2048、法線は 1024。
- Both tiers are downscaled from the same source image; `check_scene.mjs` decodes both tiers (using the same Basis transcoder as phones) and fails if the average color difference exceeds 3/255.
  2 ティアとも同じ元画像から縮小する。`check_scene.mjs` は両ティアをデコードし（スマートフォンと同じ Basis トランスコーダーを使う）、平均色の差が 3/255 を超えると失敗する。

## Navigation mesh / ナビゲーションメッシュ

recast runs only at generation time (WASM); the page uses `nav.json` to do its own A* and path straightening (frontend-design 8.6, 9.4). Only the part inside the walkable area in `layout.json` and connected to the player's starting point is kept; each polygon is tagged with its place, and when `places[].enabled = false` the page removes that place's polygons from pathfinding. Heights are snapped to the real ground; steps are slopes in the detail mesh, and location points themselves stand on the steps.

recast は生成時にだけ実行され（WASM）、ページは `nav.json` を使って自前で A* と経路の直線化を行う（frontend-design 8.6、9.4）。`layout.json` の歩ける領域の内側で、プレイヤーの開始位置とつながっている部分だけを残す。各ポリゴンには地点が付けられ、`places[].enabled = false` のときページはその地点のポリゴンを経路探索から外す。高さは実際の地面に合わせてあり、階段は詳細メッシュでは斜面になっていて、位置点そのものは階段の上に立つ。

## Generated output stays out of the repo; only the manifest goes in (PM decision 2026-10-10) / 生成物はリポジトリに入れずマニフェストだけを置く（PM 決定 2026-10-10）

When the project container pushes Git LFS, `lfs.github.com` is blocked by network policy (upload to storage succeeds, but the confirmation step is rejected, so the object does not count). Therefore `build/` is not in the repo; the repo has only the `scene.json` manifest; page development, CI, and later deployment builds all generate on the spot. Three conditions:

プロジェクトコンテナが Git LFS にプッシュするとき、`lfs.github.com` がネットワークポリシーでブロックされる（ストレージへのアップロードは成功するが、確認のステップが拒否され、オブジェクトは有効にならない）。そのため `build/` はリポジトリに入れず、リポジトリには `scene.json` マニフェストだけを置く。ページ開発、CI、今後のデプロイビルドはすべてその場で生成する。条件は 3 つ：

1. **Reproducible**. Inputs come only from files in the repo, or downloads with a pinned version and sha256; downloaded materials get their source and license (CC0, etc.) written in `assets/manifest/`. Generating twice from the same input must give the same sha256 values in the manifest (CI checks this when the pipeline or scene changes; see "Reproducibility" below).
   **再現できること**。入力はリポジトリ内のファイル、またはバージョン固定で sha256 付きのダウンロードだけから得る。ダウンロードした素材は `assets/manifest/` に出所とライセンス（CC0 など）を書く。同じ入力から 2 回生成したとき、マニフェストの sha256 は一致しなければならない（パイプラインかシーンを変更したときに CI が検査する。下の「再現性」を参照）。
2. **CI generates on the spot only when the pipeline or scene changed** (`paths` in `.github/workflows/assets.yml`). Record the duration of each run in the PR description; PM reconciles Actions minutes when M2-0 ends.
   **CI はパイプラインかシーンを変更したときだけその場で生成する**（`.github/workflows/assets.yml` の `paths`）。毎回の所要時間は PR の説明に書き、M2-0 の終了時に PM が Actions の分数を突き合わせる。
3. **Keep the LFS rules in `.gitattributes`**. If some thread mistakenly adds `.glb` or `.ktx2`, the push fails at the LFS step if git-lfs is installed; if not installed, they enter git as ordinary files, and CI's `check_large_files.py` goes red (files that match the LFS rules but entered git as something other than an LFS pointer).
   **`.gitattributes` の LFS ルールは残す**。どのスレッドかが誤って `.glb` や `.ktx2` を追加した場合、git-lfs が入っていれば push は LFS のステップで失敗する。入っていなければ通常のファイルとして git に入り、そのとき CI の `check_large_files.py` が赤になる（LFS ルールに一致するのに、git に入ったのが LFS ポインタではない）。

On deployment, use the `scene.json` and files from the same generation; do not pair the manifest in the repo with files generated on the spot: on a different machine the sha256 values will not match.

デプロイ時は同じ生成の `scene.json` とファイルを使うこと。リポジトリ内のマニフェストをその場で生成したファイルと組み合わせてはならない。マシンが変わると sha256 が一致しなくなる。

## Reproducibility / 再現性

When the pipeline or scene changes (`paths` in `assets.yml`), CI generates the draft tier from scratch twice in two different directories and compares the two `scene.json` files (which hold the sha256 of every file) with `cmp`; a mismatch turns it red. This also proves incidentally that the output carries no local paths.

パイプラインかシーンを変更したとき（`assets.yml` の `paths`）、CI は 2 つの異なるディレクトリでドラフト品質をゼロから 2 回生成し、2 つの `scene.json`（全ファイルの sha256 を含む）を `cmp` で比較する。一致しなければ赤になる。これにより、出力にローカルのパスが含まれていないことも併せて証明される。

- Placeholder textures are generated from a fixed seed; Cycles bakes on the CPU with a fixed seed and sample count, so the two lightmaps match.
  プレースホルダーのテクスチャは固定シードで生成する。Cycles は固定のシードとサンプル数で CPU 上でベイクするので、2 回のライトマップは一致する。
- Blender's glTF exporter does not necessarily give the same triangle order every time (encountered with the distant cypress block). So `pack_scene.mjs` sorts the triangles of each block before packing (without changing winding), after which the meshopt output is consistent.
  Blender の glTF エクスポーターは、三角形の順序が毎回同じとは限らない（遠景の糸杉のブロックで発生した）。そのため `pack_scene.mjs` はパックの前に各ブロックの三角形を並べ替える（巻き方向は変えない）。その後の meshopt 圧縮の出力は一致する。
- Consistent on the same machine, not guaranteed across CPUs: floating-point results from Cycles and Basis encoding can differ slightly, and the sha256 values change with them. So the manifest in the repo is not compared by sha256 with CI-generated files; only budgets, both tiers' colors, and layout are checked, then `inputs` are compared: if the draft tier generated by CI and the manifest in the repo came from the same inputs (`layout.json`, scripts, texture sources, tool versions, environment variables), they match; a difference means the pipeline or layout was changed without rerunning the full-quality tier. When checking only the manifest (`node.yml`, a few seconds), it also first compares `inputs.files` with the files now in the repo, and if a script or the layout changed it reports stale immediately without waiting for generation. Dependency versions are locked in `requirements.txt` (with hashes) and `pnpm-lock.yaml`.
  同じマシンでは一致するが、CPU が変わると保証されない：Cycles と Basis エンコードの浮動小数点の結果は少し異なる場合があり、sha256 もそれに伴って変わる。そのためリポジトリ内のマニフェストは CI が生成したファイルと sha256 では比較せず、予算、2 ティアの色、レイアウトだけを検査したうえで `inputs` を比較する：CI が生成したドラフト品質とリポジトリ内のマニフェストが同じ入力（`layout.json`、スクリプト、テクスチャの出所、ツールのバージョン、環境変数）から来ていれば一致し、異なればパイプラインかレイアウトを変更したのに本番品質を再実行していないことを意味する。マニフェストだけを検査する場合（`node.yml`、数秒）も、まず `inputs.files` をリポジトリ内の現在のファイルと比べ、スクリプトかレイアウトが変わっていれば生成を待たずにただちに古いと報告する。依存関係のバージョンは `requirements.txt`（hash 付き）と `pnpm-lock.yaml` で固定する。

## Current limitations / 現在の制限

- **Textures are placeholders**: the container cannot reach Poly Haven or ambientCG. CC0 scanned materials must be downloaded from somewhere that can reach those sites (zg's Mac, with zg's approval), with sources and sha256 recorded in `assets/manifest/`, then regenerate pointing to them with `PLAZA_SCANS`. Final materials also wait for UX's material list.
  **テクスチャはプレースホルダー**：コンテナは Poly Haven や ambientCG にアクセスできない。CC0 のスキャンマテリアルはそれらのサイトにアクセスできる場所（zg の Mac。zg の同意が必要）でダウンロードし、`assets/manifest/` に出所と sha256 を記録して、`PLAZA_SCANS` で指して再生成する。正式なマテリアルも UX のマテリアルリストを待つ。
- Only the sunset time slot has lightmaps; buildings are procedurally generated blocks; the two small alleys to the south are visible but cannot be entered (outside the walkable area).
  ライトマップは日没の 1 時間帯だけ。建物は手続き的に生成したブロック。南の 2 本の小道は見えるが入れない（歩ける領域の外）。
- Lightmap seams and resolution are not polished (the card explicitly says not to).
  ライトマップの継ぎ目と解像度は仕上げていない（カードに「やらない」と明記されている）。

## H-1 Stonemason's workshop spot top-up / H-1 石工房の立ち位置の追加

The stonemason's workshop now has 10 automatic spots, enough for the current 9 non-group characters and the player to be present at once. The old spots and the staging-only points are unchanged; the 8 newly added points are on flat ground of the existing nav mesh, at least 1.2 meters from each other and from the old points.

石工房には自動の立ち位置が 10 個あり、現在の非群衆の人物 9 人とプレイヤーが同時にいるのに十分。古い立ち位置と演出専用の点は変わらない。新しく加えた 8 点は既存のナビメッシュの平地にあり、互いにも古い点とも少なくとも 1.2 メートル離れている。

`refresh_spots.mjs` can be used only when adding flat-ground spots; its inputs are the old layout, the new layout, a `nav.json` whose SHA matches the manifest, and the `scene.json` to update. The script verifies that the layout is unchanged except for the new spots, that all build script hashes are unchanged, and that place assignment and heights are correct; geometry, texture, bake, and nav file bytes are untouched, and the manifest only gains the spots and updates the layout input hash. Changing terrain, existing spots, slopes, or steps still requires a full build. When repackaging for deployment, the updated manifest must be used; do not just replace the server-side layout or reuse the old scene.json.

`refresh_spots.mjs` は平地の立ち位置を追加するときだけ使える。入力は古いレイアウト、新しいレイアウト、マニフェストの SHA と一致する `nav.json`、更新対象の `scene.json`。スクリプトは、新規の立ち位置以外のレイアウトが変わっていないこと、すべてのビルドスクリプトの hash が変わっていないこと、地点への帰属と高さが正しいことを検証する。ジオメトリ、テクスチャ、ベイク、nav ファイルのバイト列は変更せず、マニフェストには立ち位置の追加とレイアウトの入力 hash の更新だけを行う。地形、既存の立ち位置、斜面、階段を変更する場合は、引き続き完全なビルドが必要。デプロイのために再パックするときは更新後のマニフェストを使わなければならず、サーバー側の layout だけを差し替えたり、古い scene.json を再利用したりしてはならない。
