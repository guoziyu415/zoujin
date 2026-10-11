# 村子的流水线（F-11）

照归途的做法（`../road/README.md`、`../plaza/README.md`：只有清单进仓库，现场生成，两次生成逐字节一致）。广场的天空、烘焙、编码、打包、检查脚本直接调用，靠环境变量换场景；Blender 小工具、占位贴图、路边共用包的键表在 `../common/`，和路共用。

```
assets/pipeline/village/build.sh [final|draft] [out_dir]
```

一条命令出：

- `village`（`scene.village`，牧童的第一屏）：屋外的全部几何、导航（含屋里的地面）、晴的白天那一套光（一日目 10:00，太阳 116°、高 58°）。第一次进场只下这个包和它用的 `road-common` 文件。
- `road-common`：村子用到的路边键（土路、干草、露头、树皮、白杨、圣栎、远山、麦）挪进共用包（`../common/roadside.mjs`），和川的同一份字节；麦是村子加进来的。

| 变量                 | 村子                  |
| -------------------- | --------------------- |
| `SCENE_STEM`         | `village`             |
| `SCENE_ROT_DEG`      | 0                     |
| `SCENE_MINUS_X_AZ`   | 270（+x 朝东）        |
| `PLAZA_BAKE_MINUTE`  | 600（10:00）          |
| `BAKE_SUN_E`、`_RGB` | 6、58° 高的太阳的颜色 |
| `BAKE_RES`           | 1024                  |

步骤：贴图（`../common/road_tex.py`）→ 场景（`build_village.py`）→ 天空 → 烘焙 → **实例化**（`merge_inst.mjs`）→ 编码 → 打包 → 叶子贴图小尺寸重编码 → 挪共用贴图 → 18:30 的天空 → **重烘**（`relight.py`：日没、夜、雨）→ **光的子包**（`pack_sub.mjs`）→ 检查（`../plaza/check_scene.mjs`，再 `check_village.mjs`：共用文件、draw call、实例化节点）。

**实例化**（卡第 3 条）：麦、麦捆、葡萄藤、羊各一个 draw call。`build_village.py` 把每样东西的原型导出成 `<stem>_proto.glb`（各自在原点），每个副本的位置、朝向、大小写进 `<stem>_inst.json`；烘焙时副本以链接复制的形式站在 `inst` 集合里，只当遮挡（地上有它们的阴影和遮蔽），自己不烘。`merge_inst.mjs` 在烘焙之后把原型加进 `<stem>_raw.glb`，每样一个带 `EXT_mesh_gpu_instancing` 的节点（three.js 的 GLTFLoader 认成 `InstancedMesh`），每个副本按哈希给一点颜色变化（`_COLOR_0`），同样的输入出同样的字节。

**光的子包**（卡第 1 条）：烘完村子以后，`relight.py` 打开烘好的 `<stem>_baked.blend`（光照图的 UV 已经定了），换光再烘一遍 `ground`、`arch`，`pack_sub.mjs` 打包。清单叫 `pack.json`（后端把 `assets/scenes/*/scene.json` 当布局读），放在村子目录旁边：

| 子包                   | 光                                                                     | 上限 |
| ---------------------- | ---------------------------------------------------------------------- | ---- |
| `village-light-sunset` | 18:30，广场的 `sky.py` 画 18:30 的天，太阳 6、暖色                     | 2 MB |
| `village-light-night`  | 星空（均匀的暗蓝天光），花婿家葡萄架下一盏油灯烘进去                   | 2 MB |
| `village-light-rain`   | 暴雨的阴天（CIE 阴天的天光分布，没有太阳）；雨夜、三日目薄明由页面调暗 | 2 MB |

- 只带间接光（全光减去太阳的直射，灯的直射留在里面），AO 用村子包的，太阳照样实时画。天空、太阳、灯的位置写进清单，页面照着放动态光。
- 屋里的子包 `village-interior` 是自己的流水线（`interior/build.sh`）。
- `village/scene.json` 多出 `subPacks`（全部子包，屋里的按它进仓库的 `pack.json`）、`subPackBytes`，以及布局里抄过来的 `lightSets`（每个时段屋外、屋里用哪套光，两套之间按时刻插值；变天以后用雨和宴席）。
- `check_village.mjs` 查：子包的文件和 sha256、各自的上限、光照图尺寸和村子一致、`lightSets` 引用的光都存在、加上屋里以后的 draw call、整个村子（标准档、用到的共用文件、全部子包）≤ 11 MB，强机档另算。

贴图现在全是占位；CC0 扫描经第一个前端线程的资产流程，放进 `ROAD_SCANS` 目录重新生成。
