# 调研：Gemini Live 语音、iPhone Safari 的音频限制、语音优先游戏的先例

UX 线程 2026-10-06 整理（调研助手检索，UX 审读）。每条事实都附来源编号，URL 在文末；「推断」是推测，不是来源原话。后端、前端可直接引用；和 backend-design.md 3.2 节的结论一致的地方没有重复论证。


所有来源的检查日期都是 2026-10-06。每条事实后面标了来源编号，URL 和发布/更新日期集中列在文末。标「推断」的内容来源里没有写，是我推出来的。

---

## 1. Gemini Live API（2026 年 10 月现状）

### 1.1 当前模型
| 模型 ID | 状态 | 要点 |
|---|---|---|
| `gemini-3.8-live` | Stable，2026-09-15 发布 | 官方定位是"大多数低延迟语音 agent 的默认选择"；`thinkingLevel` 不能配置；异步函数调用默认 `NON_BLOCKING`；输入上限 131,072 tokens [G1][G2][G9] |
| `gemini-3.8-live-extended-thinking` | Gemini API 上标为 Stable，Cloud 博客写的是 Enterprise 上 private preview（两处说法不一致） | 推理更强；thinking 可设 low/medium/high；边推理边说话，会先说"Let me check that…"之类的口头提示 [G2][G3][G14][G15] |
| `gemini-3.1-flash-live-preview` | Legacy preview | 不支持 affective dialog、proactive audio、异步函数调用 [G2][G3][G7] |
| `gemini-2.5-flash-native-audio-preview-12-2025` | 只对已有用户开放 | 旧模型 [G2] |

**3.8 Live 的两个关键变化**（来自官方 model card）[G1]：
- 「Affective dialogue is removed from the API」：情感自适应开关已经删除。
- 「Proactive audio is now permanently enabled. Setting `proactive_audio: false` returns an error」：模型判断某句话与自己无关时可以不回应，这个行为关不掉 [G4]。
- 另外，`turn_complete=true` 会无条件打断正在生成的回复。所以文字输入发出去时，NPC 正在说的话会被切断。

**Vertex AI 侧**：Google Cloud 文档的 URL 已经迁到 "Gemini Enterprise Agent Platform"。导航里列了 Gemini 3.8 Live [G16]。Cloud 博客（2026-09-24）宣布 Gemini 3.8 Live with Live Avatar GA，提供 US/EU 端点，支持 97 种语言 [G15]。Vertex 页面正文我抓不到，**模型 ID、region、voice 列表需要人工到控制台确认**。另外，2026 年 5 月到 8 月的开发者论坛帖子说 3.1 Flash Live 一直没有上 Vertex [G17]。

### 1.2 日语与声音
- **语言**：live-guide 列出 99 种语言，包括 `ja` [G3]（Cloud 博客写 97 种 [G15]）。native audio 模型「automatically choose the appropriate language and don't support explicitly setting the language code」[G3]。官方建议在 system instruction 里写「RESPOND IN {LANG}. YOU MUST RESPOND UNMISTAKABLY IN {LANG}.」[G5][G10]。
- **预置声音**：Live API「supports any of the voices available for our TTS models」[G3]，共 30 个，默认 Puck [G10][G11]。下表的性别和特征来自 Firebase 文档：

| 男声 | 女声 |
|---|---|
| Achird(Friendly) Algenib(Gravelly) Algieba(Smooth) Alnilam(Firm) Charon(Informative) Enceladus(Breathy) Fenrir(Excitable) Iapetus(Clear) Orus(Firm) Puck(Upbeat) Rasalgethi(Informative) Sadachbia(Lively) Sadaltager(Knowledgeable) Schedar(Even) Umbriel(Easy-going) Zubenelgenubi(Casual) | Achernar(Soft) Aoede(Breezy) Autonoe(Bright) Callirrhoe(Easy-going) Despina(Smooth) Erinome(Clear) Gacrux(Mature) Kore(Firm) Laomedeia(Upbeat) Leda(Youthful) Pulcherrima(Forward) Sulafat(Warm) Vindemiatrix(Gentle) Zephyr(Bright) |

- **每个角色换一个声音**：voice 写在 `speechConfig.voiceConfig.prebuiltVoiceConfig.voiceName` 里 [G3]。setup 消息「to be sent in the first (and only in the first)」client message [G6]，所以**一个 session 只能用一个声音，换角色就要新开 session**（推断）。已知坑：如果用 ephemeral token，把 speechConfig 写进 token 是无效的。Google 员工 2026-09-14 回复说要放在 client 的 setup 消息里 [G18]。你们走 Cloud Run 代理，在服务端写 setup 就行。
- **语气、年龄、口音**：官方只在 best practices 里写了 persona 写法，以及「指定口音时同时指定输出语言」[G5]。TTS 模型有 `style` 字段和行内标签可以控制风格 [G11]，Live API 没有对应字段，只能靠 system instruction（推断）。日语 30 个声音各自的自然度，官方没有公开评测，**必须在 AI Studio 里逐个试听**。

### 1.3 轮次检测与打断（barge-in）
- **自动 VAD（默认）**：`automaticActivityDetection` 下可以设：`startOfSpeechSensitivity`（HIGH/LOW）、`endOfSpeechSensitivity`（HIGH/LOW）、`prefixPaddingMs`、`silenceDurationMs`。官方建议 silenceDurationMs 取 500–800ms，更短「often cause fragmented audio」[G3][G6]。
- **手动方式（适合 push-to-talk）**：设 `disabled: true` 后，由客户端发送 `activityStart` / `activityEnd` [G3]。
- **打断行为**：`activityHandling` 默认是 `START_OF_ACTIVITY_INTERRUPTS`，用户一开口就打断模型；也可以改成 `NO_INTERRUPTION` [G6]。被打断时服务端返回 `serverContent.interrupted: true`，还没发出的生成内容被丢弃，已经发出的部分会留在历史里 [G3]。官方要求客户端「must immediately discard your client-side audio buffer」[G5]。
- `turnCoverage` 对 3.1 及以后版本的默认值是 `TURN_INCLUDES_AUDIO_ACTIVITY_AND_ALL_VIDEO` [G6]。
- 3.8 Live 的 VAD 和延迟都有改进（客户 Specs 在 Cloud 博客里的引述）[G15]。

### 1.4 转写
- 打开方式：在 setup 里加 `inputAudioTranscription` / `outputAudioTranscription`。输出转写的语言「inferred from the model's response」[G3]。
- 转写随 server content 增量下发（「Incremental server update」），但「sent independently of the other server messages and there is no guaranteed ordering」[G6]。也就是说，字幕和音频的对齐要客户端自己做（推断）。
- API reference 里 `AudioTranscriptionConfig` 新增了几个字段 [G6]：
  - `languageCodes`（BCP-47 提示）
  - `customVocabulary`（可以放 メロス／ディオニス／セリヌンティウス／シラクス 这些专有名词）
  - `wordTimestamp`、`diarization`
  - `mode`：`VERBATIM` 或 `SMART`（SMART 会去掉口头禅）

  这些字段对 3.8 Live 是否全部生效，需要实测。
- 已知问题：
  - 输入转写和模型实际理解的内容可能不一样（例如说的是 "wifi doesn't work"，转写成 "wife isn't well"）。论坛从 2026-03 到 09 都有人报，涉及 2.5、3.1、3.8。社区的结论是：**转写只用来显示，不要拿来驱动逻辑** [G19]。
  - 在 2.5 上，连续说 20–40 秒以上时，转写会延迟或者丢失 [G20]。

### 1.5 延迟（没有官方毫秒数）
Google 的发布材料只说"ultra-low latency"，没有给出毫秒数 [G1][G13][G14]。能找到的数字都是第三方报告：
- 3.1 Flash Live 开着 Google Search 工具时，总延迟 3–3.5 秒；关掉后首包约 100ms，总延迟 1–1.5 秒（LiveKit 社区，2026-04-03）[G21]。
- 2.5 native audio 端到端 5–6 秒（论坛，2026-02 到 03）[G22]。
- 官方的流式建议：音频按 20–40ms 一块发送，不要缓冲 1 秒；麦克风采集要重采样到 16kHz；输出是 24kHz [G5][G8]。

**结论：首包延迟必须在 iPhone 上实测。**

### 1.6 会话时长、计费、安全、工具
| 项 | 值 |
|---|---|
| 纯音频 session（不压缩） | 15 分钟；音视频 2 分钟 [G4] |
| 单条连接 | 约 10 分钟，断开前会收到 `GoAway`（带 `timeLeft`）[G4] |
| Session resumption | handle 在 session 结束后 2 小时内有效 [G4] |
| 长对话 | context window compression（sliding window + 触发 token 阈值）[G4] |
| 音频 token 速率 | 约 25 token/秒 [G5] |
| 价格（3.8 Live / Extended / 3.1 相同） | 音频输入 $3/1M（≈$0.005/分钟），音频输出 $12/1M（≈$0.018/分钟），文本输入 $0.75，文本输出 $4.50，有免费层 [G12] |
| Ephemeral token | 默认 30 分钟过期，新建 session 窗口 1 分钟，只支持 v1beta，可用 `liveConnectConstraints` 锁定配置 [G23] |
| 函数调用 | 支持。`NON_BLOCKING` 下结果回传时可选 `INTERRUPT` / `WHEN_IDLE` / `SILENT` [G7] |
| Cloud Run WebSocket | **请求超时默认 5 分钟**，最长 60 分钟；session affinity 只是 best effort；客户端必须自己处理重连 [G24] |

---

## 2. iPhone Safari / 移动 Web 的限制

| 问题 | 事实 | 来源 |
|---|---|---|
| 麦克风权限会不会反复弹 | 网站设置分 Ask / Deny / Allow，默认是 Ask。WebKit 工程师说，没有用户交互就调用 gUM「usually ends up triggering a prompt in Safari, except if users opt-in to always grant」。2025-06 有开发者报告，同一个 origin 的 SPA 换路由时会间歇性重新弹窗 | [I1][I2][I3] |
| AudioContext 必须在用户手势里 resume | 「Create or resume context from inside a user gesture」 | [I4] |
| 切走页面或锁屏 | iOS Safari 上 AudioContext 会进入 `interrupted` 状态，需要手动 `resume()` | [I5] |
| 静音键 | Web Audio 会被静音拨片静音（`<audio>` 不会）。iOS 17 起可以用 `navigator.audioSession.type = "playback"` 绕过 | [I6][I7] |
| 开麦后外放变小、走听筒 | WebKit bug 218012：授权麦克风后声音被路由到听筒、音量骤降。从 Safari 14 到 iOS 18.6 都有报告，最新评论是 2026-05。workaround 是采集前设 `play-and-record`、采集结束改回 `playback`，但"只是有时有效" | [I8] |
| iOS 26.3–26.6 的严重 bug | 系统音频守护进程重置后，gUM 永久报 `NotAllowedError`，重新加载页面也恢复不了，只能重启 Safari。一家远程医疗平台的数据：约 20% 的 iPhone 访问遇到这个问题，其中 64% 没能恢复。已修复，2026-09-08 回移到 26.x，Safari 27.2 beta 的 release notes 已收录 | [I9][I10] |
| Safari 27.0（2026-09-14） | 修复了「WebProcess AudioSession to remain active while microphone capture is live」 | [I11] |
| 回声消除、降噪 | `echoCancellation` 是 Baseline（2020 年起）；`noiseSuppression` 支持有限，要先用 `getSupportedConstraints()` 检测 | [I12][I13] |
| 后台和锁屏 | 有报告说锁屏或最小化时 WebSocket 会立刻触发 onclose（2022）；iOS 会在应用进入后台后不久将其挂起（Apple DTS）；LiveKit 社区 2026-07 报告切换 App 后麦克风被挂起，推荐的做法是加一个显式的"Join Audio"按钮来解锁音频 | [I14][I15][I16] |
| 长按按钮出现选字或菜单 | `-webkit-touch-callout: none` 关闭长按菜单；`user-select` 在 Safari 上必须写 `-webkit-` 前缀；`touch-action: manipulation` 去掉双击缩放（写 `none` 会影响可访问性） | [I17][I18][I19] |
| AudioWorklet | iOS Safari 14.5 起支持 | [I20] |

---

## 3. 语音优先游戏 / AI NPC 的先例

| 作品 | 输入方式 | 状态提示、延迟处理 | 听错与越狱 | 口碑 |
|---|---|---|---|---|
| **Whispers from the Star**（Anuttacon，2025-08-14，PC） | 视频通话段只能语音，信息 App 段可以打字 [U2]。玩家要求"不用再按 end 按钮"，推断是点击开始、点击结束 [U4] | 云端运行，音画不同步、延迟不稳定 [U3] | 说话说到一半停下时，Stella 会追问。但玩家分不清是没听清还是角色故意这样回答 [U5]。碰到敏感话题时内容过滤会让她出戏 [U6] | Steam 好评率 80%（1,663 条）[U1]；批评集中在重复、爱追问、闲聊没有目标，以及缺少文字模式 [U3][U4][U6] |
| **Suck Up!**（Proxima，2023 年起，Steam 版 2025-10-01） | 真人说话，按"语气和策略"回应，后端接 ChatGPT [U7] | 未查到公开说明 | 主播靠"想办法把 NPC 玩坏"走红 [U8] | 好评率 63%（210 条）[U7] |
| **Vaudeville**（Bumblebee，2023 年 EA，2025-11-28 正式版） | 打字或说话都行 [U9] | 未查到 | 大主播专门尝试搞坏 NPC [U10] | 好评率 48%（283 条）[U9] |
| **Fortnite AI Darth Vader**（2025-05-16） | 专门绑定一个 "Conversational AI" 按键，HUD 上有 Vader 按钮 [U11][U12] | 未查到 | 上线几小时就被诱导说脏话和歧视语；Epic「pushed a hot fix within 30 minutes」；13 岁以下需要家长许可 [U13][U14] | 话题性很强，但安全事故也是公开的 |
| **Fortnite Persona（UEFN AI NPC，2026-04-16 实验版）** | 语音聊天 [U15] | 官方承认「LLM response times are slower than we expect of the final release」 | 模型外加安全层；禁止做医疗、恋爱伴侣或绕过安全机制的角色；每局清空会话 [U15][U16] | 实验阶段 |
| **Ubisoft NEO NPC**（GDC 2024，Inworld + NVIDIA） | 语音 | 屏幕上有关系值条 [U17] | 遇到离题请求时，Bloom 会先用一句俏皮话接住，再把话题拉回任务 [U18] | 试玩者评价是"护栏太重、目标太离散" [U18] |
| **Ubisoft Teammates**（2025-11-21） | 语音指令 | 未查到 | 叙事总监说用"fences"让 NPC 在设定范围内即兴发挥 [U19] | 有几百人参加封闭测试 |
| **PUBG Ally**（NVIDIA ACE，2026） | 语音 | 为了"可预测的响应时间"选择端侧运行；行为树负责即时反应，LLM 负责慢思考 [U20] | 只开放一张地图、一个模式来缩小领域 | — |

**对话延迟的研究依据**：
- 10 种语言的轮次间隔平均差约 250ms，**日语平均只有 7ms**，是最短的；丹麦语约 500ms [R1][R2]。
- 间隔超过 700ms 时，"拒绝、不情愿"类回应的比例明显升高，也就是说沉默本身开始带有含义 [R3]。
- 日本人的附和（相槌）频率明显高于美国人 [R4]。
- 语音 agent 业界的说法：人类典型响应时间约 500ms，1,500ms 的 voice-to-voice 是一个"重要目标" [R5]。

---

## 4. 语音 UX 最佳实践

**三种收音方式的取舍**：
- **按住说话（PTT）**：轮次判定不含糊，但「quite different from a natural conversation」[R5]。
- **点按切换**：比按住省力；结束靠第二次点按或 VAD。
- **开放麦克风**：最自然，但可能误触发。OpenAI 的 semantic VAD 用 eagerness 在"等用户说完"和"抢话"之间做取舍 [R6]；Gemini 建议 silence 取 500–800ms [G3]。
- **不能只靠语音**：语音必须是可选输入，要有非语音的替代方式 [R7]。Whispers from the Star 因为文字模式不足被大量批评 [U2][U6]。

**显示"听到了什么"**：Alexa 的原则是"Always show what was heard to enable correction"[R8]。但 Gemini 的转写可能和模型实际理解的不一致 [G19]。

**关键操作要确认**：Alexa 建议后果大的操作用显式确认，后果小的用隐式或上下文确认 [R8]。Google 的错误处理是逐级加提示，连续 3 次 no-match 就优雅退出 [R9]。

**字幕（XAG 104）**：换说话人时标出名字；每行不超过 40 字符（英文）；最多 2 行；背景不透明度可以在 0–100% 调节；可以随时开关 [R10]。日文每行字数的标准没有查到，建议按全角约 20 字自行测试（推断）。

---

## 5. UX 建议（以下都是建议）

1. **默认用按住说话，设置里提供点按切换**，开放麦克风只作为实验选项。
   - 实现：关闭自动 VAD；按下时发 `activityStart`，松开时发 `activityEnd`。
   - 保留 `START_OF_ACTIVITY_INTERRUPTS`：一按下就打断 NPC，**同时立刻清空本地播放缓冲**，不要等服务端的 `interrupted`。
   - 理由：可以绕开日语附和误触发打断、外放回声导致 NPC 自我打断（推断），以及 proactive audio 不回应造成的歧义；同时减少输入计费。
2. **四个状态，加一个"无应答"状态**：待机 → 聆听（AudioWorklet 电平波形）→ 思考 → 说话（字幕流式出现）。松开按钮后 **200ms 内**角色要有可见反应（点头、抬眼），因为日语轮次间隔极短 [R1]。超过约 700ms 时，播放该角色的预录附和（「うむ…」「ほう」）[R3]，这些附和用 TTS 模型、同一个 voiceName 预先生成，保证音色一致（推断：两边的 voice 名称共用 [G3][G11]）。约 6 秒还没回应，就显示「もう一度話す／文字で送る」。
3. **一个角色一个 Live session**：分别配 voiceName 和 system instruction（时代口吻、第一人称、「RESPOND IN JAPANESE」、护栏写法参考 Bloom 那种"先接住再拉回"的偏题处理）。走到角色附近时提前建立 session 来隐藏握手时间（推断）。剧情状态用函数调用写回游戏，转写结果不进逻辑。
4. **选角建议（需要试听确认）**：
   - メロス：Puck 或 Fenrir
   - 王ディオニス：Algenib 或 Charon
   - セリヌンティウス：Iapetus 或 Achird
   - 妹：Leda
   - 老人、旁白：Rasalgethi 或 Gacrux
   - 可以做一个"演员表"页面，让评委逐个试听。
5. **显示听到的内容**：淡色气泡显示 `inputTranscription`，点一下就进入文字输入、并预填转写内容。在 `customVocabulary` 里加入人名地名（需实测）。
6. **关键剧情要显式确认**：比如"交出セリヌンティウス当人质"、"接受王的条件"，由模型触发函数调用，UI 弹出确认卡片，语音说「はい」也可以确认。
7. **防出戏和越狱**：system instruction 里写护栏；服务端过滤输出；记录日志。Vader 的教训是上线当天就会有人试图破坏 NPC [U13]。
8. **iOS 启动流程**：一个「はじめる」按钮，在这次点按里依次完成：
   - 创建或 resume AudioContext
   - 设置 `navigator.audioSession.type`
   - 调用一次 gUM
   - 建立 WebSocket

   之后再处理这些情况：
   - 监听 `visibilitychange` 和 `interrupted`，显示「タップして再開」，并用 resumption handle 重连。
   - 推荐戴耳机（规避听筒路由和回声问题）。
   - gUM 报 `NotAllowedError` 但权限其实是允许状态时，提示重启 Safari，并直接切换到文字输入 [I9]。
   - 说话按钮加上 `-webkit-user-select:none; -webkit-touch-callout:none; touch-action:manipulation`。
9. **服务端**：Cloud Run 请求超时调到 60 分钟；处理 `GoAway`；超过 15 分钟的会话开启 context compression [G4][G24]。
10. **字幕**：说话人名字配颜色；最多 2 行；流式出现，并按音频播放进度对齐；生僻词（邪智暴虐 等）加注假名。

---

## 来源（全部检查于 2026-10-06）
- [G1] ai.google.dev/gemini-api/docs/models/gemini-3.8-live（更新于 2026-09-15）
- [G2] ai.google.dev/gemini-api/docs/models（2026-10-01）
- [G3] ai.google.dev/gemini-api/docs/live-guide（2026-09-18）
- [G4] ai.google.dev/gemini-api/docs/live-session（2026-09-15）
- [G5] ai.google.dev/gemini-api/docs/live-api/best-practices（2026-09-15）
- [G6] ai.google.dev/api/live（2026-09-04）
- [G7] ai.google.dev/gemini-api/docs/live-tools（2026-09-15）
- [G8] ai.google.dev/gemini-api/docs/live（未注明日期）
- [G9] ai.google.dev/gemini-api/docs/changelog（9-15 条目）
- [G10] firebase.google.com/docs/ai-logic/live-api/configuration（2026-10-01）
- [G11] ai.google.dev/gemini-api/docs/speech-generation（2026-10-01）
- [G12] ai.google.dev/gemini-api/docs/pricing（检查于 2026-10-06）
- [G13] blog.google/innovation-and-ai/technology/developers-tools/build-with-gemini-3-1-flash-live/（2026-03-26）
- [G14] androidheadlines.com/2026/09/google-launches-gemini-3-8-live-audio-models.html（2026-09-15）；thurrott.com/a-i/google-gemini-a-i/341685/（2026-09-15）
- [G15] cloud.google.com/blog/products/ai-machine-learning/gemini-3-8-live-with-live-avatar-is-now-generally-available（2026-09-24）
- [G16] docs.cloud.google.com/gemini-enterprise-agent-platform/models/maas/google（正文无法读取）
- [G17] discuss.ai.google.dev/t/…eu-region-availability/144429（2026-05 至 08）
- [G18] discuss.ai.google.dev/t/bug-voicename-configuration-is-silently-ignored…/179065（2026-08-20，官方回复 09-14）
- [G19] discuss.ai.google.dev/t/…input-audio-transcription-returns-incorrect-text…/128300（2026-03 至 09）
- [G20] discuss.ai.google.dev/t/…delays-or-missing-input-audio-transcription-events/110732（2025-12 至 2026-01）
- [G21] community.livekit.io/t/how-to-fix-latency-3-secs-of-gemini-3-1-flash-live/766（2026-04-03）
- [G22] discuss.ai.google.dev/t/live-api-5-6-second-response-latency/123254（2026-02-16）
- [G23] ai.google.dev/gemini-api/docs/ephemeral-tokens（2026-09-15）
- [G24] docs.cloud.google.com/run/docs/triggering/websockets（2026-09-30）
- [I1] lists.w3.org/Archives/Public/public-webrtc-logs/2020Mar/0214.html（2020-03-30）
- [I2] ios.gadgethacks.com/how-to/customize-camera-microphone-location-permissions-for-specific-websites-ios-13s-safari-0198476/（iOS 13 时期）
- [I3] developer.apple.com/forums/thread/788518（2025-06）
- [I4] developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Best_practices（2026-08-27）
- [I5] developer.mozilla.org/en-US/docs/Web/API/BaseAudioContext/state（2025-07-24）
- [I6] bugs.webkit.org/show_bug.cgi?id=237322（2022 年报告，2024-09 有评论）
- [I7] developer.mozilla.org/en-US/docs/Web/API/Audio_Session_API（2026-08-19）
- [I8] bugs.webkit.org/show_bug.cgi?id=218012（2020 年报告，最新评论 2026-05-20）
- [I9] bugs.webkit.org/show_bug.cgi?id=319706（2026-07-17，回移于 2026-09-08）
- [I10] developer.apple.com/documentation/safari-release-notes/safari-27_2-release-notes（2026-09-16）
- [I11] developer.apple.com/documentation/safari-release-notes/safari-27-release-notes（2026-09-14）
- [I12] developer.mozilla.org/en-US/docs/Web/API/MediaTrackSettings/echoCancellation
- [I13] developer.mozilla.org/en-US/docs/Web/API/MediaTrackConstraints/noiseSuppression
- [I14] bugs.webkit.org/show_bug.cgi?id=247943（2022–2024）
- [I15] developer.apple.com/forums/thread/716118（2022-09）
- [I16] community.livekit.io/t/…background-audio-suspension-for-ios-users/1649（2026-07）
- [I17] developer.mozilla.org/en-US/docs/Web/CSS/-webkit-touch-callout
- [I18] developer.mozilla.org/en-US/docs/Web/CSS/user-select（2026-04-20）
- [I19] developer.mozilla.org/en-US/docs/Web/CSS/touch-action（2026-04-20）
- [I20] caniuse.com/mdn-api_audioworklet
- [U1] store.steampowered.com/app/3730100/
- [U2] steamcommunity.com/app/3730100/discussions/0/608668111724477736/（2025-08-15）
- [U3] 36kr.com/p/3428919332048259（2025-08-19）
- [U4] vaporlens.app/app/3730100/whispers_from_the_star.md（玩家评测汇总）
- [U5] steamcommunity.com/app/3730100/discussions/0/506216918922069229/（2025-10-18）
- [U6] blog.soullink.io/whispers-from-the-star-review/（2026-07-01）
- [U7] store.steampowered.com/app/2726370/Suck_Up/
- [U8] knowyourmeme.com/memes/subcultures/suck-up
- [U9] store.steampowered.com/app/2240920/Vaudeville/
- [U10] knowyourmeme.com/memes/subcultures/vaudeville-video-game
- [U11] beebom.com/how-to-talk-to-darth-vader-ai-in-fortnite/（2025-05-16）
- [U12] thespike.gg/fortnite/beginner-guides/star-wars-vader-ai
- [U13] foxnews.com/tech/epic-games-debuts-voice-interactive-darth-vader-fortnite-its-already-being-tricked-swearing（2025-05-17）
- [U14] nintendolife.com/news/2025/05/fortnite-turns-to-the-dark-side-with-ai-darth-vader-voice-and-of-course-its-been-swearing（2025-05）
- [U15] fortnite.com/news/bring-npcs-to-life-with-ai-powered-conversations（2026-04-16）
- [U16] dev.epicgames.com/documentation/fortnite/developing-personas-overview-in-unreal-editor-for-fortnite
- [U17] videogameschronicle.com/news/ubisoft-shows-off-ai-powered-game-characters-at-gdc-the-game-world-actually-listens（2024-03-19）
- [U18] wccftech.com/inworld-ai-npc-gdc-2024-hands-on-nvidia-and-ubisoft-show-a-glimpse-of-the-future/（2024-03-30）
- [U19] news.ubisoft.com/en-us/article/3mWlITIuWuu0MoVuR6o8ps/（2025-11-21）
- [U20] developer.nvidia.com/blog/how-krafton-built-pubg-ally-a-co-playable-character-powered-by-nvidia-ace/（2026-06-25）
- [R1] nationalgeographic.com/science/article/pregnant-pauses-and-rapid-fire-how-do-different-cultures-take-turns-to-talk（2009-06-19）
- [R2] forms.mpi.nl/node/50939（Stivers et al., PNAS 2009, 106(26)）
- [R3] eprints.whiterose.ac.uk/116177（Kendrick & Torreira, Discourse Processes 2015）
- [R4] cambridge.org/core/journals/language-in-society/article/abs/backchannels-across-cultures-a-study-of-americans-and-japanese1/B26AC3C44C237B9A380A5494EA5693ED（White, 1989）
- [R5] voiceaiandvoiceagents.com（2026-06 更新版）
- [R6] developers.openai.com/api/docs/guides/realtime-vad
- [R7] gameaccessibilityguidelines.com/ensure-that-speech-input-is-not-required-and-included-only-as-a-supplementary-alternative-input-method/
- [R8] developer.amazon.com/en-US/alexa/alexa-haus/design-principles/be-trustworthy
- [R9] developers.google.com/assistant/conversation-design/errors（2024-09-18）
- [R10] learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/104（2026-03-04）

**还没有核实的内容**：
- Vertex AI 页面正文抓不到，所以 Vertex 上 3.8 Live 的模型 ID、region、voice 列表没有核实。
- Whispers from the Star 和 Suck Up! 到底是按住说话还是点按切换，没有找到明确来源。
- `customVocabulary` 等新转写字段对 3.8 Live 是否生效，需要实测。