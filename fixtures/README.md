# fixtures

测试用的固定数据：录好的模型回放、假 Live 的台词、mock 的数据和剧本。回放只从合成的输入录（dev-plan 2.5），按模型、提示版本、请求哈希存，提示改了 CI 会报「回放过期」。B-0、E-0 往里放。

这里的台词和摘要都是为测试写的：不放原作的句子、真人录音或真人说过的话，也不放地址、项目 ID、邀请码。

| 目录 | 谁读 | 是什么 |
|---|---|---|
| `mock/rest/`、`sessions/` | `zoujin-mock`（B-1） | mock 的 REST 回答和 WebSocket 剧本，见各自的 README |
| `fake-voice/lines.json` | 假 Live（B-0，`models/live.py`） | 每个人物一串「玩家说的话 + 人物的回答」，按轮次依次用，用完从头再来。语音一轮的玩家字幕就是 `player`（假的没有语音识别），文字一轮只用 `reply`。人物的音频按回答的字数合成，不是录的。没列的人物用 `default` |
| `fake-text/*.json` | 假文本模型（`ZJ_MODEL=fake`，默认） | 每种提示（`triage`、`extract`、`check`、`rewrite`、`reply`、`narrate`、`plan`、`ending`、`safety`）有一个过 Schema 的默认输出：安全筛查（B-12 `safety`）判 none、分流判「可能」、提取没有候选、检查全过、改写原样（降级做不到）、回答一句「……そうか。」。这里的 `rules` 按提示类型和条件 `when` 覆盖它，第一条对上的生效。条件：`character`（对谁说）、`playerContains` / `replyContains`（这一轮的原话含某几个字）、`summaryContains`（候选的摘要）、`confirmOpen`（B-4：提取的请求里有没有在等回答的反问），其他键要等于请求里同名的值（例：`mode`）。B-9 的 `ending` 默认按请求确定地写一份能过校验的结局（尾声从最后几个照原作发生的事件的摘要拼，每句引用那个事件）。规则还能写 `output`（整个输出）、`broken`（只给 `ending`：引用全空，测重写和模板）、`fail`（只给 `check`：`{rule, reason}`，对上的候选这条规则判不过，其余全过）、`error`（`rate-limit` / `invalid` / `unavailable` / `refusal`（B-12：模型拒答））、`latencyMs`（先等这么久，测时限）、`times`（最多用几次）。剧本要的特定输出放这里 |
| `fake-armor/*.json` | 假 Model Armor（B-12，`models/armor.py`） | 默认全不命中。`rules`：`method`（`prompt` 玩家输入 / `response` 人物输出，不写两样都认）、`contains`（子串）、`result`（`pi`、`rai`、`sdp`、`uri`，同 `ArmorResult`）、`error: "unavailable"`、`latencyMs`，第一条对上的生效 |
| `model-replays/*.jsonl` | 回放（`ZJ_MODEL=replay`） | 子目录 `armor/*.jsonl` 是 Model Armor 的（键 `armor\|<模板配置的版本>\|<方法>\|<文字的 sha256>`，`response` 是 `ArmorResult`）；别的一行一次文本模型调用：`key`、`kind`、`provider`、`model`、`promptVersion`、`request`、`response`、`usage`、`costUsd`、`recordedAt`。`key` = `<模型>\|<提示版本>\|<规范化请求的 sha256>`，读的时候重算，对不上就报错。查不到的请求抛 `ReplayMissing`（「回放缺失或过期」），不退回假模型 |

## 改了以后

- 改了提示文本（`models/prompts.py`）、叙事者发给模型的请求或 `fake-text` 的输出：`b0-minimal.jsonl` 会过期。重写（要测试库，见 `services/backend/README.md`）：

  ```sh
  ZJ_UPDATE_REPLAYS=1 DATABASE_URL=… uv run pytest services/backend/tests/test_eval_api.py -k fixture
  ```

  它跑一遍最小剧本那一轮（旅人在广场对老爺说一句），把假模型的各次调用（回答、分流、提取、检查、改写）按回放格式写下来。评审时看差异。
  结局的回放 `b9-ending.jsonl`（切片两条路的 `ending` 调用：「市に残り」走到日没的大団円，梅洛斯来不及的期限结算；Mac 探针拿这两个请求量）同样重写：`… pytest services/backend/tests/test_b9.py -k fixture`。真模型的结局回放等 Mac 探针（B-9 验收第 13 条）。
- 真模型录的回放在 M2 只在 zg 的 Mac 上录（G-7）：设 `ZJ_RECORD_REPLAYS=<目录>`，格式和上面一样，`request` 里只有合成的输入。留出集的回放不进仓库，用 `ZJ_REPLAYS` 指过去读。
- 改了假模型的输出也会改 E-0 的报告：同一个 PR 里更新 `evals/tests/snapshots/fake`（命令在 `evals/tests/test_cli.py` 开头）。
