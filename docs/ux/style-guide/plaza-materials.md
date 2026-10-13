# Plaza material list (Syracuse square, including the execution ground and 石屋の工房) / 広場マテリアル一覧（シラクスの広場、刑場と石屋の工房を含む）

| Item / 項目 | Content / 内容 |
|---|---|
| Purpose / 用途 | Frontend picks and tunes against this when F-2b switches to the final materials; UX runs its acceptance check against it / フロントエンドが F-2b で正式なマテリアルに差し替えるとき、これに従って選び、調整する。UX はこれに従って受け入れ確認をする |
| Basis / 根拠 | art-direction 4.2 (materials), 4.3 (period accuracy), 6 (scarlet), 7 (image treatment), 9.2–9.5 (two tiers); the material slots in frontend F-2a's `assets/scenes/syracuse-square/scene.json` / art-direction 4.2（マテリアル）、4.3（時代考証）、6（緋色）、7（画面処理）、9.2〜9.5（二つのティア）。フロントエンド F-2a の `assets/scenes/syracuse-square/scene.json` のマテリアルスロット |
| Status / 状態 | Colors and roughness are UX's initial ranges, to be tuned together once F-2b's real-device images are available [UX's initial values] / 色と粗さは UX の暫定の範囲で、F-2b の実機画面が出た後に一緒に調整する〔UX の暫定値〕 |

## Read these three first / まずこの三つ

1. **Limestone is the lead.** The ground and the royal castle's walls take up most of the first screen (art-direction 9.3). Syracuse limestone is a honey-tinted white that turns gold in the setting sun, but the base color itself must not be yellow or orange: the gold comes from the light, not the texture.
   **石灰岩が主役。** 地面と王城の壁が最初の画面の大半を占める（art-direction 9.3）。シラクスの石灰岩は蜜色がかった白で、夕日の下で金色に輝くが、下地の色そのものを黄色やオレンジにしてはならない：金色は光で出し、テクスチャでは出さない。
2. **No red other than scarlet** (art-direction 6). Cloth awnings, clay roof tiles, pottery and plants are all kept low in saturation; at sunset the most saturated thing in the frame must be the traveler's sash.
   **緋色以外の赤は使わない**（art-direction 6）。布の日よけ、素焼きの瓦、陶器、植物はすべて彩度を抑え、日没時に画面で最も彩度の高いものは旅人の腰帯でなければならない。
3. **Realism mostly breaks on period.** Scanned assets were photographed today and often include things from two thousand years later. Run section 4 first when choosing assets.
   **リアルさの破綻はたいてい時代に出る。** スキャン素材は今日撮影されたもので、二千年後のものがよく紛れ込んでいる。素材を選ぶときはまず第 4 節を通す。

## 1. List / 一覧

Matched one to one with frontend F-2a's current material slots. The "High-end 2048" column agrees with art-direction 9.3 and is exactly the 6 slots for which frontend has already enabled the high-end version; keep it unchanged.

フロントエンド F-2a の現在のマテリアルスロットと一対一で対応させている。「高性能機 2048」の列は art-direction 9.3 と一致し、ちょうどフロントエンドが現在高性能機版を有効にしている 6 つのスロットでもあるので、変えない。

| # | Material / マテリアル | Frontend slot / フロントエンドのスロット | Used on / 使用箇所 | High-end 2048 / 高性能機 2048 | Mean base color (sRGB) / 下地の平均色（sRGB） | Roughness / 粗さ | Key points / 要点 |
|---|---|---|---|---|---|---|---|
| 1 | Limestone paving / 石灰岩の石畳 | `floor` | All ground in the square and the gate street, in front of the royal castle / 広場と城門通りの地面全体、王城の前 | Yes / はい | About `#B9AC93` (R 180–195, G 168–180, B 140–155) / 約 `#B9AC93`（R 180〜195、G 168〜180、B 140〜155） | 0.65–0.85; polished paths 0.45–0.6 / 0.65〜0.85。磨かれた道筋は 0.45〜0.6 | **The exploration camera looks at it all the time.** Large irregular slabs, 60–120 cm each, with dust and dry grass in the joints. The polished paths (the corridor of light from the city gate to the pillar, the ring around the fountain, doorways) are not painted into the repeating texture but use one low-resolution mask over the whole square [frontend decides how]. In the evening it is lit gold and bounces light onto faces / **探索カメラがずっと見ている。** 不規則な大きな石板で、1 枚 60〜120 cm、目地には埃と枯れ草。磨かれた道筋（城門から柱への光の回廊、噴水のまわり、戸口）は繰り返しテクスチャには描かず、広場全体に一枚の低解像度マスクを使う〔方法はフロントエンドが決める〕。夕方は金色に照らされ、光を人の顔に照り返す |
| 2 | Royal castle ashlar / 王城の切石 | `ashlar_warm` | Royal castle walls, towers, city walls, the back walls of the colonnade, the temple's inner sanctuary / 王城の壁、塔、城壁、柱廊の奥の壁、神殿の内陣 | Yes / はい | Honey-tinted white, about `#C8B796` (R 195–210, G 178–192, B 140–160). The current placeholder `(200, 168, 122)` leans yellow; the final one should be whiter / 蜜色がかった白、約 `#C8B796`（R 195〜210、G 178〜192、B 140〜160）。現在の仮の値 `(200, 168, 122)` は黄色寄りなので、正式なものはもう少し白く | 0.75–0.9 / 0.75〜0.9 | **Dry-laid, no mortar joints between blocks**; joints thin and straight. Courses of large blocks of equal height: each course 45–60 cm high, each block 90–150 cm long. Chisel marks on the surface, readable in low-angle sunlight. The bottom ~30 cm of the wall darkened by splashes and dust; higher up, bleached whiter by the sun / **空積みで、石の間にモルタルの目地はない**。目地は細くまっすぐ。同じ高さの大きな石を段に積む：1 段の高さ 45〜60 cm、1 個の長さ 90〜150 cm。表面に鑿の跡があり、低い角度の日差しで読み取れる。壁の足元約 30 cm は跳ねた水と埃で暗く、高いところは日に焼けてより白い |
| 3 | Ordinary house stone walls / 一般の家の石壁 | `ashlar` | Walls of ordinary houses (about 60%), the workshop's enclosure wall / 一般の家の壁（約六割）、工房の囲い壁 | No / いいえ | A little grayer and darker than the royal castle, about `#B5A88F` / 王城より少し灰色で暗い、約 `#B5A88F` | 0.8–0.95 / 0.8〜0.95 | Rubble stones of uneven size, earth-colored mud in the joints, **not cement gray**. Rougher and less regular than the royal castle's walls; at a glance, a poor household / 大きさの不揃いな野石で、目地は土色の泥、**セメントの灰色ではない**。王城の壁より粗く不揃いで、一目で貧しい家と分かる |
| 4 | Plaster / 漆喰 | `plaster` | Walls of ordinary houses (about 40%), houses in the distant town / 一般の家の壁（約四割）、遠景の町の家 | Yes / はい | Warm white, about `#D6CCB6` (R 205–220, G 195–208, B 170–185). A few houses may be washed pale ochre, but less saturated than Melos's tunic / 暖かい白、約 `#D6CCB6`（R 205〜220、G 195〜208、B 170〜185）。少数の家は淡い黄土色に塗ってもよいが、彩度はメロスの短衣より低く | 0.85–0.95 / 0.85〜0.95 | Flaking in places, exposing the stone or mud brick beneath. Splashed dirt at the base of the wall. Vertical streaks under the eaves where rainwater has run / ところどころ剥がれて、下の石や日干し煉瓦がのぞく。壁の足元に跳ねた汚れ。軒下には雨水が流れた縦の筋 |
| 5 | Limestone details / 石灰岩の細部 | `stone` | Steps, columns, door frames, cornices, the fountain, the scaffold, the workshop's column drums and freshly cut blocks in the yard / 階段、柱、戸枠、軒、噴水、磔台、工房の柱の石鼓と中庭の切り出したばかりの石 | Yes / はい | Same as the paving, slightly brighter, about `#C0B49C` / 石畳と同じでやや明るい、約 `#C0B49C` | 0.6–0.8 / 0.6〜0.8 | Finely chiseled or smoothed faces, no large joints. Step edges worn round, shallow hollows trodden into the middle (normal map). In the fountain basin, a band of dark water stain and a little moss below the waterline / 細かく鑿で仕上げたか磨いた面で、大きな目地はない。階段の縁は踏まれて丸くなり、中央は浅くくぼむ（法線）。噴水の水盤は水面より下に暗い水染みの帯と少しの苔 |
| 6 | Old wood / 古い木 | `doors` | Doors, shutters, the city gate, the royal castle's gates / 扉、鎧戸、城門、王城の門 | Yes / はい | Old wood weathered gray, about `#807666` (R 120–140, G 112–128, B 100–115) / 日に焼けて灰色になった古い木、約 `#807666`（R 120〜140、G 112〜128、B 100〜115） | 0.75–0.9 / 0.75〜0.9 | **Windows have no glass**; wooden shutters instead. Ironwork limited to a few black iron nails and door rings; no modern hinges or locks. The lower half of doors scuffed dirty and worn fuzzy / **窓にガラスはなく**、木の鎧戸を使う。金具は少量の黒い鉄釘と扉の環だけで、現代の蝶番や錠は使わない。扉の下半分は蹴られて汚れ、擦れて毛羽立っている |
| 7 | Clay roof tiles / 素焼きの瓦 | `roof` | All roofs, the colonnade's lean-to roofs, the workshop's shed / すべての屋根、柱廊の片流れ屋根、工房の小屋 | Yes / はい | Faded orange-brown, about `#9A6E58`. **HSV saturation at most 0.45** (R1 is 0.80). The current placeholder `(127, 77, 51)` has saturation 0.60, too red; tone it down / 褪せたオレンジがかった褐色、約 `#9A6E58`。**HSV 彩度は 0.45 以下**（R1 は 0.80）。現在の仮の値 `(127, 77, 51)` は彩度 0.60 で赤すぎるので抑える | 0.7–0.85 / 0.7〜0.85 | Wide pan tiles plus cover tiles over the joints, the Greek way. No modern machine-made tiles (interlocking grooves, every tile identical, bright red). Dust and gray-green lichen patches on the tiles, color uneven in patches / 幅の広い平瓦に継ぎ目を覆う丸瓦を載せる、ギリシアのやり方。現代の機械製の瓦（噛み合わせの溝があり、一枚一枚がまったく同じで、真っ赤）は使わない。瓦には埃と地衣類の灰緑色の斑点があり、色はまだらに不揃い |
| 8 | Rough wood / 粗い木 | `bark` | Market-stall posts and tables, the workshop's door and benches, shed posts, **the 磔の柱** / 露店の柱と台、工房の扉と長椅子、小屋の柱、**磔の柱** | No / いいえ | About `#6E5E4C` / 約 `#6E5E4C` | 0.85–0.95 / 0.85〜0.95 | Man-made things use **debarked, roughly hewn timber** with axe marks. Only tree trunks have bark. The 磔の柱 is a single debarked rough log, darker and rougher than the old wood of doors, with no bark / 人が作ったものは**皮を剥いだ粗削りの木材**で、斧の跡がある。樹皮つきなのは木の幹だけ。磔の柱は皮を剥いだ一本の粗い丸太で、扉の古い木より暗く太く、樹皮はない |
| 9 | Cloth / 布 | `fabric_red`, `fabric_blue` / `fabric_red`、`fabric_blue` | Awnings of two market stalls; later door curtains and laundry / 二つの露店の布の日よけ。今後は戸口の幕、干した衣服 | No / いいえ | Undyed linen L0, faded woad, pale ochre (the color table in the style-guide README) / 染めていない亜麻 L0、褪せた大青、淡い黄土（style-guide README の色表） | 0.9–1.0 / 0.9〜1.0 | **No red.** Please rename the current slot `fabric_red` (e.g. `fabric_a`) and use undyed linen for its color. In backlight, translucency matters more than the normal map: an awning seen from behind in the evening should glow through. Moved by the wind (art-direction 7), with fuzzy edges and patches / **赤は使わない。** 現在のスロット名 `fabric_red` は改名し（例：`fabric_a`）、色は染めていない亜麻にする。逆光では法線より透過が大事：夕方に背後から見た日よけは光が透けて見えること。風で揺れ（art-direction 7）、縁は毛羽立ち、継ぎが当たっている |
| 10 | Pottery / 陶器 | `terracotta` | Jars, water pitchers and oil lamps on stalls and at doorways / 露店や戸口の壺、水がめ、油ランプ | No (prop, 512) / いいえ（小道具 512） | Unglazed earth yellow to light orange, about `#B08A68`, saturation at most 0.45 / 素焼きの土の黄色から淡いオレンジ、約 `#B08A68`、彩度は 0.45 以下 | 0.8–0.9 / 0.8〜0.9 | Only a little black patterning. Currently borrows the stone texture (color parameters have no effect when a texture is set); F-2b gives it its own 512 / 黒い文様が少しあるだけ。現在は石のテクスチャを借りている（テクスチャがあると色パラメータは効かない）。F-2b で専用の 512 を一枚用意する |
| 11 | Cornices and friezes / 軒とフリーズ | `trim`, `cornice` / `trim`、`cornice` | Friezes of the colonnade and the temple, the temple's cornice / 柱廊と神殿のフリーズ、神殿の軒 | No / いいえ | Same as limestone details / 石灰岩の細部と同じ | 0.6–0.8 / 0.6〜0.8 | The temple's triglyphs and metopes use relief normals. Ancient Greek temples were originally painted; here only very faint traces of blue and ochre remain, **no red** [inferred] / 神殿のトリグリフとメトープは浮き彫りの法線を使う。古代ギリシアの神殿はもともと彩色されていたが、ここではごく淡い青と黄土の痕跡だけを残し、**赤は使わない**〔推定〕 |
| 12 | Water / 水 | `water` | The fountain / 噴水 | — | Clear water, the bottom of the basin visible / 澄んだ水で、水盤の底が見える | About 0.05 / 約 0.05 | Fine ripples on the surface, moving. Reflections in the setting sun; bloom only here and around firelight (art-direction 7) / 水面に細かいさざ波があり、動いている。夕日のときに照り返しがあり、ブルームはここと火の光のまわりだけ（art-direction 7） |
| 13 | Plants / 植物 | `cypress`, plus the trees at the edge of the square / `cypress`、および広場の縁の木 | Cypresses in the distance; olives and figs at the edge of the square; the grape arbor at the old man's door (section 2) / 遠景の糸杉。広場の縁のオリーブ、イチジク。老爺の家の戸口の葡萄棚（第 2 節） | No / いいえ | Olive leaves gray-green on top, silver-gray underneath; cypress deep green, nearly black / オリーブの葉は表が灰緑色、裏が銀灰色。糸杉は黒に近い深緑 | — | Early summer: the grapes are small green bunches, not yet ripe. **No flowers**, especially no red flowers / 初夏：葡萄は青く小さな房で、まだ熟していない。**花は置かない**。特に赤い花は置かない |
| 14 | Distant hills / 遠くの山 | `hill` | The Hyblaean hills to the west / 西のイブレイ山地 | No / いいえ | Changes with the sky and the fog / 空の色と霧に合わせて変わる | — | Fading into the distance and shifting toward the sky's color (art-direction 7's aerial perspective) / 遠くほど淡くなり、空の色に寄る（art-direction 7 の空気遠近法） |

Two additions:

補足が二つ：

- **The yard of 石屋の工房**: the ground uses the same paving texture, with a layer of stone chips and white stone dust on top, thicker the closer to the benches [frontend may use decals or vertex color]. The blocks in the yard use `stone` (finely chiseled faces, brighter): freshly cut single blocks with no course joints, whiter than the royal castle's walls and not sun-aged.
  **石屋の工房の中庭**：地面は同じ石畳のテクスチャを使い、その上に石屑と白い石の粉を一層重ね、長椅子に近いほど厚くする〔フロントエンドはデカールか頂点カラーを使ってよい〕。中庭の石は `stone`（細かく鑿で仕上げた面で、より明るい）を使う：切り出したばかりの単独の石で、段の目地はなく、王城の壁より白く、日に焼けて古びていない。
- **The execution ground**: no dedicated material. The scaffold is built from limestone details (5) and the 磔の柱 is rough wood (8). The foot of the pillar and the steps are polished brighter by hands and feet [inferred].
  **刑場**：専用のマテリアルはない。磔台は石灰岩の細部（5）で積み、磔の柱は粗い木（8）。柱の根元と階段は人に触られ、踏まれてより明るく光っている〔推定〕。

## 2. The grape arbor at the old man's door / 老爺の家の戸口の葡萄棚

art-direction 4.2 suggests putting it here. In dialogue, light falls on his face through gaps in the leaves: cheap and beautiful.

art-direction 4.2 がここに置くことを提案している。会話中、葉の隙間から光が彼の顔に落ちる。安上がりで美しい。

| Item / 項目 | Requirement / 要件 |
|---|---|
| Position / 位置 | In front of 老爺の家, covering the position point `old-man-house` and the doorway, about 3 × 2.5 m / 老爺の家の前、位置点 `old-man-house` と戸口を覆う、約 3 × 2.5 m |
| Structure / 構造 | 4 debarked old wooden posts, about 2.4 m tall, with crossbars on top. The vine climbs one post, and its leaves cover most of the top / 皮を剥いだ古い木の柱 4 本、高さ約 2.4 m、上に横木を渡す。蔓は一本の柱を這い上がり、葉が屋根の大半を覆う |
| Season / 季節 | Early summer: the leaves are newly grown, tender green; the fruit is small green bunches / 初夏：葉は出たばかりで若緑。実は青く小さな房 |
| Light / 光 | While the sun still reaches the doorway, leaf shadows fall on the old man's face and on the ground. **Do not create a separate sun just for the leaf shadows** (art-direction 3, "the sun is the clock"). Once the doorway is in shadow, the arbor is a dark roof, and the face relies on skylight and the lamp at the door (old-man.md). When the doorway falls into shadow is checked by frontend with the real-time sun and written into F-2b's notes / 日差しがまだ戸口に届いている間は、葉の影が老爺の顔と地面に落ちる。**葉の影のために別の太陽を作らない**（art-direction 3「太陽が時計」）。戸口が影に入った後は、葡萄棚は暗い屋根になり、顔は天空光と戸口の灯り（old-man.md）に頼る。戸口がいつ影に入るかは、フロントエンドがリアルタイムの太陽で確認し、F-2b の説明に書く |
| How it is made / 作り方 | Leaves as alpha-textured cards. Whether the leaf shadows use real-time shadows or a projected texture (cookie) is decided by frontend based on frame time / 葉は透過テクスチャの板ポリゴンで作る。葉の影にリアルタイムシャドウを使うか投影テクスチャ（cookie）を使うかは、フロントエンドがフレーム時間を見て決める |
| Lamp at the door / 戸口の灯り | An unglazed clay oil lamp, hung beside the door or placed in a small niche in the wall, lit after dark [inferred] / 素焼きの油ランプを一つ、戸の脇に掛けるか壁の小さな壁龕に置き、暗くなったら灯す〔推定〕 |

## 3. Shared rules / 共通ルール

1. **Saturation**: the mean base color of environment materials has an HSV saturation of at most 0.45 (roof tiles and pottery are the highest), and limestone and plaster at most 0.25. That way the characters' clothes (Melos's ochre 0.62, the traveler's sea color 0.37) all stand out from the background, and scarlet (0.80) stands out most.
   **彩度**：環境マテリアルの下地の平均色は HSV 彩度 0.45 以下（瓦と陶器が最も高い）、石灰岩と漆喰は 0.25 以下。こうすれば人物の衣服（メロスの黄土 0.62、旅人の海の色 0.37）はどれも背景より際立ち、緋色（0.80）が最も際立つ。
2. **Both tiers from the same source** (art-direction 9.5): 2048 and 1024 are downscaled from the same source image. Frontend's `scene.json` already records the mean color of each texture at both tiers; at the acceptance check, each channel differs by at most 2.
   **二つのティアは同じ元画像から**（art-direction 9.5）：2048 と 1024 は同じ元画像から縮小する。フロントエンドの `scene.json` には各テクスチャの両ティアの平均色がすでに記録されている。受け入れ確認では各チャンネルの差が 2 以下。
3. **No visible repetition**: looking down from the exploration camera about 15 m away, the ground and walls show no repeating pattern. Break it up with large-scale variation, e.g. the lightmap's AO, or one dirt mask over the whole scene [frontend decides how].
   **繰り返しを見せない**：探索カメラで約 15 m 離れたところから見下ろしても、地面と壁に繰り返しの模様が見えない。大きなスケールの変化で崩す。たとえばライトマップの AO や、シーン全体を覆う一枚の汚れマスク〔方法はフロントエンドが決める〕。
4. **How much one texture covers**: go by the real size of the scan so the stones are the right size (paving slabs 60–120 cm each, royal castle courses 45–60 cm high). Frontend's current values are 3 m per tile for the ground and 6 m for walls. If the wall behind the dialogue camera is blurry on tier B, shrink walls to 4 m per tile [UX suggestion; frontend decides].
   **一枚のテクスチャがどれだけの大きさを表すか**：スキャンの実寸に合わせ、石の大きさを正しくする（石畳は 1 枚 60〜120 cm、王城の石は 1 段の高さ 45〜60 cm）。フロントエンドの現在の値は地面が 1 枚 3 m、壁が 6 m。会話カメラの背後の壁がティア B でぼやけるなら、壁を 1 枚 4 m に縮める〔UX の提案、フロントエンドが決める〕。
5. **Dirt and wear follow people**: the bottom ~30 cm of walls darkened; doorways, the middles of steps and the line from the city gate to the pillar trodden bright; the area around the fountain wet and dark. Corners where nobody walks have dust and dry grass.
   **汚れと摩耗は人の動きに従う**：壁の足元約 30 cm は暗く、戸口、階段の中央、城門から柱への線は踏まれて明るく、噴水のまわりは濡れて暗い。人の通らない隅には埃と枯れ草。
6. **Texture must read in low-angle light**: at 17:30 and 18:50 the sun is very low, and chisel marks, stone joints and the relief of tiles must show in the raking light. Normal strength is tuned at these two times.
   **低い角度の光で質感が読み取れること**：17:30 と 18:50 は太陽がとても低く、鑿の跡、石の目地、瓦の起伏が横からの光で見えなければならない。法線の強さはこの二つの時刻で調整する。
7. **No light in the color map**: choose "unlit" color maps (albedo). Scans with the shoot's sunlight and hard shadows baked into the color map are not used.
   **色マップに光を入れない**：「ライティングなし」の色マップ（albedo）を選ぶ。撮影時の日差しと硬い影が色マップに焼き込まれたスキャンは使わない。

## 4. Choosing scanned assets (CC0) / スキャン素材の選び方（CC0）

- **Sources**: CC0 scanned materials such as Poly Haven and ambientCG. Each one's source, license and sha256 are recorded in `assets/manifest/` (F-2 card, S-075); source files do not go into the repository.
  **入手元**：Poly Haven、ambientCG などの CC0 のスキャンマテリアル。一枚ごとの入手元、ライセンス、sha256 を `assets/manifest/` に記録する（F-2 カード、S-075）。元ファイルはリポジトリに入れない。
- **Downloading**: the project container cannot reach these sites, so they are downloaded on zg's Mac, with zg's consent first. UX does not download, does not spend money, and does not buy assets.
  **ダウンロード**：プロジェクトのコンテナからはこれらのサイトにアクセスできないので、zg の Mac でダウンロードし、事前に zg の同意を得る。UX はダウンロードせず、お金を使わず、素材も買わない。
- **How to choose**: for each material, frontend picks 2–3 candidates, places them in F-2b's square, and takes one screenshot each at 17:30 and 18:50 from the same camera; UX chooses from those. Do not choose from the thumbnails on the sites: thumbnails are shot under neutral light and change in the setting sun.
  **選び方**：フロントエンドはマテリアルごとに候補を 2〜3 個選び、F-2b の広場に置き、同じカメラで 17:30 と 18:50 にそれぞれ 1 枚ずつスクリーンショットを撮る。UX はその中から選ぶ。サイトのサムネイルで選ばない：サムネイルは中性の光で撮られていて、夕日の下では変わる。
- **Run art-direction 4.3's table first**, then look specifically for these things that often slip in:
  **まず art-direction 4.3 の表を通し**、それから次のよく紛れ込むものを特に確認する：

| Avoid / 避けるもの | Often found in / よく出てくる場所 |
|---|---|
| Cement mortar joints (gray, straight, uniform width) / セメントモルタルの目地（灰色、まっすぐ、幅が一定） | Stone-wall scans. Greek ashlar walls are dry-laid / 石壁のスキャン。ギリシアの切石の壁は空積み |
| Machine-sawn, uniform square paving slabs; curbstones, asphalt, concrete / 機械で切った同じ大きさの四角い石板、縁石、アスファルト、コンクリート | Ground scans / 地面のスキャン |
| Drill holes, rust, rebar, wires, graffiti, oil stains / ドリルの穴、錆、鉄筋、電線、落書き、油染み | Walls and ground / 壁と地面 |
| Red brick; modern machine-made tiles / 赤煉瓦、現代の機械製の瓦 | Walls and roofs / 壁と屋根 |
| Cactus and agave leaves, fallen citrus fruit, cigarette butts, plastic / サボテンやリュウゼツランの葉、柑橘の落ちた実、吸い殻、プラスチック | Debris mixed into ground scans / 地面のスキャンに紛れ込んだごみ |
| Sunlight and hard shadows from the shoot / 撮影時の日差しと硬い影 | Color maps (see section 3, item 7) / 色マップ（第 3 節第 7 項を参照） |

## 5. Acceptance check (viewed in F-2b, tier B first) / 受け入れ確認（F-2b で見る。まずティア B）

1. **First screen** (17:30, from the southwest corner facing northeast, art-direction section 10): the paving and the royal castle's walls are a honey-tinted white, golden but not orange. Melos, the old man and the traveler standing on them separate at a glance.
   **最初の画面**（17:30、南西の角から北東を向く、art-direction 第 10 節）：石畳と王城の壁は蜜色がかった白で、金色を帯びるがオレンジではない。その上に立つメロス、老爺、旅人が一目で区別できる。
2. **Sunset** (18:50–19:00): the most saturated thing in the frame is the traveler's sash; the roof tiles and awnings are both paler than it (art-direction 6).
   **日没**（18:50〜19:00）：画面で最も彩度の高いものは旅人の腰帯で、瓦も日よけもそれより淡い（art-direction 6）。
3. **Exploration camera**: viewing the ground and walls from about 15 m away, no repetition is visible.
   **探索カメラ**：約 15 m 離れたところから地面と壁を見て、繰り返しが見えない。
4. **Dialogue camera** (1–3 m): the wall and door behind do not blur into a mush on tier B; you can tell stone and wood.
   **会話カメラ**（1〜3 m）：背後の壁と扉がティア B でひとかたまりにぼやけず、石と木だと分かる。
5. **Tier up / down**: the color does not change at the switch, it just gets sharper (9.5); in `scene.json` the mean colors at the two tiers differ by at most 2 per channel.
   **ティアの昇降**：切り替えの瞬間に色が変わらず、鮮明になるだけ（9.5）。`scene.json` の両ティアの平均色は各チャンネルの差が 2 以下。
6. **Period**: none of the things in 4.3 or the table in section 4 appear.
   **時代**：4.3 と第 4 節の表にあるものが一つもない。

## Needed later (not in F-2b) / 今後必要なもの（F-2b には含まない）

- Goods on the stalls (bread, olives, cloth, pottery) and the execution-ground crowd (art-direction 5.5).
  露店の品物（パン、オリーブ、布、陶器）と刑場の群衆（art-direction 5.5）。
- Light-source props for night: oil lamps, braziers (art-direction 3.2).
  夜の光源となる小道具：油ランプ、火鉢（art-direction 3.2）。
- Materials for the throne room, the village and the way back: delivered with each scene's design (art-direction 9.3 already lists each scene's 2048 materials).
  玉座の間、村、帰り道のマテリアル：それぞれのシーン設計と一緒に出す（art-direction 9.3 に各シーンの 2048 マテリアルがすでに挙がっている）。
