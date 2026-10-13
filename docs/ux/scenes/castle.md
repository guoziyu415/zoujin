# Castle (throne room and courtyard): plan, furnishings, staging, light, materials v1.1 / 王城（玉座の間と中庭）：平面、調度、演出、光、素材 v1.1

| Item / 項目 | Content / 内容 |
|---|---|
| Purpose / 用途 | For the second frontend thread to follow when building the castle (D-026: design first). The slice has no castle (`ux/slice/act1-end-and-gate.md`: the slice stops at the castle gate); this is for the full version / 2 つ目のフロントエンドスレッドが王城を作るときに、これに沿って組む（D-026 でまず設計）。スライスには王城がない（`ux/slice/act1-end-and-gate.md`：スライスは王城の門で止まる）。これは完全版用 |
| Basis / 根拠 | Data's world model 1.0.0-draft: `scene.castle-throne`, `place.castle`, beat.04〜07, beat.s2 (三日目 16:00 セリヌンティウス「ちらと友を疑う」), `aff.vouch`, `aff.stay-by-master`; ux-design 4.4 end-of-act destinations (「城に残り、セリヌンティウスのそばにいる」, `exit.1.vigil` in the world model), 5.1 (how the traveler gets into the throne room; the apprentice can enter when following their master); art-direction v1.4 (3.4, 4.1, 4.2 throne room, 5.3, 6); paragraphs 9〜26 of the original / データの世界モデル 1.0.0-draft の `scene.castle-throne`、`place.castle`、beat.04〜07、beat.s2（三日目 16:00 セリヌンティウス「ちらと友を疑う」）、`aff.vouch`、`aff.stay-by-master`。ux-design 4.4 の幕末の行き先（「城に残り、セリヌンティウスのそばにいる」、世界モデルの `exit.1.vigil`）、5.1（旅人がどうやって玉座の間に入るか、師匠に付き従う弟子は入れる）。art-direction v1.4（3.4、4.1、4.2 玉座の間、5.3、6）。原作の第 9〜26 段落 |
| Plan / 平面図 | [castle/plan.svg](castle/plan.svg) |
| Status / 状態 | v1.1 (2026-10-11): added furnishings and dimensions (3.1), staging and camera (3.2), and the checklist for Frontend 4 (section 8); F-14 builds from this. v1.0.2 (2026-10-10). Frontend and Data reviewed v0.1, and their answers have been folded into each section (the last section records what was agreed). v1.0.1 added daytime in the throne room (PM chose A, #52) / v1.1（2026-10-11）：調度と寸法（3.1）、演出とカメラ（3.2）、フロントエンド 4 向けのリスト（8 節）を追加。F-14 はこれに沿って作る。v1.0.2（2026-10-10）。フロントエンドとデータが v0.1 を確認し、回答は各節に反映済み（最後の節が決定事項）。v1.0.1 で玉座の間の昼を追加（PM が A に決定、#52） |

The castle maid and guard identities belong to the second release (`release: 2` on `role.castle-maid` and `role.guard`); in the first release the castle is nobody's first screen.

王城の侍女と警吏の 2 つの身分は第 2 版（`role.castle-maid`、`role.guard` の `release: 2`）。第 1 版では、王城は誰の最初の画面でもない。

---

## 0. What plays out here / ここで演じること

| Scheduled time / 予定時刻 | Beat / ビート | Where / 場所 | Original / 原作 |
|---|---|---|---|
| 約束の日 20:00 | beat.04: Melos walks up to the castle gate, is seized by the patrolling guards, and a dagger is found on him / beat.04 メロスが王城の門まで来て、巡邏の警吏に捕まり、懐から短剣が見つかる | **In front of the castle gate on the plaza side** (`place.execution-ground`, the plaza scene; the slice's `piece.gate-taken` plays there). This scene starts as he is marched into the gate passage / **広場側の王城の門前**（`place.execution-ground`、広場のシーン。スライスの `piece.gate-taken` はそこで演じる）。このシーンは彼が城門の通路へ連れ込まれるところから始まる | 「のそのそ王城にはいって行った。たちまち彼は、巡邏の警吏に捕縛された。」 |
| 20:30 | beat.05: questioning by the king, the pact / beat.05 王との問答、約束 | Throne room / 玉座の間 | 「その王の顔は蒼白で、眉間の皺は、刻み込まれたように深かった。」 |
| 23:30 | beat.06: セリヌンティウス is summoned in the middle of the night, the two embrace, and he is bound / beat.06 セリヌンティウスが深夜に呼び出され、二人は抱き合い、彼は縛られる | Throne room / 玉座の間 | 「暴君ディオニスの面前で、佳き友と佳き友は、二年ぶりで相逢うた。」 |
| 23:45 | beat.07: Melos sets off at once / beat.07 メロスはすぐに出発する | Courtyard → gate / 中庭 → 城門 | 「初夏、満天の星である。」 |
| 一日目〜三日目 | The hostage is tied up in the castle; those who stay by him keep him company (`aff.stay-by-master`) / 人質は王城に縛られている。そばに残る人が付き添う（`aff.stay-by-master`） | North colonnade of the courtyard / 中庭の北の柱廊 | — |
| 三日目 16:00 | beat.s2: for the first time in his life, セリヌンティウス doubts his friend for a flash / beat.s2 セリヌンティウスは生まれて初めて、一瞬だけ友を疑う | North colonnade of the courtyard / 中庭の北の柱廊 | He says it himself at the execution ground (「生れて、はじめて君を疑った」) / 刑場で彼自身が口にする（「生れて、はじめて君を疑った」） |

Of the end-of-act-1 destinations, the only one in the world model that leads to the castle is 「城に残り、セリヌンティウスのそばにいる」 (the hostage night, `exit.1.vigil`). The earlier sketch in ux-design 4.4 also had 「王城にとどまる」 (the king remembers you and you stay on as a guest of the castle); **it is not in the first release** (it isn't in the world model; PM decided on 10-10 at 16:05Z: there are enough destinations, and one destination doesn't justify baking an extra daytime lighting set). So the castle has to carry **the night of act 1** (throne room, courtyard) and **the courtyard during the hostage's three days**.

第一幕の幕末に王城へ向かう行き先は、世界モデルでは「城に残り、セリヌンティウスのそばにいる」（人質の夜、`exit.1.vigil`）だけ。ux-design 4.4 の以前の略図には「王城にとどまる」（王があなたを覚えていて、王城の客として残る）もあったが、**第 1 版では作らない**（世界モデルにない。PM が 10-10 16:05Z に決定：行き先は十分多く、1 つの行き先のために昼の光をもう 1 セットベイクする価値はない）。したがって王城が支えるのは、**第一幕の夜**（玉座の間、中庭）と**人質の 3 日間の中庭**。

Players guarding the hostage (including the apprentice who stays with their master) can walk into the throne room during the day on 一日目〜三日目 (act 2 ends at 一日目 10:00, Data #57); the king is at `king-throne` and can be talked to (pointed out by Data in #52). The first release doesn't bake a separate daytime throne room: **by day too the curtain is drawn, the high windows are shut and the lamps are lit, using the night lighting set**; only the main door lets in the courtyard's daylight (PM chose A; section 3, 5.1).

人質を見守るプレイヤー（師匠に付き従う弟子を含む）は、一日目〜三日目の昼も玉座の間に入れる（第二幕は一日目 10:00 に終わる、データ #57）。王は `king-throne` にいて、話しかけられる（データが #52 で指摘）。第 1 版では玉座の間の昼を別にベイクしない：**昼も垂れ幕を引き、高窓を閉め、灯をともして、夜の光のセットを使う**。大扉から中庭の昼の光が差し込むだけ（PM が A に決定、3 節、5.1）。

## 1. Orientation and overall layout / 方角と全体

- The castle stands on high ground east of the plaza (art-direction 4.1), with its gate facing west toward the plaza steps. Coordinates: +x points east (deeper into the castle), compass 90°, +y points north.
  王城は広場の東の高台にあり（art-direction 4.1）、城門は西を向いて広場の階段に面している。座標は +x が東（城の奥へ向かう方向）、方位 90°、+y が北。
- From west to east: **gate passage → courtyard (colonnades on four sides) → throne room**; the throne is at the far east end, facing west, straight toward the door. The tower stands behind the northeast corner of the throne room (the one whose top keeps the last ray of light seen from the plaza), and is visible when you look up from the courtyard.
  西から東へ：**城門の通路 → 中庭（四方に柱廊）→ 玉座の間**。王座は一番東の端にあり、西を向いて扉の真正面にある。塔は玉座の間の北東の角の後ろにあり（広場で最後のひと筋の光が頂に残るあの塔）、中庭から見上げると見える。
- The gate and steps on the plaza side belong to the plaza scene (the slice's guards `piece.gate-taken` and `piece.gate-promise` are there). Melos is seized there (world model 1.7 puts beat.04 at `place.execution-ground`) and then marched in. A `go` through the plaza's castle gate lands you in this scene's gate passage.
  広場側の城門と階段は広場のシーンに属する（スライスの警吏 `piece.gate-taken`、`piece.gate-promise` はそこにいる）。メロスはそこで捕まり（世界モデル 1.7 では beat.04 は `place.execution-ground`）、それから連れて来られる。広場の城門から `go` で入ると、このシーンの城門の通路に着地する。

```
 West (plaza)                                                                                          East
 Gate passage ═ Courtyard [north colonnade: hostage tied to a column] ═ Porch ═ Throne room [two rows of columns · throne on the steps · curtain]  Tower
                         [south colonnade]

 西（広場）                                                        東
 城門の通路 ═ 中庭［北の柱廊：人質が柱に縛られている］═ 門廊 ═ 玉座の間［2 列の柱 · 段の上の王座 · 垂れ幕］ 塔
                  ［南の柱廊］
```

## 2. Plan (+x = 90°, due east) / 平面（+x = 90°、真東）

| Thing / もの | Position (x, y) / 位置（x, y） | Notes / 説明 |
|---|---|---|
| Gate passage / 城門の通路 | x −30〜−24, y −2〜2, 5 m high / x −30〜−24、y −2〜2、高さ 5 m | A doorway under a stone lintel, with guards standing on both sides. One brazier at night / 石のまぐさの門口で、両側に警吏が立つ。夜は火鉢が 1 つ |
| Courtyard / 中庭 | x −24〜−6, y −10〜10; open-air part x −20〜−10, y −6〜6 / x −24〜−6、y −10〜10。露天の部分は x −20〜−10、y −6〜6 | Limestone flagstone floor, with a cistern wellhead in the center (−15, 0). Colonnades on four sides, 4 m deep. Columns on the north and south sides at x = −20, −17.5, −15, −12.5, −10; on the east and west sides at y = ±2, ±4, ±6; the middle bay facing the gate and the main door is 4 m wide / 石灰岩の敷石の床で、中央に貯水槽の井桁 (−15, 0)。四方に柱廊があり、奥行き 4 m。南北の柱は x = −20、−17.5、−15、−12.5、−10、東西の柱は y = ±2、±4、±6。城門と大扉に正対する中央の柱間は幅 4 m |
| North colonnade / 北の柱廊 | y 6〜10, two rows of columns (y = 6 and y = 8) / y 6〜10、柱は 2 列（y = 6 と y = 8） | **The hostage is tied to one of the second-row columns** (section 4 `hostage-column`). At noon the sun is about 72° high and reaches only 1.5 m in past the front row; the second row is always in shadow / **人質は 2 列目の柱の 1 本に縛られる**（4 節 `hostage-column`）。正午の太陽高度は約 72° で、日が届くのは前列の柱から奥へ 1.5 m まで。2 列目はずっと日陰 |
| South colonnade / 南の柱廊 | y −10〜−6 | Two braziers at night / 夜は火鉢が 2 つ |
| Porch and main door / 門廊と大扉 | x −6, door 4 m wide (y −2〜2) / x −6、扉の幅 4 m（y −2〜2） | A two-column porch leading into the throne room / 2 本柱の門廊で、玉座の間へ入る |
| **Throne room / 玉座の間** | x −6〜16, y −7〜7, 8 m high / x −6〜16、y −7〜7、高さ 8 m | Two rows of 4 columns each (x = −2, 3, 8, 13, y = ±4). A row of narrow windows high on the north and south walls (high windows), plus one on the east wall above the curtain; stars show through them at night / 柱は 2 列に 4 本ずつ（x = −2、3、8、13、y = ±4）。南北の壁の高い位置に細い窓が並び（高窓）、東の壁の垂れ幕の上にも 1 つある。夜は星が見える |
| Steps and throne / 段と王座 | Three steps x 10〜12, 0.9 m high; throne (13.5, 0), facing west / 3 段 x 10〜12、高さ 0.9 m。王座 (13.5, 0)、西向き | A heavy curtain hangs behind the throne / 王座の後ろに厚い垂れ幕が下がる |
| Hanging lamp / 吊りランプ | (11, 0), 4.5 m above the floor / (11, 0)、床から 4.5 m | A bronze fitting with many oil lamps, hung above and in front of the throne: **the king's light comes from above** (art-direction 4.2) / 青銅の多灯式の油ランプで、王座の前上方に吊るす：**王の光は上から来る**（art-direction 4.2） |
| Braziers / 火鉢 | (9, ±2.5) | Two at the foot of the steps, to give the king's eyes a little catchlight / 段の足もとに 2 つ。王の目に少し映り込みの光を入れる |
| Tower / 塔 | Behind the throne room's northeast corner (16〜22, 8〜14), about 30 m high / 玉座の間の北東の角の後ろ (16〜22, 8〜14)、高さ約 30 m | Seen over the roof when looking northeast from the courtyard / 中庭から北東を見ると屋根越しに見える |

## 3. Throne room (interior) / 玉座の間（屋内）

- The floor is polished dark stone, with long reflections of the lamplight on it. Columns and walls are plastered limestone, with a dark band (ochre-black) around the base of the walls, **no red** (art-direction 6).
  床は磨いた暗色の石で、灯の長い映り込みがある。柱と壁は漆喰を塗った石灰岩で、壁の足もとに暗い帯（赭黒）が一周する。**赤は使わない**（art-direction 6）。
- Curtain: heavy wool, deep indigo or deep purple, on the cool side; it must not read as red under the lamplight.
  垂れ幕：厚い羊毛で、深い藍色か深い紫、寒色寄り。灯の下で赤に見えてはいけない。
- The king's light: the hanging lamp is above and in front of him, his eye sockets fall into shadow, and the furrow between his brows looks deeper (「蒼白」「刻み込まれたように深かった」); during dialogue the braziers below the steps give his eyes a little catchlight, otherwise his expression can't be read (art-direction 4.2).
  王の光：吊りランプは彼の前上方にあり、眼窩は影に落ち、眉間の皺はいっそう深く見える（「蒼白」「刻み込まれたように深かった」）。会話中は段の下の火鉢が目に少し映り込みを与える。そうしないと表情が読めない（art-direction 4.2）。
- **The dialogue camera is a low-angle shot**: the king sits on a 0.9 m dais, the player stands below it, and the over-the-shoulder shot looks up at him from behind your shoulder. That is exactly the relationship this scene wants.
  **会話のカメラはあおり**：王は高さ 0.9 m の台に座り、プレイヤーは台の下に立ち、肩越しのショットがあなたの肩の後ろから彼を見上げる。これこそこの場面に必要な関係。
- Camera: the room is 22 × 14 m and 8 m high; its width can't fit the follow camera 9 m behind the player, so indoors uses the indoor mode (5.5 m behind, 2.6 m high, 3.2). ux-design 7.x calls this "a tight place like the throne room": many people, not far to walk.
  カメラ：部屋は 22 × 14 m、高さ 8 m で、幅が足りず背後 9 m の追従カメラが収まらないため、屋内では室内モードを使う（背後 5.5 m、高さ 2.6 m、3.2）。ux-design 7.x の言う「玉座の間のような狭い場所」：人が多く、遠くまで歩けない。
- **Daytime (first release)**: only lamplight, same as at night. The tyrant trusts no one and keeps the curtain closed; the high windows have wooden shutters, closed by day against the heat and opened at night for the cool (that is simply how Sicilian summers are lived), so the stars are still visible at night. Walking in from the bright courtyard, it suddenly goes dark:
  **昼（第 1 版）**：夜と同じく灯だけ。暴君は誰も信じず、垂れ幕は開けない。高窓には板戸があり、昼は暑さを避けて閉め、夜は涼をとるために開ける（シチリアの夏はもともとそう過ごす）ので、夜は相変わらず星が見える。明るい中庭から入ると、急に暗くなる：
  - **The interior ignores the sun and sky** (Frontend #52): the throne room uses fully baked lighting (lamps, braziers), its materials are marked as interior and are unaffected by the sun and real-time shadows, and ambient light comes from the room's own probes. So the interior doesn't follow the clock in the first place; day and night are the same set.
    **屋内は太陽と空を受けない**（フロントエンド #52）：玉座の間は完全にベイクした光（灯、火鉢）を使い、素材は屋内として扱い、太陽とリアルタイムの影の影響を受けない。環境光は部屋独自のプローブを使う。だから屋内はもともと時計に従わず、昼も夜も同じセット。
  - **Exposure**: under daytime exposure, a hall lit only by lamps is almost black, and the king's face and the firelight in his eyes can't be read. When crossing the threshold the hall switches to its own exposure and recovers in about 1 second (first a sudden darkness, then the eyes adjust and you see what you'd see at night); leaving reverses it. At night, walking from the dark courtyard into the lit hall is the same step. The main door behind stays a whitish bright; the grade adds no night blue (`uNight` follows the clock and is 0 by day).
    **露出**：昼の露出のままだと灯だけの広間はほぼ真っ暗で、王の顔も目の中の火の光も読めない。敷居をまたぐと広間専用の露出に切り替わり、約 1 秒で戻る（まず急に暗くなり、目が慣れると夜と同じように見える）。外へ出るときは逆。夜に暗い中庭から灯のともる広間へ入るときも同じ手順。背後の大扉は白っぽく明るいまま残し、色調整で夜の青を加えない（`uNight` は時計に従い、昼は 0）。
  - **High windows**: closed wooden shutters (geometry, really closed, otherwise the openings would show the daytime sky), with a few thin lines of light through the gaps, made as thin emissive strips, not baked. They open and close with the sun: open after sunset, close before sunrise (suggested by Frontend #57). Don't snap them over while the player is in the hall: switch when the camera can't see the high windows, or have them swing open slowly.
    **高窓**：閉じた板戸（ジオメトリで本当に閉める。そうしないと窓から昼の空が見えてしまう）。板の隙間から細い光の線が何本か差し込み、発光する細い帯で作り、ベイクしない。開閉は太陽に合わせる：日没後に開け、日の出前に閉める（フロントエンド #57 の提案）。プレイヤーがちょうど広間にいるときに一瞬で切り替えない：カメラから高窓が見えないときに切り替えるか、ゆっくり押し開けるようにする。
  - **Main door**: outside the door is the courtyard's daylight (grey when it rains, with no light inside the door). The patch of light on the floor inside the door is a soft-edged light-patch texture (Frontend #52, about 50〜100 KB, not separately baked), **with its shape computed from the real-time sun**: take the sunlit part of the doorway and project it onto the floor along the sun's direction, recomputing the four corners at every clock update; brightness and color follow the sun. The sunlit part of the doorway is bounded below by the shadow of the courtyard's west wall (8 m high) and above by the eaves of the colonnade in front of the door:
    **大扉**：扉の外は中庭の昼（雨の日は灰色で、扉の内側に光はない）。扉の内側の床の光は、縁の柔らかい光だまりのテクスチャで作る（フロントエンド #52、約 50〜100 KB、別にベイクしない）。**形はリアルタイムの太陽から計算する**：門口のうち日が当たる部分を、太陽の方向に沿って床に投影し、時計が更新されるたびに四隅を計算し直す。明るさと色は太陽に従う。門口の日が当たる部分の下端は中庭の西の壁（高さ 8 m）の影、上端は扉の前の柱廊の軒：
    - Around 14:30 light starts at the foot of the door. After that it's a patch growing inward from the threshold: about 1.5 m at 15:00, about 4.5 m at 16:00, about 8 m at 16:45;
      14:30 ごろ扉の足もとに光が差し始める。その後は敷居から奥へ伸びる光：15:00 に約 1.5 m、16:00 に約 4.5 m、16:45 に約 8 m。
    - Around 16:55 the west wall's shadow reaches the foot of the door (the wall-shadow clock in 5.1); the light leaves the threshold and becomes a band moving inward and getting thinner, slanting south: about 3.5〜12 m inside the door at 17:15, about 7.5〜15 m at 17:30, reaching the south half of the steps around 17:45;
      16:55 ごろ西の壁の影が扉の足もとに達し（5.1 の壁の影の時計）、光は敷居を離れて、奥へ進みながら細くなっていく光の帯になり、南へ斜めにずれる：17:15 に扉の内側約 3.5〜12 m、17:30 に約 7.5〜15 m、17:45 前後に段の南半分に届く。
    - Around 18:05 the wall shadow covers the top of the door and the light goes out.
      18:05 ごろ壁の影が扉の上端を覆い、光は消える。
    - Players guarding the hostage are mostly in the courtyard's north colonnade; when they walk into the throne room in the afternoon to see the king, they can watch this band travel toward the throne and then go out: a clock inside the room, driven by the same sun as the wall shadow in the courtyard. On 一日目 and 二日目 the king stays on the dais; on 三日目 the king is taken to the execution ground at beat.s1 (18:00, at the earliest 17:00), so by the time the band reaches the steps the throne is most likely empty. The stretches where the south row of columns blocks the band can be skipped in the first release.
      人質を見守るプレイヤーはたいてい中庭の北の柱廊にいる。午後に玉座の間へ入って王に会うと、この光の帯が王座のほうへ進み、やがて消えるのが見える：屋内の時計であり、中庭の壁の影と同じ太陽。一日目と二日目、王はずっと台の上にいる。三日目、王は beat.s1 で刑場へ連れて行かれる（18:00、早ければ 17:00）ので、光の帯が段に届くころには王座はたいてい空になっている。南の列の柱が光の帯を遮る部分は、第 1 版では作らなくてよい。
    - 〔Estimate: door height taken as 5 m, colonnade eaves as 6 m, west wall 8 m, sun from the formula in art-direction 3.1. Frontend computes with the real heights in the model〕
      〔推算。扉の高さを 5 m、柱廊の軒を 6 m、西の壁を 8 m とし、太陽は art-direction 3.1 の式による。フロントエンドはモデルの実際の高さで計算する〕
- When a real daytime is built later (the second release's maid and guard identities, or if 「王城にとどまる」 is added later): open the high windows and the curtain, with shafts of light from the high windows and dust floating in them. In the morning the sun comes in through the high windows on the east, behind the throne: the king is backlit.
  のちに本当の昼を作るとき（第 2 版の侍女・警吏の身分、またはのちに「王城にとどまる」を加える場合）：高窓と垂れ幕を開け、高窓から光の柱が差し込み、空気中の塵がその中に浮かぶ。午前は太陽が東の高窓から入り、王座の後ろにある：王は逆光になる。

### 3.1 Furnishings and dimensions / 調度と寸法

Build the model from this table (positions on the plan don't change). Heights are measured from the throne room floor.

この表に沿ってモデルを作る（平面図上の位置は変わらない）。高さは玉座の間の床から測る。

| Thing / もの | Size, position / 寸法、位置 | Look / 見た目 |
|---|---|---|
| Floor / 床 | x −6〜16, y −7〜7 / x −6〜16、y −7〜7 | Polished dark stone slabs, each about 1.2 × 1.2 m, with very fine joints. Along the central axis from the main door to the foot of the steps runs a 2 m wide strip of stone one shade lighter (x −6〜10, y −1〜1), leading the eye to the throne / 磨いた暗色の石板で、1 枚約 1.2 × 1.2 m、目地はごく細い。中心軸に沿って大扉から段の足もとまで、幅 2 m で一段明るい色の石の帯（x −6〜10、y −1〜1）を通し、視線を王座へ導く |
| Columns / 柱 | 8 of them, 0.8 m in diameter, at (−2, 3, 8, 13, ±4); shaft to cornice 6.5 m / 8 本、直径 0.8 m、(−2、3、8、13、±4)、柱身から軒まで 6.5 m | Doric, with 20 shallow flutes on the shaft (normal map, no geometry), simple capitals. Above them a stone cornice, and above that a ceiling of dark wooden beams (8 m) with plaster between them. The ceiling gets almost no light and is dark, which is correct / ドーリア式で、柱身に浅い溝 20 本（法線マップで、ジオメトリは作らない）、柱頭は簡素。上に石の軒が一周し、その上は暗い木の梁の天井（8 m）で、梁の間は漆喰。天井にはほとんど光が当たらず暗いが、それで正しい |
| Walls / 壁 | 8 m high / 高さ 8 m | Plastered limestone, **with a 1.2 m ochre-black band around the base**. No murals (the tyrant's hall is cold) / 漆喰を塗った石灰岩で、**足もとに高さ 1.2 m の赭黒の帯が一周する**。壁画は描かない（暴君の広間は冷たい） |
| Steps / 段 | Three steps, x 10〜12, y −3.4〜3.4; each 0.3 m high with a tread of about 0.67 m / 3 段、x 10〜12、y −3.4〜3.4。1 段の高さ 0.3 m、踏み面約 0.67 m | The same dark stone as the floor; each step edge has a slightly lighter stone line so the edges read clearly under the lamps / 床と同じ暗色の石。各段の縁に少し明るい石の線を入れ、灯の下で段の縁がはっきり見えるようにする |
| Dais / 台 | x 12〜16, y −3.4〜3.4, 0.9 m high / x 12〜16、y −3.4〜3.4、高さ 0.9 m | Same as above / 同上 |
| Throne / 王座 | (13.5, 0), facing west. Overall 1.6 m wide (including arms), 1.3 m deep; seat 0.45 m above the dais, top of the back 1.9 m above the dais / (13.5, 0)、西向き。全体の幅 1.6 m（肘掛けを含む）、奥行き 1.3 m。座面は台から 0.45 m、背もたれの頂は台から 1.9 m | Dark carved wood (olive-wood color), with the arm ends and the top of the back sheathed in dulled bronze (palmette pattern). A deep indigo wool cushion on the seat (the same cloth as the curtain), and a low footstool. **When the king sits, his head is in front of the back and in front of the curtain**: the background to his face is dark / 暗色の彫刻を施した木（オリーブ材の色）で、肘掛けの先と背もたれの頂はくすんだ青銅で覆う（パルメット文様）。座には深い藍色の羊毛のクッション（垂れ幕と同じ布）、足もとに低い足台。**王が座ると、頭は背もたれの前、垂れ幕の前にある**：顔の背景は暗い |
| Curtain / 垂れ幕 | x 15.6, y −3.2〜3.2, hanging from 6.4 m down to the dais, with the hem pooling a little on the dais / x 15.6、y −3.2〜3.2、6.4 m から台まで垂れ、裾は台の上に少したまる | Heavy **deep indigo** wool (about `#2B3550`), with folds roughly every 0.35 m. Set to indigo, not deep purple: the king's outer robe is deep purple P1, and the two must not blur together (style guide [king.md](../style-guide/characters/king.md), "Seated pose and the throne room") / **深い藍色**の厚い羊毛（約 `#2B3550`）で、ひだは約 0.35 m ごと。深い紫ではなく藍色に決めた：王の上衣が深い紫 P1 なので、両者が一体に溶けてはいけない（スタイルガイド [king.md](../style-guide/characters/king.md)「座り姿勢と玉座の間」） |
| High windows / 高窓 | 5 on each of the north and south walls, at x −3, 1, 5, 9, 13; 1.6 m wide, 1.2 m high, sill at 6.3 m. One on the east wall above the curtain, 1.6 m wide, 0.8 m high, sill at 6.8 m / 南北の壁に各 5 つ、x −3、1、5、9、13。幅 1.6 m、高さ 1.2 m、窓台 6.3 m。東の壁の垂れ幕の上に 1 つ、幅 1.6 m、高さ 0.8 m、窓台 6.8 m | Two inward-opening wooden shutters. When closed, a few thin lines of light come through the gaps (section 3); when open, stars are visible / 内開きの 2 枚の板戸。閉じているときは隙間から細い光の線が何本か入り（3 節）、開いているときは星が見える |
| Hanging lamp / 吊りランプ | (11, 0), lower edge 4.5 m above the floor / (11, 0)、下端は床から 4.5 m | A bronze ring 1.4 m across with 8 oil lamps, hung from the beams by three chains. The king's face is 2.5 m behind and below it: the light comes from the front and above / 直径 1.4 m の青銅の輪に油ランプ 8 つ、3 本の鎖で梁から吊るす。王の顔はその下の 2.5 m 後ろ：光は前上方から来る |
| Braziers / 火鉢 | (9, ±2.5) | Bronze tripods, bowl 0.6 m across, rim 1.0 m above the floor, flames about 0.4 m high / 青銅の三脚で、鉢の径 0.6 m、鉢の縁は床から 1.0 m、炎の高さ約 0.4 m |
| Wall lamps / 壁掛けランプ | 2 on each of the north and south walls, at x −4 and 0.5, 2.4 m above the floor / 南北の壁に各 2 つ、x −4、0.5、床から 2.4 m | Oil lamps on iron brackets, very dim. They keep the west half from going dead black: coming in from the main door, you first see the nearby columns, and only further in the lit throne / 壁の鉄の受けに載せた油ランプで、ごく暗い。西半分が真っ黒にならないようにする：大扉から入ると、まず手前の柱が見え、奥に進んでようやく明るい王座が見える |
| Main door / 大扉 | x −6, 4 m wide (y −2〜2), 5 m high / x −6、幅 4 m（y −2〜2）、高さ 5 m | Two thick wooden leaves clad in bronze, opening inward against the walls (y ±2〜±4). Always open in the first release / 青銅で覆った厚い木の扉 2 枚で、内側に開いて壁に沿う（y ±2〜±4）。第 1 版ではずっと開いている |
| Guards / 警吏 | Inside the main door on both sides (−5, ±2.6), at both ends of the steps (9.8, ±3.6) / 大扉の内側の両脇 (−5, ±2.6)、段の両端 (9.8, ±3.6) | A crowd, placed by Frontend per place (contract 3.1, they don't take spots). The two at the ends of the steps also tell the player "this far and no further" / 群衆で、フロントエンドが場所ごとに配置する（契約 3.1、スポットを占有しない）。段の両端の 2 人は、プレイヤーに「ここまで」と伝える役も兼ねる |
| Courtiers / 群臣 | Outside the north row of columns, x −2〜11, y 5.5, about 6 people / 北の列の柱の外側、x −2〜11、y 5.5、約 6 人 | Section 4. Style guide [m3-extras.md](../style-guide/characters/m3-extras.md), "Courtiers" / 4 節。スタイルガイド [m3-extras.md](../style-guide/characters/m3-extras.md)「群臣」 |

Navmesh: the throne room floor is walkable up to the foot of the steps (x 9.8), **the player doesn't go up the steps**; columns and braziers are walked around.

ナビメッシュ：玉座の間の床は段の足もと（x 9.8）まで歩ける。**プレイヤーは段を上らない**。柱と火鉢は避けて通る。

### 3.2 Staging and camera / 演出とカメラ

Camera rules follow ux-design 6.3. The throne room is 14 m wide and can't fit the exploration camera 9 m behind the player, so **indoors uses the indoor mode**: 5.5 m behind the player, 2.6 m high, looking at a point 1.5 m above the player's feet. It switches together with the roughly 1-second exposure transition when crossing the main door (section 3), and switches back on the way out. During story moments **the camera is never taken over**: characters entering and leaving don't cut or turn the camera; footsteps and characters turning their heads tell the player where to look.

カメラのルールは ux-design 6.3 に従う。玉座の間は幅 14 m で、背後 9 m の探索カメラが収まらないため、**屋内は室内モードを使う**：プレイヤーの背後 5.5 m、高さ 2.6 m で、プレイヤーの足もとから 1.5 m 上の点を見る。大扉をまたぐときの約 1 秒の露出の切り替えと一緒に切り替え（3 節）、外へ出るときに戻す。物語の場面でも**カメラを奪わない**：人物の登場や退場でカットを切り替えたりカメラを回したりせず、足音と人物の振り向きでプレイヤーにどこを見ればよいかを伝える。

**beat.04 Marched in** (around 約束の日 20:00) / **beat.04 連行**（約束の日 20:00 前後）
- Melos appears at `melos-led-in`, with two guards one on each side, each half a step behind, one holding the end of the rope binding his hands. He walks slowly (about 1.0 m/s) through the courtyard at night (braziers, starry sky), into the throne room, and stops at `before-king`, with the guards standing at (5, ±1.6).
  メロスは `melos-led-in` に現れ、2 人の警吏が左右に 1 人ずつ半歩遅れて付き、1 人が手を縛った縄の端を持つ。ゆっくり歩き（約 1.0 m/s）、夜の中庭（火鉢、星空）を抜けて玉座の間に入り、`before-king` で止まる。警吏は (5, ±1.6) に立つ。
- His look follows "Bound in the throne room" under "Looks added in M3" in the style guide [melos.md](../style-guide/characters/melos.md): hands bound in front, dagger confiscated, his bundle set down by the guards beside the steps (at the foot of the steps on the south side, about (9.6, −1.4)).
  見た目はスタイルガイド [melos.md](../style-guide/characters/melos.md)「M3 で追加する姿」の「玉座の間で縛られる」に従う：両手は体の前で縛られ、短剣は没収され、荷物は警吏が段の横（南側の段の足もと、約 (9.6, −1.4)）に置く。
- He stands, does not kneel, and keeps his head up looking at the king (「悪びれずに答えた」).
  彼は立ったまま、ひざまずかず、顔を上げて王を見る（「悪びれずに答えた」）。
- A player who followed him in lands at `gate-in`, follows him to the throne room, and stands at `companion-aside` (ux-design 5.1).
  ついて来たプレイヤーは `gate-in` に着地し、玉座の間までついて行き、`companion-aside` に立つ（ux-design 5.1）。

**beat.05 Questioning and the pact** (20:30) / **beat.05 問答、約束**（20:30）
- The king is seated, using seated idle and talking animations; his face uses the presets in [king.md](../style-guide/characters/king.md): neutral when asking 「この短刀で何をするつもりであったか」, 「憫笑」 at 「おまえがか？」 (followed by 「おまえには、わしの孤独がわからぬ」), 「北叟笑む」 after Melos offers to leave セリヌンティウス as a hostage (「そっと北叟笑んだ」), with his head turned aside to hide it.
  王は座ったまま、座りの待機と会話のモーションを使う。顔は [king.md](../style-guide/characters/king.md) のプリセットを使う：「この短刀で何をするつもりであったか」と問うときは平常、「憫笑」は「おまえがか？」で（続いて「おまえには、わしの孤独がわからぬ」）、「北叟笑む」はメロスがセリヌンティウスを人質に残すと申し出たあと（「そっと北叟笑んだ」）、顔をそむけて人に見せない。
- When the player isn't speaking they just stand at `companion-aside` and watch: in the default shot Melos is center-left (from behind with a little of his profile), the king is center-top, the hanging lamp is at the top edge of the frame above the king's head, and the courtiers are behind the columns on the right.
  プレイヤーが話していないときは `companion-aside` に立って見ている：デフォルトのショットではメロスは中央やや左（後ろ姿に少し横顔）、王は中央上、吊りランプは王の頭上で画面の上端、群臣は右側の柱の後ろ。
- **The player speaks to the king**: over-the-shoulder shot, camera 1.2 m behind the player's right shoulder, 1.4 m high (below eye level), looking up at the king's face: the king's face in the upper third of the frame, the indigo curtain behind him, the hanging lamp's light coming in from the top edge of the frame. **No reverse shot**: when the king speaks it stays on this shot; there is no "king looking down at the player" shot. More than 6 m from the king (e.g. saying 「保証する」 from `companion-aside`), narrow the field of view to about 25° so the king's upper body still fills the upper third of the frame.
  **プレイヤーが王に話しかける**：肩越しのショットで、カメラはプレイヤーの右肩の後ろ 1.2 m、高さ 1.4 m（目より低い）、王の顔を見上げる：王の顔は画面の上 1/3 に、背後には藍色の垂れ幕、吊りランプの光が画面の上端から入る。**切り返しはしない**：王が話すときもこのショットのままで、「王がプレイヤーを見下ろす」ショットは出さない。王から 6 m 以上離れているとき（たとえば `companion-aside` から「保証する」と言うとき）は画角を約 25° に絞り、王の上半身が画面の上 1/3 を占めるようにする。
- Things to check: catchlights from the braziers in both of the king's eyes; neither the king's robe nor the curtain reads as red under the lamps.
  確認すること：王の両目に火鉢の映り込みがある。王の上衣と垂れ幕が灯の下で赤に見えない。
- 「保証する」: when the player speaks, the king turns his head toward the player (about 30〜40°), and Melos glances back. The king's answer is still directed at the player.
  「保証する」：プレイヤーが口を開くと王は頭をプレイヤーのほうへ向け（約 30〜40°）、メロスは振り返ってちらりと見る。王の答えはそのままプレイヤーに向ける。

**beat.06 セリヌンティウス is summoned** (23:30) / **beat.06 セリヌンティウスが呼び出される**（23:30）
- He comes in from `selinuntius-in` with a guard behind him, his look following "Summoned" in [selinuntius.md](../style-guide/characters/selinuntius.md) (a cloak over his shoulders, taken off him once he's inside). He walks to `selinuntius-meet` at about 1.2 m/s. His footsteps echo in the hall: players who hear them turn around.
  彼は `selinuntius-in` から入ってきて、後ろに警吏が 1 人付く。見た目は [selinuntius.md](../style-guide/characters/selinuntius.md) の「召喚される」に従う（外套をはおり、入るとそれを取られる）。約 1.2 m/s で `selinuntius-meet` まで歩く。足音が広間に反響し、聞いたプレイヤーは振り向く。
- Melos turns to face him. The guard first unties Melos's rope (about 3 seconds). Melos tells him what happened (the original has only one line, 「メロスは、友に一切の事情を語った」: don't play it all out; the narration covers it in one line), セリヌンティウス nods without a word and **holds Melos tight** (「ひしと抱きしめた」, about 3 seconds, F-16's dedicated animation). Then the guard ties セリヌンティウス's hands in front of him (「セリヌンティウスは、縄打たれた」).
  メロスは彼のほうへ向き直る。警吏がまずメロスの縄をほどく（約 3 秒）。メロスが事情を話す（原作は「メロスは、友に一切の事情を語った」の 1 文だけ：全部は演じず、ナレーションの 1 行で済ませる）。セリヌンティウスは無言でうなずき、**メロスをひしと抱きしめる**（「ひしと抱きしめた」、約 3 秒、F-16 の専用モーション）。それから警吏がセリヌンティウスの両手を体の前で縛る（「セリヌンティウスは、縄打たれた」）。
- When the two embrace they are about 4 m from `companion-aside`, and in the indoor-mode shot they are in the middle of the frame: the spots were arranged with this in mind.
  二人が抱き合うとき、`companion-aside` から約 4 m 離れていて、室内モードのショットでは二人が画面の中央にいる：スポットはこれに合わせて配置した。

**beat.07 Departure** (23:45) / **beat.07 出発**（23:45）
- Melos picks up his bundle beside the steps, turns and leaves at once (about 1.6 m/s, a brisk walk, not a run), back the way he came through the courtyard and the gate passage, fading out at `way.plaza`. As he steps out of the main door the camera switches back to exploration mode: the courtyard sky is full of stars (「初夏、満天の星である」).
  メロスは段の横から荷物を取り上げ、すぐに向きを変えて去る（約 1.6 m/s、早足で、走らない）。来た道を戻って中庭と城門の通路を抜け、`way.plaza` でフェードアウトする。大扉を出た瞬間にカメラは探索モードに戻る：中庭の空は満天の星（「初夏、満天の星である」）。
- セリヌンティウス is led by a guard to `hostage-column`. The player can follow Melos as far as the gate passage; outside the gate is the plaza scene (`go`).
  セリヌンティウスは警吏に `hostage-column` まで連れて行かれる。プレイヤーはメロスについて城門の通路まで行ける。城門の外は広場のシーン（`go`）。

**The hostage's three days** (一日目〜三日目, the courtyard's north colonnade) / **人質の 3 日間**（一日目〜三日目、中庭の北の柱廊）
- He has his back against a second-row column, the rope tied to an iron ring on the column (selinuntius.md, "Three days in the colonnade"). His pose changes with the time of day; Frontend schedules the idles from this table:
  彼は 2 列目の柱に背をもたせ、縄は柱の鉄の輪に結ばれている（selinuntius.md「柱廊での三日間」）。姿勢は時刻によって変わり、フロントエンドはこの表に沿って待機モーションを並べる：

| When / いつ | Pose / 姿勢 |
|---|---|
| 一日目 0:00〜sunrise / 一日目 0:00〜日の出 | Sitting against the column, head resting on it / 柱にもたれて座り、頭を柱にあずける |
| 一日目 daytime / 一日目の昼 | Sitting; stands up when someone comes / 座っている。人が来ると立ち上がる |
| 二日目 from 12:30, rain / 二日目 12:30 から雨 | Sitting, watching the rain / 座って雨を見ている |
| 三日目 morning / 三日目の午前 | Sitting, clothing at stage 2 / 座っている、衣服は第 2 段階 |
| 三日目 from 15:30 / 三日目 15:30 から | Stands up and looks west at the wall over the gate (the sun is beyond that wall) / 立ち上がり、西の城門のある壁を見ている（太陽は壁の向こう） |
| 三日目 16:00 (beat.s2) / 三日目 16:00（beat.s2） | The wall shadow sweeps to just in front of him: the flash of 「一瞬の疑い」 (selinuntius.md acceptance check 3), then he lowers his head / 壁の影が彼の真ん前まで来る：「一瞬の疑い」のひらめき（selinuntius.md 受け入れ確認 3）、それからうつむく |
| 三日目 evening / 三日目の夕方 | Taken to the execution ground, hands now tied behind him (the look from the ending version) / 刑場へ連行され、両手は後ろ手に縛り直される（エンディング版の見た目） |

- **The player talks beside him**: when he is sitting and the player comes within 1.5 m and speaks, the player character drops to one knee (using an existing crouch idle; Frontend picks the clip), so their eyes are at about the same height and the over-the-shoulder shot looks at him level. When he is standing the player stands too.
  **プレイヤーが彼のそばで話す**：彼が座っているとき、プレイヤーが 1.5 m 以内に来て話し始めると、プレイヤーキャラクターは片膝をつく（既存のしゃがみ待機を使い、クリップはフロントエンドが選ぶ）。二人の目の高さがほぼそろい、肩越しのショットは水平に彼を見る。彼が立っているときはプレイヤーも立つ。
- The colonnade is about 5 m high and 4 m deep: there is room for the over-the-shoulder dialogue shot; the exploration camera looks into the colonnade from the open-air courtyard.
  柱廊は高さ約 5 m、奥行き 4 m：会話の肩越しのショットは収まる。探索カメラは中庭の露天部分から柱廊の中をのぞく。

## 4. Spots / スポット

Order them like this in the layout. A character with no spot written stands at the first free auto spot of the place (Data 16:01Z, contract 3.1), so **`king-throne` comes first**: the king is in the castle from the start, and no beat writes a spot for him (Data, #44 review). Player start and landing spots and staging spots are all marked `auto: false`; the only auto spots are `king-throne` and `hostage-visit`.

レイアウトではこの順に並べる。スポットが書かれていない人物は、その場所で最初に空いている自動で立てるスポットに立つ（データ 16:01Z、契約 3.1）。だから **`king-throne` を一番目にする**：王は最初から王城にいて、彼にスポットを書くビートがない（データ、#44 レビュー）。プレイヤーの開始点と着地点、演出用のスポットはすべて `auto: false` とし、自動で立てるのは `king-throne` と `hostage-visit` だけ。

| Name / 名前 | Position / 位置 | Facing / 向き | Use / 用途 |
|---|---|---|---|
| `king-throne` | (13.5, 0), on the dais / (13.5, 0)、台の上 | −x | The king. **The first auto spot of `place.castle`** / 王。**`place.castle` の最初の自動で立てるスポット** |
| `hostage-visit` | (−14.5, 4.5) | North-northeast (toward the hostage) / 北やや東（人質のほう） | In the courtyard, diagonally in front of the hostage; people who come to see the hostage stand here. The second auto spot / 中庭の、人質の斜め前。人質に会いに来た人はここに立つ。2 つ目の自動で立てるスポット |
| `gate-in` `auto: false` | (−27, 0) | +x | **Landing spot when coming in from the plaza** (for those who follow Melos into the castle); the `startSpots` of `place.castle`. Behind is outside the gate; the camera sits in the gate passage, pulled in close / **広場から入るときの着地スポット**（メロスについて城に入った人）。`place.castle` の `startSpots`。背後は城門の外で、カメラは門の通路の中に置いて寄せる |
| `melos-led-in` `auto: false` | (−25, 0), in the gate passage / (−25, 0)、城門の通路の中 | +x | Where Melos appears when marched in (after being seized on the plaza side at beat.04). Target: `before-king`: two guards lead him, hands bound in front, through the courtyard into the throne room. How he walks on the way is played out by Frontend along the navmesh; no route is written. 2 m ahead of `gate-in`: a player who follows lands behind him / メロスが連行されてくるときに現れる起点（beat.04 で広場側で捕まったあと）。目標は `before-king`：2 人の警吏が彼を連れ、両手は体の前で縛られ、中庭を抜けて玉座の間へ入る。途中の歩き方はフロントエンドがナビメッシュに沿って演じ、経路は別に書かない。`gate-in` の 2 m 前：ついて来たプレイヤーは彼の背後に着地する |
| `before-king` `auto: false` | (5, 0) | +x | Melos is brought before the steps, with a guard on each side (5, ±1.6). beat.04's relocate writes this spot / メロスは段の前まで連れて来られ、両側に警吏が 1 人ずつ (5, ±1.6)。beat.04 の relocate はこのスポットを書く |
| `companion-aside` `auto: false` | (1.0, −1.8) | +x, slightly north (toward (1, 0.2)) / +x やや北（(1, 0.2) の方向） | For someone brought in alongside who "stands to one side" (ux-design 5.1), 4 m behind Melos to his left, south of the central axis. 「保証する」 is said from here. A spot for the player. v1.1 moved it from (3.5, −4.8): there the south wall was right behind, leaving no room for the indoor-mode camera; from here both Melos and the king are in frame (3.2) / 一緒に連れて来られた人が「脇に立つ」ためのスポット（ux-design 5.1）。メロスの左後方 4 m、中心軸の南側。「保証する」はここから言う。プレイヤーが立つスポット。v1.1 で (3.5, −4.8) から移した：元の位置は背後が南の壁で室内モードのカメラが収まらなかった。ここからならメロスも王も画面に入る（3.2） |
| `selinuntius-in` `auto: false` | (−5, 0), inside the main door / (−5, 0)、大扉の内側 | +x | Where セリヌンティウス appears when brought in at beat.06; he walks to `selinuntius-meet` / beat.06 でセリヌンティウスが連れて来られるときに現れる起点。`selinuntius-meet` まで歩く |
| `selinuntius-meet` `auto: false` | (4, 0.6) | Toward Melos / メロスのほう | beat.06's relocate writes this spot: he walks up to Melos, the two embrace, then he is bound / beat.06 の relocate はこのスポットを書く：メロスの前まで歩き、二人が抱き合い、それから縛られる |
| `hostage-column` `auto: false` | (−12.5, 7.6), a second-row column of the north colonnade / (−12.5, 7.6)、北の柱廊の 2 列目の柱 | South (toward the courtyard) / 南（中庭のほう） | The hostage is tied here, standing or sitting against the column. beat.07's relocate writes this spot / 人質はここに縛られ、立つか柱にもたれて座る。beat.07 の relocate はこのスポットを書く |
| `hostage-near` `auto: false` | (−13.4, 6.6), between two front-row columns of the north colonnade / (−13.4, 6.6)、北の柱廊の前列の 2 本の柱の間 | Northeast (toward (0.67, 0.74), toward the hostage) / 北東（(0.67, 0.74) の方向、人質のほう） | **Landing spot for 「城に残り、セリヌンティウスのそばにいる」** (`exit.1.vigil`; Data writes this spot in the destination). About 1.35 m from the hostage. The camera is behind at (−19.4, −0.1), in the open-air courtyard, clear of the cistern and the columns. v1.1 moved it from (−12.5, 5.5): from there the front-row column (−12.5, 6) stood right in front and blocked the hostage / **「城に残り、セリヌンティウスのそばにいる」の着地スポット**（`exit.1.vigil`、データが行き先にこのスポットを書く）。人質から約 1.35 m。背後の (−19.4, −0.1) がカメラで、中庭の露天部分にあり、貯水槽と柱を避けている。v1.1 で (−12.5, 5.5) から移した：元の位置は真正面に前列の柱 (−12.5, 6) があり、人質を隠していた |
| `hostage-guard` `auto: false` | (−8.5, 9.3) | Southwest / 南西 | Where the watching guards (`char.guards`) stand. Guards are a crowd and don't take spots (contract 3.1, api-contract 2.3); Frontend places them here per place, and Data doesn't write this spot / 見張りの警吏（`char.guards`）が立つ場所。警吏は群衆でスポットを占有しない（契約 3.1、api-contract 2.3）。フロントエンドが場所ごとにここに配置し、データはこのスポットを書かない |
| `way.plaza` | (−31, 0) | | Back to the plaza / 広場へ戻る |

- The courtiers (`courtiers`) are not a spot: outside the north row of columns, x −2〜11, y 5.5, about 6 people, facing south. They aren't in the world model; they are set dressing (ux-design 10, the king's "doesn't expose his failings in front of the courtiers"). They are on the opposite side from `companion-aside`: whoever followed in doesn't mix with the courtiers.
  群臣（`courtiers`）はスポットではない：北の列の柱の外側、x −2〜11、y 5.5、約 6 人、南向き。世界モデルにはいない人々で、背景の飾り（ux-design 10 の王の「群臣の前では彼の短所を暴かない」）。`companion-aside` とは反対側に分ける：ついて来た人は群臣に混ざらない。
- beat.07: Melos turns and leaves at once, from `before-king` through the courtyard and out of the gate, fading out at `way.plaza` under a sky full of stars. Data has beat.07 move him out of the castle (onto the road outside the city); Frontend plays out the walk.
  beat.07：メロスはすぐに向きを変えて去り、`before-king` から中庭を抜けて城門を出て、満天の星の下 `way.plaza` でフェードアウトする。データは beat.07 で彼を王城の外（城外の道）へ移し、道中はフロントエンドが演じる。
- Each spot in the layout is a single point. When a character changes place they appear at the start point and walk along the navmesh to the target point (Frontend, #44 review), so the table above gives start and target points, not routes.
  レイアウトのスポットはどれも 1 点。人物が場所を変えるときは起点に現れ、ナビメッシュに沿って目標点まで歩く（フロントエンド、#44 レビュー）。だから上の表には起点と目標点を書き、経路は書かない。

## 5. Light / 光

### 5.1 How each time of day looks / 時間帯ごとの見た目

| Time / 時間帯 | Where / 場所 | Look / 見た目 |
|---|---|---|
| 約束の日 20:00〜23:45 | Throne room / 玉座の間 | Only the hanging lamp and the braziers, about 1800〜2000K, flickering gently; the shadows have color and aren't dead black (art-direction 2 references 『バリー・リンドン』). Stars outside the high windows / 吊りランプと火鉢だけで、約 1800〜2000K、かすかに揺らめく。暗部に色があり、真っ黒ではない（art-direction 2 の参照は『バリー・リンドン』）。高窓の外は星 |
| Same as above / 同上 | Courtyard, gate passage / 中庭、城門の通路 | Braziers. Look up and the sky is full of stars, no moon. When Melos leaves the city the Milky Way is overhead (「満天の星」) / 火鉢。見上げると満天の星で、月はない。メロスが城を出るとき頭上には天の川（「満天の星」） |
| 一日目〜三日目 daytime / 一日目〜三日目の昼 | Courtyard / 中庭 | Real-time sun. The hostage is in the second row of the north colonnade, always in shadow, watching the shadows of the front-row columns move across the flagstones / リアルタイムの太陽。人質は北の柱廊の 2 列目にいて、ずっと日陰にいて、前列の柱の影が敷石の上を動いていくのを見ている |
| **三日目 after 16:00 / 三日目 16:00 以降** | Courtyard / 中庭 | **A clock the hostage can see**: the sun drops behind the wall over the west gate (about 8 m high), and the wall's shadow sweeps across the courtyard flagstones from west to east (at 16:00 the sun is 35° high and the shadow about 11 m long, reaching just in front of the hostage; at 17:00 about 19 m, covering the whole courtyard), then climbs the front of the throne room (about 4 m up at 18:00, about 6 m at 18:30), until only the top of the tower is lit (the tower is outside the shadow frustum, so the light on its top is computed separately from the sun's altitude, Frontend 15:57Z): the same sun, and the same meaning, as the shadow climbing the castle wall seen from the plaza (art-direction 3.4 ①). The flash of doubt in beat.s2 (16:00) comes exactly when the wall shadow sweeps to just in front of him / **人質の側から見える時計**：太陽が西の城門の壁（高さ約 8 m）の向こうへ沈み、壁の影が中庭の敷石を西から東へ掃いていく（16:00 は太陽高度 35°、影の長さ約 11 m で人質の真ん前まで届く。17:00 は約 19 m で中庭全体を覆う）。それから玉座の間の正面を這い上がり（18:00 に高さ約 4 m、18:30 に約 6 m）、最後は塔の頂にだけ光が残る（塔は影の範囲の外にあるので、塔の頂の光は太陽高度から別に計算する、フロントエンド 15:57Z）：広場から見える王城の壁を這い上がる影（art-direction 3.4 ①）と同じ太陽、同じ意味。beat.s2 の一瞬の疑い（16:00）は、壁の影が彼の真ん前まで来たときに起きる |
| Night (一日目〜三日目) / 夜（一日目〜三日目） | Courtyard / 中庭 | Braziers and starry sky. The hostage's face is lit by a single brazier / 火鉢と星空。人質の顔を照らすのは火鉢 1 つだけ |
| Rain (二日目 12:30〜三日目 09:00) / 雨（二日目 12:30〜三日目 09:00） | Courtyard / 中庭 | Weather is one global value (`var.weather`, Data 16:01Z), so it rains in the city too: rain falls on the open-air courtyard, the colonnades stay dry, and the hostage watches the rain from under the colonnade. From 三日目 09:00 it's after the rain: the flagstones are wet and slowly drying, and the afternoon wall shadow falls on nearly dry stone / 天気は全体で 1 つの値（`var.weather`、データ 16:01Z）なので、城の中も雨：雨は中庭の露天部分に降り、柱廊の下は乾いていて、人質は柱廊の下から雨を見ている。三日目 09:00 からは雨上がり：敷石は濡れていて少しずつ乾き、午後の壁の影はほぼ乾いた敷石の上に落ちる |
| 一日目〜三日目 daytime / 一日目〜三日目の昼 | Throne room / 玉座の間 | The first release uses the night lighting set: lamplight, curtain drawn, high windows shut with a few lines of light through the shutter gaps, and the courtyard's daylight coming in through the main door. In the afternoon a patch of light that follows the sun lies on the floor inside the door (section 3): it grows inward from the threshold, leaves the threshold around 16:55 and becomes a band moving inward, and goes out around 18:05. Crossing the threshold, the exposure recovers in about 1 second / 第 1 版は夜の光のセットを使う：灯、垂れ幕は引いたまま、高窓は閉じて板の隙間から光の線が何本か、大扉から中庭の昼の光が差し込む。午後は扉の内側の床に太陽に合わせて動く光がある（3 節）：敷石から奥へ伸び、16:55 ごろ敷居を離れて奥へ進む光の帯になり、18:05 ごろ消える。敷居をまたぐと露出が約 1 秒で戻る |
| Daytime (later) / 昼（のちに） | Throne room / 玉座の間 | Shafts of light from the high windows (section 3). How to build it later (Frontend 15:57Z): for each high window a set of soft-edged translucent cards plus slowly drifting dust motes, oriented by the real-time sun from the window toward the floor, drawing only the few windows visible to the camera / 高窓からの光の柱（3 節）。のちに作るときのやり方（フロントエンド 15:57Z）：高窓ごとに縁の柔らかい半透明のカードを 1 組とゆっくり漂う塵の粒を置き、向きはリアルタイムの太陽から窓から床へ向けて計算し、カメラに映る数枚の窓だけ描く |

### 5.2 How many sets to bake / ベイクするセットの数

| Priority / 優先度 | Set / セット | Used for / 用途 |
|---|---|---|
| 1 | Throne room · night (hanging lamp and braziers) / 玉座の間・夜（吊りランプと火鉢） | The main scene of act 1 / 第一幕の見せ場 |
| 1 | Courtyard · 三日目 16:00〜19:00 (wall shadow sweeping the courtyard) / 中庭・三日目 16:00〜19:00（壁の影が中庭を掃く） | The hostage's 「日没」 / 人質の側の「日没」 |
| 2 | Courtyard · night (braziers and starry sky) / 中庭・夜（火鉢と星空） | Hostage night, Melos's departure / 人質の夜、メロスの出発 |
| 3 | Courtyard · daytime / rain / 中庭・昼 / 雨 | 一日目, 二日目 / 一日目、二日目 |

Frontend 15:57Z: in practice about 4 bakes: throne room · night (lamps and braziers are static, baked once; the flicker is a gentle adjustment of overall brightness), throne room · daytime, courtyard · evening (mainly the real-time sun, with baked skylight), courtyard · night; courtyard daytime and rain share one set, dimmed. Each set is about 0.6〜1 MB, about 6〜7 MB to download in total. The castle isn't a first screen; on `go` from the plaza, download the set needed first (about 2〜3 MB, under 4 seconds on 4G) and the rest in the background. The first release doesn't do throne room · daytime (PM 16:05Z), so it's 3 bakes, about 5 MB 〔estimated from Frontend's numbers〕.

フロントエンド 15:57Z：実際には約 4 回のベイク：玉座の間・夜（灯と火鉢は静止しているので 1 回ベイクし、揺らめきは全体の明るさを軽く変えて表す）、玉座の間・昼、中庭・夕方（リアルタイムの太陽が主で、天空光をベイク）、中庭・夜。中庭の昼と雨は 1 セットを暗くして共用する。1 セット約 0.6〜1 MB で、ダウンロードは合計約 6〜7 MB。王城は最初の画面ではないので、広場から `go` で入るときに必要なセットを先にダウンロードし（約 2〜3 MB、4G で 4 秒以内）、残りはバックグラウンドで落とす。第 1 版は玉座の間・昼を作らない（PM 16:05Z）ので、ベイクは 3 回、約 5 MB〔フロントエンドの数字から推算〕。

## 6. People and materials / 人物と素材

### 6.1 People / 人物

| Who / 誰 | Detail level / 精度 | Key points / 要点 |
|---|---|---|
| 王ディオニス | Dialogue grade / 会話用 | Style guide [king.md](../style-guide/characters/king.md) (face, expression presets, seated pose, robe border), silhouette per `ending-cast.md`. Seated in the throne room: the seated idle and talking use UAL's ready-made `Sitting_Idle_Loop` and `Sitting_Talking_Loop`; 「憫笑」 and 「北叟笑ん」 are facial, done with ARKit blendshape expression presets (one corner of the mouth raised, eyelids, brows), not animation clips. Only the gestures need to be made separately, scheduled together with the dedicated ending animations (Frontend 15:57Z) / スタイルガイド [king.md](../style-guide/characters/king.md)（顔、表情プリセット、座り姿、上衣の縁取り）、輪郭は `ending-cast.md` に従う。玉座の間では座っている：座りの待機と会話は UAL の既製の `Sitting_Idle_Loop`、`Sitting_Talking_Loop` を使う。「憫笑」「北叟笑ん」は顔なので、ARKit のブレンドシェイプによる表情プリセット（口角の片側を上げる、まぶた、眉）で作り、アニメーションクリップには数えない。別に作るのは手振りだけで、エンディングの専用モーションと一緒に予定を組む（フロントエンド 15:57Z） |
| Melos / メロス | Dialogue grade / 会話用 | "Bound in the throne room" under "Looks added in M3" in the style guide [melos.md](../style-guide/characters/melos.md): act 1 clothing, hands tied in front with hemp rope, bundle set beside the steps, untied before the embrace / スタイルガイド [melos.md](../style-guide/characters/melos.md)「M3 で追加する姿」の「玉座の間で縛られる」：第一幕の衣服、両手は体の前で麻縄で縛られ、荷物は段の横に置かれ、抱き合う前にほどかれる |
| セリヌンティウス | Dialogue grade / 会話用 | Style guide [selinuntius.md](../style-guide/characters/selinuntius.md): "Summoned" (cloak, taken off once inside), and once bound, "Three days in the colonnade" in 2 stages (一日目 night〜二日目, 三日目); the expression presets include 「一瞬の疑い」 and 「憔悴」 / スタイルガイド [selinuntius.md](../style-guide/characters/selinuntius.md)：「召喚される」（外套をはおり、入ると取られる）、縛られたあとは「柱廊での三日間」の 2 段階（一日目の夜〜二日目、三日目）。表情プリセットに「一瞬の疑い」と「憔悴」がある |
| Guards / 警吏 | Walk-around grade (the two leading Melos before the steps need to hold up at medium distance) / 歩行用（段の前でメロスを連れる 2 人は中景に耐えること） | Shared with the plaza / 広場と共用 |
| Courtiers / 群臣 | Walk-around grade / 歩行用 | About 6 people, style guide [m3-extras.md](../style-guide/characters/m3-extras.md), "Courtiers" / 約 6 人、スタイルガイド [m3-extras.md](../style-guide/characters/m3-extras.md)「群臣」 |

### 6.2 Materials / 素材

| Material / 素材 | Distance / 距離 | Key points / 要点 |
|---|---|---|
| Polished dark stone floor / 磨いた暗色の石の床 | **Close-up, most important / 近景、最重要** | Throne room. Reflections of the lamplight; always in the lower part of the frame in the low-angle dialogue shot / 玉座の間。灯の映り込み。会話のあおりのショットでは常に画面の下部にある |
| Columns and walls (plastered limestone) / 柱と壁（漆喰を塗った石灰岩） | Close-up / 近景 | An ochre-black band around the base of the walls / 壁の足もとに赭黒の帯が一周 |
| Heavy curtain / 厚い垂れ幕 | Close-up / 近景 | Deep indigo or deep purple wool, must not turn red / 深い藍色か深い紫の羊毛、赤になってはいけない |
| Throne / 王座 | Close-up / 近景 | Carved wood, bronze fittings, high back / 彫刻した木、青銅の飾り金具、高い背もたれ |
| Bronze lamps and braziers / 青銅のランプと火鉢 | Close-up / 近景 | Dulled bronze, firelight / くすんだ青銅、火の光 |
| Courtyard flagstones / 中庭の敷石 | Close-up / 近景 | The same limestone as the plaza, more regular / 広場と同じ石灰岩で、より整っている |
| Hemp rope / 麻縄 | Close-up / 近景 | On the hostage and on Melos's hands / 人質の体とメロスの手に |

**Swap to 2048 on high-end devices** (as art-direction 9.3 already says): polished dark stone floor, columns and walls, heavy curtain, throne.

**ハイエンド機では 2048 に差し替える**（art-direction 9.3 の記述どおり）：磨いた暗色の石の床、柱と壁、厚い垂れ幕、王座。

## 7. Agreed with Frontend and Data / フロントエンド、データと決めたこと

**Frontend** (10-10 15:57Z, `frontend/estimates/village-castle-answers.md`, folded into 5.1, 5.2, 6.1):
- Light shafts are cards plus dust motes, oriented by the real-time sun (the first release has no daytime throne room; left for later).
- The king's seated idle and talking use ready-made animations, 「憫笑」 and 「北叟笑ん」 use facial blendshape presets; only the gestures are scheduled together with the dedicated ending animations.
- The courtyard wall shadow follows the plaza's approach (real-time sun + baked skylight and occlusion); the last ray of light on the tower top is computed separately from the sun's altitude.
- The first release has 3 bakes (throne room · night, courtyard · evening, courtyard · night; courtyard daytime and rain share one set, dimmed), about 5 MB 〔estimate〕.

**フロントエンド**（10-10 15:57Z、`frontend/estimates/village-castle-answers.md`、5.1、5.2、6.1 に反映済み）：
- 光の柱はカードと塵の粒で作り、向きはリアルタイムの太陽に従う（第 1 版は玉座の間の昼を作らず、のちに回す）。
- 王の座りの待機と会話は既製のモーションを使い、「憫笑」「北叟笑ん」は顔のブレンドシェイプのプリセットを使う。手振りだけをエンディングの専用モーションと一緒に予定を組む。
- 中庭の壁の影は広場のやり方に従う（リアルタイムの太陽＋天空光と遮蔽のベイク）。塔の頂の最後のひと筋の光は太陽高度から別に計算する。
- 第 1 版のベイクは 3 回（玉座の間・夜、中庭・夕方、中庭・夜。中庭の昼と雨は 1 セットを暗くして共用）、約 5 MB〔推算〕。

**Data** (10-10 16:01Z, folded into sections 0, 4 and 5.1):
- `place.castle` isn't split; spots are enough: people in the courtyard, the colonnades and the throne room all count as present for beat.05, 06, 07 and s2. The king's whisper `fact.king-whisper` is private and can't be heard even by those present.
- Beat relocates: beat.04 Melos → `before-king`; beat.06 セリヌンティウス → `selinuntius-meet` (changed in the #44 review from "the end point of `selinuntius-in`" to a separate spot); at beat.07, as Melos departs, セリヌンティウス → `hostage-column`; `exit.1.vigil` lands at `hostage-near`.
- beat.04 is in front of the castle gate on the plaza side (`place.execution-ground`), the same place as in the slice; the castle scene starts from being marched into the gate passage (sections 0 and 4, `melos-led-in`).
- Weather is one global value, so it rains in the city too (5.1).

**データ**（10-10 16:01Z、0 節、4 節、5.1 に反映済み）：
- `place.castle` は分けず、スポットで足りる：中庭、柱廊、玉座の間にいる人はみな beat.05、06、07、s2 に居合わせたとみなす。王の耳打ち `fact.king-whisper` は private で、居合わせても聞こえない。
- ビートの relocate：beat.04 メロス → `before-king`。beat.06 セリヌンティウス → `selinuntius-meet`（#44 レビューで「`selinuntius-in` の終点」から独立したスポットに変更）。beat.07 でメロスが出発するときセリヌンティウス → `hostage-column`。`exit.1.vigil` は `hostage-near` に着地する。
- beat.04 は広場側の王城の門前（`place.execution-ground`）で、スライスと同じ場所。王城のシーンは城門の通路へ連れ込まれるところから始まる（0 節、4 節 `melos-led-in`）。
- 天気は全体で 1 つの値なので、城の中も雨が降る（5.1）。

**PM** (10-10 16:05Z): 「王城にとどまる」 is not in the first release; the first release only does the throne room at night.

**PM**（10-10 16:05Z）：「王城にとどまる」は第 1 版では作らない。第 1 版の玉座の間は夜だけ作る。

**PM** (10-10 19:52Z, after Data pointed out in #52 that players guarding the hostage can enter the throne room by day): chose A, using the night lighting set by day too (sections 0, 3, 5.1). The concrete approach is in the Frontend paragraph below.

**PM**（10-10 19:52Z、人質を見守るプレイヤーが昼に玉座の間に入れることをデータが #52 で指摘したのを受けて）：A を選び、昼も夜の光のセットを使う（0 節、3 節、5.1）。具体的なやり方は下のフロントエンドの段落を参照。

**Frontend** (10-10 20:29Z, #52 review): A can be made to look good; "bright courtyard → sudden darkness, only lamps" is attractive in itself. Four things, none needing an extra baked set: ① the interior ignores the sun and sky (fully baked, interior materials, the room's own probes); ② about 1 second of exposure adjustment when crossing the threshold, at night too; ③ a faint light-patch texture on the floor inside the door, on by day and off at night; ④ the high windows really closed. UX and Frontend went over it together (PM asked both sides at 20:30Z to talk directly): the shape of ③'s light patch is computed from the real-time sun (section 3, "Main door"), not a fixed patch. Frontend agreed at 20:48Z: every clock update moves the four vertices of the quad, texture and material unchanged, off in rain and at night; the real heights of the doorway and eaves get measured when the castle is built, and a timetable of the light band from the real model goes back to UX for checking.

**フロントエンド**（10-10 20:29Z、#52 レビュー）：A はきれいに作れる。「明るい中庭 → 急に暗くなって灯だけ」はそれ自体が美しい。4 点あり、どれも光のセットを追加でベイクする必要はない：① 屋内は太陽と空を受けない（完全ベイク、屋内用の素材、部屋独自のプローブ）。② 敷居をまたぐとき約 1 秒で露出を調整する。夜も必要。③ 扉の内側の床に淡い光だまりのテクスチャを置き、昼はオン、夜はオフ。④ 高窓は本当に閉める。UX とフロントエンドで突き合わせた（PM が 20:30Z に両者で直接話すよう依頼）：③ の光だまりの形はリアルタイムの太陽から計算する（3 節「大扉」）。固定の 1 枚ではない。フロントエンドは 20:48Z に同意：時計が更新されるたびに四角形の 4 頂点を動かし、テクスチャと素材は変えず、雨の日と夜はオフ。門口と軒の実際の高さは王城を作るときに測り、光の帯の時刻表を実際のモデルでもう一度作って UX に確認してもらう。

**#44 review** (10-10):
- Data 16:26Z: the king would get placed in the gate passage, so `king-throne` comes first and `gate-in` and `hostage-near` are marked `auto: false` (section 4). `hostage-guard` and the courtiers don't take spots. Data changed this in the M3 world model themselves (this doc doesn't need to change): beat.07 moves Melos out of the castle; otherwise he would still be in the castle when `exit.1.vigil` lands at 一日目 0:00.
- Frontend 16:20Z: routes are not written into the layout; they are recorded as a start point plus a target point (section 4).

**#44 レビュー**（10-10）：
- データ 16:26Z：王が城門の通路に配置されてしまうので、`king-throne` を一番目にし、`gate-in`、`hostage-near` を `auto: false` にした（4 節）。`hostage-guard` と群臣はスポットを占有しない。データ自身が M3 の世界モデルで直した（この文書は変更不要）：beat.07 でメロスを王城の外へ移す。そうしないと `exit.1.vigil` が一日目 0:00 に着地したとき彼がまだ城の中にいる。
- フロントエンド 16:20Z：経路はレイアウトに書かず、起点と目標点として記録する（4 節）。

## 8. Checklist for Frontend 4 (F-14) / フロントエンド 4（F-14）向けのリスト

F-14 builds the castle from this document. Order:

F-14 はこの文書に沿って王城を作る。順番：

| Order / 順番 | What / 内容 | Section / 節 |
|---|---|---|
| 1 | Throne room geometry and furnishings: columns, steps, throne, curtain, high windows and shutters, hanging lamp, braziers, wall lamps, main door; the central stone strip in the floor / 玉座の間のジオメトリと調度：柱、段、王座、垂れ幕、高窓と板戸、吊りランプ、火鉢、壁掛けランプ、大扉。床の中心軸の石の帯 | 2, 3.1 / 2、3.1 |
| 1 | Throne room · night bake (lamps and braziers baked once, flicker as a gentle overall brightness change); the roughly 1-second exposure change at the threshold switches together with the camera mode / 玉座の間・夜のベイク（灯と火鉢は 1 回ベイクし、揺らめきは全体の明るさを軽く変える）。敷居での約 1 秒の露出の切り替えはカメラのモードと一緒に切り替える | 3, 5.2 / 3、5.2 |
| 1 | Spot layout (`king-throne` first), navmesh up to the foot of the steps / スポットのレイアウト（`king-throne` が一番目）、ナビメッシュは段の足もとまで | 4, 3.1 / 4、3.1 |
| 1 | Blocking for beat.04〜07: marched in, the embrace (F-16's animation), being bound, departure / beat.04〜07 の動き：連行、抱擁（F-16 のモーション）、縛られる、出発 | 3.2 |
| 2 | Courtyard and colonnades, gate passage, courtyard · night bake (beat.07 departure and hostage night) / 中庭と柱廊、城門の通路、中庭・夜のベイク（beat.07 の出発と人質の夜） | 2, 5.1 / 2、5.1 |
| 2 | The hostage's pose schedule, crouching to talk in the colonnade / 人質の姿勢の予定表、柱廊でしゃがんで話す | 3.2 |
| 3 | Courtyard · 三日目 evening (wall shadow sweeping the courtyard, climbing the main door, last ray on the tower top); courtyard daytime and rain share one dimmed set / 中庭・三日目の夕方（壁の影が中庭を掃き、大扉を這い上がり、塔の頂に最後のひと筋の光）。中庭の昼と雨は 1 セットを暗くして共用 | 5.1 |
| 3 | The daytime light patch inside the door (shape follows the sun), high windows opening and closing at sunset and sunrise / 昼の扉の内側の光だまり（形は太陽に従う）、高窓は日没と日の出で開閉 | 3 |
| Later / のちに | Real daytime in the throne room (light shafts, dust) / 玉座の間の本当の昼（光の柱、塵） | 3, 5.1 / 3、5.1 |

**Download**: 3 baked sets, about 5 MB. On `go` from the plaza into the castle, download throne room · night first (about 2〜3 MB, under 4 seconds on 4G), the rest in the background (5.2).

**ダウンロード**：ベイク 3 セットで約 5 MB。広場から `go` で王城に入るときは、玉座の間・夜を先にダウンロードし（約 2〜3 MB、4G で 4 秒以内）、残りはバックグラウンドで落とす（5.2）。

**People**: the king ([king.md](../style-guide/characters/king.md)), Melos "Bound in the throne room" ([melos.md](../style-guide/characters/melos.md)), セリヌンティウス "Summoned" and the two stages of "Three days in the colonnade" ([selinuntius.md](../style-guide/characters/selinuntius.md)), 6 guards (2 at the main door, 2 at the steps, 2 leading Melos; the courtyard watch counted separately), about 6 courtiers ([m3-extras.md](../style-guide/characters/m3-extras.md)). Three-view drawings: [m3-views.svg](../style-guide/characters/m3-views.svg). The models are made by Frontend 5 (F-16); F-14 places them and hooks up the animations.

**人物**：王（[king.md](../style-guide/characters/king.md)）、メロス「玉座の間で縛られる」（[melos.md](../style-guide/characters/melos.md)）、セリヌンティウス「召喚される」と「柱廊での三日間」の 2 段階（[selinuntius.md](../style-guide/characters/selinuntius.md)）、警吏 6 人（大扉 2、段 2、メロスの連行 2。中庭の見張りは別）、群臣約 6 人（[m3-extras.md](../style-guide/characters/m3-extras.md)）。三面図は [m3-views.svg](../style-guide/characters/m3-views.svg)。モデルはフロントエンド 5（F-16）が作り、F-14 が配置してモーションをつなぐ。

**Acceptance checks** (portrait 390×844, mid-range phone):
1. Standing at `companion-aside`, the default indoor-mode shot shows both Melos and the king, and no column blocks either face.
2. Over-the-shoulder shot speaking to the king: the king's face in the upper third, firelight in both eyes; the king's robe, the curtain and the cushion don't read as red under the lamps, and the robe and the curtain are distinguishable.
3. Entering the main door from the bright courtyard: first a sudden darkness, then the throne is clear after about 1 second; leaving reverses it. This step happens at night too.
4. Landing at `hostage-near`: the hostage is in the default shot, not blocked by a column (ux-design 6.3: landing spots don't rely on pulling the camera in to fix things).
5. During the beat.06 embrace, the two are in the default shot from `companion-aside`, and at least one of the two faces is visible.
6. Throne room at 30 fps or more; the first lighting set on entering the castle loads in under 4 seconds on 4G.
7. Looking from `hostage-near` around 三日目 16:00, the edge of the wall shadow sweeps to just in front of the hostage (5.1).

**受け入れ確認**（縦画面 390×844、ミドルレンジ機）：
1. `companion-aside` に立つと、室内モードのデフォルトのショットにメロスと王が同時に映り、柱が二人の顔を隠さない。
2. 王に話しかける肩越しのショット：王の顔は画面の上 1/3 にあり、両目に火の光がある。王の上衣、垂れ幕、クッションは灯の下で赤に見えず、上衣と垂れ幕は見分けられる。
3. 明るい中庭から大扉に入る：まず急に暗くなり、約 1 秒後に王座がはっきり見える。外へ出るときは逆。夜もこの手順がある。
4. `hostage-near` に着地する：デフォルトのショットに人質が映り、柱に隠れない（ux-design 6.3：着地点はカメラを寄せることで補わない）。
5. beat.06 の抱擁のとき、二人は `companion-aside` のデフォルトのショットの中にいて、2 つの顔のうち少なくとも 1 つが見える。
6. 玉座の間は 30 fps 以上。王城に入ったときの最初の光のセットは 4G で 4 秒以内。
7. 三日目 16:00 前後に `hostage-near` から見ると、壁の影の縁がちょうど人質の真ん前まで来る（5.1）。


---

## Revision history / 改訂履歴

- v1.1 (2026-10-11): step 23 (U-1), for Frontend 4's F-14. Added 3.1 furnishings and dimensions (steps, throne, curtain set to deep indigo, high windows, hanging lamp, braziers, wall lamps, main door, where the guards stand, navmesh up to the foot of the steps), 3.2 staging and camera (indoor-mode camera inside, blocking for beat.04〜07, low-angle over-the-shoulder shot when speaking to the king with no reverse shot, the hostage's three-day pose table, crouching to talk in the colonnade), and the section 8 checklist and acceptance checks; 6.1 now points to the character files of style guide v1.1. Moved two spots: `companion-aside` (3.5, −4.8) → (1.0, −1.8) (the south wall was right behind it, leaving no room for the camera), `hostage-near` (−12.5, 5.5) → (−13.4, 6.6) (a front-row column used to block the hostage). plan.svg updated to match.
  v1.1（2026-10-11）：第 23 ステップ（U-1）、フロントエンド 4 の F-14 用。3.1 調度と寸法（段、王座、垂れ幕を深い藍色に決定、高窓、吊りランプ、火鉢、壁掛けランプ、大扉、警吏の立ち位置、ナビメッシュは段の足もとまで）、3.2 演出とカメラ（屋内は室内モードのカメラ、beat.04〜07 の動き、王に話しかけるときはあおりの肩越しで切り返さない、人質の 3 日間の姿勢表、柱廊でしゃがんで話す）、8 節のリストと受け入れ確認を追加。6.1 はスタイルガイド v1.1 の人物ファイルを指すようにした。スポットを 2 つ移した：`companion-aside` (3.5, −4.8) → (1.0, −1.8)（元は背後が南の壁でカメラが収まらなかった）、`hostage-near` (−12.5, 5.5) → (−13.4, 6.6)（元は前列の柱が人質を隠していた）。plan.svg も合わせて更新。
- v1.0.2 (2026-10-10): section 3 adds when the high windows open and close: open after sunset, close before sunrise, without snapping while the player is in the hall (suggested by Frontend #57).
  v1.0.2（2026-10-10）：3 節の高窓に開閉の時刻を補足：日没後に開け、日の出前に閉め、広間にいるときに一瞬で切り替えない（フロントエンド #57 の提案）。
- v1.0.1 (2026-10-10): daytime in the throne room (PM chose A, #52; players guarding the hostage can come in during the day on 一日目〜三日目): by day the curtain is drawn, the high windows shut and the lamps lit, using the night lighting set. Wrote up the approach from Frontend's #52 review: the interior ignores the sun, about 1 second of exposure adjustment at the threshold (at night too), the high windows really closed, and a light-patch texture on the floor inside the door whose shape is computed from the real-time sun (in the afternoon it grows inward from the threshold, becomes a band moving inward from about 16:55, reaches the south half of the steps around 17:45, and goes out around 18:05) (sections 0, 3, 5.1, 7).
  v1.0.1（2026-10-10）：玉座の間の昼（PM が A に決定、#52。人質を見守るプレイヤーは一日目〜三日目の昼も入れる）：昼も垂れ幕を引き、高窓を閉め、灯をともして、夜の光のセットを使う。フロントエンドの #52 レビューに沿ってやり方を書いた：屋内は太陽を受けない、敷居で約 1 秒かけて露出を調整する（夜も）、高窓は本当に閉める、扉の内側の床に光だまりのテクスチャを置き、形はリアルタイムの太陽から計算する（午後は敷居から奥へ伸び、16:55 ごろから奥へ進む光の帯になり、17:45 前後に段の南半分に届き、18:05 ごろ消える）（0 節、3 節、5.1、7 節）。
- v1.0 (2026-10-10): first version. v0.1 was reviewed by Frontend and Data, and their answers have been folded into each section. Destination names follow the world model's `ActExit.label` (Data review #43). Section 4 revised per the #44 review: `king-throne` first, `hostage-visit` added, player and staging spots marked `auto: false`, routes changed to start plus target points (`melos-led-in` moved to (−25, 0), `selinuntius-meet` added, `melos-depart` removed).
  v1.0（2026-10-10）：最初の版。v0.1 をフロントエンドとデータが確認し、回答は各節に反映済み。行き先の名前は世界モデルの `ActExit.label` に従う（データのレビュー #43）。#44 レビューに沿って 4 節を修正：`king-throne` を一番目に、`hostage-visit` を追加、プレイヤーと演出用のスポットを `auto: false` に、経路を起点と目標点に変更（`melos-led-in` を (−25, 0) へ移し、`selinuntius-meet` を追加、`melos-depart` を削除）。
