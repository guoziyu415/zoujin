# fixtures

测试用的固定数据：录好的模型回放、假 Live 的台词、mock 的数据和剧本。回放只从合成的输入录（dev-plan 2.5），按模型、提示版本、请求哈希存，提示改了 CI 会报「回放过期」。B-0、E-0 往里放。

这里的台词和摘要都是为测试写的：不放原作的句子、真人录音或真人说过的话，也不放地址、项目 ID、邀请码。

| 目录 | 谁读 | 是什么 |
|---|---|---|
| `mock/rest/`、`sessions/` | `zoujin-mock`（B-1） | mock 的 REST 回答和 WebSocket 剧本，见各自的 README |
| `fake-voice/lines.json` | 假 Live（B-0，`models/live.py`） | 每个人物一串「玩家说的话 + 人物的回答」，按轮次依次用，用完从头再来。语音一轮的玩家字幕就是 `player`（假的没有语音识别），文字一轮只用 `reply`。人物的音频按回答的字数合成，不是录的。没列的人物用 `default` |
| `fake-text/*.json` | 假文本模型（`ZJ_MODEL=fake`，默认） | 每种提示（`reply`、`extract`）有一个过 Schema 的默认输出；这里的 `rules` 按提示类型和条件覆盖它。条件 `when` 现在有 `character`（对谁说）和 `playerContains`（玩家这句含某个词），第一条对上的生效。剧本要的特定输出放这里 |
| `model-replays/*.jsonl` | 回放（`ZJ_MODEL=replay`） | 一行一次调用：`key`、`kind`、`provider`、`model`、`promptVersion`、`request`、`response`、`usage`、`costUsd`、`recordedAt`。`key` = `<模型>\|<提示版本>\|<规范化请求的 sha256>`，读的时候重算，对不上就报错。查不到的请求抛 `ReplayMissing`（「回放缺失或过期」），不退回假模型 |

## 改了以后

- 改了提示文本（`models/prompts.py`）、叙事者发给模型的请求或 `fake-text` 的输出：`b0-minimal.jsonl` 会过期。重写（要测试库，见 `services/backend/README.md`）：

  ```sh
  ZJ_UPDATE_REPLAYS=1 DATABASE_URL=… uv run pytest services/backend/tests/test_eval_api.py -k fixture
  ```

  它跑一遍最小剧本那一轮（旅人在广场对老爺说一句），把假模型的两次调用按回放格式写下来。评审时看差异。
- 真模型录的回放在 M2 只在 zg 的 Mac 上录（G-7），格式和上面一样，`request` 里只有合成的输入。
- 改了假模型的输出也会改 E-0 的报告：同一个 PR 里更新 `evals/tests/snapshots/fake`（命令在 `evals/tests/test_cli.py` 开头）。
