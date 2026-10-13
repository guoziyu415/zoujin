# A-0 art pipeline pilot: acceptance criteria (UX) / A-0 アートパイプライン・パイロット：受け入れ基準（UX）

| Item / 項目 | Content / 内容 |
|---|---|
| Written by / 作成者 | UX, 2026-10-10 / UX、2026-10-10 |
| Card / 対応するカード | A-0 (`pm/dev-plan.md` section 4). Frontend writes the card; UX sets the criteria and does the acceptance check / A-0（`pm/dev-plan.md` 第 4 節）。カードはフロントエンドが書き、基準と受け入れ確認は UX が担当 |
| Basis / 根拠 | `ux/art-direction.md` v1.1: section 5 characters, section 9 two-tier specs, section 10 checkpoint 3, section 11 step 3; the budget in `frontend/frontend-design.md` 10.6.2; `ux/ux-design.md` 6.3 dialogue camera, 7.4 dialogue states, 16.2 pre-recorded lines / `ux/art-direction.md` v1.1：第 5 節 登場人物、第 9 節 2 ティアの仕様、第 10 節 チェックポイント 3、第 11 節 第 3 ステップ。`frontend/frontend-design.md` 10.6.2 の予算。`ux/ux-design.md` 6.3 会話カメラ、7.4 会話の状態、16.2 事前収録セリフ |

## 0. What A-0 has to answer / A-0 が答えるべきこと

Can a free pipeline (the MPFB base model is CC0, plus scripts) produce a **realistic character that does not break immersion in an iPhone dialogue camera**, fit within the budget, and how much work does it take?

無料のパイプライン（MPFB のベースモデルは CC0、それにスクリプト）で、**iPhone の会話カメラで没入感を損なわないリアルな登場人物**を作り、予算内に収められるか。そしてどれだけの手間がかかるか。

There are only three possible conclusions (section 7): pass, pass after fixes, or the free pipeline cannot do it (PM brings screenshots and numbers to zg, dev-plan Z-12).

結論は 3 通りしかない（第 7 節）：合格、修正後に合格、無料パイプラインでは無理（PM がスクリーンショットと数値を持って zg に相談する。dev-plan Z-12）。

## 1. What the frontend hands to UX / フロントエンドが UX に渡すもの

1. **Three glTF files**, each with its download size noted:
   **glTF 3 つ**。それぞれダウンロードサイズを書く：
   - Dialogue version, high-end (40k faces);
     会話版・ハイエンド（4 万面）。
   - Dialogue version, tier B (20k–30k faces);
     会話版・ティア B（2〜3 万面）。
   - Walking version (8k faces).
     歩行版（8k 面）。
2. **A test page**, built on S7's plaza, that can switch the following:
   **テストページ 1 つ**。S7 の広場をベースに、次のものを切り替えられる：
   - Camera: the dialogue camera (two-person over-the-shoulder, ux-design 6.3, with Melos as the person facing the camera), and the exploration camera (characters 40–80 px tall).
     カメラ：会話カメラ（2 人の肩越し、ux-design 6.3。メロスは向かい側の人物）と、探索カメラ（人物の高さ 40〜80px）。
   - Time of day: 17:30 (first screen, the plaza in shadow), true noon 真昼 (the hardest top light, where a plastic look shows most easily), and 18:50 日没 backlight (the silhouette for key moments, art-direction 5.3).
     時刻：17:30（最初の画面。広場は日陰）、真昼（真上からの光がいちばん硬く、プラスチック感がいちばん出やすい）、18:50 日没の逆光（重要な場面のシルエット、art-direction 5.3）。
   - Tier: force tier B / force high-end, switchable back and forth within the same shot.
     ティア：ティア B 強制 / ハイエンド強制。同じショットの中で行き来して切り替えられる。
   - Motion: dialogue idle (breathing, blinking, gaze, very small weight shifts), and running (walking version, exploration camera). Running is Melos's signature, and "weight in motion" is the first priority for realism (5.1).
     動作：会話の待機（呼吸、瞬き、視線、ごく小さな重心移動）と、走り（歩行版、探索カメラ）。走りはメロスの象徴であり、「動作の重量感」はリアルさの最優先事項でもある（5.1）。
   - Speech: play 3 lines in a Japanese male voice, with the character's mouth following. The three are: a short aizuchi (相槌, ≤ 0.5 s), a line of about 3 s, and a line of 8 s or more with pauses. The voice uses lines recorded with the Melos candidate voice from S-1 casting (on zg's Mac); if those are unavailable, use any Japanese male voice sample and note it.
     発話：日本語の男性の声で 3 つのセリフを再生し、人物の口が合わせて動く。3 つは、短い相槌（≤ 0.5 秒）、約 3 秒のもの、間を含む 8 秒以上のもの。声は S-1 のキャスティングでメロス候補の声で録ったセリフを使う（zg の Mac にある）。手に入らない場合は任意の日本語男性の声のサンプルを使い、その旨を明記する。
3. **Screen recordings on zg's iPhone** (portrait): one clip per time of day for each of the two tiers, each 20 seconds or longer, including both speaking and not speaking.
   **zg の iPhone での画面収録**（縦向き）：3 つの時刻 × 2 ティアで各 1 本、それぞれ 20 秒以上。話しているときと話していないときの両方を含める。
4. **Numbers**:
   **数値**：
   - Frame time: with 2 dialogue-version characters on screen in the dialogue camera (tier B) and 4 (high-end), measure `gpuMs` using S7's stress method;
     フレーム時間：会話カメラで会話版の人物を同時に 2 体（ティア B）、4 体（ハイエンド）表示し、S7 の負荷方式で `gpuMs` を測る。
   - Hours spent on each step: modeling, decimation, rigging, animation, lip-sync, export; which steps need hand-tuning in the Blender UI on the Mac;
     各ステップにかかった時間：モデリング、減面、リギング、アニメーション、口パク、エクスポート。どのステップが Mac の Blender の画面での手作業を必要とするか。
   - The source and license of every asset used (base model, textures, animations).
     使ったすべての素材（ベースモデル、テクスチャ、アニメーション）の出典とライセンス。

## 2. Hard requirements to pass first (if these fail, the face is not reviewed) / 先に通すべき必須指標（これを通らなければ顔は見ない）

| Item / 項目 | Tier B / ティア B | High-end / ハイエンド | Basis / 根拠 |
|---|---|---|---|
| Face count / 面数 | 20k–30k / 2〜3 万 | ≤ 40k / ≤ 4 万 | art-direction 9.2 |
| Materials / マテリアル | 4–5 (skin, eyes, hair cards, clothes, teeth) / 4〜5 個（肌、目、髪カード、衣服、歯） | Same as left / 左に同じ | 9.2 |
| Textures / テクスチャ | All 1024 / すべて 1024 | Skin (including the face) color map and normal map 2048, the rest 1024 / 肌（顔を含む）のカラーマップと法線マップは 2048、その他は 1024 | 9.2 |
| Expressions / 表情 | 52 ARKit blend shapes; lip-sync follows the frontend's approach (see section 3, item 4) / ARKit の表情モーフ 52 個。口パクはフロントエンドの方式に従う（第 3 節第 4 項を参照） | Same as left / 左に同じ | frontend 10.6.2 |
| Download / ダウンロード | ≤ 4 MB | ≤ 6.5 MB | frontend 10.6.2 |
| Walking version / 歩行版 | 8k faces, ≤ 2 materials, one 1024 texture, ≤ 60 bones, ≤ 0.5 MB / 8k 面、マテリアル ≤ 2、1024 テクスチャ 1 枚、ボーン ≤ 60、≤ 0.5 MB | Same as left / 左に同じ | frontend 10.6.2 |
| Frame time / フレーム時間 | Plaza + 2 dialogue-version characters on screen; one frame's GPU time extrapolated to iPhone 12 (× 3.4) ≤ 25 ms, i.e. about ≤ 7.3 ms on zg's phone [extrapolated] / 広場 + 会話版 2 体を同時表示し、1 フレームの GPU 時間を iPhone 12 に換算（× 3.4）して ≤ 25 ms、つまり zg のスマートフォンで約 ≤ 7.3 ms〔推算〕 | Plaza + 4 dialogue-version characters on screen; one frame's GPU time on zg's phone ≤ 12 ms / 広場 + 会話版 4 体を同時表示し、zg のスマートフォンで 1 フレームの GPU 時間 ≤ 12 ms | The L1 and L2 starting-tier conditions in frontend-design 10.6.3, consistent with A-0.md / frontend-design 10.6.3 の L1、L2 開始ティアの条件。A-0.md と一致 |
| License / ライセンス | Every asset can be used commercially, with its source clearly recorded / すべての素材が商用利用可能で、出典をきちんと記録する | Same as left / 左に同じ | — |

## 3. What to look at in close-up (in the priority order of art-direction 5.1) / 接写で見るもの（art-direction 5.1 の優先順位どおり）

Look at the dialogue camera on zg's iPhone. For each item, look at tier B first, then high-end.

zg の iPhone で会話カメラを見る。各項目とも、まずティア B、次にハイエンドを見る。

| # | What to look at / 見るもの | What counts as a pass / 合格の基準 |
|---|---|---|
| 1 | **Proportions and silhouette** (5.1, 5.4) / **プロポーションと輪郭**（5.1、5.4） | 7–7.5 heads tall, no enlarged head or eyes. Lean and long, body leaning forward, bare arms; a wool short tunic (exomis) baring one shoulder, in ochre and undyed wool colors, leather sandals, short hair. In the exploration camera, with the character painted solid black so only the silhouette shows, he is still recognizable as Melos and distinct from the old man (hunched, with a cane) and the traveler (wide-brimmed hat) / 7〜7.5 頭身で、頭と目を大きくしない。細長い体つきで前傾し、腕はむき出し。片方の肩を出す羊毛の短衣エクソミスで、色は黄土色と未染色の羊毛の色、革のサンダル、短髪。探索カメラで人物を真っ黒に塗りシルエットだけを見ても、メロスだと分かり、老爺（猫背、杖）や旅人（つばの広い帽子）と見分けがつく |
| 2 | **Weight in motion** (5.1 item 1) / **動作の重量感**（5.1 第 1 項） | Running: body leaning forward, the center of gravity rises and falls, feet do not slide on landing. Dialogue idle: breathing and very small weight shifts, neither completely still nor swaying back and forth / 走り：体が前傾し、重心に上下動があり、着地で足が滑らない。会話の待機：呼吸とごく小さな重心移動があり、完全に静止してもおらず、左右に揺れ続けてもいない |
| 3 | **Eyes** (5.1 item 2) / **目**（5.1 第 2 項） | A blink every 3–6 seconds at irregular intervals. Gaze is on the player while speaking and listening; when turning, the eyes arrive first and the head follows. The catchlight in the eyes is visible on tier B too. No "dead stare": the gaze makes very small movements every second or two / 3〜6 秒ごとに瞬きし、間隔は不規則。話すときも聞くときも視線はプレイヤーに向く。振り向くときは目が先に、頭が後から動く。目のハイライトはティア B でも見える。「目が据わる」状態にならない：視線が 1〜2 秒ごとにごく小さく動く |
| 4 | **Lip-sync** (5.1 item 3) / **口パク**（5.1 第 3 項） | The mouth moves when there is sound and closes when there is none. The mouth lags the voice by no more than about 90 ms (the acceptable range in ITU-R BT.1359; people start to notice beyond about 45 ms, so shorter is better). Teeth are visible when the mouth opens; the inside of the mouth is not a black hole and does not shine. The frontend's first version opens and closes by volume (frontend-design 7.3): A-0 has to answer whether, on a face about 2 cm tall, opening and closing alone looks like a puppet. If it does, write it down; M2 adds mouth shapes for 「あいうえお」 estimated from the voice spectrum. This does not block A-0 / 声があるときに動き、ないときは閉じる。口の動きの声に対する遅れは約 90 ミリ秒以内（ITU-R BT.1359 の許容範囲。約 45 ミリ秒を超えると気づく人が出始めるので、短いほどよい）。口を開けたときに歯が見え、口の中が黒い穴にならず、光りもしない。フロントエンドの初版は音量で開閉する（frontend-design 7.3）。A-0 が答えるべきは、高さ約 2 cm の顔で開閉だけだと操り人形のように見えるかどうか。そう見えるなら記録し、M2 で声のスペクトルから「あいうえお」の口の形を推定する方式を追加する。A-0 の妨げにはしない |
| 5 | **Brows** (5.1 item 4) / **眉**（5.1 第 4 項） | Flat, furrowed and raised can all be made, switching smoothly without jumps. Which one it is can be told apart on tier B too / 平ら、ひそめる、上げるの 3 種類がすべて作れ、切り替えが滑らかで跳ばない。ティア B でもどれなのか見分けられる |
| 6 | **Cloth** (5.1 item 5) / **布**（5.1 第 5 項） | In idle and while running, clothes do not pass into the body; folds come from the normal map / 待機中も走っているときも、衣服が体にめり込まない。しわは法線マップで表現する |
| 7 | **Skin** (5.1 item 6) / **肌**（5.1 第 6 項） | A sun-tanned herdsman with healthy color. Under the true-noon top light it does not look like plastic: not greasy-shiny and not gray. In backlight, the edges of the ears and nostrils may show a little translucent red (an approximation of subsurface scattering; nice to have). No pores or vellus hair / 日焼けした羊飼いで、血色がある。真昼の真上からの光の下でプラスチックのように見えない：テカテカせず、くすみもしない。逆光では耳と小鼻の縁が少し赤く透けてもよい（サブサーフェスの近似。あればよい）。毛穴や産毛は作らない |
| 8 | **Hair** (5.1 item 7) / **髪**（5.1 第 7 項） | Short hair; hair-card edges do not flicker when turning the head on tier B / 短髪。ティア B で振り向いたときに髪カードの縁がちらつかない |
| 9 | **Overall: uncanny valley** (checkpoint 3) / **全体：不気味の谷**（チェックポイント 3） | Watch the whole recording: is there any moment that feels off — a dead stare, a mouth that does not move, plastic-looking skin, a face more realistic than the motion? The face's realism must not exceed the motion's realism (5.1); when the two do not match, make the face simpler / 録画を通して見て、違和感を覚える瞬間がないか：目が据わる、口が動かない、肌がプラスチックのよう、顔が動作よりリアル。顔のリアルさが動作のリアルさを超えてはならない（5.1）。両者が合わないときは、むしろ顔をシンプルにする |

At **all three times of day**, the following must all hold:

**3 つの時刻**すべてで、次のことが成り立つこと：

- 17:30 in shadow: the face is not gray and not dead black; the dark areas carry the blue of skylight (art-direction section 7).
  17:30 の日陰：顔がくすまず、真っ黒にもならず、暗部に天空光の青みがある（art-direction 第 7 節）。
- True noon 真昼: item 7's "does not look like plastic" is mainly checked here.
  真昼：第 7 項の「プラスチックのように見えない」は主にここで見る。
- 18:50 backlight: the silhouette and pose are clearly readable; the face is in shadow but not a black hole. This is the image used for key moments (5.3).
  18:50 の逆光：輪郭と姿勢がはっきり分かる。顔は影の中だが、黒い穴ではない。これは重要な場面で使う画面である（5.3）。

## 4. Comparing the two tiers (art-direction 9.5, 9.6) / 2 ティアの比較（art-direction 9.5、9.6）

- Same shot, tier B and high-end screenshots side by side: high-end should only be "clearer" and must not add anything. The average color difference over the facial skin area is ΔE ≤ 2 (almost invisible).
  同じショットでティア B とハイエンドのスクリーンショットを並べる：ハイエンドは「より鮮明」なだけで、何かが増えてはならない。顔の肌領域の平均色差は ΔE ≤ 2（ほぼ見分けがつかない）。
- On tier B it is still readable where the gaze points, that the character is blinking, which brow type it is, and that the mouth is opening and closing.
  ティア B でも、視線がどこを向いているか、瞬きしていること、眉がどの種類か、口が開閉していることが読み取れる。
- A tier upgrade happens at the moment of a camera cut: colors do not jump.
  ティアの昇格はカメラ切り替えの瞬間に起こり、色が跳ばない。
- Switching between the walking version and the dialogue version (the camera cut when entering or leaving a conversation): skin tone, clothing color and silhouette are consistent, so you cannot tell the model was swapped.
  歩行版と会話版の切り替え（会話の出入りのカメラ切り替え）：肌の色、衣服の色、輪郭が一致し、モデルが入れ替わったと分からない。

## 5. Not part of A-0 / A-0 に含まれないもの

- Act 4's torn-clothes and scraped version, the short-sword prop, and dedicated motions such as clenching a fist (5.6): made later during batch production.
  第四幕の破れた衣服と擦り傷のバージョン、短剣の小道具、拳を握るなどの専用の動作（5.6）：量産のときに作る。
- All 52 blend shapes must exist, but A-0 only checks the ones used above (blink, gaze, the three brow types, lip-sync).
  表情モーフ 52 個はすべて必要だが、A-0 の受け入れ確認は上で使うもの（瞬き、視線、眉 3 種類、口パク）だけ。
- The crowd (5.5) and other characters.
  群衆（5.5）とその他の登場人物。

## 6. Who reviews and how it is recorded / 誰が見て、どう記録するか

1. UX first looks at the frontend's recordings, screenshots and numbers and writes them up in `ux/reviews/a0-melos.md`, checking item by item against sections 2–4.
   UX がまずフロントエンドの録画、スクリーンショット、数値を見て `ux/reviews/a0-melos.md` に書き、第 2〜4 節と 1 項目ずつ照らし合わせる。
2. Once UX considers it a pass, PM asks zg to look at checkpoint 3 on the iPhone (art-direction section 10, item 3). zg's opinion takes priority.
   UX が合格と判断したら、PM が zg に iPhone でチェックポイント 3（art-direction 第 10 節第 3 項）を見てもらう。zg の意見が優先される。
3. Without an iPhone 12, tier B is viewed on zg's phone with tier B forced, and frame time is extrapolated using S7's conversion, marked [extrapolated].
   iPhone 12 がない場合、ティア B は zg のスマートフォンでティア B を強制して見て、フレーム時間は S7 の換算で推算し、〔推算〕と記す。

## 7. Conclusion / 結論

| Conclusion / 結論 | When / 条件 | Next step / 次のステップ |
|---|---|---|
| Pass / 合格 | Section 2 passes in full; section 3 items 1–4 and 9 all pass; the rest have at most minor issues / 第 2 節がすべて合格。第 3 節の第 1〜4、9 項がすべて合格。その他は小さな問題がある程度 | Batch-produce the slice's characters with this pipeline: the old man and the player traveler (art-direction section 11, step 4) / このパイプラインでスライスの登場人物を量産する：老爺、プレイヤーの旅人（art-direction 第 11 節第 4 ステップ） |
| Pass after fixes / 修正後に合格 | There are problems, but it is clear what to fix / 問題はあるが、どこを直すか言える | Frontend fixes, UX reviews again, at most two rounds / フロントエンドが直し、UX が再確認する。最大 2 ラウンド |
| The free pipeline cannot do it / 無料パイプラインでは無理 | After two rounds, items 3, 4, 7 or 9 of section 3 still fail, or the work is so large that 7 characters cannot be finished / 2 ラウンド後も第 3 節の第 3、4、7、9 項のどれかが不合格、または手間が多すぎて 7 人の登場人物を作り終えられない | PM brings the recordings, numbers and hours per step to zg: whether to spend money on purchased assets or outsourcing (dev-plan Z-12) / PM が録画、数値、ステップごとの工数を持って zg に相談する：素材の購入や外注にお金をかけるかどうか（dev-plan Z-12） |

The hours item is for PM's estimate: the slice needs 3 characters (Melos, the old man, the traveler), and the first version has 7 talkable characters plus 3 player roles.

工数の項目は PM の見積もり用：スライスには 3 人の登場人物（メロス、老爺、旅人）が必要で、初版は会話できる登場人物 7 人とプレイヤーの身分 3 つ。
