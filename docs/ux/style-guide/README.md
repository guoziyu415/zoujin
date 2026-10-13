# Style Guide v1.1 (Slice and M3) / スタイルガイド v1.1（スライスと M3）

| Item / 項目 | Content / 内容 |
|---|---|
| Purpose / 用途 | Concrete specs for art assets: whoever makes models and textures follows them, and UX accepts against them. art-direction sets the goals and principles; this applies them to each asset. / アートアセットの具体的な仕様。モデルやテクスチャを作る人はこれに従い、UX はこれに基づいて検収する。art-direction が目標と原則を定め、ここでそれを各アセットに落とし込む。 |
| Author / 作者 | UX. Technical numbers (polygon counts, texture sizes, bones) follow frontend-design 10.6 and art-direction 9.2; they are only cited here. / UX。技術的な数値（ポリゴン数、テクスチャサイズ、ボーン）は frontend-design 10.6 と art-direction 9.2 に従い、ここでは引用のみ。 |
| Basis / 根拠 | art-direction v1.3 (sections 4–7, 9); ux-design 5.1 (identity), 6.3 (camera), 11.1 (positions in the ending scene); the world model `worlds/hashire-merosu/1.0.0-draft/world.json` `characters` and `items`; the original text from Aozora Bunko (`worlds/hashire-merosu/sources/`); card A-0 (`docs/tasks/m2-0/A-0.md`) / art-direction v1.3（第 4〜7、9 節）、ux-design 5.1（アイデンティティ）、6.3（カメラ）、11.1（エンディング演出の立ち位置）、世界モデル `worlds/hashire-merosu/1.0.0-draft/world.json` の `characters`・`items`、原作の青空文庫版（`worlds/hashire-merosu/sources/`）、A-0 カード（`docs/tasks/m2-0/A-0.md`） |
| Scope / 範囲 | Slice (M2): three characters (Melos, the old man, the traveler); the other characters in the slice ending (walking-version fidelity); the square's materials. M3 (added in v1.1): the sister, the groom, Philostratus; dialogue versions of the king and Selinuntius; two identities, the stonemason's apprentice and the village shepherd boy; Melos's look at the royal castle and the village; extras and animals in the village, on the way back and at the castle. The square's layout and sun path are in art-direction 3 and 4.1 and in frontend F-2a's `assets/scenes/syracuse-square/layout.json`; the layout, light and materials of the castle, village and way back are in `docs/ux/scenes/`, none repeated here. / スライス（M2）：メロス、町の老爺、旅人の三人。スライスのエンディングに登場するその他の人物（歩行版の精度）、広場のマテリアル。M3（v1.1 で追加）：妹、花婿、フィロストラトス、王とセリヌンティウスの会話版、石屋の弟子と村の牧童の二つのアイデンティティ、王城と村でのメロスの姿、村・帰り道・王城のエキストラと動物。広場の平面と太陽の軌道は art-direction 3、4.1 とフロントエンド F-2a の `assets/scenes/syracuse-square/layout.json` にあり、王城・村・帰り道の平面、光、マテリアルは `docs/ux/scenes/` にあるので、ここでは繰り返さない。 |
| Last updated / 最終更新 | 2026-10-11 (v1.1, M3 characters) / 2026-10-11（v1.1、M3 の人物） |

## Files / ファイル

| File / ファイル | Content / 内容 |
|---|---|
| [characters/melos.md](characters/melos.md) | Melos: entering the town in act 1, two sets for the ending / メロス：第一幕の入城、エンディングの二着 |
| [characters/old-man.md](characters/old-man.md) | The old man of the town / 町の老爺 |
| [characters/traveler.md](characters/traveler.md) | Player: the traveler / プレイヤー・旅人 |
| [characters/views.svg](characters/views.svg) | Three-view drawings (front, side, back) of the three characters and a height comparison at the same scale / 三人の三面図（正面・側面・背面）と同縮尺の身長比較 |
| [characters/silhouettes.svg](characters/silhouettes.svg) | 60px silhouette comparison (size in the exploration camera) / 60px シルエット比較（探索カメラでの大きさ） |
| [characters/ending-cast.md](characters/ending-cast.md) | The other characters in the slice ending: Selinuntius, the king, the guard, the crowd, the girl in the scarlet cloak (walking version) / スライスのエンディングのその他の人物：セリヌンティウス、王、警吏、群衆、緋のマントの少女（歩行版） |
| [characters/ending-cast.svg](characters/ending-cast.svg) | Front colors of the ending characters, 60px silhouettes, and whether they can be found from behind the crowd / エンディング人物の正面の色、60px シルエット、群衆の後ろから見て見つけられるか |
| [plaza-materials.md](plaza-materials.md) | Final plaza material list / 広場マテリアル一覧の確定版 |
| **M3 (v1.1) / M3（v1.1）** | |
| [characters/sister.md](characters/sister.md) | Melos's sister: herding sheep on ordinary days, the wedding / メロスの妹：平日の羊飼い、婚礼 |
| [characters/groom.md](characters/groom.md) | The groom: ordinary days, the wedding / 花婿：平日、婚礼 |
| [characters/philostratus.md](characters/philostratus.md) | Philostratus / フィロストラトス |
| [characters/king.md](characters/king.md) | The king's dialogue version: face, expression presets, hands, seated pose / 王の会話版：顔、表情プリセット、手、座り姿勢 |
| [characters/selinuntius.md](characters/selinuntius.md) | Selinuntius's dialogue version: face, workshop, being summoned, three days in the colonnade / セリヌンティウスの会話版：顔、工房、召喚される場面、柱廊での三日間 |
| [characters/apprentice.md](characters/apprentice.md) | Player: the stonemason's apprentice / プレイヤー・石屋の弟子 |
| [characters/shepherd-boy.md](characters/shepherd-boy.md) | Player: the village shepherd boy / プレイヤー・村の牧童 |
| [characters/m3-extras.md](characters/m3-extras.md) | Bandits, courtiers, villagers, people on the way back, sheep, dogs, donkeys; the master list of extras that are "not placed" / 山賊、群臣、村人、帰り道の人々、羊、犬、ロバ。エキストラを「置かない」ものの総表 |
| [characters/m3-cast.svg](characters/m3-cast.svg) | Front colors of the M3 characters, back views of the two new identities, 60px silhouettes, "looking together" in the village and workshop / M3 人物の正面の色、新しい二つのアイデンティティの背面、60px シルエット、村と工房での「一緒に見る」 |
| [characters/m3-views.svg](characters/m3-views.svg) | Three views handed to frontend 5 (F-16): the king, Selinuntius (workshop), the sister (ordinary days, wedding), the groom, Philostratus, the stonemason's apprentice, the village shepherd boy; front / side / back / フロントエンド 5（F-16）に渡す三面図：王、セリヌンティウス（工房）、妹（平日・婚礼）、花婿、フィロストラトス、石屋の弟子、村の牧童。正面 / 側面 / 背面 |

## Rules shared by all characters / すべての人物に共通するルール

### Size / サイズ

1 unit = 1 meter, with the soles at 0. Height is the top of the head when standing straight in bare feet.

1 単位 = 1 メートル、足の裏が 0。身長は素足でまっすぐ立ったときの頭頂の高さ。

| Character / 人物 | Height / 身長 | Head-to-body / 頭身 | Build / 体型 |
|---|---|---|---|
| Melos / メロス | 1.75 m | 7.5 | Lean with long limbs, muscular but not bulky / 痩せて手足が長く、筋肉はあるが盛り上がらない |
| Old man of the town / 町の老爺 | 1.68 m (about 1.56 m at the top of the head when stooped) / 1.68 m（猫背で頭頂は約 1.56 m） | 7 | Thin, stooped / 痩せて猫背 |
| Traveler (player) / 旅人（プレイヤー） | 1.68 m | 7.25 | Medium to slim, gender-neutral (see traveler.md) / 中肉やや細め、性別を問わない（traveler.md 参照） |

Characters in the ending (ending-cast.md) are aligned to this: the king is tallest at 1.82 m, Selinuntius is widest at 1.72 m, and the girl in the scarlet cloak is about 1.50 m.

エンディングの人物（ending-cast.md）はこれに合わせる：王が 1.82 m で最も高く、セリヌンティウスは 1.72 m で最も幅が広く、緋のマントの少女は約 1.50 m。

Added for M3:

M3 で追加：

| Character / 人物 | Height / 身長 | Head-to-body / 頭身 | Build / 体型 |
|---|---|---|---|
| Melos's sister / メロスの妹 | 1.55 m | 7 | Small and slender, shoulders slightly narrow / 小柄で細く、肩はやや狭い |
| Groom / 花婿 | 1.74 m | 7.5 | Sturdy, broad shoulders / がっしりして肩幅が広い |
| Philostratus / フィロストラトス | 1.70 m | 7.25 | Thin, weight forward / 痩せて重心が前 |
| Stonemason's apprentice (player) / 石屋の弟子（プレイヤー） | 1.66 m | 7.25 | Slim, gender-neutral / 細身で性別を問わない |
| Village shepherd boy (player) / 村の牧童（プレイヤー） | 1.48 m | 6.5 | A child, the shortest of all characters / 子ども。全人物で最も背が低い |

### Color / 色

Only low-saturation colors that natural dyes can produce (art-direction 5.4). The table below gives **sRGB values of the base color texture**, measured under neutral white light. On screen, lighting and grading change them; acceptance is judged on the tier B image on an iPhone. [UX's initial values; to be adjusted once real-device images from A-0 and F-2b are available]

天然染料で染められる低彩度の色だけを使う（art-direction 5.4）。下表は**ベースカラーテクスチャ（base color）の sRGB 値**で、中性の白色光の下で測定したもの。実際の画面では光と色調整の影響を受けるため、検収は iPhone のティア B の画面で行う。〔UX の暫定値。A-0 と F-2b の実機画面が出た後に調整する〕

| ID / 番号 | Name / 名前 | sRGB | Used for / 用途 |
|---|---|---|---|
| W0 | Undyed wool / 染めていない羊毛 | `#CBBDA3` | Melos's bundle and waist cord; the traveler's coat / メロスの包みと腰縄、旅人の外套 |
| L0 | Undyed linen / 染めていない亜麻 | `#BDB39D` | The old man's underclothes; the square's cloth awnings / 老爺の下着、広場の布の日よけ |
| O1 | Ochre (faded) / 黄土（褪色） | `#A5733F` | Melos's tunic / メロスの短衣 |
| N1 | Walnut brown / 胡桃色 | `#5E4636` | Small items: straps, staff head / 小物：帯、杖の頭 |
| B1 | Faded woad (sea color) / 褪せた大青（海の色） | `#4F6A7E` | The traveler's long robe (the player's own color) / 旅人の長衣（プレイヤー自身の色） |
| G1 | Olive / オリーブ | `#6B6A45` | Later: the groom / 今後：花婿 |
| A1 | Old gray-brown wool / 古い灰褐色の羊毛 | `#7E776C` | The old man's outer robe / 老爺の外衣 |
| K1 | Old leather (vegetable-tanned) / 古い革（植物なめし） | `#6E4A2E` | Sandals, water skin, cords / サンダル、水袋、紐 |
| F1 | Felt / フェルト | `#6F5E4B` | The traveler's hat / 旅人の帽子 |
| R1 | Scarlet (madder-dyed wool) / 緋（茜染めの羊毛） | `#8E271C` | Only three things: the player's waist sash (the same one for all three identities) and the scarlet cloak in the ending (the UI's causal lines use the UI color `#b93a26`, not listed here) / 三つだけ：プレイヤーの腰帯（三つのアイデンティティで同じもの）、エンディングの緋のマント（UI の因果線は UI 色 `#b93a26` を使い、ここには含めない） |
| P1 | Murex purple (deep) / 貝紫（濃） | `#46304A` | Only the king's robe (ending-cast.md) / 王の外衣のみ（ending-cast.md） |
| **M3 (v1.1) / M3（v1.1）** | | | |
| W2 | Brown wool (undyed) / 褐色の羊毛（無染色） | `#6E5B48` | The sister's ordinary-day robe; bandits / 妹の平日の長衣、山賊 |
| B2 | Light woad / 淡い大青 | `#7D93A0` | Only the sister's headscarf / 妹の頭巾のみ |
| S1 | Saffron yellow (faded) / サフラン黄（褪色） | `#AE9150` | Only the bride's robe / 花嫁の長衣のみ |
| S2 | Saffron gauze / サフランの薄絹 | `#D2BF8E` | The bride's veil and sash / 花嫁のベールと帯 |
| M1 | Myrtle green / ミルトの緑 | `#4E5B3B` | Wedding wreaths and foliage / 婚礼の花輪と枝葉 |
| T1 | Gray-brown linen / 灰褐色の亜麻 | `#85796A` | Philostratus's tunic / フィロストラトスの短衣 |
| U1 | Earth-colored wool / 土色の羊毛 | `#7A6A52` | The stonemason's apprentice's tunic (the player's own color) / 石屋の弟子の短衣（プレイヤー自身の色） |
| N3 | Deep walnut / 濃い胡桃色 | `#57432F` | The village shepherd boy's tunic (the player's own color) / 村の牧童の短衣（プレイヤー自身の色） |
| FL | Natural fleece (fur) / 羊毛の生成り（毛皮） | `#D5C9B0` | The shepherd boy's sheepskin cape / 牧童の羊皮のケープ |
| ST | Straw / 草 | `#C9B27A` | The wheat harvesters' straw hats / 麦刈りの人の麦わら帽子 |

- Base colors are not below sRGB 30 or above 240 (too dark or too white is unrealistic under PBR).
  ベースカラーは sRGB 30 未満にも 240 超にもしない（暗すぎ・白すぎは PBR では不自然）。
- **Scarlet must stand out through saturation** (art-direction 6): R1 must be the most saturated color in the frame. No red is used other than scarlet; ochre O1 leans yellow-brown and must not read as red.
  **緋色は彩度で際立たせる**（art-direction 6）：R1 は画面で最も彩度の高い色でなければならない。緋色以外に赤は使わない。黄土 O1 は黄褐色寄りで、赤に見えてはいけない。
- Clothes must separate from the limestone: the square's ground and walls are honey-tinted white (plaza-materials.md), so **the largest color area on each character must be darker or more saturated than the wall**. Melos's ochre, the traveler's sea color and the old man's gray-brown were chosen this way: the three main colors are yellow-brown, blue and gray, with distinct hues. The same in the village: plaster walls lean earthy yellow and the wheat is golden, so the sister's brown and the shepherd boy's deep walnut are both darker than they are.
  衣服は石灰岩と区別できなければならない：広場の地面と壁は蜜色がかった白（plaza-materials.md）なので、人物の**最も面積の大きい色は壁より暗いか、壁より彩度が高い**こと。メロスの黄土、旅人の海の色、老爺の灰褐色はこの基準で選んだ。三人の主色は黄褐色・青・灰色で、色相も離れている。村でも同様で、漆喰の壁は土っぽい黄色、麦は金色なので、妹の褐色と牧童の濃い胡桃色はどちらもそれらより暗い。
- **Each of the three player identities has its own "own color"**, placed on the largest garment and paired with the scarlet sash: the traveler's sea color B1, the apprentice's earth color U1, the shepherd boy's deep walnut N3.
  **三つのプレイヤー・アイデンティティにはそれぞれ「自分の色」がある**。最も面積の大きい衣服に置き、緋色の帯と組み合わせる：旅人は海の色 B1、弟子は土色 U1、牧童は濃い胡桃色 N3。
- Saffron yellow S1 is less saturated than scarlet, but the bride covers a large area and is in full daylight: once the wedding frame is available, check whether scarlet is still the most striking (sister.md).
  サフラン黄 S1 の彩度は緋より低いが、花嫁は面積が大きく、しかも真昼にいる。婚礼の画面が出たら、緋がまだ最も目立つかを確認する（sister.md）。

### Skin / 肌

| Character / 人物 | Base sRGB / ベース sRGB | Notes / 説明 |
|---|---|---|
| Melos / メロス | `#8A5A3C` | A deeply tanned herdsman (art-direction 5.1). The exposed right shoulder and arm are equally dark. / 日に焼けて黒い牧人（art-direction 5.1）。露出した右肩と腕も同じく黒い。 |
| Old man of the town / 町の老爺 | `#A07A5F` | Weathered for many years, grayish; wrinkles come from the normal map (9.4). / 長年日に焼けて灰色がかっている。皺は法線マップで表現する（9.4）。 |
| Traveler / 旅人 | `#A47B5F` | Only the hands, calves and back of the neck are visible. / 見えるのは手、ふくらはぎ、首の後ろだけ。 |

- It needs a flush of blood and a sense of translucency, with no pores, fine hair or oily shine (5.1).
  血色と透け感を出し、毛穴、産毛、脂のテカリは作らない（5.1）。
- No blood (9.4). In the original, Melos's "口から血が噴き出た" is not acted out.
  血は描かない（9.4）。原作でメロスの「口から血が噴き出た」は演じない。

### Wear and dirt / 摩耗と汚れ

- The hem of clothing has a 10–15 cm band of dust color, heavier toward the bottom; feet and calves also carry dust.
  衣服の裾には 10〜15 cm の埃色の帯があり、下へいくほど濃い。足とふくらはぎにも埃がつく。
- Cloth edges are fuzzy, and knees, elbows and shoulders are sun-faded.
  布の縁は毛羽立ち、膝、肘、肩は日に褪せている。
- Dirt and wear are painted into the color map, **and both tiers use the same source image**; the stronger devices just show it more clearly (9.1, item 3).
  汚れと摩耗は色マップに描き込み、**二つのティアで同じ元画像を使う**。高性能機ではより鮮明に見えるだけ（9.1 第 3 項）。

### Polygon counts and textures (cited from art-direction 9.2, not set separately) / ポリゴン数とテクスチャ（art-direction 9.2 を引用、別途定めない）

- Dialogue version: 20–30k polygons on tier B, 40k on strong devices; 4–5 materials (skin, eyes, hair cards, clothes, teeth).
  会話版：ティア B で 2〜3 万ポリゴン、高性能機で 4 万ポリゴン。マテリアルは 4〜5 個（肌、目、髪のカード、衣服、歯）。
- **All clothes, shoes, straps and carried items share one "clothes" material and one 1024 texture** (1024 on both tiers, 9.2). So each character's costume table lists roughly how much area of that texture each part takes.
  **衣服、靴、帯、身につけるものはすべて「衣服」という一つのマテリアルと一枚の 1024 テクスチャを共有する**（両ティアとも 1024、9.2）。そのため各人物の衣装表に、このテクスチャ上で各部位がおよそどれだけの面積を占めるかを書いている。
- Walking version: 8k polygons, 2 materials, all parts present, same silhouette.
  歩行版：8k ポリゴン、マテリアル 2 個、すべての部位を備え、シルエットは同じ。
- Props held in the hand (staff, water skin) are counted separately: 512 when exploring, 1024 when held in the hand during dialogue (9.2).
  手に持つ小道具（杖、水袋）は別枠：探索では 512、会話中に手に持つ場合は 1024（9.2）。

### Silhouette / シルエット

The exploration camera is about 15.5 m from the character at a depression angle of about 29° (ux-design 6.3: distance 13.5, height 7.6), so on a phone a character is only 40–80 px tall. Each character needs **three things recognizable at this size**, listed in its costume table. Acceptance:

探索カメラは人物から約 15.5 m、俯角は約 29°（ux-design 6.3：距離 13.5、高さ 7.6）で、手機上では人物は高さ 40〜80 px にしかならない。各人物にはこの大きさで見分けられる**三つの特徴**が必要で、それぞれの衣装表に書いてある。検収：

1. In F-2b's square, view the character from front, back, left and right with the exploration camera, render it as a pure black silhouette, and shrink it to 60 px tall.
   F-2b の広場で、探索カメラを使って人物を前後左右の四方向から見て、真っ黒なシルエットにレンダリングし、高さ 60 px に縮小する。
2. The three characters can be told apart at a glance from each other and from the execution-ground crowd (art-direction 5.5).
   三人の人物が、互いに、また刑場の群衆（art-direction 5.5）とも、一目で見分けられる。
3. If not, fix the silhouette first (hat, carried items, pose), not the color.
   見分けられない場合は、まずシルエット（帽子、背負うもの、姿勢）を直し、色には頼らない。

[silhouettes.svg](characters/silhouettes.svg) is an eye-level illustration; the real test uses the in-game camera.

[silhouettes.svg](characters/silhouettes.svg) は水平視点の図であり、本当のテストにはゲーム内のカメラを使う。

### Moving parts / 動く部分

No cloth simulation on the phone (frontend decides), but these places must move, using a few bones:

手機では布のシミュレーションは行わない（フロントエンドが決める）が、次の箇所は動かす必要があり、数本のボーンで動かす：

- Hem: swings when walking and running.
  裾：歩く・走るときに揺れる。
- Tails of straps and folded edges of coats: move gently in the wind (art-direction 7, "wind").
  帯の端と外套の折り返し：風でゆるやかに動く（art-direction 7「風」）。
- Carried items and the water skin: sway with the steps.
  背負うものと水袋：歩調に合わせて揺れる。

The motion is the same on both tiers (9.2).

動きは両ティアで同じ（9.2）。

## To be added later / 後で補うもの

- Two identities, the royal castle's maidservant and the guard's apprentice (second version, ux-design 5.2).
  王城の侍女、警吏の見習いの二つのアイデンティティ（第二版、ux-design 5.2）。
- How the traveler's coat is draped (night, rain): to be decided once identities with night and rain scenes exist (traveler.md).
  旅人の外套の羽織り方（夜、雨）：夜景と雨景のアイデンティティができてから決める（traveler.md）。
- The figures (m3-cast.svg, m3-views.svg) are generated from `ux/tools/style-guide/m3_cast.py` and `m3_views.py` in the project folder, using the same mannequin as gen_views.py and ending_cast.py.
  図（m3-cast.svg、m3-views.svg）はプロジェクトフォルダの `ux/tools/style-guide/m3_cast.py`、`m3_views.py` で生成し、gen_views.py、ending_cast.py と同じマネキンを使う。
