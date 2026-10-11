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
- 提取标了要确认、又不可逆的候选（让节拍 `prevented` / `altered`，改人质或玩家的身份处境）：对话里的存成草稿、问玩家（B-4，见下）；动作里的丢掉，`candidates_confirm_dropped` 加一。
- `playthrough_metrics` 多了各类提示的花费和这些计数：分流跳过、超时降级、改写、降级、拒绝、因要确认而丢弃（迁移 `0002_b2_metrics`）。
- 提示：`models/prompts.py` 定义 Schema 和版本号，正文在 `models/prompt_texts/*.txt`。改了正文版本号就变，回放随之过期（`fixtures/README.md`）。
- Span（`trace.py`，data-design 第 8 节）：每次调文本模型一个，属性只有白名单里的 ID、计数、规则名和耗时，写进日志 `zoujin.trace`。

### 真模型（只在 zg 的 Mac 上，PM 通知之后）

```sh
uv sync --all-packages --extra real      # anthropic、google-auth；CI 的 lint 任务也装它，好让 mypy 查真客户端
```

B-8 起每种提示走哪家、哪一档写在 `config.TEXT`：`reply`（评测里替 Live 当人物）走 Google，其余走 Claude（D-028）。`ZJ_MODEL=real` 按这个分给两个客户端；只调 Claude 的跑（S-2、小测）不要求 Vertex 的环境变量。

- **Claude**（`models/claude.py`）：zg 的 Anthropic API 额度。Key 只从钥匙串读进**这一个终端**的环境变量，SDK 自己读，不进日志、Trace、回放、账本和异常消息；模型 ID 也只在环境变量里（仓库只写档名加版本），认出来的档名加版本和 `config.TEXT` 不一样就不调：

  ```sh
  export ANTHROPIC_API_KEY="$(security find-generic-password -s zoujin-claude -w)"
  export ZJ_CLAUDE_HAIKU=… ZJ_CLAUDE_SONNET=…      # 模型 ID，不写进仓库
  export ZJ_LEDGER=~/.zoujin/ledger.jsonl ZJ_MAX_CLAUDE_USD=100   # D-029：Claude 那本账跨所有跑次累计
  ```

  临时换档量 Haiku（S-085 ③）：`ZJ_TEXT_MODELS=check=haiku-5.5`（逗号分开可以换几种；只能换 Claude 的，思考和 effort 照旧；回放的键、账本、`check.checker` 跟着变）。
- **Google**（`models/vertex.py`）：Vertex AI 上的 Gemini，走 REST，认证用 Mac 上 gcloud 登录的应用默认凭证，没有 API Key。项目 ID 和地区**只**从 `ZJ_VERTEX_PROJECT`、`ZJ_VERTEX_LOCATION` 读，真要调 Google 那几种时才查，没设就退出、不发请求；不用 gcloud 的默认项目。项目 ID 不进日志、Trace、回放和账本。上限 `ZJ_MAX_GOOGLE_USD`（D-027）。
- 账本（`zoujin_llm.Ledger`，和数据的评审员共用）：两本账同一个文件，一行一次调用，带 `provider` 和 `use`（叙事者各步是 `product`，评审员、AI 玩家是 `eval`）。总上限只算自己那家；`ZJ_MAX_ITEM_USD` 和 `ZJ_LEDGER_ITEM` 是单项的上限和记在哪一项下，单项把同一项的两本账合起来算。调用前按预计花费判，到了就 `BudgetStop`；被时限取消的调用按预计花费记账，输出不合格（含 Claude 的 `refusal`、`max_tokens`）的按实际花费记账，这两种也按同一个数记进这一轮的花费。没提交的那几次（作废的一轮、失败后重来的）也记进这一局的 `playthrough_metrics`。
- 429、529：Mac 上的跑第一次就停（退出码 3）；服务玩家的叙事者（`narrator/app.py`）当作这一次失败，按时限的规则处理（`Pipeline.on_rate_limit`）。
- `ZJ_RECORD_REPLAYS=<目录>`：fake 和 real 的每次调用按回放格式录一行（`<目录>/<提示类型>.jsonl`，键是 `<provider>|<模型>|<提示版本>|<请求的 sha256>`）。`ZJ_REPLAYS=<目录>` 让 `replay` 读别的目录（例：留出集的回放，不进仓库）。

### S-2 的运行脚本

```sh
uv run zoujin-s2 evals/s2/s2_dev.jsonl --out out/s2-dev            # 假模型，不花钱
uv run zoujin-s2 <标注集.jsonl> --out <目录> --resume                # 中断后接着跑
```

- 每条起局、调 `check(model_checks="all")`，跑 `--runs` 次（默认 3），结果逐行写 `results.jsonl`，跑完或停下写 `report.json` 和 `report.md`（只有条目 ID、判定、规则、理由和 trace ID，不抄原话和摘要）。
- 真模型要同时有 `ZJ_MODEL=real`、`ZJ_EVAL_LIVE=1`、`ZJ_LEDGER`、Claude 的 Key 和两档的模型 ID、`--max-item-usd`、`--max-claude-usd` 和 `--confirm`；少一样只打印预计花费和命令，不调用。到上限或第一个 429、529 退出码 3，回放缺失或配置不对退出码 2。Haiku 再量一遍：同样的命令前面加 `ZJ_TEXT_MODELS=check=haiku-5.5`，换一个 `--out`。
- 没有默认的标注集路径。留出集的规矩见 `docs/tasks/m2/B-2.md`。

### 小测（B-8，`zoujin-probe`）

量每种走 Claude 的提示的首字、全部的延迟和 token。请求从假模型录下的回放里取（不碰留出样本）：

```sh
docker compose up -d db
ZJ_RECORD_REPLAYS="$PWD/out/probe-requests" DATABASE_URL=… uv run zoujin-eval --mode fake --deterministic-only --slice --quiet --out out/probe-e0
uv run zoujin-probe --requests out/probe-requests --out out/probe --max-item-usd 2 --max-claude-usd 100    # 只打印预计花费和命令
```

- 每种取 `--per-kind` 个（默认 20；同样的请求只算一个，不够就轮着用），串行调，记 Claude 那本账、item 是 `b8-probe`。zg 点头后在打印出来的命令后面带 `--confirm`，环境变量照上面设。
- 第一个 429、529 或到上限就停（退出码 3），别的 HTTP 错误跳过这种提示剩下的。结果 `probe.jsonl`、`summary.json` 只有数字（种类、档名加版本、毫秒、token、花费），交协调拷进项目文件夹。

## 作废和意图确认（B-4）

- 提交窗口：网关交给叙事者时写 `turns.commit_after`（`turn_complete`、或打算的定稿之后 3 秒，乘 `ZJ_SPEED`；速度 0 没有窗口）。叙事者判完等到这个时刻再提交，这期间 `turn_retract` 能把这一轮改成 `retracted`（`store.retract_queued`），叙事者提交时只认 `leased`，谁先拿到行锁谁算数。
- 还在连接内存里的一轮（人物还没说完）作废：停掉转发、写一行 `retracted`、不交给叙事者。对话的一轮作废以后重建这个人物的会话，新会话只带这条连接上最近几轮里没作废的（只在内存里）。
- 意图确认（`narrator/confirm.py`）：过了检查的要确认的候选存进 `drafts`（迁移 `0004_b4_confirm`），这一轮照常提交；网关推完那一轮的结果再反问、推 `confirm`、开计时（30 秒乘 `ZJ_SPEED`）。按钮、声音、超时都写一行 `kind: "confirm"` 的任务，叙事者重查以后提交或丢掉，推 `confirm_closed`。叙事者取任务前先给到期的草稿写超时的任务（断线时网关的计时不在）。
- 评测入口：`say(hold=True)` 先不提交，`retract(n)`、`confirm(answer)`（api-contract 第 7 节）。

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
- `tests/test_b4.py`：意图确认、评测入口的 hold 和作废、提交窗口、作废和提交同时来、不记原话、迁移 0004。`tests/test_gateway_b4.py`：网关和叙事者在测试进程里（后台线程的 uvicorn），查作废和重建（假 Live 收到的最近的对话）、识别改正、幕末的打算、确认的推送顺序、超时和重连。
- `tests/test_eval_api.py`：评测入口（S-2 的 10 条起点和 `check`、E-0 的替身逐事件比、没做的步骤、回放）。回放 fixture 过期时的重写命令见 `fixtures/README.md`。
- E-0 的运行器经 `eval_api` 跑，也要 `DATABASE_URL`：`uv run zoujin-eval --mode fake --deterministic-only`。
