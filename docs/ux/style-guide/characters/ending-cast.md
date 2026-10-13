# The other characters in the slice ending / スライスのエンディングに登場するその他の人物

The slice plays a simplified ending in the square at sunset on 三日目 (day 3) (S-050). On 2026-10-10 PM set who appears in the ending in the slice configuration (S-077): セリヌンティウス, the king, the guards, the crowd, and the girl in the 緋のマント. This page describes how they must look in the slice, **first at walking-version fidelity** (8k polygons, 2 materials, art-direction 9.2). Which shots are close and need higher fidelity is decided by UX and frontend in `ux/slice/ending-shots.md` in the project folder; once decided, it goes into ux-design.

スライスでは三日目の日没の広場で簡略版のエンディングを演じる（S-050）。PM は 2026-10-10 にスライスの構成でエンディングに登場する人物を決めた（S-077）：セリヌンティウス、王、警吏、群衆、緋のマントの少女。このページはスライスで彼らに必要な姿を書く。**まずは歩行版の精度**（8k ポリゴン、マテリアル 2 個、art-direction 9.2）で作る。どのショットが近く、より高い精度が必要かは、UX とフロントエンドがプロジェクトフォルダの `ux/slice/ending-shots.md` で決め、決まったら ux-design に書く。

In M3, セリヌンティウス and the king become characters you can talk to, and each will then get a full costume table (dialogue version, face, mouth shapes). This page fixes their outline, colors and look in the ending first; M3 builds on top of it without overturning it.

M3 ではセリヌンティウスと王が会話できる人物になり、そのときそれぞれに完全な衣装表（会話版、顔、口の形）を補う。ここではまず輪郭、色、エンディングでの姿を決める。M3 はこれに積み上げ、ひっくり返さない。

For shared rules (size, color table, wear, silhouette acceptance) see the [README](../README.md). Figure: [ending-cast.svg](ending-cast.svg) (front colors, 60 px silhouettes, whether each can be found in the crowd).

共通のルール（サイズ、色表、摩耗、シルエットの受け入れ確認）は [README](../README.md) を参照。図：[ending-cast.svg](ending-cast.svg)（正面の色、60 px シルエット、群衆の中で見つけられるか）。

**One thing we saw once it was drawn**: looking at a dense crowd from behind, in the backlit silhouette **the old man can hardly be found**: his hood looks like the other women's, and his stoop and staff are blocked by the people in front and behind. The traveler (by the hat brim), the guards (by the conical helmets and spears) and the king (by his height and the guards on either side) are all still recognizable. So in the ending the old man must not be buried in the middle of the crowd: he stands **in the front row or at the edge of the crowd** (ux-design 11.1's `in-crowd` already requires the front row), and when the player has chosen 「老爺の家に身を寄せる」 he stands next to the player. When the camera shoots from behind the crowd, he must be at the edge of the crowd in the frame.

**描いてみて分かったこと**：密集した群衆を背後から見ると、逆光のシルエットでは**老爺がほとんど見つからない**：フードはほかの女性と同じに見え、猫背と杖は前後の人に隠れる。旅人は帽子のつば、警吏は円錐形の兜と槍、王は背の高さと両脇の警吏で、どれもまだ見分けられる。だからエンディングで老爺を群衆の真ん中に埋もれさせてはならない：**最前列か群衆の端**に立たせる（ux-design 11.1 の `in-crowd` はもともと最前列を求めている）。プレイヤーが「老爺の家に身を寄せる」を選んだ場合はプレイヤーの隣に立つ。カメラが群衆の背後から撮るとき、彼は画面内で群衆の端にいること。

## Separable at a glance / 一目で区別できる

The ending is played in backlight and twilight, and faces are mostly not readable (art-direction 5.3). Each person is told apart in silhouette by the following:

エンディングは逆光と夕闇の中で演じられ、顔はほとんど読み取れない（art-direction 5.3）。各人物はシルエットで次のものによって区別する：

| Character / 人物 | What identifies them in silhouette / シルエットで見分ける手がかり | Most easily confused with / 最も混同しやすい相手 | How to separate them / 区別の仕方 |
|---|---|---|---|
| Melos (ending version) / メロス（エンディング版） | Almost bare above the waist, running all the way in from the city gate / 上半身がほぼ裸で、城門からずっと走って入ってくる | Bare-shouldered workers in the crowd / 群衆の中の肩をむき出しにした労働者 | No one in the crowd is bare above the waist / 群衆には上半身裸の人を置かない |
| Selinuntius / セリヌンティウス | The man bound to the pillar; once let down, broad shoulders and a short beard / 柱に縛られた人。下ろされた後は肩幅が広く、短い髭 | — | Position is enough / 位置だけで十分 |
| The king / 王 | Tallest, standing bolt upright, robe to the ankles, a thin gold band on the head / 最も背が高く、まっすぐ立ち、外衣は足首まで、頭に細い金の帯 | Old men in long robes in the crowd / 群衆の中の長衣の老人 | The king's robe is the darkest; two guards follow him / 王の外衣が最も暗い色。両脇に警吏が二人つく |
| Guards / 警吏 | Conical helmets, upright spears / 円錐形の兜、立てた槍 | — | No one in the crowd wears a conical cap or holds a long pole / 群衆には円錐形の帽子をかぶる人や長い棒を持つ人を置かない |
| The girl in the 緋のマント / 緋のマントの少女 | Small, head veil, holding a bundle in her arms / 小柄で、頭に薄布をかぶり、腕に何かを抱えている | Women in the crowd / 群衆の中の女性 | She cannot be told apart before she hands over the cloak, and does not need to be: she should step out of the crowd suddenly / マントを差し出す前は区別できないし、区別する必要もない：彼女は群衆の中から突然出てくるべき人物 |
| The old man of the town / 町の老爺 | Stoop, hood, staff (old-man.md) / 猫背、フード、杖（old-man.md） | Old people in the crowd / 群衆の中の老人 | No one in the crowd has "covered head + staff" / 群衆には「頭をかぶる＋杖」の人を置かない |
| Traveler (player) / 旅人（プレイヤー） | Wide-brimmed hat, sea color, scarlet sash (traveler.md) / つば広の帽子、海の色、緋色の腰帯（traveler.md） | — | No wide-brimmed hats in the crowd / 群衆にはつば広の帽子を置かない |

## Selinuntius / セリヌンティウス

> 竹馬の友、セリヌンティウスは、深夜、王城に召された。……セリヌンティウスは、縄打たれた。

Melos's childhood friend, a stonemason in the town, about the same age as Melos (early twenties) [inferred: the original only says 「竹馬の友」]. Three days ago he was summoned to the royal castle late at night as a hostage, has been held ever since, and today is marched to the execution ground.

メロスの竹馬の友で、町で石工をしている。年はメロスとほぼ同じ（二十代前半）〔推定：原作は「竹馬の友」としか言わない〕。三日前の深夜に人質として王城に呼ばれ、それからずっと閉じ込められ、今日刑場に引き出される。

| Item / 項目 | Requirement / 要件 |
|---|---|
| Height, build / 身長・体型 | 1.72 m, 7.25 heads tall. **The widest of all the characters**: broad shoulders, thick arms, a stonemason's body. Side by side with Melos, one is lean and long, the other broad and solid / 1.72 m、7.25 頭身。**全人物の中で最も幅が広い**：肩幅が広く腕が太い、石工の体。メロスと並ぶと、一方は細長く、一方は厚みがある |
| Face / 顔 | Calm; in the original he 「無言で首肯き」. A short, neat dark-brown beard (about 1 cm), **with the moustache parted**, since M3 needs to read his mouth shapes / 落ち着いている。原作では「無言で首肯き」。短く整った濃い茶色の髭（約 1 cm）、**口髭は左右に分ける**。M3 で口の形を読み取る必要がある |
| Hair / 髪 | Dark brown, short, straighter than Melos's / 濃い茶色、短く、メロスよりまっすぐ |
| Skin / 肌 | `#9A6A4C`, a little lighter than Melos: he works in a stone yard in town, not herding sheep / `#9A6A4C`。メロスより少し明るい：羊を飼うのではなく、町の石切り場で働いている |
| Clothes / 衣服 | A stonemason's tunic (exomis), **bare at the left shoulder, the opposite of Melos**, undyed wool W0 washed until grayish, with white stone dust on it. **No leather apron in the ending**: he was called away from the workshop late at night three days ago and the apron stayed there (in M3's workshop scene, the apron hangs on the workshop wall [inferred]) / 石工の短衣（エクソミス）。**メロスとは逆に左肩を出す**。染めていない羊毛 W0 を洗いざらして灰色がかり、白い石の粉がついている。**エンディングでは革の前掛けはない**：三日前の深夜に工房から呼び出され、前掛けは工房に残った（M3 の工房のシーンでは前掛けが工房の壁に掛かっている〔推定〕） |
| How he is bound / 縛られ方 | Hemp rope, **hands tied behind his back**, the rope wound across his chest and around the pillar and hoisted up. Arms not spread: there is only one upright post, not made to look like a cross (art-direction 4.1) / 麻縄で**両手を背中で縛り**、縄は胸と柱に回して上へ吊る。両腕は広げない：柱は縦一本だけで、十字架の形にはしない（art-direction 4.1） |
| Traces of three days / 三日間の痕跡 | Clothes wrinkled and dirty, beard a little longer than usual because he has not shaved, face sallow. No wounds (he was not beaten; the original does not say so) / 衣服は皺くちゃで汚れ、髭を剃っていないので普段より少し長く、顔色は暗い。傷は作らない（殴られてはいない。原作に書かれていない） |
| After being let down / 下ろされた後 | The rope is untied, leaving a red ring on each wrist (dark reddish-brown on the color map, no blood). He stands on the scaffold and he and Melos strike each other, then embrace / 縄がほどかれ、手首に赤い跡が一周残る（色マップ上の濃い赤褐色、血は描かない）。磔台の上でメロスと殴り合い、抱き合う |

## King Dionys / 王ディオニス

> その王の顔は蒼白で、眉間の皺は、刻み込まれたように深かった。

| Item / 項目 | Requirement / 要件 |
|---|---|
| Height, build / 身長・体型 | 1.82 m, **the tallest of all the characters**, 7.5 heads tall. Broad-shouldered but thin, standing bolt upright; his back never bends / 1.82 m、**全人物の中で最も背が高い**、7.5 頭身。肩幅は広いが痩せていて、まっすぐ立ち、背中は決して曲がらない |
| Age / 年齢 | About fifty [inferred]. The original gives no age; set by a man who has been a 「暴君」 for many years and has killed his own kin / 五十歳前後〔推定〕。原作に年齢はなく、長年「暴君」であり、肉親を殺した人物として決めた |
| Face / 顔 | **蒼白** (skin `#B89A86`, the lightest and coolest of all the characters). Two very deep vertical lines between the brows (normal map), deep-set eyes / **蒼白**（肌 `#B89A86`、全人物の中で最も明るく冷たい）。眉間に二本のとても深い縦皺（法線）、目のくぼみが深い |
| Beard and hair / 髭と髪 | A short, neatly trimmed dark-gray beard streaked with white, **with the moustache parted** (M3 needs to read his mouth shapes). Short hair combed back / 白の混じった濃い灰色の短い髭を整え、**口髭は左右に分ける**（M3 で口の形を読み取る必要がある）。髪は短く、後ろへなでつける |
| Clothes / 衣服 | A long chiton to the ankles, dark gray `#4A4744`; over it a **heavy deep-purple robe** (himation, murex purple). Deep purple P1 `#46304A` is the most saturated color other than scarlet, but much darker than scarlet, and must not be read as red (art-direction 5.4) / 足首までの長衣（キトン）、濃い灰色 `#4A4744`。その上に**厚く重い濃紫の外衣**（ヒマティオン、貝紫）。濃紫 P1 `#46304A` は緋色に次いで彩度が高い色だが、緋よりずっと暗く、赤に見えてはならない（art-direction 5.4） |
| Headband / 頭帯 | A thin gold headband (diadem), about 1.5 cm wide. By the time the king appears the sun has set; when the execution ground's torches catch it, it glints, and from a distance he is recognized by this and his height / 細い金の頭帯（ディアデム）、幅約 1.5 cm。王が登場するときにはすでに日が沈んでいて、刑場の松明が当たると一瞬光る。遠くからはこれと背の高さで見分ける |
| Shoes / 靴 | Dark leather shoes covering the top of the foot (not sandals), setting him apart from commoners / 足の甲を覆う濃い色の革靴（サンダルではない）で、庶民と区別する |
| In the ending / エンディングでは | The original: 「群衆の背後から二人の様を、まじまじと見つめていた」, then 「静かに二人に近づき」. So the king first stands **behind the crowd** (on the west side, the city-gate side), not on the royal castle's steps, then walks through the crowd as it parts toward the scaffold [ux-design 11.1's `approaching`]. Two guards follow him / 原作は「群衆の背後から二人の様を、まじまじと見つめていた」、そして「静かに二人に近づき」。だから王はまず**群衆の背後**（西側、城門の側）に立ち、王城の階段の上ではない。それから道を空けた群衆の間を通って磔台へ歩く〔ux-design 11.1 の `approaching`〕。両脇に警吏が二人つく |
| Movement / 動き | Walks slowly and steadily; as he approaches, his hands hang down and he puts on no airs. The original's 「顔をあからめて」: a flushed face cannot be seen at this distance, so it is left to the narration / ゆっくり落ち着いて歩き、近づくときは両手を下ろし、威張らない。原作の「顔をあからめて」：この距離では顔の赤みは見えないので、語りに任せる |

## 城の警吏 (`char.guards`: the patrolling guards and the executioners at the execution ground) / 城の警吏（`char.guards`：巡回する警吏と刑場の刑吏）

The world-model name is 「城の警吏」 (changed on 10-11; the old bracketed 「警吏（巡邏・刑吏）」 would have been shown to the player as is). "Guards" below always means this group.

世界モデル上の名前は「城の警吏」（10-11 に変更。以前の括弧付きの「警吏（巡邏・刑吏）」はそのままプレイヤーに表示されてしまう）。以下で「警吏」と言う場合はすべてこの一団を指す。

| Item / 項目 | Requirement / 要件 |
|---|---|
| How they are made / 作り方 | Share the crowd's low-poly model (art-direction 5.5), plus helmet, spear and cloak / 群衆と同じローポリモデル（art-direction 5.5）を共有し、兜、槍、外套を足す |
| Helmet / 兜 | **A conical helmet** (pilos type), old bronze, matte and dulled. Only the guards wear one among all the characters, so they are recognized at a glance in silhouette / **円錐形の兜**（ピロス型）、古い青銅、つや消しでくすんでいる。全人物の中で警吏だけがかぶり、シルエットで一目で分かる |
| Spear / 槍 | About 2.4 m, wooden shaft, iron head. Held upright, the head higher than everyone's head / 約 2.4 m、木の柄に鉄の穂先。立てて持ち、穂先は誰の頭よりも高い |
| Clothes / 衣服 | A tunic to just above the knee, deep walnut brown N1; over it a short cloak of dark undyed wool. **No red cloak** (the Spartan-style red cloak is the easiest thing to slip in, and it would steal from scarlet) / 膝上までの短衣、濃い胡桃色 N1。その上に染めていない濃い色の羊毛の短い外套。**赤い外套は使わない**（スパルタ風の赤い外套は最も紛れ込みやすく、緋色を食ってしまう） |
| Executioners / 刑吏 | The two or three men pulling ropes at the execution ground: the same outfit, no helmet, no spear, sleeves rolled up / 刑場で縄を引く二、三人：同じ衣装で、兜も槍もなく、袖をまくっている |
| The city-gate scene / 城門の場面 | They are the ones who seize Melos and stop the traveler at the royal castle's gate on the night of act 1 (`ux/slice/act1-end-and-gate.md` in the project folder). At night they carry torches / 第一幕の夜に王城の門でメロスを捕らえ、旅人を止めるのは彼ら（プロジェクトフォルダの `ux/slice/act1-end-and-gate.md`）。夜は松明を持つ |

## The execution-ground crowd / 刑場の群衆

Following art-direction 5.5: 3–4 body types × 3 costumes × small color variations, with animations staggered in time. Additions:

art-direction 5.5 に従う：体型 3〜4 種 × 衣装 3 種 × 色の微調整、動きは時間をずらす。補足：

- **Colors** are chosen only from the color table: undyed linen L0, undyed wool W0, walnut brown N1, faded woad B1, olive G1, old gray-brown A1. **No scarlet and no other red**, and no ochre either (that is Melos's).
  **色**は色表からだけ選ぶ：染めていない亜麻 L0、染めていない羊毛 W0、胡桃色 N1、褪せた大青 B1、オリーブ G1、古い灰褐色 A1。**緋色やその他の赤は使わない**。黄土も使わない（それはメロスの色）。
- **Three costumes**:
  **衣装**は三種：
  1. Men in a long robe plus an outer robe (the most common);
     男性、長衣に外衣（最も多い）。
  2. Women in a long robe, the outer robe pulled up over the head (no staff);
     女性、長衣で、外衣を引き上げて頭にかぶる（杖は持たない）。
  3. Working men in a tunic with a low round felt cap (not conical; conical belongs to the guards). **The tunic covers both shoulders**, no bare right shoulder (that is Melos's).
     労働者の男性、短衣に低い丸いフェルト帽（円錐形ではない。円錐形は警吏のもの）。**短衣は両肩を覆い**、右肩は出さない（それはメロスのもの）。
- **Not placed**: wide-brimmed hats (the traveler's), "covered head + staff" (the old man's), conical caps and long poles (the guards'), people bare above the waist (Melos in the ending).
  **置かないもの**：つば広の帽子（旅人のもの）、「頭をかぶる＋杖」（老爺のもの）、円錐形の帽子と長い棒（警吏のもの）、上半身裸の人（エンディングのメロス）。
- Vary the heads (bald, veils, felt caps): the crowd is seen from behind and backlit, and in silhouette the head and shoulders are what is seen first.
  頭には変化をつける（禿げ頭、薄布、フェルト帽）。群衆はカメラに背を向け、逆光で見られるので、シルエットでまず目に入るのは頭と肩だから。

## The girl in the 緋のマント / 緋のマントの少女

> ひとりの少女が、緋のマントをメロスに捧げた。

| Item / 項目 | Requirement / 要件 |
|---|---|
| How she is made / 作り方 | A variant of the crowd's female costume, small (about 1.50 m) / 群衆の女性衣装の一つのバリエーションで、小柄（約 1.50 m） |
| Age / 年齢 | In her teens [inferred]. The original only says 「少女」 and 「可愛い娘さん」 / 十代〔推定〕。原作は「少女」「可愛い娘さん」としか言わない |
| Clothes / 衣服 | A light-colored long robe L0, a head veil (undyed thin linen, lighter than the old man's hood and letting light through) / 明るい色の長衣 L0、頭の薄布（染めていない薄い亜麻。老爺のフードより軽く、光を通す） |
| Cloak / マント | The 緋のマント (melos.md) is **folded and held in her arms, covered by her own outer robe**, and only unfolded when she hands it over. Until then there is no scarlet in the crowd: scarlet is reserved for three things (art-direction 6), and the cloak must leap out at that moment. Made as two meshes: the folded bundle (held in her arms) and the unfolded cloth (handed over and draped on Melos), swapped at the moment she hands it over (suggestion from frontend PR #18) / 緋のマント（melos.md）は**畳んで腕に抱え、自分の外衣で覆う**。差し出すときにだけ広げる。それまで群衆の中に緋色は見えない：緋色は三つのものにしか使わず（art-direction 6）、マントはその瞬間に飛び出して見えなければならない。メッシュは二つ作る：畳んだ塊（腕に抱える）と広げた一枚（差し出してメロスに掛ける）。差し出す瞬間に切り替える（フロントエンド PR #18 の提案） |
| Movement / 動き | Steps out from the front row, holds the unfolded cloak up in both hands to Melos, then goes back into the crowd / 最前列から歩み出て、広げたマントを両手で捧げてメロスに渡し、群衆の中へ戻る |

## Bones (walking version) / ボーン（歩行版）

- The king and セリヌンティウス: a standard humanoid skeleton plus 2–4 bones for the hem. For the face, only a single jaw bone for now (to open the mouth when shouting or crying) [frontend decides how]; full expression blend shapes wait for M3's dialogue version.
  王とセリヌンティウス：標準的な人型のボーンに裾のボーン 2〜4 本を足す。顔はまず顎のボーン 1 本だけ（大声で話す、泣くときに口を開ける）〔方法はフロントエンドが決める〕。完全な表情のブレンドシェイプは M3 の会話版を待つ。
- The guards' spears and the king's headband are rigid bodies. The girl's cloak must be able to move when unfolded, with at least 4 bones.
  警吏の槍と王の頭帯は剛体。少女のマントは広げたときに動けるよう、ボーンを少なくとも 4 本。
