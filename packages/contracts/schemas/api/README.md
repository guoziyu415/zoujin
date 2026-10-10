# 接口的 JSON Schema（C-1，后端负责）

`docs/backend/api-contract.md` v1.0 的全部传输形状。数据字段以 `schemas/data/`（C-2，数据负责）为准，这里只引用。

| 文件                    | 内容                                                                                                                                       |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `common.schema.json`    | 几处共用的形状：快照（2.3）、事件的可见投影（2.4）、因果链（2.6）、记忆和约定（2.7、3.4）、幕末（3.11）、结局演出（3.13）、续玩（第 4 节） |
| `ws/client.schema.json` | 3.2 的 17 种消息，整体是按 `type` 区分的 `oneOf`（`ClientMessage`）                                                                        |
| `ws/server.schema.json` | 3.3 的 30 种消息（`ServerMessage`）                                                                                                        |
| `rest/*.schema.json`    | 每个接口一个文件，`x-endpoint` 写方法、路径、要不要 `Idempotency-Key`、路径参数、查询参数、请求体和每个状态码的响应（`null` = 没有响应体） |
| `error.schema.json`     | 第 5 节的错误                                                                                                                              |
| `telemetry.schema.json` | `POST /v1/telemetry` 的请求体（data-design 9.3，字段由数据定）                                                                             |
| `binary.json`           | 3.1 的二进制帧常量（不是 Schema；生成 `binary.ts` / `binary.py`）                                                                          |

## 写法

- JSON Schema 2020-12；`$id` 是相对 `schemas/` 的路径，`$ref` 只用相对引用。
- 对象一律 `additionalProperties: false`，不用 `allOf`（测试会查）。以后加字段先改这里。
- 关死只约束写的一方：服务端发出的消息和响应、mock、前端发出的消息。读的一方按 api-contract 第 0 节忽略不认识的字段、消息类型和枚举值，运行时不拿 Schema 校验对方的消息（Service Worker 缓存的旧前端会连到新服务端）。生成的 pydantic 模型是 `extra="forbid"`，服务端解析客户端消息时先去掉不认识的字段再校验（B-0）。
- 整个用数据类型的地方 `$ref` 到 `data/` 的 `$defs`；接口在数据类型上加减了字段的（结局、事件的可见投影、記憶帳），写成接口自己的对象，共有的字段用 JSON 指针引用数据那边的字段，加减了哪些字段在 `tests/test_alignment.py` 里列着。
- `$defs` 的名字就是生成的类型名，和 `data/` 的不能重名。
- 只在非生产环境有的（`hello.debug`、`fakeVoice`、`event_rejected`、`POST /v1/test/…`）照样写，`description` 里标「非生产」。
- 文档没写清、C-1 评审时定下来的地方，`description` 末尾标「（C-1 评审定）」；api-contract v1.0.1 已把它们写进正文。

改完跑 `uv run contracts-gen` 重新生成类型，再跑 `uv run pytest packages/contracts`。
