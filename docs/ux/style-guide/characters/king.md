# King Dionys (dialogue version) / 王ディオニス（会話版）

> 「おまえがか？」王は、憫笑した。「仕方の無いやつじゃ。おまえには、わしの孤独がわからぬ。」

In M3 the king becomes a character you can talk to (`char.king`, voice D-025: Algieba): in act 1 he tries Melos in the throne room (with the traveler as the 「連れの者」 and the apprentice present with their master), and a player guarding the hostage can also walk into the throne room to see him during the daytime on 一日目 to 三日目 (castle.md section 0).

M3 で王は会話できる人物になる（`char.king`、声は D-025：Algieba）：第一幕、玉座の間でメロスを裁く（旅人は「連れの者」として、弟子は親方について同席する）。人質を見守るプレイヤーは一日目〜三日目の昼間にも玉座の間に入って王に会える（castle.md 第 0 節）。

**Outline, colors, clothes and his look in the ending follow [ending-cast.md](ending-cast.md), "King Dionys"**; this page only adds what the dialogue version needs: face, hands, seated pose and how he looks in the throne room. For shared rules see the [README](../README.md).

**輪郭、色、衣服、エンディングでの姿は [ending-cast.md](ending-cast.md)「王ディオニス」に従う**。ここでは会話版に必要なものだけを足す：顔、手、座り姿勢、玉座の間での姿。共通のルールは [README](../README.md) を参照。

## Face (the focus of the dialogue version) / 顔（会話版の要点）

The king's dialogue camera is a **low-angle shot**: he sits on a dais 0.9 m high, with the player below it (castle.md section 3). His face is in the upper part of the frame, with the lamp above and in front of him.

王の会話カメラは**あおり**：彼は高さ 0.9 m の壇上に座り、プレイヤーは壇の下にいる（castle.md 第 3 節）。顔は画面の上方にあり、灯りは彼の前上方にある。

| Item / 項目 | Requirement / 要件 |
|---|---|
| Skin / 肌 | `#B89A86`, 蒼白, the lightest and coolest of all the characters (ending-cast.md). No flush of blood: even the lips lean gray / `#B89A86`、蒼白、全人物の中で最も明るく冷たい（ending-cast.md）。血色は足さない：唇も灰色寄り |
| Between the brows / 眉間 | Two very deep vertical lines (「刻み込まれたように深かった」), on the normal map, **clearly visible on tier B too**: in the low-angle shot with top light, these two lines are the darkest lines on his face / 二本のとても深い縦皺（「刻み込まれたように深かった」）、法線マップで作る。**ティア B でもはっきり見えること**：あおりで上からの光のとき、この二本が顔で最も暗い線になる |
| Eyes / 目 | Deep-set, falling into shadow under the hanging lamp; the brazier gives the eyes a little reflection (castle.md section 3), and without that glint you cannot read whom he is looking at. A cold gaze; he rarely blinks / 目のくぼみが深く、吊り灯の下で影に沈む。火鉢が目に少し反射光を与える（castle.md 第 3 節）。この光がないと誰を見ているのか読み取れない。目つきは冷たく、あまり瞬きしない |
| Facial hair / 髭 | Dark gray streaked with white, short and neat, **with the moustache parted**; the mouth is clearly visible / 白の混じった濃い灰色、短く整え、**口髭は左右に分ける**。口がはっきり見える |
| Hair / 髪 | Short, combed back, dark gray streaked with white / 短く、後ろへなでつけ、白の混じった濃い灰色 |

**Expressions** (ARKit's 52 blend shapes plus Japanese vowel mouth shapes, art-direction 9.2). castle.md 6.1 says the king's 「憫笑」 and 「北叟笑ん」 are faces, made as blend-shape presets rather than animation clips. The presets are defined here:

**表情**（ARKit の 52 個のブレンドシェイプに日本語の母音の口の形を加える、art-direction 9.2）。castle.md 6.1 は、王の「憫笑」「北叟笑ん」は顔であり、ブレンドシェイプのプリセットで作り、アニメーションクリップには数えないとしている。ここでそのプリセットを定める：

| Preset / プリセット | Original / 原作 | How it is made / 作り方 |
|---|---|---|
| 憫笑 (pitying smile) / 憫笑 | 「王は、憫笑した」 | One corner of the mouth raised (left), eyelids half lowered, brows still. No teeth. He looks at people as if at a child / 片方の口角を上げる（左）、まぶたを半分下ろし、眉は動かさない。歯は見せない。子どもを見るように人を見る |
| 北叟笑む (smirking to himself) / 北叟笑む | 「残虐な気持で、そっと北叟笑んだ」 | Both corners of the mouth raised slightly, mouth closed, eyes narrowed a little, gaze shifting to the side: a smile for himself, not for the other person / 両方の口角を軽く上げ、口は閉じ、目を少し細め、視線を横へそらす：相手にではなく自分に向けた笑い |
| 冷笑・嗤う (sneering) / 冷笑・嗤う | 「暴君は、嗄れた声で低く笑った」 | Chin raised slightly, one corner of the mouth raised, a touch of the nostrils. Beyond the voice, the facial movement stays small / 顎を少し上げ、片方の口角を上げ、小鼻を少し動かす。声以外の顔の動きは小さく |
| 孤独 (loneliness) / 孤独 | 「わしの孤独がわからぬ」「わしだって、平和を望んでいるのだが」 | Brows drawn toward the center and slightly up, gaze down, mouth relaxed. Appears only on lines like these, and **flashes and is withdrawn** back to his usual cold face / 眉を中央へ、少し上へ寄せ、視線を下げ、口は緩める。この種のセリフにだけ出し、**一瞬で引っ込めて**いつもの冷たい顔に戻る |
| Neutral / 平常 | — | A face where nothing moves. The king's default expression is no expression / 何も動かない顔。王のデフォルトの表情は無表情 |

- 「顔をあからめて」 in the ending: the blush does not change the skin color and is left to the narration (ending-cast.md). For the expression, use a lighter level of the 「孤独」 preset plus an averted gaze.
  エンディングの「顔をあからめて」：赤面で肌の色は変えず、語りに任せる（ending-cast.md）。表情は「孤独」プリセットの一段軽いものに、視線をそらすことを加える。

## Hands / 手

- Long fingers, prominent knuckles; hands that have never done labor.
  指が長く、関節が目立つ。労働をしたことのない手。
- A **signet ring** (gold, small) on the right index finger. No other jewelry: the only gold is the headband and this ring.
  右手の人差し指に**印章指輪**（金、小さい）。ほかの装身具はつけない：金は頭帯とこの指輪だけ。
- When seated, both hands rest on the arms of the throne; when speaking he lifts only the right wrist and fingers, never waving his arm (「静かに」).
  座っているとき両手は玉座の肘掛けに置き、話すときは右手の手首と指だけを上げ、腕は振らない（「静かに」）。

## Seated pose and the throne room / 座り姿勢と玉座の間

- The seated idle and talking use UAL's ready-made `Sitting_Idle_Loop` and `Sitting_Talking_Loop` (castle.md 6.1, frontend 15:57Z). Gestures are made separately and scheduled together with the ending-only animations.
  座った待機と会話には UAL の既製の `Sitting_Idle_Loop`、`Sitting_Talking_Loop` を使う（castle.md 6.1、フロントエンド 15:57Z）。手の仕草は別に作り、エンディング専用の動きと一緒に予定に入れる。
- When he is seated, the outer robe (deep purple P1) hangs from the left shoulder down onto the steps, covering part of the throne. **Deep purple is almost black in lamplight**: add a woven border about 3 cm wide along the robe's edge in dark gold-brown `#6E5A3A` (the same color as the guards' old bronze, not bright gold), so the cloth's edges and folds show when the lamplight catches them.
  座ると外衣（濃紫 P1）が左肩から階段へ垂れ、玉座の一部を覆う。**濃紫は灯火の下ではほとんど黒**：外衣の縁に幅約 3 cm の織り縁を足し、暗い金褐色 `#6E5A3A`（警吏の古い青銅と同じ色で、明るい金は使わない）にして、灯りが当たったときに布の縁と襞が分かるようにする。
- The curtains are deep indigo or deep purple (castle.md section 3), and the king's robe must not blur into the curtains: the king is a little warmer than the curtains (P1 leans a little toward red-purple, the curtains toward blue), and he also has the woven border and the gold headband. UX checks this once frontend has the throne-room frame.
  幕は濃い藍か濃紫（castle.md 第 3 節）で、王の外衣が幕と一体に溶けてはならない：王は幕より少し暖かい（P1 はやや赤紫寄り、幕は青寄り）うえ、織り縁と金の頭帯もある。フロントエンドが玉座の間の画面を出したら UX がこの点を確認する。

## Moving parts / 動く部分

- 4 bones for the hanging corner of the outer robe and the hem (the part lying on the steps when he is seated does not move).
  外衣の垂れた端と裾にボーン 4 本（座ったときに階段に垂れている部分は動かさない）。
- The headband and the ring are rigid bodies.
  頭帯と指輪は剛体。

## Acceptance check / 受け入れ確認

1. In the low-angle dialogue shot, the two lines between the brows and the glint in the eyes read on tier B (iPhone, art-direction 9.6).
   あおりの会話ショットで、眉間の二本の皺と目の反射光がティア B で読み取れる（iPhone、art-direction 9.6）。
2. Seen side by side, the 「憫笑」 and 「北叟笑む」 presets are distinguishable: the first is aimed at the person, the second avoids them.
   「憫笑」と「北叟笑む」の二つのプリセットを並べて見ると区別できる：前者は相手に向け、後者は相手を避ける。
3. Under the throne room's lamplight, the king's robe and the curtains separate.
   玉座の間の灯火の下で、王の外衣と幕が区別できる。
