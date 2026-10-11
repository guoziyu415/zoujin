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

步骤：贴图（`../common/road_tex.py`）→ 场景（`build_village.py`）→ 天空 → 烘焙 → **实例化**（`merge_inst.mjs`）→ 编码 → 打包 → 叶子贴图小尺寸重编码 → 挪共用贴图 → 检查（`../plaza/check_scene.mjs`，再 `check_village.mjs`：共用文件、draw call、实例化节点）。

**实例化**（卡第 3 条）：麦、麦捆、葡萄藤、羊各一个 draw call。`build_village.py` 把每样东西的原型导出成 `<stem>_proto.glb`（各自在原点），每个副本的位置、朝向、大小写进 `<stem>_inst.json`；烘焙时副本以链接复制的形式站在 `inst` 集合里，只当遮挡（地上有它们的阴影和遮蔽），自己不烘。`merge_inst.mjs` 在烘焙之后把原型加进 `<stem>_raw.glb`，每样一个带 `EXT_mesh_gpu_instancing` 的节点（three.js 的 GLTFLoader 认成 `InstancedMesh`），每个副本按哈希给一点颜色变化（`_COLOR_0`），同样的输入出同样的字节。

光的子包（日没、夜、雨）和屋里的子包是 F-11 的第 2 个 PR。

贴图现在全是占位；CC0 扫描经第一个前端线程的资产流程，放进 `ROAD_SCANS` 目录重新生成。
