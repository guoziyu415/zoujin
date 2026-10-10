# fixtures/mock/rest：mock 的 REST 固定数据（B-1）

mock 的 REST（`services/backend/src/zoujin_backend/mock/rest.py`）回这里的数据，发出前按 `packages/contracts/schemas/api/rest/` 校验，不过就回 500 并在终端报错。内容和 `fixtures/sessions/` 的导览是同一局：旅人告诉メロス王的事、帮老爺推车、答应做メロス的帮手、留在市里等到第三天的日落。

| 文件 | 接口（api-contract） | mock 另外做的 |
|---|---|---|
| `manifest/hashire-merosu.json` | `GET /v1/books/{bookId}/manifest`（2.1） | 文件名就是 `bookId`。预录台词和资源路径是示意，文件不存在 |
| `me.json` | `GET /v1/me`、登录的响应（1、2.0） | `activePlaythrough` 和剩余语音分钟按这个 Cookie 的局现填 |
| `snapshot.json` | 开局的快照（2.2、2.3） | 之后的快照 = 它加上推过的 `commit.patch` 和 `act_transition`；`lastSeq`、`pending`、`voice` 现填 |
| `timeline.json` | `GET …/timeline`（2.5） | `lastSeq` 现填 |
| `why.json` | `GET …/why`（2.6） | `target` 照 query；这一局推过的事件，`seq` 换成真的 |
| `memories.json` | `GET …/memories`（2.7） | 删过的记忆去掉；删了约定的记忆，那个约定变 `voided`，关系照删除时的响应 |
| `memory-impact.json` | `GET …/memories/{memoryId}/impact`（2.7） | 以记忆的名字为键；不认识的记忆回 404 |
| `memory-delete.json` | `DELETE …/memories/{memoryId}`（2.7） | 同上；删过的再删回 404；重建那个人物的会话（`session_preparing reason: rebuild`） |
| `ending.json` | `GET …/ending`（2.8） | 结局演出开始前 404，`ending_ready` 之前 202，之后 200 |

不靠固定数据的：`POST /v1/auth/login`（只认邀请码 `mock`，连错 5 次以后回 429）、`logout`、`POST /v1/playthroughs`（一个 Cookie 一局进行中的局，再开回 409）、`events`（推过的 `commit` 里的事件）、`DELETE /v1/playthroughs/{id}`（开着的连接以 4004 关闭）、`telemetry`（校验后丢掉）、`POST /v1/test/playthroughs/{id}/advance`（推一条只带时钟的 `commit`）。

占位符和剧本一样：`{{id:<前缀>:<名字>}}` 是这一局里这个名字的运行时 ID，和剧本共用，所以 `/memories`、`/ending` 引用的事件 ID 就是推过的那些。`{{playthroughId}}`、`{{userRef}}`、`{{memoryId}}` 由 mock 填。

## 控制接口（mock 专用，不进契约）

| 接口 | 做什么 |
|---|---|
| `GET /__mock/scenarios` | 现在的剧本和全部剧本名 |
| `POST /__mock/scenario {"name": …}` | 换剧本（见 `fixtures/sessions/README.md`） |
| `POST /__mock/expire-session` | 当前 Cookie 失效：之后 REST 回 401，WebSocket 以 4001 关闭（开着的也关） |
| `POST /__mock/drop` | 断开当前 Cookie 的连接，不发 `goaway`、没有关闭帧（客户端看到 1006），模拟断网 |
| `POST /__mock/reset` | 清空全部会话和局（端到端测试每个用例开头用） |
