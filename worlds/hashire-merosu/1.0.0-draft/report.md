# 世界模型校验报告

- 源文件：`worlds/hashire-merosu/1.0.0-draft/world.src.json`
- 原文：`worlds/hashire-merosu/sources/melos_plain.txt`（75 段，sha256 `2a437c047d7f09857355bfefc07e466e8b8b09fd1ee9db9c54f285a6efd5e685`）
- 出处 ID：`aozora:1567_ruby_4948@sha256:2a437c047d7f`
- 人物 13、地点 12、事实 31、节拍 29、因果边 26、状态变量 27、身份 5、锚点 17
- 出处条数：289；被引用段落 65/75（86%）
- **错误 0，警告 1**

## 错误

（无）

## 警告

- role.guard: 第二版的身份名「警吏」在世界模型里还指别的（4 处，例 $.ruby/14.word），开放第二版前给这个身份另起名（contracts 2.7）

- 场景 4、幕 4、世界结局 5（情景能走到 5）、能对话的角色 7、第一版身份 3、互助 33、情境动作 20（第四幕 12）、物品 9（能带在身上的 8）

情景 24 个，世界结局署名（endings.signature）不同的 10 种。

## 情景模拟（世界结局能否走到）

最后一列：beat.s2（セリヌンティウスがちらと疑う）/ beat.25（殴り合い）用的演法。

| 情景 | 说明 | 世界结局 | beat.24 | 到达 | 身代わり | 王 | 疑い / 殴り合い |
|---|---|---|---|---|---|---|---|
| sc.canon | 原著どおり（プレイヤーは何もしない） | canon-reunion | happened | Day 3 19:00 | released | reformed | happened / happened |
| sc.king-hardened | 約束の場でプレイヤーが王を嘲り、王の信頼が負になる | in-time-king-unchanged | happened | Day 3 19:00 | released | tyrant | happened / happened |
| sc.river-delay | 川岸でプレイヤーがメロスを 4 時間引き留める | too-late | late | — | executed | tyrant | happened / late |
| sc.river-delay-short | 川岸で 20 分だけ引き留める。原著のメロスは日没ちょうどに着くので、余裕はゼロ | too-late | late | — | executed | tyrant | happened / late |
| sc.delay-offset | 過場で「急かす」を選び（40 分稼ぐ）、川岸で 20 分引き留める | canon-reunion | happened | Day 3 18:40 | released | reformed | happened / happened |
| sc.no-dawdle | 第三幕末の過場で「急かす」を選ぶ（exit.3.road の enRoute）。のんびり歩かないので川に 40 分早く着く（体力の消耗は同じ） | canon-reunion | happened | Day 3 18:20 | released | reformed | happened / happened |
| sc.player-hostage | プレイヤーがセリヌンティウスの代わりに人質になる | player-substituted | happened | Day 3 19:00 | released | reformed | precondition-failed / precondition-failed |
| sc.player-hostage-late | プレイヤーが人質になり、メロスが遅れる | player-substituted | late | — | executed | tyrant | precondition-failed / late |
| sc.king-relents-early | 二日目にプレイヤーが王の心を先に開かせ、メロスは遅れる（S-034 第 5 類） | king-changed-first | late | — | on-cross | reformed | happened / late |
| sc.water-at-spring | 峠を降りたメロスに水を渡し、力尽きさせない（60 分早い） | canon-reunion | happened | Day 3 18:00 | released | reformed | happened / beat.25.v-selinuntius-only |
| sc.hold-then-help | 川岸で 30 分引き止め、その後で水を渡す（差し引き 30 分早い） | canon-reunion | happened | Day 3 18:30 | released | reformed | happened / beat.25.v-selinuntius-only |
| sc.detour | 牧童（または花婿から抜け道を聞いた人）が峠の脇道へ案内する。待ち伏せの峠を通らず格闘しないので体力が残り、その先で倒れない（60 分早い）。メロスは疑わず、刑場で殴られるのはセリヌンティウスだけ | canon-reunion | happened | Day 3 18:00 | released | reformed | happened / beat.25.v-selinuntius-only |
| sc.pass-scout | 誰でもできる峠の「帮他快」：あなたが先に登って待ち伏せに気づき、知らせる。片づくのが 10 分早いだけで、三人と戦い、その先で力尽き、刑場では原作どおり殴り合う（UX 校対 7.4） | canon-reunion | happened | Day 3 18:50 | released | reformed | happened / happened |
| sc.hold-no-help | 川岸で 30 分引き止め、何も補わない | too-late | late | — | executed | tyrant | happened / late |
| sc.wake-early | 第三幕、祝宴のあと夜明け前にメロスを起こして急かす（aff.wake-melos、出発が 60 分早まる） | canon-reunion | happened | Day 3 18:00 | released | reformed | happened / happened |
| sc.wake-early-then-hold | 夜明け前に起こしたうえで、川岸で 30 分引き止める（第三幕で稼いだ時間を第四幕で使う） | canon-reunion | happened | Day 3 18:30 | released | reformed | happened / happened |
| sc.groom-prep | 花婿の支度を手伝い、夜明けを待たずに承知させる（beat.10 が変わる）。婚礼は真昼のままで、出発も到着も原作どおり | canon-reunion | happened | Day 3 19:00 | released | reformed | happened / happened |
| sc.apprentice-faith | S-064：弟子が人質の夜に親方のそばにいて（+2）、二日目に「メロスは必ず戻る」と一緒に信じ続ける（+1）。親方は一度も疑わず、刑場で殴られるのはメロスだけ | canon-reunion | happened | Day 3 19:00 | released | reformed | precondition-failed / beat.25.v-melos-only |
| sc.apprentice-vigil-only | S-064：そばにいるだけ（+2）。言葉で支えなかったので、三日目の午後に親方はちらと疑う（原作どおり） | canon-reunion | happened | Day 3 19:00 | released | reformed | happened / happened |
| sc.no-doubt-at-all | 弟子が親方を支え（+2、+1）、旅の途中では泉で水を渡してメロスも倒れない。どちらも疑わず、殴り合わずに抱き合う | canon-reunion | happened | Day 3 18:00 | released | reformed | precondition-failed / beat.25.v-neither |
| sc.all-help | 第三、四幕の「帮他快」を全部やる（夜明け前に起こす、過場で急かす、浅瀬、脇道、泉で水、近道、先に知らせる）。上限なしなら 190 分早い 16:10 着。到着の下限 17:30（clock.deadline.earliestArrival、S-066）で止まる | canon-reunion | happened | Day 3 17:30 | released | reformed | happened / beat.25.v-selinuntius-only |
| sc.all-help-then-hold | 第三幕の「帮他快」（夜明け前に起こす、過場で急かす）で下限 17:30 に届いたあと、川岸で 30 分引き止め、その後は何もしない。下限より早い分は作廃なので 30 分そのまま遅れて 18:00（S-066 ②：拖慢不受上限影响） | canon-reunion | happened | Day 3 18:00 | released | reformed | happened / happened |
| sc.capped-hold-then-water | sc.all-help-then-hold のあと、泉で水を渡す。下限を離れていたので「帮他快」がまた効き、17:30 に戻る（それより早くはならない。ux-design 4.3） | canon-reunion | happened | Day 3 17:30 | released | reformed | happened / beat.25.v-selinuntius-only |
| sc.act4-help | 第四幕だけで「帮他快」を全部やる（浅瀬、脇道、近道、先に知らせる）。90 分早い | canon-reunion | happened | Day 3 17:30 | released | reformed | happened / beat.25.v-selinuntius-only |

## 原著路径时间线

| 节拍 | 故事时间 | 状态 |
|---|---|---|
| beat.01 未明、村を発つ | Day 0 04:00 | happened |
| beat.02 市の異変 | Day 0 19:10 | happened |
| beat.03 王の暴虐を知る | Day 0 19:30 | happened |
| beat.04 王城で捕縛 | Day 0 20:00 | happened |
| beat.05 王との問答と約束 | Day 0 20:30 | happened |
| beat.06 深夜、友が召される | Day 0 23:30 | happened |
| beat.07 満天の星の下を発つ | Day 0 23:45 | happened |
| beat.08 村に着き、婚礼を告げる | Day 1 10:00 | happened |
| beat.09 支度をして眠る | Day 1 10:30 | happened |
| beat.10 花婿を夜通し説く | Day 2 04:30 | happened |
| beat.11 真昼の婚礼 | Day 2 12:00 | happened |
| beat.12 大雨 | Day 2 12:30 | happened |
| beat.13 祝宴と別れの言葉 | Day 2 21:00 | happened |
| beat.14 薄明、雨中を走り出る | Day 3 04:30 | happened |
| beat.17 濁流、橋が流される | Day 3 06:00 | happened |
| beat.15 雨が上がる | Day 3 09:00 | happened |
| beat.16 気を緩めて歩く | Day 3 09:40 | happened |
| beat.18 激流を泳ぎ切る | Day 3 12:00 | happened |
| beat.19 峠の山賊 | Day 3 14:00 | happened |
| beat.20 力尽きる | Day 3 15:00 | happened |
| beat.s2 ちらと友を疑う | Day 3 16:00 | happened |
| beat.21 泉 | Day 3 16:30 | happened |
| beat.22 黒い風のように | Day 3 17:30 | happened |
| beat.s1 刑場に引き出される友 | Day 3 18:00 | happened |
| beat.23 フィロストラトス | Day 3 18:30 | happened |
| beat.24 日没、刑場へ | Day 3 19:00 | happened |
| beat.25 殴り合いと抱擁 | Day 3 19:05 | happened |
| beat.26 王の改心 | Day 3 19:15 | happened |
| beat.27 緋のマント | Day 3 19:20 | happened |

## 未被引用的段落

- 第 3 段：「なぜ殺すのだ。」…
- 第 5 段：「たくさんの人を殺したのか。」…
- 第 7 段：「おどろいた。国王は乱心か。」…
- 第 16 段：「なんの為の平和だ。自分の地位を守る為か。」こんどはメロスが嘲笑した。「罪の無い…
- 第 23 段：「なに、何をおっしゃる。」…
- 第 40 段：「待て。」…
- 第 41 段：「何をするのだ。私は陽の沈まぬうちに王城へ行かなければならぬ。放せ。」…
- 第 51 段：「ああ、メロス様。」うめくような声が、風と共に聞えた。…
- 第 52 段：「誰だ。」メロスは走りながら尋ねた。…
- 第 75 段：（古伝説と、シルレルの詩から。）…
