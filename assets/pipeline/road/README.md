# Road pipeline / 帰り道のパイプライン (F-10)

The road's stopping points are generated the same way as the plaza (`../plaza/README.md`: only the manifest goes into the repo, generated on the spot, two generations are byte-identical). The plaza's sky, bake, encode, pack, and check scripts are called directly, and the scene is switched via environment variables (the defaults are the plaza's, so plaza output is unchanged):

帰り道の滞在地点は広場と同じ方法で生成する（`../plaza/README.md`：リポジトリに入れるのは一覧だけ、その場で生成、2回の生成はバイト単位で一致）。広場の空、ベイク、エンコード、パック、検査のスクリプトを直接呼び出し、環境変数でシーンを切り替える（デフォルトは広場のものなので、広場の出力は変わらない）：

| Variable / 変数              | Meaning / 意味                                                                                                                                 | Plaza / 広場                          | River / 川                          |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- | ----------------------------------- |
| `SCENE_STEM`                 | File name in the working directory `<stem>_raw.blend` / `.glb` / 作業ディレクトリ内のファイル名 `<stem>_raw.blend` / `.glb`                    | `plaza`                               | Pack name / パック名                |
| `SCENE_ROT_DEG`              | Angle for rotating plane coordinates into glTF, matching `rotationDeg` in `layout.json` / 平面座標を glTF に回す角度。`layout.json` の `rotationDeg` と一致 | 144                                   | 0                                   |
| `SCENE_MINUS_X_AZ`           | Azimuth of plane −x / 平面 −x の方位角                                                                                                         | 294                                   | 270 (+x faces east / +x が東向き)   |
| `PLAZA_BAKE_MINUTE`          | Bake time of day / ベイクする時刻                                                                                                              | 1110 (18:30)                          | 315 / 705                           |
| `SKY_SUN_ELEV_DEG`           | Change only the sky's sun elevation, direction unchanged / 空の太陽高度だけを変える（方向は不変）                                              | —                                     | Act 2 −1.5 / 第2幕 −1.5             |
| `BAKE_SUN_E`, `BAKE_SUN_RGB` | Direct light used for baking (0 = none) / ベイクに使う直射光（0 = なし）                                                                       | 6, color at 18:30 / 6、18:30 の色     | 0 / 6, 5500 K / 0 / 6、5500 K       |
| `BAKE_RES`                   | Edge length of the final-quality lightmap / 本番品質のライトマップの一辺の長さ                                                                 | 2048                                  | 1024                                |
| `SCENE_INPUTS`               | Scripts the manifest records as this scene's own / 一覧にこのシーン固有として記録するスクリプト                                                | —                                     | Scripts in this directory / このディレクトリのスクリプト |

```
assets/pipeline/road/build.sh [final|draft] [out_dir]        # River / 川 (F-10)
assets/pipeline/road/build_rest.sh [final|draft] [out_dir]   # Pass, spring, field path, run segments / 峠、泉、野の道、ランセグメント (F-15)
```

One command produces: / 1つのコマンドで次を出力する：

- `road-river-calm` (Act 2 05:15) and `road-river-flood` (Act 4 11:45): the same `build_road_river.py`, switched by `RIVER_STATE`.
  `road-river-calm`（第2幕 05:15）と `road-river-flood`（第4幕 11:45）：同じ `build_road_river.py` を `RIVER_STATE` で切り替える。
- `road-common`: textures shared along the roadside, with the key table fixed in `../common/roadside.mjs` (dirt road, hay, outcrop, gravel, bark, poplar, holm oak, distant mountains, wheat; the village uses them too, F-11). `merge_river.mjs` calls it and moves the files for these keys out of the two packs into it; both sides must be byte-identical. Generation only adds to an existing `road-common`; a key whose bytes changed is overwritten, and the checks of other packs using it will then fail, so regenerate them. Each pack's `bytes.shared` counts only the files it uses itself. The manifest is called `pack.json`, not `scene.json` (the backend reads every `assets/scenes/*/scene.json` as a scene layout).
  `road-common`：道端で共用するテクスチャ。キー表は `../common/roadside.mjs` で固定（土の道、干し草、露頭、砕石、樹皮、ポプラ、ホルムオーク、遠山、麦。村でも使う、F-11）。`merge_river.mjs` がこれを呼び、2つのパックにあるこれらのキーのファイルをここへ移す。両側は同一のバイト列でなければならない。生成は既存の `road-common` への追加のみで、バイト列が変わったキーは上書きされ、それを使う他のパックの検査が失敗するので再生成が必要。各パックの `bytes.shared` は自分が使うファイルだけを数える。一覧は `pack.json` と呼び、`scene.json` とは呼ばない（バックエンドは `assets/scenes/*/scene.json` をすべてシーンレイアウトとして読むため）。
- `road-river/index.json`: the page picks a pack by act (the page cannot see world variables), with the corresponding value of `var.bridge` attached; `road-river/scene.json`: the `scene.road-river` layout read by the backend and `build_world` (the locations, exits, and position points of the two packs combined).
  `road-river/index.json`：ページが幕ごとにパックを選ぶ（ページはワールド変数を取得できない）。`var.bridge` の対応する値を付ける。`road-river/scene.json`：バックエンドと `build_world` が読む `scene.road-river` レイアウト（2つのパックの地点、出口、位置点を合わせたもの）。

Checks: each pack runs `../plaza/check_scene.mjs` (budget taken from `scenes.<pack name>` in `assets/budgets.json`), then `check_road.mjs` (shared pack, draw calls, indices and the combined layout, and that every act in the world model that has this scene can pick exactly one pack).

検査：各パックで `../plaza/check_scene.mjs`（予算は `assets/budgets.json` の `scenes.<パック名>` から取る）を実行し、続けて `check_road.mjs`（共用パック、draw call、インデックスと合成レイアウト、ワールドモデルでこのシーンを持つ各幕がちょうど1つのパックを選べること）を実行する。

`preview_river.py` is a Cycles preview for development and is not part of the build.

`preview_river.py` は開発用の Cycles プレビューで、ビルドには含まれない。

All textures are placeholders for now (`../common/road_tex.py` generates them from a fixed seed, shared by the road and the village; the Blender helper `../common/bl.py` and the small-size re-encoding of leaf textures `../common/small_tex.mjs` are also there); CC0 scans are downloaded on zg's Mac, go through the first frontend thread's asset workflow, and are placed in the `ROAD_SCANS` directory before regenerating.

テクスチャは現在すべてプレースホルダー（`../common/road_tex.py` が固定シードで生成し、道と村で共用。Blender の小道具 `../common/bl.py` と、葉のテクスチャの小サイズ再エンコード `../common/small_tex.mjs` もそこにある）。CC0 スキャンは zg の Mac でダウンロードし、最初のフロントエンドスレッドの資産フローを経て、`ROAD_SCANS` ディレクトリに置いて再生成する。

The remaining items (F-15): `build_rest.sh` generates the pass `road-pass-day`, spring `road-spring-day`, field path `road-field-day` (run segment), and run segments `road-run-r1`, `-r2`, `-r2s`, `-r3`, `road-run-night` (the Act 2 night road, standing in for three places). Scene scripts are `build_road_pass.py`, `build_road_spring.py`, `build_road_run.py` (sharing `roadkit.py`); the new textures are in `rest_tex.py`; the merge is `merge_rest.mjs` (writes `index.json` and `scene.json` for `road-pass`, `road-spring`, and `road-field`); the check is `check_rest.mjs`; the committed manifest is `check_committed.sh`. The run segment's `layout.runway` (a 36 m stretch of road surface that loops, with set pieces appearing by time of day) is copied into the pack's `scene.json`, and the page plays it like a treadmill in `apps/web/src/three/road/runway.ts`.

その他（F-15）：`build_rest.sh` は、峠 `road-pass-day`、泉 `road-spring-day`、野の道 `road-field-day`（ランセグメント）、およびランセグメント `road-run-r1`、`-r2`、`-r2s`、`-r3`、`road-run-night`（第2幕の夜道。3か所の代わり）を生成する。シーンスクリプトは `build_road_pass.py`、`build_road_spring.py`、`build_road_run.py`（`roadkit.py` を共用）、新しいテクスチャは `rest_tex.py`、マージは `merge_rest.mjs`（`road-pass`、`road-spring`、`road-field` の `index.json` と `scene.json` を書く）、検査は `check_rest.mjs`、リポジトリに入れる一覧は `check_committed.sh`。ランセグメントの `layout.runway`（36 m の路面をループさせ、背景を時刻ごとに出す）はパックの `scene.json` にコピーされ、ページは `apps/web/src/three/road/runway.ts` でそれをランニングマシンのように再生する。
