# 接口一致性核对（设计阶段收尾）· 2026-10-07

核对范围：`data/contracts.md` v1.5 ↔ `backend/api-contract.md` v0.3.6 ↔ `frontend/frontend-design.md` v1.0（第 6、7、9、12、14 节）↔ `pm/prd.md` v1.0.11；涉及到的地方顺带看了 `ux/ux-design.md` v1.0、`pm/decisions.md`、世界模型 `data/worlds/hashire-merosu/1.0.0-draft/world.json`。
只读核对，不改别人的文件；每条发给负责人，改完复核。

**总体结论**：主干对得上。消息名（3.2、3.3 全部 31 种）、事件 `type` / `actor` / `origin`、`promise` 状态、`via`、`activity`、结局三层和卡面字数（14 / 26 / 40 / 48、28px）、`staging` 8 个状态、5 类底线结局、`enRoute` / `melosMinutes` / `cue`、错误码、关闭码、S-017 的延迟线，四份文档一致。下面 23 处不一致（最初误数成 22）都不挡开发，但 P-1、B-1、F-1、F-2、F-6、P-2 会直接影响实现，建议进开发前改掉。

状态：○ 待改　✓ 已改并复核。**2026-10-07 05:51Z：23 处全部改好并复核。**

## 后端 · api-contract.md

| # | 问题 | 位置 | 对照 | 以谁为准 / 建议 | 状态 |
|---|---|---|---|---|---|
| B-1 | 按钮例子用汉数字：「浅瀬を探す（十分早まる）」「引き止める（三十分遅れる）」「手伝う（一時間ほど）」「六十分遅れる」 | api-contract.md:142 | ux-design.md:213（半角数字，「十分」会读成じゅうぶん）、contracts.md:500、:531 | UX / 契约：改成「（10分早まる）」「（30分遅れる）」「（1時間ほど）」「1時間遅れる」 | ✓ 10-07 复核（api-contract v0.3.7） |
| B-2 | 幕末例子 `exit.1.vigil` 的 `tLabel` 写「約束の日・深夜」 | api-contract.md:537 | world.json `exit.1.vigil.t = 1440` →「一日目・深夜」（Day 0 的「深夜」不会出现） | 世界模型：改成「一日目・深夜」 | ✓ 10-07 复核（api-contract v0.3.7） |
| B-3 | 时间线节拍 `status` 用 `canon`，契约里没有这个值 | api-contract.md:187 | contracts.md:675 `WorldState.beats` 是 `happened` | 保留 `canon`（UX「原作どおり」），在 2.5 写一句「`canon` = WorldState 的 `happened`」 | ✓ 10-07 复核（api-contract v0.3.7） |
| B-4 | `too_late` 时「……もう伝わってしまった。」说「前端播放预录」，但 manifest `prerecorded` 里没有这句 | api-contract.md:364、:90 | ux-design.md:1132-1146（6 句 + `arrival_capped`，没有这句）；frontend-design.md:294 | 和 UX 一起定：要么加进预录（`cues.too_late`，每个人物一句），要么写明「只出字幕」 | ✓ 10-07 复核：不预录，叙事一行（api-contract v0.3.8 :364、frontend :304、ux :961） |
| B-5 | 文件头引用 backend-design v1.0.3，最近更新 2026-10-06（v0.3.6 是 10-07） | api-contract.md:5-6 | backend-design.md:1 是 v1.0.6 | 改版本号和日期 | ✓ 10-07 复核（api-contract v0.3.7） |

## 数据 · contracts.md

| # | 问题 | 位置 | 对照 | 以谁为准 / 建议 | 状态 |
|---|---|---|---|---|---|
| D-1 | `relationLevel` 1〜5 在接口和 UX 里都用（記憶帳 5 格刻度），但没有一处写明哪档对哪个数 | contracts.md:730-736 | api-contract.md:138（「按 contracts 第 4 节」）、ux-design.md:726、:750-756 | 契约第 4 节的表加一列 level（≤-40 = 1 … ≥40 = 5），加法、不改语义 | ✓ 10-07 复核：contracts.md:727、:731-737 |

## 前端 · frontend-design.md

| # | 问题 | 位置 | 对照 | 以谁为准 / 建议 | 状态 |
|---|---|---|---|---|---|
| F-1 | `relationLabel` 注释写「顔見知り」「UX 10.1 的 6 档」「按数据的 valueLabels 给」 | frontend-design.md:185 | contracts.md:730-738（5 档，按 trust 区间，不是 valueLabels）；ux-design.md:758「6 档阶梯作废」 | 契约 + UX：改成 5 档；加 `relationLevel`（api-contract.md:125） | ✓ 10-07 复核（frontend-design v1.0.1） |
| F-2 | `WorldStore` 缺快照里前端要用的字段：`places[].enabled/reason`、`actions[]`（`melos`、`melosMinutes`、`melosInTime`、`estimatedMinutes`）、`deadline`、`forecast`、`pending`、`interactables[].estimatedMinutes` | frontend-design.md:173-192 | api-contract.md:108-136、:403（`patch` 按这些字段合并）；frontend 9.3、9.4 都在用 | api-contract：store 按快照补齐 | ✓ 10-07 复核（frontend-design v1.0.1） |
| F-3 | 「约 1.5 秒「言い直す」窗口」 | frontend-design.md:245 | api-contract.md:464（到 `turn_settled` 为止，实际 3〜5 秒）、:649；frontend 7.5（:292）已经按 `turn_settled` | api-contract：改成「到 `turn_settled` 为止（约 3〜5 秒）」 | ✓ 10-07 复核（frontend-design v1.0.1） |
| F-4 | 已经定了的事还写着「等后端」：按钮叫法「请 UX 和后端确认」(:289)、识别改正「〔待后端〕」(:295)、走动中的人物算哪「要后端定」(:399)、提交「合并还是规定顺序，等后端答复」(:452)、动作 `kind`「等 UX 和数据定」(:470)、`lastTurn`「〔待后端〕」(:490) | 见左 | 第 15 节 F-23、F-16、F-18 已写「已对齐」；api-contract 3.4、3.6、3.8、第 4 节 | 改成已定，指向 api-contract 对应节 | ✓ 10-07 复核（frontend-design v1.0.1） |
| F-5 | 事件投影字段列表有 `reason`（接口不给），少 `turnId`、`forPlayer`、`promise` | frontend-design.md:450 | api-contract.md:150-158 | api-contract | ✓ 10-07 复核（frontend-design v1.0.1） |
| F-6 | 人物走过来时玩家「走开（`far`）」 | frontend-design.md:406 | api-contract.md:330、:527（`approach_dismiss { reason: "walked_away" }`）；ux-design.md:436 | api-contract：走开时发 `approach_dismiss`（`far` 只管预热） | ✓ 10-07 复核（frontend-design v1.0.1） |
| F-7 | CSP 注释「结局插画走同源 `/v1/media/…`」 | frontend-design.md:773 | api-contract.md:274、:282（兜底图 `/assets/endings/…`，插画前端离屏渲染、不经后端） | api-contract：改路径说明 | ✓ 10-07 复核（frontend-design v1.0.1） |
| F-8 | 409 只写「进入它」，没写「新しく始める」= 先 `DELETE` 旧局再开局；结局字段写「按 contracts 第 5 节」，接口形状其实不同（`outcomeId`、`baseline`、`you.*`）；F-12 引「api-contract 3.5」 | frontend-design.md:804、:809、:836 | api-contract.md:103、:280、3.6；ux-design.md:942 | api-contract | ✓ 10-07 复核（frontend-design v1.0.1） |
| F-9 | `MicPrimer`「条款等后端确认后定稿」 | frontend-design.md:129 | decisions S-059；api-contract.md:751（已核对，可以写「学習には使いません」） | 改成已定 | ✓ 10-07 复核（frontend-design v1.0.1） |

## PM · prd.md

| # | 问题 | 位置 | 对照 | 以谁为准 / 建议 | 状态 |
|---|---|---|---|---|---|
| P-1 | 首次进入：「4G 打开网址到能走 ≤ 8 秒；点はじめる到能走 ≤ 6 秒；单个场景资产 ≤ 4MB」 | prd.md:189 | decisions.md:28 D-019（单场景 ≤ 10 MB、首次进入 ≤ 10 秒）；frontend-design.md:66、:511 | D-019（zg 定的）：PRD 7.1 改成 D-019 的数字 | ✓ 10-07 复核（PRD v1.0.12） |
| P-2 | 「导演事件次数」的数据来源写 `actor: "narrator"` | prd.md:249 | decisions S-062；contracts.md:49、:555、:689（导演事件 = `origin: "director"`，`narrator` 只用于 correction） | S-062：改成 `origin: "director"` | ✓ 10-07 复核（PRD v1.0.12） |
| P-3 | 「世界时钟」一行没有优先级；期限那句写「間に合わなければ身代わりが死ぬ」，实际界面文字是「期限　三日目の日没／遅れれば、身代わりが死ぬ」 | prd.md:138 | ux-design.md:164；api-contract.md:116 | 补 P0；文案以 UX 为准（或注明 PRD 只写意思） | ✓ 10-07 复核（PRD v1.0.12） |
| P-4 | 已经解决的还写着待定：一键改正「〔可行性待 S-1〕」(:135)；「学習には使いません」待后端确认 (:173，S-059 已确认)；延迟「S-1 后定稿」(:199，S-073 已实测通过)；UX「v1.0 待交」(:308) | 见左 | api-contract 3.6；decisions S-059、S-073 | 更新为已定 | ✓ 10-07 复核（PRD v1.0.12） |

## UX · ux-design.md

| # | 问题 | 位置 | 对照 | 以谁为准 / 建议 | 状态 |
|---|---|---|---|---|---|
| U-1 | 接口给了 `melosInTime`（做了以后还赶不赶得上），前端说「先不显示，等 UX」，UX 4.3 没提 | ux-design.md:205-222 | api-contract.md:142；frontend-design.md:459 | UX 定：显示不显示、怎么显示 | ✓ 10-07 复核（ux-design :219-224、:751、:552/:961、:8/:712） |
| U-2 | 約束的状态只有「まだ」「果たされた」「破られた」，没有 `voided`（删了约定类记忆后）怎么显示 | ux-design.md:743 | api-contract.md:226；contracts.md:655 | UX 定：不显示，或给一个说法 | ✓ 10-07 复核（ux-design :219-224、:751、:552/:961、:8/:712） |
| U-3 | 和 B-4 同一件事：`too_late` 那句要不要预录、每个人物怎么说 | ux-design.md:1132 | api-contract.md:364 | UX 出台词或说只出字幕，后端照着改 | ✓ 10-07 复核（ux-design :219-224、:751、:552/:961、:8/:712） |
| U-4 | 引用节号：`turn_retract` 引「api-contract 3.5」(:545，应为 3.6)；`/why` 折叠引「api-contract 2.5」(:705，应为 2.6)；文件头依据 prd v0.4、contracts v1.1、frontend v0.8 | 见左 | — | 改引用 | ✓ 10-07 复核（ux-design :219-224、:751、:552/:961、:8/:712） |
