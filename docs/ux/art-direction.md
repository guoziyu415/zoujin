# Art direction (art-direction.md) v1.4.3: realism / 画風の方向性（art-direction.md）v1.4.3：リアル

| Item / 項目 | Content / 内容 |
|---|---|
| Purpose / 用途 | The target look for D-016's “high-definition, stunning, realistic”. A reference for Frontend when building the S7 realism prototype and, later, the art assets; PM uses the checkpoints in section 10 when taking it to zg / D-016「高精細、目を見張る、リアル」の目標とする画面。フロントエンドが S7 のリアル版プロトタイプや今後のアートアセットを作るときに照らし合わせる。PM が zg に確認しに行くときは第 10 節のチェックポイントを使う |
| Author / 作成者 | UX (division of work with Frontend: UX sets the target look; Frontend builds the S7 test page and measures frame time and load time on iPhone; the technical tiers are written in frontend-design 10.6) / UX（フロントエンドとの分担：UX が目標の画面を決め、フロントエンドが S7 のテストページを作り、iPhone でフレーム時間と読み込み時間を測る。技術的なティアは frontend-design 10.6 に書く） |
| Basis / 根拠 | `docs/pm/decisions.md` D-016, D-019 (tier B as the base, automatic upgrade on high-end phones), S-014 (performance budget), S-036 (zero time margin), S-055 (the card illustration is a frame of the ending set piece); `docs/data/contracts.md` 2.6 (sunset = 19:00, `sunsetMinuteOfDay` 1140) and 2.8 (act table); the original Aozora Bunko text (`worlds/hashire-merosu/sources/`); Frontend's two technical facts from 2026-10-06 about baked lighting and Gaussian Splatting / `docs/pm/decisions.md` D-016、D-019（ティア B を基本とし、高性能機は自動で上げる）、S-014（性能予算）、S-036（時間の余裕はゼロ）、S-055（カードのイラストはエンディング演出の 1 フレーム）；`docs/data/contracts.md` 2.6（日没 = 19:00、`sunsetMinuteOfDay` 1140）と 2.8（幕の表）；原作の青空文庫版（`worlds/hashire-merosu/sources/`）；ベイクしたライティングと Gaussian Splatting についてのフロントエンドの 2026-10-06 の 2 つの技術的事実 |
| Prototype / プロトタイプ | Realism prototype = Frontend's S7 (`frontend/spikes/s7-realism/`; UX's review is at [reviews/frontend-s7.md](reviews/frontend-s7.md)). The A 絵本 / B 木版 / C 影絵 in the UX prototype [prototype/plaza.html](prototype/plaza.html) are the old v0.1 prototypes, kept for comparison; see appendix A / リアル版プロトタイプ = フロントエンドの S7（`frontend/spikes/s7-realism/`、UX のレビューは [reviews/frontend-s7.md](reviews/frontend-s7.md)）。UX プロトタイプ [prototype/plaza.html](prototype/plaza.html) の A 絵本／B 木版／C 影絵 は v0.1 の旧プロトタイプで、比較用に残している。付録 A を参照 |
| Last updated / 最終更新 | 2026-10-10 |

---

## 0. Conclusions / 結論

1. **Realistic light, restrained people.** “Stunning” comes mainly from light and air, not polygons. The sun, the sky, long shadows, dust and haze in the air, the color of stone lit by the setting sun: these are the cheapest and most effective parts of realism, so the budget goes here first.
   **リアルな光、控えめな人物。** 「目を見張る」は主に光と空気から生まれ、ポリゴンからではない。太陽、空、長い影、空気中の土埃ともや、夕日に照らされた石の色。これらはリアルさの中でいちばん安く、いちばん効果が大きいので、予算はまずここに使う。
2. **The one image that must be best is the plaza at sunset.** Act 1 starts here, act 4 ends here, and the ending card illustration is taken from here too (S-055). The first thing the player sees is the plaza in the evening.
   **いちばんよく作るべき画面は日没の広場。** 第一幕はここから始まり、第四幕はここで終わり、エンディングカードのイラストもここから取る（S-055）。プレイヤーが最初に目にするのは夕方の広場だ。
3. **The sun is the clock, and it is visible in the world.** The plaza is laid out by the real sun direction: at sunset the sun sinks right into the western gate street, and the royal castle is to the east. As the sun goes down, the shadow edge climbs up the castle wall, and the last ray of light stays on top of the tower. The original says 「まさに最後の一片の残光も、消えようとした時」, and the image is this very moment (3.4).
   **太陽が時計であり、それは世界の中で見える。** 広場は実際の太陽の方位に合わせて配置する：日没のとき、太陽はちょうど西の城門の大通りに沈み、王城は東にある。太陽が沈むにつれて影の境目が王城の壁を上っていき、最後の光が塔の頂に残る。原作の「まさに最後の一片の残光も、消えようとした時」、画面はこの瞬間だ（3.4）。
4. **Characters: real proportions, real cloth and skin, but no pores.** On a phone during dialogue, the face is only about 2 cm tall (5.2). Realism goes into movement, gaze and mouth shapes, not skin detail. The face must never be more realistic than its movement, or it falls into the uncanny valley.
   **人物：実際の人体のプロポーション、本物の布と肌。ただし毛穴は作らない。** スマートフォンでの会話中、顔の高さは約 2 cm しかない（5.2）。リアルさは動き、視線、口の形に使い、肌のディテールには使わない。顔のリアルさが動きのリアルさを超えてはならない。超えると不気味の谷に落ちる。
5. **緋色 is only for “what you change”**; this rule stays as before (section 6).
   **緋色は「あなたが変えたもの」だけに使う**。このルールは従来どおり（第 6 節）。

---

## 1. What this world should convey / この世界が伝えるべきこと

- **The world of the original**: the city of Syracuse (シラクス) in ancient Sicily, the royal castle, the village, the river, the mountain road. The season is early summer (「初夏、満天の星である」). Stone, clay tiles, olives and cypresses everywhere.
  **原作の世界**：古代シチリアの都市シラクス、王城、村、川、山道。季節は初夏（「初夏、満天の星である」）。どこもかしこも石、瓦、オリーブ、糸杉。
- **Dazai's narration**: short sentences, urgent, hot. The realistic image has to keep that “heat” and “urgency”: the strong summer light, the dust, the panting of running. Don't shoot it as a quiet postcard.
  **太宰の語り**：短い文、せき立てるようで、熱い。リアルな画面でもこの「熱さ」と「急き」を保つ：夏の強い光、土埃、走る息づかい。静かな絵はがきのように撮ってはいけない。
- **The real geography happens to match the original**:
  **実際の地理が、ちょうど原作と合う**：
  - Syracuse is on the east coast of Sicily, with the sea to the east and the inland Hyblaean Mountains (Monti Iblei) to the west. So the sun sets behind the mountains, not into the sea.
    シラクスはシチリアの東岸にあり、東は海、西は内陸のイブレイ山地（Monti Iblei）。だから太陽は海ではなく山の向こうに沈む。
  - Melos's village is inland, and on his way back to the city he **runs east with the setting sun at his back**. In the original, he sees from far down the road 「シラクスの市の塔楼が見える。塔楼は、夕陽を受けてきらきら光っている」: the towers shine as they face the setting sun, which means the sun is behind him.
    メロスの村は内陸にあり、市へ戻るとき彼は**夕日を背にして東へ走る**。原作では道の遠くから「シラクスの市の塔楼が見える。塔楼は、夕陽を受けてきらきら光っている」。塔楼が夕日を受けて光るのは、太陽が彼の背後にあるということだ。
  - 「赤く大きい夕陽ばかりを見つめていた」 means he keeps looking back at the sun while running, to see how much is left.
    「赤く大きい夕陽ばかりを見つめていた」は、走りながら振り返って、太陽があとどれだけ残っているかを見ているのだ。
- **Two sunsets in the same plaza**:
  **同じ広場の 2 つの日没**：
  - Act 1: when Melos enters the city 「もう既に日も落ちて」, and the city 「ひっそりしている」. This is the blue afterglow **after** sunset: cold, few people, hardly any lit windows.
    第一幕：メロスが市に入るとき「もう既に日も落ちて」、市は「ひっそりしている」。これは日没**後**の青い残照で、冷たく、人が少なく、窓の灯もほとんどない。
  - Act 4: the last red light **before** sunset, hot, the execution ground packed with people.
    第四幕：日没**前**の最後の赤い光。熱く、刑場は人で埋まっている。
  - One image is cold and the other hot; light alone tells them apart, helped by the crowd and the sound.
    一方は冷たく、一方は熱い。光だけで見分けられ、そこに群衆と音が加わる。

---

## 2. References (what to learn from each) / 参考（それぞれから何を学ぶか）

Learn only the methods from the references; **do not use their assets, images or characters**.

参考からは手法だけを学び、**その素材、画面、人物は使わない**。

| Reference / 参考 | What to learn / 学ぶこと | What not to learn / 学ばないこと |
|---|---|---|
| The game 『アサシン クリード オデッセイ』 (Assassin's Creed Odyssey, 2018) and its Discovery Tour / ゲーム『アサシン クリード オデッセイ』（2018）とその Discovery Tour | The limestone, clay tiles and plaster of ancient Greek cities, and the feel of the air under strong Mediterranean light. Syracuse was a Greek colony to begin with, so the materials can be compared directly / 古代ギリシャの都市の石灰岩、瓦、漆喰と、地中海の強い光の下の空気感。シラクスはもともとギリシャの植民都市なので、素材はそのまま照らし合わせられる | Postcard-style oversaturated blue skies; UI all over the screen / 絵はがきのような彩度の高い青空、画面いっぱいの UI |
| The film 『天国の日々』 (Days of Heaven, 1978, cinematography by ネストール・アルメンドロス) / 映画『天国の日々』（1978、撮影 ネストール・アルメンドロス） | Mostly shot at “magic hour”: the sun very low, characters with backlit outlines, the color of the sky itself carrying mood and time. The plaza at sunset learns from this / 大部分を「マジックアワー」に撮影している：太陽がとても低く、人物には逆光の輪郭があり、空の色そのものが感情と時間を表す。日没の広場はこれに学ぶ | Overly long empty shots / 長すぎる風景だけのショット |
| The game 『A Plague Tale: Requiem』 (2022) / ゲーム『A Plague Tale: Requiem』（2022） | How far faces go in a realistic game: proportions, cloth and light are all realistic, skin doesn't chase pores, and expressions and posture read even at a distance. Its southern French summer light is also close to our Sicily / リアルなゲームで人の顔をどこまで作るか：プロポーション、布、光はすべてリアルで、肌は毛穴まで追わず、遠くからでも表情と姿勢が読み取れる。南フランスの夏の光も私たちのシチリアに近い | The overall grayish, dark grading / 全体に灰色がかった暗めのカラーグレーディング |
| The game 『Ghost of Tsushima』 (2020) / ゲーム『Ghost of Tsushima』（2020） | “Stunning” comes from wind, floating particles and a different grade for each time of day, not from texture resolution. Wind moves grass, awnings and hems, keeping the world alive / 「目を見張る」は風、漂う粒子、時刻ごとに違うカラーグレーディングから生まれ、テクスチャの精度からではない。風が草、日よけの布、衣の裾を揺らし、世界を生かしている | Its stylized, oversaturated grading; we want more restraint / 様式化された彩度の高いグレーディング。私たちはもっと控えめにする |
| The film 『バリー・リンドン』 (Barry Lyndon, 1975) / 映画『バリー・リンドン』（1975） | Interiors at night lit only by fire; the dark areas have color, not dead black. The throne room at night learns from this / 夜の室内は火の明かりだけ。暗部には色があり、真っ黒ではない。夜の王座の間はこれに学ぶ | The overly slow pace / 遅すぎるテンポ |

---

## 3. Light: the sun is the clock / 光：太陽が時計

### 3.1 How the sun moves / 太陽の動き

Using Syracuse's latitude (37°N) in early summer, the solar declination is taken as +19° (about mid-May). The sun then sets at exactly **19:00**, matching the data world model's sunset (`sunsetMinuteOfDay` = 1140). The table below gives values computed with the astronomical formula; Frontend can use the same formula directly, computing continuously from story time `t` rather than jumping between a few presets.

シラクスの緯度（北緯 37°）、初夏で、太陽の赤緯は +19°（5 月中旬ごろ）とする。こうすると太陽はちょうど **19:00** に沈み、データの世界モデルの日没（`sunsetMinuteOfDay` = 1140）と一致する。下の表は天文の公式で計算した値で、フロントエンドは同じ公式をそのまま使い、物語の時刻 `t` に合わせて連続的に計算できる。いくつかのプリセットの間で飛ばさない。

| Story time / 物語の時刻 | Elevation / 高度角 | Azimuth (north 0°, clockwise) / 方位（真北 0°、時計回り） | Shadow length to object height / 影の長さと物の高さの比 | Notes / 説明 |
|---|---|---|---|---|
| 04:30 | −5° | — | — | Twilight; Melos sets out in the rain (end of act 3, in the village); those who stayed in the city start act 4 from here / 薄明。メロスが雨の中を出発する（第三幕の最後、村）。市に残った人は第四幕をここから始める |
| 05:00 | 0° | 66° (east-northeast) / 66°（東北東） | — | Sunrise / 日の出 |
| 06:00 | 11° | 75° | 5× / 5 倍 | Morning / 朝 |
| 09:00 | 47° | 102° | 0.9× / 0.9 倍 | Late morning / 午前 |
| 12:00 | 72° | 180° (due south) / 180°（真南） | 0.3× / 0.3 倍 | Midday; shadows shrink under feet and eaves / 真昼。影は足元と軒下に縮む |
| 16:00 | 35° | 268° (due west) / 268°（真西） | 1.4× / 1.4 倍 | Evening (夕方) begins / 夕方の始まり |
| 17:30 | 17° | 281° | 3.2× / 3.2 倍 | Act 1 opens (17:30, traveler and apprentice) / 第一幕の開始（17:30、旅人と弟子） |
| 18:00 | 11° | 285° | 5× / 5 倍 | The whole plaza floor is in shadow (3.4) / 広場の地面がすべて影に入る（3.4） |
| 18:30 | 6° | 290° | 10× / 10 倍 | The shadow edge has climbed halfway up the castle wall / 影の境目が王城の壁の半分まで上る |
| 19:00 | 0° | 294° (west-northwest) / 294°（西北西） | — | **Sunset = the deadline**. The last ray of light leaves the top of the tower / **日没 = 期限**。最後の光が塔の頂から消える |
| 19:30 | −5° | — | — | Afterglow, the blue hour; Melos enters the city in act 1 / 残照、青い時間。第一幕でメロスが市に入る |
| 20:00 | −10° | — | — | Dark; stars begin to appear / 暗くなり、星が見え始める |

### 3.2 What each time of day looks like / 時刻ごとの見え方

The color temperatures are starting values for the direct light 〔inference, based on commonly measured ranges〕; Frontend tunes them in S7 against what real phones show.

色温度は直射光の初期値〔推定、一般的な実測範囲に基づく〕。フロントエンドが S7 で実機の画面を見ながら調整する。

| Time / 時刻 | Sun and direct light / 太陽と直射光 | Sky / 空 | Shadows / 影 | Air / 空気 | Artificial light / 人工の光 | Where used / 使う場面 |
|---|---|---|---|---|---|---|
| Twilight / 薄明 | No direct light / 直射光なし | Gray-blue, the eastern horizon turning white / 灰青色、東の地平線が白む | None / なし | Damp after the rain, mist over the river / 雨上がりの湿気、川に霧 | Hearth fires in the village / 村のかまどの火 | End of act 3, Melos sets out in the rain; the start of act 4 for those who stayed in the city: cold, wet, departure / 第三幕の最後にメロスが雨の中を出発する。市に残った人の第四幕の冒頭：冷たく、湿って、出発 |
| Morning, late morning / 朝・午前 | 11°〜60°, about 4500〜5500K / 11°〜60°、約 4500〜5500K | Clear blue, thin haze from the sea in the distance / 澄んだ青、遠くに海から来る薄いもや | Medium length, crisp edges / 中くらいの長さ、輪郭がはっきり | Fresh / 爽やか | None / なし | The village on day 1; following Melos to the river in act 4 (day 3, before noon, the rain just stopped, the ground still wet) / 一日目の村。第四幕でメロスについて川へ行くとき（三日目・昼前、雨が上がったばかりで地面はまだ濡れている） |
| Midday, afternoon / 真昼・午後 | 60°〜72°, about 5500〜6000K / 60°〜72°、約 5500〜6000K | Deep blue overhead, the horizon whitish / 頭上は深い青、地平線は白っぽい | Very short and hard, gathered under eaves and feet / とても短く硬く、軒下と足元に集まる | Heat shimmer, bleached highlights / 陽炎、白っぽいハイライト | None / なし | The wedding at noon on day 2 (then it clouds over and rains); act 4's 「午後の灼熱の太陽」 / 二日目正午の婚礼（その後曇って雨になる）。第四幕の「午後の灼熱の太陽」 |
| Evening, before sunset / 夕方・日没前 | 35°→0°, about 4000K → 2000K, getting redder / 35°→0°、約 4000K → 2000K、だんだん赤くなる | Gold → orange-red / 金色 → 橙赤色 | Longer and longer, finally covering the whole plaza / どんどん長くなり、最後は広場全体を覆う | Dust glowing in the backlight / 逆光の中で土埃が光る | Lamps just starting to be lit / 灯がともり始める | The opening of act 1; the end of act 4; at the spring on the homeward road, 「斜陽は赤い光を、樹々の葉に投じ」 / 第一幕の冒頭。第四幕の最後。帰り道の泉のほとり「斜陽は赤い光を、樹々の葉に投じ」 |
| Afterglow after sunset / 日没後の残照 | No direct light / 直射光なし | A band of orange in the west, deep blue above it; a pink band over the sea to the east (the 「ヴィーナスベルト」 above the Earth's shadow) / 西に橙色の帯、その上は深い青。東の海の上にピンクの帯（地球影の上の「ヴィーナスベルト」） | Almost none, very soft / ほとんどなく、とてもやわらかい | Cooling down / 涼しくなる | A few windows / わずかな窓 | Melos enters the city in act 1 (「ひっそりしている」) / 第一幕でメロスが市に入る（「ひっそりしている」） |
| Night, late night / 夜・深夜 | No moon (the original's 「満天の星」) / 月なし（原作「満天の星」） | A sky full of stars; at midnight the Milky Way slants low in the southeast / 満天の星。真夜中には天の川が南東に低く斜めにかかる | Only shadows cast by lamps and fires / 灯火が落とす影だけ | Cold, blue / 冷たく、青い | Oil lamps and braziers, about 1800〜2000K, flickering slightly / 油のランプと火鉢、約 1800〜2000K、わずかに揺らめく | The second half of act 1 (the castle), act 2 / 第一幕の後半（王城）、第二幕 |
| Rain / 雨 | Overcast, flat light, about 6500〜7500K / 曇天、フラットな光、約 6500〜7500K | Low, heavy clouds (「黒雲が空を覆い」) / 低く重い雲（「黒雲が空を覆い」） | None / なし | Streaks of rain, gray in the distance / 雨の筋、遠くは灰色にかすむ | Hearth fires / かまどの火 | The afternoon of day 2 through twilight on day 3; on the homeward road the river is a muddy yellow 濁流 / 二日目の午後から三日目の薄明まで。帰り道の川は濁った黄色の濁流 |

- **Night uses film's day-for-night technique**: the image leans blue with lower saturation, but exposure is not pushed too low; characters and paths must stay clearly visible.
  **夜は映画の「デイ・フォー・ナイト」（昼間に夜景を撮る）手法を使う**：画面を青寄りにして彩度を下げるが、露出は下げすぎず、人物と道ははっきり見えるようにする。
- **At any time of day, characters must stand out from the background**:
  **どの時刻でも、人物は背景から見分けられなければならない**：
  - in the evening and before sunset, a backlit character gets a bright rim;
    夕方と日没前、逆光の人物には明るい縁取りが付く。
  - the face is filled by warm light bouncing up off the sunlit flagstones. This is the most realistic and most beautiful light in this plaza: the limestone reflects the setting sun onto people's faces;
    顔は、照らされた石畳から照り返す暖かい光で明るくする。これがこの広場でいちばんリアルで、いちばん美しい光だ。石灰岩が夕日を人の顔へ反射する。
  - at night, there must be a lamp or fire near the character.
    夜は、人物の近くに灯火が必要。
- **Fill light in the shadows comes from both above and below**: above is the sky (bluish), below is the lit ground (limestone bounces warm light). While the ground is in sunlight, the side facing away from the sun cannot get only skylight: light warm colors (beige wool, limestone) lit only by the sky turn cyan-green (A-0 Melos round 5: in the exploration camera, the bundle on his back turned into a cyan patch). So the ambient light must include the ground, and its color follows how brightly the ground is lit. When the ground is also in shadow (the plaza after 17:30), this fill is naturally weak and cool, and the cold shadows of the first screen stay as they are. This cannot be replaced by color grading, because grading cannot tell skylight from ground bounce.
  **影の中の補助光は上下の両方から来る**：上は空（青寄り）、下は照らされた地面（石灰岩の照り返しは暖かい）。地面が日なたにあるとき、日の当たらない側を空の光だけにしてはいけない：明るい暖色（ベージュの羊毛、石灰岩）が空の光だけで照らされると青緑になる（A-0 メロス第 5 ラウンド：探索カメラで背中の包みが青い塊になった）。だから環境光には地面を含め、その色は地面の照らされ具合に従う。地面も影の中にあるとき（17:30 以降の広場）は、この補助光は自然に弱く冷たくなり、最初の画面の冷たい影は変わらない。これはカラーグレーディングでは代用できない。グレーディングでは空の光と地面の照り返しを区別できないからだ。

### 3.3 Four times of day, told apart at a glance / 4 つの時刻をひと目で見分ける

PM asked that evening, late night, midday and sunset be distinguishable at a glance. This relies on three cues that **have nothing to do with color**, so players with different color vision can tell them apart too:

PM は夕方、深夜、真昼、日没をひと目で見分けられるよう求めた。頼りにするのは**色に関係しない** 3 つの手がかりで、色覚の異なるプレイヤーでも見分けられる：

| | Overall brightness / 画面全体の明るさ | Shadows / 影 | Brightest part of the sky / 空のいちばん明るいところ |
|---|---|---|---|
| Midday / 真昼 | Brightest, highlights blown white / いちばん明るく、ハイライトが白く飛ぶ | Shortest, under the feet / いちばん短く、足元にある | Overhead / 頭上 |
| Evening / 夕方 | Bright / 明るい | Long. Around 16:00 they stretch diagonally across the plaza; by 17:30 the shadows of the western houses already cover the plaza, and only the whole castle wall is golden / 長い。16:00 前後は斜めに広場を横切る。17:30 には西の家々の影がすでに広場を覆い、王城の壁全面だけが金色 | The west, with the sun still partway up the sky / 西。太陽はまだ中空にある |
| Sunset / 日没 | Medium; only high places are lit / 中くらい。高いところだけが明るい | Covering the ground; only the upper half of the walls and the tower have light / 地面を覆い尽くし、壁の上半分と塔だけに光がある | The western horizon, where the sun is sinking right into the gate / 西の地平線。太陽がちょうど城門に沈んでいく |
| Late night / 深夜 | Darkest / いちばん暗い | Only shadows from lamps and fires / 灯火の影だけ | None; a sky full of stars / なし。満天の星 |

The sun band in the UI (ux-design 4.2) is always there. The image is only responsible for letting people “feel” the time; it does not replace the sun band.

UI の太陽帯（ux-design 4.2）は常にある。画面の役割は時刻を「感じさせる」ことだけで、太陽帯の代わりにはならない。

### 3.4 Two clocks visible in the world / 世界の中で見える 2 つの時計

**① The shadow edge climbing the castle wall** (the plaza, the opening of act 1 and the end of act 4)

**① 王城の壁を上っていく影の境目**（広場、第一幕の冒頭と第四幕の最後）

- The houses on the west side of the plaza block the low sun, and their shadow falls on the castle wall to the east. The lower the sun, the higher the shadow edge climbs.
  広場の西側の家々が低い太陽を遮り、その影が東の王城の壁に落ちる。太陽が低いほど、影の境目は高く上る。
- Illustration (the numbers are only for explanation; check with the real-time sun once the scene is built): the western houses are 8m tall and 40m from the castle wall.
  例示（数字は説明のためだけで、シーンを組んだらリアルタイムの太陽で確かめる）：西の家の高さは 8m、王城の壁までは 40m。
  - 18:00, the whole plaza floor is in shadow;
    18:00、広場の地面がすべて影に入る。
  - 18:30, the shadow edge has climbed about 4m up the wall;
    18:30、影の境目が壁の約 4m まで上る。
  - 19:00, only the part of the wall above 8m is still lit. The top of the tower, taller than the western houses, stays lit last and goes dark the moment the sun sinks.
    19:00、壁で光が残るのは 8m より上だけ。西の家より高い塔の頂が最後まで光り、太陽が沈むと同時に消える。
- 磔の柱 stands in front of the castle, and the head of セリヌンティウス, hung up on it, is exactly one of the last places in the plaza to have light just before sunset.
  磔の柱は王城の前に立ち、吊り上げられたセリヌンティウス の頭部は、日没間際の広場で最後まで光が当たる場所のひとつになる。
- This line needs no UI element; the player only has to look up to know how much time is left. So the plaza must use a **real-time sun and shadows**; this part of the light cannot be fully baked (see 3.5).
  この線には UI 要素はいらない。プレイヤーは見上げるだけで、あとどれだけ時間があるか分かる。だから広場は**リアルタイムの太陽と影**を使わなければならず、この部分の光を丸ごとベイクしてはならない（3.5 参照）。

**② The glint of the distant towers** (the homeward road, act 4)

**② 遠くの塔楼の照り返し**（帰り道、第四幕）

- From the homeward road the towers are seen far away: 「塔楼は、夕陽を受けてきらきら光っている」.
  帰り道から遠くに塔楼が見える：「塔楼は、夕陽を受けてきらきら光っている」。
- The distant view on the homeward road must show the towers of Syracuse, their western faces lighting up in the evening.
  帰り道の遠景ではシラクスの塔楼が見え、夕方には塔楼の西面が明るく輝くようにする。
- This is act 4's “almost there, but will he make it?” image, and it also tells the player which way to run.
  これは第四幕の「もうすぐだ、でも間に合うのか」の画面であり、どちらへ走ればよいかもプレイヤーに伝える。

### 3.5 Priorities for Frontend (relation to baking and Gaussian Splatting) / フロントエンドへの優先順位（ベイクと Gaussian Splatting との関係）

Frontend raised two technical facts: baked lighting is valid only for a fixed sun position, and Gaussian Splatting freezes the light at capture time. UX's trade-offs:

フロントエンドから 2 つの技術的事実が挙がった：ベイクしたライティングは固定した太陽の位置でしか成り立たない。Gaussian Splatting は撮影時の光を中に固定してしまう。UX の判断：

1. **The plaza's sun and shadows must be computed in real time**, because the shadow clock in 3.4 is a game mechanic. Bake only the parts that don't depend on the sun (ambient occlusion, skylight).
   **広場の太陽と影は必ずリアルタイムで計算する**。3.4 の影の時計はゲームの仕組みそのものだからだ。ベイクするのは太陽に関係しない部分（アンビエントオクルージョン、空の光）だけ。
2. **If some scenes need a separate bake per time slot**, the priority is: before sunset and sunset > afterglow and night > midday > morning and twilight. Sunset is the opening, the finale and the ending card, the most often seen and screenshotted.
   **時間帯ごとに別々にベイクするシーンがあるなら**、優先順位は：日没前と日没 > 残照と夜 > 真昼 > 朝と薄明。日没は冒頭、結末、エンディングカードであり、いちばん多く見られ、スクリーンショットされる。
3. **The homeward road is built per stop** (S-081, decided by PM 2026-10-10): in act 4 you follow Melos past 川 (late morning after the rain → midday), 峠 (the blazing afternoon sun), 泉 (afternoon → evening) and 市へ続く野の道 (before sunset), with stretches of running side by side between the stops; act 2 stops only at 川 (twilight), and the rest is one continuous night road. Each stop is seen at only one or two times of day, so each stop gets one baked set of skylight and occlusion for that time (one set for each of the river's two states, 5 sets in total), while the sun is still computed in real time; the running stretches use only real-time light. The order of the 5 sets follows item 2 above: 野の道 > 泉 > 峠, act 4's 川 > act 2's 川. Layout, light and materials are in [scenes/homeward-road.md](scenes/homeward-road.md).
   **帰り道は停留地点ごとに作る**（S-081、2026-10-10 PM 決定）：第四幕ではメロスについて 川（雨上がりの午前 → 真昼）、峠（午後の烈日）、泉（午後 → 夕方）、市へ続く野の道（日没前）を通り、地点と地点の間は並んで走る区間になる。第二幕は川（薄明）にだけ止まり、残りはひと続きの夜道。各地点は 1〜2 つの時刻にしか見られないので、地点ごとにその時刻の空の光と遮蔽を 1 セットずつベイクし（川は 2 つの状態に 1 セットずつ、計 5 セット）、太陽はやはりリアルタイムで計算する。走る区間はすべてリアルタイムの光を使う。5 セットの順番は上の第 2 項に従う：野の道 > 泉 > 峠、第四幕の川 > 第二幕の川。平面図、光、マテリアルは [scenes/homeward-road.md](scenes/homeward-road.md) を参照。
4. **The first version does not use Gaussian Splatting.** The light changes in every one of our scenes, so even the distant views would be lit wrong. For the distant mountains, a sky shader plus a few layers of silhouettes is enough, with the silhouettes changing with the sky.
   **最初の版では Gaussian Splatting を使わない。** 私たちのシーンはどれも光が変わるので、遠景まで間違った光になってしまう。遠くの山は空のシェーダーに数層のシルエットを重ねれば足り、シルエットは空の色に合わせて変える。

---

## 4. Places and materials / 場所とマテリアル

### 4.1 Layout requirements for the plaza / 広場の配置の要件

```
West (294°, direction of sunset)                                              East (toward the sea)
City gate ═ West street ═ Plaza [stalls, fountain, old man's house, stonemason's workshop] ═ 磔の柱 ─ Castle steps ─ Tower
  ↑ 19:00 the sun sets right into this street   ↑ 18:00 the ground is fully in shadow   ↑ the last ray of light stays here
```

```
西（294°、日没の方向）                                            東（海の方向）
城門 ═ 西の大通り ═ 広場［露店・噴水・老爺の家・石屋の工房］ ═ 磔の柱 ─ 王城の階段 ─ 塔
  ↑ 19:00 太陽がちょうどこの通りに沈む     ↑ 18:00 地面がすべて影に入る     ↑ 最後の光がここに残る
```

- **The west street and the city gate face 294°**, so at sunset the sun sets right at the mouth of the street. In act 4 Melos bursts in through this gate **with the last sunlight at his back**, his long shadow reaching toward 磔の柱 ahead of him.
  **西の大通りと城門は 294° を向く**。だから日没のとき、太陽はちょうど通りの入口に沈む。第四幕でメロスはこの城門から**最後の日の光を背に**駆け込み、長い影が彼より先に磔の柱へ伸びる。
- **The royal castle is on higher ground to the east, with a tower**, and the tower must be much taller than the western houses to keep the last light. Historically, Dionysius's fortress was also on the island of Ortygia, on Syracuse's eastern seaward side.
  **王城は東の高台にあり、塔が 1 つある**。塔は西の家々よりずっと高くなければ、最後の光を留められない。歴史上もディオニュシオスの要塞はシラクス東側の海に面したオルティージャ島にあった。
- **磔の柱 is a single upright post, with no crossbeam** (Frontend's approach in S7, which UX agrees with): the story is set in ancient Greece, so it is not made to look like a cross.
  **磔の柱は縦の柱 1 本だけで、横木は付けない**（フロントエンドの S7 のやり方で、UX も同意）：物語の舞台は古代ギリシャなので、十字架のようには作らない。
- **The crowd at the execution ground faces the pillar to the east, with their backs to the western gate.** That is how the original's 「群衆は、ひとりとして彼の到着に気がつかない」 makes sense on screen.
  **刑場の群衆は東の柱を向き、西の城門に背を向けている。** だから原作の「群衆は、ひとりとして彼の到着に気がつかない」が画面の上で筋が通る。
- **Leave a clear straight line from the city gate to 磔の柱.** The width of the gate street continues all the way to the pillar, with nothing fixed such as a fountain or stalls in between (the crowd is alive and will move aside). Around sunset the sunlight enters the plaza only through this street, so this line is the corridor of light: Melos charges along it toward the pillar, his shadow ahead of him; ending B's camera looks along it from the pillar toward the gate (ux-design 11.4).
  **城門から磔の柱まで、何もない直線を 1 本残す。** 城門の大通りの幅をそのまま柱の前まで伸ばし、間に噴水や露店などの固定物は置かない（群衆は生きているので道をあける）。日没前後、日の光はこの通りからしか広場に入らないので、この線が光の回廊になる：メロスはこれに沿って柱へ突進し、影が彼より先に伸びる。エンディング B のカメラはこれに沿って柱から城門を見る（ux-design 11.4）。
- **老爺の家 is at the edge of the plaza, with its door facing the plaza**, and there is a location point in front of the door. The traveler can 「暗くなる道を家まで送る」 (world model `aid.old-man.listen`); the M2 slice already needs this.
  **老爺の家は広場の端にあり、扉は広場に向いている**。扉の前には位置点が 1 つある。旅人は「暗くなる道を家まで送る」ことができ（世界モデル `aid.old-man.listen`）、M2 スライスですでに使う。
- **At the foot of the pillar is a low platform (磔台).** The original: 「ついに磔台に昇り、釣り上げられてゆく友の両足に、齧りついた」. Melos climbs onto it from the plaza side; standing on the platform you can reach the feet of the person hung up; the head of the person hung up is clearly above the heads of the crowd. Frontend sets the platform and pillar heights using the real-time sun 〔inference: platform 1〜1.5 m, pillar about 6 m from the ground〕.
  **柱の根元には低い台（磔台）がある。** 原作「ついに磔台に昇り、釣り上げられてゆく友の両足に、齧りついた」。メロスは広場の側から登る。台の上に立てば、吊り上げられた人の足に手が届く。吊り上げられた人の頭部は群衆の頭よりはっきり高い。台と柱の高さはフロントエンドがリアルタイムの太陽で決める〔推定：台 1〜1.5 m、柱は地面から 6 m 前後〕。
- **The head of the person on the pillar must be lit last** (3.4). The heights of the gate opening, the western houses, the platform and the pillar together decide when he is lit. Estimated from F-2a's dimensions, about ten minutes before sunset the light coming through the gate opening falls right on the head of the person on the pillar, matching the moment in the original when Melos bursts in 〔inference; Frontend checks with the real-time sun〕. When changing any of these heights, look at them together.
  **柱の上の人の頭部に、最後に光が当たるようにする**（3.4）。城門の開口部、西の家、台、柱の高さがそろって、彼にいつ光が当たるかを決める。F-2a の寸法で見積もると、日没の約 10 分前に城門の開口部から差し込む光がちょうど柱の上の人の頭部に当たり、原作でメロスが駆け込む時刻と合う〔推定、フロントエンドがリアルタイムの太陽で確認〕。これらの高さを変えるときは一緒に見る。
- The plaza orientation in the prototype is an arbitrary placeholder; the real scene follows this diagram.
  プロトタイプの広場の向きは適当に置いた仮のもので、実際のシーンはこの図に従う。

### 4.2 Material list / マテリアル一覧

Near view means things within 1〜3m of the dialogue camera, and things the exploration camera keeps looking at; these need the most detail.

近景とは、会話カメラから 1〜3m 以内のものと、探索カメラがずっと見ているもので、いちばん精細に作る。

| Material / マテリアル | Where / 場所 | Distance / 距離 | Key points / 要点 |
|---|---|---|---|
| Limestone flagstone ground / 石灰岩の石畳 | Plaza, in front of the castle / 広場、王城の前 | **Near, the most important** / **近景、最重要** | The exploration camera looks down at it all the time. Busy routes are worn shiny (different roughness); dust and dry grass in the joints; golden in the evening light, which it bounces back onto faces / 探索カメラがずっと見下ろしている。人通りの多い経路はすり減って光っている（粗さが違う）。目地には土埃と枯れ草。夕方は金色に照らされ、その光を人の顔へ照り返す |
| Limestone ashlar walls / 石灰岩の切り石の壁 | Castle, temple, houses of the rich / 王城、神殿、裕福な家 | Near / 近景 | Syracuse's local limestone is a honey-tinged white that turns gold in the setting sun. Chisel marks on the surface; the bottom 30cm or so darkened by splashes and dust; the upper parts bleached by the sun / シラクス産の石灰岩は蜂蜜色を帯びた白で、夕日に金色に輝く。表面にのみの跡がある。壁の下 30cm ほどは跳ねた水と土埃で黒ずみ、高いところは日に焼けて白っぽい |
| Plaster (漆喰) / 漆喰 | Ordinary houses / 庶民の家 | Near / 近景 | Warm white or ochre, peeling in places to show the stone or mud brick beneath / 暖かみのある白か黄土色。ところどころ剥がれて下の石や日干しれんがが見える |
| Wood / 木材 | Doors, shutters, carts, railings / 扉、鎧戸、荷車、手すり | Near / 近景 | Old wood weathered gray by the sun. **Windows have no glass**; use wooden shutters / 日に焼けて灰色になった古い木。**窓にガラスはなく**、木の鎧戸を使う |
| Cloth / 布 | Sun awnings, laundry, door curtains / 日よけの布、干した衣類、戸口の垂れ幕 | Near or middle / 近景・中景 | Moves in the wind; light shines through it against the evening sun / 風に揺れる。夕方の逆光で透ける |
| Water / 水 | The plaza fountain; the spring on the homeward road; the river / 広場の噴水、帰り道の泉、川 | Near / 近景 | The spring is clear, welling up from a crack in the rock (「岩の裂目から滾々と…清水が湧き出ている」); the river is a churning, muddy yellow 濁流, and only the stakes of the broken bridge remain / 泉は澄んでいて、岩の割れ目から湧き出る（「岩の裂目から滾々と…清水が湧き出ている」）。川は黄色く濁って渦巻く濁流で、壊れた橋は杭だけが残る |
| Clay roof tiles / 瓦 | Roofs / 屋根 | Middle / 中景 | Greek-style pan and cover tiles. Faded orange-brown; **must not compete with 緋色** / ギリシャ式の平瓦と丸瓦。色あせた橙褐色で、**緋色と競ってはならない** |
| Pottery / 陶器 | Amphorae, oil lamps, water jars / アンフォラ、油のランプ、水がめ | Middle / 中景 | Unglazed, with a little black patterning / 素焼きで、黒い文様が少しある |
| Plants / 植物 | Olive, fig, grape arbor / オリーブ、イチジク、ブドウ棚 | Middle / 中景 | Olive leaves are silver-gray underneath. **A grape arbor casts dappled light on faces**: cheap and beautiful; we suggest putting one at the old man's door / オリーブの葉の裏は銀灰色。**ブドウ棚は顔にまだらな光と影を落とす**。安くて美しいので、老爺の家の戸口に置くことを勧める |
| Cypress / 糸杉 | In the distance / 遠く | Far / 遠景 | Dark vertical silhouettes that mark the skyline / 暗い縦長のシルエットでスカイラインを描く |
| Distant view / 遠景 | City walls, the temple's Doric columns, the Hyblaean Mountains to the west, the sea to the east / 城壁、神殿のドーリア式の柱、西のイブレイ山地、東の海 | Far / 遠景 | A sky shader and a few layers of silhouettes, with colors following the sky / 空のシェーダーと数層のシルエットで作り、色は空の色に合わせて変わる |

**Other scenes**:

**その他のシーン**：

- **The village**:
  **村**：
  - dry-stone walls, no mortar;
    空積みの石垣で、モルタルは使わない。
  - golden wheat fields in early summer, just the season for the wheat harvest and weddings;
    初夏の金色の麦畑。ちょうど麦の収穫と婚礼の季節。
  - the sheep shed, with stone walls and a thatched roof;
    羊小屋は石の壁に草葺きの屋根。
  - the wedding courtyard.
    婚礼の中庭。
- **The homeward road** (four stops and the running stretches; details in [scenes/homeward-road.md](scenes/homeward-road.md)):
  **帰り道**（4 つの地点と走る区間。詳細は [scenes/homeward-road.md](scenes/homeward-road.md)）：
  - white limestone dirt roads and dry grass, green near water; wildflowers only in yellow, white and purple, no red corn poppies (section 6);
    白い石灰岩の土の道と枯れ草、水辺は緑。野の花は黄、白、紫だけで、赤いヒナゲシは置かない（第 6 節）。
  - 川: in act 2 a calm river and a wooden bridge; in act 4 the 濁流, the stakes of the broken bridge and fresh silt on the banks;
    川：第二幕は穏やかな川と木の橋。第四幕は濁流、壊れた橋の杭、岸に新しく積もった泥。
  - 峠: a sun-bleached limestone rock gateway, scree, dwarf fan palms (the small fan-leaved palm native to Sicily);
    峠：日に焼けて白くなった石灰岩の岩門、砕石、チャボトウジュロ（シチリア原産の扇形の葉の小さなヤシ）。
  - 泉: clear water welling from a crack in the rock, moss and maidenhair fern, three oriental plane trees to the west (lit through from behind by the sun at 16:30, 「葉も枝も燃えるばかりに」);
    泉：岩の割れ目から湧く清水、苔とホウライシダ、西側に 3 本のスズカケノキ（16:30 に背後から日に透かされ、「葉も枝も燃えるばかりに」）。
  - 野の道: golden wheat fields, the distant towers (3.4 ②).
    野の道：金色の麦畑、遠くの塔楼（3.4 ②）。
- **The throne room**:
  **王座の間**：
  - polished dark stone floor, columns, heavy cloth curtains;
    磨かれた暗色の石の床、柱、重厚な布の幕。
  - high windows;
    高い窓。
  - at night only oil lamps and braziers. The king's light comes from above, so his eye sockets fall into shadow and the furrows between his brows look deeper (the original: 「その王の顔は蒼白で、眉間の皺は、刻み込まれたように深かった」). During dialogue give his eyes a little catchlight from the lamps, or his expression cannot be read.
    夜は油のランプと火鉢だけ。王の光は上から来るので、眼窩は影に沈み、眉間の皺がいっそう深く見える（原作「その王の顔は蒼白で、眉間の皺は、刻み込まれたように深かった」）。会話のときは彼の目に灯火の映り込みを少し入れる。そうしないと表情が読めない。

### 4.3 Period accuracy: common mistakes in scanned assets / 時代考証：スキャン素材によくある間違い

With realism, “something is off” gets noticed. When using free scanned assets, do not use the following:

リアルにすると、「どこかおかしい」が見抜かれる。無料のスキャン素材を使うとき、次のものは使わない：

| Don't use / 使わないもの | Why / 理由 |
|---|---|
| Prickly pear, agave / ウチワサボテン、リュウゼツラン | From the Americas; they reached the Mediterranean only after 1492. They are everywhere in photos of Sicily today, so they are the easiest to slip in / アメリカ大陸原産で、地中海に来たのは 1492 年以降。今のシチリアの写真にはどこにでも写っているので、いちばん紛れ込みやすい |
| Eucalyptus / ユーカリ | From Australia, introduced only in the 19th century / オーストラリア原産で、19 世紀になって持ち込まれた |
| Lemon and orange groves / レモンやオレンジの果樹園 | Large-scale cultivation dates from Arab rule onward / 大規模な栽培はアラブ支配の時代以降 |
| Tomatoes, maize / トマト、トウモロコシ | From the Americas / アメリカ大陸原産 |
| Glass windows, concrete, modern red brick, metal doors and windows / ガラス窓、コンクリート、現代の赤れんが、金属の扉や窓 | Wrong period / 時代が合わない |
| Lots of arches / 多数のアーチ | Greek building was mainly post and lintel; a few arches are fine / ギリシャの建築は柱と梁が中心で、アーチは少しならあってよい |
| Large patches of red flowers such as poppies / ケシなど赤い花の群生 | Fine for the period, but they compete with 緋色 (section 6) / 時代は問題ないが、緋色と競ってしまう（第 6 節） |

---

## 5. Characters / 人物

### 5.1 How real / どこまでリアルにするか

- **Proportions**: real human (7〜7.5 heads tall); no enlarged heads or eyes.
  **プロポーション**：実際の人間（7〜7.5 頭身）。頭や目を大きくしない。
- **Where realism goes**, in order:
  **リアルさをどこに使うか**、順に：
  1. the weight of movement (shifts of the body's center of gravity when walking, running, stopping, turning);
     動きの重さ（歩く、走る、止まる、振り向くときの重心の移り変わり）。
  2. eyes: a blink every 3〜6 seconds; the gaze on the player during dialogue; highlights in the eyes;
     目：3〜6 秒に 1 回まばたきする。会話中は視線をプレイヤーに向ける。目にハイライトがある。
  3. mouth shapes: the five Japanese vowels 「あいうえお」 plus closed, following the voice. A voice playing while the mouth doesn't move is the quickest way to break immersion;
     口の形：日本語の 5 つの母音「あいうえお」と閉じた口を、声に合わせて動かす。声が鳴っているのに口が動かないのは、いちばん没入を壊しやすい点だ。
  4. brows: three states, level, furrowed, raised;
     眉：平ら、ひそめる、上げるの 3 種類。
  5. cloth;
     布。
  6. skin;
     肌。
  7. hair.
     髪。
- **Skin**:
  **肌**：
  - it needs a healthy flush and translucency (an approximation of subsurface scattering);
    血色と透明感が必要（サブサーフェス・スキャタリングの近似）。
  - tan varies by person: Melos is a herdsman burned dark by the sun, the king is 「蒼白」;
    日焼けの度合いは人による：メロスは日に焼けて浅黒い牧人、王は「蒼白」。
  - no pores or fine hair, no oily shine.
    毛穴や産毛は作らず、テカらせない。
- **Principle**: the face must never be more realistic than its movement. When the animation budget runs short, make the face a little simpler rather than let a very real face move stiffly.
  **原則**：顔のリアルさが動きのリアルさを超えてはならない。アニメーションの予算が足りないときは、とてもリアルな顔がぎこちなく動くよりも、顔を少し簡素にするほうを選ぶ。

### 5.2 How big the face is during dialogue / 会話中の顔の大きさ

- In the portrait over-the-shoulder two-shot (ux-design 6.3), the other person's face (chin to hairline) takes up about 12〜15% of the screen height, roughly 100〜130pt, about 2 cm on a 6.1-inch phone. The eyes are only 8〜10pt wide. 〔Inference, computed from the prototype's camera; measure in S7〕
  縦画面の肩越しのツーショット（ux-design 6.3）では、相手の顔（あごから生え際まで）は画面の高さの約 12〜15%、およそ 100〜130pt で、6.1 インチのスマートフォンで約 2 cm。目の幅は 8〜10pt しかない。〔推定、プロトタイプのカメラで計算。S7 で実測する〕
- So skin detail is almost invisible on a phone. What reads is gaze, blinks, brows, mouth, head angle and body posture.
  だから肌のディテールはスマートフォンではほとんど見えない。読み取れるのは視線、まばたき、眉、口、頭の角度、体の姿勢だ。
- Face textures: 1024 in tier B, 2048 on high-end phones (9.2). Tier B at DPR 1.5 makes the face about 150〜200 pixels tall, for which 1024 is enough; high-end phones at DPR 2〜3 make it about 200〜390 pixels tall, and only 2048 shows the shape of the eyelids and lips 〔inference〕.
  顔のテクスチャ：ティア B は 1024、高性能機は 2048（9.2）。ティア B は DPR 1.5 で顔の高さが約 150〜200 ピクセルなので 1024 で足りる。高性能機は DPR 2〜3 で顔の高さが約 200〜390 ピクセルになり、2048 でないとまぶたや唇の形が見えない〔推定〕。

### 5.3 No extreme close-ups at key moments / 重要な瞬間でも極端なクローズアップにしない

- When a key moment (ux-design 8.3) needs emphasis, use a **backlit profile**: the character stands in front of a bright sky, the face in shadow, only the outline and posture visible. This is how v0.1's C 「影絵」 silhouette idea is used in the realistic style.
  重要な瞬間（ux-design 8.3）を強調するときは、**逆光の横顔**を使う：人物が明るい空の前に立ち、顔は影の中にあり、輪郭と姿勢だけが見える。v0.1 の C「影絵」のシルエットの発想は、リアルな画風ではこう使う。
- This feels cinematic without pushing the face to the size most prone to the uncanny valley.
  こうすれば映画的でありながら、顔をいちばん不気味の谷に陥りやすい大きさまで寄せずに済む。
- With “reduce motion” on, no push-ins or pull-outs (ux-design section 13).
  「動きを減らす」がオンのときは、カメラを寄せたり引いたりしない（ux-design 第 13 節）。

### 5.4 Costumes and silhouettes / 服装とシルエット

In the exploration camera characters are only 40〜80px tall, and realistic people at this size tend to look alike, so **each character needs a silhouette recognizable at a glance**. Costumes follow what ancient Greeks actually wore: the linen chiton (long tunic), the wool himation (outer robe), the exomis work tunic that leaves one shoulder bare, and the traveler's short cloak chlamys and wide-brimmed hat petasos.

探索カメラでは人物の高さは 40〜80px しかなく、この大きさだとリアルな人間は似通って見えやすい。だから**一人ひとりにひと目で分かるシルエットが必要**。服装は古代ギリシャの実際の装いに従う：麻の chiton（長衣）、羊毛の himation（外衣）、片方の肩を出す労働用の短衣 exomis、旅人の短いマント chlamys とつばの広い帽子 petasos。

| Character / 登場人物 | Clothing / 服装 | Silhouette / シルエット | Colors / 色 |
|---|---|---|---|
| メロス | Wool short tunic (exomis, fastened only at the left shoulder), rope belt, leather sandals. In act 1 he carries on his back what he bought for his sister (「買い物を、背負ったままで」); the dagger is hidden inside his clothes, out of sight (「懐中からは短剣が出て来た」), and is found and confiscated when he enters the castle. In act 4 his clothes are torn, and he is covered in dust and scrapes / 羊毛の短衣（exomis、左肩だけで留める）、腰紐、革のサンダル。第一幕では妹のために買った物を背負っている（「買い物を、背負ったままで」）。短剣は懐に隠れて見えず（「懐中からは短剣が出て来た」）、王城に入るときに見つかって没収される。第四幕では服が裂け、全身が土埃と擦り傷だらけ | Lean and tall, leaning forward, right shoulder and arm bare; in act 1 a bundle on his back / 細長く、前のめり、右肩と右腕を出す。第一幕では背中に包み | Ochre, undyed wool / 黄土色、染めていない羊毛の色 |
| 王ディオニス | A heavy deep-purple robe (Tyrian purple), a thin gold headband / 重厚な深紫の長衣（貝紫）、細い金の頭飾り | Tall, broad-shouldered, standing very straight / 背が高く、肩幅が広く、まっすぐに立つ | Deep purple, dark gray / 深紫、濃い灰色 |
| セリヌンティウス | A stonemason's exomis, leather apron, rolled-up sleeves, stone dust on him / 石工の exomis、革の前掛け、まくり上げた袖、体に石粉 | Broad, sturdy / 幅があり、がっしりしている | Gray, earth tones / 灰色、土色 |
| 妹 | Everyday: a brown wool long tunic and a pale woad-blue headscarf; at the wedding: a saffron-yellow long tunic and veil / 普段は茶色の羊毛の長衣と淡い大青色の頭巾。婚礼ではサフラン色の長衣とベール | Small and slight / 小柄で細い | Brown; saffron yellow at the wedding / 茶色。婚礼ではサフラン色 |
| 花婿 | A herdsman's thick wool cloak, round felt cap; a myrtle wreath at the wedding / 牧人の厚い羊毛のマント、丸いフェルト帽。婚礼ではギンバイカの花冠 | Stocky / ずんぐりしている | Olive / オリーブ色 |
| フィロストラトス | Short tunic, a headscarf covering his hair, stone dust / 短衣、髪を包む頭巾、石粉 | Thin, leaning forward / 痩せて、前のめり | Gray-brown / 灰褐色 |
| 町の老爺 | A faded outer robe pulled up over his head, white beard, walking stick / 色あせた外衣を頭までかぶり、白いひげ、杖 | Hunched / 背が曲がっている | Gray / 灰色 |
| Player: 旅人 / プレイヤー：旅人 | Woad-dyed linen long tunic, a short cloak (chlamys, world model `item.cloak`) folded over the left arm, a wide-brimmed traveler's hat (petasos, the mark of a traveler in ancient Greece), a water skin slung across the body, **緋色 sash** / 大青で染めた麻の長衣、短いマント（chlamys、世界モデル `item.cloak`）を畳んで左腕に掛け、つばの広い旅人の帽子（petasos、古代ギリシャの旅人の目印）、斜め掛けの水袋、**緋色の帯** | Hat brim / 帽子のつば | 海色 + 緋 |
| Player: 石屋の弟子 / プレイヤー：石屋の弟子 | Short tunic covering both shoulders, leather apron (straps crossing at the back), headband, a chisel tucked in the belt, **緋色 sash** / 両肩を覆う短衣、革の前掛け（背中で交差する紐）、鉢巻き、腰にのみを差す、**緋色の帯** | Apron, mallet / 前掛け、木槌 | Earth tones + 緋 / 土色 + 緋 |
| Player: 村の牧童 / プレイヤー：村の牧童 | Short sheepskin cape (fleece outward), 羊飼いの杖 (shepherd's crook), **緋色 sash**, no hat / 羊皮の短い肩掛け（毛を外側に）、羊飼いの杖、**緋色の帯**、帽子なし | Short, crook / 背が低い、牧杖 | Dark walnut + 緋 / 濃い胡桃色 + 緋 |

- **All hair is short, or covered by a hat, headscarf or veil.** This fits the clothing of the time, and also avoids the hardest thing to do realistically on a phone: long hair.
  **髪はすべて短いか、帽子、頭巾、ベールで覆う。** 当時の装いに合い、リアルな表現でスマートフォン上いちばん難しいもの、つまり長い髪も避けられる。
- **Colors are only the low-saturation colors natural dyes can produce**: undyed linen and wool, ochre, walnut brown, faded woad blue, olive. The king's deep purple is the only rich color, and it is not red. No red other than 緋色.
  **色は天然染料で出せる彩度の低い色だけ**：染めていない麻と羊毛、黄土色、胡桃の茶色、色あせた大青、オリーブ色。王の深紫だけが濃い色だが、赤ではない。緋色以外の赤は使わない。
- **Melos at the end is 「ほとんど全裸体」**: show it as clothes torn until almost nothing is left, not as nudity.
  **最後のメロスは「ほとんど全裸体」**：服がほとんど残らないほど裂けた姿で表し、裸体は描かない。
- The costume sheets and silhouettes of all characters are in the [style guide](style-guide/README.md) (the slice's three characters and the ending characters; v1.1 added the M3 characters and two roles). They are more detailed than this table; build models from there. Where the two differ, the style guide wins.
  すべての人物の服装表とシルエットは[スタイルガイド](style-guide/README.md)にある（スライスの 3 人とエンディングの人物。v1.1 で M3 の人物と 2 つの身分を追加）。この表より詳しいので、モデルはそちらに従って作る。両者が食い違うときはスタイルガイドを優先する。

### 5.5 The crowd at the execution ground / 刑場の群衆

- **Number and method**: Frontend's instanced low-poly models. 3〜4 body types × 3 outfits × slight color variations, with animations at different time offsets so they don't move in unison.
  **数と作り方**：フロントエンドのインスタンス化したローポリモデル。体型 3〜4 種 × 服装 3 種 × 色の微調整で、動きは時間をずらして一斉にそろわないようにする。
- **Placement**: facing the pillar to the east, backs to the western gate (4.1). The eastern half is packed, and the edges gradually fade into shadow and haze.
  **配置**：東の柱を向き、西の城門に背を向ける（4.1）。東半分はぎっしり埋まり、端は少しずつ影ともやに溶け込む。
- **Light**: before sunset the crowd is a backlit silhouette, and the roughness of the low-poly models is hidden by the light. Here realism and budget do not conflict.
  **光**：日没前の群衆は逆光のシルエットで、ローポリの粗さは光に隠れる。ここではリアルさと予算がぶつからない。
- **Reaction**: when Melos climbs onto the 磔台, the whole crowd breaks into a 「どよめき」 (a wave of bodies swaying and voices).
  **反応**：メロスが磔台に登ると、群衆全体に「どよめき」（体の揺れと声の波）が起こる。

### 5.6 Animation / アニメーション

- Shared: idle, walk, run, nod, shake head, think, point, kneel, plus Frontend's turn in place and beckon / call out.
  共通：待機、歩く、走る、うなずく、首を振る、考える、指さす、ひざまずく。これにフロントエンドが挙げたその場で振り向く、手招き / 呼びかけを加える。
- Each character has 1〜2 signature moves: the king's cold smile, Melos clenching his fist, the old man turning back while leaning on his stick.
  人物ごとに専用の動きを 1〜2 個：王の冷笑、メロスが拳を握る、老爺が杖をついて振り返る。
- For the realistic style, motion-capture clips are recommended. Frontend decides the source and licensing.
  リアルな画風ではモーションキャプチャのクリップを勧める。入手先とライセンスはフロントエンドが決める。

### 5.7 Violence and injuries / 暴力と傷

- The fight with the bandits and the two friends slapping each other (「音高くメロスの右頬を殴った」) can both be shown, but with no spurting blood.
  山賊との戦いも、2 人の友が互いの頬を打つ場面（「音高くメロスの右頬を殴った」）も演じてよいが、血しぶきはない。
- Injuries are shown with dust, scrapes and torn clothes.
  傷は土埃、擦り傷、裂けた服で表す。
- The execution itself is not shown (ux-design 11.1, section 14; about CERO B).
  処刑そのものは描かない（ux-design 11.1、第 14 節、CERO B 程度）。
- The two shots for not making it in time are in ux-design 11.4 (S-067).
  間に合わなかったときの 2 つのショットは ux-design 11.4 を参照（S-067）。
  - When the 身代わり is セリヌンティウス: the crowd faces west, and the last ray of light leaves the top of the tower.
    身代わりがセリヌンティウスのとき：人々は西を向き、最後の光が塔の頂から消える。
  - When the 身代わり is you: the camera is behind you on the pillar, looking toward the west gate; the sun sinks into the gate opening, and no one comes running in.
    身代わりがあなたのとき：カメラは柱の上のあなたの背後から西の門を見る。太陽が門の開口部に沈み、誰も駆け込んでこない。
  - Both shots stop at the moment the light disappears.
    どちらのショットも光が消えたその瞬間で止まる。

---

## 6. 緋色 (scarlet) / 緋色

- **Only three things get it**: the player's sash (your mark in this world), the causal lines in the UI (what you change), and the 「緋のマント」 the girl offers Melos in the ending. In the ending the cloak ties the first two together.
  **使うのは 3 つだけ**：プレイヤーの帯（この世界でのあなたの印）、UI の因果の線（あなたが変えたもの）、そしてエンディングで少女がメロスに捧げる「緋のマント」。エンディングでマントが前の 2 つを結びつける。
- **In the realistic style**:
  **リアルな画風では**：
  - the sash is madder-dyed cloth, deep and matte, not fluorescent red;
    帯は茜で染めた布で、深く、つやのない色。蛍光の赤ではない。
  - everything else in the world avoids red: clay tiles are pushed to a faded orange-brown, and there are no large patches of red flowers;
    世界のほかのものはすべて赤を避ける：瓦は色あせた橙褐色に抑え、赤い花の群生は置かない。
  - at sunset the whole image runs warm, so the sash has to stand out by **saturation** rather than hue. Please check this specifically in S7's sunset image.
    日没時は画面全体が暖色に寄るので、帯は色相ではなく**彩度**で目立たせる。S7 の日没の画面で、ここを特に確認してほしい。
- The UI's 緋色 `#b93a26` stays the same.
  UI の緋色 `#b93a26` は変えない。

---

## 7. Image treatment / 画面処理

| Item / 項目 | Requirement / 要件 |
|---|---|
| Tone mapping / トーンマッピング | Use Khronos PBR Neutral. S7 measurements showed AgX washes out bright warm colors, turning the limestone in the setting sun pale beige. The sunset sky must not blow out to white; dark areas must not be dead black, but carry the blue of the skylight / Khronos PBR Neutral を使う。S7 の実測では AgX は明るい暖色を薄めてしまい、夕日の石灰岩が淡いベージュになった。日没の空を真っ白に飛ばしてはならない。暗部は真っ黒にせず、空の光の青を残す |
| Color grading / カラーグレーディング | On top of the physically correct light, add a very light grade (LUT) for each time of day, blending with `t`. **The night blue (day-for-night, 3.2) tints only where skylight reaches**: fires, lamps and the walls, ground and faces they light stay warm (about 1800〜2000K). Cold night color against warm lamplight is what night looks like; fire tinted blue-white or pale violet no longer looks like fire (the firelight comparison on the F-2c measurement page). Conversely, the stone and skin lit most brightly by fire should also keep a little blue rather than be pure orange all over: next to the fire on #54's stand-in there was an area where the blue channel was 0, and it looked like orange paint. This sets the color and intensity of fire; tune the fire in each scene by this rule / 物理的に正しい光の上に、時刻ごとにごく軽いグレーディング（LUT）を重ね、`t` に合わせて徐々に変える。**夜の青（デイ・フォー・ナイト、3.2）は空の光が届くところだけを染める**：火、灯、それらが照らす壁、地面、人の顔は暖色のまま（約 1800〜2000K）。冷たい夜の色に暖かい灯火が映えるのが夜の姿だ。火が青白や薄紫に染まると火に見えなくなる（F-2c の計測ページの火の光の比較）。逆に、火にいちばん明るく照らされた石や肌にも少し青を残し、一面の純粋なオレンジにしない：#54 の代役では火のそばに青が 0 のピクセルの領域があり、オレンジのペンキのように見えた。これが火の色と強さで、各シーンの火はこのルールで調整する |
| Fog and aerial perspective / 霧と空気遠近法 | **Required**; it is the cheapest way to give the image “air”: distant things become paler and shift toward the sky color / **必須**。画面に「空気」を与えるいちばん安い方法：遠くのものほど淡く、空の色に寄る |
| Wind / 風 | Awnings, laundry, grass and cypresses move gently. Very small movements, but they keep the world alive / 日よけの布、干した衣類、草、糸杉がそっと揺れる。動きはごく小さいが、世界を生かす |
| Bloom / ブルーム | Only around the sun, firelight and reflective water / 太陽、火の明かり、光を反射する水面のまわりだけ |
| Not used / 使わない | Lens flares everywhere, chromatic aberration, heavy vignetting, film grain (costly on phones, and they hurt text legibility) / 画面中に飛び交うレンズフレア、色収差、強いビネット、フィルムグレイン（スマートフォンでは性能を食い、文字の読みやすさも損なう） |
| Resolution / 解像度 | 3D may drop resolution by quality tier; UI text is in the web layer and always sharp (frontend section 10) / 3D は画質のティアに応じて解像度を下げてよい。UI の文字はウェブのレイヤーにあり、常にくっきりしている（frontend 第 10 節） |

---

## 8. The UI and the realistic image / UI とリアルな画面の関係

- **The UI is still “paper laid on the world”**: 紙色 panel `#f1e9d8`, ink-colored text `#27221d`, and the only accent colors are 緋色 `#b93a26` and 海色 `#3f6f6c`.
  **UI は引き続き「世界の上に置いた紙」**：紙色の下地 `#f1e9d8`、墨色の文字 `#27221d`、強調色は緋色 `#b93a26` と海色 `#3f6f6c` だけ。
- **Fonts stay the same**: BIZ UDPGothic for the UI, Shippori Mincho B1 for titles, narration and the ending.
  **フォントは変えない**：UI は BIZ UDPGothic、書名、語り、エンディングは Shippori Mincho B1。
- **The sunset sky is very bright**, so the paper panel behind subtitles must be more opaque against bright backgrounds, keeping contrast ≥ 4.5:1 (ux-design section 13).
  **日没の空はとても明るい**ので、明るい背景の前では字幕の紙の下地の不透明度を上げ、コントラスト ≥ 4.5:1 を保つ（ux-design 第 13 節）。
- **The ending card illustration is a frame of the ending set piece (S-055)**, so the ending shots are composed for the card's illustration area (1080×640):
  **エンディングカードのイラストはエンディング演出の 1 フレーム（S-055）**なので、エンディングのショットはカードのイラスト領域（1080×640）に合わせて構図を決める：
  - the horizon in the upper third;
    地平線は上から 3 分の 1。
  - the setting sun in the city gate, or the last light on top of the tower, visible in the frame;
    城門の夕日か、塔の頂の最後の光が画面に見える。
  - characters and the pillar in the lower two thirds.
    人物と柱は下の 3 分の 2。

---

## 9. Art specs: tier B and the high-end upgrade (D-019) / アート仕様：ティア B と高性能機のアップグレード（D-019）

zg decided “tier B as the base, automatic upgrade on high-end phones” (D-019). This section is the spec for art assets. Rendering parameters (resolution, shadows, post-processing) and the upgrade/downgrade logic are Frontend's call; see frontend-design 10.3, 10.6. The numbers below defer to Frontend's 10.6; where they differ, align with Frontend.

zg は「ティア B を基本とし、高性能機は自動で上げる」と決めた（D-019）。この節はアートアセットの仕様。レンダリングのパラメータ（解像度、影、ポストプロセス）とティアの上げ下げのロジックはフロントエンドが決める。frontend-design 10.3、10.6 を参照。下の数字はフロントエンドの 10.6 を正とし、食い違うときはフロントエンドとすり合わせる。

### 9.1 Principles / 原則

1. **One set of art, built fully for the high-end tier, then exported to tier B.** Photo-scanned materials are 2K〜4K to begin with, and the pipeline (gltf-transform) scales them down for tier B; characters are first built at 40,000 faces, then reduced to a 20,000〜30,000-face version and an 8k-face version.
   **アートは 1 セット。高性能機のティアで作り込み、そこからティア B を書き出す。** 写真スキャンのマテリアルはもともと 2K〜4K で、ティア B はパイプライン（gltf-transform）で縮小する。人物はまず 4 万面の版を作り、そこから 2〜3 万面と 8k 面の 2 つの版に減らす。
2. **Run acceptance checks on tier B first.** Every player sees at least tier B; high-end phones are only sharper. Each asset passes its check on tier B first, then is looked at on the high-end tier.
   **受け入れ確認はまずティア B で行う。** すべてのプレイヤーが少なくともティア B を見る。高性能機はより鮮明になるだけ。各アセットはまずティア B で確認を通り、その後で高性能機のティアを見る。
3. **Both tiers are the same world.** Composition, light, color, silhouettes, and the kinds of expressions and animations are exactly the same. The high-end tier adds nothing tier B cannot see: no extra props, no extra expressions, no details that only make sense when seen clearly. For example, the lamplight catchlight in the king's eyes in the throne room (4.2) and Melos's scrapes in act 4 (5.4) must read on tier B too.
   **2 つのティアは同じ世界。** 構図、光、色、シルエット、表情とアニメーションの種類はまったく同じ。高性能機のティアにはティア B で見えないものを何も足さない：小道具も表情も足さず、はっきり見えて初めて分かるディテールも置かない。たとえば王座の間で王の目に映る灯火（4.2）や、第四幕のメロスの擦り傷（5.4）は、ティア B でも読み取れなければならない。
4. **Money goes first to**: light → near-view ground and walls → character movement, eyes and mouth shapes → cloth → skin → middle view (tiles, doors, plants) → distant view → hair. The extra 25〜40% or so on high-end phones is spent in the same order (9.4), not on pores (5.1: the face must never be more realistic than its movement).
   **費用をかける順番**：光 → 近景の地面と壁 → 人物の動き、目、口の形 → 布 → 肌 → 中景（瓦、扉、植物）→ 遠景 → 髪。高性能機で増える約 25〜40% も同じ順番で使い（9.4）、毛穴には使わない（5.1：顔のリアルさが動きのリアルさを超えてはならない）。

### 9.2 The two tiers compared / 2 つのティアの比較

| Asset / アセット | Tier B (all phones, baseline iPhone 12) / ティア B（すべてのスマートフォン、最低ライン iPhone 12） | High-end upgrade / 高性能機のアップグレード | Notes / 備考 |
|---|---|---|---|
| Environment materials / 環境マテリアル | All 1024, KTX2 / すべて 1024、KTX2 | In each scene the 4〜6 that fill the most screen get a 2048 color map + 1024 normal map (9.3); the rest stay 1024 / 各シーンで画面に占める割合がいちばん大きい 4〜6 種を 2048 のカラーマップ + 1024 の法線マップに替える（9.3）。残りは 1024 のまま | About 6〜9 MB more per scene. Upgrading every material would be about +15 MB; not done / シーンごとに約 6〜9 MB 増える。すべてのマテリアルを替えると約 +15 MB になるので、やらない |
| Environment geometry / 環境ジオメトリ | The same set / 同じもの | Same as tier B / ティア B と同じ | Not split by tier / ティアで分けない |
| Lightmaps / ライトマップ | 2048, one set per time slot / 2048、時間帯ごとに 1 セット | Same as tier B / ティア B と同じ | — |
| Sky, fog, sun / 空、霧、太陽 | Real time, the same parameters / リアルタイム、同じパラメータ | Same as tier B / ティア B と同じ | “The sun is the clock” is the same in both tiers (section 3) / 「太陽が時計」は両ティアで同じ（第 3 節） |
| Talkable characters, dialogue version / 会話できる人物・会話版 | 20,000〜30,000 faces; 4〜5 materials (skin, eyes, hair cards, clothes, teeth); 1024 textures; 52 expression blend shapes + Japanese vowel mouth shapes / 2〜3 万面。マテリアル 4〜5 個（肌、目、髪のカード、服、歯）。テクスチャ 1024。表情のブレンドシェイプ 52 個 + 日本語の母音の口形 | 40,000 faces; skin (including the face) color and normal maps at 2048, the rest (eyes, hair cards, clothes, teeth) stay 1024; blend shapes and mouth shapes same as tier B / 4 万面。肌（顔を含む）のカラーマップと法線マップは 2048、それ以外（目、髪のカード、服、歯）は 1024 のまま。表情のブレンドシェイプと口形はティア B と同じ | About 2.5 MB more per character; with 6〜8 main characters, about 15〜20 MB more per game, downloaded in batches as they appear / 人物ごとに約 2.5 MB 増え、主要人物 6〜8 人で 1 局あたり約 15〜20 MB 増える。登場に合わせて分けてダウンロードする |
| Talkable characters, walking version / 会話できる人物・歩行版 | 8k faces, 2 materials / 8k 面、マテリアル 2 個 | Same as tier B / ティア B と同じ | In the exploration camera characters are only 40〜80px tall / 探索カメラでは人物の高さは 40〜80px しかない |
| The crowd at the execution ground / 刑場の群衆 | Instanced low-poly models (5.5) / インスタンス化したローポリモデル（5.5） | Same as tier B / ティア B と同じ | Backlit silhouettes; the low poly is hidden by the light / 逆光のシルエットで、ローポリは光に隠れる |
| Props (jars, lamps, walking stick, chisel) / 小道具（壺、ランプ、杖、のみ） | 512; 1024 for those held in hand during dialogue / 512。会話中に手に持つものは 1024 | Same as tier B / ティア B と同じ | frontend 10.6.2 |
| Animation and mouth shapes / アニメーションと口形 | The same set / 同じもの | Same as tier B / ティア B と同じ | Animation is not split by tier / アニメーションはティアで分けない |

High-end phones first enter with tier B's resources and swap in the high-definition resources once they finish downloading in the background (frontend 10.6), so the time to first entry is the same on both tiers (≤ 10 seconds).

高性能機もまずティア B のリソースで入場し、高精細のリソースはバックグラウンドでダウンロードし終えてから差し替える（frontend 10.6）。だから最初に入るまでの時間は両ティアで同じ（≤ 10 秒）。

### 9.3 Materials upgraded to 2048 on high-end phones (4〜6 per scene) / 高性能機で 2048 に替えるマテリアル（シーンごとに 4〜6 種）

Chosen by “fills a lot of the screen, close to the camera” (the near view in 4.2). 〔UX's first pass; adjust by the actual screen share once the scenes are built〕

「画面に占める割合が大きく、カメラに近い」もので選ぶ（4.2 の近景）。〔UX の暫定案。シーンができたら実際の画面の占有率で調整する〕

| Scene / シーン | Materials upgraded to 2048 / 2048 に替えるマテリアル |
|---|---|
| The Syracuse plaza (including the execution ground) / シラクスの広場（刑場を含む） | Limestone flagstone ground, the castle's ashlar walls (including the steps and tower), the plaster walls of ordinary houses, old wood (doors, shutters), clay tiles / 石灰岩の石畳、王城の切り石の壁（階段と塔を含む）、庶民の家の漆喰の壁、古い木（扉、鎧戸）、瓦 |
| The throne room / 王座の間 | Polished dark stone floor, columns and walls, heavy cloth curtains, the throne / 磨かれた暗色の石の床、柱と壁、重厚な布の幕、王座 |
| The village / 村 | Dry-stone walls, the ground of the dirt road and wedding courtyard, the sheep shed's thatched roof, near-view wheat / 空積みの石垣、土の道と婚礼の中庭の地面、羊小屋の草葺き屋根、近景の麦 |
| The homeward road (four packs plus a shared roadside material pack) / 帰り道（4 つのパックと共通の道端マテリアルパック） | Shared pack: limestone dirt road, dry grassland, limestone outcrops. 川: wet rock and mud on the banks, the stakes of the broken bridge. 峠: scree and stone steps. 泉: wet rock and moss, plane-tree bark. 野の道: wheat, the cloth of the banquet / 共通パック：石灰岩の土の道、枯れ草の地面、石灰岩の露頭。川：岸の濡れた岩と泥、壊れた橋の杭。峠：砕石と石段。泉：濡れた岩と苔、スズカケノキの樹皮。野の道：麦、酒宴の布 |

In the first screen (17:30, southwest corner, section 10) the largest areas are the flagstone ground and the castle wall, so these two are made first.

最初の画面（17:30、南西の角、第 10 節）でいちばん面積が大きいのは石畳と王城の壁なので、この 2 つを最初に作る。

### 9.4 Where the extra art on high-end phones goes / 高性能機で増えるアートの使いどころ

**Characters** (about 30〜50% more; the bulk of it), in the order of 5.1:

**人物**（約 30〜50% 増、ここが大部分）、5.1 の順に：

1. Eyes: eyelid thickness, the tear line along the lower lid, wet highlights, and a more precise gaze when looking at the player.
   目：まぶたの厚み、下まぶたの涙の線、潤んだハイライト。プレイヤーを見るときの視線をより正確に。
2. Mouth: more accurate lip shape, smoother transitions between vowel mouth shapes, visible positions of teeth and tongue.
   口：唇の形をより正確に、母音の口形の間の移り変わりをより滑らかに、歯と舌の位置が分かるように。
3. Brows and forehead: the king's 「眉間の皺」 and the old man's wrinkles detailed with normals, without adding faces.
   眉と額：王の「眉間の皺」と老爺の皺は法線で細かく作り、面は増やさない。
4. Cloth: folds, seams and wear (normals).
   布：しわ、縫い目、すり切れ（法線）。
5. Skin: variation in flush and translucency (the sunburned Melos, the 蒼白 king).
   肌：血色と透明感の変化（日焼けしたメロス、蒼白な王）。
6. Denser hair cards. Hair is mostly covered by hats and headscarves (5.4), so it comes last.
   髪のカードをより密に。髪はほとんど帽子や頭巾で覆われている（5.4）ので最後。

Not done: pores, fine hair, sweaty shine, blood.

作らないもの：毛穴、産毛、汗のテカり、血。

**UV**: give the face large areas on the texture so tier B's 1024 isn't blurry in dialogue close-ups. Once the first MPFB character is made, Frontend measures close-ups on an iPhone and adjusts if blurry.

**UV**：テクスチャ上で顔に大きな領域を割り当て、ティア B の 1024 でも会話のアップでぼやけないようにする。最初の MPFB の人物ができたら、フロントエンドが iPhone でアップを実測し、ぼやけていれば調整する。

**Environment** (about 10〜20% more, mostly checks on each tier): for the few 2048 materials, chisel marks, worn shiny paths and grime at the base of walls (4.2) are clearer on high-end phones, but the pattern and color come from the same source image as tier B.

**環境**（約 10〜20% 増、主にティアごとの確認）：2048 にした数種のマテリアルでは、のみの跡、すり減って光る経路、壁の根元の汚れ（4.2）が高性能機でよりはっきり見えるが、模様と色はティア B と同じ元画像から来る。

### 9.5 Image requirements when upgrading and downgrading / ティアを上げ下げするときの画面の要件

When to upgrade or downgrade and how to decide is Frontend's call (D-019: upgrade only at camera cuts and when entering or leaving dialogue). UX's requirements for the image:

いつ上げ下げするか、どう判断するかはフロントエンドが決める（D-019：ティアを上げるのはカメラの切り替えと会話の出入りのときだけ）。画面についての UX の要件：

- **Swapping textures must not change colors.** 2048 and 1024 are scaled from the same source image, with the same average color and roughness. At the moment of the upgrade the player should only feel “it got sharper”, never “the colors changed”. At acceptance, compare side-by-side screenshots of both tiers.
  **テクスチャを替えても色が変わってはならない。** 2048 と 1024 は同じ元画像から縮小し、平均色と粗さをそろえる。ティアが上がったその瞬間、プレイヤーは「鮮明になった」とだけ感じるべきで、「色が変わった」と感じてはならない。受け入れ確認では両ティアのスクリーンショットを並べて比べる。
- **Never swap a character's version in the middle of speech.** During key moments (ux-design 8.3), the end-of-act page and the ending set piece, neither upgrade nor downgrade.
  **話している最中に人物の版を替えない。** 重要な瞬間（ux-design 8.3）、幕末ページ、エンディング演出の間はティアを上げも下げもしない。
- **When an immediate downgrade is needed (sustained frame drops), lower only the resolution; don't swap models or textures**: resolution changes are the least noticeable. Shadows, bloom, textures and the number of dialogue-version characters wait for the next camera cut (frontend 10.6.3).
  **すぐにティアを下げなければならないとき（フレーム落ちが続く）は、解像度だけを下げ、モデルやテクスチャは替えない**：解像度の変化がいちばん目立たない。影、ブルーム、テクスチャ、会話版の人物の数は次のカメラの切り替えまで待って替える（frontend 10.6.3）。
- **Colors don't change even at the lowest level**: the lowest level turns off only bloom and anti-aliasing, keeping color grading and vignetting (frontend 10.6.3).
  **最低レベルまで下げても色は変わらない**：最低レベルで切るのはブルームとアンチエイリアスだけで、カラーグレーディングとビネットは残す（frontend 10.6.3）。
- The ending card illustration is an offscreen 1080×640 render (frontend 10.5), with the same composition on both tiers.
  エンディングカードのイラストはオフスクリーンの 1080×640 レンダリング（frontend 10.5）で、構図は両ティアで同じ。

### 9.6 Acceptance checks / 受け入れ確認

- Each asset is looked at on two phones: tier B on an iPhone 12 (without an old phone, force tier B on zg's phone); the high-end tier on zg's iPhone 17 Pro Max.
  各アセットを 2 台のスマートフォンで見る：ティア B は iPhone 12（古い機種がなければ zg のスマートフォンで強制的にティア B にする）、高性能機は zg の iPhone 17 Pro Max。
- Tier B first: all five checkpoints in section 10 must pass on tier B.
  まずティア B：第 10 節の 5 つのチェックポイントをすべてティア B で通す。
- Then the high-end tier: it should only be “sharper”, with nothing new visible (9.1, item 3).
  次に高性能機：「より鮮明」になるだけで、新しいものが見えてはならない（9.1 第 3 項）。

---

## 10. How to ask zg to look at the realism prototype / zg にリアル版プロトタイプをどう見てもらうか

When PM shows S7 to zg, please ask zg to look at these five things on an iPhone:

PM が zg に S7 を見せるとき、zg には iPhone で次の 5 点を見てもらう：

1. **The first screen**: it opens straight onto the plaza at 17:30 at the start of act 1. The camera is in the southwest corner, looking northeast: the plaza cool in shadow, the golden castle and tower, a blue sky (S7's “southwest corner” view). Would you want to take a screenshot? (This is the bar for “stunning”.)
   **最初の画面**：開くとすぐ、第一幕開始の 17:30 の広場。カメラは南西の角から北東を見ている：影の中の冷たい広場、金色の王城と塔、青空（S7 の「南西の角」の視点）。スクリーンショットを撮りたくなるか。（これが「目を見張る」の基準）
2. **Wait for the sun to go down**: the line of light climbs the castle wall and finally disappears at the top of the tower. Without looking at the UI, can you feel “it's getting dark, time is almost up”?
   **太陽が沈むのを待つ**：王城の壁の光の線が上っていき、最後に塔の頂で消える。UI を見ずに「もうすぐ暗くなる、時間が迫っている」と感じられるか。
3. **Face to face with the old man**: does he seem like a real, frightened person? Is there any moment that feels off, such as a fixed stare, a mouth that doesn't move, or plastic-looking skin?
   **老爺と向き合う**：本当に怯えている人に見えるか。目が据わっている、口が動かない、肌がプラスチックのよう、など変だと感じる瞬間はないか。
4. **Switch to late night and midday**: without looking at the UI, can you tell roughly what time it is?
   **深夜と真昼に切り替える**：UI を見ずに、今がだいたい何時ごろか言えるか。
5. **Play for three minutes holding the phone**: is it laggy, does it get hot, how long did entry take (Frontend records the numbers at the same time)?
   **スマートフォンを持って 3 分遊ぶ**：カクつかないか、熱くならないか、入場までどれだけ待ったか（フロントエンドが同時に数字を記録する）。

Afterwards, PM asks zg to decide two things: which tier the realism goes to; and whether to raise the baseline phone and loosen the asset budget for image quality.

見終わったら、PM は zg に 2 つのことを決めてもらう：リアルさをどのティアまでやるか。画質のために最低ラインの機種を上げ、アセットの予算を緩めるか。

〔Decided〕 zg chose “tier B as the base, automatic upgrade on high-end phones” (D-019): the baseline phone stays the iPhone 12, and tier B's budget is loosened to ≤ 10 MB per scene and ≤ 10 seconds to first entry. The iPhone 12 numbers are estimates for now; measure them once we borrow an old phone. Art specs are in section 9.

〔決定済み〕zg は「ティア B を基本とし、高性能機は自動で上げる」を選んだ（D-019）：最低ラインの機種は引き続き iPhone 12、ティア B の予算はシーンごとに ≤ 10 MB、最初の入場まで ≤ 10 秒に緩めた。iPhone 12 の数字は今のところ推算で、古い機種を借りたら実測する。アート仕様は第 9 節を参照。

---

## 11. After the decision / 決定の後

1. **Frontend**: implement tiering and the upgrade/downgrade logic per D-019 (frontend-design 10.3, 10.6).
   **フロントエンド**：D-019 に従ってティア分けと上げ下げのロジックを書く（frontend-design 10.3、10.6）。
2. **UX produces style guide v1** (every asset marked with its tier B and high-end specs, 9.2):
   **UX がスタイルガイド v1 を作る**（すべてのアセットにティア B と高性能機の仕様を記す、9.2）：
   - a costume sheet and silhouette sketches (front, side, back) for each character;
     人物ごとの服装表とシルエットのスケッチ（正面、側面、背面）。
   - the plaza floor plan and sun path;
     広場の平面図と太陽の軌道。
   - a reference grade for each time of day;
     時刻ごとの参考のカラーグレーディング。
   - the final material list.
     マテリアル一覧の確定版。

   The slice half is already out: [style-guide/](style-guide/README.md), with costume sheets, three-view drawings and silhouettes for three characters and the plaza's material list. The plaza layout and sun path are in 4.1 and Frontend's F-2a scene layout. The reference grade for each time of day waits until F-2b's images are out.

   スライスの半分はすでにできている：[style-guide/](style-guide/README.md)。3 人の服装表、三面図、シルエットと広場のマテリアル一覧がある。広場の平面と太陽の軌道は 4.1 とフロントエンドの F-2a のシーン配置にある。時刻ごとの参考のカラーグレーディングは F-2b の画面ができてから作る。
3. **Run one character (Melos) through the whole process**: modeling (40,000 faces) → reduce to 20,000〜30,000 faces and 8k faces → rigging → two animations → mouth shapes → export glTF for both tiers → measure frame time on a real phone in S7, and check that the upgrade moment is only “sharper” (9.5). The parts that need Blender on zg's Mac are arranged through the coordinator.
   **1 人の人物（メロス）で全工程を通す**：モデリング（4 万面）→ 2〜3 万面と 8k 面に減らす → リギング → アニメーション 2 つ → 口形 → 両ティアの glTF を書き出す → S7 で実機のフレーム時間を測り、ティアが上がる瞬間が「より鮮明」なだけかを見る（9.5）。zg の Mac で Blender を使う部分は、コーディネーターを通して手配する。
4. Once that passes, produce the other characters and scenes in bulk.
   それを通ったら、ほかの人物とシーンをまとめて作る。

---

## Appendix A: v0.1's three stylized directions (no longer used) / 付録 A：v0.1 の 3 つの様式化された方向性（使用終了）

After seeing them, zg chose realism (D-016), and the three directions below are no longer used. They can still be switched in the prototype for comparison.

zg は見たうえでリアルを選んだ（D-016）ので、以下の 3 つの方向性はもう使わない。比較しやすいよう、プロトタイプではまだ切り替えられる。

| | A 絵本 | B 木版 | C 影絵 |
|---|---|---|---|
| In one sentence / ひとことで | Soft three-step shading, like an illustrated literary book / やわらかい 3 段階の明暗で、挿絵入りの文学書のよう | Two-step shading with thick outlines and flat 藍 and 朱, like a woodblock print / 2 段階の明暗に太い輪郭線、藍と朱のベタ塗りで、木版画のよう | Unlit silhouettes against an intense sky / 光を受けないシルエットを、濃い空の前に置く |
| Character readability (dialogue) / 人物の読みやすさ（会話） | Good / 良い | Medium / 中 | Poor / 悪い |
| Time-of-day readability / 時刻の読みやすさ | Good / 良い | Medium / 中 | Excellent for sunset and late night; weak at midday / 日没と深夜は非常に良い。真昼は弱い |
| Performance / 性能 | Good / 良い | Poor (outlines roughly double the draw calls) / 悪い（輪郭線で draw call が約 2 倍） | Best / 最良 |

What was kept:

残したもの：

- the 緋色 rule (section 6);
  緋色のルール（第 6 節）。
- the UI's paper and ink (section 8);
  UI の紙と墨（第 8 節）。
- a silhouette recognizable at a glance for each character (5.4);
  人物ごとにひと目で分かるシルエット（5.4）。
- C's silhouettes, turned into realistic backlit profiles (5.3).
  C のシルエットを、リアルな逆光の横顔に変えて使う（5.3）。

---

## Revision history / 改訂履歴

- v1.4.3 (2026-10-11): the 5.4 table follows style guide v1.1 (M3 characters): the sister's wedding outfit is now saffron yellow (no red other than 緋色; the white veil was changed); the shepherd boy wears no straw hat (straw hats are for the villagers bringing in the harvest, and a wide brim belongs to the traveler) and gets a sheepskin cape instead; the apprentice's short tunic covers both shoulders (Melos and セリヌンティウス are the ones with a bare shoulder).
  v1.4.3（2026-10-11）：5.4 の表をスタイルガイド v1.1（M3 の人物）に合わせて変更：妹の婚礼の衣装をサフラン色に（緋色以外の赤は使わないので、白いベールをやめた）。牧童は麦わら帽子をかぶらない（麦わら帽子は村で麦を刈る人のもので、つばの広い帽子は旅人のもの）ので、羊皮の肩掛けに変えた。弟子の短衣は両肩を覆う（片方の肩を出すのはメロスとセリヌンティウス）。
- v1.4.2 (2026-10-10): one sentence added to the color grading row in section 7: the stone and skin lit most brightly by fire should also keep a little blue rather than be pure orange (#54 UX review; Frontend suggested adding it in #57).
  v1.4.2（2026-10-10）：第 7 節のカラーグレーディングの行に一文を追加：火にいちばん明るく照らされた石と肌にも少し青を残し、純粋なオレンジにしない（#54 の UX レビュー、フロントエンドが #57 で書き込むよう提案）。
- v1.4.1 (2026-10-10): one sentence added to the color grading row in section 7: the night blue tints only where skylight reaches, and fire and firelight stay warm (Frontend found on the F-2c measurement page that the night grade turned fire blue-white; UX agreed to change it). One item added to 3.2: fill light in the shadows comes from both the sky and the lit ground, so the ambient light must include the ground (A-0 round 5, beige turning cyan in shadow).
  v1.4.1（2026-10-10）：第 7 節のカラーグレーディングの行に一文を追加：夜の青は空の光が届くところだけを染め、火と火の明かりは暖色のままにする（フロントエンドが F-2c の計測ページで夜のグレーディングが火を青白く染めているのを見つけ、UX が変更に同意）。3.2 に 1 項目追加：影の中の補助光は空と照らされた地面の両方から来るので、環境光には地面を含める（A-0 第 5 ラウンド、影の中のベージュが青くなった）。
- v1.4 (2026-10-10): the homeward road is set as 4 stops plus stretches of running side by side (S-081). Item 3 of 3.5 rewritten per stop (one bake per stop, 5 sets in total, real-time light on the running stretches); the homeward road entry in 4.2 lists materials per stop; the homeward road row in 9.3 lists them per pack. Details in the new [scenes/homeward-road.md](scenes/homeward-road.md).
  v1.4（2026-10-10）：帰り道を 4 つの停留地点と並んで走る区間に決定（S-081）。3.5 の第 3 項を地点ごとの書き方に変更（地点ごとに 1 セットずつベイク、計 5 セット、走る区間はリアルタイムの光）。4.2 の帰り道の項目は地点ごとにマテリアルを列挙し、9.3 の帰り道の行はパックごとに列挙した。詳細は新しく追加した [scenes/homeward-road.md](scenes/homeward-road.md)。
- v1.3 (2026-10-10): two changes to Melos's row in 5.4 to follow the original text: the dagger is hidden inside his clothes, out of sight, and in act 1 he carries what he bought on his back. The traveler now wears a sea-colored long tunic with the cloak over the left arm, so that the sash at the back shows. 5.4 and section 11 point to style guide v1 (the slice half). The paths of the decisions, data contract and original text in the basis row now point to their locations in the repo.
  v1.3（2026-10-10）：5.4 のメロスの行を原文に合わせて 2 か所変更：短剣は懐に隠れて見えない、第一幕では買った物を背負っている。旅人は海色の長衣にし、マントを左腕に掛けて、背中の帯が見えるようにした。5.4 と第 11 節でスタイルガイド v1（スライスの半分）を参照するようにした。根拠の行の決定事項、データ契約、原作のパスをリポジトリ内の場所に変更。
- v1.2 (2026-10-10): after looking at Frontend's F-2a plaza layout, four items were added to 4.1: a clear straight line from the city gate to 磔の柱, the door of 老爺の家 facing the plaza, the 磔台 at the foot of the pillar, and the head of the person on the pillar being lit last.
  v1.2（2026-10-10）：フロントエンドの F-2a の広場の配置を見て、4.1 に 4 項目を追加：城門から磔の柱まで何もない直線を残す、老爺の家の扉は広場向き、柱の根元の磔台、柱の上の人の頭部に最後に光が当たる。
- v1.1 (2026-10-06): aligned with Frontend in 4 places (frontend-design v0.9.4): high-end phones upgrade only skin (including face) textures; props 512 / 1024; an emergency downgrade lowers only resolution; colors don't change at the lowest level. Per D-019, section 9 rewritten as the art spec for two tiers: principles, comparison table, materials upgraded to 2048 on high-end phones, where the extra art goes, image requirements when upgrading and downgrading, acceptance checks (9.1〜9.6). Face textures in 5.2 split into two tiers; section 10 records zg's decision; the process in section 11 revised for two tiers.
  v1.1（2026-10-06）：フロントエンドと 4 か所をすり合わせた（frontend-design v0.9.4）：高性能機で上げるのは肌（顔を含む）のテクスチャだけ。小道具は 512 / 1024。緊急時のティア下げは解像度だけ。最低レベルでも色は変わらない。D-019 に従い、第 9 節を 2 つのティアのアート仕様に書き換えた：原則、比較表、高性能機で 2048 に替えるマテリアル、増えるアートの使いどころ、ティアを上げ下げするときの画面の要件、受け入れ確認（9.1〜9.6）。5.2 の顔のテクスチャを 2 つのティアに分けた。第 10 節に zg の決定を記録した。第 11 節の工程を 2 つのティア向けに変更した。
- v1.0 (2026-10-06): changed to realism per D-016. New:
  v1.0（2026-10-06）：D-016 に従ってリアルに変更。新規追加：
  - references and what to learn from them (section 2);
    参考と学ぶ点（第 2 節）。
  - the sun path computed from the real latitude (3.1), the shadow clock and the glint of the towers (3.4);
    実際の緯度で計算した太陽の軌道（3.1）、影の時計と塔楼の照り返し（3.4）。
  - layout requirements for the plaza (4.1), the material list and period accuracy (4.2, 4.3);
    広場の配置の要件（4.1）、マテリアル一覧と時代考証（4.2、4.3）。
  - how real the characters are, face size during dialogue, costumes and silhouettes (5.1〜5.4), the crowd at the execution ground (5.5), violence and injuries (5.7);
    人物のリアルさ、会話中の顔の大きさ、服装とシルエット（5.1〜5.4）、刑場の群衆（5.5）、暴力と傷（5.7）。
  - image treatment (section 7), how the budget is spent (section 9), checkpoints for zg (section 10).
    画面処理（第 7 節）、予算の使い方（第 9 節）、zg 向けのチェックポイント（第 10 節）。
  - The old three directions moved to appendix A.
    旧来の 3 つの方向性は付録 A に移した。
- v1.0 addendum the same day (after seeing the third version of S7):
  v1.0 同日の追記（S7 の第 3 版を見て）：
  - tone mapping set to Khronos PBR Neutral (section 7).
    トーンマッピングを Khronos PBR Neutral に決定（第 7 節）。
  - The first screen set to 17:30, from the southwest corner looking northeast (section 10).
    最初の画面を 17:30、南西の角から北東を見る視点に決定（第 10 節）。
  - The “evening” row in 3.3 now says that at 17:30 the plaza is already in shadow.
    3.3 の「夕方」の行に、17:30 には広場がすでに影の中にあることを明記。
  - The S7 review is in reviews/frontend-s7.md.
    S7 のレビューは reviews/frontend-s7.md にある。
- v0.1 (2026-10-06): three stylized directions, A 絵本, B 木版, C 影絵, recommending A.
  v0.1（2026-10-06）：3 つの様式化された方向性 A 絵本、B 木版、C 影絵。A を推奨。
