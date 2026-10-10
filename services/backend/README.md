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
