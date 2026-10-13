# zoujin 交接（给接手的人或 AI）

写于 2026-10-12（日本时间）。之前由多个 Claude 会话分角色开发，现在交给新的团队接手。本文只写接手要知道的事，细节看文中指的文档。

## 提交材料与公开授权（2026-10-13 最新）

用户已明确允许公开产品概念、项目说明、架构图及演示视频；实际应用继续保留密码与邀请码，仓库保持私有。日语提交说明、架构 PNG/SVG、官方统计与评分对应、录制脚本见 [提交材料](submission/README.md)。视频录制与 YouTube 上传由用户负责，不再继续录制或运行真实对局。正式表单提交尚未核实。

现网运行镜像源码为 `31e2684`，默认分支已包含该版本及后续交接记录。下文部署段、H-1 本地段保留开发历史，以本节及「用户试玩后的界面调整」为当前状态。提交材料依据代码核对了路由：Gemini Live 提供人物语音，Gemini 文字模型提供人物文字回复；Claude 负责叙事、提取、检查、记忆、安全与候选等处理。不应把人物全部回复写成 Claude。

## R-1 回归验证接续（2026-10-13 更新）

用户已明确授权恢复此前延后的四幕剧情、防剧透、CI 和分阶段模拟，真实模型调用及费用在本轮授权范围内；评审员校准与预录语音试听仍然暂缓。六个 CI 工作流和隔离的本机 runner 已恢复，实际执行记录与未完成项见 [R-1 任务卡](tasks/r-1/README.md)。下文历史快照中的「CI 停止」「测评不跑」已被本轮授权取代。恢复测试不等于测试通过，也不等于部署；入口仍需保持私密。

最新范围是修复结局与未完成流程、限流与失败记录、web/assets CI、防剧透四项。2026-10-13 用户随后明确跳过剩余真实对局与 CI，自己试玩；已停止当前批次并取消排队/运行中的 CI，不再等待其验收。保留已完成与中断记录，取消不能算通过。200 局与四幕 980 次全量均未启动。代码位于私有分支 `r-1-deferred-validation`；没有修改默认分支，不得把旧本地结果写成新版已全部通过。今天提交的额外材料与访问缺口见 [提交交接](tasks/r-1/submission-handoff.md)。

## 经用户授权部署（2026-10-13）

用户明确回复「部署」后，修复版本已部署到既有 Cloud Run 网关与叙事者，实际镜像源码提交为 `be03d70`（在 `2ce6b26` 上仅补云端健康探测路径）。两个服务均已切换 100% 正式流量，真实文本/Live 配置及密码 Secret 引用已核实。候选与正式地址均通过密码、邀请码、首页、场景、开局、WebSocket、匿名页面/资源/API 拒绝的冒烟检查；不代表整局语音或全量质量通过。

Cloud Run 保留部分以 `z` 结尾的路径，旧 `/healthz` 在平台层返回 404；云端探测改用空 204 的 `/health`，旧路径仍兼容本机。该修改的四项门禁测试通过，没有恢复 CI 或批量对局。

云端 IAM 仍私有，隐私锁保留。供用户这台 Mac 试玩的认证代理只监听回环，入口为 `http://127.0.0.1:8090`，访问的是实际云端服务而非假模型。外层本机转发修正同源 Origin，并仅在本机 HTTP 跳转移除 Secure cookie 属性；云端生产 cookie 仍 Secure。密码和邀请码、代理及发布证据只在本机部署私有目录；不进入仓库。评审无需 Google 身份的外部访问方式尚未开放，不能把本机入口当作赛事部署 URL。

### 外部评审入口已按用户指示准备

用户随后明确要求「把外部评审入口也弄好，必须带密码」。已清除网关全部临时标签，仅开放当前验过密码的网关 HTTPS 入口；叙事服务保持 IAM 私有。没有 Google 身份或 Cookie 时，实际前端脚本、GLB、场景入口、音频路径及 API 共 17 条路径均被密码门禁拦住，未认证 WebSocket 握手被拒，页面只显示密码表单。输入密码后还需邀请码登录，生产 cookie 保持 Secure/HttpOnly。

评审主账号和两份备用邀请码已准备。主账号保留真实生成的开局状态；外部登录、书目录、进度、人物资源及 WebSocket 启动通过，未伪造结局。日语说明和全部 URL/凭证只在本机部署私有目录。隐私锁保留，新增仅允许已验当前版本的本机授权记录；未来部署、切换或回滚必须先恢复 IAM 私有。相关 25 项短测通过，不恢复批量对局或 CI。代码同步到私有仓库默认分支 main，供赛事读取；说明、架构图、视频的公开和正式提交仍未执行。

### 用户试玩后的界面调整

用户指出对话挡住场景，随后明确只需手动收起。`31e2684` 增加「字幕をたたむ／字幕をひらく」，仅切换本机显示，不清空当前文字、不暂停声音、不触发动作或模型；收起后的空白区可点击到 3D。选书页的「原作を読んでいない方へ」可展开查看开场背景及原作开场前的人物关系，不给未来节拍或结局，不强制重演原剧情；内容按书籍 ID 隔离。

类型、lint、构建及体积检查通过（首屏 108.1 KB / 120，3D 235.3 KB / 250）。本机真实 3D＋mock 模型浏览器检查确认手机/桌面收起与展开、文字保留及点击穿透；开场介绍在手机纵横屏可读，截图保留在仓库外。独立复核确认无新增未来信息或数据写入。此为界面验证，不是人物语音质量认证。

该版本已更新到既有服务；部署前先恢复私有 IAM 并实际确认匿名 403，候选与正式密码/登录/开局冒烟通过后清除临时标签，重新验证 17 条外部内容路径及评审登录/资源/WebSocket 才恢复外部入口。原账号、密码、邀请码及评审样例进度保留，没有恢复 CI 或批量对局。

## H-1 本地续作（同日更新）

用户明确产品是多书平台，目前只有《走れメロス》；新增原创欧式书房，从书架选择书、继续服务器存档、回看亲自经历的结局。实现与验证见 [H-1 交付记录](tasks/h-1/README.md)。代码和生成资产目前只在本地分支 `h-1-reader-home`，未推送、未部署，不能把本地结果当成已上线。

用户要求严格保密。已撤销旧线上网关的匿名调用权限并验证匿名页面、书目录与角色清单返回 403；本地新版增加整站密码门禁，静态资源、API 和 WS 都受保护。部署脚本不再自动公开服务，并尊重本机隐私锁；每次部署仍须单独获得授权。下文第 3 节的无密码线上状态及第 4 节的未生成人物，是本次续作之前的交接快照，不是当前验收结果。

## 1. 这是什么

- **产品**：进入书中世界的写实 3D 多书平台，目前唯一开放的书是太宰治『走れメロス』。玩家从自己的书房选择书，在手机浏览器里走动，用日语语音和书里的人物对话。叙事者 Agent 是世界状态唯一的写入者，结局分三层。目标用户是日本 18〜34 岁成人，第一版只给邀请的 18 岁以上的人玩。
- **技术栈**：
  - 前端：`apps/web`，Vite、React、Three.js，手机优先。
  - 后端：`services/backend`，一个 Python 包，含网关、叙事者和 mock。用 uv 管理，数据库是 PostgreSQL，迁移用 Alembic。
  - 模型：Claude 负责叙事、意图提取、规则检查、记忆、安全与候选生成；Google Gemini 提供人物文字回复，Gemini Live 提供人物语音，另使用预录台词和 Model Armor。
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
