# Village: plan, light, materials v1.0 / 村：平面、光、素材 v1.0

| Item / 項目 | Content / 内容 |
|---|---|
| Purpose / 用途 | For the second frontend thread to follow when building the village (D-026: design first). Same as the plaza and the homeward road: UX sets the requirements and positions, Frontend writes `layout.json`, checks against the real-time sun, and tells UX about any changes / 2 つ目のフロントエンドスレッドが村を作るときに、これに沿って組む（D-026 でまず設計）。広場や帰り道と同じ：UX が要件と位置を決め、フロントエンドが `layout.json` を書き、リアルタイムの太陽で確認し、変えたら UX に伝える |
| Basis / 根拠 | Data's world model 1.0.0-draft: `scene.village`, `place.village` / `place.melos-home` / `place.groom-house`, beat.08〜14, the act 3 affordances, `role.shepherd-boy` (starts at the village field edge at 一日目 09:00), `exit.2.village` (those who walk the night road with Melos arrive at 一日目 10:00); art-direction v1.4 (3.1, 3.2, 4.2 village, 4.3, 6); ux-design 4.1 (the cut point for the shepherd boy's free prologue), 5.1; paragraphs 27〜37 of the original / データの世界モデル 1.0.0-draft の `scene.village`、`place.village` / `place.melos-home` / `place.groom-house`、beat.08〜14、第三幕の affordance、`role.shepherd-boy`（一日目 09:00 に村の畑の端から始まる）、`exit.2.village`（メロスと夜道を歩いた人は一日目 10:00 に着く）。art-direction v1.4（3.1、3.2、4.2 村、4.3、6）。ux-design 4.1（牧童の無料プロローグの区切り）、5.1。原作の第 27〜37 段落 |
| Plan / 平面図 | [village/plan.svg](village/plan.svg) |
| Status / 状態 | v1.0 (2026-10-10). Frontend and Data reviewed v0.1, and their answers have been folded into each section (the last section records what was agreed) / v1.0（2026-10-10）。フロントエンドとデータが v0.1 を確認し、回答は各節に反映済み（最後の節が決定事項） |

**This is the shepherd boy's first screen.** The shepherd boy starts in the village (`startPlace` of `role.shepherd-boy`), so the village package must meet the first-entry budget (≤ 10 MB, ≤ 10 seconds, the same rule as the plaza); it can't be treated as a scene "downloaded only in act 3".

**ここは牧童の最初の画面。** 牧童は村から始まる（`role.shepherd-boy` の `startPlace`）ので、村のパッケージは初回入場の予算（≤ 10 MB、≤ 10 秒、広場と同じルール）に収める必要があり、「第三幕で初めてダウンロードする」シーンとして扱えない。

Frontend estimated at 15:57Z (`frontend/estimates/village-castle-answers.md`, 〔estimate〕, using the plaza's measurements as the yardstick): **it fits**. The first entry downloads only the first screen's lighting set (clear daytime); the scene is about 4.5〜5.5 MB, under 10 MB with characters and code; the interior is a separate package, downloaded in the background right after the first screen (Melos goes in to sleep at 一日目 10:30 and the player can follow him; Frontend #44 review), and the other three exterior lighting sets also download in the background. If it really doesn't fit, cut in this order: ① the two neighbors' houses as silhouettes only, ② only the nearest two rows of the vineyard, ③ distant wheat fields replaced with backdrop cards, ④ sheep reduced to 10. Wheat, vines, sheep and sheaves are all instanced; draw call target ≤ 50.

フロントエンドが 15:57Z に見積もった（`frontend/estimates/village-castle-answers.md`、〔推算〕、広場の実測を物差しにした）：**収まる**。初回入場では最初の画面の光のセット（晴れた昼）だけをダウンロードし、シーンは約 4.5〜5.5 MB、人物とプログラムを加えても 10 MB 以内。屋内は別のパッケージにし、最初の画面のあとすぐバックグラウンドでダウンロードする（一日目 10:30 にメロスは家に入って眠り、プレイヤーはついて入れる。フロントエンド #44 レビュー）。屋外のほかの 3 セットの光もバックグラウンドで落とす。どうしても収まらないときは次の順に削る：① 隣家 2 軒はシルエットだけ、② ぶどう畑は手前の 2 列だけ、③ 遠くの麦畑は遠景のカードに置き換える、④ 羊を 10 頭に減らす。麦、ぶどう、羊、麦束はすべてインスタンス化し、draw call の目標は ≤ 50。

---

## 0. What this village has to stage / この村で演じること

| Scheduled time / 予定時刻 | Beat / ビート | Where / 場所 | Original / 原作 |
|---|---|---|---|
| 一日目 09:00 | The shepherd boy's start / 牧童の開始 | The field edge at the edge of the village / 村はずれのあぜ道 | — |
| 一日目 10:00 | beat.08: Melos reaches the village and tells his sister the wedding is tomorrow / beat.08 メロスが村に着き、妹に明日婚礼をすると告げる | The road at the village entrance, the pasture gate / 村の入口の道、牧場の門 | 「陽は既に高く昇って、村人たちは野に出て仕事をはじめていた。メロスの十六の妹も、きょうは兄の代りに羊群の番をしていた。よろめいて歩いて来る兄の、疲労困憊の姿を見つけて驚いた。」 |
| 一日目 10:30 | beat.09: decorates the altar, lays out the feast, collapses and sleeps until night / beat.09 祭壇を飾り、祝宴の席を整え、倒れ込んで夜まで眠る | Melos's yard, indoors / メロスの家の中庭、屋内 | 「家へ帰って神々の祭壇を飾り、祝宴の席を調え、間もなく床に倒れ伏し」 |
| 一日目 night → 二日目 04:30 / 一日目の夜 → 二日目 04:30 | beat.10: talks all night at the groom's house / beat.10 花婿の家で夜通し話す | Under the vine pergola at the groom's house / 花婿の家のぶどう棚の下 | 「葡萄の季節まで待ってくれ」「夜明けまで議論をつづけて」 |
| 二日目 12:00 | beat.11: the wedding at high noon / beat.11 真昼の婚礼 | The altar in Melos's yard / メロスの家の中庭の祭壇 | 「結婚式は、真昼に行われた。」 |
| 二日目 12:30 | beat.12: black clouds, heavy rain (the rain lasts until the next morning) / beat.12 黒雲、大雨（雨は翌朝まで続く） | The whole village / 村全体 | 「黒雲が空を覆い、ぽつりぽつり雨が降り出し、やがて車軸を流すような大雨となった。」 |
| 二日目 night 21:00 / 二日目の夜 21:00 | beat.13: the feast, and what Melos says to his sister and the groom / beat.13 祝宴、メロスが妹と花婿に語る言葉 | **Inside** Melos's house / メロスの家の**屋内** | 「狭い家の中で、むんむん蒸し暑いのも怺え、陽気に歌をうたい、手を拍った。」 |
| 二日目 late night / 二日目の深夜 | Melos crawls into the sheep shed to sleep / メロスが羊小屋にもぐり込んで眠る | Sheep shed / 羊小屋 | 「羊小屋にもぐり込んで、死んだように深く眠った。」 |
| 三日目 04:30 | beat.14: jumps up and runs out into the rain / beat.14 跳ね起きて、雨の中を走り出る | Sheep shed → the road east / 羊小屋 → 東への道 | 「雨中、矢の如く走り出た。」 |

**This act spans 43 hours**: clear morning, afternoon, sunset, starry night, twilight, high noon, the storm rolling in, rainy day, rainy night and twilight in the rain all have to work in the same scene. Light is the most expensive part of this scene (section 5).

**この幕は 43 時間にわたる**：晴れた午前、午後、日没、星空の夜、薄明、真昼、押し寄せる暴風雨、雨の昼、雨の夜、雨の中の薄明が、すべて同じシーンの中で成り立たなければならない。光がこのシーンで最も高くつく部分（5 節）。

---

## 1. Orientation and overall layout / 方角と全体

- Coordinates follow the plaza and the homeward road: meters, +x east (compass 90°), +y north, z up. The road to Syracuse leaves the village heading east (the village is 十里 west of Syracuse, art-direction 1).
  座標は広場と帰り道に合わせる：メートル、+x が東（方位 90°）、+y が北、z が上。シラクスへの道は村から東へ出ていく（村はシラクスの西十里、art-direction 1）。
- Sun: at 一日目 10:00 it is at 116° (east-southeast) and 58° high; at 12:00 due south and 72° high; at 19:00 it sets at 294°, behind the hills to the west.
  太陽：一日目 10:00 は 116°（東南東）、高度 58°。12:00 は真南、高度 72°。19:00 に 294° で西の山の向こうへ沈む。
- **The road is to the east**: Melos walks back along the road from the east (having walked west from the city all night), and on 三日目 runs out along this road into the rain.
  **東は道**：メロスは東の道を歩いて帰ってくる（一晩かけて町から西へ歩いた）。三日目にはこの道を雨の中へ走り出る。
- **The threshing floor is to the west**: a raised round stone floor at the west end of the village, with a view of the western hills and the sunset.
  **西は脱穀場**：村の西端にある一段高い円形の石の広場で、西の山と日没が見える。

```
                  North: vineyard                                Pasture (sister and sheep)
   Groom's house [vine pergola · table]    Two houses   Well
═══════════════ Village lane ══════════════════════════════ Road east (to Syracuse) ══
   Threshing floor (high, facing west)   Melos's house [yard · altar · fig] Sheep shed  Sheepfold   Field edge (shepherd boy starts)
                        [house]                                              Wheat field (harvesters)
                  South: wheat fields

                  北：ぶどう畑                     牧場（妹と羊）
   花婿の家［ぶどう棚·テーブル］     家 2 軒  井戸
═══════════════ 村の小道 ══════════════════════════════ 東への道（シラクスへ）══
   脱穀場（高所、西向き）   メロスの家［中庭·祭壇·イチジク］羊小屋 羊の囲い      あぜ道（牧童の開始）
                        ［家屋］                                  麦畑（麦を刈る人）
                  南：麦畑
```

## 2. Plan (+x = 90°, due east) / 平面（+x = 90°、真東）

| Thing / もの | Position (x, y) / 位置（x, y） | Notes / 説明 |
|---|---|---|
| Lane and road east / 小道と東への道 | (−32, 2) → (36, 2), 3 m wide, continuing further east / (−32, 2) → (36, 2)、幅 3 m、さらに東へ延びる | Dirt road, sharing the limestone dirt-road material with the homeward road. The eastern stretch has fields on both sides / 土の道で、帰り道と共用の石灰岩の土道の素材。東側の区間は両側が畑 |
| **Melos's yard / メロスの家の中庭** | Yard wall x −14〜2, y −14〜−0.5, 1.8 m high / 塀 x −14〜2、y −14〜−0.5、高さ 1.8 m | Dry-stone wall. The yard gate is in the north wall at x −7.5〜−5.5, facing the lane / 空積みの石垣。門は北の塀の x −7.5〜−5.5 にあり、小道に面する |
| House / 家屋 | x −14〜−2, y −14〜−8.5, eaves 3 m high / x −14〜−2、y −14〜−8.5、軒の高さ 3 m | Rough stone walls with earthen plaster, a single-pitch roof of old clay tiles. The door at (−8, −8.5) opens north onto the yard, with two small windows with wooden louvers. **The interior can be entered** (section 3) / 粗い石の壁に土の漆喰を塗り、古い素焼き瓦の片流れ屋根。扉は (−8, −8.5) で北の中庭へ開き、木の鎧戸の付いた小窓が 2 つ。**屋内に入れる**（3 節） |
| Altar / 祭壇 | (−6, −4.5), 1.2 × 0.8 m, 1 m high / (−6, −4.5)、1.2 × 0.8 m、高さ 1 m | A stone altar in the middle of the yard (the household altar to Zeus in a Greek family's courtyard 〔inference, common practice〕). Melos decorates it on 一日目; the wedding is held here on 二日目 / 中庭の中央の石の祭壇（ギリシア人の家の中庭でゼウスを祀る家の祭壇〔推測、よくあるやり方〕）。一日目にメロスが飾り、二日目の婚礼はここで行う |
| Fig tree / イチジクの木 | (−11.5, −3), crown radius 3 m / (−11.5, −3)、樹冠の半径 3 m | Northwest corner of the yard, summer shade / 中庭の北西の角、夏の木陰 |
| Sheep shed / 羊小屋 | Outside the east side of the yard: x 2〜7, y −14〜−10 / 中庭の東側の外：x 2〜7、y −14〜−10 | Stone walls and a thatched roof, **open on the north side** (toward the sheepfold), with hay inside. No separate interior: the inside is visible from outside / 石の壁に草葺きの屋根で、**北側は開いている**（羊の囲いのほう）。中は干し草。屋内は別に作らない：外から中が見える |
| Sheepfold / 羊の囲い | x 2〜12, y −14〜−3, dry-stone wall 1.2 m high / x 2〜12、y −14〜−3、空積みの石垣 高さ 1.2 m | Empty by day (the sheep are in the pasture), full at night. The fold gate (7, −3) faces the road. The yard's east wall has a narrow opening at (2, −11) into the sheepfold / 昼は空（羊は牧場にいる）、夜はいっぱい。囲いの門 (7, −3) は道に面する。中庭の東の塀の (2, −11) に、羊の囲いへ通じる狭い口がある |
| Pasture / 牧場 | x 6〜32, y 5〜24, enclosed by a dry-stone wall, gate at (10, 3.5) / x 6〜32、y 5〜24、空積みの石垣で囲み、門は (10, 3.5) | On the morning of 一日目 the sister grazes about 20 sheep here / 一日目の午前、妹がここで約 20 頭の羊の番をしている |
| Well / 井戸 | (4, 4.5) | Stone wellhead, wooden bucket. "Water can also be drawn at wells and springs" (ux-design 5.1) / 石の井桁、木の桶。「井戸や泉でも水を汲める」（ux-design 5.1） |
| Two houses / 家 2 軒 | A: x −12〜−4, y 5〜11; B: x −2〜4, y 7〜12 / A：x −12〜−4、y 5〜11。B：x −2〜4、y 7〜12 | Village neighbors, exterior only / 村の隣人の家で、外観だけ |
| **Groom's house / 花婿の家** | Yard wall x −32〜−18, y 5〜18, yard gate (−21, 5) / 塀 x −32〜−18、y 5〜18、門 (−21, 5) | The house is on the north side, x −32〜−20, y 13〜18 / 家屋は北側の x −32〜−20、y 13〜18 |
| Vine pergola / ぶどう棚 | x −30〜−22, y 7〜11.5, 2.4 m high / x −30〜−22、y 7〜11.5、高さ 2.4 m | Under the pergola a wooden table and two benches, the table at (−26, 9). An oil lamp on the table at night. The vines have only leaves and small green berries, **no ripe grapes** (early summer; the groom wants to wait for 「葡萄の季節」; Data 16:01Z) / 棚の下に木のテーブルと長椅子 2 脚、テーブルは (−26, 9)。夜はテーブルに油ランプが 1 つ。棚には葉と小さな青い実だけで、**熟したぶどうはない**（初夏。花婿は「葡萄の季節」まで待ちたい。データ 16:01Z） |
| Vineyard / ぶどう畑 | North of the groom's house, x −34〜−16, y 19〜26, rows running east–west / 花婿の家の北、x −34〜−16、y 19〜26、東西方向の列 | **The grapes are still small green berries**: the groom says 「葡萄の季節まで待ってくれ」, and the player can see what he is waiting for / **ぶどうはまだ小さな青い粒**：花婿は「葡萄の季節まで待ってくれ」と言い、プレイヤーは彼が何を待っているのかを目で見られる |
| **Threshing floor / 脱穀場** | Center (−26, −10), radius 5 m, about 1.5 m above the road / 中心 (−26, −10)、半径 5 m、道より約 1.5 m 高い | A round floor paved with flat stones, edged with a low stone curb. A path leads down to it from the lane at (−24, 2). Standing here and looking west you see the hills and the sunset / 平らな石を敷いた円形の広場で、低い石の縁が一周する。小道の (−24, 2) から小径が下りている。ここに立って西を見ると山と日没が見える |
| Wheat fields / 麦畑 | Southeast x 14〜36, y −26〜−3; southwest x −36〜−16, y −26〜−16 / 南東 x 14〜36、y −26〜−3。南西 x −36〜−16、y −26〜−16 | Golden, part of it cut and bound into standing sheaves. Harvesters on the morning of 一日目 / 金色で、一部は刈り取られ束にして立ててある。一日目の午前に麦を刈る人がいる |
| Distance / 遠景 | West: the ridge of the Hyblaean Mountains (sunset); east: the road to the next village running into the hills; north and south: olive terraces on the slopes / 西：イブレイ山地の稜線（日没）。東：隣村への道が丘陵へ延びる。北と南：斜面のオリーブの段々畑 | Sky shader plus a few layers of silhouettes / 空のシェーダーと数層のシルエット |

### 2.1 Place polygons (layout `places`) / 場所のポリゴン（レイアウトの `places`）

Presence is computed per place (contract 2.4.1). Data agreed at 16:01Z to one `place.melos-home` polygon plus spots, with no further subdivision:

居合わせたかどうかは場所ごとに判定する（契約 2.4.1）。データは 16:01Z に、`place.melos-home` を 1 つのポリゴンとスポットで表し、それ以上細かく分けないことに同意した：

| Place / 場所 | Polygon / ポリゴン | Includes / 含むもの |
|---|---|---|
| `place.melos-home` (メロスの家と羊小屋) / `place.melos-home`（メロスの家と羊小屋） | (−14, −14) → (12, −14) → (12, −0.5) → (32, −0.5) → (32, 24) → (6, 24) → (6, 3.5) → (−14, 3.5) | The yard, the house (interior), the sheep shed, the sheepfold, the stretch of road in front of the gate, **the pasture**. In the original, 「羊群の番をしていた……よろめいて歩いて来る兄……家へ帰って」 is all on the family's own land, so the pasture, `melos-meet`, `sister-meet` and `road-arrive` are all inside it / 中庭、家屋（屋内）、羊小屋、羊の囲い、門の前の道、**牧場**。原作の「羊群の番をしていた……よろめいて歩いて来る兄……家へ帰って」は同じ自分の家の土地なので、牧場、`melos-meet`、`sister-meet`、`road-arrive` はすべてこの中にある |
| `place.groom-house` | Yard wall x −32〜−18, y 5〜18 / 塀 x −32〜−18、y 5〜18 | The yard, the vine pergola, the house. `groom-table` and `melos-groom` are inside / 中庭、ぶどう棚、家屋。`groom-table`、`melos-groom` はこの中 |
| `place.village` | Everything else / それ以外 | Both ends of the lane, the well, the two houses, the threshing floor, the wheat fields, the vineyard. `field-edge` is here (1 m south of `melos-home`) / 小道の東西の両端、井戸、家 2 軒、脱穀場、麦畑、ぶどう畑。`field-edge` はここ（`melos-home` の南 1 m） |

- `place.melos-home` is L-shaped, not convex. The navigation pipeline only accepts convex polygons for tagging places, so Frontend splits it in the layout into three rectangles (x −14〜12, y −14〜3.5; x 12〜32, y −0.5〜24; x 6〜12, y 3.5〜24), which together form the outline above (Frontend #44 review).
  `place.melos-home` は L 字形で、凸ではない。ナビゲーションのパイプラインは場所のタグ付けに凸ポリゴンしか受け付けないので、フロントエンドはレイアウトで 3 つの長方形に分ける（x −14〜12、y −14〜3.5。x 12〜32、y −0.5〜24。x 6〜12、y 3.5〜24）。合わせると上の輪郭になる（フロントエンド #44 レビュー）。
- The shepherd boy starts at `field-edge` and has to walk onto the road or into the pasture himself to count as present for the siblings' meeting at 10:00. As on the plaza, it's the player's own choice.
  牧童は `field-edge` から始まり、自分で道か牧場まで歩いて行かないと、10:00 の兄妹の再会に居合わせたことにならない。広場と同じく、プレイヤー自身の選択。
- The altar has no beat of its own: between beat.08 (10:00) and beat.09 (10:30), Frontend plays "walks past the altar → goes inside and collapses". Data writes the beat relocates: beat.08 → `melos-meet` (sister `sister-meet`), beat.09 → `melos-sleep`, beat.10 → `melos-groom` / `groom-table`, beat.11 → `wedding-*`, beat.13 → `melos-hut`. Once Frontend has put the village layout in the repo, Data writes them by name, and the validation tool checks that each spot belongs to its place.
  祭壇には専用のビートがない：beat.08（10:00）から beat.09（10:30）の間に、フロントエンドが「祭壇のそばを通る → 家に入って倒れ込む」を演じる。ビートの relocate はデータが書く：beat.08 → `melos-meet`（妹は `sister-meet`）、beat.09 → `melos-sleep`、beat.10 → `melos-groom` / `groom-table`、beat.11 → `wedding-*`、beat.13 → `melos-hut`。フロントエンドが村のレイアウトをリポジトリに入れたら、データは名前で書き、検証ツールが各スポットがその場所に属しているかを確認する。

## 3. Interior (Melos sleeping by day, the feast on the night of 二日目) / 屋内（メロスが昼に眠る、二日目の夜の祝宴）

- The house interior is 12 × 5.5 m, about 3 m high. A hearth in the middle (−8, −11.5), a row of benches along the south wall, a loom and a few amphorae at the west end. The door and both small louvered windows are in the north wall, facing the yard.
  家の中は 12 × 5.5 m、高さ約 3 m。中央に炉 (−8, −11.5)、南の壁に沿って長椅子が並び、西の端に織機とアンフォラがいくつか。扉と鎧戸の小窓 2 つはどれも北の壁にあり、中庭に面する。
- **一日目 daytime** (beat.09, from 10:30): Melos collapses onto the straw mat at `melos-sleep` at the west end and sleeps until night, and the player can follow him in. The door faces north, so from 10:30〜16:00 the sun doesn't reach inside; the interior has only skylight through the door and windows: dark, a bright door-shaped patch on the floor by the doorway, and a cold hearth. Toward evening the sun swings to the northwest and a very low-angled ray grazes in through the doorway (real-time sun, not separately baked).
  **一日目の昼**（beat.09、10:30 から）：メロスは西の端の `melos-sleep` の藁の敷物に倒れ込んで夜まで眠り、プレイヤーはついて入れる。扉は北向きなので、10:30〜16:00 は日が差し込まず、屋内には扉と窓から入る天空光だけ：暗く、戸口の床に扉の形の明るい光があり、炉は冷えている。夕方になると太陽が北西に回り、とても低い角度の光が戸口から擦るように入ってくる（リアルタイムの太陽を使い、別にベイクしない）。
- The feast on the night of 二日目: 15〜20 villagers packed inside, low tables, cups, bread; the bride and groom sit at the east end. The door is open and it's raining outside; the light at the doorway is a cold blue-grey, the interior is warm firelight (「むんむん蒸し暑い」: the heat must show inside, with a sheen of sweat on faces and smoke in the air).
  二日目の夜の祝宴：15〜20 人の村人が中にひしめき、低いテーブル、杯、パン。新郎新婦は東の端に座る。扉は開いていて外は雨。戸口の光は冷たい青灰色で、屋内は暖かい火の光（「むんむん蒸し暑い」：屋内の暑さが見て取れるように、顔に汗の光、空気に煙）。
- **Camera**: the follow camera (9 m behind) doesn't fit inside. Indoors uses a **close follow** (decided by Frontend at 15:57Z): about 4 m behind, about 2.4 m high, field of view opened to about 70° in portrait; on hitting a wall it pulls in under the current rules, and when walking sideways it comes in as close as over-the-shoulder at most. No fixed camera positions: controls are camera-relative, so "forward" would change direction every time the camera position switched. At the feast, people standing between the camera and the player become semi-transparent (dithered transparency). Dialogue shots work as usual (pull in when blocked by a wall; when close enough to crop the face, switch to a frontal single, ux-design 6.3).
  **カメラ**：追従カメラ（背後 9 m）は屋内に収まらない。屋内では**近い追従**を使う（フロントエンドが 15:57Z に決定）：背後約 4 m、高さ約 2.4 m、縦画面の画角は約 70° に広げる。壁に当たったら今のルールどおり寄せ、横に歩くときは最も近くて肩越しまで下がる。固定カメラは使わない：操作はカメラ基準なので、カメラ位置が切り替わるたびに「前」の向きが変わってしまう。祝宴でカメラとプレイヤーの間をふさぐ人は半透明にする（ディザ透明）。会話のショットは通常どおり（壁に遮られたら寄せ、顔が切れるほど近づいたら正面の 1 人のショットに変える、ux-design 6.3）。
- So the interior has two looks: daytime skylight and the firelight of the feast, each with a small lightmap set (5.2). The interior is the only indoor space in this scene. The sheep shed is open and the night talk at the groom's house is outdoors, so no other interiors are needed.
  したがって屋内には昼の天空光と祝宴の火の光の 2 つの見た目があり、それぞれ小さなライトマップのセットを 1 つ持つ（5.2）。このシーンの屋内はここだけ。羊小屋は開いていて、花婿の家での夜の語らいは屋外なので、ほかの屋内は要らない。

## 4. Spots / スポット

| Name / 名前 | Position / 位置 | Facing / 向き | Use / 用途 |
|---|---|---|---|
| `field-edge` `auto: false` | (24, −1.5) | −x (toward the village) / −x（村のほう） | **The shepherd boy's start** (一日目 09:00, `startSpots` of `place.village`). Behind it, (33, −1.5) is the default camera, on the road / **牧童の開始**（一日目 09:00、`place.village` の `startSpots`）。背後の (33, −1.5) がデフォルトのカメラで、道の上 |
| `well-side` | (3, 5.4) | Southeast (toward the well) / 南東（井戸のほう） | By the well. **Listed in the layout as the first auto spot of `place.village`**: every other spot in this place is a player start or a staging spot, so characters with no spot written stand here / 井戸のそば。**レイアウトでは `place.village` の最初の自動で立てるスポットにする**：この場所のほかのスポットはどれもプレイヤーの開始点か演出用なので、スポットが書かれていない人物はここに立つ |
| `road-arrive` `auto: false` | (20, 2) | −x | **Arrival in the village for those who walked the night road with Melos** (`exit.2.village`, 一日目 10:00), with Melos beside them. Data will change this destination to land in `place.melos-home` (otherwise they wouldn't count as present for beat.08 and wouldn't learn about "the wedding tomorrow"), so this spot is inside the `melos-home` polygon (2.1). Also the `startSpots` of `place.melos-home` / **メロスと夜道を歩いた人の村への到着**（`exit.2.village`、一日目 10:00）、メロスがそばにいる。データはこの行き先の着地を `place.melos-home` に変える（そうしないと beat.08 に居合わせたことにならず、「明日の婚礼」を知ることができない）ので、このスポットは `melos-home` のポリゴンの中にある（2.1）。`place.melos-home` の `startSpots` でもある |
| `sister-sheep` | (16, 13) | South / 南 | The sister grazing sheep in the pasture (morning of 一日目). **Listed in the layout as the first auto spot of `melos-home`**: the sister's `initialActivity` is work, characters have no schedules, and characters with no spot written stand at the first free spot in the place (Data 16:01Z) / 妹が牧場で羊の番をしている（一日目の午前）。**レイアウトでは `melos-home` の最初の自動で立てるスポットにする**：妹の `initialActivity` は work で、人物には日程がなく、スポットが書かれていない人はその場所の最初の空いているスポットに立つ（データ 16:01Z） |
| `yard-fig` | (−10.5, −5) | East (toward the altar) / 東（祭壇のほう） | Under the fig tree in the yard. The second auto spot of `melos-home`: people who come to help and to congratulate on the daytime of 二日目 / 中庭のイチジクの木の下。`melos-home` の 2 番目の自動で立てるスポット：二日目の昼に手伝いや祝いに来た人 |
| `yard-east` | (−2.5, −3.2) | West (toward the altar) / 西（祭壇のほう） | East side of the yard, on the right as you come in through the gate. The third auto spot / 中庭の東側、門から入って右手。3 番目の自動で立てるスポット |
| `melos-meet` `auto: false` | (12.3, 3) | −x | At 一日目 10:00 Melos walks up to the pasture gate (beat.08). x is not 12: that is the seam between two of the rectangles `melos-home` is split into (Data #44 review) / 一日目 10:00 にメロスが牧場の門まで歩いてくる（beat.08）。x は 12 にしない：そこは `melos-home` を分けた長方形の継ぎ目（データ #44 レビュー） |
| `sister-meet` `auto: false` | (10.7, 3.3) | East (toward Melos) / 東（メロスのほう） | The sister sees him and runs from the pasture gate up to him (beat.08; Data writes it in the same beat) / 妹は彼を見つけ、牧場の門から彼のもとへ駆け寄る（beat.08、データがビートの中で一緒に書く） |
| `melos-altar` `auto: false` | (−6, −3.2) | South (toward the altar) / 南（祭壇のほう） | Decorating the altar on 一日目 / 一日目に祭壇を飾る |
| `melos-sleep` `auto: false` | (−11, −12.5), indoors / (−11, −12.5)、屋内 | — | Collapses on 一日目 daytime and sleeps until night / 一日目の昼に倒れ込み、夜まで眠る |
| `groom-work` | (−20, 10) | South (toward the yard gate) / 南（門のほう） | The groom working on the east side of his yard: sitting on a wooden block weaving a wattle fence for a sheepfold 〔inference, a herdsman's work〕. **Listed in the layout as the first auto spot of `place.groom-house`**: the groom starts at home (`initialActivity` work), and before beat.10 no beat writes a spot for him; when the shepherd boy comes by day to ask him (`aid.groom.agree`), he finds him here (Data #44 review) / 花婿が中庭の東側で仕事をしている：木の台に座って羊の囲いの枝の柵を編んでいる〔推測、牧人の仕事〕。**レイアウトでは `place.groom-house` の最初の自動で立てるスポットにする**：花婿は最初から家にいて（`initialActivity` work）、beat.10 より前には彼にスポットを書くビートがない。牧童が昼に頼みに来たら（`aid.groom.agree`）ここで彼を見つける（データ #44 レビュー） |
| `groom-gate` `auto: false` | (−21, 6.5) | North (toward the yard) / 北（中庭のほう） | Just inside the yard gate, the `startSpots` of `place.groom-house` (Frontend #44 review). On entering you see the groom at `groom-work`, about 3.6 m away / 門のすぐ内側で、`place.groom-house` の `startSpots`（フロントエンド #44 レビュー）。入るとすぐ `groom-work` の花婿が見え、距離は約 3.6 m |
| `groom-table` / `melos-groom` `auto: false` | (−27, 9.5) / (−24.5, 9.5) | Facing each other / 向かい合う | From the night of 一日目 to the twilight of 二日目, talking all night under the vine pergola (beat.10) / 一日目の夜から二日目の薄明まで、ぶどう棚の下で夜通し話す（beat.10） |
| `wedding-bride` / `wedding-groom` `auto: false` | (−6.8, −3.4) / (−5.2, −3.4) | South (toward the altar) / 南（祭壇のほう） | The vows at 二日目 12:00 (beat.11) / 二日目 12:00 の誓い（beat.11） |
| `wedding-melos` `auto: false` | (−6, −6) | North (standing on the other side of the altar, facing the two) / 北（祭壇の反対側に立ち、二人と向き合う） | The household is just the two siblings, so Melos is the head of the family 〔inference〕 / 家には兄妹の二人しかおらず、メロスが家長〔推測〕 |
| `feast-bride` / `feast-groom` `auto: false` | Indoors at the east end (−3.5, −12) / (−3.5, −10.5) / 屋内の東の端 (−3.5, −12) / (−3.5, −10.5) | West / 西 | In the rain on 二日目 and at the night feast (Data writes these two spots in beat.12 and beat.13). Marked `auto: false` so that people who come to help by day don't get placed into the indoor feast seats (Frontend #44 review) / 二日目の雨の中と夜の祝宴（データが beat.12、beat.13 でこの 2 つのスポットを書く）。`auto: false` にして、昼に手伝いに来た人が屋内の祝宴の席に並べられないようにする（フロントエンド #44 レビュー） |
| `melos-hut` `auto: false` | (4.5, −12.5), in the sheep shed / (4.5, −12.5)、羊小屋の中 | — | Sleeping in the hay late on the night of 二日目; whoever does 「夜明け前にメロスを起こす」 walks to here / 二日目の深夜に干し草の中で眠る。「夜明け前にメロスを起こす」人はここまで歩いてくる |
| `way.east` | (36, 2) | | The direction he runs out into the rain at 三日目 04:30 (`exit.3.road`) / 三日目 04:30 に雨の中を走り出ていく方向（`exit.3.road`） |

- **What comes first**: a character with no spot written stands at the first free auto spot of the place in the layout (Data 16:01Z), so each of the three places has one listed first: `place.village` is `well-side`, `place.melos-home` is `sister-sheep` (then `yard-fig`, `yard-east`), `place.groom-house` is `groom-work`. Player start and landing spots are all marked `auto: false` and are never assigned to characters.
  **先頭に置くもの**：スポットが書かれていない人物は、レイアウト上でその場所の最初の空いている自動で立てるスポットに立つ（データ 16:01Z）。だから 3 つの場所にはそれぞれ先頭のスポットがある：`place.village` は `well-side`、`place.melos-home` は `sister-sheep`（次に `yard-fig`、`yard-east`）、`place.groom-house` は `groom-work`。プレイヤーの開始点と着地点はすべて `auto: false` にし、人物には割り当てない。
- **Start spots** (`startSpots`; the pipeline needs one for every place): `place.village` = `field-edge`, `place.melos-home` = `road-arrive`, `place.groom-house` = `groom-gate`.
  **開始点**（`startSpots`、パイプラインはどの場所にも 1 つ必要とする）：`place.village` = `field-edge`、`place.melos-home` = `road-arrive`、`place.groom-house` = `groom-gate`。
- Clear space for the default camera: behind both `field-edge` and `road-arrive` is the road; 9 m behind `groom-gate`, (−21, −2.5) is open ground south of the lane, across the 1.8 m yard wall, with the camera above the wall; for spots in the yard (altar, wedding), 9 m back hits the yard wall, so pull in per ux-design 6.3; the yard wall is only 1.8 m high and the camera is above it, so nothing blocks the view.
  デフォルトのカメラのための空き：`field-edge` と `road-arrive` の背後はどちらも道。`groom-gate` の背後 9 m の (−21, −2.5) は小道の南の空き地で、高さ 1.8 m の塀を挟み、カメラは塀より上にある。中庭のスポット（祭壇、婚礼）は背後 9 m で塀に当たるが、ux-design 6.3 に従って寄せればよい。塀は高さ 1.8 m しかなく、カメラは塀より上にあるので遮られない。

## 5. Light / 光

### 5.1 How each time of day looks / 時間帯ごとの見た目

| Time / 時間帯 | Sky / 空 | Sun / 太陽 | Key points / 要点 |
|---|---|---|---|
| 一日目 09:00〜12:00 (start, arrival in the village) / 一日目 09:00〜12:00（開始、村に着く） | Clear, limpid blue / 晴れ、澄んだ青 | 102°→140°, altitude 47°→68° / 102°→140°、高度 47°→68° | **The shepherd boy's first screen**. Looking west at the village from `field-edge`, the sun is behind on the left: the village is front-lit, clean and easy to read; shadows fall to the front right (northwest). Harvesters, sheep, the sister / **牧童の最初の画面**。`field-edge` から西に村を見ると、太陽は左後ろ：村は順光で、すっきり読み取りやすい。影は右前（北西）に落ちる。麦を刈る人、羊、妹 |
| 一日目 afternoon / 一日目の午後 | Clear, hot / 晴れ、暑い | High, southwest / 高く、南西 | Melos sleeps indoors (only skylight from the door and windows inside, section 3). The village is quiet, people are out in the fields / メロスは屋内で眠っている（屋内は扉と窓からの天空光だけ、3 節）。村は静かで、人は畑に出ている |
| 一日目 17:30〜19:30 | Gold → orange-red → afterglow / 金色 → 橙赤色 → 残照 | 281°→294°, setting behind the western hills / 281°→294°、西の山の向こうへ沈む | Sunset seen looking west from the threshing floor; workers coming back from the fields. The same sun as the act 4 sunset on the plaza; this is the peaceful version / 脱穀場から西に日没を見る。仕事を終えた人が畑から戻ってくる。広場の第四幕の日没と同じ太陽で、ここは穏やかな版 |
| 一日目 night (20:00〜04:00) / 一日目の夜（20:00〜04:00） | Full of stars, no moon / 満天の星、月はない | — | An oil lamp under the groom's vine pergola: **the only warm light of this night**, lighting the two men's faces, with the vine leaves casting shadows from the lamp. Everywhere else is art-direction 3.2's day-for-night / 花婿の家のぶどう棚の下に油ランプが 1 つ：**この夜唯一の暖かい光**で、二人の顔を照らし、ぶどうの葉がランプの光で影を落とす。ほかの場所は art-direction 3.2 のデイ・フォー・ナイト |
| 二日目 04:00〜06:00 | Twilight / 薄明 | Sunrise 05:00 at 66° / 日の出 05:00、66° | The groom is persuaded and day breaks (beat.10, 04:30) / 花婿を説得し終え、夜が明ける（beat.10 04:30） |
| 二日目 07:00〜12:20 | Clear / 晴れ | Due south and 72° high by 12:00 / 12:00 に真南、高度 72° | Wedding preparations, the wedding at high noon: in the yard the shadows shrink under people's feet, the altar is in full sun. **The bride's dress is saffron yellow** (section 6 below), the brightest color in the frame in the noon light / 婚礼の準備、真昼の婚礼：中庭では影が足もとに縮み、祭壇は日差しをいっぱいに受ける。**花嫁の衣装はサフランの黄色**（下の 6 節）で、正午の光の中で画面で最も明るい色 |
| 二日目 12:20〜13:00 | Clear → black clouds rolling in → downpour / 晴れ → 黒雲が押し寄せる → 大雨 | Hidden by cloud / 雲に隠れる | **The weather turns in real time within the same scene**: the west (beyond the hills) darkens first, the clouds roll in, the sun is covered, the light suddenly turns flat and cold; first scattered big raindrops hit the yard's dirt (dark spots), then the 「車軸を流すような」 downpour. The crowd runs indoors / **同じシーンの中でリアルタイムに天気が変わる**：西（山の向こう）が先に暗くなり、雲が押し寄せ、太陽が隠れ、光は急に平坦で冷たくなる。まず大粒の雨がぽつぽつと中庭の土に落ち（暗い点）、それから「車軸を流すような」豪雨になる。人々は家の中へ駆け込む |
| 二日目 afternoon and night (rain) / 二日目の午後、夜（雨） | Low, heavy clouds, grey / 低く重い雲、灰色 | — | Rain streaks, puddles and running water on the ground, drips from the eaves. At night only the house's doorway and window gaps let out warm light / 雨の筋、地面の水たまりと流れる水、軒からのしずく。夜は家の戸口と窓の隙間から暖かい光が漏れるだけ |
| 三日目 03:30〜04:30 (twilight in the rain) / 三日目 03:30〜04:30（雨の中の薄明） | Grey-blue, the rain letting up a little (「雨も、いくぶん小降りに」) / 灰青色、雨は少し弱まる（「雨も、いくぶん小降りに」） | Not yet up / まだ昇っていない | Melos jumps up in the sheep shed and runs out into the rain. If the player has the lamp lent by the groom (`item.lantern`), the lamp in their hand is the only warm light (per Data's notes on aff.wake-melos). The lamp is one dynamic point light: no shadows, about 6 m range, flickering gently (Frontend 15:57Z); if tier B runs over its frame time, it falls back to a little warm fill light near the player / メロスが羊小屋で跳ね起き、雨の中へ走り出る。プレイヤーが花婿に借りたランプ（`item.lantern`）を持っていれば、手の中のランプが唯一の暖かい光（データの aff.wake-melos の説明）。ランプは動的な点光源 1 つ：影を落とさず、約 6 m を照らし、軽く揺らめく（フロントエンド 15:57Z）。ティア B でフレーム時間を超えたら、プレイヤーの近くに少し暖色の補助光を置くだけに落とす |

### 5.2 How many sets to bake / ベイクするセットの数

The real-time sun is the base (for clear periods), with baked skylight and occlusion. Following the priorities in art-direction 3.5 item 2 (sunset > afterglow and night > high noon > morning and twilight), plus the rain and interior specific to the village:

リアルタイムの太陽を土台にし（晴れの時間帯）、天空光と遮蔽をベイクする。art-direction 3.5 の第 2 項の優先順位（日没 > 残照と夜 > 真昼 > 朝と薄明）に、村ならではの雨と屋内を加える：

| Priority / 優先度 | Set / セット | Used for / 用途 |
|---|---|---|
| 1 | Before sunset (18:30) / 日没前（18:30） | 一日目 evening / 一日目の夕方 |
| 1 | Indoor feast (hearth and oil lamps, rainy night outside the door) / 屋内の祝宴（炉と油ランプ、扉の外は雨の夜） | 二日目 night / 二日目の夜 |
| 2 | Night (starry sky, one lamp at the groom's house) / 夜（星空、花婿の家にランプ 1 つ） | 一日目 night / 一日目の夜 |
| 2 | Rain (overcast daytime; rainy night and twilight in the rain use the same set dimmed) / 雨（昼の曇天。雨の夜と雨の中の薄明は同じセットを暗くして使う） | 二日目 after 12:30 / 二日目 12:30 以降 |
| 3 | Clear daytime (10:00) / 晴れた昼（10:00） | 一日目 morning (first screen), the 二日目 wedding / 一日目の午前（最初の画面）、二日目の婚礼 |
| 3 | Indoor daytime (skylight through the door and north windows) / 屋内の昼（扉と北の窓から入る天空光） | 一日目 10:30 until night, Melos sleeping inside / 一日目 10:30 から夜まで、メロスが屋内で眠る |

〔UX's initial plan: 6 sets in total, 4 outdoor and 2 small indoor ones. More than each spot on the homeward road, because one scene has to carry 43 hours. The first screen uses set 3: the low priority reflects "how often it is seen and screenshotted", not that the first screen is unimportant; the first screen gets its own check following art-direction section 10〕

〔UX の当初案は合計 6 セット：屋外 4 セット、屋内に小さいもの 2 セット。帰り道の各地点より多いのは、1 つのシーンで 43 時間を支えるため。最初の画面は 3 番目のセットを使う：優先度が低いのは「見られる回数、スクリーンショットされる回数」で並べたからで、最初の画面が重要でないわけではない。最初の画面は art-direction 第 10 節のやり方で別に確認する〕

Frontend 15:57Z: 4 outdoor sets, each about 1.5〜2 MB and about 35〜40 minutes to bake; two small indoor sets (daytime, feast), each about 0.3 MB (changed in the #44 review: the interior is needed from the morning of 一日目, not just the night of 二日目). The village downloads about 8〜9 MB in total; **the first entry downloads only the clear-daytime set** (about 5 MB, see the start of this document); the interior package downloads in the background right after the first screen, and there are still a few minutes of real time before 10:30, which is enough; the rest downloads in the background.

フロントエンド 15:57Z：屋外 4 セットで、1 セット約 1.5〜2 MB、ベイクに約 35〜40 分。屋内の小さい 2 セット（昼、祝宴）は 1 セット約 0.3 MB（#44 レビューで変更：屋内は二日目の夜だけでなく一日目の午前から使う）。村のダウンロードは合計約 8〜9 MB で、**初回入場では晴れた昼のセットだけをダウンロードする**（約 5 MB、文書の冒頭を参照）。屋内のパッケージは最初の画面のあとすぐバックグラウンドで落とす。10:30 まで実時間でまだ数分あるので間に合う。残りもバックグラウンドで落とす。

### 5.3 The real-time weather transition / 天気のリアルタイムの移り変わり

- From 12:20, for about 10 minutes (story time): clouds push in from the west, the sun's direct light falls to 0, the skylight switches to the rain set, and the color temperature moves cooler.
  12:20 から約 10 分（物語の時間）：雲が西から押し寄せ、太陽の直射光の強さが 0 まで下がり、天空光は雨のセットに切り替わり、色温度は寒色へ移る。
- Rain intensity has three levels: scattered big raindrops (dark spots appear on the ground) → heavy rain → downpour (rain streaks, splashes off the ground, strings of drips from the eaves). It stays a downpour through the night and drops one level at the twilight of 三日目. The world model's weather is one global value (`var.weather`): storm from 二日目 12:30, after-rain from 三日目 09:00; 「小降り」 has no value of its own, and Frontend eases off within storm on its own (Data 16:01Z).
  雨の強さは 3 段階：大粒の雨がぽつぽつ（地面に暗い点が出る）→ 大雨 → 豪雨（雨の筋、地面からはねる水しぶき、軒から連なって落ちるしずく）。夜までずっと豪雨で、三日目の薄明に 1 段階下げる。世界モデルの天気は全体で 1 つの値（`var.weather`）：二日目 12:30 から storm、三日目 09:00 から after-rain。「小降り」には専用の値がなく、フロントエンドが storm の中で自分で弱める（データ 16:01Z）。
- The ground gets wet: the dirt road and the yard's earth turn darker and puddles appear (the same wet material parameter as the river in act 4 on the homeward road).
  地面が濡れる：土の道と中庭の土の色が濃くなり、水たまりができる（帰り道の第四幕の川と同じ「濡れ」の素材パラメータ）。
- With reduced motion on: thinner rain streaks. **No lightning** (default, Frontend agreed): the original only mentions black clouds and heavy rain, no thunder or lightning.
  動きを減らす設定がオンのとき：雨の筋を少なくする。**稲妻は作らない**（デフォルト、フロントエンドも同意）：原作には黒雲と大雨しか書かれておらず、雷はない。
- Approach (Frontend 15:57Z): for the few seconds of the transition both the clear and rain lightmap sets are present and interpolated in the shader, then the clear set is dropped; the rain streaks are a cluster of instanced quads that follows the camera (2〜4 thousand quads, 1 draw call); dark raindrops on the ground, puddles and running water use the same "wet" parameter as the river on the homeward road; drips from the eaves use a few particles. Tier B costs about 1〜2 ms more per frame; F-2c will measure it again on real devices.
  やり方（フロントエンド 15:57Z）：移り変わりの数秒間は晴れと雨の 2 セットのライトマップを同時に持ち、シェーダーで補間し、移り終わったら外す。雨の筋はカメラについていくインスタンス化した板ポリゴンの塊（2〜4 千枚、draw call 1 回）。地面の暗い雨粒、水たまり、流れる水は帰り道の川と同じ「濡れ」のパラメータを使う。軒のしずくは少数のパーティクルで作る。ティア B では 1 フレームあたり約 1〜2 ms 増える。F-2c で実機でもう一度測る。

## 6. People and materials / 人物と素材

### 6.1 People / 人物

| Who / 誰 | Detail level / 精度 | Key points / 要点 |
|---|---|---|
| Melos / メロス | Dialogue grade / 会話用 | No bundle in act 3; for the wedding he can add a clean belt (style guide, "needed later"). His clothes get soaked when he runs out on 三日目 / 第三幕では荷物を持たない。婚礼ではきれいな帯を足してもよい（スタイルガイド「のちに必要なもの」）。三日目に走り出るとき服は雨に濡れる |
| Sister / 妹 | **Dialogue grade / 会話用** | Sixteen. Normally dressed for herding sheep; **her wedding clothes are what Melos bought in the city** (「綺麗な衣裳も買って来た」): a saffron-yellow long dress and veil (a common color for Greek brides 〔inference〕), **no red** (art-direction 6: 緋色 is reserved for three things) / 16 歳。普段は羊の番をする身なり。**婚礼の衣装はメロスが町で買ってきたもの**（「綺麗な衣裳も買って来た」）：サフラン色の長衣とベール（ギリシアの花嫁によくある色〔推測〕）。**赤は使わない**（art-direction 6：緋色は 3 つのものにだけ使う） |
| Groom / 花婿 | **Dialogue grade / 会話用** | A young herdsman, both 「頑強」 and 「揉み手して、てれていた」: honest and earnest (voice D-025 Sadachbia). A myrtle wreath on his head at the wedding / 若い牧人で、「頑強」でありながら「揉み手して、てれていた」：実直でまじめ（声は D-025 Sadachbia）。婚礼では頭にギンバイカの花輪 |
| Villagers / 村人 | Crowd variants (sharing the plaza's rig) / 群衆のバリエーション（広場と骨格を共用） | Harvesters (straw hats, sickles), 15〜20 guests at the wedding and the feast / 麦を刈る人（麦わら帽子、鎌）、婚礼と祝宴の客 15〜20 人 |
| Sheep / 羊 | Instanced low-poly, about 20 / インスタンス化したローポリ、約 20 頭 | In the pasture on the morning of 一日目, in the sheepfold at night / 一日目の午前は牧場、夜は羊の囲い |
| Sheepdog / 牧羊犬 | Shared with the dog from the homeward road's 野の道 / 帰り道の野の道の犬と共用 | Follows the sister / 妹についていく |

### 6.2 Materials / 素材

| Material / 素材 | Where / 場所 | Distance / 距離 | Key points / 要点 |
|---|---|---|---|
| Dry-stone wall / 空積みの石垣 | Yard walls, sheepfold, pasture / 中庭の塀、羊の囲い、牧場 | **Close-up, most important / 近景、最重要** | No mortar, grass growing in the joints (art-direction 4.2). Shared with the homeward road / 漆喰を使わず、石の隙間に草が生える（art-direction 4.2）。帰り道と共用 |
| Yard dirt floor / 中庭の土の地面 | Melos's yard / メロスの家の中庭 | Close-up / 近景 | Rammed earth, whitish in clear weather, dark with puddles after rain. A few myrtle leaves scattered on the wedding day / 突き固めた土で、晴れの日は白っぽく、雨のあとは濃い色で水たまりができる。婚礼の日はギンバイカの葉を少し撒く |
| Rough stone wall with earthen plaster / 粗い石の壁に土の漆喰 | Melos's house, the neighbors, the groom's house / メロスの家、隣家、花婿の家 | Close-up / medium / 近景 / 中景 | Earthier and yellower than the plaster in the city, flaking off in patches to show the stone / 町の漆喰より土っぽく黄色みがあり、ところどころ剥がれて石がのぞく |
| Old clay tiles / 古い素焼き瓦 | Roofs / 屋根 | Medium / 中景 | Same as the plaza, faded orange-brown / 広場と同じもので、色あせた橙褐色 |
| Thatch / 草葺き | Sheep shed / 羊小屋 | Medium / 中景 | Dry grass, darker in the rain / 干し草で、雨で色が濃くなる |
| Old wood / 古い木 | Doors, louvers, tables and benches, the vine pergola, the loom / 扉、鎧戸、テーブルと長椅子、ぶどう棚、織機 | Close-up / 近景 | Wood bleached grey by the sun / 日に焼けて灰色になった木 |
| Wheat / 麦 | Fields / 畑 | Medium / 中景 | Golden, shared with the homeward road / 金色で、帰り道と共用 |
| Grapevines / ぶどうの木 | The groom's pergola and the vineyard / 花婿の家の棚とぶどう畑 | Close-up (the night talk under the pergola) / 近景（ぶどう棚の下の夜の語らい） | Big leaves, small green bunches of grapes / 大きな葉、小さな青いぶどうの房 |
| Fig / イチジク | Melos's yard / メロスの家の中庭 | Medium / 中景 | Big leaves, smooth grey-white bark / 大きな葉、灰白色のなめらかな樹皮 |
| Cloth / 布 | The wedding veil, the feast tablecloth / 婚礼のベール、祝宴のテーブルクロス | Close-up / 近景 | The bride's saffron yellow; tablecloth in natural linen / 花嫁のサフラン色。テーブルクロスは生成りの亜麻 |
| Myrtle wreaths / ギンバイカの花輪 | The altar, the door, the groom's head / 祭壇、扉、花婿の頭 | Close-up / 近景 | Small dark green leaves, white flowers: the plant used at Greek weddings 〔inference, common practice〕 / 濃い緑の小さな葉と白い花：ギリシアの婚礼に使う植物〔推測、よくあるやり方〕 |

**Swap to 2048 on high-end devices** (as art-direction 9.3 already says): the dry-stone walls, the dirt road and yard floor, the sheep shed's thatch, the close-up wheat.

**ハイエンド機では 2048 に差し替える**（art-direction 9.3 の記述どおり）：空積みの石垣、土の道と中庭の地面、羊小屋の草葺き、近景の麦。

**Period accuracy** follows art-direction 4.3; the things most likely to creep into the village are: prickly pear cactus hedges (everywhere along field edges in rural Sicily today), lemon and orange trees, maize and tomatoes.

**時代考証**は art-direction 4.3 に従う。村に最も紛れ込みやすいのは：ウチワサボテンの生け垣（今日のシチリアの田舎では畑の縁のいたるところにある）、レモンとオレンジの木、トウモロコシとトマト。

## 7. Camera and the first screen / カメラと最初の画面

- **The shepherd boy's first screen** (一日目 09:00, at `field-edge` facing west): in the foreground the field edge and wheat stubble; in the middle ground on the left Melos's sheepfold and yard wall, on the right the pasture, the sheep and the sister; in the distance the village roofs, the threshing floor and the western hills. The sun is behind on the left, front-lighting the scene. This screen must pass the same checks as art-direction section 10 (the time of day recognizable at a glance, people separable from the background, 60 px silhouettes).
  **牧童の最初の画面**（一日目 09:00、`field-edge` から西向き）：近景はあぜ道と麦の刈り株、中景の左にメロスの家の羊の囲いと塀、右に牧場と羊と妹、遠景に村の屋根、脱穀場、西の山。太陽は左後ろで順光。この画面は art-direction 第 10 節と同じ確認に合格しなければならない（一目で時刻がわかる、人物と背景が分かれる、60 px のシルエット）。
- At 一日目 10:00 Melos walks in along the road from the east: the direction behind the player. The sister sees him first and runs toward the road; the player turns around and sees a staggering figure on the bright white road (backlit, sun at 116°).
  一日目 10:00 にメロスが東の道から歩いてくる：プレイヤーの背後の方向。妹が先に彼を見つけて道へ駆け出し、プレイヤーが振り返ると、白く光る道をよろめきながら歩く人影が見える（逆光、太陽は 116°）。
- The wedding (二日目 12:00): the staging camera shoots the altar from the yard gate facing south, the couple make their vows with their backs to the camera, and Melos is on the other side of the altar facing the camera. Then the weather turns: from the same camera position we watch the sky darken and the first raindrops fall in the yard.
  婚礼（二日目 12:00）：演出のカメラは門から南に祭壇を撮り、新郎新婦はカメラに背を向けて誓い、メロスは祭壇の反対側でカメラのほうを向いている。続いて天気が変わる：同じカメラ位置のまま、空が暗くなり、最初の雨粒が中庭に落ちるのを見る。
- Running out at 三日目 04:30: from the yard gate facing east, Melos dashes through the sheepfold gate onto the road and vanishes into the grey-blue of the rain. Before he dashes off, 「ぶるんと両腕を大きく振って」.
  三日目 04:30 に走り出る：門から東を向くと、メロスが羊の囲いの門を抜けて道へ飛び出し、雨の灰青色の中へ消える。飛び出す前に「ぶるんと両腕を大きく振って」。

## 8. Agreed with Frontend and Data / フロントエンド、データと決めたこと

**Frontend** (10-10 15:57Z, `frontend/estimates/village-castle-answers.md`, folded into the start of this document, section 3, and 5.1〜5.3):
- Indoors uses the close follow, no fixed camera positions (section 3).
- It fits in 10 MB: the first entry downloads only the clear-weather lighting set, the scene is about 4.5〜5.5 MB; the interior is a separate package, and the other lighting sets download in the background after entry. The order of cuts if it really doesn't fit is at the start of this document.
- 4 outdoor sets plus 1 small indoor set, the village downloads about 8〜9 MB in total (5.2); the weather change is two lightmap sets interpolated plus instanced rain, about 1〜2 ms more on tier B, no lightning (5.3).
- The lamp in hand in the rain: one light, no shadows, about 6 m (5.1).

**フロントエンド**（10-10 15:57Z、`frontend/estimates/village-castle-answers.md`、文書の冒頭、3 節、5.1〜5.3 に反映済み）：
- 屋内は近い追従を使い、固定カメラは使わない（3 節）。
- 10 MB に収まる：初回入場では晴れの光のセットだけをダウンロードし、シーンは約 4.5〜5.5 MB。屋内は別のパッケージで、ほかの光は入場後にバックグラウンドで落とす。どうしても収まらないときに削る順番は文書の冒頭を参照。
- 屋外 4 セットと屋内の小さい 1 セットで、村のダウンロードは合計約 8〜9 MB（5.2）。天気の変化は 2 セットのライトマップの補間とインスタンス化した雨で、ティア B で約 1〜2 ms 増え、稲妻は作らない（5.3）。
- 雨の中で手に持つランプ：1 つ、影を落とさず、約 6 m（5.1）。

**Frontend #44 review** (10-10 16:20Z, folded in): `melos-home` split into three convex rectangles (2.1); a start spot for each place, with `groom-gate` added for the groom's house (section 4); `feast-*` marked `auto: false`, `yard-fig` and `yard-east` added in the yard (section 4); the interior is used from 一日目 10:30, so a small daytime lightmap set is added and the interior package downloads right after the first screen (section 3, 5.2).

**フロントエンド #44 レビュー**（10-10 16:20Z、反映済み）：`melos-home` を 3 つの凸の長方形に分ける（2.1）。場所ごとの開始点として、花婿の家に `groom-gate` を追加（4 節）。`feast-*` を `auto: false` にし、中庭に `yard-fig`、`yard-east` を追加（4 節）。屋内は一日目 10:30 から使うので、昼の小さいライトマップのセットを加え、屋内のパッケージは最初の画面のあとすぐダウンロードする（3 節、5.2）。

**Data** (10-10 16:01Z, folded into 2.1, the vine pergola in section 2, and section 4):
- "What someone is doing" belongs to the world model's activity (the sister's `initialActivity` work, beat.08 talk, beat.09 and beat.13 sleep, beat.14 run); "which spot someone stands at" belongs to the layout's spots: if a beat's relocate writes a spot they stand there, and anyone without one stands at the first free auto spot of the place. Data writes the beats with the spot names from section 4.
- One `place.melos-home` polygon plus spots, including the pasture (2.1). `exit.2.village` now lands at `road-arrive` in `place.melos-home`, so those who come to the village with Melos are present for the siblings' meeting and learn about "the wedding tomorrow".
- Persuading the groom under the vine pergola (outdoors) matches the original, and presence is counted by `place.groom-house`. That night is clear.
- Weather is one global value: storm from 二日目 12:30, after-rain from 三日目 09:00 (5.3).

**データ**（10-10 16:01Z、2.1、2 節のぶどう棚、4 節に反映済み）：
- 「何をしているか」は世界モデルの activity が受け持ち（妹の `initialActivity` は work、beat.08 は talk、beat.09 と beat.13 は sleep、beat.14 は run）、「どのスポットに立つか」はレイアウトのスポットが受け持つ：ビートの relocate にスポットが書かれていればそこに立ち、書かれていない人はその場所の最初の空いている自動で立てるスポットに立つ。データは 4 節のスポット名でビートを書く。
- `place.melos-home` は 1 つのポリゴンとスポットで表し、牧場を含む（2.1）。`exit.2.village` の着地を `place.melos-home` の `road-arrive` に変えた。これでメロスについて村に来た人は兄妹の再会に居合わせ、「明日の婚礼」を知ることができる。
- ぶどう棚の下（屋外）で花婿を説得するのは原作に合っていて、居合わせたかどうかは `place.groom-house` で判定する。その夜は晴れ。
- 天気は全体で 1 つの値：二日目 12:30 から storm、三日目 09:00 から after-rain（5.3）。

**Data #44 review** (10-10 16:26Z): the groom's house needs an auto spot listed first, so `groom-work` was added (section 4). Data changed this in the M3 world model themselves (this doc doesn't need to change): beat.12's place is now `place.melos-home`, the sister and the groom take shelter indoors (`feast-*`), so those at the wedding learn about the storm (`fact.storm`); beat.13 also writes `feast-*` for the two; beat.14 writes `way.east` for Melos.

**データ #44 レビュー**（10-10 16:26Z）：花婿の家には先頭に置く自動で立てるスポットが必要なので、`groom-work` を追加した（4 節）。データ自身が M3 の世界モデルで直した（この文書は変更不要）：beat.12 の場所を `place.melos-home` に変え、妹と花婿は屋内に避難する（`feast-*`）。これで婚礼に出た人が大雨のこと（`fact.storm`）を知ることができる。beat.13 でも二人に `feast-*` を書く。beat.14 ではメロスに `way.east` を書く。

---

## Revision history / 改訂履歴

- v1.0 (2026-10-10): first version. v0.1 was reviewed by Frontend and Data, and their answers have been folded into each section. Added per the #44 review: spot ordering and start spots (added `well-side`, `yard-fig`, `yard-east`, `groom-work`, `groom-gate`; player spots marked `auto: false`), `melos-home` split into three convex pieces, the interior used from 一日目 daytime with a daytime lighting set added; `melos-meet` moved to (12.3, 3), off the seam between rectangles.
  v1.0（2026-10-10）：最初の版。v0.1 をフロントエンドとデータが確認し、回答は各節に反映済み。#44 レビューに沿って補足：スポットの順序と開始点（`well-side`、`yard-fig`、`yard-east`、`groom-work`、`groom-gate` を追加し、プレイヤーのスポットを `auto: false` に）、`melos-home` を凸の 3 つに分割、屋内は一日目の昼から使い、昼の光のセットを追加。`melos-meet` を (12.3, 3) へ移し、長方形の継ぎ目から外した。
