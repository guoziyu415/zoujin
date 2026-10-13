# Selinuntius (dialogue version) / セリヌンティウス（会話版）

> セリヌンティウスは無言で首肯き、メロスをひしと抱きしめた。

In M3 Selinuntius becomes a character you can talk to (`char.selinuntius`, voice D-025: Iapetus). The 石屋の弟子 identity starts in his workshop, and a player guarding the hostage is by his side for all three days (castle.md, north colonnade `hostage-column`).

M3 でセリヌンティウスは会話できる人物になる（`char.selinuntius`、声は D-025：Iapetus）。石屋の弟子は彼の工房から始まり、人質を見守るプレイヤーは三日間ずっと彼のそばにいる（castle.md 北の柱廊 `hostage-column`）。

**Outline, colors, and his look bound at the execution ground and after being let down follow [ending-cast.md](ending-cast.md), "Selinuntius"**; this page adds the face the dialogue version needs, and his three looks before the execution ground. For shared rules see the [README](../README.md). Figure: [m3-cast.svg](m3-cast.svg) (him in his apron in the "Workshop" panel).

**輪郭、色、刑場で縛られた姿と下ろされた後の姿は [ending-cast.md](ending-cast.md)「セリヌンティウス」に従う**。ここでは会話版に必要な顔と、刑場以前の三つの姿を足す。共通のルールは [README](../README.md) を参照。図：[m3-cast.svg](m3-cast.svg)（「工房」の前掛けをつけた彼）。

## Face / 顔

| Item / 項目 | Requirement / 要件 |
|---|---|
| Face / 顔 | A broad face, square jaw, calm. In the original he says little (「無言で首肯き」「メロスは来ます、とだけ答え」), so **his expressions are small**: when he talks, his brow and mouth movements are half the size of Melos's / 幅広の顔、角ばった顎、落ち着いている。原作では口数が少ない（「無言で首肯き」「メロスは来ます、とだけ答え」）ので、**表情は小さく**：話すときの眉と口の動きはメロスの半分 |
| Facial hair / 髭 | A short, neat dark-brown beard, about 1 cm, **with the moustache parted** (ending-cast.md). A little longer after three days (below) / 短く整った濃い茶色の髭、約 1 cm、**口髭は左右に分ける**（ending-cast.md）。三日後には少し伸びる（下記） |
| Eyes / 目 | Steady; he does not look away from people. This is the biggest difference between him and the flustered フィロストラトス and the king, who avoids people / 落ち着いていて、人を見るときに目をそらさない。これが、慌てやすいフィロストラトスや人を避ける王との最大の違い |

**Expression presets** (52 blend shapes + vowel mouth shapes):

**表情プリセット**（ブレンドシェイプ 52 個＋母音の口の形）：

| Preset / プリセット | When / いつ | How it is made / 作り方 |
|---|---|---|
| 首肯く (nodding) / 首肯く | His most common answer / 彼の最もよく使う返事 | The chin nods slowly once, eyes stay on the other person, mouth closed. Together with the head-bone animation / 顎をゆっくり一度うなずかせ、目は相手から離さず、口は閉じる。頭のボーンの動きと一緒に |
| 信じている (trusting) / 信じている | 「メロスは来ます」 | Level brows, relaxed corners of the mouth, a steady gaze. No smile / 眉は平ら、口角は緩め、目つきは落ち着いている。笑わない |
| 一瞬の疑い (a moment's doubt) / 一瞬の疑い | 三日目 16:00 (beat.s2, in the colonnade) / 三日目 16:00（beat.s2、柱廊で） | The gaze drops and slides aside for a moment, the brows knit slightly, then come straight back. **Just a flash**, seen only by someone beside him (castle.md section 0) / 視線が一瞬下へ、横へそれ、眉が軽く寄り、すぐに戻る。**一瞬で過ぎる**。そばにいる人にだけ見える（castle.md 第 0 節） |
| 憔悴 (worn out) / 憔悴 | 三日目 | Heavier eyelids, corners of the mouth a little lower (layered on top of other presets) / まぶたを少し重く、口角を少し下げる（ほかのプリセットに重ねる） |

## Three looks before the execution ground / 刑場以前の三つの姿

| Look / 姿 | When, where / いつ、どこで | Compared with the ending version in ending-cast.md / ending-cast.md のエンディング版との比較 |
|---|---|---|
| **Workshop / 工房** | Around 17:30 on 一日目 (the apprentice's start, the day of the pact). The workshop / 一日目 17:30 前後（弟子の開始、約束の日）。工房 | The same tunic with the bare left shoulder, **wearing a leather apron** (dark brown leather, from the chest to below the knee, two straps crossing at the back), sleeves rolled up, stone dust all over his hands and apron. A chisel or mallet in his hand. When he is called away the apron stays on the workshop wall (ending-cast.md) / 同じ左肩を出した短衣で、**革の前掛けをつけている**（濃い茶色の革、胸から膝下まで、背中で二本の紐が交差する）。袖をまくり、手と前掛けは石の粉だらけ。手には鑿か木槌。呼び出されたとき、前掛けは工房の壁に残る（ending-cast.md） |
| **Summoned / 召喚される** | 一日目 23:30 (beat.06). The throne room / 一日目 23:30（beat.06）。玉座の間 | No apron, the stone dust still on him. Called out of his home late at night, with an outer robe of undyed wool W0 over his shoulders [inferred: going out at night], taken off him when he enters the throne room. After he embraces Melos, **his hands are bound in front of him with hemp rope** / 前掛けはなく、石の粉はまだついている。深夜に家から呼び出され、肩に染めていない羊毛 W0 の外衣を羽織っている〔推定：夜の外出〕。玉座の間に入るときに取り上げられる。メロスと抱き合った後、**両手を体の前で麻縄で縛られる** |
| **Three days in the colonnade / 柱廊での三日間** | Late night on 一日目 to the evening of 三日目 (before being marched to the execution ground). The north colonnade of the courtyard, second row of pillars / 一日目深夜〜三日目夕方（刑場へ引かれる前）。中庭の北の柱廊、二列目の柱 | Sitting on the ground with his back to a pillar, hands bound in front, the other end of the rope tied to an iron ring on the pillar. He can stand up and turn around but cannot walk away. His clothes age day by day, **in two stages** (castle.md 6.1): **stage 1** (night of 一日目 to 二日目): clothes wrinkled, some of the stone dust gone; **stage 2** (三日目): clothes dirty, neckline loose, beard about 1.5 cm, face sallow, bluish under the eyes (one mask layer on the color map, switched on by stage, the same method as Melos on the road). No wounds: he was not beaten (ending-cast.md) / 柱に背をもたせて地面に座り、両手は体の前で縛られ、縄のもう一端は柱の鉄の輪につながれている。立ち上がることも向きを変えることもできるが、離れることはできない。衣服は日ごとに古びていき、**二段階に分ける**（castle.md 6.1）：**第 1 段階**（一日目夜〜二日目）：衣服に皺が寄り、石の粉が少し落ちる。**第 2 段階**（三日目）：衣服は汚れ、襟元が緩み、髭は約 1.5 cm、顔色は暗く、目の下が青い（色マップのマスク一層で、段階に応じてオンにする。道中のメロスと同じやり方）。傷は作らない：殴られてはいない（ending-cast.md） |

- When he is marched to the execution ground (evening of 三日目), his hands are re-tied behind his back, which is the ending-version look.
  刑場へ引かれるとき（三日目夕方）、両手は背中で縛り直され、それがエンディング版の姿になる。
- The three looks and the ending version use **the same model**: the apron and the outer robe are each a mesh that can be switched on and off; the two bound-hands poses (in front, behind) are animations, and the rope is two meshes, one shown per pose.
  三つの姿とエンディング版は**同じモデル**を使う：前掛けと外衣はそれぞれオン・オフできるメッシュ。縛られた手の二つの姿勢（前、後ろ）はアニメーションで、縄はメッシュを二つ用意して姿勢に応じて一つを表示する。

## Dialogue version / 会話版

- The dialogue version per art-direction 9.2; polygon counts and textures as given there.
  art-direction 9.2 の会話版。ポリゴン数とテクスチャはそこに従う。
- Talking while seated in the colonnade: the seated idle and talking use UAL's `Sitting_Idle_Loop` and `Sitting_Talking_Loop` (same as the king), hands in front, no hand gestures when speaking (they are bound). The dialogue camera crouches to meet him at eye level: with the player standing, the camera would look down too steeply, so the over-the-shoulder height is taken from his seated eye height [frontend decides how: the player automatically sits or crouches on approaching `hostage-column`].
  柱廊で座って話す：座った待機と会話には UAL の `Sitting_Idle_Loop`、`Sitting_Talking_Loop` を使い（王と同じ）、両手は体の前、話すときに手で身振りはしない（縛られている）。会話カメラはしゃがんで彼と同じ目の高さにする：プレイヤーが立ったままだとカメラが見下ろしすぎるので、肩越しショットの高さは座った彼の目の高さに合わせる〔方法はフロントエンドが決める：プレイヤーが `hostage-column` に近づくと自動で座るかしゃがむ〕。

## Acceptance check / 受け入れ確認

1. In the 60 px silhouette, he in the workshop (wide, apron) separates from the apprentice and フィロストラトス (the "Workshop" panel at the bottom of m3-cast.svg).
   60 px のシルエットで、工房の彼（幅広、前掛け）が弟子やフィロストラトスと区別できる（m3-cast.svg 下部の「工房」）。
2. Put stage 2 (三日目) next to stage 1, and you can tell at a glance that two days have passed; but he does not look injured.
   三日目の第 2 段階を第 1 段階と並べると、二日経ったことが一目で分かる。ただし怪我をしたようには見えない。
3. 「一瞬の疑い」 viewed slowed down is a complete expression; at normal speed it flashes past, and someone beside him can see it.
   「一瞬の疑い」はスローで見ると一つの完全な表情で、通常の速度では一瞬で過ぎ、そばにいる人には見える。
