# 物語 (Monogatari) · Market research research.md / 物語 (Monogatari) · 市場調査 research.md

| Item / 項目 | Content / 内容 |
|---|---|
| Version / バージョン | v1.1 (v1.0 incorporates the PM review; v1.1 incorporates the UX review `ux/reviews/market-research-v1.0.md`) / v1.1（v1.0 で PM のレビューを反映、v1.1 で UX のレビュー `ux/reviews/market-research-v1.0.md` を反映） |
| Author / 作成者 | Market research / 市場調査 |
| Last updated / 最終更新 | 2026-10-06 |
| Basis / 根拠 | `brief/handoff.md`, `pm/prd.md` v0.4, `pm/decisions.md` (D-008〜D-016, S-001〜S-047) / `brief/handoff.md`、`pm/prd.md` v0.4、`pm/decisions.md`（D-008〜D-016、S-001〜S-047） |
| Evidence / 証拠 | [evidence/segments.md](evidence/segments.md) (user data), [evidence/competitors.md](evidence/competitors.md) (competitors; §9 is the product-by-product check of "mutual influence"), [evidence/pain-points.md](evidence/pain-points.md) (user reviews), [evidence/business-benchmarks.md](evidence/business-benchmarks.md) (prices; the rough cost estimate is for reference only) / [evidence/segments.md](evidence/segments.md)（ユーザーデータ）、[evidence/competitors.md](evidence/competitors.md)（競合。§9 は「互いの影響」の製品ごとの確認）、[evidence/pain-points.md](evidence/pain-points.md)（ユーザーの評価）、[evidence/business-benchmarks.md](evidence/business-benchmarks.md)（価格。コストの概算は参考のみ） |

Notation: every figure has a source and year (in the evidence files); "inferred" marks market research's own judgment; anything we could not find is marked "not found".

表記：数字にはすべて出典と年がある（evidence のファイル内）。「推測」は市場調査の判断。見つからなかったものは「見つからず」と書く。

## Summary / 要約

1. **Main users: Japanese adults aged 18〜34 who already enjoy "entering a story" kinds of entertainment** (AI character chat, 推し活, マダミス, リアル脱出, ノベルゲーム). "Has read 『走れメロス』" is a shared precondition for almost everyone, so it cannot be used to tell people apart. Decided by PM, confirmed by zg (S-022).
   **メインユーザー：「物語に入る」タイプの娯楽をすでに楽しんでいる 18〜34 歳の日本の成人**（AI キャラクターとのチャット、推し活、マダミス、リアル脱出、ノベルゲーム）。「『走れメロス』を読んだことがある」はほぼ全員に共通する前提なので、人を区別するのには使えない。PM が決定し、zg が確認済み（S-022）。
2. **Secondary users: middle-school students and Japanese-language teachers, in a second phase**; overseas Japanese learners are only watched. But as long as we use Gemini, this second phase cannot happen (S-060, see §1.4).
   **サブユーザー：中学生と国語の教師で、第 2 段階に回す**。海外の日本語学習者は観察のみ。ただし Gemini を使っている限り、この第 2 段階は実現できない（S-060、§1.4 参照）。
3. **The problems every product gets criticized for are "repeating, going in circles, interrogating the player" and "instability, disconnects"** (out of 10 products: 9 for repeating, 7 for instability, 5 for interrogating). PM has raised the corresponding requirements to P0 (S-023〜S-025).
   **どの製品も批判されている問題は「繰り返し、堂々巡り、プレイヤーへの質問攻め」と「不安定、切断」**（10 製品中、繰り返し 9、不安定 7、質問攻め 5）。PM は対応する要件を P0 に引き上げた（S-023〜S-025）。
4. **No single feature is unique; the combination is.** Characters that remember you, relationships that decide whether a character helps you, characters acting on their own, asking you for help, entering a classic, each character's own ending: all of these have been done (§2.2). What we did not find in public material is: **in an original everyone knows, the mutual help and promises between you and the characters are written as events in the world, checked against the original's causality, and finally land in three layers of ending compared with the original**; plus 3D + Japanese voice + mobile web. Publicly we cannot say "first" or "only".
   **単体の機能はどれも独自ではなく、独自なのは組み合わせ。** 登場人物があなたを覚えている、関係によって登場人物が助けてくれるかが変わる、登場人物が自分で行動する、あなたに助けを求める、名作の中に入る、登場人物それぞれの結末——どれもすでに誰かがやっている（§2.2）。公開資料で見つからなかったのは、**誰もが知っている原作の中で、あなたと登場人物の助け合いや約束を世界のイベントとして書き、原作の因果で検証し、最後に原作と照らし合わせた 3 層の結末にたどり着くこと**。それに 3D + 日本語の音声 + スマホ向けウェブが加わる。対外的に「初」「唯一」とは言えない。
5. **For the business model, validate "buy each book once + a free prologue" first.** Schools and municipalities are the second phase; culture, tourism and publishing partnerships happen when the other party comes to us. The first version is free (PRD §9).
   **ビジネスモデルはまず「1 冊買い切り + 無料の序章」を検証する。** 学校と自治体は第 2 段階。文化、観光、出版との提携は相手から声がかかったら行う。最初の版は無料（PRD §9）。
6. **The most uncertain thing**: whether main users from 推し活 will see 『走れメロス』 as "textbook stuff". There is no direct data; we test it during recruiting and in the R1 playtest (§1.5).
   **最も不確かなこと**：推し活をしているメインユーザーが『走れメロス』を「教科書のもの」と感じないか。直接のデータはなく、募集と R1 の試遊で測る（§1.5）。

---

## 1. Target users / 1. ターゲットユーザー

### 1.1 Conclusion / 1.1 結論

| Priority / 優先度 | Users / ユーザー | Versus the PM hypothesis / PM の仮説に対して | What it means for the first version / 最初の版にとっての意味 |
|---|---|---|---|
| **Main / メイン** | Japanese adults aged 18〜34 who already spend time or money on "entering a story and interacting with characters": AI character chat, 推し活, マダミス, リアル脱出ゲーム, ノベルゲーム / 「物語に入り、登場人物とやり取りする」ことにすでに時間やお金を使っている 18〜34 歳の日本の成人：AI キャラクターとのチャット、推し活、マダミス、リアル脱出ゲーム、ノベルゲーム | A holds, narrowed by behavior (S-022) / A は成立し、行動で絞り込む（S-022） | Japanese voice and text are equal entry points; endings must be worth sharing; target is 18 and over / 日本語の音声とテキストは対等な入口。結末はシェアする価値がなければならない。対象は 18 歳以上 |
| Secondary (second phase) / サブ（第 2 段階） | 2nd-year middle-school students and Japanese-language teachers / 中学 2 年生と国語の教師 | B holds / B は成立 | Not in the first version; do not block it architecturally (age, data minimization) / 最初の版では扱わない。アーキテクチャ上で道をふさがない（年齢、データの最小化） |
| Watch / 観察 | Overseas Japanese learners / 海外の日本語学習者 | C holds / C は成立 | Not targeted in the first version; ふりがな (P1) helps them / 最初の版では対象にしない。ふりがな（P1）は彼らの役に立つ |
| A channel, not a target / ターゲットではなくチャネル | Fans of literary greats (文スト, 文アル) / 文豪ファン（文スト、文アル） | New / 新規 | Leverage them for promotion; do not design characters to their taste / 宣伝で力を借りるが、キャラクターを彼らの好みに合わせて設計しない |

### 1.2 Why the main users are "young adults who already play with stories", not "all adults who have read it" / 1.2 メインユーザーが「読んだことのあるすべての成人」ではなく「物語で遊んでいる若い成人」である理由

1. **"Has read it" does not tell people apart.** At least 3 current middle-school Japanese textbooks (光村, 三省堂, 東京書籍) include 『走れメロス』 in the 2nd year, and a 2016 paper said every publisher included it at the time; every year about 1.03 million 2nd-year students all study this piece. It is a shared precondition for all Japanese people, which makes "you changed the story" visible at a glance, but it is not a reason for anyone to come and play.
   **「読んだことがある」では人を区別できない。** 現行の中学の国語教科書のうち少なくとも 3 社（光村、三省堂、東京書籍）が『走れメロス』を中学 2 年に収録しており、2016 年の論文によると当時はすべての出版社が収録していた。毎年約 103 万人の中学 2 年生全員がこの作品を学ぶ。日本人全体に共通する前提で、「物語をあなたが変えた」ことをひと目でわかるようにしてくれるが、誰かが遊びに来る理由にはならない。
2. **In behavior, young people are closest to us.** Generative AI use among 15〜24-year-olds is 83.1% (LINE リサーチ 2025-12); 60.2% of Gen Z users have used it for conversation or casual chat, most often as "someone to chat with when bored" (CyberAgent 2026); among 20〜69-year-olds overall it is only 38.9%, with 53% for people in their 20s (NRC 2025-09).
   **行動面で私たちに最も近いのは若者。** 15〜24 歳の生成 AI 利用率は 83.1%（LINE リサーチ 2025-12）。Z 世代の利用者の 60.2% が会話や雑談に使ったことがあり、最も多いのは「暇なときの話し相手」（CyberAgent 2026）。20〜69 歳全体では 38.9% にとどまり、20 代は 53%（NRC 2025-09）。
3. **These people already pay to "take part in stories".** One マダミス session costs ¥2,500〜8,500; リアル脱出ゲーム has had 10.9 million visits in total; 推し活 participants number about 26 million; more than 10% of people who watch c.ai's micro-dramas to episode 7 pay to keep watching.
   LINE マンガ キャラチャット's figures **cannot be used as evidence that Japanese main users pay**: "6 million cumulative users, 78% in their teens to 20s" is a global figure from before the Japan launch (as of 2026-01); "paid messages make up 52%" is data from a single chatbot in Korea; both come from an anime-store blog's retelling of a Naver Webtoon announcement, a secondary source. The Japanese version only launched in 2026-02, and there is no data on Japanese users. It only shows that "young people pay to chat with story characters" holds in Korea.
   **この人たちはすでに「物語に参加する」ことにお金を払っている。** マダミスは 1 回 ¥2,500〜8,500。リアル脱出ゲームは累計 1,090 万人が参加。推し活をしている人は約 2,600 万人。c.ai のショートドラマを第 7 話まで見た人の 10% 超がお金を払って続きを見ている。
   LINE マンガ キャラチャットの数字は**日本のメインユーザーが払う証拠には使えない**：「累計 600 万ユーザー、78% が 10〜20 代」は日本でのサービス開始前（2026-01 時点）の全世界の数字で、「有料メッセージが 52%」は韓国のあるチャットボット 1 つのデータ。どちらもアニメショップのブログが Naver Webtoon の発表を紹介したもので、二次情報。日本版は 2026-02 に始まったばかりで、日本のユーザーのデータはない。「若者が物語のキャラクターとのチャットにお金を払う」ことが韓国で成り立つことを示しているだけ。
4. **Minors are not in the first version.** Character.AI shut off open-ended chat for minors in 2025-11; the PRD's first version also has no governance for minors and no teacher panel. The first version targets 18 and over; the invite-code phase invites only adults and does not collect age (S-022, S-010); how to handle minors at public launch is to be asked of zg before launch (Q-011).
   **未成年は最初の版に入れない。** Character.AI は 2025-11 に未成年に対して自由なチャットを停止した。PRD の最初の版にも未成年向けのガバナンスや教師用パネルはない。最初の版の対象は 18 歳以上で、招待コードの段階では成人だけを招き、年齢は集めない（S-022、S-010）。公開時に未成年をどう扱うかは公開前に zg に聞く（Q-011）。
5. **"Nostalgic readers" aged 35 and up are not excluded**, but we found no evidence that they pay for this kind of experience, and their generative AI use is lower. In promotion, 「あの『走れメロス』に入れる」 works for every age, but the design is based on young adults (inferred).
   **35 歳以上の「懐かしむ読者」は除外しない**が、この種の体験にお金を払う証拠は見つからず、生成 AI の利用率も低い。宣伝の「あの『走れメロス』に入れる」はどの年齢にも効くが、設計は若い成人を基準にする（推測）。

### 1.3 When main users play (inferred) / 1.3 メインユーザーはいつ遊ぶか（推測）

- **At home, alone, with earphones, before bed or on weekends, for 15〜20 minutes.** Talking into a phone on a Japanese train is hard, and voice products are often criticized for recognition outdoors (Cotomo 「一言もちゃんと聞き取ってもらえない」).
  **自宅で、一人で、イヤホンをつけて、寝る前や週末に、15〜20 分。** 日本の電車の中でスマホに向かって話すのは難しく、音声製品は屋外での認識についてよく批判される（Cotomo「一言もちゃんと聞き取ってもらえない」）。
- So text input and voice are equal entry points, and the game can also be played with text while commuting. PM has adopted this (S-022, S-025). Questions 4 and 5 of the playtest screening questionnaire test this inference.
  そのためテキスト入力と音声は対等な入口で、通勤中もテキストで遊べる。PM が採用済み（S-022、S-025）。試遊のスクリーニングアンケートの第 4・5 問でこの推測を検証する。
- "Before bed, in bed" has two more implications (UX review 1-1):
  「寝る前、ベッドで」にはさらに 2 つの意味がある（UX レビュー 1-1）：
  - **Players will speak quietly.** Whether quiet Japanese can be recognized accurately has not been tested by anyone yet. Backend and frontend have been asked to add "recognition rate for quiet speech (about 40dB)" to the voice validation; UX observes in R1 how loudly players actually speak.
    **プレイヤーは小声で話す。** 小声の日本語を正しく聞き取れるかは、まだ誰もテストしていない。バックエンドとフロントエンドに、音声の検証に「小声（約 40dB）での認識率」を加えるよう依頼した。UX は R1 でプレイヤーが実際にどれくらいの声で話すかを観察する。
  - **A full screen of paper color is glaring with the lights off.** UX v1.0 adds a night color scheme that follows the system's dark mode.
    **電気を消した後、画面いっぱいの紙の色はまぶしい。** UX v1.0 でシステムのダークモードに合わせた夜間の配色を加える。

### 1.4 Basis for the secondary and watched users / 1.4 サブユーザーと観察対象ユーザーの根拠

- **Middle-school students and teachers**: large and stable (3.105 million middle-school students, about 1.03 million per grade), with 90.4% using phones to go online. But this market has to wait: the digital textbooks the state provides free cover only English and arithmetic/mathematics, not 国語; digital textbooks only become official in fiscal 2030; procurement is per municipal board of education on annual budgets; the price benchmark is ¥880〜1,760/person/year. It also needs governance for minors and a teacher panel (Q-005). It suits a second-phase version that "teachers can try for free directly in class" to acquire users (inferred).
  **Limitation (S-060)**: Google's terms do not allow Gemini in services aimed at people under 18 or likely to be accessed by people under 18 (Service Specific Terms §20(d); PM has checked the original text). So as long as we use Gemini this market is closed to us, unless we change model provider or negotiate separate terms with Google. Recruiting and promotion also cannot target students.
  **中学生と教師**：規模が大きく安定している（中学生 310.5 万人、1 学年約 103 万人）、スマホでのネット利用率は 90.4%。ただしこの市場は待つ必要がある：国が無償で提供するデジタル教科書は英語と算数・数学だけで、国語は含まれない。デジタル教科書が正式な教科書になるのは 2030 年度。調達は市町村の教育委員会単位で年度予算による。価格の基準は ¥880〜1,760/人/年。さらに未成年向けのガバナンスと教師用パネルが必要（Q-005）。第 2 段階で「教師が授業でそのまま無料で試せる」版を作ってユーザーを獲得するのに向いている（推測）。
  **制限（S-060）**：Google の規約では、18 歳未満を対象とする、または 18 歳未満が利用する可能性が高いサービスで Gemini を使うことは認められていない（Service Specific Terms §20(d)、PM が原文を確認済み）。そのため Gemini を使っている限りこの市場には参入できない。モデルの提供元を変えるか、Google と別途条件を交渉する場合は別。募集と宣伝も学生を対象にできない。
- **Overseas Japanese learners**: 4 million learners in institutions (国際交流基金 2024), 17 million+ Japanese learners on Duolingo, 26% of whom learn "just for fun". But most are beginners, and Dazai's original text and free voice conversation are a high bar; they would need difficulty levels, slow speech and furigana. c.ai Books and Whispers from the Star both unexpectedly attracted users who "practice a foreign language through stories", which suggests the need exists (inferred); re-evaluate after the second book.
  **海外の日本語学習者**：教育機関の学習者は 400 万人（国際交流基金 2024）、Duolingo の日本語学習者は 1,700 万人以上で、26% が「just for fun」。ただし大半は初級で、太宰の原文と自由な音声会話はハードルが高く、難易度別、ゆっくりした話し方、ふりがなが必要。c.ai Books と Whispers from the Star では、どちらも思いがけず「物語で外国語を練習する」ユーザーが現れており、需要はあることを示している（推測）。2 冊目以降に改めて評価する。
- **Fans of literary greats**: 文スト has sold 12 million copies in total, 文アル has 1.6 million registrations. But what they follow is the moe-styled authors themselves; メロス and the king are not their 推し (inferred). They suit being a promotion channel.
  **文豪ファン**：文ストは累計 1,200 万部、文アルは登録 160 万。ただし彼らが追っているのは萌えキャラ化された文豪本人で、メロスや王は彼らの推しではない（推測）。宣伝のチャネルに向いている。

### 1.5 What we are least sure about / 1.5 最も不確かなこと

**Main users love characters and their 推し. For them, 『走れメロス』 may carry the impression of "textbook stuff, a preachy story", and they may not want to play it.** This is the biggest risk in the main-user conclusion, and there is no direct data yet.

**メインユーザーが愛しているのはキャラクターと推し。彼らにとって『走れメロス』は「教科書のもの、説教くさい話」という印象があり、遊びたいと思わないかもしれない。** これはメインユーザーの結論で最大のリスクで、今のところ直接のデータはない。

- **Signs pointing the other way** (all indirect evidence, inferred):
  **逆の方向を示す兆候**（いずれも間接的な証拠、推測）：
  - 車で走れメロス (a free browser game, 2026-09-10) got about 7,000 likes, showing this IP can spread as a "meme".
    車で走れメロス（2026-09-10 の無料ブラウザゲーム）は約 7,000 いいねを集めており、この IP が「ネタ」として広まりうることを示している。
  - It ranked 2nd in Aozora Bunko's 2022 XHTML access ranking (253,431 views), showing people still seek it out to read.
    青空文庫の 2022 年の XHTML アクセスランキングで 2 位（253,431 回）で、今も自分から読みに行く人がいることを示している。
  - But neither shows that "people into 推し活 are willing to spend 20 minutes on it".
    ただしどちらも「推し活をしている人がこれに 20 分使う」ことを示してはいない。
- **How to test it** (playtest-plan.md Q9):
  **どう測るか**（playtest-plan.md Q9）：
  - The recruiting post does not name the book; screening question 7 first asks 「好きな物語なら遊びたいか」, then 「『走れメロス』なら遊びたいか」, and the difference between the two shows whether the title itself adds or subtracts.
    募集の投稿には書名を書かない。スクリーニング第 7 問でまず「好きな物語なら遊びたいか」、次に「『走れメロス』なら遊びたいか」を聞き、2 問の差で書名そのものが加点か減点かを見る。
  - In R1, ask for the reason aloud before play; after play, ask 「作品の印象は変わったか」.
    R1 ではプレイ前に口頭で理由を聞き、プレイ後に「作品の印象は変わったか」を聞く。
- **Reduce the risk in the design first** (UX review 1-3, owned by UX): the cover and identity pages talk about the experience and the characters first, not about the work; no 「原作では…」 explanations within the first 3 minutes, leaving comparison with the original for players to discover in the map and the ending; the first character speaks first, pulling people in with an emotional line rather than narration explaining the background. The R1 observation adds the code LESSON (the moment 「教科書っぽい」 or 「授業みたい」 comes up), to see directly which screen gave people the feeling of being in class.
  **設計の面でまずリスクを下げる**（UX レビュー 1-3、UX が担当）：表紙と身分のページでは作品紹介ではなく体験と登場人物を先に語る。開始 3 分以内に「原作では…」という説明を出さず、原作との比較は地図と結末でプレイヤー自身が見るように残す。最初の登場人物が先に口を開き、背景を説明するナレーションではなく感情のこもった一言で引き込む。R1 の観察にコード LESSON（「教科書っぽい」「授業みたい」が出た瞬間）を加え、どの画面で授業のような印象を持たれたかを直接見る。
- **If it turns out to subtract** (inferred, to be decided after R1): promotion leads with the experience (入る, 話す, 約束する, 変える) and puts the title later; put the characters' appeal up front (セリヌンティウス's friendship, the king's loneliness); also keep this in mind when choosing the second book.
  **減点要因だとわかった場合**（推測、R1 の結果を見て決める）：宣伝は体験（入る、話す、約束する、変える）を先に語り、書名は後ろに回す。登場人物の魅力を前に出す（セリヌンティウスの友情、王の孤独）。2 冊目を選ぶときもこの点を考慮する。

---

## 2. Gaps in similar products: problems everyone gets criticized for / 2. 類似製品の欠点：どこも批判されている問題

### 2.1 Eight things the first version must get right / 2.1 最初の版で必ずうまくやるべき 8 つのこと

Based on user reviews of 10 products (Character.AI, AI Dungeon, Whispers from the Star, Vaudeville, Suck Up!, Talkie, Cotomo, AIのべりすと, Duolingo Max, Speak); the matrix and verbatim quotes are in [evidence/pain-points.md](evidence/pain-points.md).

10 製品（Character.AI、AI Dungeon、Whispers from the Star、Vaudeville、Suck Up!、Talkie、Cotomo、AIのべりすと、Duolingo Max、Speak）のユーザーの評価に基づく。マトリクスと原文の引用は [evidence/pain-points.md](evidence/pain-points.md) にある。

| # | Pain point / 問題点 | Products criticized / 批判された製品 | What the first version must do / 最初の版でやるべきこと | How PRD v0.4 handles it / PRD v0.4 での扱い |
|---|---|---|---|---|
| 1 | **Repeating, going in circles, interrogating the player** (Character.AI's "Can I ask you a question?", Cotomo 「質問攻めにされるってこんなに苦痛」, Speak "almost every sentence ends with a question") / **繰り返し、堂々巡り、プレイヤーへの質問攻め**（Character.AI の「Can I ask you a question?」、Cotomo「質問攻めにされるってこんなに苦痛」、Speak「ほぼすべての文が質問で終わる」） | Repeating: 9; interrogating: 5 / 繰り返し 9、質問攻め 5 | Characters have their own goals and push things forward; no repeated question within one game; limit the share of characters' questions to the player / 登場人物には自分の目標があり、自分から話を進める。1 局の中で同じ質問を繰り返さない。登場人物がプレイヤーに質問する比率を制限する | P0 (S-023); characters asking the player for help is the main source of "pushing forward" and does not count as interrogation (S-029 ⑥) / P0（S-023）。登場人物がプレイヤーに助けを求めるのは「自分から話を進める」主な源で、質問攻めには数えない（S-029 ⑥） |
| 2 | **Instability: disconnects, queues, crashes** (WftS 10-hour queues, c.ai voice disconnecting every 3〜5 minutes) / **不安定：切断、待ち行列、クラッシュ**（WftS の 10 時間待ち、c.ai の音声が 3〜5 分ごとに切断） | 7 of 10 / 10 製品中 7 | After a disconnect, return to the same game at the same moment; on model timeouts, use pre-written lines or an in-story waiting set piece; no queues / 切断後は同じ局の同じ瞬間に戻る。モデルのタイムアウト時は事前に書いた台詞か物語内の待機演出を使う。待ち行列を作らない | Save and resume raised to P0 (S-024) / セーブと再開を P0 に引き上げ（S-024） |
| 3 | **Forgetting; memory split between voice and text** (WftS "in the video she has no idea what you're talking about", Cotomo 「好感度も記憶も積み重ならない」) / **忘れる、音声とテキストで記憶が分断される**（WftS「動画の中の彼女はこちらが何の話をしているのかまったくわかっていない」、Cotomo「好感度も記憶も積み重ならない」） | All text-chat products / テキストチャット系すべて | Structured memory, with voice and text reading the same store; the 記憶帳 lets players see what characters remember / 構造化された記憶で、音声とテキストが同じものを読む。記憶帳でプレイヤーに登場人物が何を覚えているかを見せる | 記憶帳 P0; voice and text share memory (S-025) / 記憶帳は P0。音声とテキストで記憶を共有（S-025） |
| 4 | **Consequences failing in both directions**: too linear (WftS "she has a preprogrammed path") or too free (Vaudeville "everything is a lie/hallucination") / **結果の失敗は 2 方向**：直線的すぎる（WftS「she has a preprogrammed path」）か、自由すぎる（Vaudeville「everything is a lie/hallucination」） | AI Dungeon, WftS, Vaudeville / AI Dungeon、WftS、Vaudeville | Anchors + causal constraints; within the first 3 minutes, one moment where "the world reacts to me"; 「なぜこうなった？」 / 錨 + 因果の制約。開始 3 分以内に一度「世界が自分に反応した」瞬間がある。「なぜこうなった？」 | Covered. After zg asked for more freedom and per-game endings (D-013, D-014), the eval bar for "makes sense" is not lowered (S-030 ⑤, S-031 ④) / 対応済み。zg が自由度を上げ、結末を局ごとに生成するよう求めた（D-013、D-014）後も、「筋が通る」の評価の基準は下げない（S-030 ⑤、S-031 ④） |
| 5 | **Poor speech recognition, latency, no room for 「間」** (WftS "sick of repeating myself", Cotomo 「一瞬黙ると…どうしたの を連呼」) / **音声認識が悪い、遅延、「間」を与えない**（WftS「sick of repeating myself」、Cotomo「一瞬黙ると…どうしたの を連呼」） | All voice products / すべての音声製品 | Show the recognized text in real time with one-tap correction; recognition biasing for proper nouns; do not rush the player when silent; cover latency with 相槌; text and voice are equal entry points / 認識した文字をリアルタイムに表示し、ワンタップで訂正できる。固有名詞の認識バイアス。プレイヤーが黙っても急かさない。相槌で遅延を隠す。テキストと音声は対等な入口 | P0 (S-025); feasibility of one-tap correction awaits voice validation S-1 / P0（S-025）。ワンタップ訂正の実現性は音声検証 S-1 待ち |
| 6 | **Guardrails breaking immersion** (WftS "The guardrails really ruin the experience", c.ai blocking even holding hands) / **ガードレールで没入が途切れる**（WftS「The guardrails really ruin the experience」、c.ai は手をつなぐことさえブロック） | Character.AI, AI Dungeon, WftS / Character.AI、AI Dungeon、WftS | Refusals happen inside the story, blocked by characters and circumstances, with no system pop-ups / 拒否は物語の中で起こし、登場人物や状況が止める。システムのメッセージは出さない | Covered (PRD §6.3) / 対応済み（PRD §6.3） |
| 7 | **Voice data and privacy** (WftS requires giving up all rights to voice content; AI Dungeon scans private stories) / **音声データとプライバシー**（WftS は音声内容のすべての権利の放棄を求める、AI Dungeon は非公開の物語をスキャンする） | AI Dungeon, WftS / AI Dungeon、WftS | Before microphone permission, say in one sentence how recordings are handled and how long they are kept; characters do not ask about private real-life matters / マイクの許可の前に、録音をどう扱い、どれくらい保存するかを一文で伝える。登場人物は現実の私的なことを聞かない | P0 (S-025); wording awaits backend confirming the model-side terms / P0（S-025）。文言はバックエンドがモデル側の規約を確認するのを待つ |
| 8 | **Payment interrupting the story** (c.ai waiting room, Talkie energy system, AI Dungeon credits) / **課金が物語を中断する**（c.ai の待合室、Talkie のエネルギー制、AI Dungeon のポイント） | 4 products / 4 製品 | Even when we charge later, never charge in the middle of a game; state the price once, clearly / 今後課金するとしても 1 局の途中では課金しない。価格は一度ではっきり伝える | Written into PRD §9 / PRD §9 に記載 |

### 2.2 Our differences, ranked honestly / 2.2 私たちの差異、実情に沿って並べる

The product-by-product check is in [evidence/competitors.md](evidence/competitors.md) §1 and §9 (2026-10-06).

製品ごとの確認は [evidence/competitors.md](evidence/competitors.md) §1 と §9（2026-10-06）にある。

| Difference / 差異 | Unique? / 独自か | Basis / 根拠 |
|---|---|---|
| **Causal changes of course that make sense**: the story really changes course, but keeps the original's logic; 「なぜこうなった？」 shows the chain and the source in the original / **筋の通った因果による進路変更**：物語は本当に進路を変えるが、原作の論理は守る。「なぜこうなった？」で連鎖と原作の出典が見える | **Unique** (inferred) / **独自**（推測） | c.ai Books has only Book Arc (follows the original's main plot) and Go Off Script (free RP); Hidden Door uses licensed or public-domain worlds, but a design review says its world state is weak and chapter goals resolve automatically; Voyage has a World Engine, but the world is built by the player / c.ai Books には Book Arc（原作の本筋に沿う）と Go Off Script（自由な RP）しかない。Hidden Door はライセンスやパブリックドメインの世界を使うが、デザインのレビューでは世界状態が弱く、章の目標が自動で解決されると指摘されている。Voyage には World Engine があるが、世界はプレイヤーが自分で作る |
| **You and the characters influence each other**: relationships are shaped by what happens; when the relationship is strong enough, characters do things for you (possibly when you are not there); characters ask you for help; promises have "in progress / kept / broken" (D-012, S-029, S-030) / **あなたと登場人物が互いに影響し合う**：関係は起きた出来事で決まる。関係が十分になれば登場人物はあなたのために動く（あなたがその場にいないときも）。登場人物があなたに助けを求める。約束には「進行中 / 守った / 破った」がある（D-012、S-029、S-030） | **No single part is unique; we found no such combination within an original work's framework** / **単体ではどれも独自ではなく、原作の枠組みの中での組み合わせは見つからなかった** | Voyage's NPCs act on their own motives, hold grudges, switch sides, track relationships, and the world goes on after the player logs off; in Where Winds Meet, AI NPCs become "old friends" after you help them, give gifts and help fight bosses; Justice Mobile's AI NPCs remember you, and the pre-launch introduction mentioned "repaying kindness by taking a blade for you"; NPCs in Mantella (a Skyrim mod) can be persuaded to become followers; PageSpeak (a Japanese app) lets you chat with characters from books, and relationships change. None of them place mutual help inside the causality of a classic, and none have promises with state or endings compared with the original / Voyage の NPC は自分の動機で動き、恨みを覚え、陣営を変え、関係を追跡し、プレイヤーがログアウトした後も世界は続く。燕雲十六声の AI NPC は助けた後に「旧友」になり、贈り物をしたりボス戦を手伝ったりする。逆水寒のモバイル版の AI NPC はあなたを覚えており、リリース前の紹介には「恩返しに刃を受け止める」があった。Mantella（Skyrim の mod）の NPC は説得して仲間にできる。PageSpeak（日本のアプリ）では本の登場人物とチャットでき、関係が変化する。いずれも助け合いを名作の因果の中に置いておらず、状態を持つ約束も原作と比べる結末もない |
| **Three layers of ending**: the world's ending (generated per game, 5 types as baselines, S-031, S-034), each character's ending (「原作では…／あなたの世界では…」, S-032), your own ending / **3 層の結末**：世界の結末（局ごとに生成、5 種類は最低ライン、S-031、S-034）、各登場人物の結末（「原作では…／あなたの世界では…」、S-032）、あなた自身の結末 | **Character endings themselves are not unique; we found no AI-generated, per-game character endings compared with the original** / **登場人物の結末そのものは独自ではない。AI が局ごとに生成し、原作と比べる登場人物の結末は見つからなかった** | Companions' individual endings are a mature design in hand-written games (the ending slides of Dragon Age and Fallout: New Vegas, loyalty deciding life or death in Mass Effect 2); the public material of AI narrative products (c.ai Books, Hidden Door, Voyage) has no personal endings or character endings / 仲間それぞれの結末は手作りのゲームで成熟した設計（Dragon Age や Fallout: New Vegas のエンディングのスライド、Mass Effect 2 では忠誠が生死を決める）。AI ナラティブ製品（c.ai Books、Hidden Door、Voyage）の公開資料には、個人の結末も登場人物の結末もない |
| A walkable 3D world + Japanese voice + mobile web / 歩き回れる 3D 世界 + 日本語の音声 + スマホ向けウェブ | **Unique as a combination** / **組み合わせとして独自** | c.ai Books, Hidden Door and Voyage are text; voice AI games are on PC or apps and English only; Cotomo and SynClub have Japanese voice but no narrative from an original work / c.ai Books、Hidden Door、Voyage はテキスト。音声 AI ゲームは PC かアプリで英語のみ。Cotomo と SynClub には日本語の音声があるが原作の物語はない |
| Entering a classic / 名作の中に入る | **Not unique** / **独自ではない** | c.ai Books (20+ public-domain classics), Hidden Door (Oz, Pride and Prejudice, etc.) / c.ai Books（パブリックドメインの名作 20 冊以上）、Hidden Door（オズ、高慢と偏見など） |
| Characters remember you / 登場人物があなたを覚えている | **Not unique** / **独自ではない** | Voyage has cross-session memory; c.ai has Story Memory, Facts and Lorebook; our first version only remembers within one game (S-012) / Voyage はセッションをまたいで記憶する。c.ai には Story Memory、Facts、Lorebook がある。私たちの最初の版は 1 局の中でしか覚えていない（S-012） |
| Japanese literature / 日本文学 | Not unique / 独自ではない | Humanitext Aozora (calls itself 「近代日本文学の研究ツール」; at launch you could text-chat with literary greats or characters from their works); 車で走れメロス; PageSpeak / Humanitext Aozora（「近代日本文学の研究ツール」を名乗り、公開時に文豪や作品の登場人物とテキストで会話できた）、車で走れメロス、PageSpeak |

**Implications / 意味**:

1. **Do not say "first" or "only" publicly.** "AI characters that remember you, act for you and ask you for help" and "stepping into a classic with AI" have both been done. Internally we can write "as far as we know, as of 2026-10, no public product does all of... at once"; c.ai Books' internal mechanics are not public, and Voyage and c.ai could add these at any time, so **check again before launch**.
   **対外的に「初」「唯一」と言わない。** 「AI のキャラクターがあなたを覚え、あなたのために動き、助けを求める」も「AI で名作の中に入る」もすでに誰かがやっている。内部の判断としては「私たちの知る限り、2026-10 時点で……を同時に実現した公開製品はない」と書いてよい。c.ai Books の内部の仕組みは公開されておらず、Voyage と c.ai はいつでも追いつく可能性があるので、**公開前にもう一度調べる**。
2. **The headline claim is still "makes sense"**, and the second is "mutual influence". Do not tell mutual influence as a generic "AI characters help you", but as this book's own theme: 『走れメロス』 is precisely about trust and promises. The promises between you and the characters are remembered, and keeping or breaking them changes the story and their endings. What others cannot do is this echo of the original (inferred).
   **一番の主張は引き続き「筋が通る」**で、2 番目が「互いの影響」。互いの影響を漠然とした「AI のキャラクターが手伝ってくれる」として語らず、この本自身のテーマとして語る：『走れメロス』はまさに信頼と約束の物語。あなたと登場人物の約束は覚えられ、守るか破るかで物語と彼らの結末が変わる。他社にできないのは、この原作との響き合い（推測）。
3. **How to talk publicly about "unlimited possibilities" (D-014)**: endings are not picked from a list but generated from what you did in this game. We can say that, but not numbers like 「無限」 or 「何万通り」 until the ending-diversity eval (S-031 ⑤) produces numbers. Wording is in positioning.md §4.
   **「無限の可能性」（D-014）を対外的にどう言うか**：結末はリストから選ぶのではなく、あなたがこの局でしたことから生まれる。そう言うのはよいが、「無限」「何万通り」のような数字は、結末の多様性の評価（S-031 ⑤）で数字が出るまで言わない。言い方は positioning.md §4 にある。
4. **Free alternatives already exist, and the same IP has just gone viral.** The free prologue must make people feel on the spot that "this is different from the others" (inferred).
   **無料の代替手段はすでにあり、同じ IP が最近話題になったばかり。** 無料の序章でその場で「これは他と違う」と感じてもらわなければならない（推測）。

---

## 3. Business model options (at most three) / 3. ビジネスモデルの選択肢（最大 3 つ）

The first version is free (PRD §9). The three options below are for deciding where to go later and what hooks the first version needs to leave in place. Price anchors and sources are in [evidence/business-benchmarks.md](evidence/business-benchmarks.md).

最初の版は無料（PRD §9）。以下の 3 つは、今後どの方向に進むか、最初の版にどんな接点を残しておくかを決めるためのもの。価格の基準と出典は [evidence/business-benchmarks.md](evidence/business-benchmarks.md) にある。

**Per-game cost uses only the backend and data engineering figures / 1 局あたりのコストはバックエンドとデータエンジニアリングの数字だけを使う** (S-058; the "update" at the end of data-design.md §10, backend-design §8. All are estimates, to be replaced by backend S-5 measurements from simulated games / S-058、data-design.md §10 末尾の「更新」、backend-design §8。すべて推計で、バックエンドの S-5 でシミュレーションの局を実測して置き換える):

- With D-012〜D-015 and the UX additions: a 20-minute game costs about ¥198, 30 minutes about ¥271, the stress tier about ¥399. The largest addition is world progression (about ¥37).
  D-012〜D-015 と UX の追加分を加えると：20 分の局で約 ¥198、30 分で約 ¥271、負荷の高いケースで約 ¥399。最大の追加分は世界の進行（約 ¥37）。
- Fixed monthly costs are separate: database about $10〜50, load balancer about $18.
  固定の月額は別：データベース約 $10〜50、ロードバランサー約 $18。
- The per-game cap of ¥300 (S-019) is not changed for now. 30-minute games will go into the economy tier (from ¥240). After the S-5 measurements, choose one of three: "raise the cap to ¥350 / accept that long games go into the economy tier / reduce world progression" (Q-B8).
  1 局の上限 ¥300（S-019）はいったん変えない。30 分の局は節約モード（¥240 から）に入る。S-5 の実測後、「上限を ¥350 に上げる / 長い局が節約モードに入ることを受け入れる / 世界の進行を減らす」の 3 つから選ぶ（Q-B8）。

| | A. Buy each book once + free prologue (**validate first, recommended**) / A. 1 冊買い切り + 無料の序章（**まず検証することを推奨**） | B. Schools and municipalities (second phase; **not possible while using Gemini**, S-060) / B. 学校と自治体（第 2 段階。**Gemini を使っている間は不可**、S-060） | C. Culture, tourism and publishing partnerships (only when someone approaches us) / C. 文化、観光、出版との提携（声がかかったら行う） |
|---|---|---|---|
| Who pays / 誰が払うか | The main users themselves / メインユーザー本人 | Municipal boards of education (procuring "per person × year"), or school fees (paid by parents) / 市町村の教育委員会（「人 × 年」で調達）、または学校徴収金（保護者が払う） | Municipal tourism, literary museums, publishers / 自治体の観光部門、文学館、出版社 |
| Why they pay / なぜ払うか | A complete story experience that belongs only to them, which they can replay as another identity for a different ending / 自分だけの完結した物語体験で、身分を変えて遊び直せば別の結末になる | All 2nd-year middle-school students study 『走れメロス』; there is no free state-provided digital material for 国語; digital textbooks become official in 2030 / 中学 2 年生全員が『走れメロス』を学ぶ。国語には国が無償で提供するデジタル教材がない。2030 年にデジタル教科書が正式化 | The "add a new book" pipeline is itself a sellable capability: on the data side one short story takes about 3〜4 person-days (data engineering's estimate based on the actual メロス work); 3D scenes, voice and art are separate and are the main workload (UX gives a rough estimate in art-direction v1.0 §9; frontend estimates separately) / 「新しい本を追加する」パイプラインそのものが売れる能力：データ側では短編 1 本で約 3〜4 人日（データエンジニアリングがメロスの実績から見積もり）。3D の場面、声、アートは別で、こちらが主な作業量（UX が art-direction v1.0 §9 で概算を出し、フロントエンドは別途見積もる） |
| Price anchors / 価格の基準 | A single ノベルゲーム ¥990〜7,480; one マダミス session ¥2,500〜8,500; c.ai+ $9.99/month; the 『走れメロス』 e-book ¥110 / ノベルゲーム 1 本 ¥990〜7,480、マダミス 1 回 ¥2,500〜8,500、c.ai+ $9.99/月、『走れメロス』の電子書籍 ¥110 | ロイロノート about ¥216/person/year; student digital textbooks ¥880〜1,760/person/year; スタディサプリ (paid by parents) ¥6,160/year / ロイロノート約 ¥216/人/年、学習者用デジタル教科書 ¥880〜1,760/人/年、スタディサプリ（保護者が払う）¥6,160/年 | 箕面市's AR cultural tour commission capped at about ¥19.88 million (デジ田交付金); palan AR from ¥35,000/month; HarperCollins pays $5,000 per book for AI licensing / 箕面市の AR 文化周遊の委託上限は約 ¥1,988 万（デジ田交付金）。palan AR は ¥35,000/月から。HarperCollins は AI 向けのライセンスに 1 冊 $5,000 |
| Cost constraint (inferred) / コストの制約（推測） | One paying user playing 3 games costs about ¥590 (at ¥198/game); selling at ¥980 gives about 40% gross margin, at ¥1,480 about 60% (both before payment fees and fixed monthly costs). So the lower bound of the price assumption, ¥980, is tight; if Van Westendorp shows we can only sell at ¥980, we have to cut costs (the levers in S-058). A free full game would lose money, so **the free part can only be a prologue**: up to the end of act 1 (3〜6 minutes on UX's timing table, about ¥50/person, estimated as a quarter of a game), and it also needs a total cap / 有料ユーザー 1 人が 3 局遊ぶと約 ¥590（1 局 ¥198 として）。¥980 で売ると粗利は約 40%、¥1,480 なら約 60%（いずれも決済手数料と固定の月額は未控除）。つまり価格仮説の下限 ¥980 は厳しく、Van Westendorp の結果が ¥980 でしか売れないと出たら、コスト削減（S-058 の手段）に頼る必要がある。無料で 1 局全部遊ばせると赤字になるので、**無料部分は序章だけ**：第一幕の終わりまで（UX の所要時間表で 3〜6 分、1 局の 4 分の 1 として 1 人約 ¥50）、さらに総量の上限も必要 | One student playing 2〜3 games a year costs about ¥400〜590, close to the ¥880 price benchmark, so margins are very thin / 生徒 1 人が年に 2〜3 局遊ぶと約 ¥400〜590 で、¥880 の価格基準に近く、粗利はごく薄い | Charged per project, so costs can be built into the quote / プロジェクト単位で料金を取るので、コストを見積もりに含められる |
| Strength of evidence / 証拠の強さ | Medium: willingness to pay has anchors (マダミス, people paying to keep watching c.ai micro-dramas), but no direct precedent for "buying a single AI narrative outright" / 中：支払い意欲には基準がある（マダミス、c.ai のショートドラマにお金を払って続きを見る）が、「AI ナラティブを 1 冊買い切り」の直接の前例はない | Medium: price and procurement path are clear; long cycles, needs governance for minors and a teacher panel / 中：価格と調達の経路は明確。期間が長く、未成年向けのガバナンスと教師用パネルが必要 | Weak: no cases found of literary museums paying for interactive experiences; copyrighted works need licensing (集英社 asked for a compensation mechanism in 2025-10) / 弱：文学館がインタラクティブな体験にお金を払った例は見つからなかった。著作権のある作品にはライセンスが必要（集英社は 2025-10 に補償の仕組みを求めた） |
| What the first version should leave in place / 最初の版に残しておくもの | Per-game cost is computable (already in PRD §7.4); saving the ending-card image (S-026, the main acquisition channel); **cut the prologue at a narrative end point, not by time** (S-052): at the close of act 1, before the first end-of-act choice, give a small 「約束の日」 ending card that tells the player 「物語はここから三日間続く」; the shepherd boy has no act 1, so his cut point is set separately. Never stop a game midway to ask for money (§2.1 item 8) / 1 局ごとのコストを計算できる（PRD §7.4 にある）。結末カードの画像の保存（S-026、主な獲得チャネル）。**序章は時間ではなく物語の区切りで切る**（S-052）：第一幕の締めくくり、最初の幕末の選択の前に、小さな「約束の日」の結末カードを出し、「物語はここから三日間続く」と伝える。牧童には第一幕がないので、切る位置は別に決める。1 局の途中で止めてお金を求めない（§2.1 第 8 項） | Age confirmation; no personal information collected; data can be aggregated per class (for a later teacher panel) / 年齢確認。個人情報を集めない。データをクラス単位で集計できる（今後の教師用パネルのため） | The world-model extraction pipeline is designed around "add a new book" (already in PRD §9) / 世界モデルの抽出パイプラインは「新しい本を追加する」前提で設計する（PRD §9 にある） |

**Recommendations / 推奨**:

1. The first version is free; real-person playtest R2 tests price with the four Van Westendorp questions (playtest-plan.md §6.2). The price assumption is ¥980〜1,480/book (inferred, to be tested).
   最初の版は無料にし、実際の人による試遊 R2 で Van Westendorp の 4 問を使って価格を測る（playtest-plan.md §6.2）。価格仮説は ¥980〜1,480/冊（推測、要検証）。
2. Consider subscriptions only once there are 3 or more books (Audible Japan ¥1,500/month is the anchor).
   サブスクリプションは本が 3 冊以上になってから検討する（Audible 日本の ¥1,500/月が基準）。
3. Cost is the key to whether A can work. Data engineering has already worked out the two biggest savings: open voice sessions per character in segments (cuts to about a third), and skip narrator extraction on small-talk turns (data-design §10). "The Live API re-bills the cumulative context on every turn" ([official forum 2026-07-07 / 公式フォーラム 2026-07-07](https://discuss.ai.google.dev/t/does-gemini-live-native-audio-bill-cumulative-prompt-tokens-on-every-turn-cost-seems-to-scale-with-turn-count-not-call-duration/173248)) is already included in their model.
   A が成り立つかどうかの鍵はコスト。最大の節約ポイント 2 つはデータエンジニアリングがすでに計算している：音声は登場人物ごとに区切ってセッションを開く（約 3 分の 1 に削減）、雑談のターンではナレーターによる抽出を行わない（data-design §10）。「Live API はターンごとに累積したコンテキストを課金し直す」（[公式フォーラム 2026-07-07](https://discuss.ai.google.dev/t/does-gemini-live-native-audio-bill-cumulative-prompt-tokens-on-every-turn-cost-seems-to-scale-with-turn-count-not-call-duration/173248)）もすでに彼らのモデルに含まれている。

---

## 4. Feedback on the PRD scope: status / 4. PRD のスコープへの意見：対応状況

The detailed PRD review is in [reviews/prd-v0.1.md](reviews/prd-v0.1.md); PM adopted all of it (PRD v0.3, v0.4).

PRD の詳しいレビューは [reviews/prd-v0.1.md](reviews/prd-v0.1.md) にあり、PM がすべて採用した（PRD v0.3、v0.4）。

| Feedback / 意見 | Status / 対応 |
|---|---|
| Raise save and resume to P0 / セーブと再開を P0 に引き上げる | S-024 |
| Characters push things forward, no interrogating, no repeating / 登場人物が自分から話を進め、質問攻めや繰り返しをしない | S-023 |
| Recognition results visible and editable in real time, no rushing silence, voice data explanation / 認識結果をリアルタイムに表示・訂正できる、沈黙を急かさない、音声データの説明 | S-025 |
| First version targets 18 and over / 最初の版の対象は 18 歳以上 | S-022; handling at public launch in Q-011 / S-022。公開時の扱いは Q-011 |
| Add one line "how it differs from the original" to the ending card / 結末カードに「原作との違い」を 1 行加える | S-026 |
| Immersion measured by between-group comparison, scoring and behavioral metrics / 没入感は群間比較、採点、行動指標で測る | S-027 |
| Three rules for character endings (1〜3 sentences each, compared with the original, those untouched written as 「原作どおり」) / 登場人物の結末の 3 つのルール（1 人 1〜3 文、原作と比較、関わらなかった人物は「原作どおり」と書く） | S-032 |

Still open, to follow up later:

まだ決まっておらず、後で追いかけること：

1. Whether 『走れメロス』 appeals to main users (§1.5), handed to PM after R1.
   『走れメロス』がメインユーザーにとって魅力があるか（§1.5）。R1 の後に PM に渡す。
2. Before launch, check again whether competitors (Voyage, c.ai Books) have added "constraints from the original + mutual help + character endings" (§2.2 implication 1).
   公開前に、競合（Voyage、c.ai Books）が「原作による制約 + 助け合い + 登場人物の結末」を追加していないかもう一度調べる（§2.2 意味 1）。

## 5. Positioning / 5. 位置づけ

The one-page positioning, the comparison with c.ai Books and the product name candidates are in [positioning.md](positioning.md); the real-person playtest plan is in [playtest-plan.md](playtest-plan.md). Key points: the category is 「物語に入る体験」, and we do not call ourselves AI チャット, ゲーム or 教材; the headline claim is 「知っている物語に入って、筋の通った形で変える」, the second is 「信頼と約束：あなたと彼らは互いに動かし合う」, and the third is the three layers of ending (S-028).

1 ページの位置づけ、c.ai Books との比較、製品名の候補は [positioning.md](positioning.md)、実際の人による試遊計画は [playtest-plan.md](playtest-plan.md) にある。要点：カテゴリーは「物語に入る体験」で、AI チャット、ゲーム、教材とは名乗らない。一番の主張は「知っている物語に入って、筋の通った形で変える」、2 番目は「信頼と約束：あなたと彼らは互いに動かし合う」、3 番目は 3 層の結末（S-028）。

## Revision history / 改訂履歴

- v1.1 addendum (2026-10-06): per S-060, summary item 2, §1.4 and §3 B state "the student market is not possible while using Gemini"; §3 cost updated per S-058 (about ¥198 per game), and the margins for A and B recomputed.
  v1.1 追補（2026-10-06）：S-060 に従い、要約の第 2 項、§1.4、§3 B に「Gemini を使っている間は学生市場に参入できない」と明記。§3 のコストを S-058 に従って更新（1 局約 ¥198）し、A と B の粗利を計算し直した。
- v1.1 (2026-10-06): changes per the UX review: §1.3 adds quiet speech and the night color scheme; §1.5 adds UX's design countermeasures; §3 A cuts the free prologue at a narrative end point (S-052); world-ending baselines changed to 5 types (S-034).
  v1.1（2026-10-06）：UX のレビューに従って変更：§1.3 に小声と夜間の配色を追加。§1.5 に UX の設計上の対策を追加。§3 A の無料の序章は物語の区切りで切る（S-052）。世界の結末の最低ラインを 5 種類に変更（S-034）。
- v1.0 (2026-10-06): changes per the PM review and D-012〜D-015, S-029〜S-032:
  v1.0（2026-10-06）：PM のレビューと D-012〜D-015、S-029〜S-032 に従って変更：
  - Added §1.5 "what we are least sure about".
    §1.5「最も不確かなこと」を追加。
  - §1.2 item 3 states that the LINE キャラチャット data is not from Japan.
    §1.2 第 3 項に LINE キャラチャットのデータは日本のものではないと明記。
  - §2.1 changed to how PRD v0.4 handles each item.
    §2.1 を PRD v0.4 での扱いに変更。
  - §2.2 rewritten, based on the product-by-product check, on whether "mutual influence" and "three layers of ending" are unique, with implications for public messaging.
    §2.2 を製品ごとの確認に基づいて書き直し、「互いの影響」と「3 層の結末」が独自かどうかを見直し、対外的な言い方への意味を追加。
  - §3 cost cites only backend and data (my rough estimate moved to evidence as a reference); C adds the workload for adding a new book.
    §3 のコストはバックエンドとデータの数字だけを引用（私の概算は参考として evidence に移した）。C に新しい本を追加する作業量を追加。
  - §4 changed to status.
    §4 を対応状況に変更。
- v0.2 (2026-10-06): per zg's direction, differences and positioning add "two-way relationships" and "three layers of ending" (§2.2, summary item 4).
  v0.2（2026-10-06）：zg の方向性に従い、差異と位置づけに「双方向の関係」と「3 層の結末」を追加（§2.2、要約の第 4 項）。
- v0.1 (2026-10-06): first draft. §1〜§3 were written first for PM to use in writing the PRD.
  v0.1（2026-10-06）：初稿。§1〜§3 は PM が PRD を書くためにまず書いた。
