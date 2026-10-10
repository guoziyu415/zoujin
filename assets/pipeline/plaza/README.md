# 锡拉库萨广场的资产流水线（F-2）

从 S7 写实样板（`spikes/frontend/s7-realism/`）搬来，生成 `scene.syracuse-square` 的全部场景资源。一条命令：

```bash
BPY_PYTHON=<装了 bpy 5.2、numpy、pillow 的 Python 3.13> pnpm assets:plaza          # 正式档，4 核约 30 分钟
BPY_PYTHON=... bash assets/pipeline/plaza/build.sh draft /tmp/plaza               # 草稿档，CI 用这个
```

Python 依赖见 `requirements.txt`（`uv venv --python 3.13 && uv pip install -r requirements.txt`），Node 依赖在 `assets/pipeline/package.json`。不需要网络，不花钱。

## 步骤

| 步骤 | 脚本                 | 做什么                                                                                                                                                                               |
| ---- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 贴图 | `placeholder_tex.py` | 每种材质的颜色、法线、粗糙度图。`PLAZA_SCANS` 目录里有扫描材质就用扫描的，没有就按固定种子生成占位图（颜色按 UX art-direction 4.2）。来源记在 `tex/sources.json`                     |
| 场景 | `build_plaza.py`     | 在 Blender 里按 art-direction 4.1 摆广场：城门大街朝 294°，王城和塔在东，神殿在北，喷泉、摊位、刑柱，西南角石工的院子（`place.stonemason-workshop`）。院门是单独的节点，页面可以关上 |
| 天空 | `sky.py`             | Blender 的物理天空，烘焙和页面用同一套太阳公式（`sunpos.py`：北纬 37°、赤纬 +19°、正午 12:00）                                                                                       |
| 烘焙 | `bake.py`            | 地面和建筑的光照图：遮蔽、太阳直射、全部光照，18:30 一个时段                                                                                                                         |
| 编码 | `encode.py`          | 浮点光照图 → 8 位 PNG（间接光 = 全部 − 直射），记下亮度系数 K                                                                                                                        |
| 打包 | `pack_scene.mjs`     | 几何（meshopt）、两档 KTX2 贴图、KTX2 光照图、导航网格（`nav.mjs`，recast），写 `scene.json`                                                                                         |
| 检查 | `check_scene.mjs`    | 下载预算、贴图显存、两档平均颜色、`scene.json` 和 `layout.json` 一致；CI 也跑                                                                                                        |

另有 `preview.py`：从 `plaza_raw.blend` 渲几张 Cycles 预览图看画面，不在流水线里。

## 输出（`assets/scenes/syracuse-square/`）

- `layout.json`（手写）：可走区域、地点边界、位置点（api-contract 的 `spot`）、出口。平面坐标，和 `build_plaza.py` 同一套。
- `scene.json`（生成，进仓库）：页面要的全部信息，坐标已换成 glTF（米，+Y 朝上）。`spots` 的每一项有 `pos`、`yaw`（绕 +Y 把模型的 +Z 转向朝向点）、`place`；`files` 列出每个文件的大小和 sha256，`pack` 是 `entry`（进场包，能走之前下完）或 `hi`（高档在后台下）。
- `build/`（生成，暂不进仓库，见下）：`geo.glb`、`nav.json`、`tex/std/`、`tex/hi/`、`lm/`。

地点和出口：

| 地点 / 出口                 | 在哪                                                 |
| --------------------------- | ---------------------------------------------------- |
| `place.syracuse-square`     | 默认：广场、城门大街、神殿前廊                       |
| `place.stonemason-workshop` | 西南角的院子，北墙上的门是唯一入口                   |
| `place.execution-ground`    | 王城门前：刑柱和台阶（S-050 同一个广场第三天变刑场） |
| 出口 `place.road-to-city`   | 位置点 `exit.road-to-city`，城门外                   |
| 出口 `place.castle`         | 位置点 `exit.castle`，台阶顶上的城门                 |

位置点 21 个，名字和说明在 `layout.json`。后端和数据在 `characters[].spot`、`player.spot` 里只用这些名字；要加新的位置点，改 `layout.json` 再重新生成。

## 两档贴图（frontend-design 10.6.2，art-direction 9.3）

- 标准档：颜色 1024（ETC1S），法线和粗糙度 512（法线 UASTC）。
- 高档另外下：石板地、王城切石墙、普通石材（台阶）、灰泥墙、门和百叶、陶瓦的颜色 2048，法线 1024。
- 两档从同一张源图缩出；`check_scene.mjs` 把两档都解码（和手机用同一个 Basis 转码器），平均颜色差超过 3/255 就失败。

## 导航网格

recast 只在生成时跑（WASM），页面用 `nav.json` 自己做 A* 和拉直（frontend-design 8.6、9.4）。只保留 `layout.json` 里可走区域内、和玩家起点连通的部分；每块多边形标了地点，`places[].enabled = false` 时页面把那个地点的多边形从寻路里去掉。高度已贴到真实地面；台阶在细节网格里是斜坡，位置点本身站在台阶上。

## 生成物不进仓库，只放清单（PM 2026-10-10 决定）

项目容器推 Git LFS 时 `lfs.github.com` 被网络策略挡住（上传到存储成功，确认那一步被拒，对象不算数）。所以 `build/` 不进仓库，仓库里只有 `scene.json` 清单；页面开发、CI 和以后的部署构建都现场生成。三个条件：

1. **能复现**。输入只来自仓库里的文件，或者固定版本、带 sha256 的下载；下载的素材在 `assets/manifest/` 写上来源和授权（CC0 等）。同一份输入生成两次，清单里的 sha256 要一致；做不到逐字节一致的步骤写在下面「复现性」里。
2. **CI 只在改了流水线或场景时现场生成**（`.github/workflows/assets.yml` 的 `paths`）。每次的时长写进 PR 描述，M2-0 结束时 PM 核对 Actions 分钟。
3. **`.gitattributes` 的 LFS 规则留着**。哪个线程误加了 `.glb`、`.ktx2`，推送会在 LFS 那步失败，不会悄悄进普通 git。

## 现在的限制

- **贴图是占位图**：容器访问不了 Poly Haven、ambientCG。CC0 扫描材质要在能上这些网站的地方下载（zg 的 Mac，要 zg 同意），按 `assets/manifest/` 记来源和 sha256，再用 `PLAZA_SCANS` 指过来重新生成。正式材质也要等 UX 的材质清单。
- 只有日没一个时段的光照图；建筑是程序生成的方块；南边两条小巷看得见但走不进去（可走区域外）。
- 光照图的接缝和分辨率没有精修（卡里写明不做）。
