# 归途的流水线（F-10）

归途的停留点照广场的做法生成（`../plaza/README.md`：只有清单进仓库，现场生成，两次生成逐字节一致）。广场的天空、烘焙、编码、打包、检查脚本直接调用，靠环境变量换场景（默认值就是广场的，广场的输出不变）：

| 变量                         | 意思                                                             | 广场          | 川             |
| ---------------------------- | ---------------------------------------------------------------- | ------------- | -------------- |
| `SCENE_STEM`                 | 工作目录里的文件名 `<stem>_raw.blend` / `.glb`                   | `plaza`       | 包名           |
| `SCENE_ROT_DEG`              | 平面坐标转进 glTF 的角度，和 `layout.json` 的 `rotationDeg` 一致 | 144           | 0              |
| `SCENE_MINUS_X_AZ`           | 平面 −x 的方位角                                                 | 294           | 270（+x 朝东） |
| `PLAZA_BAKE_MINUTE`          | 烘焙时刻                                                         | 1110（18:30） | 315 / 705      |
| `SKY_SUN_ELEV_DEG`           | 只换天空的太阳高度，方向不变                                     | —             | 第二幕 −1.5    |
| `BAKE_SUN_E`、`BAKE_SUN_RGB` | 烘焙用的直射光（0 = 没有）                                       | 6、18:30 的色 | 0 / 6、5500 K  |
| `BAKE_RES`                   | 正式档光照图的边长                                               | 2048          | 1024           |
| `SCENE_INPUTS`               | 清单里记成本场景自己的脚本                                       | —             | 本目录的脚本   |

```
assets/pipeline/road/build.sh [final|draft] [out_dir]
```

一条命令出：

- `road-river-calm`（第二幕 05:15）、`road-river-flood`（第四幕 11:45）：同一份 `build_road_river.py`，`RIVER_STATE` 开关。
- `road-common`：路边共用的贴图，键表固定在 `../common/roadside.mjs`（土路、干草、露头、碎石、树皮、白杨、圣栎、远山、麦；村子也用，F-11）。`merge_river.mjs` 调它把两个包里这些键的文件挪进去，两边必须是同一份字节；生成只往已有的 `road-common` 里加，换了字节的键会覆盖，其他用到它的包的检查就会失败，要重新生成。每个包的 `bytes.shared` 只算它自己用的那几个文件。清单叫 `pack.json`，不叫 `scene.json`（后端把 `assets/scenes/*/scene.json` 都当场景布局读）。
- `road-river/index.json`：页面按幕挑包（页面拿不到世界变量），附 `var.bridge` 的对应值；`road-river/scene.json`：后端和 `build_world` 读的 `scene.road-river` 布局（两个包的地点、出口、位置点合起来）。

检查：每个包跑 `../plaza/check_scene.mjs`（预算取 `assets/budgets.json` 的 `scenes.<包名>`），再跑 `check_road.mjs`（共用包、draw call、索引和合起来的布局、世界模型里有这个场景的每一幕都挑得出唯一一个包）。

`preview_river.py` 是开发用的 Cycles 预览，不进构建。

贴图现在全是占位（`../common/road_tex.py` 按固定种子生成，路和村子共用；Blender 小工具 `../common/bl.py`、叶子贴图的小尺寸重编码 `../common/small_tex.mjs` 也在那里）；CC0 扫描在 zg 的 Mac 上下载，经第一个前端线程的资产流程，放进 `ROAD_SCANS` 目录重新生成。
