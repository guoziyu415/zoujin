# fixtures/sessions：mock 的会话剧本（B-1）

`uv run zoujin-mock`（或 `docker compose up mock`）按这里的剧本回放 WebSocket 会话。一个文件一个剧本，一行一步（JSON Lines）。剧本跟着局走，不跟着连接走：断线期间剧本照样往下走，`commit` 记下来，重连发 `hello { lastSeq }` 时补发。

选剧本：启动时 `--scenario <名字>`（默认 `tour`），或者 `POST /__mock/scenario {"name": "<名字>"}`。换剧本以后新开的局用它，正在跑的局从头跑新剧本（已发的 `commit` 留着，序号接着走）。`GET /__mock/scenarios` 列出全部。

每个剧本第一行的 `note` 写着玩家要做什么。剧本以外的输入 mock 忽略，在终端记一行。

## 剧本

api-contract 第 7 节的 11 种，B-1 卡的 5 种边角情况，加一个「未来的消息」和 v1.0.4 的固定演出。「人物」一栏是要先 `focus` 的人。

| 剧本 | 情形 | 人物 | 玩家要做的 |
|---|---|---|---|
| `full-turn` | 一整轮：事件、记忆、关键时刻（`reveal` 带因果链） | メロス | 说一句或发一句文字 |
| `small-talk` | 闲聊：只带时钟的 `commit`，`turn_settled` 是 `no_change` | 市の老爺 | 说一句 |
| `interrupt` | 打断：`interrupted`，剩下的音频不发 | メロス | 说一句；他说话的 6 秒里再按下说话或发文字 |
| `retract` | 作废（`retracted`、`too_late`）和识别改正 | 市の老爺 | 第 1 轮人物回答后约 4 秒内「言い直す」；第 2 轮判完后再作废；第 3 轮字幕识别错了，`turn_retract` 加 `text { via: "correction" }` |
| `confirm` | 意图确认：按按钮回答、超时 | メロス | 说两句，原来那一轮先 `commit`（10 分钟）、`turn_settled`，再反问、推 `confirm`。第 1 次人物的回答就是反问，按按钮（一直等），答「是」先推草稿的 `commit` 再 `confirm_closed`；第 2 次服务端发起一轮（`turn_started reason: confirm`）再问，不回答，30 秒后超时，只推 `confirm_closed` |
| `approach` | 人物走过来，接着一个动作 | 市の老爺 | 收到 `approach` 后发 `approach_arrived`（或 `approach_dismiss`）；他开口后回一句；再点动作「家まで送る」 |
| `act-end` | 幕末：`leaving` 的一轮、`act_ended`（去处带副题 `where`、`sub`）、说出打算、`act_transition`（带落地 `arrival`） | — | 可以直接 `act_choose`；也可以先 `act_propose` 或用声音（`activity_start purpose: "act_plan"`），拿到不成行和替代去处（只演一次）后再 `act_choose`。选「老爺の家に身を寄せる」时落地带 `opener`：显示完落地那一行发 `act_landed`，老爺先开口（`turn_started reason: arrival`） |
| `set-piece` | 固定演出（3.14）：`action_result` 带 `setPiece` 不带 `narration`，紧接着 `set_piece`；mock 的 manifest 没有录音，只出字幕 | — | 等 mock 加上「戸を叩く」（`obj.workshop-door`）后点它（`action kind: examine`）；再点一次，回普通的 `narration` |
| `goaway` | `goaway` 后 1012 关闭，断线期间判完，重连补发 | 市の老爺 | 说一句；被关掉后按第 4 节重连 |
| `other-tab` | 4009 | 市の老爺 | 同一局再开一条连接，旧的以 4009 关闭；在新连接上说一句 |
| `safety` | `safety_hint`；再一次 `safety_pause` → `safety_resumed` | 市の老爺 | 说两句；出戏卡上选「物語に戻る」（`safety_resume`） |
| `ending` | 结局：`cue`、刑场的节拍、`ending_started`、约 4 秒后 `ending_ready` | — | 什么都不用做；之前 `GET …/ending` 回 202，之后 200 |
| `late-transcript` | 人物的定稿晚于 `turn_complete`（补转写，`source: "fallback"`） | 市の老爺 | 说一句 |
| `transcript-failed` | 补转写也失败：`{final: true, text: null, source: "fallback"}` | 市の老爺 | 说一句 |
| `no-audio` | 人物没出声：`turn_complete { audio: false }`，`no_response` | 市の老爺 | 说一句 |
| `degraded` | 降级为文字回答（`session_ready.voiceAvailable: false`） | 市の老爺 | 发一句文字 |
| `limits` | 今天的语音还剩 5 分钟 | — | 什么都不用做 |
| `future-message` | 一条 Schema 里没有的 `type`，之后一行叙事 | — | 什么都不用做（前端应该忽略不认识的消息） |
| `tour` | 导览：上面除 `other-tab` 以外的全部，按 `full-turn`、`small-talk`、`approach`、`set-piece`、`confirm`、`interrupt`、`retract`、`late-transcript`、`transcript-failed`、`no-audio`、`safety`、`goaway`、`limits`、`future-message`、`act-end`、`degraded`、`ending` 的顺序串成一局 | | 照各段做 |

不靠剧本、mock 自己回的（`services/backend/src/zoujin_backend/mock/ws.py`）：`hello` → `welcome` 和补发的 `commit`；`ping` → `pong`；`near`、`focus` → `session_preparing` / `session_ready`（预热 800 ms，重建 1 秒，重连后第一次是 `reconnect`）；`turn_retract` → `turn_retract_result`（判完之前作废还会推 `turn_settled retracted` 并重建会话）；人物发音频时收到 `activity_start` 或 `text` → `interrupted`；不合 Schema 的消息 → `error invalid_request`；`act_choose` 选了不在这次幕末里的去处 → `error invalid_choice`；对不上现在的确认的 `confirm_answer`（超时之后才到的）忽略。

## 一行的写法

```json
{"on": "activity_end", "delayMs": 120, "send": {"type": "narration", "line": "日が傾いてきた。"}}
```

| 键 | 意思 |
|---|---|
| `on` | 先等前端发来这几种消息之一（字符串或数组；`"turn"` = `activity_end` 或 `text`）。等到的那条叫「触发消息」，从这一行到下一个带 `on` 的行是一组 |
| `timeoutMs` | 和 `on` 一起用：等这么久还没等到，就以 `{"type": "timeout"}` 开始这一组 |
| `if` | `{变量: 值或值的列表}`，全部满足才做这一行（带 `on` 的行不满足就不等）。变量见下面的占位符 |
| `when` | `voice` 或 `text`：这一组是语音还是文字触发的才做 |
| `delayMs` | 做之前等多久（乘 `--speed`） |
| `newServerTurn` | 服务端发起一轮：分配新的 `turnId` 和最高位为 1 的 `turnSeq`（3.1），之后这一组的 `{{turnId}}`、`{{turnSeq}}` 指它 |
| `send` | 发一条服务端消息。发出前用 `packages/contracts` 生成的类型构造、再按 Schema 校验，不过就不发并在终端报错 |
| `unchecked` | 和 `send` 一起用：跳过自检。只有 `future-message` 用 |
| `hidden` | 和 `send` 一起用（`commit`）：这次提交里玩家看不到的事件有几个，占 `seq` 不推（3.4）。不写时：没有可见事件的提交算 1 个 |
| `audio` | `{"seconds": 2.4, "chunkMs": 40}`：按这一组的 `turnSeq` 发合成的 24 kHz 人物音频（3.1）；被打断、被作废或断线就停 |
| `close` | `{"code": 1012, "reason": "…"}`：关闭当前连接 |
| `set` | `{名字: 值}`：剧本变量，之后用 `{{var.名字}}` 和 `if` 读 |
| `include` | 把另一个剧本原样插在这里（这一行只能写 `include` 和 `note`） |
| `note` | 说明，mock 不读 |

一行只做一件事（`send`、`audio`、`close`、`set`、`include` 之一）。这一组的触发消息所在的轮次被作废以后，这一组剩下的行都不做（3.6）。

**占位符** `{{名字}}`、`{{名字|默认值}}`：整个字符串就是一个占位符时换成原值（数字、`null`），嵌在字符串里时换成文字。

| 名字 | 值 |
|---|---|
| `turnId`、`turnSeq` | 这一组的轮次：前端发来的，或 `newServerTurn` 分配的 |
| `playerTurnId` | 最近一次玩家发起的轮次（服务端插进来的一轮之后，用它把 `commit`、`turn_settled` 记回玩家那一轮） |
| `serverTurnId`、`serverTurnSeq` | 最近一次服务端发起的轮次 |
| `interrupted` | 这一组的轮次被玩家打断了没有（`true` / `false`） |
| `trigger.<字段>` | 触发消息的字段，例 `trigger.optionId`、`trigger.clientMsgId`、`trigger.type` |
| `var.<名字>` | `set` 设的变量 |
| `id:<前缀>:<名字>` | 这一局里这个名字对应的运行时 ID（`ev`、`mem`、`prm`、`rev`、`draft`、`plan`、`end`…），第一次用到时生成，之后不变；REST 的固定数据用同一套名字，所以 `/memories`、`/ending` 里的事件 ID 和推过的对得上。重跑剧本时重新生成 |
| `playthroughId`、`roleId`、`lastSeq` | 这一局的 |
| `t`、`tLabel` | 现在的故事时间和说法 |
| `t+N`、`tLabel+N` | 往后 N 分钟（按世界模型的 `clock.labels` 算说法）。剧本不写死时刻，导览里前后剧本接得上 |

**mock 现填的**：`commit` 的 `fromSeq`、`seq` 和每个事件的 `seq`；`reveal.chain` 里没写 `seq` 的事件步骤（按事件 ID 找）；`act_transition.snapshot` 的 `playthroughId`、`lastSeq`、`status`、`pending`、`voice`。

## 时间

默认按 `delayMs` 等，保留真实的间隔（叙事者在 `turn_complete` 后约 3.7 秒提交，候选话语约 1 秒）。`--speed 0` 完全不等，给 CI 用；`--speed 2` 两倍慢。

`--speed 0` 下要靠时机的情形会走另一条路：人物的音频一下就发完，所以打断不到（不会有 `interrupted`），「言い直す」来不及（回 `too_late`），第 2 次确认立刻超时，`GET …/ending` 直接是 200。剧本照样走完、每条消息照样过 Schema。要在测试里按真的时序走这些情形，用一个小的倍数（B-1 的测试用 `--speed 0.04`）。

## 剧本里的日语

都是为 mock 写的，或者照 api-contract、ux-design 里已有的句子；不含真人说过的话、真实的人名和个人信息。时刻和到达预计只是示意，mock 不算排程。
