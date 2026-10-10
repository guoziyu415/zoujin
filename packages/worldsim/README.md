# packages/worldsim

世界状态的共享规则库（W-1）：初始状态、应用 effects、到点的节拍、时间传播、结局分类。叙事者、评测和数据的工具都只用这一套规则。数据负责，后端评审。只用标准库。

| 目录                                 | 内容                                                                                                                                                                                                                   |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/zoujin_worldsim/sim.py`         | 一口气推演 `Sim`（`run` / `resume` / `arrival_delta` / `classify` / `value_requires`），从参考实现原样移植，开局状态按身份读                                                                                           |
| `src/zoujin_worldsim/incremental.py` | 逐事件推演：`initial_state` / `apply` / `settle` / `world_state` / `check_effects`，加上 `classify` / `predict` / `arrival_delta`                                                                                      |
| `reference/`                         | 参考实现 `worldsim.py`（R-0 从项目文件夹 `data/spikes/pipeline/` 原样搬来），是黄金文件的来源；同目录还有数据的工具 `build_world.py`、`review_sheet.py`、`check_evals.py`、`check_probes.py`，它们从包 import 推演规则 |
| `tests/golden/`                      | 参考实现生成的黄金文件和生成脚本 `gen_golden.py`；CI 重跑生成脚本查一致                                                                                                                                                |

## 逐事件推演怎么用

```python
from zoujin_worldsim import apply, check_effects, initial_state, role_of, settle

s = initial_state(world, "role.traveler")
drafts, s = settle(world, s, role_of(world, "role.traveler")["startT"])  # 开局前到点的节拍也写成系统事件
# 每一轮：先查候选事件，提交后 apply，再 settle 到新的时钟
problems = check_effects(world, s, event["effects"], event["origin"])
s = apply(world, s, event)
drafts, s = settle(world, s, s["t"])
```

- 状态 `SimState` 只由事件推出，能直接存成 JSON。`settle` 返回的状态就是把草稿依次 `apply` 的结果，所以从 `initial_state` 加事件日志重放得到同一个状态（契约 3.1）。
- 同一时刻先节拍、再期限、最后事件：先 `settle` 到事件的 `t` 再 `apply` 它，下一次 `settle` 不早于这个 `t`。
- 草稿是 `{event, beat, variant, reason, reasonCode}`：`event` 是契约 Event 的子集（`actor: "system"`、`origin: "schedule"`、`dt: 0`），B-0 补上 `eventId`、`seq`、`summary` 等再写库；`prevented` 的草稿带一句日语原因。
- 期限每局写一个系统事件（`type: "action"`），`onDeadline` 一条都不成立时 `effects` 为空：状态靠它记下期限结算过了。
- `check_effects` 按 `origin` 判：不是 `schedule` 的（叙事者的候选事件、导演事件）不能写 `{op: "beat", to: "happened"}`，也按 `StateVar.valueRequires`（契约 1.6）判。

## 改规则

规则要改先改 `reference/worldsim.py`，再跑 `python3 -I packages/worldsim/tests/golden/gen_golden.py` 重新生成黄金文件，然后改包，让 `pytest packages/worldsim` 重新全过。移植时发现像 bug 的地方不在移植里改，回参考实现改（W-1 卡「不做」最后一条）。
