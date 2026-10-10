# 契约的例子

```
examples/
  valid/data/<类型>/*.json     合法例子，必须过
  invalid/data/<类型>/*.json   反例，必须不过
  valid/api/…                  接口的合法例子（C-1），目录规则见下面「接口」
  invalid/api/…                接口的反例（C-1）
```

`<类型>` 是 Schema 里 `$defs` 的名字（`Event`、`Effect`、`Ending`…），测试按它找到对应的定义来校验。

全部合法例子（数据和接口）还要经生成的 pydantic 模型解析再导出，和原文件相同（C-1，`tests/test_examples.py`）。

## 数据契约（C-2）

**合法例子**：每个主类型至少 1 个，`Effect` 的 8 种各 1 个，另有 `Promise`、`RunFact`、`Relationship`、`CharacterEnding`。`WorldModel` 不另写例子，测试直接校验 `worlds/*/*/world.json`。

contracts.md 第 6 节的 JSON 原样抄进来了：`Fact/fact-promise.json`、`Beat/beat-11-wedding.json`、`CausalEdge/edge-10-11.json`、`Event/say-mock-king.json`、`Event/promise-made.json`。补了这些：

- 省略号的 ID（`ev_01J…`、`pt_01J…`、`turn_01J…`、`utt_01J…`、`prm_01J…`）补成完整的 26 位 ULID；`idempotencyKey` 跟着补。
- `say-mock-king.json` 去掉了 `"reason": null`：类型是 `reason?: string`，不允许 `null`。contracts.md 第 6 节同一个 PR 里也去掉了。
- 第二个事件在文档里只是片段，补成完整的 Event：`schemaVersion: "1.1"`、`eventId`、`playthroughId`、`turnId`、`idempotencyKey`、`worldModelVersion`、`recordedAt`；`checker` 的 `rules@1.1+…` 补成 `rules@1.1+gemini-3.8-flash`。

例子里的日语用 contracts.md、`world.json` 里已有的句子，或中性的自写句子；没有真实的人名和个人信息。

**反例**：每个都是某个合法例子只改一处。`tests/test_data_schemas.py` 的 `INVALID_BECAUSE` 写明每个反例该在哪个位置、因为哪个关键字被拒，新加反例要在那里加一行，免得它因为别的原因被拒、测不到想测的东西。

## 接口（C-1）

下面的路径都在 `valid/api/`、`invalid/api/` 下面。目录决定对哪个 Schema 校验：

| 路径                                                              | 对谁校验                                                                       |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `ws/client/<type>/*.json`、`ws/server/<type>/*.json`              | 那一种消息，以及整个 `ClientMessage` / `ServerMessage` 联合；目录名就是 `type` |
| `rest/<接口文件名>/<request \| query \| params \| 状态码>/*.json` | `schemas/api/rest/<接口文件名>.schema.json` 的 `x-endpoint` 里写的那个 Schema  |
| `<文件>/<$defs 名>/*.json`（例 `error/ErrorResponse/`）           | `schemas/api/<文件>.schema.json` 的那个 `$defs` 条目                           |

每种 WebSocket 消息、每个有响应体的 REST 状态码和每个请求体，都至少有一个合法例子（测试会查）。反例每个只错一处，`tests/test_examples.py` 的 `INVALID_BECAUSE` 写明每个反例该在哪个位置、因为哪个关键字被拒，新加反例要在那里加一行。

### 从 api-contract 抄来的例子和补上的地方

文件名带 `doc-<节号>` 的是 `docs/backend/api-contract.md` 里的 JSON 例子原样抄来的。文档里的 `…` 按下面补成合法值，其他字段没动。

- **ID**：`pt_01J…`、`turn_…`、`ev_…`、`ev_A`、`ev_B`、`mem_…`、`prm_…`、`rev_…`、`end_…`、`draft_…`、`plan_…`、`u_01J…` 都补成「前缀 + `01K7AZ` + 20 位数字」的 ULID（例 `ev_01K7AZ00000000000000000041`）。`clientMsgId` 的 `…` 补成 UUID。
- **2.1 manifest**：`roles[].summary` 补「シラクスの市に着いたばかりの旅の者。」；`prerecorded` 的 `"…"` 补成完整的 3 句相槌（うむ。／ああ。／なるほど。）、2 句听不清、1 句等一下，每句带 `url`、`text`、`durationMs`。
- **2.2 开局**：201 的 `snapshot` 用 2.3 的例子。
- **2.8 结局**：`world.epilogue[].sentence` 补「メロスは日没の直前に刑場へ駆け込んだ。」；`characters[0].yours[].sentence` 补「工房の火を落とさずに、メロスを待ち続けた。」；`card.characterLines` 的 `"…"` 补成两句（数据契约 5 节要 2〜3 句，文档的例子只有一句）。
- **3.4 commit**：`events` 用 2.4 的事件（序号改成 44）；`patch.actions.add` 补一个「様子を見る」的动作；`reveal.chain` 用 2.6 的链。
- **3.11 幕末**：`act_ended.recapLines` 补到两行（正文写 2〜4 行，例子只有一行）。带 `enRoute` 的去处单独放在 `doc-3.11-en-route.json`，幕号和 `recapLines` 是补的。`act_transition.snapshot` 用 2.3 的快照改成第二幕开头。
- **第 4 节 welcome**、**3.13 结局演出**、**第 5 节错误**、**2.3〜2.7 的其余例子**：只补了 ID。

不是 `doc-` 开头的例子是自己写的，日语只用文档里已有的句子或中性的句子，不含真实的人名和个人信息。
