# Player: the village shepherd boy / プレイヤー・村の牧童

> メロスの村で、羊を追っている。

The player's third identity (`role.shepherd-boy`, ux-design 5.1). A child who herds sheep in Melos's village; characters call you 「坊主」. Starts in act 3: 一日目 (day 1) 09:00 on the field ridge at the edge of the village (village.md `field-edge`), and can go to the village, the way back, the square and the execution ground.

プレイヤーの三つ目のアイデンティティ（`role.shepherd-boy`、ux-design 5.1）。メロスの村で羊の番をする子どもで、人物からは「坊主」と呼ばれる。第三幕から始まる：一日目 09:00、村はずれのあぜ道（village.md `field-edge`）。村、帰り道、広場、刑場に行ける。

As with the traveler, **the player sees the back** (the points in traveler.md "Only the back is seen" apply as they are).

旅人と同じく、**プレイヤーに見えるのは後ろ姿**（traveler.md「見えるのは後ろ姿だけ」の各項目をそのまま適用）。

For shared rules see the [README](../README.md). Figure: [m3-cast.svg](m3-cast.svg) (the second row shows the backs).

共通のルールは [README](../README.md) を参照。図：[m3-cast.svg](m3-cast.svg)（二列目は後ろ姿）。

## Three things recognizable at a glance (exploration camera, 60 px, seen from behind) / 一目で分かる三つの特徴（探索カメラ、60 px、背後から）

1. **Small, with a crook taller than himself**: 1.48 m, the shortest of all the characters; the crook he leans on in his right hand is about 1.6 m, with a hook at the top, rising above his head.
   **小柄で、牧杖が背より高い**：1.48 m、全人物の中で最も背が低い。右手でつく牧杖は約 1.6 m で、先端に鉤があり、頭より高い。
2. **A short sheepskin cape**: fleece outward, covering both shoulders down to the middle of the back, light-colored, with a fluffy edge.
   **羊皮の短いケープ**：毛を外側にして両肩を覆い、背中の真ん中まで。明るい色で、縁はふわふわしている。
3. **A scarlet sash on a deep walnut tunic**: a dark body, light shoulders, and a band of red in between.
   **濃い胡桃色の短衣に緋色の腰帯**：体は暗く、肩は明るく、その間に一本の赤。

**Different from what art-direction 5.4 originally said**: it originally said "a wide-brimmed woven-straw hat". Changed: the wheat harvesters in the village all wear straw hats (village.md 6.1), and a wide brim is the traveler's mark, so if the shepherd boy wore one he could not be found in the village. Replaced with a sheepskin cape and no hat.

**art-direction 5.4 の元の記述とは異なる**：元は「草で編んだつば広の帽子」としていた。変更した：村の麦刈りの人はみな麦わら帽子をかぶり（village.md 6.1）、つば広は旅人の印でもあるので、牧童がかぶると村の中で見つからなくなる。羊皮のケープに替え、帽子はかぶらない。

## Body / 体

| Item / 項目 | Requirement / 要件 |
|---|---|
| Age / 年齢 | Twelve or thirteen [inferred: 「坊主」] / 十二、三〔推定：「坊主」〕 |
| Height, build / 身長・体型 | 1.48 m, 6.5 heads tall (child proportions: a slightly larger head, slightly shorter legs), thin, deeply tanned / 1.48 m、6.5 頭身（子どもの比率：頭が少し大きく、脚が少し短い）、痩せていて、日に焼けて黒い |
| Posture / 姿勢 | Standing, he leans his weight on the crook, or rests both hands on top of it. The idle animation pokes at things on the ground with the crook and looks at the sheep / 立っているときは重心を牧杖に預けるか、両手を杖の頭に載せる。待機モーションは杖で地面のものをつつき、羊を眺める |
| Skin / 肌 | `#9A6C4C`, tanned; only the hands, calves and back of the neck are visible / `#9A6C4C`、日焼けしている。見えるのは手、ふくらはぎ、首の後ろだけ |
| Hair / 髪 | Dark brown, short and messy, no hat / 濃い茶色、短くぼさぼさで、帽子はかぶらない |

The player speaks in their own voice, which may be an adult's. The body does not change because of that: characters call him 「坊主」, and the world treats him accordingly.

プレイヤーは自分の声で話し、それが大人の声かもしれない。それでも体は変えない：人物は彼を「坊主」と呼び、世界はそれに従って彼を扱う。

## Costume / 衣装

| # | Part / 部位 | Material and color / 素材と色 | How it is made / 作り方 | Approx. share of the 1024 map / 1024 マップ上の面積の目安 |
|---|---|---|---|---|
| ① | Tunic / 短衣 | **Deep walnut N3 `#57432F`**, coarse wool / **濃い胡桃色 N3 `#57432F`**、粗い羊毛 | To just above the knee, covering both shoulders, sleeveless, the hem worn fuzzy. **Darker than the village's plaster walls, the wheat and the dry-stone walls**: in the 9:00 front-lit first screen he is the darkest patch in the foreground (village.md section 7) / 膝上まで、両肩を覆い、袖なし。裾は擦り切れて毛羽立っている。**村の漆喰の壁、麦、空積みの石垣のどれよりも暗い**：9:00 の順光の最初の画面で、彼は近景の中で最も暗い塊になる（village.md 第 7 節） | 30% |
| ② | Sheepskin cape / 羊皮のケープ | **Natural fleece FL `#D5C9B0`**, fleece outward / **羊毛の生成り FL `#D5C9B0`**、毛を外側に | A single sheepskin tied at the chest with a leather cord, covering both shoulders and reaching below the shoulder blades at the back. Uneven edges, the fleece in tufts. The fleece's relief comes from the normal map; **no hair cards** (tier B polygon budget) / 一枚の羊皮を胸の前で革紐で結び、両肩を覆い、背中は肩甲骨の下まで。縁は不揃いで、毛は房になっている。毛の起伏は法線マップで作り、**髪カードは使わない**（ティア B のポリゴン数） | 20% |
| ③ | Sash / 腰帯 | **Scarlet R1 `#8E271C`** / **緋 R1 `#8E271C`** | The same one as the traveler's (traveler.md ②). This is the only scarlet / 旅人と同じもの（traveler.md ②）。緋色はこの一か所だけ | 8% |
| ④ | Sandals / サンダル | Old leather K1 / 古い革 K1 | The simplest kind: a piece of leather plus cords / いちばん簡単な、革一枚に紐をつけたもの | 6% |

**Things carried** (world model `role.shepherd-boy.items`):

**身につけているもの**（世界モデル `role.shepherd-boy.items`）：

| Item / もの | Where / 位置 | Notes / 説明 |
|---|---|---|
| 羊飼いの杖 (`item.crook`) / 羊飼いの杖（`item.crook`） | Right hand / 右手 | About 1.6 m, olive wood, a hook at the top. Leaned on when walking, gripped in the middle when running (the side-by-side running stretch of the way back, homeward-road section 5). Prop 512 / 1024 in dialogue / 約 1.6 m、オリーブ材、先端に鉤。歩くときはつき、走るときは真ん中を握る（帰り道で並んで走る区間、homeward-road 第 5 節）。小道具 512 / 会話中は 1024 |
| 革の水袋 (`item.waterskin`) / 革の水袋（`item.waterskin`） | Hung at the left hip, showing below the cape / 左腰に下げ、ケープの下からのぞく | The same model as the traveler's (the same ID). 「水を渡す」 takes from here: the cup of water given to Melos at the start (the opening act of help in ux-design 5.1) / 旅人と同じモデル（同じ ID）。「水を渡す」ときはここから取る：開始時にメロスに渡す一杯の水（ux-design 5.1 の開始時の助け合い） |
| The sister's 弁当 (packed lunch), the groom's borrowed lamp / 妹がくれた弁当、花婿に借りた灯り | Obtained through acts of help (ux-design 5.1, inferred) / 助け合いで手に入る（ux-design 5.1、推定） | The 弁当 is a cloth bundle hung on the sash; the lamp is a clay oil lamp held in the left hand. Both are small props, shown only once obtained / 弁当は布包みで、腰帯に下げる。灯りは素焼きの油ランプで、左手に持つ。どちらも小さな小道具で、手に入れてから表示する |

- Dust: feet, calves, hem. A little dirtier than anyone (he runs around the fields and pastures).
  埃：足、ふくらはぎ、裾。誰よりも少し汚れている（畑や牧草地を走り回っている）。
- Rain (from 二日目 12:30) and crossing the river (the way back): wet, via material parameters. The sheepskin darkens and its fleece goes flat when wet (the same texture, parameters).
  雨（二日目 12:30 から）、川を渡る（帰り道）：濡れる。マテリアルのパラメータで。羊皮は濡れると色が濃くなり、毛がぺたんとなる（同じテクスチャで、パラメータで）。

## Running with Melos (the way back) / メロスと一緒に走る（帰り道）

- On the side-by-side running stretch (homeward-road section 5) he is behind and to the side of Melos, with the camera as described in that section. Common sense says a child cannot keep up with Melos; in the world model he can, so play it as him keeping up, with quicker, shorter steps than Melos.
  並んで走る区間（homeward-road 第 5 節）では、彼はメロスの斜め後ろにいて、カメラはその節に従う。子どもがメロスについていけないのは常識だが、世界モデルではついていけるので、ついていけるものとして演じる。歩調はメロスより速く、歩幅は小さい。
- From stage 2 onward (the river crossing, the bandits) Melos's clothes get torn, but the shepherd boy's do not: he did not swim the 濁流 and did not fight. Wet and dust apply as usual.
  第 2 段階以降（川を渡る、山賊）、メロスの衣服は破れていくが、牧童の衣服は破れない：彼は濁流を泳いでおらず、戦ってもいない。濡れと埃は通常どおり。

## Camera / カメラ

- Exploration camera: distance and height per ux-design 6.3. He is shorter, so his back is smaller in the frame; frontend checks whether the 60 px acceptance (item 1 below) still passes, and if not, shortens the camera distance in proportion to height [frontend decides].
  探索カメラ：ux-design 6.3 の距離と高さに従う。背が低いので、後ろ姿は画面の中でより小さくなる。フロントエンドは 60 px の受け入れ確認（下の第 1 項）がまだ通るかを確認し、通らなければ身長に合わせてカメラの距離を少し縮める〔フロントエンドが決める〕。
- Dialogue camera: in the over-the-shoulder shot his shoulder is lower than the other person's. The camera goes behind his shoulder and frames the other person's face (face size as in ux-design 6.3), giving a slight upward angle, which is exactly how a child looks at an adult. The upward angle stays within about 10°; any more, and the camera is raised.
  会話カメラ：肩越しのとき、彼の肩は相手より低い。カメラは彼の肩の後ろに置き、相手の顔に向けて構図を取る（顔の大きさは ux-design 6.3 のまま）。少しあおりになるが、それこそ子どもが大人を見上げる姿。あおりの角度は約 10° を超えないようにし、それ以上になるならカメラを上げる。

## Moving parts / 動く部分

- 2 bones per sash tail (same as the traveler). 2 for the cape's lower edge.
  帯の端は一本につきボーン 2 本（旅人と同じ）。ケープの下縁に 2 本。
- The crook and the water skin are rigid bodies.
  牧杖と水袋は剛体。

## Acceptance check / 受け入れ確認

1. In the 60 px silhouette he is recognizable at a glance from behind (size, crook, light shoulders), and in the village separable from the wheat harvesters, Melos, the groom and the sister (the "Village" panel at the bottom of m3-cast.svg).
   60 px のシルエットで、背後から一目で分かり（背丈、牧杖、明るい肩）、村の中で麦刈りの人、メロス、花婿、妹と区別できる（m3-cast.svg 下部の「村」）。
2. In the 9:00 first screen (village.md section 7), his back is the darkest patch in the foreground, and the scarlet sash is the most saturated color in the frame.
   9:00 の最初の画面（village.md 第 7 節）で、彼の後ろ姿は近景で最も暗い塊で、緋色の腰帯は画面で最も彩度の高い色である。
3. The dialogue camera's upward angle stays within about 10°, and the other person's face is at the size given in ux-design 6.3.
   会話カメラのあおりの角度が約 10° を超えず、相手の顔は ux-design 6.3 の大きさになっている。
