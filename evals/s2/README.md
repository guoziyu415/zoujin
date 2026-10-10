# S-2 叙事者自检准确率的标注集

负责人：数据工程 · 对应 `backend/backend-design.md` S-2（和人工一致率 ≥ 90%；锚点违反漏检 0）、契约 `contracts.md` v1.5 第 3 节（Event、CheckResult、R1〜R7） · 最近更新：2026-10-10

被测的是叙事者流水线的**第 3、4 步**（backend-design 2.4）：确定性规则 R1〜R4、R7 和模型检查 R5、R6。不测提取（第 2 步）和改写（第 5 步）：每条直接给一个候选事件，看自检判过还是不过、报哪几条规则。

## 文件

| 文件 | 内容 | 谁能看 |
|---|---|---|
| `s2_dev.jsonl` | 公开样例 10 条（违规 6、合规 4），由 `../gen_s2_dev.py` 生成 | 所有人。后端用它搭运行器、调自检的提示 |
| `../holdout/s2/s2_holdout.jsonl` | **测量集 50 条**（违规 32、合规 18），由同目录的 `gen_s2_holdout.py` 生成 | 数据、UX（抽查）、PM。**后端在叙事者自检的提示定稿之前不读**，见下 |
| `../s2_check.py` | 格式自检和「确定性规则的最简判法」，两个生成器都用它 | 所有人 |

为什么分开：S-069 里后端看着 58 条样本写了 v3，在同一批样本上过线就不算数了。S-2 的 90% 也一样：自检的提示要是看着这 50 条改出来，一致率会虚高。所以测量集等提示定稿后再交给后端跑，调提示用公开的 10 条和评测 E4（世界一致）。两份不是同一批场面，摘要的字二元组 Jaccard < 0.5（生成器会查）。

```bash
cd data
python3 -I -B evals/gen_s2_dev.py evals/s2/s2_dev.jsonl
python3 -I -B evals/holdout/s2/gen_s2_holdout.py evals/holdout/s2/s2_holdout.jsonl
python3 -I -B evals/s2_check.py evals/s2/s2_dev.jsonl      # 只自检，不重新生成
```

改世界模型以后要重跑。现状：两份都是错误 0。

## 一条长什么样

```json
{"id": "s2d-06", "title": "牧童把灯递给梅洛斯，可灯不在他手上",
 "setup": {"role": "role.shepherd-boy", "checkpoint": "sc.canon@t=4380", "place": "place.melos-home"},
 "turn": {"player": "外はまだ暗いから、この灯を持っていって",
          "act": {"kind": "give", "target": "char.melos", "params": {"item": "item.lantern"}}},
 "candidate": {"t": 4380, "actor": "player", "type": "action", "origin": "action", "dt": 5, "place": "place.melos-home",
               "summary": "牧童はメロスに灯を渡した", "causes": [],
               "effects": [{"op": "hold", "item": "item.lantern", "to": "char.melos", "from": "player"}]},
 "label": {"verdict": "fail", "failedRules": ["R7-capability"], "stage": "rules",
           "rationale": "item.lantern 只有花婿借给玩家（aid.groom.lend）以后才在玩家手上……",
           "fix": "拒绝（rejected、R7）。叙事：牧童は灯を探したが、手もとにはなかった。",
           "refs": ["item.lantern", "aid.groom.lend"]},
 "tags": ["pair"]}
```

| 字段 | 含义 |
|---|---|
| `setup` | 起点，写法和评测用例完全一样（`role`、`checkpoint`、`place`、`events`，见 `../README.md`「用例格式」）。`eval_api` 的 setup 直接能用 |
| `turn` | 这一轮发生了什么：`player`（玩家原话）、`to`（对谁说）、`reply`（人物的回答，人物说错了的情况就写在这里）；动作则是 `act`（`kind`、`target`、`params`，有对应的情境动作时带 `affordance`）。没有 `to` 的是玩家自己做的事 |
| `candidate` | 叙事者第 2 步提取出来的候选事件，契约 Event 的子集：`t`、`actor`、`type`、`origin`、`dt`、`place`、`summary`、`causes`、`effects`，可带 `beneficiary`、`confirmed`。还没有 `eventId`、`seq`、`check`，约定没有 `promiseId`（提交时才分配） |
| `label.verdict` | 人工判定：`pass`（照样提交）/ `fail`（有违规，要改写、降级或拒绝） |
| `label.failedRules` | 违规的规则，第一条是主规则。自检至少要报出其中一条 |
| `label.acceptAlso` | 可选。也说得通的规则（例：推迟已经发生的节拍，R2 和 R3 都对）。自检报这些也算规则一致 |
| `label.stage` | 违规时：`rules` = 结构化的效果上就看得出，第 3 步应该拦住；`model` = 只有读懂摘要、即兴设定或人物性格才看得出，要第 4 步 |
| `label.rationale` | 为什么这样判（中文），引用世界模型的 ID 和契约条文 |
| `label.fix` | 违规时：怎样改写、降级或拒绝才对。不计分，给第 5 步和评审看 |
| `label.refs` | 依据用到的 ID（自检核对都存在） |
| `tags` | `anchor-text`（锚点违反只写在文字里）、`improv`、`claim`（玩家或人物的说法，不是事实）、`tricky-valid`（看着像违规的合规）、`pair`（同一场面的违规和合规两种写法）等 |

## 测量集的配比

违规 32 条，按主规则：R1 8、R2 4、R3 4、R4 4、R5 5、R6 3、R7 4；规则判得出 19、要读懂意思 13（R1 里规则判得出 3、要读懂意思 5）。合规 18 条，一半是看着像违规的合规（`tricky-valid`）。9 对是同一场面的两种写法（`pair`），看自检是不是只凭场面下判断。

具体是哪些场面，这里不写，只记在 `../holdout/README.md`（被测的一方定稿前不读）。2026-10-10 以前本页写过一些条目的内容，看到的条目已经换成新的；只按类别提过的几条留着，报告里单列。

## 怎么跑、怎么算

1. 每条：按 `setup` 起局（`eval_api`），调 `check(candidate, turn, modelChecks="all")`（api-contract 第 7 节：只检查、不提交；`turn` 给模型检查当上下文；`all` = 第 4 步对每条都跑，不按正式范围挑），记下 `status`（过 = `passed`；不过 = 其余三种）、`failedRules`、`reason`。
2. 每条跑 3 次，模型和思考档用叙事者正式的设置（3.8-flash、MEDIUM）。花费约 50 × 3 × $0.01 ≈ $1.5（`cost/m2-model-budget.md`）。
3. 计分：
   - **一致率** = 判定（过 / 不过）和 `label.verdict` 一样的条数 ÷ 50，门槛 ≥ 90%（最多错 5 条）。三次各算一次，报最差的一次，另报三次多数票。
   - **锚点漏检** = `failedRules` 里有 R1 的条目被判「过」的次数，门槛 0（三次里任何一次都不行）。
   - 不设门槛、要报的：规则一致（两边都判不过时，报出的规则和 `failedRules ∪ acceptAlso` 有交集）；合规被误拒几条、违规漏了几条，按 `stage` 分开；三次结果不一样的条目单列；曾在公开文档里按类别提过的条目单列（名单在 `../holdout/README.md`，跑完由数据给），看它们和别的条目有没有差别。
4. 结果写成 `report.json`（每条每次的判定、规则、`reason`、trace ID）和一页 `report.md`，交数据核对标注：不一致的条目由数据逐条看，是自检错了还是标注错了。标注错了就改生成器、重出测量集，并在报告里写明改了哪几条。

## 第 4 步的范围（已定，backend-design v1.0.9）

做标注时发现：按原来的范围（模型检查只看影响节拍或关系的事件），要读懂意思的违规大多到不了模型，「锚点漏检 0」做不到。后端已经放宽：

- 第 4 步跑过了第 3 步、`effects` 不为空的全部候选事件（含 `improv`、`learn`、变量、人物所在地）。只推进时钟的不跑。
- R6 的规则部分（电话、邮箱、地址的模式，Model Armor 的标记，和原话连续 8 字相同）放在第 3 步，每条摘要和即兴设定都跑。
- 净增约 $0.03 / 局（backend-design 第 8 节，S-5 实测替换）。

S-2 用 `modelChecks="all"`，不受范围影响。正式范围下会漏看哪些违规，由 `s2_check.py` 的 `scope_gap()` 数（`effects` 为空、标成 `model`、又不是第 3 步 R6 模式能抓的违规）：两份现在都是 0。

R6 的条目仍标 `stage: model`：第 3 步的模式抓得到电话、邮箱和照抄的原话，抓不全名字、住址和分寸；`judge()` 也不做 R6。

## 确定性规则的最简判法（`s2_check.py` 的 `judge()`）

数据用它核对标注自洽：标成 `rules` 的违规它必须报出主规则；合规的和标成 `model` 的它一条都不许报。它不是后端的实现，但**它能拦住的，后端的第 3 步也必须拦住**：

| 规则 | 判法 |
|---|---|
| R1 | `op: beat` 改一个锚点节拍（`kind: anchor` 或在 `anchors` 里），`to` 不是 `happened`；`set` 一个变量，而它现在的值是已发生的锚点节拍写的、之后没有别的节拍改过（如大雨后的 `var.weather`、冲桥后的 `var.bridge`） |
| R2 | 改一个已经有结果的节拍；候选事件让节拍 `happened`（只有到点的系统事件写 `happened`，要早用 `hastened`；W-1 的 `check_effects` 同样报）；让节拍 `altered` 而它的前提或 `requires` 的前一节拍不成立；`executed` 的变量改回别的值、移动已处刑的人质（rule.no-resurrection）；`var.king.disposition` 设 `wavering` 要 `var.king.trust` ≥ 40，设 `reformed` 要 ≥ 70（`var.king.trust` 的说明） |
| R3 | 事件的 `t` 早于此刻的时钟；`relocate` 或玩家换地点，按 `places.adjacent` 的最短路程超过 `dt` |
| R4 | `learn`：这条事实此刻成立（`trueFrom` 已发生），而且行为者知道它（人物按 `knows` 的 `since` 和本局学到的；玩家按身份的 `initialKnowledge`）；`improv` 的 `statement` 不含该人物此刻不知道的事实的 `spoilerTerms` |
| R7 | 玩家换地点要在 `access` 或此刻成立的 `conditionalAccess` 里；玩家交出的东西要在玩家手上；交给人物要和他在同一地点（或正跟着他）；情境动作的 `place`、`roles`、`when`、要用的物品都要满足 |

做标注时碰到的三件事，后端实现时要注意：

- **第四幕的路程和原作时间对不上。** 「市へ続く野の道」是一大段路：`places.adjacent` 里泉到野道 120 分、野道到刑场 62 分，但原作 `beat.21`→`beat.22` 只隔 60 分、`beat.23`→`beat.24` 只隔 30 分。按排程走的人物，R3 看排程；`adjacent` 只量玩家的移动和排程外的 `relocate`（backend-design v1.0.9 已定）。
- **有两条约束只写在说明文字里**：王的信任阈值（40 / 70），和「过桥渡河要桥还在」。前一条 `judge()` 按 R2 判（见上表，写死在这份参考判法里）；后一条现在只能靠模型。叙事者的第 3 步不写死，只读数据：契约冻结后的第一个加字段版本（1.6）把它们写成 `StateVar.valueRequires`，**S-2 测量集开跑前合并**，见 `../../contracts.md` 第 7 节 C-16。
- **人物说错话 ≠ 世界变了。** 人物的回答本身错了（说漏了还不知道的事、说错了自己的来历）时，叙事者照着提取就错了。正确做法是不提交、给这个人物的下一次局势说明加圆回提示（契约第 3 节「被否决和被修正是两回事」）。

## 请别人看的

| 谁 | 看什么 | 现状 |
|---|---|---|
| UX | 测量集里要读懂人设和分寸的条目，看判定、依据和日语 | 2026-10-10 抽查完，判定都同意；口吻和测试数据按意见改了，改过的条目请 UX 复看 |
| 后端 | 公开的 10 条和上面「最简判法」 | 2026-10-10 跑通（错误 0）；`eval_api.check` 已加；第 4 步范围已定。**测量集请等自检提示定稿后再看** |
