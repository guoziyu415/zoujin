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

骨架：账号和邀请码、REST（第 1 节）、WebSocket（第 2 节）、叙事者的单事务提交、重放。模型只有假的和回放（`ZJ_MODEL=fake`，默认；`replay` 读 `fixtures/model-replays`），Live 一律是假的，没有真模型的调用代码。

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

- 环境变量：`DATABASE_URL`（必需）、`ZJ_MODEL`（`fake` / `replay`）、`ZJ_DEV=1`（Cookie 不带 `Secure`；narrator 不查 OIDC，只在本机用）、`ZJ_NARRATOR_URL`（默认 `http://127.0.0.1:8002`）、`ZJ_ALLOW_ORIGINS`（同源以外放行的 Origin，逗号分隔）、`ZJ_SPEED`（假 Live 的间隔倍数，0 = 不等）。
- 网关收到 SIGTERM：给每条连接发 `goaway`，再以 1012 关闭，然后退出。叙事者提交后 `NOTIFY zoujin_commit`，网关 `LISTEN` 后从库里读这局新的事件推给连着的人。
- 日志和 Trace 只写 ID 和计数，不写原话（data-design 第 8 节）。
- 代码：`gateway/`（`auth.py` 邀请码和会话，`rest.py`，`ws.py`，`hub.py` 收提交通知，`core.py` 组装推送），`narrator/`（`core.py` 领任务、检查、单事务提交，`rules.py` 检查规则，`app.py` 内部接口），`db/`（表、迁移、事件行，`store.py` 写库的小函数），`eval_api.py`（评测入口），`admin.py`。

## 测试

```sh
uv run pytest                      # 不要数据库的；要数据库的跳过
docker compose up -d db
DATABASE_URL=postgresql://zoujin:zoujin@127.0.0.1:5432/zoujin_test uv run pytest -m db
```

- `db` 标记的测试用库 `zoujin_test`：会话开始时建表，每个测试开头清空全部表，别指向开发库。CI 的 `db` 任务跑同一组。
- `tests/test_narrator.py`：最小剧本、每一步注入失败后重试、第三次失败、两轮同一局、两局互不阻塞、过期结果重新检查、重放。
- `tests/test_gateway.py`：起真的 narrator 和 gateway 进程，客户端按契约的 Schema 收发：语音一轮再文字一轮、断线重连补发、登录和 Cookie、Origin、别人的局、4009、幂等键、SIGTERM。
- `tests/test_eval_api.py`：评测入口（S-2 的 10 条起点和 E-0 的替身逐事件比、没做的步骤、回放）。回放 fixture 过期时的重写命令见 `fixtures/README.md`。
- E-0 的运行器经 `eval_api` 跑，也要 `DATABASE_URL`：`uv run zoujin-eval --mode fake --deterministic-only`。
