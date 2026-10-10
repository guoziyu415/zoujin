# 数据契约的 JSON Schema

`docs/data/contracts.md` 1.7 的 39 个类型，写成 JSON Schema 2020-12（C-2，数据负责）。改字段先改 contracts.md，再改这里；契约测试会把两边逐个类型、逐个顶层字段对一遍。

| 文件                      | 主类型        | `$defs`                                                                    |
| ------------------------- | ------------- | -------------------------------------------------------------------------- |
| `common.schema.json`      | —             | `Cite`，加公共定义：`SchemaVersion`、`StoryTime`、`RecordedAt`、各种 ID 等 |
| `playthrough.schema.json` | `Playthrough` | `Playthrough`                                                              |
| `world-model.schema.json` | `WorldModel`  | 世界模型的 26 个类型                                                       |
| `event.schema.json`       | `Event`       | `Event`、`Effect`、`CheckResult`                                           |
| `utterance.schema.json`   | `Utterance`   | `Utterance`                                                                |
| `world-state.schema.json` | `WorldState`  | `WorldState`、`RunFact`                                                    |
| `memory.schema.json`      | `MemoryItem`  | `MemoryItem`、`Relationship`、`Promise`（标题 `StoryPromise`）             |
| `ending.schema.json`      | `Ending`      | `Ending`、`CharacterEnding`                                                |

## 给写的一方用

这套 Schema 给**写数据的一方**严格校验用：CI 校验世界模型和评测集，B-0 写库前校验事件和记忆。对象一律关死（`additionalProperties: false`），多一个字段就不过。

读的一方（前端）不在运行时拿它校验服务端发来的数据。契约只做加法：1.6 加一个可选字段、`Activity` 加一个值的时候，旧客户端不能因此报错。前端照 contracts.md 处理：不认识的 `Activity` 当 `idle`，不认识的字段不管。F-0 的 e2e 按 Schema 校验 mock 发的消息，那是在查 mock 这个写的一方，不矛盾。

## 写法

- `$id` 是相对路径（`data/event.schema.json`），`$ref` 都是相对引用，不写域名，测试不联网。
- 运行时 ID 是前缀加 ULID（`ev_` 加 26 位大写 Crockford base32）；世界模型的 ID 是类型前缀加小写 slug（`char.melos`、`exit.1.road`），世界结局的 ID 不带前缀（`canon-reunion`）。只用 `pattern`，不用 `format`。
- 故事时间 `t` 和故事分钟（`dt`、路程、情境动作的耗时）是整数；`melosMinutes` 带正负号。
- 子结构不另起 `$defs`，接口那边要原样复用时用 JSON 指针引用（例：`ending.schema.json#/$defs/Ending/properties/card`）。
- `sampleLines` 在契约里是 `Cite & { since?, until?, when? }`，这里写成关死的普通对象，`source` / `para` / `quote` 用 JSON 指针引 `Cite` 的字段，不用 `allOf`。
- Schema 只管形状。`quote` 是原文的精确子串、事件按 `seq` 的 `t` 不递减、`world.outcome` 等于按 2.9 判出的那一类、变量改成的值满足 `valueRequires`（1.6），这些跨字段的规矩在 `build_world`、worldsim、B-0 和结局的校验里。
- 按版本加的必填写成 `if` / `then`，不改类型里的可选：`Ending` 的 `schemaVersion` 不是 1.0〜1.5 时，`world.title`、`player.didForYou` / `youDid`、`characters`、`card` 必写（1.6，C-17）。`if` 里列的是旧版本，以后加 1.7 不用改它。生成的 pydantic 模型不管 `if` / `then`，B-0 写库前按 Schema 校验时才查。

## 以后改

1.5 已冻结，以后只做加法：新增可选字段走 1.6、1.7…，`SchemaVersion` 加一个值，contracts.md 的变更记录写一行，这里同一个 PR 改。枚举加值也算加法：前端按值渲染的枚举（`Activity`、`MemoryItem.kind` / `via`、`StoryPromise.status`、`Event.type`、`Affordance.kind` 等）以后可能加值，读的一方都要留默认分支（`Activity` 不认识的按 `idle`）。去掉值、改名、收紧约束不算加法。改 `packages/contracts` 要后端、前端、数据三方评审（dev-plan 2.3）。

例子在 `packages/contracts/examples/`，测试在 `packages/contracts/tests/test_data_schemas.py`。
