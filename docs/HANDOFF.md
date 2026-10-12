# zoujin 交接（给接手的人或 AI）

写于 2026-10-12（日本时间）。之前由多个 Claude 会话分角色开发，现在交给新的团队接手。本文只写接手要知道的事，细节看文中指的文档。

## H-1 本地续作（同日更新）

用户明确产品是多书平台，目前只有《走れメロス》；新增原创欧式书房，从书架选择书、继续服务器存档、回看亲自经历的结局。实现与验证见 [H-1 交付记录](tasks/h-1/README.md)。代码和生成资产目前只在本地分支 `h-1-reader-home`，未推送、未部署，不能把本地结果当成已上线。

用户要求严格保密。已撤销旧线上网关的匿名调用权限并验证匿名页面、书目录与角色清单返回 403；本地新版增加整站密码门禁，静态资源、API 和 WS 都受保护。部署脚本不再自动公开服务，并尊重本机隐私锁；每次部署仍须单独获得授权。下文第 3 节的无密码线上状态及第 4 节的未生成人物，是本次续作之前的交接快照，不是当前验收结果。

## 1. 这是什么

- **产品**：进入书中世界的写实 3D 多书平台，目前唯一开放的书是太宰治『走れメロス』。玩家从自己的书房选择书，在手机浏览器里走动，用日语语音和书里的人物对话。叙事者 Agent 是世界状态唯一的写入者，结局分三层。目标用户是日本 18〜34 岁成人，第一版只给邀请的 18 岁以上的人玩。
- **技术栈**：
  - 前端：`apps/web`，Vite、React、Three.js，手机优先。
  - 后端：`services/backend`，一个 Python 包，含网关、叙事者和 mock。用 uv 管理，数据库是 PostgreSQL，迁移用 Alembic。
  - 模型：Claude 负责叙事和对话文本（D-028）。Google 只用在 Gemini Live 语音、预录台词和 Model Armor（模板 `zoujin-safety-v1`）。
  - 部署：GCP Cloud Run 跑网关和叙事者，Cloud SQL 存数据，密钥放 Secret Manager。用 gcloud 脚本部署，不用 Terraform。
- **仓库**：`guoziyu415/zoujin`（私有）。

| 目录 | 内容 |
| --- | --- |
| `apps/web` | 网页前端 |
| `services/backend` | 网关、叙事者 |
| `packages/contracts` | JSON Schema 契约，以及生成的 Python 和 TS 类型 |
| `packages/worldsim` | 世界状态规则库 |
| `worlds/hashire-merosu/` | 世界模型，线上用 `1.0.0-slice` |
| `assets/` | 美术管线 `pipeline/`、场景布局 `scenes/<场景>/layout.json`、人物清单 `cast/cast.json`、预录语音 `voice/` |
| `evals/` | 测评用例和探针题（现在不跑） |
| `infra/deploy/` | 部署脚本 |
| `docs/` | 设计文档。PRD、决定记录、开发计划在 `docs/pm/`，交接快照在 `docs/brief/` |

- **关键文档**：
  - 总 brief：项目共享文件夹 `app-team/brief/handoff.md`，仓库里有快照 `docs/brief/`。
  - 接口契约：`app-team/backend/api-contract.md`。
  - 数据契约：`app-team/data/contracts.md`。
  - 怎么加东西、怎么合并：`CONTRIBUTING.md`。
  - 部署：`infra/deploy/README.md`。

## 2. 构建和部署

**资产构建**（产物不进 git，S-075）：

- 场景：`assets/pipeline/{plaza,castle,road,village,crowd}/build.sh`，输出到 `assets/scenes/<场景>/build/`。`scene.json` 是从 `layout.json` 生成的，会提交进仓库。
- 人物：`assets/pipeline/cast/build.sh [名字…]`。要先设好 `MELOS_BLEND`（Mac 上的 `melos_v2.blend`）和 `BPY_PYTHON`（Mac 上是 `~/.zoujin/bpy-venv`）。输出到 `assets/cast/build/<名字>/`，同时更新 `assets/cast/cast.json`。
- 这些都要 Blender 5.2、bpy、MPFB 2，只在 zg 的 Mac 上装好了。

**部署**（只能在 zg 的 Mac 上跑，状态在 `~/.zoujin/deploy/`）：

```sh
cd ~/Developer/zoujin && git pull && infra/deploy/deploy.sh all   # setup→build→migrate→up→promote
infra/deploy/deploy.sh verify      # 对线上冒烟
infra/deploy/deploy.sh invite 5    # 发 5 个邀请码，写到 ~/.zoujin/deploy/invites-*.txt
infra/deploy/deploy.sh rollback    # 切回上一个版本
infra/deploy/deploy.sh check       # 只读，查看现状
```

- `build` 会先跑 `infra/deploy/packs.py` 预检，对比场景包和人物模型与当前提交的清单。缺的或旧的会列出来，并给出要跑的管线命令，然后停下。只有「旧」并且确定照旧部署时，加 `ZJ_ALLOW_STALE=1`。
- 正式地址在 `~/.zoujin/deploy/url`，冒烟账号在 `~/.zoujin/deploy/smoke-code`。这两样都不能进仓库，也不能发到聊天里。
- Mac 上的 Claude 自动模式会拦「合并没审的 PR」和「部署没审的提交」，所以重新部署要 zg 自己在终端里跑。

## 3. 线上现状

- 线上是 main 的 `f25adea`（日本时间 10-12 05:31 由 zg 自己部署），只能凭邀请码登录，没有密码。没有码会被拒，叙事者只接受网关的 IAM 身份调用。
- 第一次部署时冒烟 14/14 通过，发过 5 个邀请码。
- main 现在已经到 `a0c6a5c`，比线上多一个 #265，见第 4 节第 3 条。

## 4. 已知问题和没做完的事（按优先级）

1. **5 个角色没有真人模型，显示成灰色胶囊**：旅人（玩家自己）、メロス、市の老爺、市の若い衆、市の少女。没有模型的人物由 `apps/web/src/three/mannequin.ts` 画成胶囊。
   - **main 上已有 9 套**，线上部署的就是这 9 套：王、セリヌンティウス、妹、花婿、フィロストラトス、徒弟、牧童，加上妹和花婿的婚礼装（#237、#239、#250）。
   - **补到一半的分支** `claude/f16-characters-trl9n4`（`f070434`，还没合并，基于当时的 main）。分支上已经做了：
     - 5 个人的设定：`role.traveler`、`char.melos`、老爺、若い衆、少女，写在 `assets/pipeline/cast/characters.json`。
     - 新的服装件帽子和腰带，写在 `build_cast.py`。
     - `build.sh` 里的メロス直接从 A-0 的 `melos_v2.blend` 导出。
     - 运行时的 CAST 加上了这 5 人（`apps/web/src/three/cast/cast.ts`）。
     - 结局舞台 `ending/Staging.tsx` 也换成了真人。
     - 291 个单元测试都过了，类型检查也过了，3D 主块 226/250 KB。
   - **这 5 套模型还没生成**，构建中途停了。剩下的步骤：
     1. 在仓库根目录生成这 5 套。每人大约 20〜25 分钟，可以每人开一个进程并行跑：
        `BPY_PYTHON=<带 bpy 5.2、numpy、pillow 的 python> MELOS_BLEND=<共享文件夹 app-team/frontend/spikes/a0-melos/mac/melos_v2.blend> UAL_GLB=<同一目录下的 anims/UAL1_Standard.glb> bash assets/pipeline/cast/build.sh traveler melos old-man young-man maiden`
        全部跑完后，再跑一次 `node assets/pipeline/cast/check_cast.mjs assets/cast/build assets/cast/cast.json`。
     2. 提交 `assets/cast/cast.json`，把分支合进 main。
     3. 把 `assets/cast/build/` 下的 14 个目录打成 tar，拷到 Mac 上，然后重新部署。
   - **注意**：
     - `lod_export.py` 里必须先导入 bpy，再导入 bmesh。
     - 旅人的帽子和腰带是新写的，还没有人看过成品，位置可能要调。
   - **还没做的**：
     - 群众层只有广场有包。城の警吏、山賊、旅の一団，以及其他场景的群众，都还没有真人模型。
     - 侍女、警吏見習い计划放到第二版。
2. **角色站位重叠**（截图：セリヌンティウス身边紧挨着一个胶囊）。没修，下面是查的方向：
   - **站位由服务端分配**：`services/backend/src/zoujin_backend/projection.py` 的 `snapshot()`（约 300〜315 行）调用 `world.py` 的 `Scene.character_spots()`。规则是人物按顺序占自己所在地点里还空着的点，跳过 `way.*` 和 `auto: false` 的点，玩家站的点算占着。**点不够时，多出来的人和别人重叠在第一个可用点上**（`world.py` 约 55〜67 行）。前端 `apps/web/src/three/People.tsx` 只是照服务端给的 spot 画。
   - **最可能的原因是石工房的点太少**：读的是生成的 `assets/scenes/syracuse-square/scene.json`，不是 `layout.json`，一个点属于哪个地点由 navmesh 判定。石工房 `place.stonemason-workshop` 能自动分配的点只有 `workshop-yard` 和 `workshop-bench` 两个：`workshop-gate` 判给了广场，`workshop-door` 是 `auto: false`。セリヌンティウス和フィロストラトス开局都在石工房（`worlds/hashire-merosu/1.0.0-slice/world.json` 的 `initialPlace`）。玩家一走进石工房就占了 `workshop-yard`（`startSpots`），剩下两个人只能挤在 `workshop-bench`。节拍再把メロス之类的人移进来，也会出现同样的情况。
   - **其他可能**：
     - (a) 节拍用 relocate 指定了 spot 的人（`fixed`）之间没有去重，两个人被指到同一个点就会重叠。
     - (b) 胶囊可能是玩家自己（旅人也是胶囊），玩家的位置由 `Player.tsx` 和 `startSpots` 决定，可能离人物的点很近。
     - (c) 点和点本身挨得太近，比如 `workshop-bench` 和 `workshop-door` 只隔约 2.7 米。
     - (d) 前端 `three/crowd/` 的群众随机站位和人物的点撞上了。
   - **怎么查**：在出问题的那一刻取 `GET /v1/playthroughs/{pid}/snapshot`，看 `characters[].spot` 有没有重复的值，就能区分是服务端分配的问题还是前端的问题。修法一般是在 `layout.json` 给石工房加点，然后重跑 `plaza/build.sh` 生成 `scene.json`；也可以改 `character_spots` 的兜底，让多出来的人在附近错开站。
3. **`/v1/telemetry` 在线上返回 404**：修复 #265 已合进 main，还没部署。下次部署会一起带上。
4. **PR #263 还开着**：它是黑屏问题（选完人物后黑屏）的备用修法，改的是 vite 的 castle 分包正则。正式修法 #264 已上线，所以 #263 可以合也可以关。
5. **main 上有两条测试本来就是红的**：数据工程 10-12 03:18（日本时间）报的，和最近的改动无关，还没修。跑 `uv run pytest` 就能看到是哪两条（需要本地 PostgreSQL）。
6. **删掉的第 14、15、26 步**（四幕测评、200 局模拟画像、CI）：做到哪、从哪里接，写在共享文件夹 `app-team/pm/deferred-steps.md`。CI 的自托管 runner 在 zg 的 Mac 上停着，6 个 workflow 都处于 disabled 状态。
7. **上线后没在手机真机上测过**。

## 5. 项目约定

- **仓库里不放密钥**，网址、密码、邀请码、token、GCP 项目 ID 也都不放。密钥放在 Secret Manager 和 Mac 的钥匙串（`zoujin-claude`）。
- **资产构建产物不进 git**，包括 `assets/scenes/*/build/`、`assets/cast/build/`。只提交清单和 `scene.json`。手工 `.blend`、`glb` 走 LFS。
- **zg 的 Mac 磁盘不区分大小写**，别让两个文件名只差大小写。**`/bin/bash` 是 3.2**，脚本里不能用 `mapfile`、关联数组之类的写法。
- 之前的流程是作者跑完自己改动的单元测试就自己合并 PR，不审（D-037），也不跑 CI。没有 CI 时要注意：并行的 PR 可能撞上 Alembic 迁移号，合并前先看一眼 main 上最大的迁移号。
- 文档和提交信息用中文写，游戏里的文本是日语。
