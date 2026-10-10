# S2 语音测试页（S-1b 手机实测的前端那一半）

后端的 S-1b 计划见 `backend/spikes/s1b-plan.md`。这个页面由后端的 s1b 代理在同一个地址下提供，zg 用 iPhone（关 Wi-Fi）打开，按 8 个测试项和メロス说话，页面自己记时间并上报。

## 目录

| 目录 | 内容 | 进不进镜像 |
|---|---|---|
| `page/` | `index.html`、`app.js`、`capture-worklet.js`、`play-worklet.js` | **进**：`ZJ_S1B_STATIC` / `ZJ_S1B_PAGE` 指向这个目录 |
| `test/` | `fake_serve.py`（后端真实代理 + 假的 Live 模型）、`e2e.mjs`（Chromium 假麦克风跑一遍） | 不进 |

`page/` 里的文件会原样发到手机上，所以按 D-017 保持中性：标题「音声テスト」，页面文字、文件名、注释里都没有产品名和 zg 的名字，只有メロス。改 `page/` 后用下面这条检查一遍：

```
grep -n -i "zoujin\|走进\|zj\|zg\|backend\|api-contract" page/*
```

## 页面做什么

- 登录：`GET /v1/me`，没登录就显示输入框，`POST /v1/auth/login {inviteCode}`。测试码只在 zg 的 Mac 上，不进聊天和文档。
- 连接：WebSocket `/v1/playthroughs/s1b/live`，`hello` → `near` + `focus` → `session_ready`，每 20 秒 `ping`。
- 说话：按住说话键 `activity_start`，上行 16 kHz PCM16、20 ms 一帧（`0x01` + 4 字节 turnSeq）；松手 `activity_end`。下行 24 kHz（`0x02`）放进 AudioWorklet 的环形缓冲（预缓冲 40 ms）。
- 打断：回复还在放时按下，**先在本地清空播放**再告诉服务端；旧回合的音频按 turnSeq 丢掉。
- 麦克风两种做法（第 3 项）：「对话中常开」或「每轮开关」；开麦时 `navigator.audioSession.type = 'play-and-record'`，关麦时改回 `playback`（iOS 17+ 支持，不支持的浏览器记为「不支持」）。
- 第 5 项显示要小声读的句子：后端 `zj_spike/data/s1b_lines.json` 的两组各 5 句，「出声」选外放时用手机麦克风那组，选耳机时用耳机那组；用服务端返回的识别文字算字错率，去掉的字符和后端 `cerIgnore` 一样。
- 第 7 项：切后台再回来时检查音频、麦克风、连接，需要时显示「タップで音を戻す」。

每一轮记下（毫秒）：

| 字段 | 意思 |
|---|---|
| `clientReleaseToAudibleMs` | **松手到听见第一个声音**（用 `getOutputTimestamp` 换算到真正出声的时刻）：S-1b 的主指标 |
| `serverReleaseToFirstAudioMs` | 服务端：收到松手到模型第一个音频 |
| `netMs` | 页面松手到收到第一帧下行，减去服务端那一段，约等于一次网络往返 |
| `pressToFirstUpMs`、`firstDownToAudibleMs` | 按下到第一帧上行；第一帧下行到出声 |
| `pressToSilenceMs`、`pressToInterruptedMs` | 打断时：按下到本地静音；按下到服务端确认打断 |
| `underrunCount` | 回复中途断音的次数 |
| `micOpenMs`、`connectToReadyMs` | 开麦耗时；点「开始」到可以说话 |
| `cerPct` | 第 5 项的字错率 |
| `bargeInCount` | 1 = 这一轮的回答被玩家按下说话打断了（这一轮在按下时就记下，不等播放结束） |
| `extMicCount` | 1 = 正在用的麦克风不是手机自己的（蓝牙或有线耳机），按麦克风名字自动判断，名字本身不记（可能含人名）；0 = 手机麦克风 |

结果存在手机的 localStorage（只有数字和测试项，**不存说话的文字**），同时 `POST /v1/telemetry`（代理只留 `*Ms`/`*Count`/`*Pct`、turnId/turnSeq 和几个短枚举）。「复制全部结果」可以导出 JSON。

## 容器里测过的（2026-10-06）

用后端真实的 `s1b_proxy.py`，只把 Live 模型换成假的（`test/fake_serve.py`），Chromium 假麦克风：

- 错误的码 →「コードが違います」；正确的码 → 进入；没登录的 WebSocket 被 4001 关掉。
- 握手带了 Cookie；点开始到可以说话 320〜400 ms（假模型开会话 300 ms）。
- 3 轮语音、3 轮小声句子、1 次打断、1 轮文字都记下了；本地静音 34〜40 ms。
- 识别文字晚于 `turn_complete` 到达时，字错率等文字到了再算；对话记录里你的话排在メロス的回答前面。
- 把下行放慢到比实时还慢（24 段）时，`underrunCount` = 23。
- 上报：13 条事件都进了代理日志，字段经过过滤。

**2026-10-07 修改**（S-1b 4G 实测后，后端发现的缺口）：服务端已经说完、手机还在播时按下说话，上一轮不出记录或只在 30 秒超时后出（实测第 11、19、26 轮）。原因是记录要等播放结束，而按下时清空播放，那一轮等不到结束。现在按下时就记下被打断的那一轮（`bargeInCount: 1`），服务端还没说完时最多等 5 秒它的 `turn_complete`；`turn_complete` 按 `turnId` 找回合，不只看当前一轮。另加 `extMicCount`，因为实测时「出声」选择一直没切，蓝牙耳机和外放分不开。容器里重跑 e2e：两种打断（服务端没说完 / 说完了还在播）被打断的那一轮都有记录，11 行全到，没有超时。

同日按 S-073 ②：「出声 / 网络 / 麦克风」三项没有默认值，三项都选了才能按说话键，说话键上显示当前条件（例「押して話す（外放・4G・对话中常开）」）；连接中把麦克风改成常开或每轮开关会马上开、关麦克风；自动判断的麦克风来源和「出声」不一致时，在设置下面提示。换测试项时三项清空、要重新选（iPhone Safari 拿不到网络类型，「网络」只能手选；后端的建议）。「AirPods」改成「蓝牙耳机」（值 `bluetooth`）。结果表的「其余」一栏标出「这一轮被打断」「耳机麦克风」。e2e 也覆盖了：没选条件时按下不开始一轮、提示的出现和消失。
- 控制台没有错误（只有未登录时 `/v1/me` 的 401，属于正常）。

**没测的**：真 iPhone Safari（audioSession、AirPods、静音键、LINE 内置浏览器、后台恢复）和真 Live 模型。这些只能靠 zg 的实测。

## 在容器或 Mac 上重跑

```
pip install google-genai fastapi "uvicorn[standard]"          # 版本同 backend/spikes/pyproject.toml
cd test && PYTHONDONTWRITEBYTECODE=1 python fake_serve.py 8091  # 测试码 TEST-TEST-TEST，只在本机
node e2e.mjs http://127.0.0.1:8091/                             # 需要 playwright
FAKE_PACE=0.13 python fake_serve.py 8091                        # 下行比实时慢，看断音计数
```
