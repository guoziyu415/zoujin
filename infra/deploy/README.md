# 部署（B-23）

第一版的云上环境：只给邀请的 18 岁以上的人玩。只在 zg 的 Mac 上跑，项目是 gcloud 的 `zoujin` 配置里的那个（脚本自己切到这个配置，指到别的项目就停）。仓库里没有项目 ID、地址、密码、邀请码。

## 第 27 步：一条命令

```sh
cd ~/Developer/zoujin && git pull && infra/deploy/deploy.sh all
```

`all` = `setup` → `build` → `migrate` → `up` → `promote`。哪一步停了，修好再跑 `all` 或那一步，做过的跳过（实例、密钥、账号已有的不重建）。第一次大约 30 分钟，大头是建数据库实例（约 10 分钟）和构建镜像。跑完：

```sh
open "$(cat ~/.zoujin/deploy/url)"      # 打开正式地址
infra/deploy/deploy.sh invite 5         # 5 个邀请码，写进 ~/.zoujin/deploy/invites-*.txt，一人一个
```

跑之前要有的（Mac 上已经有的不用管）：

- gcloud 的 `zoujin` 配置和 zg 的应用默认凭证（`~/.config/gcloud/application_default_credentials.json`）；
- Docker 在跑（构建镜像、Cloud SQL 代理都在 Docker 里）；
- 钥匙串里的 `zoujin-claude`（第一次 setup 存进 Secret Manager）；
- Claude 两档的模型 ID：终端里 export 的 `ZJ_CLAUDE_HAIKU`、`ZJ_CLAUDE_SONNET`，或写进 `~/.zoujin/deploy/config.env`（export 过一次就自动记进去）；
- 场景包和人物模型：前端的流水线在这个仓库里生成过的 `assets/scenes/<目录>/build/` 和 `assets/cast/build/`（不进 git，S-075）。`build` 先用 `packs.py` 和这次部署的提交里的清单比，缺的、旧的（不是照这个提交的流水线生成的：有 inputs 比 inputs，没有的比结构；人物文件比 sha256。贴图、烘焙的字节换台机器会差一点，不算旧）列出来并给出要跑的流水线命令，停下；只有「旧」、确定照旧部署时加 `ZJ_ALLOW_STALE=1`。

## 拓扑

| 东西     | 怎么建                                                                                 | 说明                                                                                                                                                                                   |
| -------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 网关     | Cloud Run，`asia-northeast1`，服务名随机 `s-` 加 8 位                                  | 默认 IAM 私有，外层整站密码加内层邀请码会话；同源发前端（`ZJ_WEB_DIST`）和场景包（`/scenes/<版本>/…`），不上负载均衡和 CDN；WebSocket 超时 60 分钟、会话亲和；最小 0 个实例、最多 3 个 |
| 叙事者   | Cloud Run，同一个镜像，服务名随机                                                      | 不许匿名，只给网关的服务账号调用权限（`ZJ_NARRATOR_AUTH=iam`，网关带 OIDC 令牌）                                                                                                       |
| 数据库   | Cloud SQL PostgreSQL 17，`db-f1-micro`，单区，开删除保护，每天备份                     | 库 `zoujin`；`zj_owner` 跑迁移，`zj_gw`、`zj_nr` 两个应用账号只能增删改查，不能建表                                                                                                    |
| 密钥     | Secret Manager：`zj-db-owner`、`zj-db-gw`、`zj-db-nr`、`zj-claude`、`zj-site-password` | 应用账号的连接串只给对应的服务账号读，Claude 的 Key 两个都能读，站点密码只给网关读                                                                                                     |
| 服务账号 | `zj-gateway`、`zj-narrator`                                                            | `cloudsql.client`、`aiplatform.user`、`modelarmor.user`；网关另有调叙事者的权限                                                                                                        |
| 镜像     | Artifact Registry `images`，标签是提交的前 7 位加时间                                  | 在 Mac 上 `docker buildx --platform linux/amd64` 构建，不用 Cloud Build                                                                                                                |

模型照开发期（D-028）：Claude 用 `zj-claude`，Gemini Live、补转写、Model Armor（模板 `zoujin-safety-v1`）用服务账号。每个实例的账本在 `/tmp`，上限 `config.env` 的 `ZJ_MAX_CLAUDE_USD`、`ZJ_MAX_GOOGLE_USD`（默认各 10 美元，实例重启归零；总额靠项目的预算提醒 G-2）。

## 上线流程（zg 的规范）

1. `up`：叙事者、网关的新版本以 `--no-traffic --tag next` 上线（第一次没有旧版本：建成私有服务，只有 zg 的身份能访问）；对候选地址跑 `smoke.py smoke`：首页、冒烟账号登录、manifest、场景包、开一局（叙事者写开局，也验了网关调叙事者的身份）、带 Cookie 的 WebSocket 握手、删掉这一局，再查匿名被拒。
2. `promote`：两个服务都切到新版本，维持现有 IAM 私密设置；对正式地址再冒烟一次，查未经站点密码的页面、资产、REST 和 WebSocket 均被拒。脚本不会自动打开公开访问。
3. 正式地址冒烟不过：`deploy.sh rollback` 切回上一个版本。

冒烟用的邀请码在 `~/.zoujin/deploy/smoke-code`，是一个专用账号，每天最多开 5 局（S-019，删了也算）；每次 `migrate` 换一个新的，重跑不会撞上次数。`build` 遇到同一个提交已经构建过就跳过，场景包换过要重建加 `ZJ_REBUILD=1`。

## 平时

- `deploy.sh check`：只读，现在有什么；
- 再部署：`git pull && infra/deploy/deploy.sh build && infra/deploy/deploy.sh migrate && infra/deploy/deploy.sh up && infra/deploy/deploy.sh promote`（或 `all`）；
- 不玩的时候：`deploy.sh pause` 停数据库（服务本来就缩到 0），`deploy.sh resume` 再开。

## 和设计不一样的地方

- **gcloud 脚本，不是 Terraform**：Mac 上没装 Terraform，第一版的资源少，脚本按「已有就跳过」写。
- **叙事者的入口是 all，不是 internal**：内部入口要网关走 VPC 出口，连 Anthropic 还得加 Cloud NAT，第一版不加；挡匿名的是 Cloud Run 的 IAM（只认网关服务账号的 OIDC 令牌）。
- **数据库账号用密码，不用 IAM 登录**：代码只读 `DATABASE_URL`；密码随机生成，只在 Secret Manager。两个应用账号权限一样，按表收窄（backend-design 2.1）要先把代码里网关写叙事者表的地方理清，留给后端。
- **没有 Cloud Tasks、Cloud Scheduler**：代码还没用到；结局和保留期删除接上时再加。

### H-1 私密站点门禁

站点密码 Secret 名称为 `zj-site-password`，只授予网关服务账号读取。`setup` 在没有该 Secret 时生成随机值并通过标准输入写入，不打印密码；`up` 缺少 Secret 时停止。网关通过 `ZJ_SITE_PASSWORD` Secret 引用读取，冒烟通过 `ZJ_SMOKE_PASSWORD` 环境传入，不放命令行或日志；门禁通行之后仍须邀请码。

生产缺密码时所有内容返回 503；`/health` 仅回空 204。旧 `/healthz` 兼容本机使用，但 Cloud Run 保留部分以 `z` 结尾的路径，云端冒烟必须使用 `/health`（[官方已知问题](https://docs.cloud.google.com/run/docs/known-issues#reserved_url_paths)）。冒烟先验证匿名页面、脚本、人物、场景、音频和 API 均被密码拦住，再验证密码+邀请码后的完整会话。密码轮换会使旧签名票立即失效。所有站点内容 `private, no-store`。

本地修改或通过测试不代表线上已经加密闭门。部署须再次获得用户明确批准；上线时要禁用/撤销旧 Service Worker、清理已有公开缓存并检查旧版本和带标签候选 URL。浏览器已经保存的离线文件无法由新版本撤回。以后任何环境的额外静态服务器/CDN也必须有相同门禁，不能直接公开场景包。

`promote` 现在只切流量，不修改 IAM、不自动加 `allUsers`，新建网关默认私有。每次 `up` / `promote` / `verify` 均读取实际 IAM 来决定冒烟是否带身份令牌，不把历史 `OPENED` 标记当成当前公开状态或公开授权。部署状态目录中 `privacy-lock.json` 存在且 IAM 仍公开时直接停止；本脚本从不删除该锁。恢复匿名入口须用户另行明确批准并在密码门禁和匿名资源拒绝都验证后单独执行。回滚到不含密码门禁的旧版本前必须保持 Cloud Run IAM 私有。

访问状态必须成功查到：服务列表、IAM 策略或身份令牌查询失败均停止，不能把失败当作私有。只有成功的服务列表空结果才表示服务尚不存在，并且仅首次 `up` 前允许。除 `allUsers` / `allAuthenticatedUsers` 外，也检查关闭 invoker IAM 的标志；任一存在即视为公开。`promote` 的匿名门禁最多重试六次，必须明确通过一次才能继续完整冒烟和写入 `DEPLOYED`；失败会停止并保持隐私锁。

### 本机受保护的开发预览

先启动本地 PostgreSQL 并完成 `pnpm --filter @zoujin/web build`，再在仓库根运行 `uv run python infra/deploy/local-preview.py`。脚本只监听 `127.0.0.1:8091`（内部叙事者 `8092`），用实际网关发 `apps/web/dist`，同时启用整站密码和邀请码；不使用 Vite 静态入口。假模型不会调用外部模型服务；游玩记录只来自独立的本地 `zoujin_home_preview` 数据库，不预填结局。

密码和本地邀请码自动生成到 `~/.zoujin/local-previews/h-1/credentials.json`（目录 0700、文件 0600），不会打印或放进命令行。可在本机编辑器打开该文件取得凭证。再次启动复用本地账号和进度；Ctrl-C 关闭两个进程但不删数据。`--prepare-only` 只准备本地库和凭证。启动时复用部署场景包检查，将每个 `assets/scenes/*/build` 映射到专用包目录并配置网关；仅顶层生成器 `note` 的差异不视为包结构变化，文件、贴图、inputs 的校验保持不变。替换前端 dist 后刷新即可；场景包变化后须重启以重新计算 manifest 版本。这个入口只用于开发审查，不能证明线上模型或真人账户的体验已通过。
