# Homeward road: how it works, the four stops and the running stretches v1.0 / 帰り道：進み方、4 つの停留地点と走る区間 v1.0

| Item / 項目 | Content / 内容 |
|---|---|
| Purpose / 用途 | For the second frontend thread to follow when building the homeward road: first build the 4 stops (the river first), then replace the time cards between stops with running stretches. Same as the plaza: UX sets the requirements and positions, Frontend writes `layout.json`, checks against the real-time sun, and tells UX about any changes / 2 つ目のフロントエンドスレッドが帰り道を作るときに、これに沿って組む：まず 4 つの停留地点を作り（川から）、次に地点と地点の間の時間カードを走る区間に置き換える。広場と同じ：UX が要件と位置を決め、フロントエンドが `layout.json` を書き、リアルタイムの太陽で確認し、変えたら UX に伝える |
| Basis / 根拠 | PM's decision on 10-10 to "design first" (D-026), and to build the homeward road as stops plus running stretches (S-081); Frontend's cost estimates and answers (project folder `frontend/estimates/homeward-road.md`, `homeward-road-stops-answers.md`); Data's and Backend's answers on the M3 contract (section 10); Data's world model 1.0.0-draft: `place.river`, `place.mountain-pass`, `place.spring`, `place.road-to-city`, beat.15〜23, the affordances along the road; art-direction v1.4 (3.1 sun formula, 3.5, 4.2, 4.3, 5.7); ux-design 4.3, 6.2, 6.3; paragraphs 38〜58 of the original (`worlds/hashire-merosu/sources/melos_plain.txt`) / PM が 10-10 に決めた「まず設計」（D-026）、帰り道は停留地点と走る区間で作ること（S-081）。フロントエンドのコスト見積もりと回答（プロジェクトフォルダの `frontend/estimates/homeward-road.md`、`homeward-road-stops-answers.md`）。M3 の契約に対するデータとバックエンドの回答（10 節）。データの世界モデル 1.0.0-draft の `place.river`、`place.mountain-pass`、`place.spring`、`place.road-to-city`、beat.15〜23、道中の affordance。art-direction v1.4（3.1 太陽の式、3.5、4.2、4.3、5.7）。ux-design 4.3、6.2、6.3。原作の第 38〜58 段落（`worlds/hashire-merosu/sources/melos_plain.txt`） |
| Plans / 平面図 | [homeward-road/plans.svg](homeward-road/plans.svg) (the three stops river, pass and spring, the act 4 timeline and the act 2 night road; `make_plans.py` draws it from the coordinates in this document, so change coordinates in both places together) / [homeward-road/plans.svg](homeward-road/plans.svg)（川、峠、泉の 3 つの停留地点、第四幕のタイムラインと第二幕の夜道。`make_plans.py` はこの文書の座標で描くので、座標を変えるときは両方を一緒に変える） |
| Status / 状態 | v1.0 (2026-10-10). Frontend and Data reviewed v0.1, and their answers have been folded into each section / v1.0（2026-10-10）。フロントエンドとデータが v0.1 を確認し、回答は各節に反映済み |

All times are scheduled times (`window.canonical`; 三日目 = from minute 4320). When the schedule is delayed or brought forward, the whole stretch shifts with it, and things on screen appear when the clock reaches them.

時刻はすべて予定時刻で書く（`window.canonical`、三日目 = 4320 分目から）。遅れたり早まったりすると全体がそれに合わせてずれ、画面上の出来事は時計がその時刻になると現れる。

Only those who go with Melos come here: the night road of act 2 (city → village) and the daytime of act 4 (village → city). Those who stay in the city never see the homeward road.

ここに来るのはメロスと行く人だけ：第二幕の夜道（町 → 村）と、第四幕の昼（村 → 町）。町に残った人は帰り道を見ない。

---

## How the road works (S-081) / 帰り道の進み方（S-081）

### On the road, the clock decides where you are / 道の上では、どこにいるかは時計が決める

- 十里 is about 40 km. The four places on the road are 45〜120 minutes apart (`Place.adjacent`), while walking within a scene costs no time (`sceneWalkMinutes` 0) and one line of speech costs 15 minutes (act 4). The distance the player covers on foot doesn't match the distance traveled in the story.
  十里は約 40 km。道中の 4 つの場所の間は 45〜120 分の道のり（`Place.adjacent`）だが、シーンの中を歩いても時間はかからず（`sceneWalkMinutes` 0）、1 回話すと 15 分かかる（第四幕）。プレイヤーが足で歩く距離と、物語の中で進む道のりは一致しない。
- When following Melos in act 4, talking while running costs your time, not his (ux-design 4.3, S-038): while you talk, the two of you keep running. Wherever the clock has got to, that's where Melos has run to, and you're there too.
  第四幕でメロスについて行くとき、走りながら話すと時間を使うのはあなたで、彼ではない（ux-design 4.3、S-038）：話している間も二人は前へ走っている。時計が進んだところまでメロスは走っていて、あなたもそこにいる。
- **So when following Melos, your place is decided by the clock and Melos's schedule, not by where you walk.** Only when you aren't following him (staying behind partway, going ahead alone) do you spend time walking the distances in `Place.adjacent`.
  **したがってメロスについて行くとき、あなたのいる場所は時計とメロスの予定で決まり、あなたがどこへ歩いたかでは決まらない。** 彼について行かないとき（途中で残る、一人で先に行く）だけ、`Place.adjacent` の道のりに従って時間をかけて歩く。

### What plays out on this road / この道で演じること

| Place / 場所 | Act 2 (一日目, night, bridge still standing) / 第二幕（一日目、夜、橋はまだある） | Act 4 (三日目) / 第四幕（三日目） | Act 4 beats and actions / 第四幕のビートとアクション | Lines possible in act 4 〔estimate, 15 min per line〕 / 第四幕で話せる回数〔推算、1 回 15 分〕 |
|---|---|---|---|---|
| Spring (泉, 峠下の草原) / 泉（峠下の草原） | 02:45, **those who go with Melos start act 2 here** (`exit.1.road`). A sky full of stars; in the dark you can hear the spring / 02:45、**メロスと行く人の第二幕はここから始まる**（`exit.1.road`）。満天の星、暗闇の中で泉の水音が聞こえる | Arrive about 14:55 / 約 14:55 に着く | beat.20 15:00 he collapses; beat.21 16:30 he drinks from the spring and gets up. 「休ませる」「水を汲んで渡す」 / beat.20 15:00 彼が倒れる。beat.21 16:30 泉の水を飲んで立ち上がる。「休ませる」「水を汲んで渡す」 | About 6. The collapsed Melos wants to give up; this is the weightiest conversation on the homeward road / 約 6 回。倒れたメロスはあきらめかけている。帰り道で最も重い会話 |
| Pass / 峠 | About 03:30, crossed in the dark / 約 03:30、暗闇の中で越える | Arrive about 13:40 (before the top) / 約 13:40 に着く（頂上の手前） | beat.19 14:00 bandits. 「先に登って様子を見る」「峠を避けて、脇道を行く」「引き止める」 / beat.19 14:00 山賊。「先に登って様子を見る」「峠を避けて、脇道を行く」「引き止める」 | About 1〜2; the bandits come quickly / 約 1〜2 回、山賊はすぐに来る |
| River and bridge / 川と橋 | About 05:10, twilight, crossing the bridge. The water is still calm and the bridge still stands, setting up act 4 / 約 05:10、薄明、橋を渡る。水はまだ穏やかで橋もある。第四幕への伏線 | Arrive 11:20 (10:40 if 「急かす」 was chosen in the transition). **Those who go with Melos start act 4 here** (`exit.3.road`) / 11:20 に着く（幕間で「急かす」を選ぶと 10:40）。**メロスと行く人の第四幕はここから始まる**（`exit.3.road`） | beat.18 12:00 he prays to Zeus and leaps into the 濁流. 「流れの緩い浅瀬を探す」「引き止める」 / beat.18 12:00 ゼウスに祈ったあと濁流に飛び込む。「流れの緩い浅瀬を探す」「引き止める」 | About 2〜3 / 約 2〜3 回 |
| The field road to the city / 市へ続く野の道 | Not passed / 通らない | Enter about 17:20 / 約 17:20 に入る | beat.22 17:30 he dashes through a drinking party in the fields and hears travelers say 「磔にかかっている」; beat.23 18:30 フィロストラトス catches up. The distant city towers shine in the setting sun. 「近道を教える」「先に走って知らせる」「引き止める」 / beat.22 17:30 野の酒宴を突っ切り、旅人が「磔にかかっている」と言うのを聞く。beat.23 18:30 フィロストラトスが追いつく。遠くの塔楼が夕日に光る。「近道を教える」「先に走って知らせる」「引き止める」 | About 6; the last 2 can be with フィロストラトス / 約 6 回、最後の 2 回はフィロストラトスと話せる |
| (Neighboring village) / （隣村） | No stop; the narration covers it / 止まらない、ナレーションで伝える | The act 3 → act 4 transition page, 「急かす / 好きにさせる」 / 第三幕から第四幕への幕間のページ、「急かす / 好きにさせる」 | beat.15, beat.16 / beat.15、beat.16 | — |

In act 4 the road holds about 15 lines plus a few actions in total, and returns to the plaza at 19:00 (beat.24). The times of day along the road run 午前 → 真昼 → 午後 → 夕方 → 日没前, exactly what art-direction 3.5 describes as "late morning after the rain → the blazing afternoon sun → 斜陽".

第四幕の道中では合計約 15 回の発話といくつかのアクションがあり、19:00 に広場へ戻る（beat.24）。道中の時間帯は 午前 → 真昼 → 午後 → 夕方 → 日没前 の順で、ちょうど art-direction 3.5 の言う「雨上がりの昼前 → 午後の烈日 → 斜陽」になる。

Every stop has the same shape: **arrive together with Melos → he stops because of the story (praying, being blocked, collapsing) → you can talk, help him or hold him back → the beat plays → he starts running → you follow (or stay)**.

どの停留地点も同じ形：**メロスと一緒に着く → 物語の都合で彼が止まる（祈る、阻まれる、倒れる）→ あなたは話し、彼を助け、あるいは引き止められる → ビートが演じられる → 彼が走り出す → あなたはついて行く（または残る）**。

### Why stops plus running stretches / なぜ停留地点と走る区間なのか

- No single continuous terrain: it doesn't fit the time rules (either the sun jumps several hours when you cross an invisible boundary, or you walk 4 hours of road in 3 minutes and Melos has to teleport or wait for people); the road between beats is empty, with no quest markers or minimap (ux-design 6.2), so it's easy to get lost and boring to walk; and 10 MB spread over a large area means lower texture density.
  ひと続きの地形は作らない：時間のルールと合わない（見えない境界をまたぐと太陽が足もとで数時間跳ぶか、4 時間の道を 3 分で歩き終えてメロスが瞬間移動するか人を待つことになる）。ビートとビートの間の道は空っぽで、クエストマーカーもミニマップもない（ux-design 6.2）ので、迷いやすく退屈。10 MB を広い面積に広げるとテクスチャの密度も下がる。
- Between stops, put running stretches side by side rather than only time cards: "running side by side, the sun sinking, the city towers getting closer" is the core image of the original, and both beats on the field road happen while running. ux-design 4.3's 「並んで走りながら話す」 gets a real picture.
  停留地点の間は時間カードだけでなく、並んで走る区間を置く：「並んで走り、太陽が沈んでいき、塔楼が近づいてくる」は原作の最も核心的な画面で、野の道の 2 つのビートはどちらも走っている最中に起きる。ux-design 4.3 の「並んで走りながら話す」が本当の画面になる。
- Build order: first the 4 stops with time cards between them, then swap the time cards for running, with no rework. With reduced motion on, time cards are shown as before. Frontend's estimate: about 40% more work than time cards alone, and 1〜1.5 MB more, for about 10〜11.5 MB in total on the homeward road 〔estimate〕; the running stretches have the characters running in place while the road scrolls backward (the treadmill technique), which neatly covers loading the next stop.
  作る順番：まず 4 つの地点を作り、地点の間は時間カードにしておき、そのあと時間カードを走る区間に置き換える。作り直しは出ない。動きを減らす設定がオンのときは従来どおり時間カードを出す。フロントエンドの見積もり：時間カードだけの場合より作業量は約 4 割増え、1〜1.5 MB 増え、帰り道の合計は約 10〜11.5 MB〔推算〕。走る区間は人がその場で走り、道が後ろへ巻き取られていく（ランニングマシン方式）ので、次の地点の読み込みをちょうど隠せる。

### Movement rules / 移動のルール

1. **Stops**: the spring, the pass and the river are small standing areas with soft boundaries (ux-design 6.2): the road extends out at both ends, and walking back along it curves you round again. When you reach the exit in the direction Melos is heading:
   **停留地点**：泉、峠、川の 3 か所は立ち止まる小さな場所で、境界は柔らかい（ux-design 6.2）：道は両端から外へ延び、戻る方向へ歩くと道は折り返してくる。メロスが向かう方向の出口まで歩いたとき：
   - **Once he has started running**: walking out counts as 「メロスを追う」, with no need to find a button. There is a button too, in 「近くの人」 and in the prompt after he leaves.
     **彼がもう走り出したあとなら**：外へ歩き出すことが「メロスを追う」になり、別にボタンを探す必要はない。ボタンもあり、「近くの人」と彼が去ったあとの案内の中にある。
   - **While he hasn't set off yet** (before the beat: praying by the river, lying by the spring): the road curves back too, and it doesn't count as you leaving. Going ahead alone is an explicit choice and must not happen just because a tap on the ground landed near the edge: say it by voice (「先に行く」), or tap 「ひとりで先へ行く」 in 「近くの人」; the button shows the distance (e.g. 「（峠まで1時間40分ほど）」). Once chosen, you no longer follow him; see item 4. No confirmation dialog: like other actions, "you know the cost before you spend it" (ux-design 4.3).
     **彼がまだ動き出していないとき**（ビートの前：川辺で祈っている、泉のそばで倒れている）：道はやはり折り返し、あなたが行ったことにはならない。一人で先に行くのははっきりした選択であり、地面をタップした位置がたまたま端だったせいで起きてはならない：音声で言う（「先に行く」）か、「近くの人」の「ひとりで先へ行く」をタップする。ボタンには道のりを書く（例：「（峠まで1時間40分ほど）」）。選んだあとは彼について行かなくなり、第 4 項に従う。確認ダイアログは出さない。ほかのアクションと同じく「使う前にわかっている」（ux-design 4.3）。
   - Why walking out doesn't count as going ahead: on a phone it's easy to tap near the edge of the area, and leaving Melos behind in one step would make players feel cheated. Once he has run off, walking forward can only mean wanting to catch up, so at that point walking out counts as following.
     なぜ外へ歩き出しただけで先に行ったことにしないのか：スマホでは地面をタップすると場所の端に当たりやすく、一歩でメロスを置き去りにすると、プレイヤーはだまされたと感じる。彼が走り去ったあとなら、前へ歩くのは追いつきたいからでしかないので、そのときは外へ出ればついて行ったことにする。
   - The river's exit is on the far bank: in act 4, before he swims across, the water surface isn't in the walkable area (the navmesh doesn't include water), so crossing the river takes a riverside action. 「調べる」 at the water's edge gives one line, 「とても渡れそうにない」: this line is sent down by the server; the frontend doesn't produce story text on its own (section 10, "Other").
     川の出口は対岸にある：第四幕で彼が泳いで渡る前は、水面は歩ける範囲に入っていない（ナビメッシュは水面を含まない）ので、川を渡るには川辺のアクションを使う。水辺で「調べる」と「とても渡れそうにない」の 1 行が出る：この 1 行はサーバーが送る。フロントエンドは物語の文字を自分で出さない（10 節「その他」）。
2. **Short running stretches** (act 4's river → pass, pass → spring, spring → field road, section 5):
   **短い走る区間**（第四幕の 川 → 峠、峠 → 泉、泉 → 野の道、5 節）：
   - 15〜25 seconds, with the camera tracking alongside from behind and to the side of the two (ux-design 6.3). Roadside dressing changes per stretch.
     15〜25 秒で、カメラは二人の斜め後ろから並行して追う（ux-design 6.3）。道端の配置は区間ごとに変える。
   - The clock runs from the departure time to the arrival time (Melos's schedule), the sun moves with it, and the time label at the top of the screen changes along with it.
     時計は出発の時刻から到着の時刻まで進み（メロスの予定）、太陽もそれに合わせて動き、画面上部の時刻ラベルも変わる。
   - **No talking on these stretches in the first release**: they're too short for a voice exchange, and we'd also have to handle "arrived halfway through a sentence". Talking happens at the stops, on the field road and on the act 2 night road.
     **第 1 版ではこの区間では話せない**：短すぎて音声のやりとりに時間が足りず、「話している途中で着いた」にも対処しなければならない。話すのは停留地点、野の道、第二幕の夜道で。
   - Tap the screen to skip. If the next stop hasn't finished loading when skipped, show a time card first and enter once it has loaded (Frontend estimate item 5; a 15〜25-second stretch normally covers the loading, so this only happens when skipping right at the start). With reduced motion, show the time card directly.
     画面をタップするとスキップする。スキップしたときに次の地点がまだ読み込み終わっていなければ、まず時間カードを出し、読み込みが終わってから入る（フロントエンドの見積もり第 5 項。15〜25 秒の区間なら本来読み込みを隠せるので、最初にすぐスキップしたときだけ起きる）。動きを減らす設定のときは直接時間カードを出す。
3. **The long running stretch: the whole field road is running** (section 4): from about 17:20 to the city gate, with things along the road appearing when the clock reaches them.
   **長い走る区間：野の道は全区間を走る**（4 節）：約 17:20 から城門まで走り、道中の出来事は時計がその時刻になると現れる。
   - Talking here works like at the stops: 15 minutes per line, and Melos's schedule doesn't change (ux-design 4.3).
     ここで話すのは停留地点と同じで、1 回 15 分、メロスの予定は変わらない（ux-design 4.3）。
   - When not talking the two keep running and the picture never stops; when idle, the usual 「時を進める」 prompt appears (here labeled 「走り続ける」), and tapping it jumps to the next event. The clock doesn't advance on its own.
     話していないときも二人は走り続け、画面は止まらない。放置しているときは通常どおり「時を進める」の案内が出て（ここでは「走り続ける」と書く）、タップすると次の出来事まで飛ぶ。時計がひとりでに進むことはない。
   - After tapping 「先に走って知らせる」, you run into the city ahead (staged on the same stretch, you alone), landing at the execution ground (`place.execution-ground`).
     「先に走って知らせる」をタップすると、あなたが先に町へ走り込み（演出は同じ区間を使い、あなた一人）、刑場（`place.execution-ground`）に着地する。
   - Reaching the city gate → switch to the plaza (scene switch ≤ 4 seconds; the whole field road can be used to preload the plaza).
     城門まで走ったら → 広場に切り替える（シーンの切り替えは 4 秒以内。野の道の全区間を広場の先読みに使える）。
4. **No longer following partway**: if you stay behind after Melos runs off (e.g. by saying 「ここで待つ」), or go ahead alone before he sets off (item 1), you no longer follow his schedule; after that, getting to the next stop costs the walking time in `Place.adjacent`, and the transition is a time card.
   **途中でついて行かなくなる**：メロスが走り去ったあとに残る（たとえば「ここで待つ」と言う）、あるいは彼が動き出す前に一人で先に行く（第 1 項）と、もう彼の予定には従わない。そのあと次の地点へ行くには `Place.adjacent` の道のりに従って時間をかけ、移動は時間カードになる。
5. **Act 2 only stops at the river**:
   **第二幕は川にだけ止まる**：
   - Act 2 has no beats on the road, and Melos never stops all night (the original: 「一睡もせず十里の路を急ぎに急いで」). So the night road is one long stretch: the two walk briskly side by side, **and can talk** (10 minutes per line in act 2), with things on the road appearing by the clock (5.1). When not talking, the idle prompt is 「歩き続ける」, and tapping it jumps to the next event.
     第二幕は道中にビートがなく、メロスは一晩中止まらない（原作「一睡もせず十里の路を急ぎに急いで」）。だから夜道はひと続きの長い区間：二人は並んで早足で歩き、**話せる**（第二幕は 1 回 10 分）。道中のものは時計に合わせて現れる（5.1）。話していないときの放置の案内は「歩き続ける」で、タップすると次の出来事まで飛ぶ。
   - Act 2 is the act where you get to know Melos, and talking is all there is to it, so the night road must allow talking; it can't be skipped over with a short stretch.
     第二幕はメロスを知る幕で、話すことがこの幕のすべてなので、夜道は話せなければならず、短い区間で済ませてはいけない。
   - The only stop is the river (about 05:10, twilight): the bridge still stands and the water is calm, foreshadowing the broken bridge of act 4. After crossing the bridge, 「メロスを追う」 goes to the end of the act.
     唯一の停留地点は川（約 05:10、薄明）：橋はまだあり、水も穏やかで、第四幕の落ちた橋への伏線になる。橋を渡ったあと「メロスを追う」で幕末に入る。
6. **Light**: each stop only appears at these times, so only 5 sets are needed (section 8). The real-time sun is the base, with one baked skylight set per key time; running stretches all use real-time light.
   **光**：各地点はこれらの時刻にしか現れないので、5 セットで足りる（8 節）。リアルタイムの太陽を土台にし、重要な時間帯ごとに天空光を 1 セットずつベイクする。走る区間はすべてリアルタイムの光。

---

## 0. Shared rules / 共通事項

### 0.1 Coordinates and orientation / 座標と方角

- One plan per stop, in meters. **+x is always the direction toward Syracuse** (the direction Melos runs in act 4), +y is to its left, z is up, and **the ground at the landing spot is z = 0**.
  地点ごとに平面図を 1 枚、単位はメートル。**+x は常にシラクスへ向かう方向**（第四幕でメロスが走る方向）、+y はその左手、z は上、**着地点の地面は z = 0**。
- For each stop, the compass bearing of +x is given (north 0°, clockwise), and Frontend sets `rotationDeg` the same way as for the plaza.
  地点ごとに +x の方位（北 0°、時計回り）を書き、フロントエンドは広場と同じやり方で `rotationDeg` を設定する。
- Real geography: Syracuse is on the east coast, and the village is 十里 inland to the west (art-direction 1). So the road runs roughly east–west: act 2 heads west, act 4 runs east. From west to east the order is: village → 隣村 → **river** → **pass** → **spring** → **field road** → city gate.
  実際の地理：シラクスは東海岸にあり、村は西の内陸十里のところ（art-direction 1）。だから道はおおむね東西に走り、第二幕は西へ、第四幕は東へ走る。西から東への順は：村 → 隣村 → **川** → **峠** → **泉** → **野の道** → 城門。
- The sun uses the formula in art-direction 3.1 (the same one as `assets/pipeline/plaza/sunpos.py`); each stop only changes the bearing of +x.
  太陽は art-direction 3.1 の式を使い（`assets/pipeline/plaza/sunpos.py` と同じ）、地点ごとに +x の方位だけを変える。

### 0.2 Where the sun is at each stop (computed from the formula) / 各地点での太陽の位置（式で計算）

| Stop / 地点 | +x bearing / +x の方位 | Time / 時刻 | Altitude / 高度角 | Azimuth / 方位 | Shadow length / object height / 影の長さ / 物の高さ | Which side of the runners the sun is on / 走る人のどちら側に太陽があるか |
|---|---|---|---|---|---|---|
| River (act 2) / 川（第二幕） | 90° | 05:10 | 1.9° | 67° (east-northeast) / 67°（東北東） | — | Walking west, the sun is behind and to the right, still blocked by the ridge to the east (1.5) / 西へ歩くので太陽は背後のやや右、まだ東の稜線に隠れている（1.5） |
| River (act 4) / 川（第四幕） | 90° | 11:20〜12:00 | 70°→72° | 151°→180° | 0.3〜0.4 | On the right (south), almost overhead / 右手（南）、ほぼ頭上 |
| Pass / 峠 | 80° | 13:40〜14:00 | 62°→58° | 237°→244° | 0.5〜0.6 | Behind on the right / 右後方 |
| Spring / 泉 | 100° | 15:00〜16:30 | 47°→29° | 258°→273° | 0.9→1.8 | Behind on the right → directly behind / 右後方 → 真後ろ |
| Field road / 野の道 | 114° | 17:20〜19:00 | 19°→0° | 280°→294° | 2.9→(none at 19:00) / 2.9→（19:00 はなし） | Directly behind. At 19:00 it's exactly behind (114° + 180° = 294°, the same axis as the plaza's gate avenue) / 真後ろ。19:00 にちょうど背後（114° + 180° = 294°、広場の城門通りと同じ軸） |

### 0.3 What every stop has / どの地点にもあるもの

- **Landing spot** (where the player appears): facing +x (−x for the act 2 river); 9 m behind and 3.5 m up is the default follow camera position (ux-design 6.3), and **that stretch must be kept clear**: only road and low grass, no trees, rocks or buildings.
  **着地点**（プレイヤーが現れる場所）：+x 向き（第二幕の川は −x 向き）。背後 9 m、高さ 3.5 m がデフォルトの追従カメラの位置（ux-design 6.3）で、**この範囲は空けておく**：道と低い草だけで、木、岩、建物は置かない。
- **Melos's spots**: where he first stands on arrival, where he stops because of the story (praying, catching his breath, collapsing), and where the beat is staged. Staging-only spots are marked `auto: false`, as on the plaza.
  **メロスのスポット**：着いて最初に立つ場所、物語の都合で止まる場所（祈る、息を整える、倒れる）、ビートを演じる場所。演出専用のスポットは広場と同じく `auto: false` にする。
- **The road ahead and the road back**: both ends are soft boundaries (ux-design 6.2). At the forward end, before Melos sets off, walking out curves you back; once he's running, walking out is 「メロスを追う」 ("Movement rules" item 1). The back end always curves you back: the first release doesn't offer walking back (there's nothing to do back there). Exit spots are named `way.<direction>`, as on the plaza.
  **前へ続く道と戻る道**：両端とも柔らかい境界（ux-design 6.2）。前の端では、メロスが動き出す前に外へ出ようとすると道は折り返し、彼が走り出したあとに外へ出れば「メロスを追う」になる（「移動のルール」第 1 項）。戻る側の端は常に折り返す：第 1 版では戻る道は用意しない（戻ってもできることがない）。出口のスポットは広場と同じく `way.<方向>` と呼ぶ。
- **The walkable core is about 30〜40 m**. The road extends about 10 m further at each end, only for the camera and the distance.
  **歩ける中心部は約 30〜40 m**。道は両端からさらに 10 m ほど延びるが、カメラと遠景のためだけ。
- **Distance**: a sky shader plus a few layers of silhouettes (art-direction 3.5 item 4). Every stop shows the direction of the previous or next stop, so the player knows where on the road they are (1.4 shows the notch of the pass, 2.4 looking back shows the river valley, 3.1 has the pass behind, 4.2 the city towers).
  **遠景**：空のシェーダーと数層のシルエット（art-direction 3.5 第 4 項）。どの地点からも前の地点か次の地点の方向が見え、プレイヤーは道のどこにいるかがわかる（1.4 では峠の切れ込みが見え、2.4 で振り返ると川の谷が見え、3.1 は背後に峠、4.2 は塔楼）。

### 0.4 Shared roadside material pack (downloaded once, Frontend estimates about 2 MB) / 共用の道端の素材パック（ダウンロードは 1 回、フロントエンドの見積もりで約 2 MB）

| Material / 素材 | Where used / 使う場所 | Distance / 距離 | Key points / 要点 |
|---|---|---|---|
| Limestone dirt road / 石灰岩の土の道 | All stops and running stretches / すべての地点と走る区間 | **Close-up, most important / 近景、最重要** | Whitish earth with a touch of ochre, fine gravel, donkey hoofprints and cart ruts. Act 4 river and R1: wet after the rain, one shade darker, puddles in the hollows reflecting the sky (same texture; wetness is a material parameter) / 白っぽく少し赭色を帯びた土、細かい砂利、ロバの蹄の跡、轍。第四幕の川と R1：雨上がりで濡れて一段濃く、くぼみの水たまりが空を映す（同じテクスチャで、濡れは素材のパラメータ） |
| Dry grassland / 乾いた草地 | Spring, field road, running stretches / 泉、野の道、走る区間 | Close-up / 近景 | Early summer, mostly already yellow, with seed heads. Green near water (the spring's trickle, riverbanks). Wildflowers only in yellow, white and purple (crown daisy, wild carrot, thistle); **no red poppies**: they're everywhere in Sicily in May, but they'd compete with 緋色 (art-direction 6) / 初夏で、大半はもう黄色く、穂がある。水の近く（泉の細い流れ、川岸）は緑。野の花は黄、白、紫だけ（シュンギク、ノラニンジン、アザミ）。**赤いヒナゲシは置かない**：シチリアの 5 月にはどこにでもあるが、緋色と競合する（art-direction 6） |
| Limestone outcrops / 石灰岩の露頭 | The pass's rock gate, the spring's rock, riverbanks / 峠の岩門、泉の岩、川岸 | Close-up / medium / 近景 / 中景 | Grey-white, rounded karst rock, with black and orange lichen. One shade darker when wet / 灰白色で角の丸いカルストの岩、黒と橙の地衣類。濡れると一段濃くなる |
| Scree / 砕石 | Pass, R2 / 峠、R2 | Close-up / 近景 | Angular scree slopes. River pebbles are round and belong to the river pack / 角ばった砕石の斜面。川の小石は丸く、川のパックに入れる |
| Dry-stone wall / 空積みの石垣 | Spring, R1, field road / 泉、R1、野の道 | Medium / 中景 | No mortar, shared with the village (art-direction 4.2) / 漆喰を使わず、村と共用（art-direction 4.2） |
| Trees and shrubs / 木と低木 | Everywhere / 各所 | Medium / far / 中景 / 遠景 | Olive (shared with the plaza), holm oak (dark green small leaves), plane tree (spring), poplar and willow (river), cypress (vertical silhouettes in the distance), dwarf fan palm (*Chamaerops humilis*, native to Sicily, fan-shaped leaves, the most place-defining plant at the pass and R2), mastic (shrub) / オリーブ（広場と共用）、セイヨウヒイラギガシ（holm oak、濃い緑の小さな葉）、プラタナス（泉）、ポプラと柳（川）、イトスギ（遠くの縦長のシルエット）、チャボトウジュロ（*Chamaerops humilis*、シチリア在来、扇形の葉、峠と R2 で最も土地らしさを出す）、マスティックの木（低木） |
| Wheat / 麦 | Field road, R3 / 野の道、R3 | Medium / 中景 | Golden, partly cut already, bound into sheaves standing in the field (early summer is harvest time, the same as the village in art-direction 4.2) / 金色で、一部はもう刈られ、束にして畑に立ててある（初夏は麦の収穫期、art-direction 4.2 の村と同じもの） |
| Reeds / 葦 | River / 川 | Medium / 中景 | Local reeds (*Phragmites*) / 在来の葦（*Phragmites*） |

**Period accuracy** (the art-direction 4.3 table still applies; these are the things most likely to creep in along the road): prickly pear cactus and agave (everywhere along Sicilian roads today, and the most common in scanned assets), eucalyptus, citrus groves, maize. One addition: no modern barbed wire or concrete drainage ditches along the road.

**時代考証**（art-direction 4.3 の表はそのまま有効。道中で最も紛れ込みやすいもの）：ウチワサボテンとリュウゼツラン（今日のシチリアの道端にはどこにでもあり、スキャン素材で最もよく見る）、ユーカリ、柑橘の果樹園、トウモロコシ。1 つ追加：道端に現代の有刺鉄線やコンクリートの排水溝を置かない。

---

## 1. River and bridge / 川と橋

Two packages with different geometry, sharing the riverbanks (Frontend estimate item 2):

ジオメトリの異なる 2 つのパッケージで、川岸は共用する（フロントエンドの見積もり第 2 項）：

| | Act 2 `scene.road-river-calm` / 第二幕 `scene.road-river-calm` | Act 4 `scene.road-river-flood` / 第四幕 `scene.road-river-flood` |
|---|---|---|
| Time / 時刻 | Arrive about 05:10 (coming from the pass), 10 minutes to cross the bridge / 約 05:10 に着く（峠の方から来る）、橋を渡るのに 10 分 | Arrive 11:20 (`exit.3.road`; those who go with Melos start act 4 here); beat.18 12:00 he swims across / 11:20 に着く（`exit.3.road`、メロスと行く人の第四幕はここから始まる）。beat.18 12:00 に泳いで渡る |
| Who is there / 誰がいるか | Melos (act 1 clothes, carrying his bundle), you / メロス（第一幕の衣服、荷物を持つ）、あなた | Melos, you / メロス、あなた |
| Direction / 方向 | Walking west: the landing spot is on the **east bank**, facing −x / 西へ歩く：着地点は**東岸**で、−x 向き | Running east: the landing spot is on the **west bank**, facing +x / 東へ走る：着地点は**西岸**で、+x 向き |
| Water / 水 | About 8 m wide in the middle of the channel, calm, dark, mirror-like, with a layer of mist lying on the surface / 川筋の中央に幅約 8 m、穏やかで暗く、鏡のよう。水面に霧が一層張りついている | All 16 m between the banks is water, muddy yellow and opaque, churning, with foam and branches swept down; the surface is about 1.5 m higher than in act 2, only 20 cm below the top of the banks. The last 3 m of the road on the west bank is under water: **the road walks straight into the water** / 両岸の間 16 m がすべて水で、濁った黄色で不透明、渦を巻き、泡と流されてきた枝がある。水面は第二幕より約 1.5 m 高く、岸の上端より 20 cm 低いだけ。西岸の道の最後の 3 m は水に沈んでいる：**道がそのまま水の中へ入っていく** |
| Bridge / 橋 | The wooden bridge is intact: deck 16 m long, 2.2 m wide, three pairs of wooden piles, about 2.2 m above the water / 木の橋は無事：橋面は長さ 16 m、幅 2.2 m、木の杭が 3 組、水面から約 2.2 m | The deck is gone. Three pairs of piles: the pair at x = −1 leans downstream, the pair at x = 3 is snapped off at the waterline, the pair at x = 7 is broken 30 cm above the water with a tangle of branches and one deck plank caught on it. The breaks are fresh: pale wood shows inside against the sun-greyed surface (this is where "just swept away" reads) / 橋面はなくなっている。3 組の杭：x = −1 の組は下流へ傾き、x = 3 の組は水面の高さで折れ、x = 7 の組は水面から 30 cm 上で折れて、枝の塊と橋板 1 枚が引っかかっている。折れ口は新しい：中の明るい色の木がのぞき、日に焼けて灰色になった表面と対比になる（「流されたばかり」と読み取れるところ） |
| Ferry landing / 渡し場 | A small wooden jetty on the downstream west bank, two flat-bottomed boats tied to posts; the ferryman's reed-roofed hut / 下流の西岸に小さな木の桟橋があり、平底の小舟 2 艘が杭につながれている。渡し守の葦葺きの小屋 | Only the jetty's posts remain, with torn rope ends on them, and no boats (「繋舟は残らず浪に浚われて」); the hut is empty with its door open (「渡守りの姿も見えない」) / 桟橋は杭だけが残り、杭には引きちぎられた縄の端があり、舟はない（「繋舟は残らず浪に浚われて」）。小屋は空で、扉が開いている（「渡守りの姿も見えない」） |
| Upstream shallows / 上流の浅瀬 | The channel widens and a dry pebble bar shows in the middle / 川筋が広がり、中央に乾いた小石の河原が出ている | The pebble bar is under water, but here the surface is flatter than elsewhere, with three or four stones breaking the surface: the place for 「流れの緩い浅瀬を探す」, readable but not conspicuous / 小石の河原は水の下だが、ここは水面がほかより平らで、石が 3、4 個水面から出ている：「流れの緩い浅瀬を探す」の場所で、見ればわかるが目立ちはしない |
| Sky / 空 | Twilight, the east whitening behind you; in the west, the Earth's shadow and a pink band (1.5) / 薄明、背後の東が白んでいる。西は地球影とピンクの帯（1.5） | After the rain, broken cumulus clearing; **dark rain clouds still sit on the hills to the north (upstream)**, showing where the water came from / 雨上がり、ちぎれた積雲が消えていく。**北（上流）の山にはまだ黒い雨雲がかかっていて**、水がどこから来たのかがわかる |

### 1.1 Plan (+x = 90°, due east) / 平面（+x = 90°、真東）

```
          North (upstream)  rain clouds on the hills (act 4)
   −x west bank ← to the village                       to the pass → +x east bank
                 Poplars      Shallows (y 9〜16)          Poplars
  way.west ═══ Landing (act 4) ═ Bridgehead ┃┃ Wooden bridge ┃┃ Bridgehead ═ Landing (act 2) ═ way.east
                 Hut  Jetty        River (x −5〜11)       Willow (the tree Melos grabs)
          South (downstream)  the sun is on this side (act 4 noon)

          北（上流）  雨雲が山にかかる（第四幕）
   −x 西岸 ← 村へ                     峠へ → +x 東岸
                 ポプラ         浅瀬（y 9〜16）     ポプラ
  way.west ═══ 着地点(第四幕) ═ 橋のたもと ┃┃ 木の橋 ┃┃ 橋のたもと ═ 着地点(第二幕) ═ way.east
                 小屋  桟橋        川（x −5〜11）     柳（メロスがつかまる木）
          南（下流）  太陽はこちら側（第四幕の正午）
```

| Thing / もの | Position (x, y) / 位置（x, y） | Notes / 説明 |
|---|---|---|
| West bank road / 西岸の道 | (−30, 0) → (−5, 0), 3 m wide / (−30, 0) → (−5, 0)、幅 3 m | Slopes gently down to the bridgehead. In act 4, x −8〜−5 is under water / 橋のたもとへ向かってゆるく下る。第四幕では x −8〜−5 が水に沈む |
| West bank top / 西岸の岸の上端 | x = −5 | In act 2 there is also a 4 m wide low flat below the bank (reeds), with the water's edge at x ≈ −1 / 第二幕では岸の下に幅 4 m の低い河原（葦）もあり、水際は x ≈ −1 |
| East bank top / 東岸の岸の上端 | x = 11 | In act 2 the water's edge is at x ≈ 7 / 第二幕の水際は x ≈ 7 |
| East bank road / 東岸の道 | (11, 0) → (30, 0) | Climbs east toward the pass (R1 connects here) / 東へ上り、峠へ向かう（R1 はここからつながる） |
| Bridge / 橋 | x −5 → 11, y ±1.1 / x −5 → 11、y ±1.1 | Piles at x = −1, 3, 7 / 杭は x = −1、3、7 |
| Ferry landing / 渡し場 | Jetty (−5, −10) → (−1, −10), 1.2 m wide; mooring posts (−5.5, −9), (−5.5, −11.5) / 桟橋 (−5, −10) → (−1, −10)、幅 1.2 m。舟をつなぐ杭 (−5.5, −9)、(−5.5, −11.5) | |
| Ferryman's hut / 渡し守の小屋 | Center (−11, −12), 3 × 3 m, door facing east / 中心 (−11, −12)、3 × 3 m、扉は東向き | |
| Upstream shallows / 上流の浅瀬 | y 9〜16, the channel widens to x −3〜13; pebble bar x 3〜7, y 10〜15 / y 9〜16、川筋は x −3〜13 まで広がる。小石の河原 x 3〜7、y 10〜15 | |
| The tree Melos grabs / メロスがつかまる木 | A willow on the east bank at (11.5, −12), about 10 m, leaning over the river with exposed roots / 東岸の (11.5, −12) の柳、約 10 m、川の上へ傾き、根がむき出し | 「対岸の樹木の幹に、すがりつく」 |
| Poplars / ポプラ | West bank (−8, 7), (−9, 13), (−7, −17); east bank (13, 5), (14, 11), (13, −17) / 西岸 (−8, 7)、(−9, 13)、(−7, −17)。東岸 (13, 5)、(14, 11)、(13, −17) | In the wind the leaves flip to show their silver-white undersides / 風が吹くと葉が裏返り、銀白色の裏が見える |

### 1.2 Spots / スポット

| Name / 名前 | Position / 位置 | Facing / 向き | Use / 用途 |
|---|---|---|---|
| `road-west` | (−16, −1) | +x | **Act 4 landing spot**. Behind it, (−25, −1) is the default camera, with only road there / **第四幕の着地点**。背後の (−25, −1) がデフォルトのカメラで、道だけがある |
| `melos-bridgehead` | (−6, 0.8) | +x | In act 4 Melos first stands here on arrival (「はたと、とまった」「茫然と、立ちすくんだ」), then paces along the bank and shouts downstream (「声を限りに呼びたててみた」) / 第四幕でメロスは着いてまずここに立ち（「はたと、とまった」「茫然と、立ちすくんだ」）、それから岸に沿って行き来し、下流へ叫ぶ（「声を限りに呼びたててみた」） |
| `melos-pray` `auto: false` | (−5.6, −2.5) | +x (toward the river) / +x（川のほう） | 「川岸にうずくまり、男泣きに泣きながらゼウスに手を挙げて哀願した」; he kneels here before 12:00 / 「川岸にうずくまり、男泣きに泣きながらゼウスに手を挙げて哀願した」。12:00 まではここにひざまずく |
| `swim-in` `auto: false` | (−5, −1) | +x | Where he leaps in at beat.18 / beat.18 で飛び込む場所 |
| `swim-out` `auto: false` | (11, −12) | — | Swept downstream, he grabs the willow / 下流へ流され、柳にしがみつく |
| `shallows-in` / `shallows-out` `auto: false` | (−5.5, 12) / (12.5, 13) | +x | Where they cross instead if 「流れの緩い浅瀬を探す」 was chosen / 「流れの緩い浅瀬を探す」を選んだときは代わりにここから渡る |
| `far-bank` | (15, −4) | +x | Where both are after crossing (Melos 「馬のように大きな胴震いを一つして」); R1 starts here / 渡ったあと二人がいる場所（メロスは「馬のように大きな胴震いを一つして」）。R1 はここから始まる |
| `road-east` | (17, 1) | −x | **Act 2 landing spot** (continuing from the night road). Behind it, (26, 1) is the default camera / **第二幕の着地点**（夜道から続く）。背後の (26, 1) がデフォルトのカメラ |
| `melos-wash` `auto: false` | (6.6, −2.5) | −x (toward the water) / −x（水のほう） | In act 2 Melos kneels at the east bank's edge, scoops water to wash his face and takes a sip, then crosses the bridge. Not a beat; just what someone who has walked all night without sleep would do 〔inference〕. In act 4 this spot is under the flood / 第二幕でメロスは東岸の水際にひざまずき、水をすくって顔を洗い、一口飲んでから橋を渡る。ビートではなく、一晩眠らずに急いだ人がすること〔推測〕。第四幕ではこの場所は洪水の下 |
| `way.west` / `way.east` | (−24, 0) / (24, 0) | | In act 4 forward is east (but you have to cross the river, see 1.3); in act 2 forward is west / 第四幕では前は東（ただし川を渡る必要がある、1.3 参照）、第二幕では前は西 |

### 1.3 Where you can walk / 歩ける場所

- **Act 2**: both banks, the bridge deck and the jetty are all walkable. After crossing the bridge, walking west out of `way.west`, or tapping 「メロスを追う」, goes to the end of act 2 (section 10: the clock jumps to beat.08).
  **第二幕**：両岸、橋面、桟橋はすべて歩ける。橋を渡って西へ `way.west` から出るか、「メロスを追う」をタップすると、第二幕の幕末に入る（10 節：時計は beat.08 へ飛ぶ）。
- **Act 4**: only the west bank (x < −5.3); you can't walk into the water; 「調べる」 at the water's edge gives the line 「とても渡れそうにない」 ("Movement rules" item 1). You only reach the east bank after the beat.18 staging: the staging shows how you got across (swimming after him, or wading across the shallows), the picture settles at `far-bank`, and R1 begins.
  **第四幕**：歩けるのは西岸（x < −5.3）だけで、水には入れない。水辺で「調べる」と「とても渡れそうにない」の 1 行が出る（「移動のルール」第 1 項）。東岸へは beat.18 の演出のあとでしか行けない：演出であなたがどう渡ったか（彼について泳いで渡る、あるいは浅瀬を歩いて渡る）を見せ、画面は `far-bank` で止まり、続いて R1 が始まる。
- Those who stop following and stay on the west bank: crossing later takes 30 minutes of swimming per Data's `place.river.crossing` 〔set by Data〕, with a time card as the transition.
  途中でついて行かず西岸に残った人：あとで川を渡るには、データの `place.river.crossing` に従って泳いで 30 分かかり〔データが決める〕、移動は時間カードになる。

### 1.4 Camera / カメラ

- Act 4 landing: from behind facing east, you see Melos 10 m ahead standing at the bridgehead, the broken piles and the 濁流, the willow and poplars on the far bank, the road climbing east, and in the distance the notch of the pass on the ridge (about 2 km, elevation angle about 5° 〔inference; the distance only needs roughly the right direction and height〕). Where the next stop is, you can see at first glance.
  第四幕の着地：背後から東を向くと、10 m 先の橋のたもとに立つメロス、折れた杭と濁流、対岸の柳とポプラ、東へ上る道、遠くの稜線に峠の切れ込みが見える（約 2 km、仰角約 5°〔推測。遠景は方向と高さがおおよそ合っていればよい〕）。次の地点がどこか、ひと目でわかる。
- Act 2 landing: from behind facing west, you see Melos at the water's edge, the wooden bridge, the water with mist lying on it, the poplars and the road on the far bank, and the hills far to the west.
  第二幕の着地：背後から西を向くと、水際のメロス、木の橋、霧の張りついた水面、対岸のポプラと道、遠く西の山が見える。
- Downstream is to the south: looking downstream at noon in act 4 is backlit, with the crests of the 濁流 glittering all over. For the beat.18 staging, the suggested camera shoots south from the `road-west` side as he is swept away, with the wave crests backlit (Frontend decides).
  下流は南側：第四幕の正午に下流を見ると逆光で、濁流の波頭が一面にきらめく。beat.18 の演出のカメラは、`road-west` の側から南へ向けて彼が流されていくところを撮り、波頭が逆光になる案を勧める（フロントエンドが決める）。

### 1.5 Light (two sets) / 光（2 セット）

| | Act 2 / 第二幕 | Act 4 / 第四幕 |
|---|---|---|
| Bake time / ベイクの時刻 | 05:15 | 11:45 |
| Direct light / 直射光 | None: although the sun is up at 05:00, it's blocked by the ridge to the east (the one with the pass), and doesn't reach the valley until about 05:40 〔inference, assuming a ridge elevation of about 7°〕. Approach (Frontend): each package records the elevation angle of the eastern ridge, and while the sun is below it direct light is 0; once it clears the ridge, real-time light slants in over the ridge, with no extra bake / なし：太陽は 05:00 にはもう昇っているが、東の稜線（峠のある尾根）に遮られ、谷に日が差すのは約 05:40〔推測、稜線の仰角を約 7° として計算〕。やり方（フロントエンド）：パッケージごとに東の稜線の仰角を 1 つ記録し、太陽がそれより低いあいだは直射光を 0 にする。越えたらリアルタイムの光が稜線から斜めに差し込み、別にベイクしない | High and hard, from the south, with short shadows huddled under feet and trees / 高く硬く、南から来る。影は短く、足もとと木の下に縮こまる |
| Sky / 空 | Grey-blue overhead. **Looking west (act 2's direction of travel) you see the Earth's shadow: a dark blue band on the horizon, with a pink band above it**. This is the reverse of the pink band over the sea to the east after sunset on the act 1 plaza: act 1 ends with pink in the east, act 2 ends with pink in the west. The peaks of the distant western hills catch the light first, a touch of pale gold. **The sky is generated as if the sun were at about −1.5°** (only the sky changes, not the sun direction): at 05:10 the sun is already 1.9° above the horizon, and physically the Earth's shadow would have sunk and the pink band would be faint (Frontend 15:54Z). The landing time isn't changed (that would mean moving the arrival time in the world model); the valley is in the hills' shadow with no direct light anyway, so a sky that still looks pre-sunrise reads as right. When building the river, Frontend makes two versions (a −1.5° sky / landing brought forward to 04:55) for UX to compare and choose / 頭上は灰青色。**西（第二幕の進む方向）を見ると地球影：地平線に暗い青の帯、その上にピンクの帯**。これは第一幕の広場で日没後に東の海の上に見えたピンクの帯の裏返し：第一幕は東のピンクで終わり、第二幕は西のピンクで終わる。西の遠い山の頂が先に照らされ、淡い金色を帯びる。**空は太陽が −1.5° 前後にあるものとして生成する**（空だけを替え、太陽の方向は変えない）：05:10 には太陽はすでに地平線から 1.9° 上にあり、物理どおりなら地球影は沈んでピンクの帯も薄い（フロントエンド 15:54Z）。着地の時刻は変えない（それには世界モデルの到着時刻を動かす必要がある）。谷はもともと山の影の中で直射光がないので、空がまだ日の出前のように見えても正しく見える。フロントエンドは川を作るときに 2 枚（−1.5° の空 / 着地を 04:55 に早める）を出し、UX が見比べて選ぶ | Broken cumulus clearing, their edges lit; dark rain clouds still on the hills upstream to the north / ちぎれた積雲が消えていき、雲の縁が照らされる。北の上流の山には暗い雨雲がかかっている |
| Air / 空気 | A layer of mist over the river; people crossing the bridge walk with their legs in the mist / 川面に霧が一層あり、橋を渡る人の脚は霧の中 | Damp and clear; the distance is sharper than usual (washed by the rain) / 湿って澄んでいて、遠くがいつもよりくっきり見える（雨に洗われた） |
| Ground / 地面 | Dry, dew / 乾いていて、露がある | Wet, one shade darker, with puddles / 濡れて一段濃く、水たまりがある |

### 1.6 Materials (river only, plus the shared pack from 0.4) / 素材（川専用、0.4 の共用パックに加えて）

| Material / 素材 | Key points / 要点 |
|---|---|
| Calm water (act 2) / 穏やかな水（第二幕） | Dark, reflecting the sky, with mist. Frontend estimate item 4: one water surface + scrolling normals + environment reflection + mist / 暗く、空を映し、霧がある。フロントエンドの見積もり第 4 項：水面 1 枚＋スクロールする法線＋環境反射＋霧 |
| 濁流 (act 4) / 濁流（第四幕） | Muddy yellow, opaque, with downstream-flowing normals and foam; the surface is subdivided for small waves, and the spray where it hits the piles is instanced quads (Frontend estimate item 4). The color is the yellow-brown of mud, **not red-brown**, kept separate from 緋色 / 濁った黄色で不透明、流れに沿った法線と泡。水面は細かく分割して小さな波を作り、杭に当たってはねる水しぶきはインスタンス化した板ポリゴン（フロントエンドの見積もり第 4 項）。色は泥の黄褐色で、**赤褐色ではない**。緋色と区別する |
| Fresh silt (act 4) / 新しい泥（第四幕） | A thin coat of yellow-brown mud over the grass and stones on the banks, with a dark high-water line along the bank / 岸の草と石に黄褐色の泥が薄く付き、岸に沿って暗い色の水位線が 1 本ある |
| Wooden bridge, piles / 木の橋、杭 | Old wood weathered grey, lashed with hemp rope. In act 4 the breaks show pale new wood / 日に焼けて灰色になった古い木で、麻縄で縛ってある。第四幕では折れ口に明るい色の新しい木がのぞく |
| Boats, jetty, hut / 小舟、桟橋、小屋 | The boats exist only in act 2; the hut has a reed roof / 小舟は第二幕にだけある。小屋は葦葺き |
| Riverbank pebbles and wet rock / 川岸の小石と濡れた岩 | Round pebbles; wet limestone one shade darker / 丸い小石。濡れた石灰岩は一段濃い |

---

## 2. The pass / 峠

`scene.road-pass`. Only a stop in act 4 (in act 2 it's crossed at night as part of the night road, see 5.4).

`scene.road-pass`。第四幕でだけ止まる（第二幕は夜に通り過ぎ、夜道の一部になる、5.4 参照）。

| Item / 項目 | Content / 内容 |
|---|---|
| Time / 時刻 | Arrive about 13:40 (Data: 20 minutes before beat.19); beat.19 14:00 bandits / 約 13:40 に着く（データ：beat.19 の 20 分前）。beat.19 14:00 山賊 |
| Who is there / 誰がいるか | Melos (clothing stage 2, just swum the river, half dry), you; 5 bandits (3 charge, 2 hang back: 「残る者のひるむ隙に」) / メロス（衣服は第 2 段階、川を泳いだばかりで半乾き）、あなた。山賊 5 人（3 人が襲いかかり、2 人はひるむ：「残る者のひるむ隙に」） |
| Original / 原作 | 「ぜいぜい荒い呼吸をしながら峠をのぼり、のぼり切って、ほっとした時、突然、目の前に一隊の山賊が躍り出た。」 |
| What you can do / できること | 「先に登って様子を見る」「峠を避けて、脇道を行く」 (the shepherd boy, or someone who heard about it from the groom) 「引き止める」; 1〜2 lines / 「先に登って様子を見る」「峠を避けて、脇道を行く」（牧童、または花婿から聞いた人）「引き止める」。1〜2 回話せる |

### 2.1 Plan (+x = 80°, east by north) / 平面（+x = 80°、東やや北）

```
                       North: rock face, holm oak scrub
              Goat track (side path) ────────────╮ rounds the shoulder of the hill, out of sight
   Cairn ◇ ╱
way.west ═ Landing ═ Shelf [small holm oak · Melos catching his breath] ═ Fork ╲ Switchbacks up ╲ ▲Rock gate▲ Saddle ═ way.east (down to the plain)
                       South: steep scree slope                            ↑ bandits hide in the shadow behind the rocks

                       北：岩壁、セイヨウヒイラギガシの茂み
              羊の通る細道（脇道）────────────╮ 山の肩を回り込んで見えなくなる
   ケルン ◇ ╱
way.west ═ 着地点 ═ 平らな段［小さなヒイラギガシ · 息を整えるメロス］═ 分かれ道 ╲ つづら折りを上る ╲ ▲岩門▲ 鞍部 ═ way.east（下は平野）
                       南：急な砕石の斜面                            ↑ 山賊は岩の裏の影に隠れている
```

| Thing / もの | Position (x, y) / 位置（x, y） | Height (z) / 高さ（z） | Notes / 説明 |
|---|---|---|---|
| Uphill road / 上り道 | (−30, −1) → (−16, −1) | −0.8 → 0.4 | Coming up from the river valley, 2.5 m wide / 川の谷から上ってくる、幅 2.5 m |
| Shelf / 平らな段 | x −16〜−4, y −5〜5 / x −16〜−4、y −5〜5 | About 1.2, flat / 約 1.2、平ら | The flattest part of this stretch, where you can walk around and talk / この区間で最も平らな場所で、歩き回ったり話したりできる |
| Small holm oak / 小さなヒイラギガシ | (−11, 4.5), about 5 m tall, crown radius 2.5 m / (−11, 4.5)、高さ約 5 m、樹冠の半径 2.5 m | | The only shade on the whole pass. At 13:40 its shade falls on the northeast side of the tree / 峠全体で唯一の木陰。13:40 の木陰は木の北東側に落ちる |
| Fork and cairn / 分かれ道とケルン | Fork (−5, 1.5), cairn (−5.5, 3) / 分かれ道 (−5, 1.5)、ケルン (−5.5, 3) | | The cairn is a herders' waymark: the shepherd boy recognizes it at once; others just see a pile of stones / ケルンは牧人の道しるべ：牧童はひと目でわかるが、ほかの人にはただの石の山にしか見えない |
| Switchbacks / つづら折り | (−4, 0) → (3, −4) → (7, 1) → (11, 0) | 1.2 → 7 | 2 m wide, with stone steps / 幅 2 m、石段がある |
| Rock gate / 岩門 | North rock x 8〜14, y 2〜6, 5 m above the saddle; south rock x 8.5〜13.5, y −5.8〜−2.2, 4 m high / 北の岩 x 8〜14、y 2〜6、鞍部より 5 m 高い。南の岩 x 8.5〜13.5、y −5.8〜−2.2、高さ 4 m | Saddle 7 / 鞍部 7 | A 4 m wide gap between two limestone rocks, set against the sky: looking up from the shelf, this is where you're going next / 2 つの石灰岩の間の幅 4 m の切れ目で、空を背にしている：平らな段から見上げると、次に向かう場所だとわかる |
| Saddle / 鞍部 | x 11〜13 | 7 | You can walk up to here. Further on (x > 13), before Melos sets off, the road curves back / ここまで歩ける。その先（x > 13）は、メロスが動き出す前なら道が折り返す |
| Goat track (side path) / 羊の通る細道（脇道） | (−5, 2) → (−1, 8) → (4, 13) → (8, 16) | 1.2 → 3 | Less than 1 m wide, rounding the shoulder of the hill, turning out of sight behind the holm oak scrub at (8, 16). Walkable up to (6, 15) / 幅 1 m 足らずで、山の肩を回り、(8, 16) でヒイラギガシの茂みの裏へ曲がって見えなくなる。(6, 15) まで歩ける |
| South side / 南側 | y < −6 | | Steep scree slope, soft boundary (narration like 「足を滑らせそうだ」; copy to be decided later) / 急な砕石の斜面で、柔らかい境界（「足を滑らせそうだ」のようなナレーション、文言はのちに決める） |
| North side / 北側 | y > 8 (except the track) / y > 8（細道を除く） | | Rock face and scrub / 岩壁と茂み |

### 2.2 Where the bandits hide / 山賊が隠れる場所

- The 5 hide in the rock shadow on the east side of the rock gate (the far side of the saddle): `bandit-1〜3` behind the north rock (15〜18, 5〜8), `bandit-4, 5` behind the south rock (15〜17, −5〜−7), all `auto: false`, outside the walkable area.
  5 人は岩門の東側（鞍部の向こう）の岩の影に隠れている：`bandit-1〜3` は北の岩の裏 (15〜18, 5〜8)、`bandit-4、5` は南の岩の裏 (15〜17, −5〜−7)。すべて `auto: false` で、歩ける範囲の外。
- At 14:00 the sun is at 244° and the rocks' shadows point to 64° (northeast), falling right behind the rock gate: **to someone climbing up from below, the rocks are bright, behind them is black, and the men hide in the black**. When baking, this patch of shadow must be pushed very deep, with strong contrast against the sun-bleached rock faces.
  14:00 の太陽は 244° で、岩の影は 64°（北東）を向き、ちょうど岩門の裏に落ちる：**下から登ってくる人には岩は明るく、その裏は黒く、人は黒の中に隠れている**。ベイクするとき、この影は非常に深く沈め、日に白く焼けた岩肌との対比を大きくする。
- Before the beat, players who walk up to the saddle can't see them either. On the west-facing side of the north rock (8, 3.2) there's a crack; standing in front of it you can glimpse a little movement behind (a corner of cloth, a pebble rolling down), a hint for those willing to look, not required 〔optional〕. When 「先に登って様子を見る」 is chosen, the staging has you go round the rock gate, see them, and turn back to warn him.
  ビートの前は、プレイヤーが鞍部まで歩いても彼らは見えない。北の岩の西向きの面 (8, 3.2) に岩の割れ目があり、その前に立つと裏の動きが少しだけ見える（布の端、転がり落ちる小石）。探す気のある人へのヒントで、必須ではない〔任意〕。「先に登って様子を見る」を選んだときは、演出であなたが岩門を回り込んで彼らを見つけ、振り返って危険を知らせる。
- The beat.19 staging is at the saddle: the bandits leap out from both sides of the rock gate, Melos wrests away a club, knocks down three, and charges down the east side of the saddle (R2 continues from here).
  beat.19 の演出は鞍部で行う：山賊が岩門の両側から躍り出て、メロスは棍棒を奪い、3 人を打ち倒し、鞍部の東側を駆け下りる（R2 はここからつながる）。
- **The bandits cover the lower half of their faces with cloths** (「ものも言わず」), walk-around grade only, faces ≤ 6% of screen height (ending-shots rule 1). Coarse wool, brown and grey, no armor, carrying wooden clubs. The fight follows art-direction 5.7: no blood spatter.
  **山賊は布で顔の下半分を覆う**（「ものも言わず」）。歩行用だけで、顔は画面の高さの 6% 以下（ending-shots ルール 1）。粗い毛織物で、褐色と灰色、鎧はなく、木の棍棒を持つ。格闘は art-direction 5.7 に従う：血しぶきはない。

### 2.3 Spots / スポット

| Name / 名前 | Position / 位置 | Facing / 向き | Use / 用途 |
|---|---|---|---|
| `shelf-west` | (−20, −1) | +x | **Landing spot**. Behind it, (−29, −1) is the default camera, on the uphill road / **着地点**。背後の (−29, −1) がデフォルトのカメラで、上り道の上 |
| `melos-breath` | (−9.2, 5.2) | +x | Melos in the shade of the small holm oak, hands on his knees catching his breath, then leaning against the trunk. He stands here for the 20 minutes (ぜいぜい荒い呼吸) 〔inference: the original doesn't say he stops; this gives the player time to talk and do one thing, and Data sets the arrival 20 minutes before beat.19〕 / メロスは小さなヒイラギガシの木陰で両手を膝について息を整え、それから幹にもたれる。20 分間ここに立っている（ぜいぜい荒い呼吸）〔推測：原作は彼が止まったとは書いていない。プレイヤーが話して 1 つ行動する時間を作るため、データは到着を beat.19 の 20 分前にした〕 |
| `saddle` `auto: false` | (12, 0) | +x | Beat staging / ビートの演出 |
| `side-path` | (−1, 8) | Along the track / 細道に沿って | After 「峠を避けて、脇道を行く」 is chosen, the two turn onto the track here, and R2 becomes 「山腹の脇道」 (section 5, R2') / 「峠を避けて、脇道を行く」を選ぶと二人はここで細道へ曲がり、R2 は「山腹の脇道」になる（5 節 R2'） |
| `way.west` / `way.east` / `way.side` | (−28, −1) / (16, 0) / (8, 16) | | |

### 2.4 Camera / カメラ

- Landing: from behind looking up toward the east, Melos is in the shade ahead on the left, the switchbacks climb, and the rock gate is at the top of the frame against the sky (at the default camera's 12.5° downward angle, the rock gate sits roughly a quarter of the way down from the top of the frame 〔estimate〕).
  着地：背後から東を見上げると、メロスは左前方の木陰にいて、つづら折りが上り、岩門は画面の上部で空を背にしている（デフォルトのカメラの俯角 12.5° で計算すると、岩門は画面の上から約 1/4 のところ〔推算〕）。
- Looking back (west): below your feet the river valley, a muddy yellow 濁流, and the rain clouds on the hills to the north. The road you came along is visible at a glance.
  振り返る（西）：足もとは川の谷で、濁った黄色の濁流があり、北の山には雨雲。歩いてきた道がひと目で見える。
- Standing on the saddle looking east: below is the plain, bleached in the heat haze, with a line of sea mist in the distance. **The city towers are not visible**; save them for the field road (4).
  鞍部に立って東を見る：下は陽炎の中で白っぽい平野、遠くに海の霧の線。**塔楼は見えない**。野の道（4）まで取っておく。

### 2.5 Light (one set) / 光（1 セット）

- Bake time 14:00. The blazing afternoon sun: highlights bleached white, short hard shadows, heat haze in the distance (art-direction 3.2 真昼・午後).
  ベイクの時刻は 14:00。午後の烈日：ハイライトは白く飛び、影は短く硬く、遠くに陽炎（art-direction 3.2 真昼・午後）。
- Sky: deep blue overhead, whitish at the horizon; the rain clouds to the north have withdrawn behind the far hills.
  空：頭上は深い青、地平線は白っぽい。北の雨雲は遠い山の向こうへ退いている。
- Clothing stage 2 is wet: it starts drying here (dry within 1 hour, a material parameter; see section 6).
  第 2 段階の衣服は濡れている：ここから乾き始める（1 時間以内に乾ききる、素材のパラメータ、6 節参照）。

### 2.6 Materials / 素材

| Material / 素材 | Key points / 要点 |
|---|---|
| Limestone outcrops (rock gate, rock face) / 石灰岩の露頭（岩門、岩壁） | **The most important close-up at this stop**. Sun-bleached faces, weathered rounded edges, lichen; cold grey in shadow / **この地点で最も重要な近景**。日に白く焼けた面、風化して丸くなった角、地衣類。影の中は冷たい灰色 |
| Scree and stone steps / 砕石と石段 | Angular, with a line worn shiny by feet / 角ばっていて、人が歩いて光るようになった筋が 1 本ある |
| Shrubs / 低木 | Dwarf fan palm, mastic, thyme-like low clumps, dry grass / チャボトウジュロ、マスティックの木、タイムのような低い茂み、枯れ草 |
| Small holm oak / 小さなヒイラギガシ | Small dark green leaves, grey-black trunk / 濃い緑の小さな葉、灰黒色の幹 |

---

## 3. The spring / 泉

`scene.road-spring`. Only a stop in act 4, and also in runs that took the side path (the act 2 night road starts out from here, see 5.4).

`scene.road-spring`。第四幕でだけ止まり、脇道を選んだ回でも止まる（第二幕の夜道の起点で、ここから出発する、5.4 参照）。

| Item / 項目 | Content / 内容 |
|---|---|
| Time / 時刻 | Arrive about 14:55 (5 minutes before beat.20); beat.20 15:00 he collapses; beat.21 16:30 he drinks from the spring and gets up. **In runs that took the side path**: beat.20 doesn't happen, and beat.21 is at 15:30 (60 minutes earlier than the original; Data ran it through worldsim): he only drinks, without the collapse, and Melos never doubts (`var.melos.doubted` is false) / 約 14:55 に着く（beat.20 の 5 分前）。beat.20 15:00 倒れる。beat.21 16:30 泉の水を飲んで立ち上がる。**脇道を選んだ回**：beat.20 は起きず、beat.21 は 15:30（原作より 60 分早い、データが worldsim で試した）：水を飲むだけで倒れる場面はなく、メロスは疑いを抱かない（`var.melos.doubted` は false） |
| Who is there / 誰がいるか | Melos (stage 3: after fighting the bandits), you / メロス（第 3 段階：山賊と戦ったあと）、あなた |
| Original / 原作 | 「午後の灼熱の太陽がまともに、かっと照って来て…ついに、がくりと膝を折った」「路傍の草原にごろりと寝ころがった」「すぐ足もとで、水が流れているらしい…岩の裂目から滾々と、何か小さく囁きながら清水が湧き出ている」「斜陽は赤い光を、樹々の葉に投じ、葉も枝も燃えるばかりに輝いている」 |
| What you can do / できること | 「水を汲んで渡す」 (before he collapses) 「休ませる」; **the weightiest conversation on the homeward road, about 6 lines**: Melos lying in the grass, wanting to give up / 「水を汲んで渡す」（彼が倒れる前）「休ませる」。**帰り道で最も重い会話、約 6 回**：草の中に倒れてあきらめかけているメロス |

### 3.1 Plan (+x = 100°, east by south) / 平面（+x = 100°、東やや南）

```
                   North: olive terraces on the hillside
      Plane trees (three, to the west)     Rock · spring
                               ↘ trickle
way.west ═ Landing ════ Road ════════ ╪ (stepping stones) ════ way.east
  ↑ the pass is behind you                      Dry-stone wall
                   South: wheat fields beyond the wall

                   北：山腹のオリーブの段々畑
      プラタナス（3 本、西側）     岩·泉
                               ↘ 細い流れ
way.west ═ 着地点 ════ 道 ════════ ╪（飛び石）════ way.east
  ↑ 背後は峠                      空積みの石垣
                   南：石垣の外は麦畑
```

| Thing / もの | Position (x, y) / 位置（x, y） | Notes / 説明 |
|---|---|---|
| Road / 道 | (−28, −4) → (24, −4), 3 m wide / (−28, −4) → (24, −4)、幅 3 m | Comes down from the pass and levels out here. z: west end +2, landing spot 0, east end −0.6 / 峠から下ってきて、ここで平らになる。z：西端 +2、着地点 0、東端 −0.6 |
| Dry-stone wall / 空積みの石垣 | South of the road at y = −6.5, x −18〜16, 0.8 m high / 道の南 y = −6.5、x −18〜16、高さ 0.8 m | Gives scale / 尺度を与える |
| Grassland / 草地 | x −16〜16, y −2.5〜16 / x −16〜16、y −2.5〜16 | Rises gently to the north, z +1.2 at y = 16 / 北へゆるやかに上がり、y = 16 で z +1.2 |
| The spring's rock / 泉の岩 | A low limestone ledge, x −3.5〜1.5, y 6.2〜8.4, 1.3 m high / 低い石灰岩の段差、x −3.5〜1.5、y 6.2〜8.4、高さ 1.3 m | A crack at the bottom of its south face / 南向きの面の下に岩の割れ目がある |
| Crack and small pool / 割れ目と小さな水たまり | Crack (−0.4, 6.1); pool center (0, 5.3), 1.2 m across / 割れ目 (−0.4, 6.1)。水たまりの中心 (0, 5.3)、直径 1.2 m | Water wells up from the crack; the pebbles on the bottom of the pool are visible / 水が割れ目から湧き出し、水たまりの底の小石が見える |
| Trickle / 細い流れ | (0.3, 4.8) → (2.5, 2.5) → (5, 0) → (6.5, −2.5), passing under a few stepping stones on the road and into the ditch beyond the wall / (0.3, 4.8) → (2.5, 2.5) → (5, 0) → (6.5, −2.5)、道の飛び石の下をくぐり、石垣の外の溝へ流れ込む | The grass on both sides of the trickle is green / 細い流れの両側の草は緑 |
| Plane trees / プラタナス | (−13, 6) 16 m tall, (−16, 10.5) 18 m tall, (−11, 12) 14 m tall / (−13, 6) 高さ 16 m、(−16, 10.5) 高さ 18 m、(−11, 12) 高さ 14 m | Oriental plane: big leaves, bark flaking off in patches of grey, cream and grey-green. On the **west side** of the spring / スズカケノキ：大きな葉、樹皮はまだらに剥がれて灰色、乳白色、灰緑色。泉の**西側**にある |
| Gentle rise to the east / 東のゆるい上り | x ≈ 20 | The ground rises a little and hides the plain to the east: the city towers still can't be seen from here / 地面が少し盛り上がり、東の平野を隠す：ここからはまだ塔楼は見えない |

**Why the plane trees are to the west** (checked against the sun):

- At 15:00 the sun is at 258° and 47° high; tree shadows point to 78° (east-northeast) and fall north of the spring, **so the place where Melos collapses is in full sun** (「まともに、かっと照って来て」).
- At 16:30 the sun is at 273° and 29° high; from the spring the plane trees are at 293°, only about 20° from the sun, so the sun sits right behind the lower-middle part of the crowns: **the leaves are lit through from behind, 「葉も枝も燃えるばかりに」**. By then the spring is also in the trees' shade, and Melos drinks in dappled light.

**なぜプラタナスが西側にあるのか**（太陽で確かめた）：

- 15:00 の太陽は 258°、高度 47° で、木の影は 78°（東北東）を向いて泉の北側に落ちる。**メロスが倒れる場所は日差しをまともに受ける**（「まともに、かっと照って来て」）。
- 16:30 の太陽は 273°、高度 29°。泉からプラタナスを見ると 293° で、太陽との差は約 20° しかなく、太陽はちょうど樹冠の中ほどから下の裏にある：**葉が背後から透けて照らされ、「葉も枝も燃えるばかりに」**。このとき泉も木陰に入り、メロスが水を飲むとき体にはまだらな光が落ちる。

### 3.2 Spots / スポット

| Name / 名前 | Position / 位置 | Facing / 向き | Use / 用途 |
|---|---|---|---|
| `road-spring` | (−12, −4) | +x | **Landing spot**. Behind it, (−21, −4) is the default camera, with only road (the plane trees are behind on the left, outside the portrait field of view) / **着地点**。背後の (−21, −4) がデフォルトのカメラで、道だけがある（プラタナスは左後方で、縦画面の画角の外） |
| `melos-stagger` | (−5, −3.5) | +x | On arrival he first staggers on the road (「よろよろ二、三歩あるいて」) / 着いてまず道の上でよろめく（「よろよろ二、三歩あるいて」） |
| `melos-down` `auto: false` | (2.5, 3.8) | — | Where he collapses at 15:00: on his back, limbs sprawled, **head to the southeast, feet to the northwest**, with the thin stream from the spring 0.5 m from his feet (「すぐ足もとで」). He can't see the spring; it's beyond his head, out of his view / 15:00 にここで倒れる：仰向けで手足を投げ出し、**頭は南東、足は北西**、足もとから 0.5 m のところに泉から流れ出る細い水がある（「すぐ足もとで」）。彼には泉が見えない。泉は彼の頭の向こうで、視界の外 |
| `melos-drink` `auto: false` | (−0.2, 4.7) | +y (toward the crack) / +y（割れ目のほう） | At 16:30 he kneels by the pool and drinks from cupped hands / 16:30 に水たまりのそばにひざまずき、両手ですくって飲む |
| `player-crouch` `auto: false` | (3.3, 2.6) | North (toward his head) / 北（彼の頭のほう） | You crouch south of his head (the road side) to talk. The low camera is behind your shoulder at (3.45, 1.7), about 0.95 m high (3.3) / あなたは彼の頭の南側（道の側）にしゃがんで話す。低いカメラはあなたの肩の後ろ (3.45, 1.7)、高さ約 0.95 m（3.3） |
| `way.west` / `way.east` | (−26, −4) / (22, −4) | | |

- **The sound of the spring**: the source is in the crack, audible from the landing spot (about 16 m), very faint, getting clearer as you get closer. Melos is too exhausted to hear it, but the player can: this is the hint for 「水を汲んで渡す」, with no markers added. He has only 5 minutes before he collapses, so the button is there from the moment you arrive (section 10: arriving at the spring is 5 minutes before beat.20). Events are resolved by start time: tapping 「水を汲んで渡す」 at 14:55 can prevent beat.20 at 15:00; tapping at exactly 15:00 is too late (Data verified with worldsim; to be written as a test in M3).
  **泉の水音**：音源は割れ目で、着地点（約 16 m）から聞こえる。ごくかすかで、近づくほどはっきりする。メロスは疲れきって聞こえないが、プレイヤーには聞こえる：これが「水を汲んで渡す」のヒントで、マークは一切付けない。彼が倒れるまで 5 分しかないので、ボタンは着いた瞬間からある（10 節：泉に着くのは beat.20 の 5 分前）。イベントは開始時刻で清算する：14:55 に「水を汲んで渡す」をタップすれば 15:00 の beat.20 を防げるが、15:00 ちょうどにタップしたのでは遅い（データが worldsim で確認、M3 でテストにする）。

### 3.3 Camera / カメラ

- Landing: facing east, Melos staggering on the road ahead, the grassland and rock to the right, the spring hidden by grass and barely visible, the sound of water ahead on the left.
  着地：東向きで、前方の道でメロスがよろめき、右側に草地と岩、泉は草に隠れてほとんど見えず、水音は左前方から聞こえる。
- **Dialogue needs a low camera**: Melos lies in the grass or half sits propped on an elbow, and you crouch beside him. The over-the-shoulder shot becomes one looking down at his face from behind your shoulder, with the face still taking up 12〜15% (art-direction 5.2). Frontend 15:54Z: made as a variant of the over-the-shoulder shot, with the camera behind your shoulder once you've crouched, about 0.9〜1.0 m high, looking down 25〜35° at his face, with the field of view computed automatically from the face's share of screen height.
  **会話には低いカメラが必要**：メロスは草の中に横たわるか、肘をついて半ば起き上がり、あなたはそのそばにしゃがむ。肩越しのショットは、あなたの肩の後ろから彼の顔を見下ろすものに変え、顔は引き続き画面の 12〜15% を占める（art-direction 5.2）。フロントエンド 15:54Z：肩越しのショットの変種として作り、カメラはしゃがんだあなたの肩の後ろ、高さ約 0.9〜1.0 m で、25〜35° 下に彼の顔を見る。画角は顔が画面の高さに占める割合から自動で計算する。
  - **You crouch south of his head** (`player-crouch`), with the camera facing north: at 15:00 the sun is at 258°, behind the camera on the left, and his face is in 3/4 side light; your shadow falls east and doesn't cover his face (crouching west or southwest of him would put your shadow right on his face). At 16:30 the sun is at 273°, and it doesn't block either. The spring and the plane trees are deep in the upper part of the frame.
    **あなたは彼の頭の南側にしゃがみ**（`player-crouch`）、カメラは北向き：15:00 の太陽は 258° でカメラの左後方にあり、彼の顔は 3/4 の側光になる。あなたの影は東へ落ち、彼の顔にはかからない（西や南西にしゃがむと、影がちょうど彼の顔に落ちる）。16:30 の太陽は 273° で、同じく遮らない。泉とプラタナスは画面の上部の奥にある。
  - Your crouch uses UAL's `Crouch_Idle_Loop` (CC0, already available); his lying down, half sitting on an elbow and small talking movements are dedicated animations, scheduled together with the ending ones.
    あなたのしゃがみは UAL の `Crouch_Idle_Loop`（CC0、既存）を使う。彼が横たわる、肘をついて半ば起きる、話すときの小さな動きは専用モーションで、エンディングのものと一緒に予定を組む。
  - The camera is above the thin stream, which doesn't get in the way (the water surface doesn't block the camera's collision checks); grass cards within 0.5 m of the camera must be culled, or they'll smear across the lens (Frontend 16:09Z).
    カメラは細い流れの上にあるが、邪魔にはならない（水面はカメラの衝突判定を遮らない）。カメラから 0.5 m 以内の草のカードは消す。そうしないとレンズの前にべったり映る（フロントエンド 16:09Z）。
- The beat.21 staging: camera low, facing northwest, Melos kneeling by the pool and standing up, with the sun-lit plane trees behind him. He is a backlit silhouette with a bright rim. Then he turns and runs east (R3), leaving the glowing trees behind.
  beat.21 の演出：カメラは低く北西向きで、メロスが水たまりのそばにひざまずき、立ち上がる。背後には日に透けるプラタナス。彼は逆光のシルエットで、縁に明るい光の輪がある。それから彼は向きを変えて東へ走り（R3）、光る木を背後に残す。
- In runs that took the side path (15:30): he doesn't collapse; on arrival he kneels straight down by the pool to drink and leaves when done, with no conversation lying in the grass. Data says that in M3 beat.21 can get a variant split on `doubted`, and the staging would split into two accordingly.
  脇道を選んだ回（15:30）：彼は倒れず、着くとすぐ水たまりのそばにひざまずいて飲み、飲み終えたら去る。横たわっての会話はない。データによれば、M3 で beat.21 に `doubted` で分かれる変種を加えられ、演出もそれに合わせて 2 通りに分かれる。

### 3.4 Light (one set) / 光（1 セット）

- Bake time 15:45 (the sun keeps moving during the 15:00〜16:30 that people are here, so the real-time sun is primary, and only skylight and occlusion are baked).
  ベイクの時刻は 15:45（人がここにいる 15:00〜16:30 の間、太陽は動き続けるので、リアルタイムの太陽を主にし、ベイクするのは天空光と遮蔽だけ）。
- 15:00: the blazing afternoon heat, slightly lower and yellower than at the pass; the grassland looks bleached.
  15:00：午後の灼熱で、峠より少し低く、少し黄色い。草地は白っぽい。
- 16:30: the start of evening, warm (art-direction 3.2, heading down from about 4000K).
  16:30：夕方の始まりで暖かい（art-direction 3.2、約 4000K から下がっていく）。
- Side-path runs at 15:30: the sun is still high (about 41°), with no 「斜陽」; use the real-time sun, no extra bake. The original says 「斜陽は赤い光」: this moment can be graded a little warmer than physical, but not truly red; true red is saved for the field road after 18:30.
  脇道の回の 15:30：太陽はまだ高く（約 41°）、「斜陽」はない。リアルタイムの太陽を使い、別にベイクしない。原作は「斜陽は赤い光」と書く：この瞬間は物理的な値より少し暖かく調整してよいが、本当の赤にはしない。本当の赤は 18:30 以降の野の道に取っておく。

### 3.5 Materials / 素材

| Material / 素材 | Key points / 要点 |
|---|---|
| Grassland / 草地 | **The largest close-up area at this stop**: dry yellow grass, seed heads, yellow, white and purple wildflowers; green on both sides of the trickle / **この地点で面積が最も大きい近景**：乾いた黄色の草、穂、黄・白・紫の野の花。細い流れの両側は緑 |
| Wet rock, moss, maidenhair fern / 濡れた岩、苔、ホウライシダ | Around the crack the rock is wet and one shade darker, with moss and maidenhair fern (*Adiantum capillus-veneris*, the most common fern on dripping limestone in Sicily; it makes this spring look real at a glance) / 割れ目のまわりは濡れて一段濃く、苔とホウライシダ（*Adiantum capillus-veneris*、シチリアの水の滴る石灰岩で最もよく見るシダで、この泉をひと目で本物らしくする）が生えている |
| Clear water / 清水 | Transparent, with the stones on the bottom of the pool visible, and a ring of small upwelling at the mouth of the crack. Built differently from the river water / 透明で、水たまりの底の石が見え、割れ目の口に小さな湧き上がりの輪がある。川の水とは別のやり方で作る |
| Plane trees / プラタナス | Mottled bark; the leaves must let light through (glowing when backlit), on tier B too / まだらな樹皮。葉は光を透す必要がある（逆光で光る）。ティア B でも |

---

## 4. The field road to the city (all running) / 市へ続く野の道（全区間を走る）

`scene.road-field`. Frontend's "treadmill" technique: the characters run in place and the road surface scrolls backward tile by tile (Frontend estimate item 3).

`scene.road-field`。フロントエンドの「ランニングマシン」方式：人はその場で走り、路面が 1 枚ずつ後ろへ巻き取られていく（フロントエンドの見積もり第 3 項）。

| Item / 項目 | Content / 内容 |
|---|---|
| Time / 時刻 | Continues from R3 at about 17:20; running all the way to the city gate (about 18:55), then switching to the plaza (beat.24 19:00) / 約 17:20 に R3 から続く。城門まで走り続け（約 18:55）、広場に切り替わる（beat.24 19:00） |
| Who is there / 誰がいるか | Melos (stage 4 = the ending version after 17:30), you; at 17:30 passers-by on the road, the drinking party in the field and a dog; about 17:45 a group of travelers; from 18:30 フィロストラトス / メロス（17:30 以降は第 4 段階 = エンディング版）、あなた。17:30 に道行く人、野の酒宴の人々と犬。約 17:45 に旅人の一団。18:30 からフィロストラトス |
| Direction / 方向 | +x = 114°, the same direction as the plaza's gate avenue (art-direction 4.1). The sun is directly behind, **so the two runners' shadows keep running ahead of them**, getting longer and longer: 5 times body height at 18:00, 10 times at 18:30, 20 times at 18:45. This is the same image as ending shot 2, "his shadow a step ahead of him", carried all the way into the city gate / +x = 114° で、広場の城門通りの方向（art-direction 4.1）。太陽は真後ろにあり、**二人の影はずっと二人の前を走り**、どんどん長くなる：18:00 に身長の 5 倍、18:30 に 10 倍、18:45 に 20 倍。これはエンディングのショット 2「影が彼より一歩先に」と同じ画面で、そのまま城門までつながる |
| Talking / 話せること | About 6 lines (15 minutes each); the last 2 can be with フィロストラトス. When idle, 「走り続ける」, and tapping it jumps to the next event / 約 6 回（1 回 15 分）、最後の 2 回はフィロストラトスと話せる。放置時は「走り続ける」で、タップすると次の出来事まで飛ぶ |

### 4.1 Road tiles (30〜40 m each, chained in rotation) / 路面（1 枚 30〜40 m、順につないでいく）

| Tile / 路面 | What it looks like / 見た目 | Used for / 使う場面 |
|---|---|---|
| F1 Road through the wheat / F1 麦畑の中の道 | A dirt road with golden wheat fields on both sides, partly cut, sheaves standing in the field; low dry-stone walls; scattered olives / 土の道の両側に金色の麦畑、一部は刈られて麦束が畑に立っている。低い空積みの石垣。ぽつぽつとオリーブ | Most of the time / ほとんどの時間 |
| F2 Field with a drinking party / F2 酒宴の野原 | A patch of grass by the road where harvesters are eating and drinking: cloths spread on the ground, amphorae, bread baskets, cups, straw hats and sickles set aside; 8〜12 people sitting and lying, one dog. **The party has spilled onto the road**, and Melos runs straight through the middle of it / 道端の草地で、麦を刈る人々が飲み食いしている：地面に布を広げ、アンフォラ、パンの籠、杯、麦わら帽子と鎌は脇に置いてある。8〜12 人が座ったり寝そべったりし、犬が 1 匹。**酒宴は道の上まで広がっていて**、メロスはその真ん中を突っ切る | 17:30 |
| F3 Brook / F3 小川 | A brook 1.5〜2 m wide crossing the road, with a few stepping stones / 幅 1.5〜2 m の小川が道を横切り、飛び石がいくつかある | After the 17:30 party; Melos clears it in one leap / 17:30 の酒宴のあと、メロスがひと跳びで越える |
| F4 Crest / F4 坂の頂 | A gentle rise; at the top the view suddenly opens up ahead / ゆるやかな上り坂で、頂に着くと前方が急に開ける | About 17:50, the city towers appear for the first time / 約 17:50、塔楼が初めて現れる |
| F5 Tomb road outside the city / F5 城外の墓の道 | Tombs cut into limestone on both sides of the road, cypresses (Greek cities had their cemeteries along the roads outside the walls 〔inference; there really are ancient necropolises outside Syracuse〕) / 道の両側に石灰岩を掘った墓、イトスギ（ギリシアの都市の墓地は城外の道端にあった〔推測、シラクスの城外には実際に古代の墓地がある〕） | After about 18:45 / 約 18:45 以降 |
| F6 City gate / F6 城門 | The city wall and the west gate (using the plaza's distant geometry, Frontend estimate item 1); the gateway faces 294°, the low sun shines straight into it, and the gateway is filled with light / 城壁と西門（広場の遠景のジオメトリを使う、フロントエンドの見積もり第 1 項）。門の通路は 294° を向き、低い太陽がちょうど通路に差し込み、通路の中は一面に明るい | About 18:55, switching to the plaza / 約 18:55、広場に切り替わる |
| F1' Path through the wheat / F1' 麦畑の小径 | A path less than 1 m wide through the wheat / 幅 1 m 足らずの小径が麦畑を抜ける | Replaces a stretch of F1 when 「近道を教える」 is chosen / 「近道を教える」を選んだときに F1 の 1 区間の代わりに使う |

### 4.2 Events that appear by the clock / 時計に合わせて現れる出来事

| Scheduled / 予定 | Event / 出来事 | Picture / 画面 | Original / 原作 |
|---|---|---|---|
| 17:20 | Continues from R3 / R3 から続く | The grassland turns into wheat fields / 草原が麦畑に変わる | — |
| 17:30 (beat.22) / 17:30（beat.22） | He pushes past people on the road (two or three leading a donkey), runs through the drinking party (people jump aside, cups tip over), a dog lunges and he kicks it away (the dog rolls over and runs off; no injury shown), and he leaps the brook / 道行く人々（ロバを引く 2、3 人）を押しのけ、酒宴を突っ切り（人々は飛びのき、杯がひっくり返る）、飛びかかってきた犬を蹴とばし（犬はひと転がりして逃げ、けがは見せない）、小川を跳び越える | F1 → F2 → F3. **Melos's clothes switch to stage 4 here**: the switch happens in the dust kicked up at the party, so nobody sees the moment it changes / F1 → F2 → F3。**メロスの衣服はここで第 4 段階に替わる**：酒宴で舞い上がる土ぼこりの中で替え、替わる瞬間を見せない | 「路行く人を押しのけ、跳ねとばし…酒宴の人たちを仰天させ、犬を蹴とばし、小川を飛び越え」 |
| About 17:45 / 約 17:45 | A group of travelers (3〜4 people, coming from the city) brushes past going the other way, and he overhears 「いまごろは、あの男も、磔にかかっているよ。」 / 旅人の一団（3〜4 人、町から来る）とすれ違いざまに、「いまごろは、あの男も、磔にかかっているよ。」と聞こえる | The voice comes from them (spatial audio), with subtitles as usual / 声は彼らのほうから聞こえ（空間オーディオ）、字幕は通常どおり | 「一団の旅人と颯っとすれちがった瞬間、不吉な会話を小耳にはさんだ」 |
| About 17:50 / 約 17:50 | The crest: far ahead, the city wall and towers, the towers shining in the setting sun / 坂の頂：はるか前方に城壁と塔楼、塔楼が夕日を受けて光る | F4. The towers are tiny (about 6 km 〔inference〕) and need a little flickering highlight to read as 「きらきら」 / F4。塔楼はとても小さい（約 6 km〔推測〕）ので、少しハイライトのきらめきを加えないと「きらきら」に見えない | 「見える。はるか向うに小さく、シラクスの市の塔楼が見える。塔楼は、夕陽を受けてきらきら光っている。」 |
| 18:30 (beat.23) / 18:30（beat.23） | A man runs toward them along the road ahead, shouting 「ああ、メロス様。」, and turns to run with them. Three abreast / 前方の道を男が駆けてきて「ああ、メロス様。」と叫び、向きを変えて一緒に走る。3 人が並ぶ | A reverse shot: shooting back from in front, the three run toward the camera, **with a huge red setting sun behind them**, the three as backlit silhouettes / 切り返しのショット：前から後ろへ向けて撮り、3 人がカメラに向かって走ってくる。**背後には赤く大きい夕日**、3 人は逆光のシルエット | 「メロスは胸の張り裂ける思いで、赤く大きい夕陽ばかりを見つめていた。」 |
| About 18:45 / 約 18:45 | Tombs and cypresses, the city wall getting taller and taller / 墓とイトスギ、城壁がどんどん高くなる | F5 | — |
| About 18:55 / 約 18:55 | The city gate, its gateway filled with light, the three runners' shadows stretching into the gateway first / 城門、通路は光に満たされ、3 人の影が先に通路へ伸びる | F6 → switch to the plaza (≤ 4 seconds; the whole field road can be used to preload the plaza, Frontend estimate item 5) / F6 → 広場に切り替える（4 秒以内。野の道の全区間を広場の先読みに使える、フロントエンドの見積もり第 5 項） | 「メロスは疾風の如く刑場に突入した」 |

- The distant city is scaled by the remaining distance: about 6 km at 17:50, 2 km at 18:30, 300 m at 18:50 〔inference, just so the size matches the original's 「はるか向うに小さく」 and 「市の近く」〕. On a portrait screen a 20 m tower at 6 km is physically only about 3 px, so draw it about 3 times larger (around 8 px), returning to physical size from 2 km on (about 8 px; about 50 px at 300 m). While the tower is smaller than about 15 px, add a 2〜4 px highlight sprite on its west face that twinkles slowly: that's the 「きらきら」 (Frontend 15:54Z).
  町の遠景は残りの距離に合わせて大きさを変える：約 17:50 に 6 km、18:30 に 2 km、18:50 に 300 m〔推測。原作の「はるか向うに小さく」と「市の近く」に大きさを合わせるためだけ〕。縦画面では 6 km 先の 20 m の塔楼は物理的には約 3 px しかないので、約 3 倍（8 px 前後）に描き、2 km からは物理的な大きさに戻す（約 8 px、300 m で約 50 px）。塔楼が約 15 px より小さいあいだは、西向きの面に 2〜4 px のハイライトのスプライトを置いてゆっくりきらめかせる。これが「きらきら」（フロントエンド 15:54Z）。
- If 「先に走って知らせる」 is chosen: you run the same road alone (no Melos, your clothes unchanged), landing at the execution ground (Data `place.execution-ground`).
  「先に走って知らせる」を選んだ場合：あなたは一人で同じ道を走り（メロスはおらず、あなたの衣服は変わらない）、刑場に着地する（データの `place.execution-ground`）。
- Melos's coughing at stage 4: the original has 「口から血が噴き出た」; per art-direction 5.7 it's played as coughing with a hand over his mouth, **no blood**.
  第 4 段階のメロスの咳：原作は「口から血が噴き出た」。art-direction 5.7 に従って、咳をして手で口を押さえる演技にし、**血は出さない**。

### 4.3 Light (one set, highest bake priority) / 光（1 セット、ベイクの優先度は最高）

- Bake time 18:30 (the road tiles are reused; what's baked is the tiles' skylight and occlusion). The real-time sun moves from 280° to 294°.
  ベイクの時刻は 18:30（路面は繰り返し使うので、ベイクするのは路面の天空光と遮蔽）。リアルタイムの太陽は 280° から 294° へ動く。
- Facing forward (the default camera from behind and to the side): front-lit ahead, the wheat fields and towers golden, the two long shadows out in front.
  前向き（デフォルトの斜め後ろからのカメラ）：前方は順光で、麦畑と塔楼は金色、二人の長い影が前にある。
- Facing back (the 18:30 reverse shot): backlit, with dust and wheat awns glowing in the air (art-direction 3.2 evening, "dust glowing in the backlight"), the sun huge and red, pressing on the western hills.
  後ろ向き（18:30 の切り返し）：逆光で、空気中の土ぼこりと麦の芒が光る（art-direction 3.2 夕方「逆光の中で土埃が光る」）。太陽は赤く大きく、西の山にのしかかる。
- After 18:45 the sun is very red and the shadows are at their longest.
  18:45 以降、太陽はとても赤く、影は最も長く伸びる。

### 4.4 Materials / 素材

| Material / 素材 | Key points / 要点 |
|---|---|
| Dirt road / 土の道 | From the shared pack. Dry here, whitish, turned gold by the setting sun / 共用パックのもの。ここでは乾いていて白っぽく、夕日で金色に染まる |
| Wheat / 麦 | The most important mid-ground: golden, the awns lighting up together when backlit / 中景で最も重要：金色で、逆光では芒が一面に光る |
| Party cloths and pottery / 酒宴の布と陶器 | Cloth in natural linen with ochre or indigo stripes, **no red**; pottery shared with the plaza / 布は生成りの亜麻で、赭色か藍色の縞。**赤は使わない**。陶器は広場と共用 |
| Tombs and city wall / 墓と城壁 | The city wall uses the plaza's distant geometry; the tombs are simple faces cut into limestone / 城壁は広場の遠景のジオメトリを使う。墓は石灰岩を彫った簡単な面 |

---

## 5. Short running stretches and the act 2 night road / 短い走る区間と第二幕の夜道

All use the treadmill technique. The 3 short stretches are 15〜25 seconds, no talking in the first release, tap to skip, time cards with reduced motion ("Movement rules" item 2). The camera tracks alongside from behind and to the side of the two (ux-design 6.3).

どれもランニングマシン方式を使う。短い 3 区間は 15〜25 秒で、第 1 版では話せず、タップでスキップでき、動きを減らす設定のときは時間カードを出す（「移動のルール」第 2 項）。カメラは二人の斜め後ろから並行して追う（ux-design 6.3）。

| Stretch / 区間 | Act / 幕 | Scheduled time / 予定時刻 | Roadside / 道端 | Light / 光 | Melos / メロス |
|---|---|---|---|---|---|
| **R1 river → pass / R1 川 → 峠** | 4 | About 12:10 → 13:40 / 約 12:10 → 13:40 | "Wet slope": a dirt road climbing out of the river valley, wet after the rain, puddles drying; olive terraces, dry-stone walls, holm oaks; more and more stone the higher you go. Behind is the river valley, ahead the ridge of the pass / 「濡れた坂」：川の谷から上る土の道で、雨上がりで濡れ、水たまりが乾きかけている。オリーブの段々畑、空積みの石垣、ヒイラギガシ。上るほど石が増える。振り返ると川の谷、前には峠の稜線 | Sun 72°→62°, moving from overhead to behind on the right, extremely short shadows / 太陽 72°→62°、頭上から右後方へ移り、影はごく短い | Stage 2, soaked. Running hard (「すぐにまた先きを急いだ」) / 第 2 段階、ずぶ濡れ。猛然と走る（「すぐにまた先きを急いだ」） |
| **R2 pass → spring / R2 峠 → 泉** | 4 | About 14:05 → 14:55 / 約 14:05 → 14:55 | "Stony descent": scree, outcrops, dwarf fan palms, mastic, heat haze / 「石の下り坂」：砕石、露頭、チャボトウジュロ、マスティックの木、陽炎 | Sun 58°→48°, behind on the right, glaring, the ground bleached / 太陽 58°→48°、右後方、まぶしく、地面は白っぽい | Stage 3 (after the bandits). **His stride gets steadily worse**: running → a dragging jog → finally staggering at a walk (「幾度となく眩暈を感じ」). This stretch has to show he's about to give out, leading into the collapse at the spring / 第 3 段階（山賊と戦ったあと）。**足取りがどんどん悪くなる**：走る → 足を引きずる小走り → 最後はよろめいて歩く（「幾度となく眩暈を感じ」）。この区間で彼がもう限界だと見せ、泉で倒れる場面につなげる |
| R2' 山腹の脇道 (hillside side path) / R2' 山腹の脇道 | 4 | When 「峠を避けて、脇道を行く」 is chosen, reaching the spring about 15:30 / 「峠を避けて、脇道を行く」を選んだとき、泉に約 15:30 に着く | A goat track around the hillside, through holm oak scrub, no rock gate / 山腹を巻く羊の通る細道で、ヒイラギガシの茂みを抜け、岩門はない | Same as R2 / R2 と同じ | Stage 2, clothes already dry, stride doesn't deteriorate (Data: no fight, 45 stamina left). **Leads to the spring, not straight to R3**: beat.21 still happens in this run (section 3) / 第 2 段階、衣服はもう乾いていて、足取りは悪くならない（データ：戦わないので体力は 45 残る）。**泉につながり、直接 R3 にはつながらない**：この回でも beat.21 は通常どおり起きる（3 節） |
| **R3 spring → field road / R3 泉 → 野の道** | 4 | 16:30 → 17:20 | "Grassland": grass, olive groves, cypresses in the distance, wheat fields starting to appear / 「草原」：草地、オリーブの林、遠くのイトスギ、麦畑が見え始める | Sun 29°→19°, directly behind, shadows starting to stretch forward, warm / 太陽 29°→19°、真後ろ、影が前へ伸び始め、暖かい | Stage 3, running steadily again (「走れ！メロス」) / 第 3 段階、また力強く走る（「走れ！メロス」） |
| **N night road / N 夜道** | 2 | 02:45 → 05:10 | Uses the R3, R2 and R1 tiles **in reverse** (heading west), with R1 switched to the dry material parameters (it hasn't rained yet in act 2) / R3、R2、R1 の路面を**逆向きに**使い（西へ向かう）、R1 は乾いた素材パラメータに替える（第二幕ではまだ雨が降っていない） | See below / 下記参照 | Act 1 clothes, carrying his bundle. The two walk briskly (Frontend estimate item 3: adapted from walking, about half a day) / 第一幕の衣服、荷物を持つ。二人は早足で歩く（フロントエンドの見積もり第 3 項：歩きを改造、約半日） |

### 5.1 The act 2 night road (talking allowed, 10 minutes per line) / 第二幕の夜道（話せる、1 回 10 分）

| Scheduled / 予定 | Tile / 路面 | Picture / 画面 |
|---|---|---|
| From 02:45 / 02:45 から | Grassland + the first tile, which has the spring / 草原＋泉のある最初の路面 | Act 2 opens in darkness: first you hear the spring, then see the silhouettes of three plane trees and a rock under the stars. This tile uses trees and rocks from the shared pack and **doesn't download the spring package** / 第二幕は始まると真っ暗で、まず泉の水音が聞こえ、それから星空の下にプラタナス 3 本と岩のシルエットが見える。この路面は共用パックの木と岩を使い、**泉のパッケージはダウンロードしない** |
| About 03:30 / 約 03:30 | Stony road (in reverse: climbing west, then down) / 石の道（逆向き：西へ上り、また下る） | At the top, the two stones of the rock gate stand against the stars. The Milky Way lies low on the left (south), the Summer Triangle overhead. It's the same place as the act 4 pass: tonight nobody is hiding there. The rock gate is in the pass package, not in the R2 tiles, so add a night-only "pass summit" tile: low-poly silhouettes of the two rocks plus a scree road, without downloading the pass package (Frontend 15:54Z, same approach as the first tile with the spring) / 頂上に着くと、岩門の 2 つの岩が星空を背にしている。天の川は左手（南）に低くかかり、夏の大三角は頭上。第四幕の峠と同じ場所だが、この夜はそこに誰も隠れていない。岩門は峠のパッケージにあって R2 の路面にはないので、夜専用の「峠の頂」の路面を 1 枚足す：2 つの岩のローポリのシルエットと砕石の道で、峠のパッケージはダウンロードしない（フロントエンド 15:54Z、泉のある最初の路面と同じやり方） |
| About 04:30 / 約 04:30 | Stony road → wet slope (dry) / 石の道 → 濡れた坂（乾いている） | The sky behind (to the east) starts to whiten, and the road ahead is the first to show its color / 背後（東）の空が白み始め、前方の道から先に色が見えてくる |
| About 04:50〜05:10 / 約 04:50〜05:10 | Down into the river valley / 川の谷へ下る | The sky ahead in the west: the dark blue Earth's shadow on the horizon with a pink band above it (1.5). Connects to the river's `road-east` / 前方の西の空：地平線に暗い青の地球影、その上にピンクの帯（1.5）。川の `road-east` につながる |

- Night lighting follows art-direction 3.2's day-for-night: bluish, desaturated, exposure not pushed too low, faces and road clearly visible. **No moon and no lamps** (they carry no lamp from act 1 to act 2; the lamp lent by the groom comes after act 3).
  夜の光は art-direction 3.2 のデイ・フォー・ナイト：青寄りで彩度を下げ、露出は下げすぎず、顔と道がはっきり見える。**月もランプもない**（第一幕から第二幕の間、彼らはランプを持っていない。花婿が貸すランプは第三幕以降のこと）。
- When idle, 「歩き続ける」, and tapping it jumps to the next event ("Movement rules" item 5).
  放置時は「歩き続ける」で、タップすると次の出来事まで飛ぶ（「移動のルール」第 5 項）。

---

## 6. How Melos looks on the road / 道中のメロスの姿

The style guide `docs/ux/style-guide/characters/melos.md` says "in act 4 his clothes get more ragged step by step along the road, and the homeward road's scene design decides how many stages". Set at four stages:

スタイルガイド `docs/ux/style-guide/characters/melos.md` は「第四幕の道中で衣服は少しずつ破れていき、何段階に分けるかは帰り道のシーン設計が決める」としている。4 段階に決める：

| Stage / 段階 | From where to where / どこからどこまで | Compared with act 1 / 第一幕との比較 |
|---|---|---|
| 1 | All of act 2; act 4 up to the river, before the crossing / 第二幕の全体。第四幕の川まで、渡る前 | The act 1 look. With the bundle in act 2, without it in act 4 (the bundle stays in the village) / 第一幕の姿。第二幕は荷物を持ち、第四幕は持たない（荷物は村に置いてくる） |
| 2 | After swimming the 濁流 (beat.18): R1, the pass / 濁流を泳いだあと（beat.18）：R1、峠 | Wet: darker, clinging, dry in about an hour (material parameter, no texture swap). A tear in the hem. **River mud on his calves** (the same place as in the ending version) / 濡れている：色が濃く、体に張りつき、約 1 時間で乾ききる（素材のパラメータで、テクスチャは替えない）。裾に裂け目が 1 つ。**ふくらはぎに川の泥**（エンディング版と同じ位置） |
| 3 | After the bandits (beat.19): R2, the spring, R3 / 山賊と戦ったあと（beat.19）：R2、泉、R3 | On top of stage 2: the left shoulder strap has snapped and the front of the garment hangs down, exposing half his chest; grazes on the right forearm and both knees (same places as the ending version, red-brown patches, no blood drawn); dust all over / 第 2 段階に加えて：左肩の紐が切れ、前身ごろが垂れ下がって胸の半分があらわになる。右の前腕と両膝にすり傷（エンディング版と同じ位置、赤褐色の斑で、血は描かない）。全身に土ぼこり |
| 4 | After beat.22 (17:30): the field road, the execution ground / beat.22（17:30）以降：野の道、刑場 | The ending version (style guide, "Ending: bursting into the execution ground at sunset") / エンディング版（スタイルガイド「エンディング：日没に刑場へ駆け込む」） |

- Stages 1〜3 are one model (Frontend 15:54Z, about 0.2〜0.3 MB more): wetness is a material parameter plus a clinging blendshape; the tear, river mud, dust and grazes are four channels of one 512 mask texture, switched on per stage; the snapped left shoulder strap exists in two copies, intact and hanging, with one shown per stage, and the hanging front uses a second blendshape; the act 2 bundle is hidden per part, with no extra draw calls. If stage 4 (the ending version) is ragged enough to need a different shape, it gets a separate model.
  第 1〜3 段階は同じモデル（フロントエンド 15:54Z、約 0.2〜0.3 MB 増）：濡れは素材のパラメータと体に張りつくブレンドシェイプ 1 つ。裂け目、川の泥、土ぼこり、すり傷は 512 のマスク画像 1 枚の 4 チャンネルで、段階に応じてオンにする。切れた左肩の紐は無事なものと垂れたものの 2 つを用意し、段階に応じてどちらか 1 つを表示する。前身ごろが垂れるのは 2 つ目のブレンドシェイプで作る。第二幕の荷物は部位ごとに隠し、draw call は増やさない。第 4 段階（エンディング版）が形を変えるほど破れているなら、別のモデルを作る。
- In runs that took the side path (R2'), stage 3 becomes "stage 2, fully dry": no fight, no grazes. But at 17:30 he still turns into stage 4 (in the original his clothes are torn by the running 〔inference〕).
  脇道（R2'）を選んだ回では、第 3 段階は「乾ききった第 2 段階」に替わる：戦っていないのですり傷はない。ただし 17:30 にはやはり第 4 段階になる（原作では衣服は走ったせいで破れる〔推測〕）。
- Dedicated animations on the road (Frontend estimate item 3): kneeling in prayer by the river, leaping in and swimming, grabbing the tree, 胴震い; at the pass, wresting a club and fighting; R2's deteriorating stride; at the spring, collapsing, lying down, talking while half sitting on an elbow, drinking from cupped hands, standing up; on the field road, kicking the dog away, leaping the brook, coughing. Scheduled together with the dedicated ending animations.
  道中の専用モーション（フロントエンドの見積もり第 3 項）：川辺でひざまずいて祈る、飛び込んで泳ぐ、木にしがみつく、胴震い。峠で棍棒を奪って打つ。R2 で足取りが悪くなる。泉で倒れる、横たわる、肘をついて半ば起きて話す、両手ですくって飲む、立ち上がる。野の道で犬を蹴とばす、小川を跳ぶ、咳をする。エンディングの専用モーションと一緒に予定を組む。

## 7. Other people on the road / 道中のほかの人々

| Who / 誰 | Where / 場所 | Detail level / 精度 |
|---|---|---|
| 5 bandits / 山賊 5 人 | Pass / 峠 | Walk-around grade, faces covered with cloths (2.2) / 歩行用、布で顔を覆う（2.2） |
| 2〜3 passers-by and a donkey / 道行く人 2〜3 人とロバ 1 頭 | Field road 17:30 / 野の道 17:30 | Crowd variants (shared with the plaza) / 群衆のバリエーション（広場と共用） |
| 8〜12 people at the party, a dog / 酒宴の人 8〜12 人、犬 | Field road 17:30 / 野の道 17:30 | Crowd variants with straw hats and sickles added; the dog made separately / 群衆のバリエーションに麦わら帽子と鎌を加える。犬は別に作る |
| 3〜4 travelers / 旅人 3〜4 人 | Field road, about 17:45 / 野の道、約 17:45 | Crowd variants. The one who speaks the line only needs a voice, no lip sync (they brush past; the face can't be made out) / 群衆のバリエーション。あの一言を言う人は声だけでよく、口の動きは合わせない（すれ違うだけで、顔はよく見えない） |
| フィロストラトス | Field road from 18:30 / 野の道 18:30 から | **Needs the dialogue grade** (players can talk to him). A young stonemason's apprentice; style guide to be written later; voice Rasalgethi as set in D-025 (only about 1.5 semitones from Melos; whether to switch to Enceladus depends on the blind listening results in ux-design 16.1) / **会話用が必要**（プレイヤーが彼と話せる）。若い石工の弟子で、スタイルガイドはのちに書く。声は D-025 で決めた Rasalgethi（メロスとの差は約 1 半音しかない。Enceladus に替えるかどうかは ux-design 16.1 のブラインド試聴の結果を見る） |

## 8. Five lighting sets / 5 つの光のセット

Build order and quality follow the priorities in art-direction 3.5 item 2 (sunset > afterglow and night > high noon > morning and twilight):

作る順番と精度は art-direction 3.5 第 2 項の優先順位（日没 > 残照と夜 > 真昼 > 朝と薄明）に従う：

| Priority / 優先度 | Package / パッケージ | Bake time / ベイクの時刻 | In one line / ひとことで |
|---|---|---|---|
| 1 | Field road / 野の道 | 18:30 | The sun directly behind, shadows running ahead, the towers shining; backlit dust in the reverse shot / 太陽は真後ろ、影が前を走り、塔楼が光る。切り返しでは逆光の土ぼこり |
| 2 | Spring / 泉 | 15:45 | The fully sunlit grassland at 15:00; the backlit plane trees at 16:30 / 15:00 の日差しをまともに受ける草地。16:30 の日に透けるプラタナス |
| 3 | Pass / 峠 | 14:00 | The sun-bleached rock gate with deep shadow behind it / 日に白く焼けた岩門と、その裏の深い影 |
| 3 | River · act 4 / 川・第四幕 | 11:45 | Noon, after the rain, wet, the backlit 濁流, rain clouds to the north / 正午、雨上がり、濡れた地面、逆光の濁流、北の雨雲 |
| 4 | River · act 2 / 川・第二幕 | 05:15 | Twilight, mist, the pink band in the west / 薄明、霧、西のピンクの帯 |

Running stretches all use real-time light (Frontend estimate item 1). The plaza uses the real-time sun plus baked skylight and occlusion, and so does this.

走る区間はすべてリアルタイムの光（フロントエンドの見積もり第 1 項）。広場はリアルタイムの太陽とベイクした天空光・遮蔽で、ここも同じ。

## 9. Materials swapped to 2048 on high-end devices (art-direction 9.3, 2〜4 per package) / ハイエンド機で 2048 に差し替える素材（art-direction 9.3、パッケージごとに 2〜4 種）

| Package / パッケージ | Swap to 2048 / 2048 に差し替え |
|---|---|
| Shared pack / 共用パック | Limestone dirt road, dry grassland, limestone outcrops / 石灰岩の土の道、乾いた草地、石灰岩の露頭 |
| River (shared by both packages) / 川（2 つのパッケージで共用） | Wet riverbank rock and mud; the piles of the broken bridge (act 4, close-up) / 川岸の濡れた岩と泥。落ちた橋の杭（第四幕、近景） |
| Pass / 峠 | (outcrops and dirt road are in the shared pack) Scree and stone steps / （露頭と土の道は共用パック）砕石と石段 |
| Spring / 泉 | Wet rock, moss and maidenhair fern (always in frame during dialogue); plane tree bark / 濡れた岩、苔とホウライシダ（会話中ずっと画面にある）。プラタナスの樹皮 |
| Field road / 野の道 | Wheat (mid-ground cards); the party cloths / 麦（中景のカード）。酒宴の布 |

〔UX's initial plan; once built, adjust by share of screen, same as the plaza〕

〔UX の当初案。組み上がったら画面に占める割合で調整する。広場と同じ〕

---

## 10. Agreed with Frontend, Data and Backend / フロントエンド、データ、バックエンドと決めたこと

All of these are M3 contracts and approaches, not part of the slice.

どれも M3 の契約とやり方で、スライスには入らない。

**Frontend** (10-10 15:54Z, answering the 6 points of v0.1, folded into each section): the low camera at the spring, see 3.2 and 3.3 (`player-crouch`); scaling the city towers by distance, see 4.2; the sky at the act 2 river, see 1.5; one model for Melos's stages 1〜3, see section 6; an extra "pass summit" tile on the night road, see 5.1; 9 m of clear space behind landing spots is enough (portrait: 9 m behind, 3.5 m high, 62° field of view; landscape: 7.5 m behind, 50°), and Frontend will say if the camera values change after F-2c.

**フロントエンド**（10-10 15:54Z、v0.1 の 6 点への回答、各節に反映済み）：泉の低いカメラは 3.2、3.3（`player-crouch`）。塔楼を距離に応じて拡大縮小するのは 4.2。第二幕の川の空は 1.5。メロスの第 1〜3 段階を 1 つのモデルにするのは 6 節。夜道に「峠の頂」の路面を足すのは 5.1。着地点の背後に 9 m 空ければ足りる（縦画面は背後 9 m、高さ 3.5 m、画角 62°、横画面は背後 7.5 m、50°）。F-2c のあとでカメラの値が変わったらフロントエンドが知らせる。

**Arrival times** (Data 10-10 12:01Z): Data puts the numbers in the world model, and worldsim computes them.

**到着時刻**（データ 10-10 12:01Z）：データが世界モデルに数値を入れ、worldsim が計算する。

- Act 4: each beat on the road gets an optional field "how many minutes early Melos arrives": pass 20, spring 5, field road 10. The river already has it: `exit.3.road` lands at 11:20, 40 minutes before beat.18. worldsim subtracts this from the run's scheduled time, so delays and advances move it too. Act 4 isn't derived from `adjacent` (those are walking minutes, and he's running).
  第四幕：道中の各ビートに任意のフィールド「メロスが何分早く着くか」を加える：峠 20、泉 5、野の道 10。川はすでにある：`exit.3.road` は 11:20 に着地し、beat.18 の 40 分前。worldsim はその回の予定時刻からこの数を引くので、遅れや早まりにも一緒に動く。第四幕は `adjacent` から逆算しない（それは歩く分数で、彼は走っている）。
- Act 2 is derived from `adjacent` starting at 02:45: pass 03:30, river 05:10.
  第二幕は 02:45 から `adjacent` で順に計算する：峠 03:30、川 05:10。
- At present the world model only moves Melos to the spring at beat.20 (15:00), so at 14:55 he isn't at the spring and 「水を汲んで渡す」 can't appear; adding "arrives at the spring 5 minutes before beat.20" leaves enough time. Events are resolved by start time: tapping at 14:55 can prevent beat.20 at 15:00, and tapping at exactly 15:00 is too late (Data verified with worldsim; to be written as a test in M3).
  現状の世界モデルではメロスは beat.20（15:00）になってから泉に移るので、14:55 には泉におらず、「水を汲んで渡す」が出ない。「泉に beat.20 の 5 分前に着く」を加えれば間に合う。イベントは開始時刻で清算する：14:55 にタップすれば 15:00 の beat.20 を防げるが、15:00 ちょうどにタップしたのでは遅い（データが worldsim で確認、M3 でテストにする）。

**Leaving a stop** (Backend 10-10 15:18Z): the four stops aren't connected on the ground, so leaving only goes through "decide first, then stage" actions, not `move`; the existing kinds are enough.

**停留地点を離れる**（バックエンド 10-10 15:18Z）：4 つの地点の間は地面でつながっていないので、離れるときは「先に判定してから演じる」アクションだけを使い、`move` は使わない。既存の kind で足りる。

- 「メロスを追う」 = `follow`, target `char.melos`. The server decides and commits once: the clock jumps to his arrival time at the next stop, the player and Melos move to that stop together, and system events due in between resolve as usual; `action_result.minutes` is the minutes skipped. Per api-contract 3.8 the server pushes `commit` first and `action_result` right after, so the two arrive almost together. After receiving `action_result`, the frontend plays the running stretch with the sun moving from the old time to the new one; it holds the `commit` back and applies it, switching to the next stop, once the stretch has played or been skipped (Frontend review #43).
  「メロスを追う」= `follow`、target は `char.melos`。サーバーが判定して 1 回でコミットする：時計は彼の次の地点への到着時刻へ飛び、プレイヤーとメロスは一緒にその地点へ移り、途中で時刻になったシステムイベントは通常どおり清算する。`action_result.minutes` は飛ばした分数。サーバーは api-contract 3.8 に従ってまず `commit` を送り、すぐ続けて `action_result` を送るので、2 つはほぼ同時に届く。フロントエンドは `action_result` を受け取ったら走る区間を演じ、太陽は古い時刻から新しい時刻へ動く。その `commit` はいったん保留し、区間を演じ終えるかスキップされたら適用して、次の地点に切り替える（フロントエンドのレビュー #43）。
- 「ひとりで先へ行く」 = `go`, target the next stop (or that exit's interactable); minutes are walking time per `Place.adjacent`, and the distance on the button is `estimatedMinutes`. After that you're no longer a companion.
  「ひとりで先へ行く」= `go`、target は次の地点（またはその出口の interactable）。分数は `Place.adjacent` による歩きの時間で、ボタンの道のりは `estimatedMinutes`。そのあとは同行者ではなくなる。
- 「走り続ける」 on the field road = `wait`, jumping to the next event due in this place.
  野の道の「走り続ける」= `wait`、この場所で次に時刻になる出来事まで飛ぶ。
- On the server, a running stretch is already the world after arrival; the stretch is only frontend staging, the talk key is off while it plays, and the server has no special rules for it.
  サーバーでは、走る区間はすでに到着後の世界であり、区間はフロントエンドの演出にすぎない。演じている間は話すキーを無効にし、サーバーは特別なルールを作らない。

**Whether Melos takes the player along when he sets off** (UX, Data and Backend agreed on 10-10):

**メロスが動き出すときにプレイヤーを連れて行くか**（UX、データ、バックエンドが 10-10 に決定）：

- While the two are walking or running together (the act 2 night road, the act 4 field road), talking pushes the clock, and when Melos relocates the player moves with him in the same system event.
  二人が一緒に歩いたり走ったりしているとき（第二幕の夜道、第四幕の野の道）、話すと時計が進み、メロスが relocate するとプレイヤーも同じシステムイベントで一緒に移る。
- At a stop, when he sets off on schedule he doesn't take the player; the server just puts 「メロスを追う」 into the actions (not written as a world-model Affordance). Tapping it, or walking out of the stop in his direction, both count as following: the player moves to wherever he is, at the time he got there, with no separate travel time.
  停留地点では、彼は予定どおり動き出してもプレイヤーを連れて行かない。サーバーが「メロスを追う」を actions に入れるだけ（世界モデルの Affordance としては書かない）。それをタップしても、彼の方向へ停留地点の外に歩き出しても、ついて行ったことになる：プレイヤーは彼のいる場所へ移り、時刻は彼がそこに着いた時刻で、道のりは別に計算しない。
- Stops are written as data, per act: `Act.stops?: string[]` (place IDs; Data 10-10 16:06Z). act.2 is [`place.river`], act.4 is [`place.river`, `place.mountain-pass`, `place.spring`]; acts without it have no stops. The spring and the pass are places passed through on the act 2 night road, so this can't hang on Place. The validation tool checks that the places in stops exist and are reachable in that act.
  停留地点はデータとして幕ごとに書く：`Act.stops?: string[]`（場所 ID。データ 10-10 16:06Z）。act.2 は [`place.river`]、act.4 は [`place.river`, `place.mountain-pass`, `place.spring`]、書いていない幕には停留地点がない。泉と峠は第二幕では夜道で通り過ぎる場所なので、Place に付けることはできない。検証ツールは stops の場所が存在し、その幕で到達できるかを確認する。
- If, after he has set off, the player first does something else that takes time (talking, an action, waiting), they haven't followed: in the same commit, `set var.player.companionOf = none`, and from then on they travel on their own by `adjacent` and `travelMinutes`, and he may already have left by the time they get there. If it isn't cleared, his next relocate would drag the player away from the stop.
  彼が動き出したあと、プレイヤーが先に時間のかかる別のこと（話す、アクション、待つ）をしたら、ついて行かなかったことになる：同じコミットで `set var.player.companionOf = none` とし、以後は `adjacent` と `travelMinutes` で自分で移動する。着いたときには彼はもう去っているかもしれない。これを消しておかないと、彼の次の relocate でプレイヤーが停留地点から引きずられてしまう。

**Other** (Data 10-10 12:01Z, 15:41Z):

**その他**（データ 10-10 12:01Z、15:41Z）：

- 「峠を避けて、脇道を行く」 stays at the pass: arriving at the pass there are still 20 minutes before beat.19, enough for one 15-minute action or one line.
  「峠を避けて、脇道を行く」は峠に置く：峠に着いた時点で beat.19 までまだ 20 分あり、15 分のアクション 1 つか 1 回の発話に足りる。
- In runs that took the side path, beat.19 and beat.20 don't happen, and beat.21 happens as usual at 15:30: Melos stops at the spring, only drinks, doesn't collapse, and doesn't doubt (section 3, section 5 R2'). If the spring staging needs to split in two, Data adds a variant of beat.21 split on `var.melos.doubted`.
  脇道を選んだ回では beat.19、beat.20 は起きず、beat.21 は 15:30 に通常どおり起きる：メロスは泉で止まり、水を飲むだけで倒れず、疑いも抱かない（3 節、5 節 R2'）。泉の演出を 2 通りに分ける必要があれば、データが beat.21 に `var.melos.doubted` で分かれる変種を加える。
- The end of act 2: tapping 「メロスを追う」 after crossing the river bridge = the clock jumps to beat.08 (about 10:00), act 2 ends, and only `exit.2.village` holds. The narration line about 隣村 goes into the jump.
  第二幕の終わり：川の橋を渡ってから「メロスを追う」をタップする = 時計は beat.08（約 10:00）へ飛び、第二幕は終わり、`exit.2.village` だけが成立する。隣村についてのナレーションはこの移動の中に入れる。
- Talking on the act 2 night road only moves the clock, and Melos's position follows the clock; `pacingNote` is extended to act 2.
  第二幕の夜道で話しても時計が進むだけで、メロスの位置は時計に従う。`pacingNote` を第二幕にも広げる。
- The shallows, the side path and the spring are all affordances (`aff.river-shallows`, `aff.pass-detour` / `aff.pass-detour-told`, `aff.spring-water`, 15 minutes each), not `objects` (which are only for 0-minute 「調べる」). When a button needs to be anchored to a specific position, Data adds an optional spot field to Affordance; where the player stands afterwards uses `playerSpot`.
  浅瀬、脇道、泉はどれも affordance（`aff.river-shallows`、`aff.pass-detour` / `aff.pass-detour-told`、`aff.spring-water`、各 15 分）で、`objects`（0 分の「調べる」専用）は使わない。ボタンを特定の位置に付ける必要があるときは、データが Affordance に任意のスポットのフィールドを加える。終わったあとプレイヤーがどこに立つかは `playerSpot` を使う。
- Melos washing his face at the river in act 2 is staging at the `melos-wash` spot, not a beat and not an activity (the contract's activities are only idle, walk, run, talk, work, sleep, absent).
  第二幕でメロスが川辺で顔を洗うのは `melos-wash` のスポットでの演出で、ビートでも activity でもない（契約の activity は idle、walk、run、talk、work、sleep、absent だけ）。
- The passers-by on the field road use the existing `char.travelers` (who can't talk); the party-goers and the dog exist only in the staging. The travelers' line 「いまごろは、あの男も、磔にかかっているよ」 is written as a set piece on beat.22 (contract 2.11, spoken by `char.travelers`).
  野の道の道行く人は既存の `char.travelers`（話せない）を使い、酒宴の人々と犬は演出の中にだけいる。旅人のあの一言「いまごろは、あの男も、磔にかかっているよ」は beat.22 の固定演出として書く（契約 2.11、話すのは `char.travelers`）。
- In act 4 the river can only be crossed by swimming (`swimMinutes` 30), and Data writes "no boats after `var.bridge = destroyed`" as data.
  第四幕では川は泳いでしか渡れない（`swimMinutes` 30）。データは「`var.bridge = destroyed` 以降は舟に乗れない」をデータとして書く。
- The 「とても渡れそうにない」 line at the river (Frontend review #43): the navmesh doesn't include water, the player can't walk into it, and the frontend doesn't produce this line on its own. To be settled in M3 with Data: UX leans toward placing an inspectable object at the water's edge (contract 2.12 `objects`, 「調べる」 0 minutes) with a set piece (2.11) that says this line; the text is fixed and not left to the narrator.
  川辺の「とても渡れそうにない」（フロントエンドのレビュー #43）：ナビメッシュは水面を含まず、プレイヤーは水に入れないが、この 1 行をフロントエンドが自分で出すことはしない。M3 でデータと決める：UX は水辺に調べられるもの（契約 2.12 の `objects`、「調べる」0 分）を置き、この 1 行を言う固定演出（2.11）を付ける案に傾いている。文言は固定で、ナレーターには任せない。

---

## Revision history / 改訂履歴

- v1.0 (2026-10-10): first version. Merged from two UX drafts in the project folder: "How the homeward road works" v1.0 (PM decided to build it as stops plus running stretches, S-081) and "The four stops and the running stretches" v0.1 (reviewed by Frontend and Data, answers folded in). Three additions per Frontend's review of #43: the running stretch plays after `action_result` arrives, holding back `commit` (section 10); when skipping before loading has finished, show a time card first ("Movement rules" item 2); the riverside line is sent by the server ("Movement rules" item 1, 1.3, section 10).
  v1.0（2026-10-10）：最初の版。プロジェクトフォルダにある UX の 2 つの原稿を合わせた：「帰り道の進み方」v1.0（PM が停留地点と走る区間で作ると決定、S-081）と「4 つの停留地点と走る区間」v0.1（フロントエンドとデータが確認し、回答を反映済み）。フロントエンドの #43 へのレビューに沿って 3 か所を補足：走る区間は `action_result` を受け取ってから演じ、`commit` を保留する（10 節）。スキップしたときに読み込みが終わっていなければまず時間カードを出す（「移動のルール」第 2 項）。川辺の 1 行はサーバーが送る（「移動のルール」第 1 項、1.3、10 節）。
