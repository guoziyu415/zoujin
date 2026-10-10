# 契约的例子

```
examples/
  valid/data/<类型>/*.json     合法例子，必须过
  invalid/data/<类型>/*.json   反例，必须不过
```

`<类型>` 是 Schema 里 `$defs` 的名字（`Event`、`Effect`、`Ending`…），测试按它找到对应的定义来校验。接口的例子（C-1）放 `valid/api/`、`invalid/api/`。

## 数据契约（C-2）

**合法例子**：每个主类型至少 1 个，`Effect` 的 8 种各 1 个，另有 `Promise`、`RunFact`、`Relationship`、`CharacterEnding`。`WorldModel` 不另写例子，测试直接校验 `worlds/*/*/world.json`。

contracts.md 第 6 节的 JSON 原样抄进来了：`Fact/fact-promise.json`、`Beat/beat-11-wedding.json`、`CausalEdge/edge-10-11.json`、`Event/say-mock-king.json`、`Event/promise-made.json`。补了这些：

- 省略号的 ID（`ev_01J…`、`pt_01J…`、`turn_01J…`、`utt_01J…`、`prm_01J…`）补成完整的 26 位 ULID；`idempotencyKey` 跟着补。
- `say-mock-king.json` 去掉了 `"reason": null`：类型是 `reason?: string`，不允许 `null`。contracts.md 第 6 节同一个 PR 里也去掉了。
- 第二个事件在文档里只是片段，补成完整的 Event：`schemaVersion: "1.1"`、`eventId`、`playthroughId`、`turnId`、`idempotencyKey`、`worldModelVersion`、`recordedAt`；`checker` 的 `rules@1.1+…` 补成 `rules@1.1+gemini-3.8-flash`。

例子里的日语用 contracts.md、`world.json` 里已有的句子，或中性的自写句子；没有真实的人名和个人信息。

**反例**：每个都是某个合法例子只改一处。`tests/test_data_schemas.py` 的 `INVALID_BECAUSE` 写明每个反例该在哪个位置、因为哪个关键字被拒，新加反例要在那里加一行，免得它因为别的原因被拒、测不到想测的东西。
