# Philostratus / フィロストラトス

> 「フィロストラトスでございます。貴方のお友達セリヌンティウス様の弟子でございます。」その若い石工も、メロスの後について走りながら叫んだ。

Selinuntius's apprentice, a young stonemason (`char.philostratus`). **Dialogue version**. Appearances:

セリヌンティウスの弟子で、若い石工（`char.philostratus`）。**会話版**。登場場面：

- Act 1: the workshop (present when the 石屋の弟子 identity starts; he is the apprentice's senior, in `role.apprentice`'s `knownCharacters`).
  第一幕：工房（石屋の弟子で始めたときにその場にいる。彼は弟子の兄弟子で、`role.apprentice` の `knownCharacters` に入っている）。
- Acts 2 and 3: in the town, near the workshop and the execution ground [decided by the world model's plans; not written separately here].
  第二幕・第三幕：町の中、工房と刑場の近く〔世界モデルのプランで決まるので、ここでは別に書かない〕。
- Act 4: on 三日目 (day 3) at 18:30 he runs out of the town and catches up with Melos on the 野の道 (beat.23, homeward-road section 7).
  第四幕：三日目 18:30 に町から走り出て、野の道でメロスに追いつく（beat.23、homeward-road 第 7 節）。

Voice D-025: Rasalgethi (only about one and a half semitones from Melos; whether to switch to Enceladus is in ux-design 16.1, to be decided at the live listening test after D-035).

声は D-025：Rasalgethi（メロスとは約 1 半音半しか違わない。Enceladus に替えるかどうかは ux-design 16.1 を参照し、D-035 以降に人が実際に聴いて決める）。

For shared rules see the [README](../README.md). Figure: [m3-cast.svg](m3-cast.svg).

共通のルールは [README](../README.md) を参照。図：[m3-cast.svg](m3-cast.svg)。

## Three things recognizable at a glance (exploration camera, 60 px) / 一目で分かる三つの特徴（探索カメラ、60 px）

1. **Thin, leaning forward**: even standing, he looks about to run. 1.70 m, a little shorter than Melos and a size thinner.
   **痩せていて、前のめり**：立っていても今にも走り出しそう。1.70 m、メロスより少し低く、一回り細い。
2. **A natural-colored headscarf wrapping his hair**: tucked in at the nape, with no hanging tails, so his head is a smooth round shape (the apprentice's headband hangs two short tails at the back of the head; that is how they are told apart).
   **髪を包む生成りの頭巾**：うなじでたくし込み、垂れる端はなく、頭はなめらかな丸になる（弟子の鉢巻きは頭の後ろに短い端が二本垂れていて、それで区別する）。
3. **White stone dust on a gray-brown tunic**: the front and the hem are patched with white.
   **灰褐色の短衣についた白い石の粉**：胸元と裾が一面白い。

**One thing we saw once it was drawn**: in the workshop, the apprentice (the player, seen from behind) and he are told apart in the 60 px silhouette only by the scarf tails on the head and the mallet at the apprentice's right hip, which is weak; in color, the apprentice has the scarlet sash and a dark leather apron, so they separate. Once frontend has built the workshop, check it on a real device; if it is still not enough, have him carry a block of stone or a crowbar on his shoulder while working in the workshop [UX's fallback].

**描いてみて分かったこと**：工房では、弟子（プレイヤー、後ろ姿）と彼は 60 px のシルエット上、頭の布の端と弟子の右腰の木槌でしか区別できず、弱い。色では弟子に緋色の腰帯と濃い色の革の前掛けがあるので区別できる。フロントエンドが工房を作ったら実機で確認する。それでも足りなければ、工房で働くときに石材かかなてこを肩に担がせる〔UX の代替案〕。

## Body and face / 体と顔

| Item / 項目 | Requirement / 要件 |
|---|---|
| Age / 年齢 | Eighteen or nineteen [inferred: the original says 「若い石工」] / 十八、九〔推定：原作「若い石工」〕 |
| Height, build / 身長・体型 | 1.70 m, 7.25 heads tall. Thin, long hands, a stonemason's hands (large, thick knuckles) / 1.70 m、7.25 頭身。痩せていて手が長く、石工の手（大きく、指の関節が太い） |
| Posture / 姿勢 | **Weight forward**, shoulders forward, neck stretched out a little. When he comes running in act 4 his upper body leans even further forward and he is panting / **重心が前**で、肩が前に出て、首が少し突き出ている。第四幕で走ってくるときは上半身がさらに前に傾き、息を切らしている |
| Skin / 肌 | `#9C6E50`; he works in the town, so lighter than Melos / `#9C6E50`。町で働いているので、メロスより明るい |
| Face / 顔 | A narrow face, large eyes, eyebrows slanting up (easily flustered). **His main expressions are panic and crying**: in the original he 「叫んだ」, 「おうらみ申します」, and then urges Melos to save his own life. Make a mouth shape for talking while crying (corners of the mouth down, upper lip trembling); no tear effects; wet eyes come from stronger eye highlights / 細い顔で、目が大きく、眉は上がり気味（慌てやすい）。**表情の主役は動揺と泣き**：原作で彼は「叫んだ」「おうらみ申します」、それからメロスに命を守るよう勧める。泣きながら話す口の形（口角が下がり、上唇が震える）を作る。涙のエフェクトは作らず、目の潤みは目のハイライトを強めて表す |
| Facial hair / 髭 | None; at most a very faint layer of stubble. The mouth is clearly visible / なし。あってもごく薄い無精髭が一層。口がはっきり見える |
| Hair / 髪 | Wrapped in the headscarf; a little dark-brown hair shows at the forehead / 頭巾に包まれ、額に濃い茶色の髪が少しのぞく |

## Costume / 衣装

| # | Part / 部位 | Material and color / 素材と色 | How it is made / 作り方 | Approx. share of the 1024 map / 1024 マップ上の面積の目安 |
|---|---|---|---|---|
| ① | Tunic / 短衣 | **Gray-brown linen T1 `#85796A`** / **灰褐色の亜麻 T1 `#85796A`** | To just above the knee, covering both shoulders, short sleeves. The front and hem carry a patch of white stone dust (the same white as Selinuntius's, a layer on the color map) / 膝上まで、両肩を覆い、半袖。胸元と裾に白い石の粉が一面についている（セリヌンティウスと同じ白で、色マップの一層） | 40% |
| ② | Headscarf / 頭巾 | Undyed linen L0 / 染めていない亜麻 L0 | Wraps the hair, tucked in at the nape, no hanging tails / 髪を包み、うなじでたくし込み、垂らさない | 10% |
| ③ | Belt / 帯 | A cloth band, walnut brown N1 / 胡桃色 N1 の布帯 | Once around, knotted at the side / 一巡りさせ、脇で結ぶ | 4% |
| ④ | Sandals / サンダル | Old leather K1 / 古い革 K1 | Flat-soled / 平底 | 8% |

- **No leather apron**: in the workshop only the master and the apprentice (the player) have aprons. He does the hauling and helping-out work [inferred]. This way he and the apprentice separate in both silhouette and color.
  **革の前掛けはない**：工房で前掛けをしているのは親方と弟子（プレイヤー）だけ。彼は運搬や手伝いの仕事をしている〔推定〕。これで彼と弟子はシルエットでも色でも区別できる。
- When he comes running in act 4 (三日目 18:30): he has run all the way from the town, covered in dust and soaked with sweat (material parameters), his headscarf a little askew.
  第四幕で走ってくるとき（三日目 18:30）：町からずっと走ってきたので全身埃まみれで汗に濡れ（マテリアルのパラメータ）、頭巾が少しずれている。

## Dialogue version / 会話版

- The dialogue version per art-direction 9.2.
  art-direction 9.2 の会話版。
- In act 4 he talks while running along behind Melos (「メロスの後について走りながら叫んだ」). The two lines the player can exchange with him on the 野の道 (homeward-road section 7) follow the rules for stopping points: while the player is speaking, he and Melos slow down to a brisk walk, with the camera per ux-design 6.3. When talking while running, mouth shapes and panting mix: frontend makes the panting a blend shape layered on top of the mouth shapes [frontend decides how].
  第四幕では彼はメロスの後について走りながら話す（「メロスの後について走りながら叫んだ」）。野の道で彼と交わせる二言（homeward-road 第 7 節）は停留点のルールに従う：プレイヤーが話している間、彼とメロスは早歩きに速度を落とし、カメラは ux-design 6.3 に従う。走りながら話す口の形と息切れが混ざる：フロントエンドは息切れを口の形の上に重ねるブレンドシェイプとして作る〔方法はフロントエンドが決める〕。

## Moving parts / 動く部分

- 2 bones for the tunic hem. The headscarf does not move.
  短衣の裾にボーン 2 本。頭巾は動かさない。

## Acceptance check / 受け入れ確認

1. In the 60 px silhouette, in the workshop he separates from the apprentice and Selinuntius (the "Workshop" panel at the bottom of m3-cast.svg); on the 野の道 in the backlight of the setting sun he separates from Melos (who is in his ending version by then, almost bare above the waist).
   60 px のシルエットで、工房では弟子やセリヌンティウスと区別でき（m3-cast.svg 下部の「工房」）、野の道の夕日の逆光ではメロスと区別できる（メロスはこのときエンディング版で、上半身がほぼ裸）。
2. When he talks while crying, the mouth shape reads and does not look like laughing.
   泣きながら話すとき、口の形が読み取れ、笑っているようには見えない。
