# Castle pipeline / 王城のパイプライン (F-14)

The castle (`scene.castle-throne`, package `assets/scenes/castle-throne/`) is generated the same way as the plaza and the river (`../plaza/README.md`: only the manifest goes in the repo, assets are generated on the spot, and two generations are byte-for-byte identical). The plaza's sky, bake, encode, pack and check scripts are called directly, switching scenes via environment variables; the plaza scripts are not modified.

王城（`scene.castle-throne`、パッケージ `assets/scenes/castle-throne/`）は広場と川と同じ方法で生成する（`../plaza/README.md`：リポジトリに入れるのはマニフェストのみ、その場で生成し、2 回の生成はバイト単位で一致する）。広場の空・ベイク・エンコード・パック・チェックのスクリプトをそのまま呼び出し、環境変数でシーンを切り替える。広場のスクリプトは変更しない。

```
assets/pipeline/castle/build.sh [final|draft] [out_dir]
```

- `castle_tex.py`: textures. The plaza's flagstones, limestone, plaster, tiles and hills, plus the throne room's polished dark stone floor, indigo wool curtains, carved wood, bronze, and ochre-black wall bases. Put CC0 scans in the `CASTLE_SCANS` directory and regenerate.
  テクスチャ。広場の石畳・石灰岩・漆喰・瓦・丘陵に、玉座の間の磨かれた暗色の石の床、藍色の羊毛のカーテン、彫刻された木、青銅、壁の裾の黄土黒を加える。CC0 のスキャンを `CASTLE_SCANS` ディレクトリに置いて再生成する。
- `build_castle.py`: modeling (the floor plan in section 2 of `docs/ux/scenes/castle.md`). Lamps and braziers are placed as Blender point lights according to `lamps` in `layout.json`; the lamps' own bronze goes in the `far` group and is not baked (the light source sits on it and would stretch the whole lightmap's range onto it).
  モデリング（`docs/ux/scenes/castle.md` 第 2 節の平面図）。灯りと火鉢は `layout.json` の `lamps` に従って Blender の点光源として配置する。灯り本体の青銅は `far` グループに置いてベイクしない（光源がその上に貼り付いているため、ライトマップ全体の範囲がそこに引き伸ばされてしまう）。
- Bake: the night of the promise at 20:30, no sun (`BAKE_SUN_E=0`), a moonless starry sky, all light from the lamps. In the daytime the courtyard uses the plaza's real-time sun plus baked occlusion; the throne room uses this same lighting in the daytime too (UX section 3).
  ベイク：約束の夜 20:30、太陽なし（`BAKE_SUN_E=0`）、月のない星空、光はすべて灯り。昼の中庭は広場と同じリアルタイムの太陽にベイクした遮蔽を加えて使う。玉座の間は昼もこの灯りを使う（UX 第 3 節）。
- `lamps.mjs`: `pack_scene.mjs` packs only the "indirect light" and occlusion; this step additionally packs the full one (`lm/<mesh>_full.ktx2`, direct and reflected lamp light) and copies `lamps` and `hall` into `scene.json` (glTF coordinates), which the page's `three/castle/HallLight.tsx` reads.
  `pack_scene.mjs` は「間接光」と遮蔽だけをパックする。このステップで完全版（`lm/<mesh>_full.ktx2`、灯りの直接光と反射光）を追加でパックし、`lamps` と `hall` を `scene.json`（glTF 座標）に写す。ページの `three/castle/HallLight.tsx` がこれを読む。

Navmesh note: `nav.mjs` takes the first polygon found directly above the start point regardless of height, so there must be no flat roof above the walkable area (the lintel of the gate passage is left uncapped, with a steep stone roof built above it).

ナビメッシュの注意：`nav.mjs` は始点の真上で最初に見つかったポリゴンを高さに関係なく採用するため、歩行可能領域の上空に平らな屋根があってはならない（城門のまぐさは天井を塞がず、その上に急勾配の石屋根を載せる）。
