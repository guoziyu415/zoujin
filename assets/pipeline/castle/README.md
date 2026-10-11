# 王城的流水线（F-14）

王城（`scene.castle-throne`，包 `assets/scenes/castle-throne/`）照广场和川的做法生成（`../plaza/README.md`：只有清单进仓库，现场生成，两次生成逐字节一致）。广场的天空、烘焙、编码、打包、检查脚本直接调用，靠环境变量换场景，广场的脚本不改。

```
assets/pipeline/castle/build.sh [final|draft] [out_dir]
```

- `castle_tex.py`：贴图。广场的石板、石灰岩、抹灰、瓦、丘陵，加王座之间的打磨深色石地面、靛蓝羊毛帘子、雕花木头、青铜、墙脚赭黑。CC0 扫描放进 `CASTLE_SCANS` 目录重新生成。
- `build_castle.py`：建模（`docs/ux/scenes/castle.md` 第 2 节的平面）。灯和火盆照 `layout.json` 的 `lamps` 放 Blender 的点光源；灯本身的青铜放在 `far` 组，不烘（光源贴在它上面，会把整张光照图的范围拉到它身上）。
- 烘焙：约定之夜 20:30，没有太阳（`BAKE_SUN_E=0`），无月的星空，光全是灯。中庭白天照广场用实时太阳加烘的遮蔽；王座之间白天也用这套灯光（UX 3 节）。
- `lamps.mjs`：`pack_scene.mjs` 只打包「间接光」和遮蔽；这一步再打包完整的那张（`lm/<mesh>_full.ktx2`，灯的直射和反射），并把 `lamps`、`hall` 抄进 `scene.json`（glTF 坐标），页面的 `three/castle/HallLight.tsx` 读。

导航网格注意：`nav.mjs` 取起点正上方找到的第一个多边形，不管高低，所以可走区域上空不能有平顶（城门洞的过梁不封顶，上面盖陡的石顶）。
