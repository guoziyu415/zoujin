# packages/worldsim

世界状态的共享规则库（W-1）：初始状态、应用 effects、到点的节拍、时间传播、结局分类。叙事者、评测和数据的工具都只用这一套规则。数据负责，后端评审。只用标准库。

| 目录                                 | 内容                                                                                                                                                                                                                   |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/zoujin_worldsim/sim.py`         | 一口气推演 `Sim`（`run` / `resume` / `arrival_delta` / `classify` / `value_requires`），从参考实现原样移植，开局状态按身份读                                                                                           |
| `src/zoujin_worldsim/incremental.py` | 逐事件推演：`initial_state` / `apply` / `settle` / `world_state` / `check_effects`，加上 `classify` / `predict` / `arrival_delta`                                                                                      |
| `src/zoujin_worldsim/opening.py`     | 开局到起点：`opening` / `parse_checkpoint`，eval_api 的 setup 里 `checkpoint`、`scenario`、`place` 三种起点（B-0 和评测运行器共用）                                                                                    |
| `src/zoujin_worldsim/primitives.py`  | 叙事者规则的原语：`knows`（R4，谁此刻知道一件事）、`travel_minutes`（R3，两地之间最少走几分钟）、`activity`（R7 和快照，人物此刻在做什么）；评测 `evals/s2_check.py` 的 R3 也用它                                      |
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

## 开局到起点

```python
from zoujin_worldsim import opening, parse_checkpoint

sc_id, until = parse_checkpoint("sc.canon@beat.05")  # 或 "sc.king-hardened@t=1235"
events, s = opening(world, "role.traveler", scenarios.get(sc_id), until, place=None)
```

- 顺序：`place` 在时钟 0 写一个事件 → 情景的节拍改动在时钟 0 合成一个事件 → `settle` 到身份的 `startT` → 情景的事件按 `t` 先 `settle` 再写 → 按起点停。`until=None` 推演到底（`scenario`）。
- 停在节拍：写完这个节拍发生的事件就停，同一时刻后面的节拍留给下一次 `settle`。这一局里它没发生（被阻止），就报错：检查点写错了。
- 停在某一刻：那一刻到点的节拍和期限都算，情景里正好在那一刻的事件不算（先停）；那一刻没有事件时写一个只推时钟的事件（`effects` 为空）。
- 每个事件是一份草稿加 `source`（`place` / `scenario` / `schedule` / `clock`），非 `schedule` 的另带一句日语 `note`（情景事件自己写了 `note` 就用它），B-0 拿去写 `summary`、在 trace 里标成评测布置。`event.seq` 从 1 起连续，B-0 补上其余字段写库。
- `setup.events`（评测布置）不在这里，B-0 在起点之后照 api-contract 第 7 节追加。

## 叙事者规则的原语

```python
from zoujin_worldsim import activity, knows, travel_minutes

knows(world, s, "char.selinuntius", "fact.promise")  # R4：beat.06 以后才知道
knows(world, s, "player", "fact.city-silent")  # 玩家 = 身份的 initialKnowledge + 这一局学到的
travel_minutes(world, "place.road-to-city", "place.syracuse-square")  # R3：60；走不到 None
activity(world, s, "char.crowd")  # R7、快照：beat.s1 之前 "absent"，被带到刑场以后 "idle"
```

- `knows` 按契约 2.1：`Character.knows` 里 `since` 已发生的（或 `pre`）、这一局 `learn` 学到的、自己的即兴设定；`trueFrom` 这一局没发生的事实谁都不算知道（2.3）。（1.7）玩家 = 身份的 `initialKnowledge` + `learn` 写 `player` 学到的：人物告诉玩家由叙事者提取；节拍发生时玩家在节拍的地点，`settle` 在那个系统事件里给 `public` 事实写 `learn`。
- `travel_minutes` 按 `places.adjacent` 的步行分钟取最短路，同一场景里的两个地点之间按 `pacing.sceneWalkMinutes`（0 分，S-038）。只量玩家的移动和排程以外的 `relocate`，按排程走的人物看排程（backend-design 2.4）。过河（`crossing`）和归途的走法 M3 再加：归途四个地点同一场景，现在互相 0 分。
- `activity` 按契约 2.4（1.1）：开局是 `initialActivity`（省略 = `idle`），节拍发生后是节拍 `activities` 里给这个人物的，到下一个给他的节拍或移动为止；移动了、没给新的就是 `idle`。参与人物先移到节拍地点（契约 3.1），节拍 `outcomes` 的 `relocate` 按这一局实际用的结果（变体、玩家事先改的）。状态里没有事件的历史，所以重放已发生的节拍算出他按节拍该在的地点，此刻 `locations` 不同 = 被事件挪过 = `idle`。只是世界模型给的那一部分，叙事者按对话再推（backend-design 2.7）；`absent` 的人物 R7 不让对话（S-077 ⑩）。

## 改规则

规则要改先改 `reference/worldsim.py`，再跑 `python3 -I packages/worldsim/tests/golden/gen_golden.py` 重新生成黄金文件，然后改包，让 `pytest packages/worldsim` 重新全过。移植时发现像 bug 的地方不在移植里改，回参考实现改（W-1 卡「不做」最后一条）。
