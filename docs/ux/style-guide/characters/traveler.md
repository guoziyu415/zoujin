# Player: the traveler / プレイヤー・旅人

> はじめてこの市に来た。誰も、あなたを知らない。

The player themselves. Characters address them as 「旅の方」; they have no name (ux-design 5.1).

プレイヤー自身。登場人物からは「旅の方」と呼ばれ、名前はない（ux-design 5.1）。

## Only the back is seen / 見えるのは後ろ姿だけ

- When exploring, the camera is behind and above (ux-design 6.3); in dialogue only a shoulder shows in the lower-left foreground. So **the back is this character's front**: the best-looking, most recognizable things all go on the back and the rear sides.
  探索中、カメラは背後の上方にある（ux-design 6.3）。会話中は肩だけが左下の前景に見える。だから**後ろ姿がこの人物の正面**：いちばん見栄えがよく、いちばん見分けやすいものは、すべて背中と斜め後ろに置く。
- **The player's face never appears at a readable size.** The exploration camera can swing around to the front, but then the character is only 40–80 px tall and the face is covered by the shadow of the hat brim. The camera never stops within 6 m in front of the player; in the ending, "you" on the pillar are also shot from behind (ux-design 11.4 B).
  **プレイヤーの顔は読み取れる大きさでは映さない。** 探索カメラは正面に回り込めるが、そのとき人物は 40〜80 px しかなく、顔は帽子のつばの影に隠れる。カメラはプレイヤーの正面 6 m 以内では止まらない。エンディングで柱の上にいる「あなた」も背後から撮る（ux-design 11.4 B）。
- **No gender.** Neither the identity card nor how characters address the player distinguishes gender (「旅の方」), and the player speaks in their own voice. So the body is medium to slim, without emphasizing male or female: hair tucked into the hat, a long robe past the knees, a coat over the arm, no beard. [UX's decision; to be changed if PM disagrees]
  **性別を分けない。** アイデンティティカードでも人物からの呼び方でも性別を区別せず（「旅の方」）、プレイヤーは自分の声で話す。だから体は中肉やや細めで、男女を強調しない形にする：髪は帽子に収め、長衣は膝下まで、外套は腕に掛け、髭はない。〔UX の決定。PM に異論があれば変更する〕

## Three things recognizable at a glance (exploration camera, 60 px) / 一目で分かる三つの特徴（探索カメラ、60 px）

1. **Wide-brimmed hat**: from above and behind it is a large disc; no other character has one.
   **つば広の帽子**：背後の上方から見ると大きな円盤で、全人物の中でこの人物だけが持つ。
2. **Scarlet sash with hanging tails**: from behind, a horizontal band of red, with two tails hanging on the left.
   **緋色の腰帯と垂れた帯の端**：背後から見ると横一本の赤で、左側に二本垂れる。
3. **The water-skin strap worn across the body**: from the left shoulder diagonally to the right hip, with the water skin at the back right.
   **斜め掛けの水袋の紐**：左肩から右腰へ斜めに掛け、水袋は右後ろにある。

## Body / 体

| Item / 項目 | Requirement / 要件 |
|---|---|
| Height, build / 身長・体型 | 1.68 m, 7.25 heads tall, medium to slim / 1.68 m、7.25 頭身、中肉やや細め |
| Posture / 姿勢 | Stands naturally upright, shoulders relaxed. When the player is not giving input, the idle animation looks around (this is someone who has just arrived) / 自然にまっすぐ立ち、肩の力は抜けている。プレイヤーが操作していないときの待機モーションは周りを見回す（来たばかりの人だから） |
| Skin / 肌 | `#A47B5F`; only the hands, forearms, calves and back of the neck are visible / `#A47B5F`。見えるのは手、前腕、ふくらはぎ、首の後ろだけ |
| Hair / 髪 | Tucked into the hat; a little short hair shows at the back of the neck / 帽子に収め、首の後ろに短い髪が少しのぞく |

## Costume (slice: the same set in act 1 and the ending) / 衣装（スライス：第一幕とエンディングで同じ）

| # | Part / 部位 | Material and color / 素材と色 | How it is made / 作り方 | Approx. share of the 1024 map / 1024 マップ上の面積の目安 |
|---|---|---|---|---|
| ① | Long robe (chiton) / 長衣（キトン） | **Woad-dyed linen, faded sea color B1 `#4F6A7E`**, unevenly dyed, sun-bleached lighter on the shoulders and back / **大青で染めた亜麻、褪せた海の色 B1 `#4F6A7E`**。染めむらがあり、肩と背中は日に焼けてより淡い | Short sleeves; the hem about 10 cm below the knee. A slight bulge above the sash. Sea color is the player's own color, so it goes on this largest garment: it separates best from the honey-colored limestone (README "Color", item 3), and the scarlet sash also pops most against blue / 半袖、裾は膝下約 10 cm。腰帯の上が少し膨らむ。海の色はプレイヤー自身の色なので、面積の最も大きいこの一着に置く：蜜色の石灰岩の上で最も区別しやすく（README「色」第 3 項）、緋色の腰帯も青の上で最も映える | 30% |
| ② | Sash / 腰帯 | **Scarlet R1 `#8E271C`**, a woven band of madder-dyed wool, about 6 cm wide, matte / **緋 R1 `#8E271C`**。茜で染めた羊毛の織り帯、幅約 6 cm、つや消し | Wound twice around the waist, **knotted at the left hip, with two tails hanging about 30 cm**. From behind the whole horizontal band is visible; from the left rear the tails can be seen moving in the wind / 腰に二回巻き、**左の腰で結び、帯の端が二本約 30 cm 垂れる**。背後から横一本の帯全体が見え、左斜め後ろから帯の端が風に揺れるのが見える | 10% |
| ③ | Coat (旅の外套, world model `item.cloak`) / 外套（旅の外套、世界モデル `item.cloak`） | Undyed wool W0 `#CBBDA3`, grayed by the journey / 染めていない羊毛 W0 `#CBBDA3`、旅の間に灰色がかった | A cloth about 1.8 × 1.0 m, **folded and draped over the left forearm**, not worn: an early-summer evening is not cold, and wearing it would cover the sash on the back. It can be given to someone: the world model has no dedicated action for it, so it goes through the generic 「渡す」 and the narrator judges [inferred: e.g. to Melos in the ending; giving it to the hostage late at night would mean entering the royal castle, which is out of reach in the slice]. Once given away it is gone from the arm, and the outline is still recognizable by 1, 2 and the water-skin strap / 約 1.8 × 1.0 m の布を**畳んで左前腕に掛け**、羽織らない：初夏の夕方は寒くないうえ、羽織ると背中の腰帯が隠れる。人にあげることができる：世界モデルに専用のアクションはなく、汎用の「渡す」を通してナレーターが判定する〔推定：たとえばエンディングのメロスに。深夜の人質にあげるには王城に入る必要があり、スライスでは届かない〕。あげた後は腕から消え、輪郭は 1、2 と水袋の紐でまだ見分けられる | 15% |
| ④ | Wide-brimmed hat (petasos) / つば広の帽子（ペタソス） | Felt F1 `#6F5E4B` / フェルト F1 `#6F5E4B` | Low crown, brim about 45 cm across (a little larger than real ones, for the outline), with a cord tied under the chin / 低い山、つばの直径は約 45 cm（輪郭のため実物より少し大きい）。顎の下で結ぶ紐が一本ある | 12% |
| ⑤ | Water skin (`item.waterskin`) / 水袋（`item.waterskin`） | Goatskin, old leather K1 / 山羊の皮、古い革 K1 | About 25 × 35 cm, slung on a leather cord from the left shoulder diagonally to the right hip, the bag at the back right. 「水を渡す」 takes from here / 約 25 × 35 cm。革紐で左肩から右腰へ斜めに掛け、袋は右後ろ。「水を渡す」ときはここから取る | Prop counted separately (512 / 1024 in dialogue) / 小道具は別枠（512 / 会話時 1024） |
| ⑥ | Travel shoes (krepides) / 旅の靴（クレピデス） | Old leather K1 / 古い革 K1 | Open-toed laced leather boots, the laces wound up to mid-calf. Only people from far away wear them / つま先の開いた紐締めの革靴で、紐はふくらはぎの真ん中まで巻く。遠くから来た人だけが履く | 10% |

- Dust: on the hem and shoes, less than on Melos (the traveler did not walk ten ri today).
  埃：裾と靴に。メロスより少ない（旅人は今日十里を歩いていない）。
- The sash is the only scarlet (art-direction 6). No red on the hat, coat or water skin.
  緋色は腰帯の一か所だけ（art-direction 6）。帽子、外套、水袋には赤を入れない。

## Dialogue camera / 会話カメラ

- In the over-the-shoulder shot only the player's shoulder shows (ux-design 6.3); **the hat brim must not enter the frame and block the other person's face**. When frontend places the camera, it leaves a margin for the width of the brim.
  肩越しのショットではプレイヤーの肩だけが見える（ux-design 6.3）。**帽子のつばが画面に入って相手の顔を隠してはならない**。フロントエンドがカメラを配置するとき、つばの幅のぶん余裕を取る。
- What shows in the lower-left foreground is the sea-colored shoulder, the player's own color. A corner of the light-colored coat draped over the left arm may show.
  左下の前景に見えるのは海の色の肩で、それがプレイヤー自身の色。左腕に掛けた明るい色の外套の端がのぞいてもよい。

## Needed later (not in the slice) / 今後必要なもの（スライスには含まない）

- How the coat looks when worn (at night, in the rain), and how the sash shows when it is worn: to be decided once there are identities with night and rain scenes.
  外套を羽織った姿（夜、雨）、羽織ったときに腰帯をどう見せるか：夜景と雨景のあるアイデンティティができてから決める。
- The two identities 石屋の弟子 (the stonemason's apprentice) and 村の牧童 (the village shepherd boy): M3.
  石屋の弟子、村の牧童の二つのアイデンティティ：M3。

## Moving parts / 動く部分

- 2 bones per sash tail, moving with the wind and the steps.
  帯の端は一本につきボーン 2 本。風と歩調に合わせて動く。
- 2 bones for the hanging edge of the coat.
  外套の垂れた縁にボーン 2 本。
- 1 bone for the water skin.
  水袋にボーン 1 本。
- The hat is a rigid body that follows the head.
  帽子は剛体で、頭に追従する。

## Acceptance check / 受け入れ確認

1. In the 60 px silhouette the traveler is recognizable at a glance from behind and the rear sides (the three things above), and separable from Melos, the old man and the crowd.
   60 px のシルエットで、背後と斜め後ろから一目で分かり（上の三つの特徴）、メロス、老爺、群衆と区別できる。
2. At sunset the whole frame is warm, and the sash is still the most saturated color in the frame (art-direction 6; checked specifically on S7's sunset frame).
   日没時、画面全体が暖色に寄っても、腰帯が画面で最も彩度の高い色である（art-direction 6。S7 の日没の画面で特に確認する）。
3. In the dialogue camera the hat brim does not block the other person's face.
   会話カメラで帽子のつばが相手の顔を隠さない。
4. When the camera swings around to the front, the face is in the shadow of the hat brim, with no features clearly visible.
   正面に回って見たとき、顔は帽子のつばの影の中にあり、はっきり見える目鼻立ちはない。
