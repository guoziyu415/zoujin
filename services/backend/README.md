# services/backend

后端：一个 Python 包 `zoujin_backend`，里面有网关、叙事者和 mock 服务三个入口，部署时是两个 Cloud Run 服务（dev-plan 2.1）。后端负责。设计见 `docs/backend/`。

## mock 服务（B-1）

给前端离线开发和前端 CI 的端到端测试用：同一个源上提供 api-contract 的 REST 和 WebSocket，按剧本回放会话。不用数据库、不调模型、不需要任何凭证。

```sh
uv run zoujin-mock                 # http://127.0.0.1:8787，默认剧本「导览」
uv run zoujin-mock --speed 0       # 不等待（CI）
uv run zoujin-mock --scenario confirm --allow-origin http://localhost:5173
docker compose up mock             # 同一个程序，在容器里
```

- 邀请码 `mock`。会话 Cookie 是 `zj_session`，本地 http 下不带 `Secure`。
- 前端最好经开发服务器的代理和 mock 同源；不同源时用 `--allow-origin` 放行开发服务器的 Origin（改数据的 REST 和 WebSocket 握手都查 Origin，第 0 节）。
- 发出的每条消息和响应都先用 `packages/contracts` 生成的 pydantic 类型构造、再按 JSON Schema 校验，不过就不发并在终端报错。
- 剧本和写法：`fixtures/sessions/README.md`。REST 的固定数据和 `/__mock/*` 控制接口：`fixtures/mock/rest/README.md`。
- 代码：`src/zoujin_backend/mock/`（`rest.py` REST，`ws.py` 握手和协议上固定的回应，`live.py` 剧本推进，`state.py` 一局的状态，`schemas.py` 自检）。不 import 数据库和叙事者的代码。
- 测试：`tests/test_mock.py` 起真的 uvicorn，用 Python 客户端在 `--speed 0` 下跑完全部剧本，再按 0.04 倍的时间跑一遍导览（打断、作废、确认、结局的时序和服务端消息的覆盖检查），外加 REST 的 16 个接口和控制接口。

## 网关和叙事者（B-0）

骨架：账号和邀请码、REST（第 1 节）、WebSocket（第 2 节）、叙事者的单事务提交、重放。线程和 CI 里模型只用假的和回放（`ZJ_MODEL=fake`，默认；`replay` 读 `fixtures/model-replays`），Live 一律是假的。真文本模型的客户端见下面「叙事者流水线（B-2）」，只在 zg 的 Mac 上跑。

```sh
docker compose up gateway          # db、建表、narrator、gateway；网关 http://127.0.0.1:8001
```

不用容器时（要一个 PostgreSQL，`docker compose up db` 就有）：

```sh
export DATABASE_URL=postgresql://zoujin:zoujin@127.0.0.1:5432/zoujin ZJ_DEV=1
uv run alembic -c services/backend/alembic.ini upgrade head
uv run zoujin-narrator             # 127.0.0.1:8002，只给网关调
uv run zoujin-gateway              # 127.0.0.1:8001
uv run zoujin-admin invite create --count 3   # 明文只打印这一次，库里只存哈希
uv run zoujin-admin replay pt_…    # 用事件重建世界状态，和缓存比：一样退出 0，不一样 1，没有这局 2
```

- 环境变量：`DATABASE_URL`（必需）、`ZJ_MODEL`（`fake` / `replay`）、`ZJ_DEV=1`（Cookie 不带 `Secure`；narrator 不查 OIDC，只在本机用）、`ZJ_NARRATOR_URL`（默认 `http://127.0.0.1:8002`）、`ZJ_ALLOW_ORIGINS`（同源以外放行的 Origin，逗号分隔）、`ZJ_SPEED`（假 Live 的间隔倍数，0 = 不等）、`ZJ_WORLD`（开新局用的 world.json 的绝对路径，没设是 `worlds/hashire-merosu/1.0.0-draft`；已有的局按开局时锁定的版本；`eval_api` 每次 `setup()` 都读）。
- 网关收到 SIGTERM：给每条连接发 `goaway`，再以 1012 关闭，然后退出。叙事者提交后 `NOTIFY zoujin_commit`，网关 `LISTEN` 后从库里读这局新的事件推给连着的人。
- 日志和 Trace 只写 ID 和计数，不写原话（data-design 第 8 节）。
- 代码：`gateway/`（`auth.py` 邀请码和会话，`rest.py`，`ws.py`，`hub.py` 收提交通知，`core.py` 组装推送），`narrator/`（`core.py` 领任务、单事务提交，`pipeline.py` 流水线，`rules.py` 第 3 步的规则，`view.py` 发给模型的状态和人物，`app.py` 内部接口），`db/`（表、迁移、事件行，`store.py` 写库的小函数），`models/`（假模型、回放、真客户端、账本、提示），`eval_api.py`（评测入口），`s2.py`（S-2 的运行脚本），`trace.py`（Span），`admin.py`。

## 叙事者流水线（B-2）

一轮对话（语音的转写，或一条 `text`）走 backend-design 2.4：分流 → 提取 → 第 3 步确定性规则（R1〜R7，`narrator/rules.py`，和 `evals/s2_check.py` 的 `judge()` 对照）→ 第 4 步模型检查 → 改写、降级或拒绝 → 单事务提交。

- 时限：分流 5 秒，提取、检查、改写各 15 秒。超时、输出不过 Schema、调用失败都重发一次；第二次还不行，分流当「可能」，其余的这一轮只提交时钟事件、候选丢弃，`turns_timed_out` 加一。429（`RateLimited`）和到上限（`BudgetStop`）不重发，整轮放回队列、往上抛。
- 提取标了要确认、又不可逆的候选（让节拍 `prevented` / `altered`，改人质或玩家的身份处境）先丢掉（B-4 才有确认），`candidates_confirm_dropped` 加一。
- `playthrough_metrics` 多了各类提示的花费和这些计数：分流跳过、超时降级、改写、降级、拒绝、因要确认而丢弃（迁移 `0002_b2_metrics`）。
- 提示：`models/prompts.py` 定义 Schema 和版本号，正文在 `models/prompt_texts/*.txt`。改了正文版本号就变，回放随之过期（`fixtures/README.md`）。
- Span（`trace.py`，data-design 第 8 节）：每次调文本模型一个，属性只有白名单里的 ID、计数、规则名和耗时，写进日志 `zoujin.trace`。

### 真模型（只在 zg 的 Mac 上，PM 通知之后）

```sh
uv sync --all-packages --extra real      # google-auth；CI 的 lint 任务也装它，好让 mypy 查真客户端
```

- `ZJ_MODEL=real`：Vertex AI 上的 Gemini，走 REST，认证用 Mac 上 gcloud 登录的应用默认凭证，没有 API Key。项目 ID 和地区**只**从 `ZJ_VERTEX_PROJECT`、`ZJ_VERTEX_LOCATION` 读，没设就退出、不发请求；不用 gcloud 的默认项目。项目 ID 不进日志、Trace、回放和账本。
- 账本和上限：`ZJ_LEDGER`（Google 那本账，一行一次调用，和 E-0 同一个文件）、`ZJ_MAX_GOOGLE_USD`（总上限，比的是账本里的累计）、`ZJ_MAX_ITEM_USD` 和 `ZJ_LEDGER_ITEM`（单项的上限和记在哪一项下；单项上限把同一项的 Google、Claude 两本账合起来算，Claude 的行由数据的运行器写）。调用前按预计花费判，到了就 `BudgetStop`；被时限取消的调用按预计花费记账，输出不合格的按实际花费记账，这两种也按同一个数记进这一轮的花费（`playthrough_metrics`）。
- `ZJ_RECORD_REPLAYS=<目录>`：fake 和 real 的每次调用按回放格式录一行（`<目录>/<提示类型>.jsonl`）。`ZJ_REPLAYS=<目录>` 让 `replay` 读别的目录（例：留出集的回放，不进仓库）。

### S-2 的运行脚本

```sh
uv run zoujin-s2 evals/s2/s2_dev.jsonl --out out/s2-dev            # 假模型，不花钱
uv run zoujin-s2 <标注集.jsonl> --out <目录> --resume                # 中断后接着跑
```

- 每条起局、调 `check(model_checks="all")`，跑 `--runs` 次（默认 3），结果逐行写 `results.jsonl`，跑完或停下写 `report.json` 和 `report.md`（只有条目 ID、判定、规则、理由和 trace ID，不抄原话和摘要）。
- 真模型要同时有 `ZJ_MODEL=real`、`ZJ_EVAL_LIVE=1`、`ZJ_LEDGER`、项目和地区、`--max-item-usd`、`--max-google-usd` 和 `--confirm`；少一样只打印预计花费和命令，不调用。到上限或第一个 429 退出码 3，回放缺失或配置不对退出码 2。
- 没有默认的标注集路径。留出集的规矩见 `docs/tasks/m2/B-2.md`。

## 预录句（B-6）

```sh
uv run zoujin-voice                                        # 假模型：合成的声音，看流程和输出，不花钱（要 ffmpeg）
uv run zoujin-voice --resume out/b6/<时间> [--only <键> …]  # 接着跑；只重读某几句
```

- 源文件 `voice/<book>.json`：每个说话人的声音（D-025）、人物说明 `direction`、人物的 6 句（ux-design 16.2）、`cues`、场面说明 `scenes` 和读音替换 `readings`；固定演出的句子和 `arrival_capped` 的文字从世界模型读。换声音改这里，再 `--only` 重跑那个人物。
- 每句读 3 遍（3 条会话），自动检查（长度、截断、补转写对原文）后挑一遍，裁头尾静音、限峰值、转 AAC。输出在 `out/b6/<时间>/release/`：`.m4a`、`voices.json`（manifest 的 `characters[].prerecorded` 和 `setPieceVoices` 两块）、`audit.md`、`ref/`，另打 zip、打印 sha256。
- 真模型（只在 Mac 上）：`ZJ_MODEL=real`、`ZJ_LEDGER`、`ZJ_VERTEX_PROJECT`、`ZJ_VERTEX_LOCATION`（补转写）、`--max-google-usd` 和 `--confirm`；Live 的地区默认 us-central1（`ZJ_LIVE_LOCATION` 换）。少一样只打印预计花费和命令。这一次跑的上限 `--max-usd` 默认 $1。到上限、第一个 429 或连接失败退出码 3（`--resume` 接着跑）。
- 跑完：release 的 zip 和 sha256 交协调拷到 `/mnt/project-files/app-team/backend/b6/`，后端核对 sha 以后交 UX 量、zg 听（B-6 卡「真的生成」）。
- mock 的 manifest 读 `assets/voice/<book>/voices.json`（有的话），`/assets/voice/<book>/<文件>` 只发清单里的文件。

## 测试

```sh
uv run pytest                      # 不要数据库的；要数据库的跳过
docker compose up -d db
DATABASE_URL=postgresql://zoujin:zoujin@127.0.0.1:5432/zoujin_test uv run pytest -m db
```

- `db` 标记的测试用库 `zoujin_test`：会话开始时建表，每个测试开头清空全部表，别指向开发库。CI 的 `db` 任务跑同一组。
- `tests/test_narrator.py`：最小剧本、每一步注入失败后重试、第三次失败、两轮同一局、两局互不阻塞、过期结果重新检查、重放、提取两次超时只提交时钟、日志和 Span 里没有原话。
- `tests/test_rules.py`（不要库）：第 3 步对照 `judge()`、每条规则的正反例、不在场的人物、切片（切片世界模型进 main 之前跳过）。`tests/test_pipeline.py`（不要库）：流水线各条路、时限、范围、请求里的别名、Span。
- `tests/test_vertex.py`（不要库、不联网）：真客户端换上假的传输层，查请求形状、花费、账本和上限、429、回放格式、项目 ID 不外漏。`tests/test_s2.py`：S-2 脚本的报告、`--resume`、到上限、回放、真模型的开关。
- `tests/test_gateway.py`：起真的 narrator 和 gateway 进程，客户端按契约的 Schema 收发：语音一轮再文字一轮、断线重连补发、登录和 Cookie、Origin、别人的局、4009、幂等键、SIGTERM。
- `tests/test_eval_api.py`：评测入口（S-2 的 10 条起点和 `check`、E-0 的替身逐事件比、没做的步骤、回放）。回放 fixture 过期时的重写命令见 `fixtures/README.md`。
- E-0 的运行器经 `eval_api` 跑，也要 `DATABASE_URL`：`uv run zoujin-eval --mode fake --deterministic-only`。
