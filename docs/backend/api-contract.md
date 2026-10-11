# 前后端接口约定（api-contract.md）v1.0.13

负责人：后端 · 状态：**v1.0.13，冻结**（v1.0 在 C-1 冻结；v1.0.1 把 C-1 评审定下的写进正文；v1.0.2 把 B-1 评审定下的几处顺序写进正文；v1.0.3 把 B-0、F-2b 评审和 S-077 ⑫ 定下的写进正文；v1.0.4 把数据契约 1.7 里前端要拿到的几样加进接口；v1.0.5 按 B-3 卡放宽三处 Schema、补一条错误说明；v1.0.6 按 UX 定的文案改下发的事件句和一句叙事，不改形状；v1.0.7 按 B-4 卡写明作废、意图确认的顺序和评测入口的三项，不改形状；v1.0.8 按 B-6 写明录音文件的格式，不改形状；v1.0.9 按 B-7 写明 manifest 的缓存和生成规则、开局时次数和进行中的局谁先查，会话没就绪时缓存整段按住的音频，不改形状；v1.0.10〜v1.0.12 在 B-9、B-5 和重连补发的 PR 里；v1.0.13 加 manifest 的地名、地图和「なぜ」的节拍出处，只做加法）：之后只做加法（第 0 节「版本」），每种消息和响应的 JSON Schema 在 `packages/contracts/schemas/api/`。v0.3 吸收了前端评审 17 条（`frontend/reviews/backend-v0.1.md` 和 frontend-design 第 14 节 1〜17）、数据评审 16 条（`data/reviews/backend-v0.1.md`）、ux-design 18.2 的接口要求，以及 decisions S-022〜S-053、D-012〜D-015。v0.3.2 和数据契约 v1.2 对齐。逐条对照见第 9 节。
数据字段以 `data/contracts.md` 为准（v1.7；标「契约 1.1」「契约 1.2」「契约 1.4」的字段是这几个小版本加的；1.3 加的随身物品不进接口，物品只出现在 `give` 类按钮上；1.6 的结局卡见 2.8；1.7 的位置点、幕末副题和落地、固定演出、可调查物见 2.3、3.8、3.11、3.14），本文只定义传输形状。字段名 camelCase；WebSocket 消息类型 snake_case。
相关：`backend/backend-design.md` v1.0.9（为什么这么设计）· `frontend/frontend-design.md` · `ux/ux-design.md`
最近更新：2026-10-11（v1.0.13）

---

## 0. 总则

| 项 | 约定 |
|---|---|
| 来源 | 静态资源和 API **同源**（`https://<同一域名>/` 和 `/v1/...`），负载均衡分流，CDN 只缓存静态资源（Q-B7，前端已确认） |
| 版本 | 路径带 `/v1`；只做加法，前端忽略不认识的字段和消息类型；删字段或改语义升 `/v2` |
| 鉴权 | 邀请码登录后发会话 Cookie（`HttpOnly; Secure; SameSite=Lax`），**有效期 30 天，每次使用滑动续期**。前端不接触任何令牌 |
| 跨站防护 | WebSocket 握手校验 Cookie 和 `Origin`；会改数据的 REST（POST、DELETE）要求 `Content-Type: application/json` 并校验 `Origin`，不符合返回 `403 forbidden` |
| 格式 | REST：JSON（UTF-8）。WebSocket：控制消息是 JSON 文本帧，音频是二进制帧（3.1） |
| 故事时间 | `t` = 故事分钟（contracts 第 0 节，Day 0 00:00 起算）；`tLabel` 由服务端用世界模型的 `clock.labels` 生成，前端直接显示，例：`t=1110` →「約束の日・日没前」，`t=1380` →「約束の日・夜」〔格式和时段按 ux-design 4.2、S-037；世界模型的 `clock.labels.format` 已是「{day}・{band}」（契约 1.1）〕。界面上不出现「刻」，接口里也不再有 `koku` |
| ID | 运行时 ID = 前缀 + ULID：`pt_` 一局、`turn_` 一轮、`ev_` 事件、`mem_` 记忆、`prm_` 约定（契约 1.1）、`draft_` 待确认的举动、`rev_` 关键时刻、`end_` 结局、`plan_` 幕末打算的替代去处（3.11）。世界模型 ID 原样用（`char.melos`、`place.syracuse-square`、`scene.syracuse-square`、`act.1`、`beat.05`、`exit.1.road`） |
| 幂等 | 会产生副作用的 POST / DELETE 带 `Idempotency-Key` 头（前端生成 UUID，同一次操作的重试用同一个）；WebSocket 上的动作带 `clientMsgId` |
| 位置点 | 场景里的位置点叫 **`spot`**（喷泉东侧、市场西侧，前端在 3D 场景里定义，后端只传名字）。`anchor` 在本项目只指故事锚点（世界模型 `anchors`） |
| 文字 | 服务端返回的文字（台词、叙事、摘要、记忆、结局）都是纯日语文本，前端按 `textContent` 渲染。任何数值（信任、体力）都不给前端显示用的原值，只给标签和等级 |
| 可见性 | 推给前端的事件只含**玩家可见投影**（contracts 2.6：改的是可见变量或节拍走向，并且玩家在场或是玩家做的；不在场的，在幕切换的「その頃」里交代后才可见）。被否决的候选事件、内部字段（`check`、`origin`、提示词版本）不推 |
| 大小 | 静态内容放 manifest（2.1）；快照只给当前场景（2.3），≤ 10 KB；之后只推增量（`commit`） |

---

## 1. 鉴权

### `POST /v1/auth/login`
```json
// 请求
{ "inviteCode": "XXXX-XXXX" }
// 200：Set-Cookie 会话；响应体同 GET /v1/me
```
`inviteCode` 不限格式（≤ 64 字），前端只去掉前后空格。错误：`401 invalid_invite`、`429 rate_limited`（带 `retryAfterSeconds`）。

### `POST /v1/auth/logout` → 204

### `GET /v1/me`
前端启动时先调它；任何 REST 返回 `401`、或 WebSocket 以 `4001` 关闭时，前端跳到邀请码页面，登录后回到原来的局。
```json
{
  "user": { "userRef": "u_01J…" },
  "limits": { "runsToday": 1, "runsPerDay": 5, "voiceMinutesLeft": 52 },
  "activePlaythrough": {
    "playthroughId": "pt_01J…", "roleId": "role.traveler", "roleName": "旅人",
    "actId": "act.2", "tLabel": "約束の日・夜", "updatedAt": "2026-10-06T12:00:00Z"
  }
}
```
`activePlaythrough` 没有进行中的局时为 `null`。封面据此直接显示「続きから」（S-024）。

---

## 2. REST

### 2.1 `GET /v1/books/{bookId}/manifest`
不变的内容，全部由仓库里的东西生成，不手写（v1.0.9，B-7）：世界模型、B-6 的声音清单、前端的场景包。正式网关和 mock 用同一个生成器（`services/backend/src/zoujin_backend/manifest.py`），网关开进程时生成一次，换世界模型、声音或场景包都要重启。要登录（邀请制，没有会话回 401）；书不是网关开新局用的那本回 404 `not_found`。

- 缓存（v1.0.9）：地址不带版本。响应头 `ETag: "<manifestVersion>"`、`Cache-Control: private, no-cache`；前端每次带 `If-None-Match` 问，没变回 304、不带内容。录音和场景包的文件自己长缓存（见下）。
- `manifestVersion`（v1.0.9）：`{worldModelVersion}+{hash}`，hash 是除它以外整份 manifest（键排序的 JSON）的 sha256 前 8 位。世界模型里给玩家的那些字段、声音清单、任何一个场景包的入口文件变了，它就变；同样的输入每次一样。只用来比相等，不要解析。
```json
{
  "manifestVersion": "hashire-merosu@1.0.0-slice.3+4f3a91c2",
  "book": { "id": "hashire-merosu", "title": "走れメロス", "author": "太宰治" },
  "roles": [
    { "roleId": "role.traveler", "name": "旅人", "summary": "…", "startSceneId": "scene.syracuse-square", "startActId": "act.1" }
  ],
  "scenes": [
    { "sceneId": "scene.syracuse-square", "places": ["place.syracuse-square", "place.stonemason-workshop", "place.execution-ground"],
      "assetUrl": "/scenes/80778e4c/syracuse-square/scene.json", "assetVersion": "80778e4c" }
  ],
  "places": [
    { "placeId": "place.syracuse-square", "name": "シラクスの広場と大路", "sceneId": "scene.syracuse-square" },
    { "placeId": "place.neighbor-village", "name": "隣村", "sceneId": null }, "…"
  ],
  "characters": [
    { "id": "char.melos", "name": "メロス", "reading": "メロス", "talkable": true,
      "prerecorded": {
        "aizuchi": [{ "url": "/assets/voice/hashire-merosu/melos-aizuchi-1.9c1e2b7a.m4a", "text": "…", "durationMs": 420 }, "…", "…"],
        "unheard": [{ "url": "/assets/voice/hashire-merosu/melos-unheard-1.03d4e5f6.m4a", "text": "…", "durationMs": 1300 }, "…"],
        "wait": { "url": "/assets/voice/hashire-merosu/melos-wait-1.5a6b7c8d.m4a", "text": "…", "durationMs": 900 },
        "cues": { "arrival_capped": { "url": "/assets/voice/hashire-merosu/melos-arrival-capped.e1f2a3b4.m4a", "text": "……これなら、間に合う。", "durationMs": 2100 } }
      } }
  ],
  "acts": [ { "actId": "act.1", "title": "約束の日", "sceneIds": ["scene.syracuse-square", "scene.castle-throne"] } ],
  "clock": {
    "deadlineT": 5460, "sunsetMinuteOfDay": 1140,
    "days": ["約束の日", "一日目", "二日目", "三日目"]
  },
  "ruby": [ { "word": "邪智暴虐", "reading": "じゃちぼうぎゃく" } ],
  "setPieceVoices": {
    "piece.gate-taken/2": { "url": "/assets/voice/hashire-merosu/guards-gate-taken-2.7d2a9c10.m4a", "text": "下がれ、旅の者。ここから先は、通さぬ。", "durationMs": 2600 }
  }
}
```
- 生成规则（数据评审第 1 条；v1.0.9 写明只出真能加载的）：
  - `book` 只有 `id`、`title`、`author`；世界模型的内部字段（`note`、`cite`、`inferred`、变量）不出。
  - `roles`：`release` 不大于开放版次（网关的配置 `ZJ_RELEASE`，第一版 1）、而且开局场景有场景包的身份，世界模型里的顺序。`summary` = `Role.summary`；`startSceneId` = `Role.startPlace` 的 `sceneRef`；`startActId` = `Role.startAct`。
  - `scenes`：有场景包的场景，世界模型里的顺序；`places` = 世界模型里 `sceneRef` 指向它的地点。
  - `places`（v1.0.13）：世界模型的全部地点，世界模型里的顺序；`name` = `Place.name`，地图节点详情、「谁知道这件事」旁边等要显示地名的地方用（幕末副题照旧用 `act_transition` 带的字）。`sceneId` = `Place.sceneRef`，没有场景、或那个场景没有包（不在 `scenes` 里）时为 `null`。地点的别的字段（`note`、`cite`、连通关系、变量）不出。
  - `acts[].sceneIds` = `Act.scenes` 里有场景包的；一个都没有的幕不出（每一幕至少一个场景）。
  - `characters`：世界模型的全部人物（不只这一版出场的），`reading`、`talkable` 照世界模型。
  - `clock`：`deadlineT` = `clock.deadline.t`，`days` = `clock.labels.days`。`ruby` 照世界模型的注音词表。
- 场景包（v1.0.9）：场景 `scene.x` 看场景包目录里的 `x/`，入口文件是 `index.json`（F-10，一个场景几个包），没有就是 `scene.json`（广场）。入口能走到的目录：场景自己的目录，加上 `index.json` 的 `packs[].manifest` 所在的目录和 `sharedPacks`（都在场景包目录下一层，例：`road-river` 走到 `road-river-calm`、`road-river-flood`、`road-common`）。`assetVersion` 是这几个目录里全部文件（相对路径和内容）合起来的 sha256 前 8 位，包里任何一个文件变了版本就变（`index.json` 只列相对地址、不带 sha，只哈希入口不够，前端 2 的 #114 评审）。`assetUrl` = `/scenes/<assetVersion>/<目录>/<入口文件>`，版本在最前、不用查询参数：部署时把入口能走到的目录一起放在 `/scenes/<assetVersion>/` 下，`../road-river-calm/scene.json` 这样的相对地址落在同一个版本里。包里别的文件的地址相对 `assetUrl` 算，`/scenes/<版本>/` 下的文件都长缓存（`immutable`）；拿着旧 manifest 的玩家照样能加载旧版的包。走到场景包目录外、或引用的目录不在的场景不出。两个入口都没有的场景没有包，不出现在 `scenes` 和任何一幕的 `sceneIds` 里。玩家走到没有包的场景时，前端留在当前画面，只出字幕和旁白。
- `prerecorded`：ux-design 16.2 的 6 句（相槌 3、听不清 2、等一下 1），后端用这个角色的声音在构建时生成（backend-design 3.6），前端在场景加载时解码。每一句是 `{ url, text, durationMs }`：`text` 是剧本原文（字幕用它，`source: "script"`，S-071），`durationMs` 是实际音频长度，前端按它分段跟着声音出字幕。现在所有固定台词都是预录的；以后若有服务端经 WebSocket 推的固定台词，`transcript {final: true, source: "script"}` 会在第一个音频包之前到。声音定了以后才有（Q-004）。`cues`：由服务端在某个时刻触发的固定台词，键是 `commit.cue.kind`（3.4）；现在只有梅洛斯的 `arrival_capped`，只放在世界模型 `clock.deadline.earliestArrivalCue.speaker` 那个人物身上，文字和它的 `line` 一字不差（同一条里的 `narration` 是地の文，没有声音）。只有能对话的人物带 `prerecorded`（v1.0.9 写明）。
- `ruby`：注音词表，词由数据工程出（F-11）。
- `setPieceVoices`（v1.0.4）：固定演出（3.14）里人物的预录句，前端在场景加载时和 `prerecorded` 一起解码。键是「{固定演出 ID}/{序号}」，序号是这一句在那条固定演出 `lines` 里的位置（从 1 起，地の文也算；上面的例子是 `piece.gate-taken` 的第 2 行，警吏的那句）。和 `prerecorded` 一样构建时用这个人物的声音生成（ux-design 16.2，声音按 UX 的文案表），不能对话的人物（警吏）也有；声音还没生成的句子没有键。世界模型没有固定演出时省略。生成时逐句和世界模型核对（v1.0.9）：那条固定演出的第 n 行是人物说的话、`text` 和它一字不差才出，对不上的、录音文件不在的只少那个键；声音清单是别的世界模型版本的也照这样核对。
- 录音文件（v1.0.8，B-6）：AAC-LC（`.m4a`），单声道，24 kHz；文件名带内容 hash，长缓存。文字和声音都相同的几个 `setPieceVoices` 键可以指向同一个 `url`（例：`piece.gate-taken/2` 和 `piece.gate-turned-away/2` 是警吏同一句）。一个人物的 6 句里有一句没生成成（自动检查三遍都不过）时，这个人物这次没有 `prerecorded`（Schema 要求 3/2/1 齐全），前端照没有预录处理；`cues` 和 `setPieceVoices` 少一句只少那个键。地址是 `/assets/voice/{bookId}/{文件名}`（v1.0.9 写明）：网关只发 manifest 里列着的文件，不要登录，`Cache-Control: public, max-age=31536000, immutable`，`Content-Type: audio/mp4`；清单外的、`voices.json` 本身、别的书回 404。
- 第一版只有 3 个身份（S-002、S-039 U-3），没开放的身份不出现在 `roles` 里。开局（2.2）只收 `roles` 里有的身份，别的回 400 `invalid_request`。
- manifest 只描述开新局用的那个世界模型版本。一局锁定的版本和它不同（评审部署期间换了版本）时，老局的人物名、场景可能和 manifest 有出入（backend-design 第 12 节）。

### 2.2 `POST /v1/playthroughs`（开局）
头：`Idempotency-Key`
```json
// 请求
{ "bookId": "hashire-merosu", "roleId": "role.traveler" }
// 201
{ "playthroughId": "pt_01J…", "snapshot": { …见 2.3… } }
```
错误：
- `409 active_playthrough_exists`：每账号同时只能有 1 局，响应里带 `activePlaythrough`（同 `/v1/me`，放在 `error` 外面，和它并列，第 5 节）。玩家选「新しく始める」时，前端先 `DELETE` 旧局（2.9），再开局。
- `429 daily_limit`（v1.0.9 写明顺序）：今天的开局次数用完时先回它，不回 409。不然玩家选「新しく始める」，前端先删了旧局，开新局才回 429，旧局没了新局也开不了。正式网关和 mock 现在都不拦次数（`/v1/me` 只显示），拦次数的卡照这个顺序做。

### 2.3 `GET /v1/playthroughs/{id}/snapshot`
当前场景的世界投影（开局、续玩、重连后对齐、幕切换后）。
```json
{
  "playthroughId": "pt_01J…",
  "lastSeq": 42,
  "status": "active",
  "actId": "act.1",
  "sceneId": "scene.syracuse-square",
  "clock": { "t": 1260, "tLabel": "約束の日・夜", "deadlineT": 5460 },
  "deadline": { "shown": true, "line": "期限　三日目の日没／遅れれば、身代わりが死ぬ" },
  "forecast": { "melosEtaT": 5460, "beforeDeadline": true },
  "player": { "roleId": "role.traveler", "place": "place.syracuse-square", "spot": "fountain-east" },
  "places": [
    { "id": "place.syracuse-square", "enabled": true },
    { "id": "place.stonemason-workshop", "enabled": false, "reason": "戸が閉ざされている" }
  ],
  "characters": [
    { "id": "char.old-man", "place": "place.syracuse-square", "spot": "market-west", "activity": "idle",
      "talkable": true, "relationLabel": "様子を見ている", "relationLevel": 3 },
    { "id": "char.crowd", "place": "place.syracuse-square", "activity": "idle", "talkable": false, "group": true }
  ],
  "interactables": [
    { "id": "obj.market-stall", "kind": "examine", "spot": "market-west", "label": "露店", "enabled": true, "estimatedMinutes": 0 }
  ],
  "actions": [
    { "actionId": "act_help_old-man_cart", "kind": "help", "target": "char.old-man", "label": "手伝う",
      "estimatedMinutes": 60, "melos": null, "melosMinutes": null, "melosInTime": null, "enabled": true }
  ],
  "pending": { "reveal": null, "confirm": null, "actEnd": null, "safetyPause": false, "approach": null },
  "voice": { "enabled": true, "degraded": false, "minutesLeftToday": 52 }
}
```
- `characters`：只给当前场景在场的；还没有关系的角色省略 `relationLabel` / `relationLevel`。`relationLevel` 是 1〜5（記憶帳的 5 格刻度），标签和区间按 contracts 第 4 节（文字由 UX 定，最上一档「信じている」）。`group: true`（v1.0.4，契约 1.7 的 `Character.group`：群众、警吏）的人物是一群人，不占位置点，没有 `spot`，前端按地点成群地放（契约 3.1）；别的人物都有 `spot`。
- `activity`：`idle`、`walk`、`run`、`talk`、`work`、`sleep`、`absent`；前端遇到不认识的按 `idle`。来源见 backend-design 2.7（世界模型节拍上的提示 + 叙事者推出）。
- `places`：本场景里各地点现在进不进得去（前端评审第 6 条）。`enabled: false` 时前端提前把那条路挡住，`reason` 是一句故事里的说明。
- `player.spot`：玩家站在哪个位置点（v1.0.4 写明来源，契约 3.1）。开局是布局的起点；幕切换以后按去处的 `ActExit.spot`（说出的打算成行时按 `Act.plan.spot`，3.11），没写就是这个地点的起点（`startSpots`）；之后的变化走 `commit.patch.player`（3.8）。
- `interactables`：场景里可「調べる」的东西（`kind: "examine"`，`estimatedMinutes` 为 0，S-038）和场景出口（`kind: "go"`，3.8）。`examine` 的来自世界模型的 `objects`（v1.0.4，契约 1.7 的 2.12）：`id` 是可调查物的 ID（`obj.…`），`label`、`spot` 照它；出口来自场景布局的 `exits`。之后的增减走 `commit.patch.interactables`（3.4）。
- `actions`：此刻能做的情境动作（`kind` 清单见 3.8）。`target` 是对象人物，没有对象的动作（`wait` 这类）省略这个字段，不给 `null`。按钮上显示 `label` 和 `estimatedMinutes`（前端写成「手伝う（1時間ほど）」；数字用半角，60 分以上写「時間」，ux-design 4.3）。`melos`：第四幕标出这个动作对梅洛斯的影响，`"delay"`（花他的时间）、`"hasten"`（替他争取时间）或 `null`（S-036、S-038）。`melosMinutes`：带 `melos` 的动作做了以后，梅洛斯到刑场的时刻**按这一局此刻的排程**实际变多少分钟，正数 = 晚到、负数 = 早到（S-066 ①）。服务端用共享规则的 `arrival_delta(本局, 动作的效果, 当前时刻)` 算（契约 2.10）：分钟数用去掉 `window.latest` 的排程算（拖到来不及时也算得出「1時間遅れる」），赶不赶得上看真实排程；含到达下限 `clock.deadline.earliestArrival`（17:30）：已经到下限时「帮他快」的动作是 0，按钮写「（変わらない）」，照常显示、照常能点（ux-design 4.3；动作还可能兑现互助）。第一次到下限时的那句话见 3.4 的 `cue`。世界模型里的 `Affordance.melosMinutes` 只是原作路径上的估计，不下发。`melosInTime`：做了以后这一局还赶不赶得上日没（`arrival_delta` 的 `inTime`），`false` = 做了就来不及；没有 `melos` 的动作给 `null`。这时按钮写对梅洛斯的影响，不写玩家花的时间，例「浅瀬を探す（10分早まる）」「引き止める（30分遅れる）」（UX 校对意见 `ux/reviews/data-world-draft3.md` 3.3）。没有 `melos` 的动作给 `null`，照旧显示 `estimatedMinutes`。
- `deadline.shown`：**玩家知道了约定以后**为 `true`，之后一直显示（S-049 ④、S-077 ⑫）；之前为 `false`，`line` 省略。「知道」= 数据契约 1.7 的 `knows(player, fact.promise)`，怎么知道的都算：人物告诉、在场看见立约（beat.05）、城门那一场（`piece.gate-promise`，S-077 ⑪）、第一幕幕末的幕切换（那条 `act-transition` 事件给玩家补 `learn`），先到的算。约定没有成立的局一直是 `false`。不再跟着 beat.05 的提交出：玩家不在场时，界面不能比叙事者先知道约定。
- `forecast`：梅洛斯预计到达刑场的时刻（太阳带上的菱形，ux-design 8.3），和 `deadline.shown` 同一个条件：**玩家知道约定以后**才给，之前为 `null`（防剧透）。`beforeDeadline: false` 时地图顶部那行变成「このままでは、日没に間に合わない」。
- `pending`：续玩时还没处理完的东西（第 4 节）。

### 2.4 `GET /v1/playthroughs/{id}/events?afterSeq=40&limit=50`
补拉事件。只含玩家可见投影：
```json
{
  "events": [
    { "eventId": "ev_…", "seq": 41, "turnId": "turn_…", "t": 1290, "dt": 10, "tLabel": "約束の日・夜",
      "type": "action", "actor": "player", "forPlayer": false,
      "place": "place.castle", "summary": "あなたがメロスの身元を保証した",
      "causes": ["ev_…"],
      "visibleEffects": [ { "kind": "beat", "beat": "beat.05", "change": "altered", "label": "王はあなたを覚えた" } ],
      "promise": null,
      "keyMoment": true, "supersedes": null }
  ],
  "lastSeq": 42
}
```
- `seq` 是一局唯一的序列。只改时间的事件（闲聊一轮的 10 分钟，3.7）和玩家不可见的事件**占用 `seq` 但不出现在这里**，所以 `seq` 会有空号；判断有没有漏消息用 `commit.fromSeq`（3.4），不要用连续性。
- `turnId`：来自哪一轮；到点的节拍、人物的打算这类不来自某一轮的事件没有这个字段。
- `actor`（数据评审第 6 条）：`"player"`、角色 ID、`"system"`（到点的节拍、期限、幕开始、环境的变化）、`"narrator"`（只用于 `type: "correction"`）。
- `summary`（v1.0.6，UX 10-10 定的）：下发时玩家一律写成「あなた」，句末不带「。」（前端放在括号里）。服务端只换这一局的身份名，名字里含身份名的人物不换（例「一団の旅人」）；库里存的那份照旧用身份名，模型、检查、评测读那一份。地图（2.5）、「なぜ」（2.6）、`commit`（3.4）里的 `summary` 同样。`visibleEffects` 的 `label`、记忆、结局标题不换（来自世界模型或人物的话）。
- `forPlayer: true`：角色为玩家做的事（ux-design 8.2「〜が、あなたのために動いた」；契约 1.1 `Event.beneficiary`）。
- `promise`：这个事件让一个约定成立、兑现或违背时给 `{ "promiseId": "prm_…", "change": "made" | "kept" | "broken" | "voided" }`（契约 1.1）。`voided` 只来自記憶帳删除时追加的 `type: "forget"` 事件（2.7）。
- `visibleEffects`：只含 `StateVar.visibleToPlayer` 的变量和节拍走向，`label` 来自 `valueLabels`（contracts 2.6），可直接显示。两种形状：节拍 `{ kind: "beat", beat, change, label }`；变量 `{ kind: "var", var, label }`，只给标签、不给原值（第 0 节）。前端只按它渲染，不从别的字段推断。
- `type: "correction"` 的事件带 `supersedes`，前端用它替换被修正的那一条（ux-design 8.5）。

### 2.5 `GET /v1/playthroughs/{id}/timeline`
連鎖反応マップ（ux-design 第 9 节）：按日子分段的时间线，事件和原作节拍合在一起，服务端排好。
```json
{
  "days": [
    { "day": 0, "label": "約束の日", "items": [
      { "kind": "event", "eventId": "ev_…", "t": 1290, "tLabel": "約束の日・夜", "summary": "あなたがメロスの身元を保証した",
        "place": "place.castle", "style": "player", "causedByPlayer": true, "forPlayer": false, "knownBy": ["char.king", "char.melos"] },
      { "kind": "beat", "beatId": "beat.05", "t": 1320, "tLabel": "約束の日・夜", "title": "王との問答と約束",
        "status": "altered", "known": true,
        "cite": [{ "source": "aozora:1567_ruby_4948@sha256:2a437c047d7f", "para": 22, "quote": "願いを、聞いた。その身代りを呼ぶがよい。" }] },
      { "kind": "beat", "beatId": "beat.06", "t": 1410, "tLabel": "約束の日・夜", "known": false }
    ] }
  ],
  "lastSeq": 42
}
```
- `style`：`player`（你的举动）、`caused`（因你而起）、`character`（人物自己做的）、`system`。
- 节拍 `status`：`canon`（原作どおり）、`hastened`、`delayed`、`prevented`、`altered`、`pending`。`canon` 就是契约 `WorldState.beats` 的 `happened`（照原作发生了），其余五个和契约同名。**还没到、或玩家还不知道的节拍 `known: false`**，只给时刻，不给 `title`（不剧透，ux-design 9.1）。
- `knownBy`：节点详情里的「谁知道这件事」，只列玩家见过的人物。
- `cite`（v1.0.13）：节拍的原作出处，世界模型 `Beat.cite` 原样（数据契约第 0 节的 `Cite`：原文版本、段落号、≤ 80 字的原句），节点详情列「原作」用（ux-design 9.1）。只在 `known: true` 时给，世界模型里没写出处的节拍省略。

### 2.6 `GET /v1/playthroughs/{id}/why?target=<eventId | beatId | revealId | forecast>`
「なぜこうなった？」：从目标往回走到玩家的举动或人物的举动。`target=forecast` 回答「为什么梅洛斯现在来不及」。
```json
{
  "target": "beat.05",
  "chain": [
    { "eventId": "ev_A", "seq": 12, "tLabel": "約束の日・夕方", "summary": "あなたが老爺に王のことを尋ねた", "actor": "player" },
    { "eventId": "ev_B", "seq": 30, "tLabel": "約束の日・夜", "summary": "老爺があなたをメロスに引き合わせた", "actor": "char.old-man", "forPlayer": true },
    { "beatId": "beat.05", "tLabel": "約束の日・夜", "summary": "王はメロスの願いを聞き入れた", "change": "altered",
      "cite": [{ "source": "aozora:1567_ruby_4948@sha256:2a437c047d7f", "para": 22, "quote": "願いを、聞いた。その身代りを呼ぶがよい。" }] }
  ],
  "collapsed": 0
}
```
- 节拍那一步带 `cite`（v1.0.13），和 2.5 一样，没写出处时省略。
- 链按时间正序，每一步都是**事件或节拍**（不是记忆）；`actor` 按 2.4。最长 12 步，超过时中间折叠，`collapsed` 给折叠了几步。
- 只讲发生了的事：被否决的候选事件不进链（数据评审第 7 条）。
- 叙事者「导演」的事件（S-031 ②）在链上和别的事件一样，按它在故事里的行为者显示；它的上一步一定是玩家或人物的举动（S-045、ux-design 8.6）。

### 2.7 記憶帳

`GET /v1/playthroughs/{id}/memories`：只列见过的人物，按人物分好四栏（ux-design 10.1），前端不从事件里推。
```json
{
  "characters": [
    { "character": "char.selinuntius", "relationLabel": "気を許している", "relationLevel": 4,
      "promises": [
        { "promiseId": "prm_…", "text": "工房を守る", "direction": "playerToCharacter", "status": "open", "eventId": "ev_…" }
      ],
      "didForYou": [ { "eventId": "ev_…", "text": "警吏の前で、あなたをかばった" } ],
      "youDid":    [ { "eventId": "ev_…", "text": "深夜、そばに座っていた" } ],
      "memories": [
        { "memoryId": "mem_…", "kind": "shared-moment", "text": "あの夜、隣に座っていてくれた人",
          "t": 1500, "tLabel": "一日目・深夜", "via": "witnessed", "promiseId": null }
      ] }
  ]
}
```
- `promises[].direction`：`playerToCharacter`（あなた→彼）、`characterToPlayer`（彼→あなた）；`status`：`open`（まだ）、`kept`（果たされた）、`broken`（破られた）、`voided`（删了这条约定的记忆，见下）。契约 1.1 `Promise`。服务端照给 `voided`，記憶帳里前端不显示它（ux-design 10.1，核对 U-2）。
- `memories[].via`：`witnessed`（見た）、`told`（聞いた）、`rumor`（噂で）。契约 1.1 `MemoryItem.via`。
- 没有内容的栏给空数组，前端整栏不显示。

`GET /v1/playthroughs/{id}/memories/{memoryId}/impact`：删除确认里「不会撤销的后果」一句（ux-design 10.2）。
```json
{ "keeps": "メロスとの約束は、そのまま続きます。", "voidsPromise": false }
```
- `keeps`：这条记忆来源的事件里，已经发生、删除也不撤销的后果，一句话；没有就是 `null`。由叙事者从已提交事件的 `summary` 生成（不读原话），结果缓存。
- `voidsPromise: true`：这条记忆属于一个还没兑现的约定。删除后这个约定变成 `voided`：人物不记得约定，就不会再去兑现，也不算违背；已经兑现的不撤销（S-009、S-029 ④）。确认里加一行「この約束も、なかったことになります。」
- 作废由一条事件记下（契约 1.1 第 4 节删除语义第 4 条）：服务端追加 `type: "forget"`、`origin: "memory"`、`actor: "player"`、`dt: 0`，效果是这个约定 `voided`，`summary` 只写「〜は、その約束を覚えていない」。重放事件得到同样的状态。这条事件照常经 `commit` 推送（`promise.change: "voided"`），不进地图时间线和「その頃」。

`DELETE /v1/playthroughs/{id}/memories/{memoryId}`（头：`Idempotency-Key`）→ `200`
```json
{ "memoryId": "mem_…", "deleted": true, "character": "char.king",
  "relationLabel": "様子を見ている", "relationLevel": 3, "promiseVoided": null, "sessionRebuilt": true }
```
- `promiseVoided`：作废了约定时给 `prm_…`，否则 `null`。
- 立即生效：这条记忆和产生它的整轮原话（玩家和人物的）一起清空；关系按剩下的记忆重算；这个人物以后不会再提起这件事；世界里已经发生的事不撤销（S-009）。
- `sessionRebuilt: true`：这个人物的语音会话被重建，WebSocket 上先收到 `session_preparing { reason: "rebuild" }`，约 1 秒后 `session_ready`。

### 2.8 结局
`GET /v1/playthroughs/{id}/ending` → 结局还没开始（还没有 `ending_started`）时 `404 not_found`；开始了、还没生成时 `202 { "status": "pending", "etaSeconds": 10 }`；生成后 `200`：
```json
{
  "endingId": "end_…",
  "world": {
    "outcomeId": "in-time-king-unchanged", "baseline": true,
    "title": "間に合ったが、王は変わらなかった",
    "epilogue": [ { "sentence": "…", "cites": ["ev_…"] } ],
    "contrast": { "original": "王は改心した。", "yours": "王は改心しなかった。", "beat": "beat.26" }
  },
  "you": {
    "title": "王の前で、黙らなかった旅人",
    "fate": "王城の客人として、市に残った",
    "didForYou": [ { "sentence": "老爺が、あなたをメロスに引き合わせた", "cites": ["ev_…"] } ],
    "youDid":    [ { "sentence": "セリヌンティウスとの約束を果たした", "cites": ["ev_…"] } ]
  },
  "characters": [
    { "character": "char.selinuntius", "rank": 1, "unchanged": false,
      "original": "メロスを信じて待ち、抱き合った。",
      "yours": [ { "sentence": "…", "cites": ["ev_…"] } ] },
    { "character": "char.melos", "rank": 2, "unchanged": false,
      "original": "日没の直前に刑場へ駆け込み、友と抱き合った。",
      "yours": [ { "sentence": "…", "cites": ["ev_…"] } ] },
    { "character": "char.philostratus", "rank": null, "unchanged": true }
  ],
  "card": {
    "title": "王の前で、黙らなかった旅人", "subtitle": "王城の客人として、市に残った",
    "characterLines": [ { "character": "char.selinuntius", "line": "…" }, { "character": "char.melos", "line": "…" } ],
    "contrast": "原作では王は改心した。あなたの世界では――",
    "fallbackImageUrl": "/assets/endings/in-time-king-unchanged.2b7d.webp"
  }
}
```
- 三层（D-015、S-032）：`world` → `you` → `characters`。`characters` 按受影响深浅排好（`rank` 从 1 起）；`unchanged: true` 的人物前端合成「ほかの人々は、原作どおりに。」一行。7 个可对话人物都在。
- `world.baseline`：`true` = 5 类底线结局之一（S-007、S-034）；`false` = 这一局生成的结局（S-031 ①），`outcomeId` 是本局生成的 ID，`title` 长短不定。
- 和契约第 5 节的对应（存储形状和 API 不完全一样）：`world.outcomeId` = `variant?.id ?? outcome`，`baseline` = 没有 `variant`，`world.title` = `variant?.title ?? title`；`world.epilogue` 存在 `player.epilogue`，API 挂在 `world` 下；`you.title` = `player.title.text`，`you.fate` = `player.fate.label`，`you.didForYou` / `youDid` = `player.didForYou` / `youDid`；`characters`、`card`、`world.contrast` 原样，`card` 由后端补 `fallbackImageUrl`。`signature`、`finalVars`、`changedBeats`、各处的 `causedBy` 不给前端。
- **每一局都有 `card`**（S-076，契约 1.6 第 5 节）：生成的结局取 `rank` 最前的 1〜3 人，排得上几人放几人；一个也没排上名时（全部 `unchanged`）放梅洛斯一句。结局校验两次都不过、改用模板尾声的局（S-065）也有卡，`card` 的字段全用 ux-design 11.4 对应那一组的预写句子（称号里填开局身份，人物行 1〜2 行），`world.title` 是世界模型 `endings.world` 里这一类的 `label`。前端的人物区按 1〜3 行排（S-076 ①：高度不变，行上下居中）。
- 文字的保证由后端生成侧负责（backend-design 2.9）：每句都有 `cites`；不逐字引用玩家原话（S-046；按契约第 5 节：先把世界模型里的专有名词换成占位符，再和这一局玩家的每句原话比，最长公共子串 ≥ 8 字就重写）；`card` 字数：`title` ≤ 14、`subtitle` ≤ 26、`characterLines[].line` ≤ 40（1〜3 条）、`contrast` ≤ 48（S-051）。前端的缩字号和截断只是最后的保险。
- 结局卡的插画：按 ux-design 11.3 用结局演出的一帧 3D 画面，由前端离屏渲染，**不经后端**（前端已确认可行，Q-B11 关闭；后端不生成插画）。截帧失败时用 `fallbackImageUrl`：每类底线结局一张预画插画，共 5 张；生成的结局用它的底线类（契约的 `world.outcome`）那张。
- 结局生成后，这一局的原话立即清空（S-035）。

### 2.9 删除整局
`DELETE /v1/playthroughs/{id}`（头：`Idempotency-Key`）→ `202`，后台按 data-design 5.2 L2 执行；进行中的 WebSocket 以 `4004` 关闭。

### 2.10 分享（P1，邀请码阶段不开放，S-026）
草案不变：`POST /v1/playthroughs/{id}/ending/share` 生成不可猜的分享 ID；`GET /v1/share/{shareId}` 无需登录，只返回 `card` 的字段和插画，不含原话、记忆和事件明细；`DELETE` 可撤销；删除整局即失效。正式公开时和公开一起问 zg。

### 2.11 `POST /v1/telemetry`
批量（≤ 50 条），字段由数据工程定（data-design 9.3）；不含音频、不含原话。成功回 `204`，没有响应体。公共属性每批带一次，只有粗粒度的设备信息（屏幕尺寸类、系统、浏览器、版本），服务端入库时抄到这一批的每条。前端的 `clientReleaseToAudibleMs` 带 `turnId`，和 `turn_complete.metrics.serverReleaseToFirstAudioMs` 按 `turnId` 对齐（前端评审第 13 条）。

---

## 3. 实时通道（WebSocket）

`GET /v1/playthroughs/{id}/live`（升级为 WebSocket）。一局一条连接，所有人物的语音和世界推送都走它。

### 3.1 二进制帧（音频）

```
字节 0      类型：0x01 = 玩家麦克风音频（上行），0x02 = 人物音频（下行）
字节 1–4    turnSeq：uint32 大端
字节 5–     PCM16 小端，单声道
              上行：16 kHz，每帧 40 ms（1,280 字节）
              下行：24 kHz，分片大小跟随 Live 原样转发
```
- **`turnSeq` 只在一条连接内有效**（前端评审第 1 条）：每次收到 `welcome` 后，前端从 1 重新分配；服务端在 `hello` 时清零。跨连接靠 `turnId`（全局唯一）对齐。
- **服务端发起的轮次**（人物先开口：3.10、3.9）由服务端分配 `turnSeq`，**最高位为 1**（`0x80000001` 起），不会和前端分配的撞号。开始时先推 `turn_started`。
- 打断后，`turnSeq` 属于已结束轮次的下行分片前端直接丢弃；服务端也丢弃已作废轮次的上行分片。

### 3.2 客户端 → 服务端（JSON）

| type | 字段 | 说明 |
|---|---|---|
| `hello` | `lastSeq`, `clientVersion`, `debug`（仅非生产环境） | 连接后第一条；服务端补发 `lastSeq` 之后的 `commit` |
| `near` | `character` | 玩家进入某个可对话人物 8 m 内：服务端预热会话。前端只对**最近的一个**发，离开 12 m 才发 `far`（滞回，前端评审第 7 条）；服务端另做 2 秒去抖 |
| `far` | `character` | 见上 |
| `focus` | `character` | 玩家点了这个人物（点的那一刻就发，不等走到）。服务端回 `session_preparing` / `session_ready` |
| `unfocus` | `reason`：`walk_away` / `silence` / `menu` / `dismiss` | 离开对话。`silence`：对话中玩家约 20 秒没有动作，前端让人物用动作收尾、结束对话（S-044 ①），不花时间 |
| `activity_start` | `turnId`, `turnSeq`, `purpose?` | 按下说话。人物正在说话时，前端先本地停播清空缓冲，再发这条（= 打断）。`purpose: "act_plan"` 用于幕末说出打算（3.11），其他情况省略 |
| （二进制 `0x01`） | — | 按住期间的音频；会话没就绪时前端把这一轮整段缓存在本地（最多 15 秒，v1.0.9；原来是 2 秒，后面的截掉，人物会只听到半句），`session_ready` 后连同 `activity_start` 一次按顺序发出。服务端按顺序转给会话，不看节奏 |
| `activity_end` | `turnId`, `turnSeq` | 松开 |
| `text` | `turnId`, `turnSeq`, `text`（≤ 200 字）, `via`：`typed` / `chip` / `correction`, `replaces?` | 文字输入，代替一轮语音；发文字也会打断正在说话的人物。`via: "chip"` = 点了候选话语；`via: "correction"` + `replaces: <被改正的 turnId>` = 识别改正（3.6） |
| `turn_retract` | `turnId` | 作废一轮：「取り消す」（人物还没开口）和「言い直す」（人物回答了、世界还没反应）都用它；12 秒没回应时前端也发它（3.6） |
| `action` | `clientMsgId`, `actionId?`, `kind`, `target?`, `params?` | 身体动作，先判后演（3.8）。快照 `actions` 里的动作带 `actionId`；同场景跨地点的移动用 `kind: "move"`。`target` 是人物 ID、地点 ID（`move`）或 interactable 的 ID：`move`、`examine`、`go` 必带；快照里的动作有 `target` 就原样带上；`wait` 这类没有对象的动作省略（服务端按 `actionId` 找回） |
| `confirm_answer` | `draftId`, `optionId` | 回答意图确认（3.9）。用声音回答时照常发一轮语音，不发这条 |
| `approach_arrived` | `character` | 走过来的人物到了玩家 2.5 m 内（3.10）；服务端收到后才让他开口 |
| `approach_dismiss` | `character`, `reason`：`dismissed` / `walked_away` / `timeout` | 玩家选了「いまは、いい」、走开，或人物等了 20 秒没等到（3.10） |
| `act_choose` | `clientMsgId`, `optionId`, `enRouteChoice?` | 幕末选给定的去处；去处带 `enRoute` 时，`enRouteChoice` 是玩家在过场页选的那一项的序号（3.11，契约 1.4） |
| `act_propose` | `clientMsgId`, `text`（≤ 200 字） | 幕末用文字说出自己的打算（3.11）；用声音时走 `activity_start { purpose: "act_plan" }` |
| `act_landed` | `actId` | 幕切换以后落地（v1.0.4，3.11）：`arrival` 带 `opener` 时，前端显示完落地那一行、玩家能动的时候发一次；服务端收到才让 `opener` 先开口 |
| `safety_resume` | — | 玩家在出戏卡上选了「物語に戻る」（3.12） |
| `ping` | — | 每 20 秒一次 |

### 3.3 服务端 → 客户端（JSON）

| type | 字段 | 说明 |
|---|---|---|
| `welcome` | `lastSeq`, `voice: { enabled, degraded, minutesLeftToday }`, `lastTurn`, `pending` | 回应 `hello`；`lastTurn`、`pending` 见第 4 节 |
| `session_preparing` | `character`, `reason`（`switch` / `rebuild` / `reconnect`）, `etaMs` | 需要等待演出（人物转身、吸气） |
| `session_ready` | `character`, `voiceAvailable` | 这个人物可以说话了 |
| `turn_started` | `turnId`, `turnSeq`, `speaker`, `reason`（`approach` / `leaving` / `confirm` / `arrival`） | 服务端发起的一轮：人物先开口（3.9、3.10；`arrival` 是 v1.0.4 加的幕切换落地，3.11）。`approach`、`arrival` 的一轮服务端把 `speaker` 当作已经 `focus` 的人物，前端不用另发 `focus` |
| `transcript` | `turnId`, `speaker`（`player` / 人物 ID）, `text`（可为 null）, `final`, `source`（只在人物的 `final: true` 上：`live` / `script` / `fallback`） | 字幕。**玩家的字幕在说话过程中就推**（`final: false`，S-025，前端第 9 条；能多早出来看 S-1 的 `first_user_transcript_ms`）；`final: true` 是这一句的定稿。**定稿可能在 `turn_complete` 之后才到**（转写会晚于语音到达，最多约 3 秒，backend-design 3.1）：前端收到 `turn_complete` 后不要锁死这一轮的字幕，同一 `turnId` 的 `final: true` 来了就替换。**人物的定稿带 `source`**（S-071）：`live` = Live 自己的文字；`script` = 剧本原文（固定台词、预录台词）；`fallback` = 补转写（Live 一段文字都没给时，`turn_complete` 一到就开始转写，3 秒截止，通常 `turn_complete` 后 1〜2 秒到）。补转写也失败时仍发定稿 `{final: true, text: null, source: "fallback"}`，前端就不用再等，字幕显示「（字幕を出せませんでした）」（ux-design 7.7）。每一轮人物都恰好有一条 `final: true`，三种例外没有：`turn_complete { audio: false }` 而人物没回答的轮，被出戏卡停下的轮（`turn_settled` 的 `outcome: "paused"`，3.12），和人物还一个字没说就被打断的轮（Schema 不许 `source: "live"` 配 `text: null`，这时和没回答一样不发）。被打断的轮只要人物说了，就有定稿，是说到一半的文字，在 `interrupted` 之后到。**降级为文字回答时**（`degraded` 之后），人物的定稿（`source: "live"`）一定在 `turn_complete { audio: false }` **之前**到：前端收到 `audio: false` 时这一轮已经有人物定稿 = 文字回答，没有 = 不回应 |
| （二进制 `0x02`） | — | 人物音频 |
| `interrupted` | `turnId` | 服务端确认打断（前端此时应该已经停播）。只在人物还在说（还没有 `turn_complete`）时被新的一轮打断才发；**被打断的轮没有 `turn_complete`**，`interrupted` 就是人物这边的结束。这一轮照样交给叙事者（玩家的话和人物说到一半的话），照常有 `turn_settled`。人物已经说完（`turn_complete` 到了、定稿还没到）时按下说话不算打断，那一轮照常交 |
| `turn_complete` | `turnId`, `audio`（bool）, `metrics: { serverReleaseToFirstAudioMs }` | 人物这一轮说完。**`audio: false` = 人物这一轮没有出声**（模型选择不回应），前端立即进入 `no-response`，不用干等 6 秒（前端第 15 条）；这时没有第一个音频分片，`serverReleaseToFirstAudioMs` 为 `null`。降级后的文字回答也是 `audio: false`，但定稿已经先到了（见 `transcript`） |
| `suggestions` | `turnId?`, `character`, `items: [{ text, kind }]` | 候选话语 2〜3 个（3.5）；`kind`：`ask` / `act` / `accept` / `decline`。新的一条替换旧的 |
| `turn_settled` | `turnId`, `outcome`, `eventIds[]`, `minutes` | **每一轮判完都推**，不管有没有事件（前端第 5 条、数据第 9 条）；见 3.4 |
| `commit` | 见 3.4 | 叙事者的一次提交，前端一次原子地应用 |
| `narration` | `line`, `ref?` | 不随事件的叙事一行（灰色地の文）：连续离题时的提示、幕将结束的预告（「日が傾いてきた。」）等。`ref` 是服务端内部的来源标记（节拍 ID、离题提示的规则名），只给日志和评测对照，前端不用、不显示 |
| `set_piece` | `pieceId`, `lines[]` | 固定演出（v1.0.4，3.14）：世界模型里写好的地の文和人物的预录句，按顺序演 |
| `confirm` | `draftId`, `character`, `prompt`, `options: [{ optionId, label }]`, `timeoutSec` | 意图确认（3.9） |
| `confirm_closed` | `draftId`, `optionId`（或 `null`）, `by`（`button` / `voice` / `timeout`） | 确认结束；`optionId: null` = 当作「不是」 |
| `approach` | `character`, `kind`（`request` / `news`） | 人物要走过来找你（3.10）；前端演出走近，到了发 `approach_arrived` |
| `action_result` | `clientMsgId`, `status`（`done` / `refused` / `partial`）, `eventIds[]`, `narration` 或 `setPiece`, `minutes` | 动作的判定结果；`narration` 是一句故事里的说明，拒绝也在故事里说。这个动作挂着固定演出时（v1.0.4，3.14）不带 `narration`，改带 `setPiece`（固定演出 ID），紧接着推那条 `set_piece`；两个正好给一个 |
| `act_ended` | `actId`, `recapLines[]`, `options[]`, `freeform` | 幕结束，给出去处（3.11）；每个去处带副题的前半 `where` 和后半 `sub`（v1.0.4） |
| `act_plan_result` | `clientMsgId` 或 `turnId`, `accepted`, `narration[]`, `alternative?`, `triesLeft` | 幕末说出的打算能不能成行（3.11）。用文字说时带 `act_propose` 的 `clientMsgId`，用声音说时带那一轮的 `turnId`，两个正好给一个；前端按它对上是哪一次，已作废那一轮的结果丢掉 |
| `act_transition` | `fromActId`, `toActId`, `recap[]`, `snapshot`, `arrival?` | 进入下一幕：「その頃」（≤ 3 件）、新场景的快照和落地（`arrival`，v1.0.4）（3.11） |
| `safety_pause` | — | 出戏卡（3.12） |
| `safety_hint` | — | 不暂停的小提示（S-069，3.12），一局最多一次 |
| `safety_resumed` | — | 回到故事 |
| `ending_started` | `trigger`, `staging` | 进入结局演出（3.13） |
| `ending_ready` | `endingId` | 结局已生成，用 2.8 取 |
| `turn_retract_result` | `turnId`, `status`（`retracted` / `too_late`） | 「取り消す」「言い直す」的结果；`too_late` 时前端把「……もう伝わってしまった。」当作叙事一行显示（地の文，和 `narration` 同样式，不以人物名义），**不播声音**，manifest 不加 `cues.too_late`（UX 定，核对 U-3）。这一行由前端从自己的文案表出，服务端不另发 `transcript` 或 `narration`，免得出两次 |
| `limits` | `voiceMinutesLeft` | 今天的语音时间剩 5 分钟时推一次（ux-design 第 12 节） |
| `degraded` | `voice: false`, `reason`（`budget` / `service` / `daily`） | 降级为文字回答 |
| `goaway` | `reason`（`deploy` / `maintenance`）, `reconnectAfterMs` | 服务端要关闭连接，前端按第 4 节重连 |
| `error` | 第 5 节的形状 | 不致命的错误；致命错误后服务端关闭连接 |
| `pong` | — | — |
| `event_rejected` | `turnId`, `candidate`, `failedRules`, `reason` | **仅调试模式**（`hello { debug: true }`，非生产环境）：候选事件被否决。`candidate` 就是写进事件流的那条被否决的事件：完整的 Event，`check.status: "rejected"`、`effects` 为空、`dt: 0`（契约第 3 节）。导演事件不合契约 3.2 的规矩时直接丢掉，不发这条 |

### 3.4 `commit` 和 `turn_settled`（一次提交原子地应用）

叙事者的一次提交（事件 + 世界状态 + 记忆 + 约定 + 可能的关键时刻）合成**一条** `commit`（前端评审第 4 条）：

```json
{
  "type": "commit",
  "fromSeq": 43, "seq": 45,
  "turnId": "turn_…",
  "events": [ { …2.4 的形状… } ],
  "patch": {
    "clock": { "t": 1300, "tLabel": "約束の日・夜" },
    "deadline": { "shown": true, "line": "期限　三日目の日没／遅れれば、身代わりが死ぬ" },
    "forecast": { "melosEtaT": 5460, "beforeDeadline": true },
    "characters": [ { "id": "char.melos", "place": "place.castle", "spot": "throne-front", "activity": "talk" } ],
    "places": [ { "id": "place.stonemason-workshop", "enabled": true } ],
    "actions": { "add": [ … ], "remove": ["act_help_old-man_cart"] },
    "interactables": { "remove": ["obj.market-stall"] },
    "player": { "place": "place.castle" }
  },
  "memories": [ { "character": "char.melos", "change": "added", "memoryId": "mem_…", "text": "王の前で、私をかばった旅の人",
                  "relationLabel": "気を許している", "relationLevel": 4, "kind": "help" } ],
  "promises": [ { "promiseId": "prm_…", "character": "char.selinuntius", "text": "工房を守る", "direction": "playerToCharacter", "status": "open" } ],
  "narration": [ "メロスは、王城の方へ駆けていった。" ],
  "cue": null,
  "reveal": {
    "revealId": "rev_…", "kind": "beat", "line": "メロスは、日没に間に合わないかもしれない。",
    "chain": [ …2.6 的 chain… ]
  }
}
```
- **序号**：一局只有一个 `seq` 序列。`commit` 覆盖 `fromSeq`〜`seq` 这一段（含两端），中间不可见的事件（3.7）也算在内。前端记住上一次的 `seq`；新 `commit.fromSeq` ≠ 上次 `seq + 1` 时，用 2.4 补拉再取快照。全是不可见事件的提交（例：玩家不在场的人物打算）也推一条 `events: []` 的 `commit`，让序号接得上。
- `patch` 的字段都是快照（2.3）字段的增量，按 id 合并（人物进场时带完整的 `CharacterPresence`，`group` 的人物也带 `group: true`，v1.0.5）；`actions` 和 `interactables` 用 `add` / `remove`，`add` 里的 id 已经有了就整条替换（例：`enabled` 变了）。`clock` 必带 `t`、`tLabel`，`deadlineT` 可省。`voice`、`status` 不走 `patch`。
- `memories[].change`：`added` / `updated` / `deleted`；記憶帳的查询失效重拉。`added`、`updated` 必带 `text` 和 `kind`，`deleted` 不带。
- `reveal`：关键时刻（S-041 的 4 种，3.4.1），**直接带上因果链**，不用再调 `/why`（前端建议第 8 条）。链和 `/why` 一样最长 12 步，超过时中间折叠，`reveal.collapsed` 给折叠了几步；没折叠时省略。
- `cue`：服务端在某个时刻触发的一句固定台词，没有时为 `null`。现在只有一种：`{ "kind": "arrival_capped", "speaker": "char.melos", "text": "……これなら、間に合う。" }`——这一局梅洛斯的预计到达第一次落在到达下限（17:30）的那次提交（S-066 ①，ux-design 4.3），只出一次；文字来自世界模型的 `clock.deadline.earliestArrivalCue`。梅洛斯和玩家在同一个地点时 `speaker` 是他，前端播 manifest 里他的 `cues.arrival_capped`（他正在说话就等这句说完）并显示字幕；不在时 `speaker` 为 `null`，`text` 是叙事（「この足なら、陽の沈む前に着く。」），按 `narration` 显示。断线后补发的 `commit` 里的 `cue`，前端按 `seq` 只演一次。
- 没有 `turnId` 的 `commit` 来自到点的节拍、人物的打算、导演事件或幕切换。

**`turn_settled`**：每一轮（语音、文字、动作）判完都推一次，在这一轮的 `commit`（如果有）之后：

| outcome | 含义 | `minutes` |
|---|---|---|
| `committed` | 有可见的事件，已在 `commit` 里 | 这一轮花的故事时间 |
| `no_change` | 闲聊，没有可见的事件；时钟照样走（3.7） | 10 或 15 |
| `rejected` | 候选事件被否决或降级，故事里的结果已由人物或叙事说出 | 同 `no_change` |
| `retracted` | 被作废（3.6） | 0 |
| `no_response` | 人物没有回应、或系统出错 | 0 |
| `paused` | 触发了出戏卡（3.12） | 0 |

`turn_settled` 之后这一轮不能再作废，前端据此收起「言い直す」按钮（不再按固定 5 秒）。

#### 3.4.1 关键时刻（`reveal.kind`，S-041）

| kind | 什么时候 |
|---|---|
| `beat` | 事件让原作的一个节拍 `prevented` / `delayed` / `hastened` / `altered` |
| `eta` | 梅洛斯的预计到达越过日没线（来得及 → 来不及，或反过来）：提交前后各用共享规则算一次 `clock.deadline.watchBeat`（beat.24）的排定时间，和 `deadline.t` 比 |
| `ending` | 预测的世界结局发生实质变化：提交前后各预测一次「玩家不再做任何事」的结局，结局署名（契约 2.9.1 `endings.signature`）不同 |
| `favor` | 一个人物兑现了为你做的一件大事（D-012）：事件兑现了 `major` 的互助（`Character.mutualAid`），或叙事者判定同等分量，`beneficiary: "player"` |

后端判定，和契约 1.1 第 3 节的四条一致；数据在评测里统计频率（目标一局 3〜5 次）。第一个通常是立约（beat.05）。期限一行和预报不跟着立约出，跟着**玩家知道约定的那次提交**出（2.3）：玩家在场看见立约时是同一条 `commit`（`patch.deadline` + `patch.forecast`）；城门那一场、人物告诉时是那一轮的 `commit`；第一幕幕末才知道时在 `act_transition.snapshot` 里。玩家还不知道约定时也不出 `eta`（那句话讲的是期限）。

### 3.5 一轮对话的顺序（示例）

**普通的一轮**
```
→ near {character: "char.melos"}
← session_preparing {character: "char.melos", reason: "switch", etaMs: 800}
→ focus {character: "char.melos"}
← session_ready {character: "char.melos"}
→ activity_start {turnId: "turn_01", turnSeq: 1}
→ [0x01 | 1 | PCM] × N
← transcript {turnId: "turn_01", speaker: "player", text: "王城に", final: false}    （说话途中）
→ activity_end {turnId: "turn_01", turnSeq: 1}
← transcript {turnId: "turn_01", speaker: "player", text: "王城に行くのか？", final: true}
← [0x02 | 1 | PCM] …                 ← 服务端测：收到 activity_end 到这里
← transcript {speaker: "char.melos", text: "ああ、", final: false} …
← turn_complete {turnId: "turn_01", audio: true, metrics: {serverReleaseToFirstAudioMs: 1180}}
← transcript {turnId: "turn_01", speaker: "char.melos", text: "ああ、行く。…", final: true, source: "live"}
← suggestions {turnId: "turn_01", character: "char.melos", items: [...]}         （约 1 秒后）
   …（叙事者判定 2〜5 秒；「言い直す」窗口）
← commit {fromSeq: 43, seq: 45, turnId: "turn_01", …}
← turn_settled {turnId: "turn_01", outcome: "committed", eventIds: [...], minutes: 10}
```

**闲聊的一轮**：没有 `commit` 里的可见事件；时钟仍然走 10 分钟，所以照样有一条只带 `patch.clock` 的 `commit`（`events: []`），然后 `turn_settled { outcome: "no_change", minutes: 10 }`。

**候选话语**（ux-design 7.8）：人物说完、或会话刚就绪时，服务端用当前局势生成 2〜3 个，至少一个不是问句（`act` 或 `accept`）。人物请你帮忙时，一个 `accept`（「手伝います」）、一个 `decline`（「いまは、いい」）。点了 `decline` 在对话里等于一句普通的话；只有 `approach` 时的「いまは、いい」走 `approach_dismiss`（3.10）。前端按 UX 规则决定什么时候收起（玩家自己说了 3 次后）。

### 3.6 作废一轮（`turn_retract`）和识别改正

UX、前端统一用一个消息（ux-design 7.6、frontend 第 14 节第 17 条）。规则：

1. **窗口**：从按下到这一轮的 `turn_settled` 之前都能作废。叙事者最早在 `turn_complete` 后 3 秒才提交这一轮（UX 的「言い直す」按钮约 5 秒，实际窗口 3〜5 秒）；被打断的轮从打断时起算。文字的一轮也一样。
2. **服务端做的事**：停止转发这一轮的下行音频；这一轮不交给叙事者，不花时间；原话立即清空（数据评审第 5 条）；**重建这个人物的语音会话，新会话里没有这一轮**（backend-design 3.2）。重建在玩家重说的同时进行，约 1 秒，期间玩家可以按下说话（前端把这一轮整段缓存，最多 15 秒，3.2）。所以人物是真的没听到，不只是「被要求忽略」。
3. 回 `turn_retract_result { status: "retracted" }`；随后 `turn_settled { outcome: "retracted", minutes: 0 }`。
4. **太晚**（这一轮已 `turn_settled`）：回 `turn_retract_result { status: "too_late" }`，世界里的结果不撤销。
5. **12 秒没回应**：前端发 `turn_retract`，人物用预录的「听不清」第 1 句接住（ux-design 7.5）。
6. **识别改正**（S-025）：玩家点自己的字幕改正后，前端发 `turn_retract { turnId: 旧 }`，紧接着 `text { turnId: 新, via: "correction", replaces: 旧, text: 改好的句子 }`。服务端等会话重建好再把这句送进去（前端照常显示 `thinking`）。旧的一轮已经 `too_late` 时，只当作新的一轮处理，之前那句的后果不撤回。
7. **幕末用声音说的打算**（3.11，v1.0.7）也能作废，规则照第 3 条：窗口到叙事者提交为止，最早在玩家的定稿后 3 秒；作废了回 `retracted`，不推 `act_plan_result` 和 `turn_settled`，不算一次试次；已经判完的回 `too_late`，结果照旧（成行的照样转场）。还在说时作废：不推转写的定稿，不写任务。
8. 服务端发起的一轮（落地 `arrival`、确认的反问 `confirm`）和不认识的 `turnId` 回 `too_late`，什么都不改（v1.0.7）。

### 3.7 时间怎么算（S-038、S-036；服务端算，前端只显示）

| 动作 | 故事时间 | 梅洛斯的时间 |
|---|---|---|
| 和人物一来一回 | 第一〜三幕 10 分，第四幕 15 分；有没有事件都算 | 不影响，除非这一轮的事件让他停下 |
| 第四幕和梅洛斯「並んで走りながら話す」 | 15 分 | **不花**（他边跑边说，到达预计不变） |
| 作废、没回应、出错、出戏卡的一轮 | 0 | — |
| 场景内走动、「調べる」 | 0 | — |
| 情境动作 | 按钮上的 `estimatedMinutes`；实际不同时 `action_result.narration` 说明原因 | `melos: "delay"` 的动作把时间加到他身上；`"hasten"` 还给他时间 |
| 场景之间移动 | 按 `Place.adjacent` 的路程 | — |
| 「時を進める」（`kind: "wait"`） | 跳到这个地点的下一个节拍 | — |
| 幕末选择 | 跳到下一幕的起点（`ActExit.t`，含 `alignTo` 的偏移） | — |

闲聊一轮的时间由一条只改时钟的事件承载（`type: "say"`，没有 `effects`），占 `seq` 但不出现在事件列表、地图和「その頃」里（契约 1.1 第 3 节）。

节拍到点、推迟和提前按契约 2.4.1、2.5.1：有 `delays` / `hastens` 出边的节拍到点时前提不成立，当场记 `prevented`，它的分钟马上退还给下游；`timeLink: "order"` 的边只要求先后、不传递偏移（现在只有 edge.17-18，洪水 → 渡河）。服务端的规则库从数据的 `data/spikes/pipeline/worldsim.py` 移植，快照里的 `deadline`、`forecast` 也用它算，和数据评测用同一批用例对照。

### 3.8 动作和场景内移动

- **同一地点里走路**：前端本地处理，不发消息、不等服务端。
- **同一场景里跨地点**（从广场走进石屋的工房）：前端照常走过去，同时发 `action { kind: "move", target: "place.stonemason-workshop" }`，不等结果；服务端回 `action_result`（不花时间）。进不去的地点已经在快照的 `places` 里标成 `enabled: false`，前端提前挡住，正常不会走进去再被推出来。
- **地点关上时玩家在里面**（F-2b 评审）：关这个地点的那次 `commit`（`patch.places` 里它变成 `enabled: false`）同时带 `patch.player { place, spot }`，把玩家放到同场景里和它相连的地点，`spot` 是那边的一个位置点（服务端按世界模型选）。前端收到和本地不同的 `patch.player.place` 时，直接把玩家摆到 `spot`，不走过去，也不回发 `move`（进场、重连按快照摆人也一样）。前端另有兜底：玩家所在的地点在他走出去之前照样能走。
- **玩家刚走进去、服务端已经关了**（关地点的 `commit` 和 `move` 擦肩而过）：`move` 回 `action_result { status: "refused" }`，带一句 `narration`，不写事件、不带 `commit`，服务端记的玩家地点不变，还是原来的地点。前端把玩家送回原来的地点（走回门口还是直接摆过去，前端定），之后不再为这次送回发 `move`。`move` 进任何 `enabled: false` 的地点都这样回。
- **做完情境动作玩家站到别处**（v1.0.4，契约 1.7 的 `Affordance.playerSpot`，例：「家まで送る」做完站在老爺家门口旁边）：这个动作的 `commit` 带 `patch.player { spot }`（地点不变，只给 `spot`）。前端和上面关地点一样直接摆到那个点，不走过去，不回发 `move`；按本节末尾的做法，`commit` 压到动作播完再应用，玩家就是在动作演完以后到那个点的。
- **走动中的人物被玩家点了**（前端第 13 条）：玩家能和画面上看得到、走得到的人物说话；叙事者把这次对话的地点算作玩家所在的地点。
- **换场景**：只通过幕末（3.11）或场景出口的 interactable（`kind: "go"`，先判后演，配过场演出）。出口出现、消失或能不能走变了，走 `commit.patch.interactables`（3.4）。
- **`kind` 清单**（ux-design 18.2）：

| kind | 日语 | 说明 |
|---|---|---|
| `examine` | 調べる | 0 分；`action_result.narration` 一行叙事；挂着固定演出时演固定演出（3.14） |
| `give` | 渡す | 给人东西；`params.item` |
| `follow` | ついて行く | 跟着一个人物走 |
| `block` | 引き止める | 拦住；第四幕对梅洛斯是 `melos: "delay"` |
| `help` | 手伝う | 帮一个人物做事；互助的主要入口（S-029） |
| `wait` | 時を進める | 跳到这个地点的下一个节拍 |
| `go` | 行き先を選ぶ | 场景出口 |
| `shortcut` | 近道を走る / 近道を教える | 第四幕 `melos: "hasten"` |
| `run-together` | 並んで走る | 第四幕和梅洛斯并肩跑，之后的对话不花他的时间 |
| `hasten` | 先に走って知らせる | 替梅洛斯争取时间 |
| `move` | — | 同场景跨地点（见上） |

动作先判后演：服务端判定后才回 `action_result`，前端在 `done` / `partial` 时播动作，`refused` 时播 `narration`。**顺序**：动作写了事件时，服务端先推这次提交的 `commit`，再推 `action_result`（和对话的 `commit` → `turn_settled` 一样）。前端可以把 `action_result` 之前到的 `commit` 先压住，播完动作再按 `seq` 应用，免得人物在动作开始前就被 `patch` 挪走、记忆提示先于动作弹出（B-1 评审，前端的做法）；`action_result` 带 `setPiece` 时也可以压到固定演出演完（例：城门的警吏说出约定，那条 `commit` 里的期限一行在他说完以后才出，3.14）。快照里出现的 `actions` 都是此刻有希望成立的（地点、身份、条件已经满足），但结果仍以判定为准。

### 3.9 意图确认（`confirm`，S-040）

只用于**会改变主线又撤不回**的举动，一局 0〜3 次：

1. 叙事者从这一轮里提出一个不可逆的关键事件，但玩家的意思不确定（例：「私が人質になります」）。这个事件先存成草稿（`draft_…`），不提交。
2. 人物反问。如果人物这一轮的回答已经是在反问（「……本気で言っているのか。」），就不再说一次；否则服务端发起一轮（`turn_started { reason: "confirm" }`），让人物用自己的声音问。
3. 推 `confirm { draftId, character, prompt, options: [{ optionId: "yes", label: "本気だ" }, { optionId: "no", label: "いや、違う" }], timeoutSec: 30 }`。
4. 玩家点选项（`confirm_answer`），或者用声音回答（照常一轮语音；服务端判断这句话是不是在回答确认，是就当作选了对应的选项）。
5. `yes`：叙事者按当前状态重新检查草稿再提交（状态这期间变了的话可能被拒绝）；`no` 或 30 秒没回答：草稿丢弃，不花时间。两种都推 `confirm_closed`。

顺序和限制（v1.0.7，B-4）：

- 原来那一轮照常先提交：`commit`（含这一轮的 10 分钟和别的事件）→ `turn_settled`，然后人物反问、推 `confirm`。反问的那一轮（`reason: "confirm"`）没有 `turn_settled`，不交给叙事者、不花时间；它的定稿存在原来那一轮下面。
- 玩家已经不在和这个人物说话（`unfocus` 了、换了人），或已经开始说下一句时，不起反问的一轮，直接推 `confirm`，`prompt` 照样是那一句。
- 答「是」：先推草稿那次 `commit`（事件 `dt: 0`，`turnId` 是原来那一轮；重查没过时没有可见的事件，`narration` 一句说这件事没成），再推 `confirm_closed`。答「不是」、超时：只推 `confirm_closed`。
- 用声音回答的那一轮照常花 10 分钟：那一轮的 `commit` → `turn_settled` → 草稿的 `commit` → `confirm_closed { by: "voice" }`。
- 一局最多问 3 次；同一时间最多一个草稿。多出来的不问，照旧当作没说。
- 收幕时不留草稿：开着的按超时关掉，`confirm_closed { optionId: null, by: "timeout" }` 排在 `act_ended` 前面；收幕那一轮新提出的不问。幕末待选时的 `confirm_answer` 忽略。
- `draftId` 不是开着的草稿（已经关了、不认识）的 `confirm_answer` 忽略，不推东西。

### 3.10 人物主动开口（`approach`，S-030 ①、S-044）

1. 服务端决定一个人物要来找你（请求或消息），推 `approach { character, kind }`。规则由服务端保证：只在你不在对话里时；同一人物每幕最多 1 次（原作固定事件不算）；开口第一句是请求或消息，不是盘问。
2. 前端演出：画面边缘的纸条、人物走近。你正在和别人说话时，他停在约 4 m 外等，最多 20 秒，超时前端发 `approach_dismiss { reason: "timeout" }`；服务端在你结束对话后可以再派他来一次（仍算这一幕的那 1 次）。
3. 走到 2.5 m 内，前端发 `approach_arrived`。服务端发起一轮（`turn_started { reason: "approach" }`，服务端分配的 `turnSeq`），人物先开口，之后照常对话；候选话语里有「いまは、いい」。
4. 选「いまは、いい」或走开：前端发 `approach_dismiss`，这一幕他不再为同一件事来找你，不花时间。
5. **对话中途人物要离开**（故事走动，S-044 ④）：服务端先发起一轮（`turn_started { reason: "leaving" }`），人物说一句（「……すまない、行かねば。」），然后 `commit` 里把他移走。

### 3.11 幕末和幕切换（S-004、S-031 ③、contracts 2.8.1）

```json
{ "type": "act_ended", "actId": "act.1",
  "recapLines": [ "あなたは、メロスに王のことを告げた。", "あなたは、老爺を家まで送った。" ],
  "options": [
    { "optionId": "exit.1.city", "label": "市に残り、メロスの帰りを待つ",
      "sceneId": "scene.syracuse-square", "tLabel": "三日目・夕方", "where": "刑場・三日目の夕方", "sub": "西の門が見える所で",
      "with": [], "because": null },
    { "optionId": "exit.1.old-man", "label": "老爺の家に身を寄せる",
      "sceneId": "scene.syracuse-square", "tLabel": "三日目・夕方", "where": "刑場・三日目の夕方", "sub": "老爺があなたを覚えている",
      "with": ["char.old-man"], "because": null }
  ],
  "freeform": { "allowed": true, "triesLeft": 2 } }
```
- `options` 来自世界模型的 `ActExit`，按 `roles`、`requires` 过滤（例子是切片的第一幕：送过老爺回家才有第二个去处）。`recapLines` 是「この幕であなたが動かしたこと」（0〜4 行；玩家这一幕什么都没动时为空，前端显示 `actEnd.summary.empty`，v1.0.5）：每行是事件的 `summary`，玩家写成「あなた」（2.4），句末补「。」（v1.0.6）。
- **副题**（v1.0.4，ux-design 4.4）：`where` 是前半「{地点}・{日子}の{时段}」，服务端算好：地点是落点 `ActExit.place` 的 `Place.name`，日子和时段是落点时刻（和 `tLabel` 同一个时刻）在世界模型 `clock.labels` 的 `days`、`bands` 里的叫法，中间用「の」，不套 `clock.labels.format`。`sub` 是后半，世界模型的 `ActExit.sub`（≤ 16 字），没有就省略。前端照 UX 拼成一行，例「刑場・三日目の夕方　西の門が見える所で」，不按去处 ID 写死。`because` 现在一律 `null`：世界模型的 `ActExit` 没有写理由的字段，条件去处的说明写在 `sub` 里（例「老爺があなたを覚えている」）。
- 选给定去处：`act_choose { optionId }`。
- **过场里的二选一**〔契约 1.4，2.8.1 第 2 步，ux-design 4.5〕：去处的跳过的这段路上有一个还能改的节拍时，这个去处多带一个 `enRoute`：
  ```json
  { "optionId": "exit.3.road", "label": "雨の中、メロスと走り出る", "sceneId": "scene.road-river", "tLabel": "三日目・午前",
    "with": ["char.melos"], "because": null,
    "enRoute": { "line": "隣村で、メロスは歩をゆるめた。",
                 "choices": [ { "index": 0, "label": "急かす", "melosMinutes": -40,
                                "afterLine": "メロスは足を速めた。河原には、思ったより早く着いた。" },
                              { "index": 1, "label": "好きにさせる", "melosMinutes": null, "afterLine": null } ] } }
  ```
  - 服务端在推 `act_ended` 时就判好哪些去处带 `enRoute`（世界模型的 `ActExit.enRoute`，它的节拍这一局还没有结果，排定时间落在现在和这个去处的目标时间之间）。幕末到玩家选定之间世界不动，所以这个判断不会过时。`choices` 正好两个，顺序照世界模型，最后一个是「照原作」（『走れメロス』是〔急かす, 好きにさせる〕）。不给效果，也不给节拍 ID。`melosMinutes`：选这一项对梅洛斯到刑场的实际影响，算法和 2.3 的按钮一样（`arrival_delta(本局, 这一项的效果, 收幕时刻)`），按钮写「急かす（40分早まる）」；到了下限是 0；最后一项（照原作）为 `null`。`afterLine`：选了这一项以后、进下一幕之前，过场页多显示的一句（世界模型的 `EnRouteChoice.after`，契约 1.5，ux-design 4.5）；`null` = 不加。下一幕开头的时刻照实际显示。
  - 前端：玩家选了带 `enRoute` 的去处以后，过场页先写 `line`，再给两个按钮；选完连同去处一起发 `act_choose { optionId, enRouteChoice }`。玩家没选就往下走时不带 `enRouteChoice`，等于选了最后一个。
  - 服务端：`enRouteChoice` 不是最后一个时，先写一条玩家的 `action` 事件（`origin: "act"`，`exitId` = 去处 ID，`dt: 0`，效果 = 那一项的效果，照常自检），再按 2.8.1 第 3、4 步算目标时间和幕切换；是最后一个或没带 → 不写事件，照常幕切换。每次过场最多一个二选一。`options[].tLabel` 是不改节拍时的到达时刻；选了改节拍的一项以后，下一幕的起点会跟着变（例：`alignTo: beat.18` 的去处早 40 分钟），以 `act_transition.snapshot.clock` 为准。
  - 这条事件和别的玩家举动一样进 `commit` 和地图时间线；它让节拍变了时（例：催梅洛斯 → `beat.16` prevented → 他早 40 分钟到河边），`act_transition.snapshot.forecast` 已经是变了以后的。
  - 选了替代去处（`act_plan_result.alternative`）或说出打算成行时没有 `enRoute`（契约只给 `ActExit` 定义了它）。
- **说出自己的打算**（ux-design 4.4）：`act_propose { text }`，或用声音（`activity_start { purpose: "act_plan" }` + 音频；这时没有人物在听，服务端只做语音转写，`transcript` 照常推）。叙事者按时间、地点、关系判断，回：
  ```json
  { "type": "act_plan_result", "clientMsgId": "…", "accepted": false,
    "narration": [ "夜の城門は、もう閉ざされている。", "夜明けを待って、門が開くとともに村へ向かうこともできる。" ],
    "alternative": { "optionId": "plan_…", "label": "夜明けを待って村へ向かう", "sceneId": "scene.village", "tLabel": "一日目・朝" },
    "triesLeft": 1 }
  ```
  `accepted: true` 时 `narration` 是「あなたは、〜ことにした。」，紧接着进入幕切换（服务端写一条玩家的 `act-transition` 事件，不带 `exitId`，带 `plan { label, toAct, place, t, with? }`，`label` 是叙事者的转述、不逐字引用玩家原话，契约 1.2 的 2.8.1；不成行不写事件，选了替代去处按成行处理）；`false` 时给最接近的替代去处，玩家可以 `act_choose { optionId: alternative.optionId }`；替代去处是另一个打算时 `optionId` 是 `plan_…`，是某个给定去处时就是那个去处的 ID（v1.0.5）。`triesLeft` 到 0 后 `freeform.allowed = false`，只能选给定去处（同一次幕末最多试 2 次）。用声音说的打算没有 `clientMsgId`，`act_plan_result` 改带那一轮的 `turnId`（3.3）；转写是空的（误按、没出声）不算一次：服务端不判，直接回 `act_plan_result { turnId, accepted: false, narration: ["声が届かなかったようです。もう一度、聞かせてください。"], triesLeft }`，`triesLeft` 不变、不带 `alternative`（v1.0.5；这句是 UX 10-10 定的，v1.0.6）。
- **幕切换**：玩家选定后，服务端按 contracts 2.8.1 结算到下一幕起点之间的节拍、人物的打算、导演事件、约定的兑现，然后推：
  ```json
  { "type": "act_transition", "fromActId": "act.1", "toActId": "act.4",
    "recap": [ { "eventId": "ev_…", "line": "セリヌンティウスは、あなたとの約束どおり、工房の火を落とさずにいた。", "promise": "kept" } ],
    "snapshot": { …2.3… },
    "arrival": { "line": "三日のあいだ、老爺はあなたを家に置いてくれた。いまは二人で、刑場の前に立っている。", "opener": "char.old-man" } }
  ```
  `recap` 是「その頃」，最多 3 件，排序：和你有关的约定兑现或违背 → `keyMoment` 事件 → 你见过的人物自己做的事（ux-design 4.5）；只写玩家在下一幕开始时可以知道的事。`line` 是事件的 `summary`，玩家写成「あなた」（2.4），句末补「。」（v1.0.6）。**不写 `voided` 的约定**：`type: "forget"` 的事件和只为成立一个后来作废的约定的事件都不进「その頃」（ux-design 10.1，核对 U-2）。没有可交代的事时为空数组，前端不显示这一页。超出 3 件的事件在地图里可见。
- **落地**（v1.0.4，契约 1.7 的 `ActExit.arrival`、`Act.plan.arrival`，ux/slice/jump-transition.md「落地」）：`act_transition.arrival` 是进新场景以后的第一行地の文 `line`，和先开口的人物 `opener`（可省）；选的去处（或成行的打算）没写 `arrival` 时省略。玩家落在 `snapshot.player.spot`（2.3）。
  - 前端：「その頃」（和切片的跳转页）之后进新场景，按地の文的样式显示 `line`。
  - 有 `opener` 时，前端在 `line` 出来、玩家能动的时候发 `act_landed { actId }`；服务端收到才发起一轮 `turn_started { reason: "arrival", speaker: <opener> }`（服务端分配的 `turnSeq`，3.1），人物先开口一句（按人设和局势生成，不是问句），之后照常对话，前端不用另发 `focus`（和 3.10 第 3 步一样）。这一句不花故事时间，也不单独交给叙事者，没有 `turn_settled`；玩家接着说的是普通的一轮。`actId` 不是现在这一幕的、同一幕再发的 `act_landed`，服务端忽略。
  - 收到 `act_landed` 之前断线：`welcome.pending.arrival` 带着这一幕的 `arrival`（第 4 节），前端重连后照样落地、发 `act_landed`。
  ```
  → act_choose {optionId: "exit.1.old-man"}
  ← commit {…}                    （选定的事件，跳过的这段时间里结算的节拍）
  ← act_transition {…, arrival: {line: "三日のあいだ、…", opener: "char.old-man"}}
     （前端：「その頃」→ 跳转页 → 进刑场，显示 arrival.line）
  → act_landed {actId: "act.4"}
  ← turn_started {turnId: "turn_…", turnSeq: 2147483650, speaker: "char.old-man", reason: "arrival"}
  ← [0x02 | 2147483650 | PCM] … transcript … turn_complete … transcript {final: true, source: "live"}
  ← suggestions {character: "char.old-man", …}
  ```

### 3.12 出戏卡（自伤、求助信号，S-043）

- 服务端对玩家的每一句话（语音的定稿字幕、文字）做安全筛查（backend-design 5.5）。判为明确的信号时：停止转发人物的回答，这一轮不交给叙事者、不花时间、原话立即清空，推 `turn_settled { outcome: "paused" }` 和 `safety_pause`。
- 卡片的文案和相谈窗口由 UX 定（ux-design 第 14 节），不从服务端下发。
- 推 `safety_pause` 时如果玩家正按着说话键（已发 `activity_start`），服务端把这一轮直接丢掉：之后这个 `turnId` 的音频帧和 `activity_end` 都忽略，不转写、不存、不交给叙事者。前端停发麦克风帧、丢掉本地录音，什么都不用补发（不发 `turn_retract`）；恢复后用新的 `turnId`。
- 暂停期间故事时间不动，人物的会话关闭；玩家选「物語に戻る」时前端发 `safety_resume`，服务端回 `safety_resumed`，前端重新 `focus`。
- 似是而非的句子（「ここで終わりにしたい」这类，故事里也说得通）不暂停（S-069）：
  - 一局里第一次：推 `safety_hint`（无字段）。前端在画面边上显示一条安静的小提示，入口和出戏卡同一个相谈窗口；文字和位置由 UX 定，不从服务端下发。人物照常说话，故事时间照常走。服务端这一轮在局势说明里不往死亡、绝望推，这一句不提取事件。
  - 同一局第二次似是而非：按明确的信号处理，走上面的 `safety_pause`。
  - `safety_hint` 一局最多推一次（断线重连后也不重推）。判定结果和原话都不写记忆、不存（S-057），`playthrough_metrics` 里只记次数。
- 筛查的提示和模型按 S-4 的结果在调（`spikes/results-s1.md` 第 7 节）。

### 3.13 结局

```json
{ "type": "ending_started", "trigger": "deadline",
  "staging": { "place": "place.execution-ground",
               "characters": [ { "id": "char.selinuntius", "state": "on-cross" }, { "id": "char.melos", "state": "arriving" },
                               { "id": "char.king", "state": "present" }, { "id": "player", "state": "in-crowd" } ] } }
```
- `trigger`：`deadline`（三日目の日没）、`story-closed`（最后一幕的收幕节拍有了结果）。
- `staging`：结局演出里谁在哪、什么状态，按这一局的世界状态给。セリヌンティウス默认在场（S-053）；这一局的事件让他不可能在场时不放进来，叙事交代他在哪。**玩家也在 `characters` 里**，`id: "player"`（「あなたが身代わりになった」那类结局里，柱上的是玩家）。`state` 按 ux-design 11.1 的 8 个：`present`、`in-crowd`、`on-cross`、`freed`、`arriving`、`approaching`、`collapsed`、`absent`，只表示人在哪、身体什么样子；前端遇到不认识的值按 `present` 演。不演处刑本身。
- 演出同时盖住结局生成的等待；生成好推 `ending_ready`，前端用 2.8 取。超过 20 秒还没好，前端按 UX 提示可以先看地图。

### 3.14 固定演出（`set_piece`，v1.0.4，契约 1.7 的 2.11）

世界模型里写好的、每局都一样的地の文和人物的话（切片：城门的警吏、工房关着的门）。演不演、演哪一条由服务端按契约 2.11 定（共享规则库的 `pick_set_piece`，演过哪些服务端按局记），前端不按 ID 写死，也不判断条件。

```json
{ "type": "set_piece", "pieceId": "piece.gate-taken",
  "lines": [ { "narration": "警吏が、あなたの前に槍を下ろした。" },
             { "speaker": "char.guards", "line": "下がれ、旅の者。ここから先は、通さぬ。" },
             { "narration": "メロスは、王城の奥へ引かれていった。" } ] }
```
- `lines` 就是世界模型的 `SetPiece.lines`，按顺序演：`narration` 是一行地の文（和 `narration` 消息同样式）；`speaker` + `line` 是这个人物的一句预录，播 manifest 的 `setPieceVoices["<pieceId>/<序号>"]`（序号是这一句在 `lines` 里的位置，从 1 起；例子里警吏那句是 `piece.gate-taken/2`，2.1），字幕是 `line`（剧本原文，和 `source: "script"` 一样）。manifest 里没有这一句的录音时只出字幕。前一句播完再出下一句；人物正在出声时等他这一句说完再演（同 3.4 的 `cue`）。
- **时机**：
  - 挂在玩家的动作上（`on.act`）：`commit`（这个动作写了事件时）→ `action_result { setPiece }` → `set_piece`。固定演出代替叙事者对这个动作的叙事，所以这时 `action_result` 不带 `narration`（3.3）。被拒的动作也可能挂（例：立约以后去王城，警吏赶人时说出约定）。
  - 挂在节拍上（`on.beat`，节拍发生时玩家在节拍的地点）：紧跟在节拍那次提交的 `commit` 之后。那次提交属于玩家的一轮或一个动作时，`set_piece` 在这一轮的 `turn_settled`（或 `action_result`）之前。
- **玩家从演出里知道的事**（`SetPiece.learns`，S-077 ⑪）：和演出同一次提交，在它前面那条 `commit` 里。城门的警吏说出约定时，`patch.deadline`、`patch.forecast` 就在那条 `commit` 里（2.3）；前端可以把它压到演完再应用（3.8 末尾）。
- `set_piece` 不是事件，不占 `seq`，不进地图和「その頃」；断线时没收到的不补发（`learns` 已经在 `commit` 里，世界状态不受影响）。

---

## 4. 断线、重连、续玩（S-024）

- 断开后，前端按 1、2、4、8 秒退避重连；重连后发 `hello { lastSeq }`，服务端补发漏掉的 `commit`（也可以用 2.4 拉取）。
- 收到 `goaway` 时，前端在 `reconnectAfterMs` 之后主动重连（部署时服务端约 10 秒内必须关闭连接）。
- **`welcome` 带回续玩需要的状态**（前端第 8 条）：
  ```json
  { "type": "welcome", "lastSeq": 45,
    "voice": { "enabled": true, "degraded": false, "minutesLeftToday": 40 },
    "lastTurn": { "turnId": "turn_…", "character": "char.melos", "status": "settled",
                  "playerText": "王城に行くのか？", "characterText": "ああ、今すぐにだ。" },
    "pending": { "reveal": null, "confirm": null, "actEnd": null, "safetyPause": false, "approach": null } }
  ```
  - `lastTurn.status`：`settled` / `pending`（叙事者还在判）/ `lost`（断线时人物还没说完）。`lost` 的轮不交给叙事者、不花时间，也不会有 `turn_settled`；人物已经说完（`turn_complete` 到了）才断线的轮照常交，是 `pending` 或 `settled`。`lost` 时人物在画面上就播他的预录「听不清」第 1 句，不在画面上就叙事一行「もう一度、話しかけてください。」（ux-design 第 12 节）。原话已清空的轮次（作废、删除）不给文字（作废的一轮 `status: "settled"`，`playerText`、`characterText` 都是 `null`，v1.0.7）；人物的文字没收到的轮次（backend-design 3.1 的 `characterTextMissing`）`characterText` 为 null。幕末用声音说打算的那一轮没有人物在听，`character` 为 `null`。
  - `pending`：断线前还没处理完的确认（`confirm` 的字段加剩余秒数 `remainingSec`，`timeoutSec` 照给）、幕末选择（`actEnd` 和 `act_ended` 同形，含 `enRoute`、`where`、`sub`）、关键时刻、出戏卡、走过来的人物，前端恢复对应画面。（v1.0.4）`arrival`：幕切换以后、`arrival` 带 `opener` 而服务端还没收到 `act_landed` 时给，和 `act_transition.arrival` 同形，前端落地后发 `act_landed`（3.11）；没有时省略。
- 关闭码：`4001` 未登录、`4003` 无权访问这一局、`4004` 这一局已被删除、`4009` 同一局在别的标签页打开（新连接踢掉旧连接）、`4290` 限流、`1012` 服务重启（立即重连）。
- 语音会话的连续性由服务端负责：用局势说明和网关内存里的最近对话重建会话（不开 Live 的会话恢复，backend-design 5.4）；前端重连后重新 `focus`。

---

## 5. 错误

```json
{ "error": { "code": "daily_limit", "message": "今日はここまでです", "retryable": false, "retryAfterSeconds": null } }
```

| code | HTTP | 说明 |
|---|---|---|
| `invalid_request` | 400 | 请求体、参数或 WebSocket 消息不合 Schema。是前端的毛病，`message` 不给玩家具体原因。WebSocket 上另有四种情况也回它（不断开）：`hello` 之前发了 `hello`、`ping` 以外的消息；没有 `focus` 的人物时发 `text` 或 `activity_start`（`purpose: "act_plan"` 除外，那时本来没有人物在听，3.11）；`focus` 了不在当前场景或此刻 `talkable: false` 的人物（之前的 `focus` 不变）；收幕以后、选定去处之前发 `text`、`activity_start`（`act_plan` 除外）或 `action`（3.11，v1.0.5）。这时那一轮不会有 `turn_settled`，`error` 也不带 `turnId`：前端把刚发出的那一轮当作没送到 |
| `unauthenticated` | 401 | 没有或过期的会话 |
| `invalid_invite` | 401 | 登录时邀请码不对（第 1 节） |
| `forbidden` | 403 | 不是你的局；或跨站请求（`Origin`、`Content-Type` 不对） |
| `not_found` | 404 | — |
| `active_playthrough_exists` | 409 | 已经有进行中的局，带 `activePlaythrough`（放在 `error` 外面，和它并列） |
| `idempotency_conflict` | 422 | 同一个 `Idempotency-Key` 用在了不同的请求内容上 |
| `rate_limited` / `daily_limit` | 429 | 带 `retryAfterSeconds` |
| `voice_unavailable` | 503 | 语音服务不可用，前端改文字（同时会收到 `degraded`） |
| `invalid_choice` | —（只在 WebSocket） | `act_choose` 的 `optionId` 不在这次 `act_ended` 里、也不是这次的替代去处，或 `enRouteChoice` 超出范围、给了不带 `enRoute` 的去处。幕末画面不变，前端按 `pending.actEnd` 重新显示 |
| `internal` | 500 | `retryable: true` |

`message` 是可以直接给玩家看的日语短句；前端也可以按 `code` 用自己的文案（UX 第 12 节）。

---

## 6. 性能约定

| 项 | 后端 | 前端 |
|---|---|---|
| 松手到出声（S-017） | 服务端：收到 `activity_end` → 发出第一个音频分片，中位 ≤ 1.2 s、p95 ≤ 1.6 s，在 `turn_complete.metrics` 回报。S-1b 4G 实测服务端中位 0.92 s（`spikes/backend/results-s1.md` 8.5）；M2 带完整人设后复核（S-073 ①） | 前端两段合计 ≤ 170 ms（S-014）；300 ms 内出等待演出；上报 `clientReleaseToAudibleMs`（带 `turnId`） |
| 打断（S-014） | 收到 `activity_start` 后不再转发旧轮次分片，同时让 Live 停止生成 | 本地停播 ≤ 0.2 s |
| 切换人物、重建会话 | 预热命中时 `session_ready` 立即返回；未命中、重建 ≤ 1 s〔S-1 的 `session_setup_ms`〕 | `session_preparing` 期间演出；点人物时就发 `focus` |
| 世界反应 | `turn_complete` 后 3〜5 s 内 `turn_settled`（叙事者判定） | 轻反馈只在 `commit` 后出现 |
| 候选话语 | `turn_complete` 后约 1 s | — |
| REST | 快照 ≤ 10 KB；事件每页 ≤ 50 条 | — |
| 静态资源 | 文件名带 hash 的资源 `public, max-age=31536000, immutable`、预压缩 br；`index.html` `no-cache`；`/v1/*` 不经 CDN 缓存（前端建议第 17 条） | — |

---

## 7. 测试支持

- **本地 mock 服务**：`uv run zoujin-mock` 一条命令启动（也提供 `docker compose up`）；同样的 REST 和 WebSocket 消息，回放录制好的会话并保留真实的时间间隔，覆盖：一整轮对话、闲聊轮、打断、作废和识别改正、意图确认、人物走过来、幕末自由说、`goaway`、`4009`、出戏卡、结局，（v1.0.4）幕切换的落地和固定演出。前端可以离线开发和做契约测试（前端建议第 12 条）。
- **JSON Schema**：3.2、3.3 的每种消息和第 2 节的每个响应都有 Schema，放在代码仓库 `packages/contracts/schemas/api/`，前端直接生成 TypeScript 类型；CI 用它校验 mock 和真实服务。
- **非生产环境**：`POST /v1/test/playthroughs/{id}/advance`（快进故事时间：请求 `{ "minutes": 60 }`，响应是快进后的快照）；`fakeVoice` 模式（`hello { debug: true, fakeVoice: true }`：服务端用录好的音频回答，不调用 Live），联调和前端 CI 的端到端测试不花钱；`event_rejected` 调试消息。生产环境没有这些。
- **评测入口** `zoujin_backend.eval_api`（给数据工程的评测运行器；Python 包内调用，不开 HTTP，生产环境没有）。用例格式以 `evals/README.md` 为准，这里只列后端提供什么。Python 的写法：`setup(setup, *, mode)`（`setup` 是用例的 `setup` 原样，`mode` 是用例的 `text` / `voice`；`ZJ_MODEL` 在每次 `setup()` 时读，不在 import 时读）；方法名用蛇形；步骤号从 1 起，按调用顺序数，`delete_memory` 的 `from_step`、`retract` 的 `step`、`utterance_cleared` 的 `step` 都按它。没实现的步骤或查询抛 `EvalNotImplemented("<名字>")`，回放里找不到这次调用抛 `ReplayMissing`，两个都在 `zoujin_backend.eval_api` 里，运行器按类名认、记跳过。
  - `setup`：`role`、`place`、`budgetTier`（`normal` / `saving`，数据评审第 14 条）；起点三选一：`checkpoint`（`"<情景 ID>@<节拍 ID>"` = 推演到该节拍刚发生之后；`"<情景 ID>@t=<分钟>"` = 推演到该时刻，含那一刻的期限规则）、`scenario`（只推演，不调用模型）、`persona` + `seed`（模拟局：后端按画像定身份和起点，按 `seed` 定假模型的种子）。`events`：起点之后追加的事件（可带 `memory` 种一条记忆），直接写入、不经叙事者，trace 里标成评测布置；只给了 `effects`（和 `note`）的，写入时补成完整的事件：`actor: "system"`、`type: "action"`、`t` = 起点时刻、`dt: 0`、`place` = 玩家所在地、`summary` = `note`、`check.status: "passed"`、`check.checker: "eval-setup"`。`sc.canon` 指原著路径（不在 `scenarios.json` 里）。
  - 步骤，每种一个调用：`say(to, text, hold=False)`（文字代替语音，之后走和语音同一条叙事者流程；v1.0.7 `hold=True`：先不提交，返回 `held: true`、没有事件，下一次调用开始时提交，事件算在那一次里）、`act(kind, target, params)`（`kind` 按 3.8 的清单，`move` = 同场景跨地点）、`delete_memory(character, from_step)`、`retract(step)`（v1.0.7：第 `step` 步还 hold 着就作废，返回 `retract: "retracted"`、`events: []`、`clockMinutes: 0`；已经提交的 `retract: "too_late"`）、`confirm(answer)`（v1.0.7：回答上一步留下的意图确认，`answer` 是 `"yes"` / `"no"` / `None`（没答）；返回 `events`、`clockMinutes`、`result`（`committed` / `rejected` / `discarded`），重查没过时带 `narration`；没有草稿在等时 `error: "no_draft"`）、`delete_playthrough()`、`new_playthrough()`（同一账号、同一起点）、`advance(minutes)`、`silence(seconds)`、`propose(text)`（幕末说出打算）、`choose(exit, en_route=None)`（幕末选给定去处，和 `act_choose` 同一条流程；`en_route` 是过场二选一的序号，不写 = 最后一个，契约 1.5）、`check(candidate, turn, model_checks="scoped")`（S-2 用：把一个候选事件直接交给叙事者第 3、4 步，**不提交**；`turn` 是这一轮的原话、人物的回答或动作，给模型检查当上下文；`model_checks`：`scoped` = 按正式范围，backend-design 2.4，默认；`all` = 每条都跑第 4 步；返回 `{ "check": 契约的 CheckResult, "rules": [ { "rule", "status": "pass" | "fail" | "skipped", "reason"? } ] }`，`rule` 用契约 `failedRules` 里的名字）。`new_playthrough()` 之后会话指向新的一局，查询都答新的那局；`delete_playthrough()` 之后的 `db_absent` 答被删的那局。
  - **模拟局**：AI 玩家在数据的运行器里，按画像一步一步调 `say` / `act` / `propose` / `choose`，幕末和真玩家一样选去处或说打算。AI 玩家用哪个模型不进后端包；玩家说过的话由运行器自己记，后端不另给。
  - 每一步返回（字段都可省，用到省了的字段的检查记跳过）：人物回答的文字（没开口为 `None`）和 `characterTextMissing`；`events`：这一步写进事件日志的**全部事件**，按 `seq` 排，都带 `eventId`，包括这一步的候选事件（提交的和被否决的）和这一步里到点结算的系统事件（`origin: "schedule"`，`world_unchanged` 按 `origin` 排除它们）；被否决的那条给候选原本的 `effects` 加上 `check`（`status: "rejected"`、`failedRules`），和日志里那条（`effects` 为空，契约第 3 节）不同；时钟前进了几分钟；危机卡片有没有出、故事有没有暂停、能不能回去；幕末打算的结果（成行时的 `plan`，不成行时的替代去处）；`silence` 之后人物追问了几次；`traceId`；（v1.0.7）`say(hold=True)` 的 `held`；这一步留下了意图确认的草稿时 `confirm: { draftId, character, prompt }`（草稿那条不在 `events` 里，下一步是 `confirm` 就按它答，是 `say` 就由叙事者判是不是在回答，别的步骤或不是在回答按超时关掉）。
  - 随时可查：`state()`（变量、节拍结果和时间、`schedule`、`promises`、`runFacts`）、`events()`（这一局的全部事件，含评测布置和被否决的，按 `seq`）、`memories(character)`（含已删除的标记）、`trust(character)`、`utterance_cleared(step)`、`db_absent(tables)`（删除整局后查 data-design 5.2、5.3 删除清单里的表，含后端的 `turns`、`briefs`；返回 `{表名: 这一局还剩几行}`）、`ending()`（契约第 5 节的完整形状，含 `signature`）。
  - `world_unchanged` 的范围按数据的定义：只看本用例的轮次引起、`effects` 非空、已提交的事件；`system` 按时间表结算的节拍不算，除非结果和原情景不同。

---

## 8. 已定和还开着的

| # | 结论 |
|---|---|
| Q-F1〜F6 | 不变：AudioWorklet 采集重采样到 16 kHz；二进制帧带 turnSeq；快照按前端清单；一对一 `focus`；同源；播放用环形缓冲、起播前攒 60〜100 ms |
| 前端 1〜17 | 全部写进本版，见第 9 节 |
| UX 18.2 | 全部写进本版或 backend-design v1.0，见第 9 节 |
| 契约 1.1 / 1.2 | 后端提的 13 条都已进契约（数据 v1.2）。和后端草案不同的 4 处按数据的写法：导演事件用 `origin: "director"`、`actor` 照常（2.6）；生成的结局在 `world.variant`（2.8 的对应）；尾声存在 `player.epilogue`（2.8）；删约定类记忆追加 `forget` 事件（2.7） |
| Q-B11 结局卡插画 | 前端确认 3D 定格可行，后端不生成插画；预画 5 张兜底（2.8） |
| `staging` 的状态 | 按 ux-design 11.1 的 8 个，玩家也在里面（3.13） |
| 契约 1.6 的结局卡 | 每一局都有 `card`，人物行 1〜3 条，模板尾声的局也有（2.8，S-076） |
| 契约 1.7 要接口给前端的（v1.0.4） | 幕末副题的前半 `where`、后半 `sub`，`because` 一律 `null`（3.11）；落地 `act_transition.arrival`、`act_landed`、`turn_started.reason: "arrival"`、`pending.arrival`（3.11、第 4 节）；固定演出 `set_piece`、`action_result.setPiece`、manifest 的 `setPieceVoices`（3.14、2.1）；`Affordance.playerSpot` 走 `commit.patch.player`（3.8）；可调查物来自 `objects`，`group` 的人物没有 `spot`，`player.spot` 的来源（2.3） |
| 契约 1.4 的界面字段 | 数据请后端定的三处：第四幕按钮的 `melosMinutes` 和 `melosInTime`（2.3，按 S-066 用 `arrival_delta` 算本局实际值）、幕末去处的 `enRoute`（3.11）、`act_choose.enRouteChoice`（3.11） |

还开着的：

| 问题 | 等谁 |
|---|---|
| 群像插话 `npc_line { character, text, audioUrl }`（P1） | 留到 P1，不在 v1.0；到时按第 0 节只做加法 |

---

## 9. 评审意见的处理

**前端**（`frontend/reviews/backend-v0.1.md` 1〜17，frontend-design 第 14 节 1〜17）

| # | 意见 | 处理 |
|---|---|---|
| 评审 1 / 14-1 | 页面重载后 turnSeq 怎么接 | turnSeq 只在一条连接内有效（3.1） |
| 评审 2 / 14-2 | `anchor` 改名 | `spot`（0、2.3） |
| 评审 3 / 14-3 | sceneId | 用世界模型的 `scene.*`（2.1、2.3） |
| 评审 4 / 14-4 | 一次提交原子地应用 | 合成一条 `commit`，带 `fromSeq`〜`seq`（3.4） |
| 评审 5 / 14-5 | 闲聊轮的结束信号 | `turn_settled`，事件带 `turnId`（3.4） |
| 评审 6 / 14-6 | 场景内走路不等叙事者 | 3.8；快照 `places[].enabled` |
| 评审 7 | `near` / `far` 滞回 | 8 m / 12 m，只发最近一个；服务端 2 秒去抖（3.2） |
| 评审 8 | `chain_reveal` 带链 | `commit.reveal.chain`（3.4） |
| 评审 9 | REST 跨站防护 | JSON 内容类型 + `Origin`（0） |
| 评审 10 | 登录和会话有效期 | `/v1/me`；30 天滑动（0、1） |
| 评审 11 | 群像插话 | `npc_line`，P1（8） |
| 评审 12 | mock 和 JSON Schema | 第 7 节 |
| 评审 13 | 延迟分段对齐 | 按 `turnId` 对齐（2.11、6） |
| 评审 14 | App 内浏览器不带 Cookie | 先用同源 Cookie，票据接口预留；S-1b 实测 |
| 评审 15 | 字幕说明 | 同意，不改接口 |
| 评审 16 | backend-design 里的旧名字 | backend-design v1.0 已改 |
| 评审 17 | 静态资源缓存 | 第 6 节 |
| 14-7 | `/v1/me` 带进行中的局 | `activePlaythrough`（1） |
| 14-8 | `welcome.lastTurn` | 第 4 节 |
| 14-9 | 玩家字幕实时推 | `transcript final:false`（3.3）；S-1 量能多早 |
| 14-10 | 识别改正 | `turn_retract` + `text { via: "correction", replaces }`，会话重建（3.6） |
| 14-11 | 结局加「和原作的不同」 | `world.contrast`、`card.contrast`（2.8） |
| 14-12 | 人物走过来的消息、turnSeq 不撞号 | `approach` / `approach_arrived` / `turn_started`；服务端 turnSeq 最高位为 1（3.1、3.10） |
| 14-13 | 走动中的人物被点了算在哪 | 算玩家所在的地点（3.8） |
| 14-14 | 幕末说出打算 | `act_propose`、`act_plan_result`（3.11） |
| 14-15 | 这一轮没有声音 | `turn_complete.audio: false`（3.3） |
| 14-16 | manifest 带预录音频和注音词表 | `prerecorded`、`ruby`（2.1） |
| 14-17 | `confirm`；作废统一用 `turn_retract` | 3.9、3.6 |

**数据工程**（`data/reviews/backend-v0.1.md`，接口相关的条目；其余在 backend-design v1.0 第 13 节）

| # | 意见 | 处理 |
|---|---|---|
| 1 | ID 和名字用世界模型的；manifest 从世界模型生成 | 2.1、2.3 的例子和生成规则 |
| 2 | `tLabel` 例子错了 | 改成约束之日起算，由同一个函数生成（0）；格式按 ux 4.2，世界模型已改成「{day}・{band}」（契约 1.1） |
| 3 | `visibleEffects` 的规则 | 按 contracts 2.6（0、2.4） |
| 5 | 作废的那一轮原话立即清空 | 3.6 第 2 条 |
| 6 | `actor` 的含义；链上一步是事件不是记忆 | 2.4、2.6 |
| 7 | 被否决的事件给不给玩家看 | 不给（0、2.6） |
| 8 | `spot` | 0 |
| 9 | 每一轮都要有结束信号 | `turn_settled`（3.4） |
| 11 | `activity` 从哪来 | 节拍上的提示 + 叙事者推出（2.3，backend-design 2.7） |
| 12 | 「顔見知り」不在表里 | 例子改用表里的文字；关系另给 `relationLevel`（2.3） |
| 14 | 评测入口的 `budgetTier` | 第 7 节；评测入口按 `data/evals/README.md` 补全（v0.3.2） |

**UX**（ux-design 18.2）

| 要什么 | 处理 |
|---|---|
| `turn_retract` 统一作废一轮；识别改正 = 窗口内 `turn_retract` + `text` | 3.6 |
| `confirm` / `confirm_answer` | 3.9 |
| `keyMoment` 按 S-041 的 4 条 | 3.4.1 |
| 人物走过来找你的调度规则（S-044） | 3.10 |
| 导演事件的规则（S-045） | backend-design 2.6 |
| 结局不逐字引用原话（S-046） | 2.8；backend-design 2.9 |
| 「学習には使いません」 | S-6 已核对服务条款，可以写（backend-design 5.4） |
| 幕末自由说的结果 | `act_plan_result`（3.11） |
| 每个人物预生成 6 句台词 | `manifest.characters[].prerecorded`（2.1）；backend-design 3.6 |
| 对话中约 20 秒没动作，人物用动作收尾 | `unfocus { reason: "silence" }`（3.2）；人设提示里写不追问（backend-design 2.3） |
| 转写的专有名词偏置；小声说话 | backend-design 3.2；S-1 量偏置的效果，小声在 S-1b 和前端 S2 一起测 |
| 人物说话方式的约束写进人设提示 | backend-design 2.3 |
| 动作清单 `action.kind`，带 `estimatedMinutes` | 3.8、2.3 |
| 删除记忆前的「不会撤销的后果」；删约定类记忆的语义 | `GET …/impact`、`voidsPromise`、约定 `voided`（2.7） |
| 自伤信号的检测标记 | 3.12 |
| 画面上不出现「刻」 | 接口里不再有 `koku`（0） |
| 「その頃」的范围和排序 | `act_transition.recap`（3.11） |
| 記憶帳按人物分好约定、做了的事 | 2.7 |

---

## 修订记录

- v1.0.13（2026-10-11）：只做加法，前端 3 做地图（F-12 之后）时提的。2.1：manifest 加必有的 `places`（地点 ID、地名、所在场景；场景没出的为 `null`），生成器照世界模型出。2.5：时间线的节拍项加可选的 `cite`（世界模型 `Beat.cite` 原样，数据契约的 `Cite`），只在 `known: true` 时给，`known: false` 的 Schema 不许带。2.6：「なぜ」链的节拍那一步也加可选的 `cite`。mock 的时间线、「なぜ」带上切片世界模型的出处；`examples/` 里的合法例子跟着加。v1.0.10〜v1.0.12 在别的 PR 里（B-9、B-5 #117、重连补发 #120），号先留着。
- v1.0.9（2026-10-11）：传输形状和 Schema 都不变，按 B-7 卡（#93）改 2.1、补 2.2 一句，和 B-7 的代码同一个 PR：manifest 的地址不带版本，`ETag` 是 `manifestVersion`、`Cache-Control: private, no-cache`、`If-None-Match` 对上回 304（原来写的「URL 带版本、`immutable`」作废）；`manifestVersion` 的形状；只出真能加载的东西（开放版次以内、开局场景有包的身份，有包的场景，`acts[].sceneIds` 跟着，没有场景的幕不出）；`assetUrl` = `/scenes/<assetVersion>/<目录>/<入口文件>`，`assetVersion` 是入口能走到的目录里全部文件的 hash；`characters` 是世界模型的全部人物；`arrival_capped` 只在说这句的人物身上；预录句逐句核对；录音文件的地址和响应头；开局只收 manifest 里的身份；到了没有包的场景前端只出字幕和旁白。3.2、3.6：会话没就绪时前端缓存按住的整段音频（最多 15 秒，原来 2 秒，前端和 UX 在 #109 提的），`session_ready` 后一次发出，服务端按顺序转。2.2：次数用完先回 429 `daily_limit`，再看 409。例子跟着改；`packages/contracts/examples/` 里的合法例子不动。mock 的 manifest 从 fixture 改成同一个生成器（`fixtures/mock/rest/manifest/` 删掉），按切片的世界模型。
- v1.0.8（2026-10-11）：传输形状和 Schema 都不变，2.1 加一条录音文件的说明（B-6）：格式是 AAC（`.m4a`）、单声道、24 kHz；几个 `setPieceVoices` 键可以指向同一个 `url`；一个人物的 6 句缺一句时这个人物没有 `prerecorded`。
- v1.0.7（2026-10-11）：传输形状和 Schema 都不变，按 B-4 卡（#65）把作废、意图确认的顺序和评测入口写进正文，前端同意以后和 B-4 的代码同一个 PR 改：幕末用声音说的打算也能作废，作废了不推 `act_plan_result`、`turn_settled`，不算试次；文字的一轮也有提交窗口；服务端发起的一轮回 `too_late`（3.6）；意图确认的推送顺序、反问那一轮没有 `turn_settled`、一局最多 3 次、同一时间一个草稿、用声音回答的一轮照常 10 分钟、收幕时不留草稿（3.9）；作废的一轮在 `lastTurn` 里是 `settled`、文字为 `null`（4）；评测入口的 `say(hold)`、`retract(step)`、`confirm(answer)` 和 `StepResult` 的 `held`、`confirm`（7）。mock 的 `confirm` 剧本照新的顺序改，两次确认的选项都用 3.9 的固定两项。
- v1.0.6（2026-10-10）：传输形状和 Schema 都不变，只改下发的文字（UX 10-10 定的，后端同意）：事件的 `summary`（2.4、2.5、2.6、`commit`）、`recapLines` 和「その頃」的 `line` 里，玩家写成「あなた」，不再用身份名；`recapLines` 和「その頃」句末补「。」，`summary` 不补。库里存的事件照旧用身份名。用声音说的打算转写为空时那句叙事改为「声が届かなかったようです。もう一度、聞かせてください。」（3.11）。2.4、2.5、2.6 的例子和 `packages/contracts/examples/` 里对应的合法例子跟着改，mock（`fixtures/sessions/`、`fixtures/mock/rest/`）也改了。跟契约 1.8（#70）：2.4、3.4 例子里 `visibleEffects` 的 `label` 改成「王はあなたを覚えた」（世界模型里写玩家的标签本来就用「あなた」）；mock 里送老爺回家那条事件句照 `pastLabel` 写成「あなたは、老爺を家まで送った」。
- v1.0.5（2026-10-10）：按 B-3 卡（#58）放宽 Schema 三处、补一条说明，前端同意以后和 B-3 的代码同一个 PR 改：`recapLines` 允许 0〜4 条（`ActEndedMessage` 和 `ActEnd` 两处；这一幕什么都没动时为空，前端显示 `actEnd.summary.empty`）；`act_plan_result.alternative.optionId` 也可以是给定去处的 ID（`PlanAlternative.optionId` 改成 `PlanOptionId` 或 `ExitId`，例：E4-106 期望的替代去处就是给定去处）；第 5 节 `invalid_request` 加一条：收幕以后、选定之前发 `text`、`activity_start`（`act_plan` 除外）、`action`；用声音说的打算转写为空时不算试次（3.11，前端评审 #61）；`commit.patch.characters[]` 加 `group`（`CharacterPresencePatch` 原来漏了它：群众、警吏进场的那次 `commit` 带完整的 `CharacterPresence`，含 `group: true`，生成的类型不收，B-3 的 WebSocket 测试查出来的）。
- v1.0.4（2026-10-10）：只做加法，把数据契约 1.7（#34）里前端要拿到的几样加进接口（F-2b 的 #37 评审和 ux-design v1.0.1 4.4 提的）：幕末去处的副题 `where`（服务端按 `Place.name` 和 `clock.labels` 拼好的前半）和 `sub`（`ActExit.sub`），`because` 写明一律 `null`（3.11）；落地：`act_transition.arrival { line, opener? }`、新的客户端消息 `act_landed`、`turn_started.reason` 加 `arrival`、`pending.arrival`（3.11、第 4 节）；固定演出：新的服务端消息 `set_piece`，`action_result` 加 `setPiece`、这时不带 `narration`（两个正好给一个），manifest 加 `setPieceVoices`（3.14、2.1）；`Affordance.playerSpot` 走 `commit.patch.player { spot }`（3.8）；快照里 `group` 的人物没有 `spot`、写明 `player.spot` 和 `examine` 的来源（2.3）。Schema 跟着改：`ActOption.where` 必有；`action_result.narration` 从必有改成和 `setPiece` 二选一；`CharacterPresence.spot` 从必有改成 `group` 的人物没有。mock 的 `act-end` 剧本按这些改，加 `set-piece` 剧本。服务端在 B-3 做。
- v1.0.3（2026-10-10）：传输形状不变，Schema 只改 `description`。把 B-0（#26）、F-2b（#32）评审和 S-077 ⑫ 定下的写进正文：期限一行和预报在玩家知道约定（契约 1.7 `knows(player, fact.promise)`）以后才出，不再跟着 beat.05 的提交出；玩家不知道约定时不出 `eta`（2.3、3.4.1）；人物一个字没说就被打断的轮没有人物定稿，被打断的轮没有 `turn_complete`、照常交给叙事者，人物说完以后按下说话不算打断（3.3）；地点关上时玩家在里面，那次 `commit` 带 `patch.player` 把人放到外面，`move` 进关着的地点回 `refused`（3.8）；`lost` 的轮不判、没有 `turn_settled`（4）；WebSocket 上 `invalid_request` 的三种情况（5）。服务端：打断、`lost`、`invalid_request` 在 B-0 做了；关地点、期限一行的条件在 B-3 做。
- v1.0.2（2026-10-10）：只补正文，传输形状和 Schema 都不变。把 B-1（mock）评审时前端要求写明、mock 已经照做的写进来：降级为文字回答时人物定稿在 `turn_complete { audio: false }` 之前；没有人物定稿的两种轮（没出声、出戏卡停下），被打断的轮照样有定稿（3.3）；动作的 `commit` 在 `action_result` 之前（3.8）；结局还没开始时 `GET …/ending` 回 404（2.8）。
- v1.0.1（2026-10-10）：只补正文，传输形状和 C-1 的 Schema 一样，只有一处收紧：`GET …/ending` 的 `card` 改成必有（S-076，契约 1.6 第 5 节；C-1 的 Schema 还写着模板尾声的局没有卡）。把 C-1 评审定下的写进正文：`plan_` 前缀（0）；`inviteCode` 的格式（1）；409 的 `activePlaythrough` 在 `error` 外面（2.2、5）；`interactables` 含场景出口，增减走 `commit.patch.interactables`（2.3、3.4、3.8）；快照动作没有对象时省略 `target`（2.3）；事件的 `turnId` 可省、`visibleEffects` 的两种形状（2.4）；遥测回 204、公共属性每批一次（2.11）；`action.target` 只在 `move` / `examine` / `go` 时必带（3.2）；`turn_complete` 没出声时 `serverReleaseToFirstAudioMs` 为 `null`、`narration.ref` 只给日志、`act_plan_result` 带 `clientMsgId` 或 `turnId`、`event_rejected.candidate` 的形状（3.3、3.11）；`patch` 的合并规则、`clock` 的必带字段、`memories` 的必带字段、`reveal.collapsed`（3.4）；`lastTurn.character` 可为 `null`、`pending.confirm` 带 `remainingSec`（4）；错误码 `invalid_request`、`invalid_invite`（5）；快进接口的请求和响应（7）。2.8 跟契约 1.6：结局卡人物 1〜3 行，模板尾声的局也出卡；例子改成 `in-time-king-unchanged`（标题用这一类的 `label`，梅洛斯排第 2）。第 7 节按和数据对好的评测入口改：Python 的写法和两个异常；`check` 的返回形状；每一步的 `events` 包括到点结算的系统事件，被否决的给原本的 `effects`；`new_playthrough()` 之后查询答新局；模拟局的 AI 玩家放在数据的运行器里，逐步调用，后端不提供玩家原话。
- v1.0（2026-10-10）：冻结（C-1）。每种消息和响应写成 JSON Schema（`packages/contracts/schemas/api/`），生成前后端类型；第 6 节松手到出声定为服务端中位 ≤ 1.2 s、p95 ≤ 1.6 s；第 7 节写 Schema 的位置；第 8 节 `npc_line` 留到 P1。C-1 评审定了文档没写清的地方，并按前端评审做了几处加法和放宽：`commit.patch.interactables`、`act_plan_result.turnId`（语音那条路，和 `clientMsgId` 恰好给一个）、`reveal.collapsed`、错误码 `invalid_request`（400）；`action.target` 只在 `move` / `examine` / `go` 时必填，`lastTurn.character` 可为 `null`。这些先写在 Schema 里（`description` 标「C-1 评审定」），正文在 v1.0.1 补上。
- v0.3.9（2026-10-10）：第 7 节评测入口加 `check`（S-2：候选事件直接进第 3、4 步，不提交）；写明 `setup.events` 只给 `effects` 时怎么补成完整事件，`sc.canon` 是原著路径。只改评测入口（Python 包内），不改传输形状。
- v0.3.8（2026-10-07）：按 UX 对核对 U-2、U-3 的决定改文字，不改字段：`too_late` 那句改为叙事一行（地の文），不播声音，manifest 不加 `cues.too_late`；`voided` 的约定記憶帳不显示（前端过滤），「その頃」和结局里也不提（结局见 backend-design 2.9）。
- v0.3.7（2026-10-07）：按接口一致性核对（`consistency/contract-check-2026-10-07.md` B-1〜B-5）改文字，不改字段，按 v0.3.6 写的代码不用动：按钮例子改用半角数字（「10分早まる」「30分遅れる」「1時間ほど」「1時間遅れる」，ux-design 4.3）；幕末例子 `exit.1.vigil` 的 `tLabel` 改为「一日目・深夜」（t=1440）；2.5 写明节拍 `canon` = 契约的 `happened`；`too_late` 那句现在只出字幕、不播声音，等 UX 定要不要每个人物各录一句（U-3）；文件头的设计版本和日期。
- v0.3.6（2026-10-07）：人物字幕的定稿带 `source`（`live` / `script` / `fallback`），补转写失败时也发 `text: null` 的定稿，每轮人物恰好一条定稿（3.3，S-071，UX 提议）；manifest 的预录台词每句带 `text` 和 `durationMs`（2.1）；`safety_pause` 时玩家正在说的那一轮由服务端丢掉，前端不补发（3.12）。
- v0.3.5（2026-10-06）：新增 `safety_hint`：似是而非的自伤句不暂停，一局第一次给安静的小提示，第二次按信号暂停（S-069，3.12）。
- v0.3.4（2026-10-06）：`lastTurn.characterText` 在人物文字没收到时为 null（第 4 节）；和数据契约 v1.4、v1.5 对齐：过场里的二选一（`act_ended.options[].enRoute`、`act_choose.enRouteChoice`、错误 `invalid_choice`，3.11）；第四幕按钮的 `melosMinutes` 改为按 S-066 用 `arrival_delta` 算的本局实际值，加 `melosInTime`（2.3）；第一次到达下限的 `commit.cue` 和 manifest 的 `prerecorded.cues`（3.4、2.1）；`enRoute.choices[]` 的 `melosMinutes` 和 `afterLine`（3.11）；评测步骤 `choose`（第 7 节）；按钮分钟数用去掉 `latest` 的排程算（2.3）。
- v0.3.3（2026-10-06）：字幕定稿可能晚于 `turn_complete`（3.3，S-1 发现）；结局演出的 `staging` 加玩家、状态按 ux-design 11.1 的 8 个（3.13）；幕末打算成行时的事件按契约 1.2 带 `plan`（3.11）；第四幕的动作加 `melosMinutes`（2.3，UX 提议）。
- v0.3.2（2026-10-06）：和数据契约 v1.2 对齐：`tLabel` 格式已统一；结局接口和契约第 5 节的字段对应（`outcomeId`、`baseline`、尾声位置、`you` 的来源）；删约定类记忆追加 `forget` 事件、DELETE 回 `promiseVoided`；关键时刻四条的判定来源（`watchBeat`、结局署名、`mutualAid`）；时间规则（当场 prevented、`timeLink: "order"`）和规则库从 `worldsim.py` 移植；不逐字引用按占位符规则；评测入口按 `data/evals/README.md` 补全；Q-B11 关闭（前端 3D 定格，不生成插画）。
- v0.3.1（2026-10-06）：S-6 完成：「学習には使いません」可以写；断线后的语音连续性改为只靠重建（不开 Live 会话恢复，第 4 节）。
- v0.3（2026-10-06）：按前端评审 17 条、数据评审、ux-design 18.2 和 S-022〜S-053、D-012〜D-015 修改。主要变化：一次提交合成 `commit`（带 `fromSeq`）并且每轮推 `turn_settled`；turnSeq 只在一条连接内有效，服务端发起的轮次最高位为 1；`anchor` 改 `spot`，ID 用世界模型的；`tLabel` 改为约束之日起算，去掉 `koku`；作废统一用 `turn_retract`，作废时重建会话、原话立即清空，识别改正 = `turn_retract` + `text`；新增意图确认（`confirm`）、人物主动开口（`approach`、`turn_started`）、候选话语（`suggestions`）、幕末说出打算（`act_propose`）、幕切换和「その頃」（`act_transition`）、出戏卡（`safety_pause`）、结局演出的站位（`staging`）、时间消耗规则（3.7）、动作清单（3.8）；快照加 `places`、`actions`、`deadline`、`forecast`、`pending`、`relationLevel`；新增地图时间线接口（2.5）、记忆删除的后果查询（2.7）；記憶帳按约定、做了的事、记忆分栏；结局改为三层并带卡面字段，插画改为前端 3D 定格；`/v1/me` 带进行中的局，`welcome` 带最后一轮和未完成的状态；REST 跨站防护、会话 30 天滑动；mock 服务和 JSON Schema。
- v0.2（2026-10-06）：按前端设计第 14 节和前端答复修改：加 manifest；快照改成前端字段清单；消息加 `near/far`、`turn_retract`、`act_choose`、`world_patch`、`chain_reveal`、`memory_updated`、`act_ended`、`ending_ready`、`goaway`；帧头加 turnSeq；事件只推玩家可见投影；插画走同源路径；加分享草案。
- v0.1（2026-10-06）：初稿。
