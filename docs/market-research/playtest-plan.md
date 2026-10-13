# 物語 (Monogatari) · Real-person playtest plan (recruiting and questionnaires) / 物語 (Monogatari) · 実際の人による試遊計画（募集とアンケート）

| Item / 項目 | Content / 内容 |
|---|---|
| Version / バージョン | v1.1 (v1.0 incorporates the PM review; v1.1 incorporates the UX review `ux/reviews/market-research-v1.0.md`) / v1.1（v1.0 で PM のレビューを反映、v1.1 で UX のレビュー `ux/reviews/market-research-v1.0.md` を反映） |
| Author / 作成者 | Market research / 市場調査 |
| Last updated / 最終更新 | 2026-10-11 |
| Corresponds to / 対応 | PRD v0.4 §7.5 (player understanding), §8 (success metrics); decisions S-020, S-022, S-026, S-027, S-029〜S-035, S-043, S-048, S-050, S-052, S-053, S-069, S-072, S-074, D-012〜D-015; research.md §1 (target users), §3 (price test); positioning.md §6 (evidence the positioning needs) / PRD v0.4 §7.5（プレイヤーの理解）、§8（成功指標）；decisions S-020、S-022、S-026、S-027、S-029〜S-035、S-043、S-048、S-050、S-052、S-053、S-069、S-072、S-074、D-012〜D-015；research.md §1（ターゲットユーザー）、§3（価格テスト）；positioning.md §6（位置づけに必要な証拠） |

## 1. Questions to answer, and which decisions they help whom make / 1. 答えるべき問いと、それが誰のどの判断に役立つか

| # | Question / 問い | Metric / 指標 | Round / ラウンド | Helps whom decide what / 誰の何の判断に使うか |
|---|---|---|---|---|
| Q1 | Can a first-time player reach the ending on their own? / 初めて遊ぶ人が自力で結末までたどり着けるか？ | R1: share who reach the slice ending in the slice without help; R2: share who finish a full game without help (PRD target ≥80%). A single moderator intervention counts as "with help" (S-027) / R1：スライスで助けなしにスライスの結末までたどり着いた割合。R2：助けなしに 1 局を遊び終えた割合（PRD の目標 ≥80%）。進行役が 1 回でも介入したら「助けあり」とする（S-027） | R1, R2 / R1、R2 | UX: whether guidance and the UI need to change; PM: whether M4 passes / UX：誘導と画面を変える必要があるか。PM：M4 を通過できるか |
| Q2 | Do players know which of their actions caused the ending? / プレイヤーは結末が自分のどの行動によるものかわかっているか？ | Attribution hit rate (PRD target ≥70%) / 原因特定の的中率（PRD の目標 ≥70%） | R1, R2 / R1、R2 | Backend, UX: whether the chain reaction and 「なぜこうなった？」 are clear enough / バックエンド、UX：連鎖反応と「なぜこうなった？」が十分わかりやすいか |
| Q3 | Is playing one game more engaging than reading the original? / 1 局遊ぶことは原文を読むより没入できるか？ | Effect size of the between-group difference in TS-SF / TS-SF の群間差の効果量 | R2 | Marketing: whether we can claim "more engaging" publicly; the first piece of evidence for a later education positioning / マーケティング：「より没入できる」と対外的に言えるか。将来の教育向け位置づけの最初の証拠 |
| Q4 | Is the ending worth sharing, and do people want to play again? / 結末はシェアする価値があるか、もう一度遊びたいか？ | Share who save or send the ending-card image on the spot (S-026; share links are not open in the first version's invite-code phase); share who switch identity and start another game on the spot (behavior) / その場で結末カードの画像を保存または送信した割合（S-026、共有リンクは最初の版の招待コード期間には開放しない）。その場で身分を変えてもう 1 局始めた割合（行動） | R2 | Marketing: whether sharing can be the main acquisition channel; UX: ending-card design / マーケティング：シェアを主な獲得チャネルにできるか。UX：結末カードのデザイン |
| Q5 | Is voice easy to use? Do players feel interrogated or repeated at? Do characters seem to have their own ideas? / 音声は使いやすいか？質問攻めにされたり、同じことを繰り返されたりしないか？登場人物は自分の考えを持っているように見えるか？ | Share of voice vs text, number of recognition corrections; 1〜7 ratings for feeling 「質問攻め」 and 「自分の考えで動いている」 / 音声とテキストの使用比率、認識の訂正回数。「質問攻め」感と「自分の考えで動いている」感の 1〜7 評価 | R1, R2 / R1、R2 | Backend, frontend: the voice pipeline; PM: whether S-023 and S-025 were achieved / バックエンド、フロントエンド：音声の経路。PM：S-023、S-025 を達成できたか |
| Q6 | How much are people willing to pay? / いくらなら払うか？ | The four Van Westendorp questions / Van Westendorp の 4 問 | R2 | The price assumption of business model A (¥980〜1,480, to be tested) / ビジネスモデル A の価格仮説（¥980〜1,480、要検証） |
| Q7 | How do players describe it to friends? / プレイヤーは友人にどう説明するか？ | Open question, compared against the positioning claims / 自由記述で、位置づけの主張と照らし合わせる | R1, R2 / R1、R2 | Marketing: whether the positioning and slogan need to change / マーケティング：位置づけとキャッチコピーを変える必要があるか |
| Q8 | Do players feel the "mutual influence"? / プレイヤーは「互いに影響し合う」ことを感じたか？ | Share who can name one thing a character did for them and one thing they did for a character (PRD target ≥70%, D-012, S-029) / 登場人物が自分のためにしてくれたことを 1 つ、自分が登場人物のためにしたことを 1 つ言える割合（PRD の目標 ≥70%、D-012、S-029） | R1, R2 / R1、R2 | UX, data: whether mutual help and promises are visible; marketing: whether "mutual influence" can be the headline claim / UX、データ：助け合いと約束が見えるか。マーケティング：「互いに影響し合う」を一番の主張にできるか |
| Q9 | Are the main users interested in 『走れメロス』 itself? (research.md §1.5 "the most uncertain thing") / メインユーザーは『走れメロス』そのものに興味があるか？（research.md §1.5「最も不確かなこと」） | The difference between the two parts of screening question 7 (「好きな物語なら」 vs 「『走れメロス』なら」); whether the impression changes after playing / スクリーニング第 7 問の 2 つの小問の差（「好きな物語なら」vs「『走れメロス』なら」）。遊んだ後に印象が変わったか | At recruiting, R1, R2 / 募集時、R1、R2 | Marketing, PM: whether the main-user conclusion needs to change; how prominently メロス is featured in promotion / マーケティング、PM：メインユーザーの結論を変える必要があるか。宣伝でメロスをどこまで前面に出すか |

Division of work: **market research** handles recruiting, questionnaires, the controlled experiment and analysis; **UX** handles moderation, observation notes and collecting usability issues; **data engineering** provides event logs (attribution scoring, mutual-help scoring, behavioral metrics); **PM** uses the results to judge whether PRD §7.5 is met.

分担：**市場調査**は募集、アンケート、対照実験、分析を担当する。**UX** は進行、観察記録、ユーザビリティの問題の整理を担当する。**データエンジニアリング**はイベントログ（原因特定の採点、助け合いの採点、行動指標）を提供する。**PM** は結果を使って PRD §7.5 を満たしたかを判定する。

## 2. Two rounds of playtests / 2. 2 ラウンドの試遊

| Round / ラウンド | Timing / 時期 | Participants / 人数 | What they play / 何を遊ぶか | What we do / 何をするか |
|---|---|---|---|---|
| R1 qualitative / R1 定性 | After the M2 vertical slice is done / M2 の垂直スライス完成後 | 6〜8 people / 6〜8 人 | The slice: S1 square + traveler + 町の老爺 and メロス (S-050), with the full pipeline and a slice ending, not a full game / スライス：S1 広場 + 旅人 + 町の老爺とメロス（S-050）。経路一式とスライスの結末があり、1 局全体ではない | Observation + a short end-of-act question + retrospective think-aloud + a short interview (§4). The aim is to find problems, not to draw statistical conclusions. Looks only at Q1 (slice version), Q2, Q5, Q7, Q8 and Q9; **"15〜20 minutes", "play again as another identity", "share rate", "price" and "TS-SF" are all left for R2** / 観察 + 幕末の短い質問 + 振り返り式の思考発話 + 短いインタビュー（§4）。目的は問題を見つけることで、統計的な結論は出さない。Q1（スライス版）、Q2、Q5、Q7、Q8、Q9 だけを見る。**「15〜20 分」「身分を変えて再プレイ」「シェア率」「価格」「TS-SF」はすべて R2 に回す** |
| R2 qualitative + quantitative / R2 定性 + 定量 | M4 (after the first version is done) / M4（最初の版の完成後） | Observation group 8〜12 people; controlled experiment ≥30 per group / 観察グループ 8〜12 人、対照実験は各グループ ≥30 人 | A full game / 1 局全体 | The observation group works as in R1, with identity chosen freely; the controlled experiment compares TS-SF between groups per §5 and also collects behavior, mutual-help and price data. **The observation group's TS-SF is not pooled with group B of the controlled experiment**: the observation group was interrupted by end-of-act questions while playing, so its scores would be lower / 観察グループは R1 と同じで、身分は自由に選ぶ。対照実験は §5 に従って TS-SF を群間比較し、行動、助け合い、価格のデータも集める。**観察グループの TS-SF は対照実験の B グループと合算しない**：観察グループはプレイ中に幕末の質問で中断されたので、スコアが低めに出る |

**Basis for sample size**: by the usual power calculation (α=.05 two-sided, power .8), reliably detecting a medium difference (d=0.5) needs about 64 per group; 30 per group can detect a difference of about d=0.73. R2 starts with ≥30 per group and reports effect sizes and 95% confidence intervals. If the result is near the threshold, top up to 64 per group. For the qualitative part, 5〜8 people are usually enough to see the main problems (knowledge.md §4.2, §6.2).

**サンプルサイズの根拠**：一般的な検出力計算（α=.05 両側、検出力 .8）では、中程度の差（d=0.5）を確実に検出するには各グループ約 64 人が必要。各グループ 30 人なら約 d=0.73 の差を検出できる。R2 はまず各グループ ≥30 人で行い、効果量と 95% 信頼区間を報告する。結果が境界付近なら各グループ 64 人まで追加する。定性の部分は通常 5〜8 人で主な問題が見える（knowledge.md §4.2、§6.2）。

## 3. Recruiting / 3. 募集

### 3.1 Who to recruit / 3.1 誰を募集するか

| Quota / 割り当て | Criteria / 条件 | R1 | R2 observation / R2 観察 | R2 controlled experiment (per group) / R2 対照実験（各グループ） |
|---|---|---|---|---|
| Main users / メインユーザー | Ages 18〜34, and in the past 3 months did at least one of: chatted with AI characters, played マダミス or リアル脱出ゲーム, played ノベルゲーム or interactive fiction, 推し活 / 18〜34 歳で、過去 3 か月に次のうち少なくとも 1 つをした：AI キャラクターとの会話、マダミスやリアル脱出ゲーム、ノベルゲームやインタラクティブフィクション、推し活 | 5〜6 | 6〜8 | ≥22 |
| Comparison / 対照 | Age 35 or older, or did none of the above in the past 3 months / 35 歳以上、または過去 3 か月に上記のどれもしていない | 1〜2 | 2〜4 | ≥8 |

**Exclusions**: team members and their families; people who have seen or played this product; under 18 (S-022; the first version targets 18 and over).

**除外**：チームメンバーとその家族。本製品を見たり遊んだりしたことがある人。18 歳未満（S-022、最初の版の対象は 18 歳以上）。

In the controlled experiment, participants are randomly assigned to A (read the original) and B (play one game), stratified by quota, so the two groups have the same quota proportions.

対照実験では割り当てごとに層化して A（原文を読む）と B（1 局遊ぶ）にランダムに割り付け、両グループの割り当て比率をそろえる。

### 3.2 Screening questionnaire (Japanese) / 3.2 スクリーニングアンケート（日本語）

The recruiting post says only 「日本の名作文学を題材にした、新しい物語体験のテスト」 and **does not name the book**, so that the people who sign up are not only メロス fans and question 7 can actually measure the pull of the title itself (Q9).

募集の投稿には「日本の名作文学を題材にした、新しい物語体験のテスト」とだけ書き、**書名は書かない**。こうすれば応募者がメロスのファンだけにならず、第 7 問で書名そのものの魅力を測れる（Q9）。

```
1. 年齢を教えてください。　□18歳未満（終了） □18〜24 □25〜34 □35〜44 □45以上
2. 『走れメロス』を読んだことがありますか。　□ある □ない □覚えていない
3. 最近3か月で、次のうち当てはまるものをすべて選んでください。
   □AIのキャラクターと会話した（Character.AI、Cotomo、キャラチャットなど）
   □マーダーミステリーやリアル脱出ゲームに参加した
   □ノベルゲームや選択肢で物語が変わるゲームを遊んだ
   □推し活をしている
   □どれもない
4. ふだんスマホでゲームや物語を楽しむ場所は？（複数可）
   □自宅 □通勤・通学中 □外出先 □その他
5. イヤホンをつけて、声でスマホに話しかけることに抵抗はありますか。
   □ない □場所による □ある
6. お使いのスマホは？　□iPhone（機種：　） □Android（機種：　）
7. 物語の世界に入って、登場人物と声で話しながら物語を進める体験があるとします。
   7a. 好きな物語が題材なら、遊んでみたいと思いますか。
       □とても思う □やや思う □どちらともいえない □あまり思わない □まったく思わない
   7b. 題材が『走れメロス』なら、遊んでみたいと思いますか。
       □とても思う □やや思う □どちらともいえない □あまり思わない □まったく思わない
       （よければ理由：　　）
```

- Question 2 does not screen anyone out; it is only recorded, to see whether people who "have not read it" can understand the game.
  第 2 問では誰もふるい落とさず、記録するだけ。「読んだことがない」人がゲームを理解できるかを見るために使う。
- Questions 4 and 5 test the inferred usage setting "at home, alone" (research.md §1.3).
  第 4・5 問は「自宅で、一人で」という利用場面の推測（research.md §1.3）を検証するために使う。
- Question 7 **does not screen anyone out**: people with low 7b scores are also invited per quota, to see whether their impression changes after playing. The difference between 7a and 7b shows whether "the title itself" adds or subtracts. The applicants were drawn in by a 「物語体験」 recruiting post, so they are close to the main users but do not represent all Japanese adults; the report states this.
  第 7 問も**誰もふるい落とさない**：7b が低い人も割り当てどおりに招き、遊んだ後に印象が変わるかを見る。7a と 7b の差が「書名そのもの」が加点か減点かを示す。応募者は「物語体験」の募集投稿に惹かれて来た人なので、メインユーザーに近いが日本の成人全体を代表するものではない。報告書にそのことを明記する。

### 3.3 Where to find people / 3.3 どこで探すか

- Main users: マダミス and escape-game player communities, AI character chat and literary circles on X, university clubs. Always use a public recruiting post that clearly states the duration, compensation and how recordings are handled.
  メインユーザー：マダミスや脱出ゲームのプレイヤーコミュニティ、X 上の AI キャラクターチャットや文学の界隈、大学のサークル。いずれも公開の募集投稿を使い、所要時間、謝礼、録音の扱いを明記する。
- Referrals from acquaintances make up at most one third, so the sample is not all "people friendly to the team".
  知人の紹介は最大 3 分の 1 までにし、サンプルが「チームに好意的な人」ばかりにならないようにする。
- Paid samples from an external research company cost money; ask zg first.
  外部の調査会社の有償サンプルは費用がかかるので、まず zg に聞く。

**Compensation**: gift cards by duration (inferred: 70 minutes for the observation group and 50 minutes for R1, about ¥1,000〜3,000; market rates not checked). **The budget needs zg's approval**: for R1, PM asks in the middle of M2 together with the storage location in §3.4 (dev-plan Z-10, open-questions Q-008); for R2, the budget for about 70 people and whether to hire a research company are asked separately in the middle of M3 (Z-13).

**謝礼**：所要時間に応じてギフトカードを渡す（推測：観察グループ 70 分、R1 50 分で約 ¥1,000〜3,000、相場は未確認）。**予算は zg の承認が必要**：R1 の分は M2 の中盤に PM が §3.4 の保管場所と一緒に聞く（dev-plan Z-10、open-questions Q-008）。R2 の約 70 人分の予算と調査会社を使うかどうかは、M3 の中盤に別途聞く（Z-13）。

### 3.4 Consent, privacy and data storage / 3.4 同意、プライバシー、データの保管

**Consent**: written consent beforehand. State clearly what is recorded (the phone screen and audio; faces are not filmed by default), what it is used for (only for analysis to improve the product), who can see it, when it is deleted, and that participants can withdraw at any time and ask for deletion. Participants log in with an invite code (S-020), and after playing they can also use 「delete all my data」 (data-design L3) to delete the game.

**同意**：事前に書面で同意を得る。何を記録するか（スマホの画面と音声、顔はデフォルトで撮らない）、何に使うか（製品改善のための分析だけ）、誰が見られるか、いつ削除するか、いつでも辞退して削除を求められることを明記する。参加者は招待コードでログインし（S-020）、遊んだ後に「自分のデータをすべて削除」（data-design L3）でその局を削除することもできる。

**Storage**: raw data is **never** put in `/mnt/project-files`, the code repo, chat or documents; the playtest URL and invite codes are one per person, sent to each participant separately, and are not written in documents or chat either (deployment security rules).

**保管**：生データは `/mnt/project-files`、コードリポジトリ、チャット、ドキュメントの**どこにも置かない**。試遊用の URL と招待コードは一人に一つで、参加者に個別に送り、ドキュメントやチャットにも書かない（デプロイのセキュリティ規則）。

| Data / データ | Where it is stored / 保管場所 | Who can see it / 閲覧できる人 | When it is deleted / 削除の時期 |
|---|---|---|---|
| Screen recordings, audio recordings, moderator notes (including verbatim quotes) / 画面録画、録音、進行役のメモ（発言そのものを含む） | Research storage: a location provided or approved by zg and open only to the people listed here (candidate: a separately shared cloud folder under zg's account). **Ask zg about the location in the middle of M2** (dev-plan Z-10), together with the compensation budget / 研究用の保管場所：zg が用意または同意し、ここに挙げた人だけに開かれた場所（候補：zg のアカウント下で個別に共有するクラウドフォルダ）。**場所は M2 の中盤に zg に聞く**（dev-plan Z-10）、謝礼の予算と一緒に | UX (moderation), market research (analysis), zg / UX（進行）、市場調査（分析）、zg | Deleted within 60 days after the report for that round is done; the consent form says 「最長 60 日」 / そのラウンドの試遊報告書の完成後 60 日以内に削除。同意書には「最長 60 日」と書く |
| Raw questionnaire answers (participant number only, no names) / アンケートの生回答（参加者番号のみ、氏名なし） | Same as above / 同上 | Same as above / 同上 | Deleted within 90 days after the invite-code playtest period ends, in sync with product data (S-035); the report keeps only aggregated results / 招待コードによる試遊期間の終了後 90 日以内に、製品データと同時に削除（S-035）。報告書には集計結果だけを残す |
| Mapping table (participant number ↔ invite code ↔ game ID) / 対応表（参加者番号 ↔ 招待コード ↔ 局 ID） | Same as above, in a separate file / 同上、別ファイル | Market research only / 市場調査のみ | Deleted at the same time as the raw questionnaire answers / アンケートの生回答と同時に削除 |
| Contact details (name used, email, information needed to pay compensation; whether they agree to interview question 7 "invite me next time") / 連絡先（呼び名、メールアドレス、謝礼の支払いに必要な情報、インタビュー第 7 問「次回の招待」への同意の有無） | **A separate table without participant numbers**, so it cannot be matched to questionnaires or event logs / **参加者番号を書かない別の表**で、アンケートやイベントログと突き合わせられないようにする | The person who handles contact and compensation / 連絡と謝礼の支払いを担当する人 | Deleted within 30 days after compensation is paid; for those who agree to "invite me next time", kept until the next invitation, at most 1 year / 謝礼の支払い後 30 日以内に削除。「次回の招待」に同意した人は次の招待まで、最長 1 年保持 |
| Event logs / イベントログ | The product database, under the data-design rules (S-010); analysis exports are by game ID and contain no player utterances / 製品のデータベース、data-design のルール（S-010）に従う。分析用のエクスポートは局 ID 単位で、プレイヤーの発言そのものは含まない | Data engineering, under data-design permissions / データエンジニアリング、data-design の権限に従う | Per S-035: player utterances are cleared after the ending is generated; everything is deleted within 90 days after the invite-code playtest period ends; deleted along with the game when a participant deletes it / S-035 に従う：プレイヤーの発言は結末の生成後に消去。招待コードによる試遊期間の終了後 90 日以内にすべて削除。参加者が局全体を削除したときは一緒に削除 |

No personal information unrelated to the research is collected. Answers to interview question 7 are recorded only in the contact table, not in the interview notes.

研究と関係のない個人情報は集めない。インタビュー第 7 問の回答は連絡先の表にだけ記録し、インタビューのメモには書かない。

**When a participant is emotionally unsettled**: the moderator first pauses the playtest and asks whether they want to continue; self-harm and help-seeking signals in the game are handled by the product: when unsure, it shows a small hint at the edge of the screen; when clear, it pauses the story and shows a quiet card that tells them about Japanese support lines (S-043, S-069). The moderator also keeps the same list of support lines at hand (the one UX verifies before launch).

**参加者の気持ちが不安定になったとき**：進行役はまず試遊を止め、続けたいかどうかを尋ねる。ゲーム内の自傷や助けを求めるサインは製品が対応する：判断がつかないときは画面の端に小さなヒントを出し、明らかなときは物語を止めて静かなカードを出し、日本の相談窓口を伝える（S-043、S-069）。進行役も同じ窓口の一覧（UX が公開前に確認したもの）を手元に用意しておく。

**Only count the pause cards** (S-072): the first version of the self-harm classifier prefers an occasional false stop over missing a real signal, so pause cards may also appear in ordinary playtests.

**一時停止カードは回数だけを数える**（S-072）：自傷の分類器の最初の版は、本物のサインを見逃すくらいなら時々誤って止めるほうを選んでいるので、普通の試遊でも一時停止カードが出ることがある。

- The moderator records on the sheet how many times pause cards appeared in this game and in which act each was. Count only the cards that pause the story (including the one escalated when the system is unsure a second time in the same game), not the small hints at the edge.
  進行役は記録表に、その局で一時停止カードが何回出たか、それぞれ第何幕だったかを書く。数えるのは物語を止めるカードだけ（同じ局で 2 回目に判断がつかなかったときに格上げされるカードを含む）で、端に出る小さなヒントは数えない。
- Do not record what the player said at that moment, and do not ask follow-up questions. Do not pick this moment when reviewing the recording, and do not quote anything said around it in notes or reports.
  そのときプレイヤーが何を言ったかは記録せず、深掘りもしない。録画を振り返るときにこの場面を選ばず、メモや報告書でその前後の発言を引用しない。
- If the player asks, say only 「物語の中の言葉でも出ることがあります。そのまま物語に戻れます。」 (the first half matches the small line of text on the card, ux-design 14.1); do not explain further or mention what the player said; this does not count as "with help" (Q1). If the player is clearly distressed, follow the previous paragraph.
  プレイヤーに聞かれたら「物語の中の言葉でも出ることがあります。そのまま物語に戻れます。」とだけ言う（前半はカードの小さな文字と同じ、ux-design 14.1）。それ以上説明せず、プレイヤーが何を言ったかにも触れない。これは「助けあり」に数えない（Q1）。プレイヤーが明らかにつらそうなら前の段落に従う。
- Market research totals up after each day's sessions: total pause cards ÷ number of games actually played (group A of the controlled experiment reads the original and is not counted). If it exceeds 1/20 (e.g. 3 in 40 games), tell PM the same day without waiting for the report; the classifier must be fixed before launch (S-072 ⑤). R1 is a slice and is reported separately from R2, along with the combined total.
  市場調査は毎日の終了後に累計する：一時停止カードの合計回数 ÷ 実際に遊んだ局数（対照実験の A グループは原文を読むので数えない）。1/20 を超えたら（例：40 局で 3 回）報告書を待たずにその日のうちに PM に伝え、公開前に分類器を直す（S-072 ⑤）。R1 はスライスなので R2 とは別に報告し、合計も報告する。
- With so few games, this figure can only reveal an obviously high rate: R1 plus R2 is about 45〜50 games in total, and even with zero occurrences the 95% upper bound is still about 6〜7%, which cannot prove the rate is below 1/20. Whether the classifier is good enough mainly depends on the backend's eval set (S-072 ②).
  局数が少ないので、この数字で見つけられるのは明らかに高い場合だけ：R1 と R2 で合計約 45〜50 局、1 回も出なくても 95% の上限はなお約 6〜7% で、1/20 を下回ることは証明できない。分類器が十分かどうかは主にバックエンドの評価セット（S-072 ②）で見る。

## 4. How one playtest session runs / 4. 試遊 1 回の流れ

**No live think-aloud** (UX review 2-1). Players have to speak to the characters; asking them to also tell the moderator their thoughts at the same time mixes the two kinds of speech: words meant for the moderator may get recorded while holding to talk, and players have to stop and think "who is this line for?", which breaks immersion. So:

**リアルタイムの思考発話はしない**（UX レビュー 2-1）。プレイヤーは登場人物に話しかける必要があり、同時に進行役にも考えを話してもらうと、2 種類の発話が混ざる：進行役に向けた言葉が押して話している間に録音されてしまうことがあり、プレイヤーも「この一言は誰に向けたものか」に気を取られ、没入が途切れる。そこで：

- While they play, the moderator only observes and takes notes.
  プレイ中、進行役は観察と記録だけをする。
- **At the end of each act** (the moment the end-of-act choice appears and story time is already paused), ask only one question: 「いま、何を考えていましたか。」
  **各幕の終わり**（幕末の選択肢が出て、物語の時間がもともと止まっている瞬間）に一言だけ聞く：「いま、何を考えていましたか。」
- After playing, the moderator and the player watch the recording together, go back to 2〜3 key moments (the set piece of a key moment, a place where they got stuck, the moment they opened the map), and do a **retrospective think-aloud**.
  遊び終わったら、進行役とプレイヤーが一緒に録画を見て、2〜3 の重要な場面（重要な場面の演出、詰まった箇所、地図を開いた瞬間）に戻り、**振り返り式の思考発話**を行う。

### 4.1 R2 observation group (about 70 minutes) / 4.1 R2 観察グループ（約 70 分）

| Time / 時間 | Segment / 段階 | Notes / 説明 |
|---|---|---|
| 0〜5 min / 0〜5 分 | Explanation and consent / 説明と同意 | "We are testing the product, not you" / 「テストしているのは製品で、あなたではありません」 |
| 5〜10 min / 5〜10 分 | Pre-play questionnaire + one spoken question / プレイ前アンケート + 口頭の質問 1 つ | §6.1; ask aloud for the reason behind screening question 7b: 「『走れメロス』と聞いて、遊んでみたいと思いましたか。なぜですか。」 (Q9) / §6.1。スクリーニング第 7b 問の理由を口頭で聞く：「『走れメロス』と聞いて、遊んでみたいと思いましたか。なぜですか。」（Q9） |
| 10〜40 min / 10〜40 分 | Play one game / 1 局遊ぶ | On their own phone with earphones, as much like at home as possible. About one third enter by tapping a link inside LINE (S-015); in R2, these people's links **do not** carry `openExternalBrowser=1`, so real people go through the in-app browser detection and guidance (R1 does this differently, see §4.2). The moderator gives no hints and only steps in after the player has been stuck for more than 2 minutes; any intervention is recorded as "with help". The time box includes the cover, identity selection, the first microphone explanation and the ending page; **it is not cut off if it runs over**, because the ending page and the ending card are exactly what Q4 looks at / 自分のスマホでイヤホンをつけ、できるだけ自宅にいるように遊ぶ。約 3 分の 1 の人は LINE の中のリンクから入る（S-015）。R2 ではこの人たちのリンクに `openExternalBrowser=1` を**付けず**、実際の人にアプリ内ブラウザの検出と誘導を通ってもらう（R1 はやり方が違う、§4.2 参照）。進行役はヒントを出さず、2 分以上詰まったときだけ介入し、介入したら「助けあり」と記録する。この時間枠には表紙、身分の選択、最初のマイクの説明、結末ページを含む。**時間を超えても中断しない**。結末ページと結末カードこそ Q4 で見るものだから |
| 40〜50 min / 40〜50 分 | Post-play questionnaire + the voice question / プレイ後アンケート + 声についての質問 | §6.2; after the questionnaire, ask aloud whether they could tell apart the voices of two characters in the same scene; the question and how to judge it are the same as in R1 (S-074, section 4 of the observation sheet) / §6.2。アンケートの後、同じ場面にいた 2 人の登場人物の声を聞き分けられたかを口頭で聞く。質問と判定方法は R1 と同じ（S-074、観察記録表の第 4 節） |
| 50〜70 min / 50〜70 分 | Review + short interview / 振り返り + 短いインタビュー | First review 2〜3 moments in the recording, then interview per §6.3 (Mom Test: ask about specific past behavior, not "would you use it"). If time is short, ask only interview questions 1, 2 and 5 (R1 must also ask question 4) / まず録画で 2〜3 の場面を振り返り、次に §6.3 に従ってインタビューする（Mom Test：「使いますか」ではなく過去の具体的な行動を聞く）。時間が足りなければ第 1、2、5 問だけ聞く（R1 では第 4 問も必ず聞く） |

Compensation is based on 70 minutes (§3.3).

謝礼は 70 分として計算する（§3.3）。

**Moderator notes** use UX's observation sheet (`ux/playtest/observation-sheet.md`; a v0.1 draft exists and will be finalized before deploying for the first review), with the codes from UX review 2-4: STUCK, WHY / BOOK, WOW / LAUGH, CONFUSE, V→T / T→V (with reason), HELP-GIVE / HELP-ASK, GRILLED, LESSON (「教科書っぽい」「授業みたい」, for Q9), AI (mentions AI or tests the character), TIME (looks at the sun band and the deadline, says 「間に合うかな」), WHO (confuses who is speaking, for Q5 and S-074 ④). In addition, record four things per game: **entry route** (opened directly / entered from LINE), **whether the microphone could be used in this game**, **audio output device** (wired earphones / Bluetooth earphones / speaker), and **how many times the pause card appeared** (count and act only, §3.4).

**進行役の記録**には UX の観察記録表（`ux/playtest/observation-sheet.md`、v0.1 の草稿があり、初回のレビュー用のデプロイ前に確定する）を使い、コードは UX レビュー 2-4 のものを採用する：STUCK、WHY / BOOK、WOW / LAUGH、CONFUSE、V→T / T→V（理由を含む）、HELP-GIVE / HELP-ASK、GRILLED、LESSON（「教科書っぽい」「授業みたい」、Q9 に対応）、AI（AI に言及する、または登場人物を試す）、TIME（太陽の帯と期限を見る、「間に合うかな」と言う）、WHO（誰が話しているかを取り違える、Q5 と S-074 ④ に対応）。加えて局ごとに 4 項目を記録する：**入り方**（直接開いた / LINE から入った）、**この局でマイクが使えたか**、**音の出力機器**（有線イヤホン / Bluetooth イヤホン / スピーカー）、**一時停止カードが何回出たか**（回数と第何幕かだけ、§3.4）。

### 4.2 R1 (about 50 minutes) / 4.2 R1（約 50 分）

Same flow as above, with the play part replaced by the slice (about 15 minutes, adjusted to the slice's actual length). **No tasks, only a scenario** (designed by UX and delivered with the observation sheet before M2), e.g. 「あなたは旅人です。日が暮れる町に着きました。好きなように過ごしてください。」 The moderator only steps in after the player has been stuck for more than 2 minutes, and phrases any intervention as part of the scenario too (「町の人に話しかけてみてもいいですよ」).

流れは上と同じで、遊ぶ部分をスライス（約 15 分、スライスの実際の長さに合わせて調整）に替える。**タスクは与えず、シナリオだけを与える**（UX が設計し、M2 の前に観察記録表と一緒に渡す）。例：「あなたは旅人です。日が暮れる町に着きました。好きなように過ごしてください。」2 分以上詰まったときだけ介入し、介入するときもシナリオの言い方を使う（「町の人に話しかけてみてもいいですよ」）。

The post-play questionnaire covers only C1〜C2, C4〜C5, C6 (when the slice has a character ending), D1〜D7, E1 and E4; no TS-SF, E2〜E3 or price. The M2 slice is "S1 square + traveler + 町の老爺 and メロス" (S-050), and every identity's first act has a small two-way mutual-help moment that can always be completed (S-048), so **R1 already tests "mutual influence"**: C4 and C5 are used from R1, with the same scoring rules as §6.2.

プレイ後アンケートは C1〜C2、C4〜C5、C6（スライスに登場人物の結末があるとき）、D1〜D7、E1、E4 だけを行い、TS-SF、E2〜E3、価格は行わない。M2 のスライスは「S1 広場 + 旅人 + 町の老爺とメロス」（S-050）で、どの身分の第一幕にも必ず達成できる双方向の小さな助け合いがある（S-048）。そのため **R1 で先に「互いに影響し合う」を測る**：C4、C5 は R1 から使い、採点ルールは §6.2 と同じ。

After the post-play questionnaire and before the review, the moderator asks one spoken question about voices (S-074 ④): when the old man and メロス are in the same scene, can they tell who is speaking from the voice alone? The question and how to judge it are in section 4 of the observation sheet. It comes after the questionnaire so it does not influence D1.

プレイ後アンケートの後、振り返りの前に、進行役が声について口頭で 1 問聞く（S-074 ④）：老爺とメロスが同じ場面にいるとき、声だけで誰が話しているか聞き分けられたか。質問と判定方法は観察記録表の第 4 節にある。D1 に影響しないようにアンケートの後に置く。

**Invite links** (UX suggestion, PM agreed): every R1 link sent to participants has `?openExternalBrowser=1` appended (use `&` when the link already has parameters). LINE's developer docs state that opening a URL with this parameter from LINE opens it in an external browser (except LIFF), so people who tap it in a LINE chat go straight into Safari / Chrome and never see the "voice may not work in the in-app browser" notice. R1 is looking for story and voice problems in the slice; the in-app browser path is left for real people to go through in R2 (§4.1).

**招待リンク**（UX の提案、PM が同意）：R1 で配るリンクにはすべて `?openExternalBrowser=1` を付ける（リンクにすでにパラメーターがあるときは `&`）。LINE の開発者向けドキュメントによると、このパラメーター付きの URL を LINE から開くと外部ブラウザで開く（LIFF を除く）。そのため LINE のチャットからタップした人もそのまま Safari / Chrome に入り、「アプリ内ブラウザでは音声が使えないことがある」という案内には出会わない。R1 で探すのはスライスの物語と音声の問題で、アプリ内ブラウザの経路は R2 で実際の人に通ってもらう（§4.1）。

- Before sending the links, tap one from a LINE chat on both iPhone and Android to confirm it really opens in an external browser.
  リンクを送る前に、iPhone と Android でそれぞれ LINE のチャットから 1 回タップし、本当に外部ブラウザで開くか確認する。
- As usual, links are one per person and sent separately, and never go into chat or documents.
  リンクは決まりどおり一人に一つで個別に送り、チャットやドキュメントには入れない。
- The observation sheet still records the entry route: people who tapped it in LINE and played in the external browser are recorded as "entered from LINE". They play in Safari / Chrome, so the telemetry `app_open.entry` will most likely record direct; R1's entry route therefore goes by the observation sheet; `app_open.inAppBrowser` should be false, and games where it is not false are flagged separately.
  観察記録表には入り方もそのまま記録する：LINE からタップして外部ブラウザで遊んだ人は「LINE から入った」と記録する。この人たちは Safari / Chrome で遊ぶので、テレメトリーの `app_open.entry` はたいてい direct と記録される。そのため R1 の入り方は観察記録表を正とする。`app_open.inAppBrowser` は false のはずで、false でない局は別に印を付ける。

## 5. Controlled experiment (R2, answers Q3) / 5. 対照実験（R2、Q3 に答える）

| Group / グループ | What they do / 何をするか | Duration / 所要時間 |
|---|---|---|
| A read the original / A 原文を読む | Read the full text of 『走れメロス』 from 青空文庫 on a phone (about ten thousand characters) / スマホで青空文庫の『走れメロス』全文（約 1 万字）を読む | About 20 minutes (inferred: 400〜600 characters per minute) / 約 20 分（推測：1 分あたり 400〜600 字） |
| B play one game / B 1 局遊ぶ | **Identity fixed as the traveler** (the default identity under 「はじめての方に」), play to an ending / **身分は旅人に固定**（「はじめての方に」のデフォルトの身分）、結末まで遊ぶ | 15〜20 minutes (S-006), not cut off if it runs over / 15〜20 分（S-006）、超えても中断しない |

**Why the identity is fixed**: the three identities follow different storylines (ux-design.md §5.1: the shepherd boy starts in the village, the 石屋の弟子 stays at the workshop), and which characters players meet differs a lot, which directly affects questions like B5 and B6 ("does a certain character come vividly to mind"). Fixing the traveler means the analysis does not have to control for identity. The observation group can choose freely.

**身分を固定する理由**：3 つの身分は通る筋が異なり（ux-design.md §5.1：牧童は村から始まり、石屋の弟子は工房に詰めている）、どの登場人物に会うかが大きく違うため、B5、B6 のような「ある登場人物が目に浮かぶか」の質問に直接影響する。旅人に固定すれば、分析で身分を統制する必要がない。観察グループは自由に選べる。

**B5 and B6 ask about メロス and セリヌンティウス** (confirmed by UX): メロス entering the city is a fixed event from the original in act 1, so the traveler meets him in every game; the ending set piece puts セリヌンティウス on stage by default (S-053, coherence first), so he is met in almost every game. For group A, reading the original, these two are also the main characters, so the groups are comparable. On the traveler's route some players may meet セリヌンティウス only in the ending without ever talking to him; the analysis uses the event log to flag "talked with セリヌンティウス or not" as a covariate, without changing the questions; games where, per S-053, he cannot be present are flagged separately in the B6 analysis.

**B5、B6 はメロスとセリヌンティウスについて聞く**（UX 確認済み）：メロスが町に入るのは第一幕の原作どおりの固定イベントなので、旅人は毎局必ず彼に会う。結末の演出はデフォルトでセリヌンティウスをその場に立たせる（S-053、筋が通ることを優先）ので、ほぼ毎局会う。A グループが原文を読むときもこの 2 人は主要人物なので、両グループを比較できる。旅人の筋では、結末でしかセリヌンティウスに会わず、話したことがない人もいるかもしれない。分析ではイベントログで「セリヌンティウスと会話したか」に印を付けて共変量として扱い、質問は変えない。S-053 に従って彼がその場にいられない局は、B6 の分析で別に印を付ける。

The two groups take about the same time, both on phones, both with earphones. Afterward they fill in the same TS-SF (worded per group as 「読んでいる間」 or 「体験している間」).

両グループの所要時間はほぼ同じで、どちらもスマホで、どちらもイヤホンをつける。終わったら同じ TS-SF に答える（文言はグループごとに「読んでいる間」または「体験している間」に変える）。

**Analysis**: Welch's t-test, reporting Cohen's d and the 95% confidence interval. Write down the hypothesis "group B's mean TS-SF is higher than group A's" in advance, and do not pick metrics after the fact. Use only groups A and B of the controlled experiment, not the observation group (§2).
**Comparison quota** (35 or older, or none of those kinds of entertainment): about 8 per group, too small a sample, **used only to see whether there is an obvious reversal** (e.g. group B clearly lower than group A for these people); not reported separately, and no separate conclusions drawn.
**Limitations**: group B has a novelty effect (new technology itself is exciting), so the conclusion can only say "this experience was more engaging than reading the original", not "long-term interest in reading increased".

**分析**：Welch の t 検定で、Cohen's d と 95% 信頼区間を報告する。「B グループの TS-SF の平均は A グループより高い」という仮説を事前に書いておき、後から指標を選ばない。対照実験の A、B 両グループだけを使い、観察グループは合算しない（§2）。
**対照の割り当て**（35 歳以上、またはそれらの娯楽のどれもしていない人）は各グループ約 8 人でサンプルが小さすぎるので、**明らかな逆転があるかを見るためだけに使い**（例：この人たちでは B グループが A グループより明らかに低い）、単独では報告せず、単独の結論も出さない。
**限界**：B グループには新奇性の効果（新しい技術そのものが楽しい）があるので、結論として言えるのは「今回の体験は原文を読むより没入できた」だけで、「長期的に読書への興味が高まった」とは言えない。

## 6. Questionnaires (Japanese) / 6. アンケート（日本語）

### 6.1 Before play / 6.1 プレイ前

```
A1. 『走れメロス』の結末を覚えていますか。覚えていることを一文で書いてください。（自由記述）
A2. メロス／王ディオニス／セリヌンティウスについて、それぞれ一言で印象を書いてください。（自由記述）
A3. 最近1か月で読んだ本の冊数（マンガを除く）：□0 □1 □2〜3 □4以上
```

### 6.2 After play (group B and the observation group; group A does only B1〜B6) / 6.2 プレイ後（B グループと観察グループ。A グループは B1〜B6 のみ）

TS-SF, adapted into Japanese (1＝まったく当てはまらない 〜 7＝とても当てはまる). The original is in knowledge.md §6.1; no validated Japanese version was found, so translate and back-translate before formal use.

TS-SF の日本語改訂版（1＝まったく当てはまらない 〜 7＝とても当てはまる）。原文は knowledge.md §6.1 にある。検証済みの日本語版は見つからなかったので、正式に使う前に翻訳とバックトランスレーションを行う。

```
B1. 体験している間、自分がその場面の中にいるように思い描けた。
B2. 体験している間、物語に気持ちが入り込んでいた。
B3. 物語がどう終わるのか知りたいと思った。
B4. この物語に心を動かされた。
B5. 体験している間、メロスの姿がありありと思い浮かんだ。          ※人物は §5 の確認後に確定
B6. 体験している間、セリヌンティウスの姿がありありと思い浮かんだ。  ※同上
```

Ending and attribution (Q2), mutual influence (Q8):

結末と原因特定（Q2）、互いの影響（Q8）：

```
C1. あなたの結末（称号）は何でしたか。（自由記述）
C2. その結末になったのは、あなたのどの行動のせいだと思いますか。いちばん大きいと思うものを一つ書いてください。（自由記述）
C3. プレイ前と同じ質問です。メロス／王／セリヌンティウスについて、それぞれ一言で印象を書いてください。（自由記述）
C4. この物語の中で、登場人物があなたのためにしてくれたことを一つ書いてください。誰が、何をしましたか。（自由記述。なければ「なし」）
C5. あなたが登場人物のためにしたことを一つ書いてください。誰のために、何をしましたか。（自由記述。なければ「なし」）
C6. いちばん結末が変わった登場人物は誰ですか。原作と比べて、どう変わりましたか。（自由記述）
```

**Scoring** (two people score independently and discuss any disagreements):

**採点**（2 人が独立して採点し、一致しないものは話し合う）：

- C2: a hit if the action the player wrote matches any event in the `cites` of the ending epilogue in the event log (S-027).
  C2：プレイヤーが書いた行動が、イベントログの結末エピローグの `cites` にあるいずれかのイベントと一致すれば的中（S-027）。
- C4: a hit if it matches an event with `actor` = a character ID that was done for the player (S-029 ②).
  C4：`actor` = 登場人物 ID で、プレイヤーのために行われたイベント（S-029 ②）と一致すれば的中。
- C5: a hit if it matches an event where the player helped a character or kept a promise to a character (記憶 `kind` is `help` or `promise`).
  C5：プレイヤーが登場人物を助けた、または登場人物との約束を守ったイベント（記憶の `kind` が `help`、`promise`）と一致すれば的中。
- Only when both C4 and C5 are hits does that person meet PRD §7.5 "mutual influence".
  C4 と C5 の両方が的中してはじめて、その人は PRD §7.5 の「互いに影響し合う」を満たしたとする。
- C6: a hit if the character and change written match that character's ending on the ending page (S-032) and the player can say how it differs from the original. This question checks whether character endings are noticed and remembered; it has no PRD target value, to be set after R1.
  C6：書いた登場人物と変化が結末ページにあるその登場人物の結末（S-032）と一致し、原作との違いを言えれば的中。この問いは登場人物の結末が気づかれ、覚えられているかを見るもので、PRD の目標値はなく、R1 の後に決める。

Experience (Q5):

体験（Q5）：

```
D1. キャラクターは、こちらの話を聞いてくれていると感じた。（1〜7）
D2. キャラクターに質問攻めにされていると感じた。（1〜7、低いほど良い）
D3. 同じことを何度も言われていると感じた。（1〜7、低いほど良い）
D4. 声で話すのは、□話しやすかった □少し話しにくかった □話しにくかった（理由：　）
D5. いちばん困った・わかりにくかった瞬間はどこですか。（自由記述）
D6. いちばん「おっ」と思った瞬間はどこですか。（自由記述）
D7. 登場人物は、それぞれ自分の考えや目的を持って動いていると感じた。（1〜7）
```

D7 corresponds to D-013 and S-030 (characters act on their own and make their own judgments); interview question 5 follows up on exactly which moment.

D7 は D-013、S-030（登場人物が自分で動き、自分で判断する）に対応する。インタビューの第 5 問で具体的にどの瞬間かを掘り下げる。

**D4 and the share of voice vs text are reported separately by "entry route" and "whether the microphone could be used"** (UX review 2-2): the LINE in-app browser may not grant the microphone (S-015), so these people may use only text for the whole game, and D4 means something different for them. These people also happen to test "a full game can be finished with text only" (PRD §7.2).

**D4 と音声・テキストの使用比率は「入り方」と「マイクが使えたか」で分けて報告する**（UX レビュー 2-2）：LINE のアプリ内ブラウザではマイクが使えないことがあり（S-015）、この人たちは 1 局ずっとテキストだけを使うかもしれず、D4 の意味が違ってくる。この人たちはちょうど「テキストだけでも 1 局遊び通せる」（PRD §7.2）の検証にも使える。

Sharing, replay and impression (Q4, Q7, Q9):

シェア、再プレイ、印象（Q4、Q7、Q9）：

```
E1. この体験を友だちに一言で紹介するとしたら？（自由記述）
E2. この結末を誰かに見せたいと思いますか。□思う（誰に：　） □思わない
E3. 別の身分でもう一度遊びたいですか。□今すぐ遊びたい □いつか □遊ばない
E4. 遊ぶ前と比べて、『走れメロス』という作品の印象は変わりましたか。
    □よくなった □変わらない □悪くなった（どう変わったか：　）
```

Behavior (not self-reported): the moderator and the event log record whether the participant **saved or sent the ending-card image on the spot** (S-026), and whether they switched identity and started another game on the spot.

行動（自己申告に頼らない）：進行役とイベントログで、参加者が**その場で結末カードの画像を保存または送信したか**（S-026）、その場で身分を変えてもう 1 局始めたかを記録する。

Price (Q6, Van Westendorp, asked only in R2 after play):

価格（Q6、Van Westendorp、R2 のプレイ後にだけ聞く）：

```
前提：今回の物語（『走れメロス』一冊分、何度でも遊べる）を買うとしたら、
F1. 高すぎて買えないと思うのはいくらからですか。
F2. 高いけれど、買うかもしれないと思うのはいくらですか。
F3. お得だと思うのはいくらですか。
F4. 安すぎて品質が心配になるのはいくらからですか。
```

The R2 sample is still under 200 people, so Van Westendorp is only a directional reference, not a basis for pricing (knowledge.md §5.1).

R2 のサンプルは 200 人に満たないので、Van Westendorp は方向性の参考にとどめ、価格は決めない（knowledge.md §5.1）。

### 6.3 Short interview guide / 6.3 短いインタビューの項目

1. What was the last time you spent time or money on a story (a game, マダミス, an AI character, a novel)? How much did you spend?
   最後に物語（ゲーム、マダミス、AI キャラクター、小説）に時間やお金を使ったのは何でしたか？どれくらい使いましたか？
2. If you were to tell a friend about the ending you just got, how would you put it?
   さっきの結末を友だちに話すとしたら、どう話しますか？
3. Was there a moment when you felt "the character isn't like that person anymore" or "the story feels off"?
   「登場人物がその人らしくなくなった」「物語がおかしい」と感じた瞬間はありましたか？
4. (Ask only in R1: the slice jumps straight from act 1 to the evening of the third day, and at the very bottom of the jump page there are two lines of small text that exist only in the trial version, S-080; the copy is `jump.trialNote` in `docs/ux/copy-ja.md`.) Ask about the small text first, then about the three days; the order must not be reversed: once the moderator mentions 「完成版では選べます」, players will think they read it.
   （R1 でだけ聞く：スライスは第一幕の後に三日目の夕方へ直接飛び、飛んだ先のページのいちばん下に試遊版だけにある 2 行の小さな文字がある。S-080、文言は `docs/ux/copy-ja.md` の `jump.trialNote`。）先に小さな文字について聞き、次にその 3 日間について聞く。順序を逆にしてはいけない：進行役が「完成版では選べます」と言った途端、プレイヤーは自分が読んだと思い込む。
   - a. Without saying what it said, first ask whether they noticed it: 「三日目に移るページのいちばん下に、小さな字が二行ありました。気づきましたか。」 If they noticed, ask: 「何と書いてあったか、覚えていますか。読んだとき、どう感じましたか。」 If they did not notice, do not bring it up again. If the player mentions these two lines on their own in question 3, that is the strongest signal of being pulled out of the story; flag it separately.
     a. 内容は言わずに、まず気づいたかを聞く：「三日目に移るページのいちばん下に、小さな字が二行ありました。気づきましたか。」気づいていたら続けて聞く：「何と書いてあったか、覚えていますか。読んだとき、どう感じましたか。」気づいていなければそれ以上触れない。プレイヤーが第 3 問で自分からこの 2 行に触れたら、物語から引き戻された最も強いサインとして別に印を付ける。
   - b. 「物語は、約束の日から三日目の夕方まで飛びました。その三日間、自分ならどこで過ごしたかったですか。」 First let the player answer in their own words; if they cannot name anything concrete, give examples: 「たとえば、メロスについて行く、身代わりになった人のそばにいる、ほかの場所にいる、など。」 Do not ask "would you buy the full version then?"
     b. 「物語は、約束の日から三日目の夕方まで飛びました。その三日間、自分ならどこで過ごしたかったですか。」まずプレイヤー自身の言葉を聞く。具体的なことが出てこなければ例を出す：「たとえば、メロスについて行く、身代わりになった人のそばにいる、ほかの場所にいる、など。」「それなら完全版を買いますか」とは聞かない。
   - Analysis: b is what the player says; compare it with where they actually chose to go at the end of the act in this game and the plan they stated at the end of the act (whether they said they wanted to go with メロス), and go by behavior. Write the results as a separate section of the R1 issue list for UX and PM (for the full version's design of "where to spend these three days").
     分析：b はプレイヤーの言い分なので、その局の幕末で実際に選んだ行き先や幕末に述べたプラン（メロスについて行きたいと言ったか）と照らし合わせ、行動を正とする。結果は R1 の問題リストの独立した節に書き、UX と PM に渡す（完全版での「この 3 日間をどこで過ごすか」の設計のため）。
5. Was there a character you wanted to help, or one you hoped would help you but did not? What happened then? Was there a moment when you felt "this person has their own ideas"?
   助けたいと思った登場人物、または助けてほしかったのに助けてくれなかった登場人物はいましたか？そのとき何が起きましたか？「この人には自分の考えがある」と感じた瞬間はありましたか？
6. When and where would you play this? What did you do the last time you were at that time and place?
   これをいつ、どこで遊びますか？前回その時間・その場所で何をしていましたか？
7. May we keep your contact details and invite you when the second book comes out? (A commitment; the answer is recorded only in the contact table in §3.4.)
   連絡先を残して、2 冊目が出たときに招待してもよいですか？（コミットメント。回答は §3.4 の連絡先の表にだけ記録する）

## 7. Outputs / 7. 成果物

- R1: an issue list (sorted by severity) for UX and PM; the results of question 7 and E4 as a separate section for PM (Q9, the risk to the main-user conclusion); the pause-card count and number of games also as a separate section for PM (§3.4).
  R1：問題リスト（深刻度順）を UX と PM に渡す。第 7 問と E4 の結果は独立した節にして PM に渡す（Q9、メインユーザーの結論のリスク）。一時停止カードの回数と局数も独立した節にして PM に渡す（§3.4）。
- R2: the playtest report `market-research/playtest-report.md`, covering: whether each item of PRD §7.5 is met, the TS-SF comparison result, mutual-influence scoring, behavioral metrics, price direction, pause-card count (§3.4), and suggested changes to the positioning. The report contains only aggregates, no verbatim quotes and nothing that could identify an individual; raw data is stored and deleted per §3.4.
  R2：試遊報告書 `market-research/playtest-report.md`。内容は PRD §7.5 の各項目を満たしたか、TS-SF の比較結果、互いの影響の採点、行動指標、価格の方向性、一時停止カードの回数（§3.4）、位置づけの修正案。報告書には集計だけを載せ、発言そのものや個人を特定できる内容は載せない。生データは §3.4 に従って保管・削除する。

## 8. What we need from others / 8. 他の人から必要なもの

| Who / 誰 | What / 何を |
|---|---|
| zg (via PM) / zg（PM 経由） | Middle of M2 (dev-plan Z-10): R1 compensation, the location of research storage (§3.4), whether they can refer acquaintances; middle of M3 (Z-13): the R2 compensation budget, whether to hire a research company; before R2 recruiting: trademark check (Z-9), decide the name (Z-15) / M2 の中盤（dev-plan Z-10）：R1 の謝礼、研究用の保管場所（§3.4）、知人を紹介できるか。M3 の中盤（Z-13）：R2 の謝礼の予算、調査会社を使うか。R2 の募集前：商標の確認（Z-9）、名前の決定（Z-15） |
| UX | Observation sheet `ux/playtest/observation-sheet.md` (a v0.1 draft exists, with the R1 scenario, a pause-card column and the voice question; finalized before deploying for the first review); the characters for B5 and B6 are confirmed (§5) / 観察記録表 `ux/playtest/observation-sheet.md`（v0.1 の草稿があり、R1 のシナリオ、一時停止カードの欄、声についての質問を含む。初回のレビュー用のデプロイ前に確定）。B5、B6 の登場人物は確認済み（§5） |
| Data engineering / データエンジニアリング | Event-log export by game ID (the field list has been sent directly to data, see below); add the "playtest number ↔ game" mapping to data-design §9 / 局 ID ごとのイベントログのエクスポート（フィールドの一覧はデータに直接送った、下記参照）。data-design §9 に「試遊番号 ↔ 局」の対応方法を追加 |
| Frontend / フロントエンド | Invite codes for the playtest (one per person, sent separately); the LINE in-app browser entry; R1 invite links with `openExternalBrowser=1`, checked by tapping once on both iPhone and Android before sending (§4.2) / 試遊用の招待コード（一人に一つ、個別に送る）。LINE のアプリ内ブラウザの入口。R1 の招待リンクに `openExternalBrowser=1` を付け、送る前に iPhone と Android でそれぞれ 1 回タップして確認する（§4.2） |

**Export fields sent to data engineering** (sent on 2026-10-06; data has written them into data-design.md 9.5, one JSON per game. Promise states are open / kept / broken / voided, where voided = the player deleted the promise in the 記憶帳, kept apart from a broken promise; "saved" = `ending_card_saved`, "sent" = `ending_shared.completed`, and when the system share sheet cannot report back, we only know the sheet was opened; gaps in telemetry are filled from moderator notes and marked `telemetryGap: true`; export files are deleted along with the research data's retention period):

**データエンジニアリングに送ったエクスポートのフィールド**（2026-10-06 に送付済み。データが data-design.md 9.5 に書き込み済みで、局ごとに 1 つの JSON。約束の状態は open / kept / broken / voided で、voided = プレイヤーが記憶帳で約束を削除したもので、約束を破ったこととは分ける。「保存」= `ending_card_saved`、「送信」= `ending_shared.completed`。システムの共有シートが結果を返せないときは、シートを開いたことしかわからない。テレメトリーの欠けは進行役の記録で補い、`telemetryGap: true` と印を付ける。エクスポートファイルは研究データの保存期間に合わせて削除する）：

| Field / フィールド | Used for / 用途 |
|---|---|
| Game ID, identity, start and end time, whether the ending was reached, world ending (one of the 5 baseline types, or the ending generated in this game and its summary, S-031, S-034) / 局 ID、身分、開始・終了時刻、結末に到達したか、世界の結末（5 種類の基本形のいずれか、またはこの局で生成された結末とその要約、S-031、S-034） | Q1, Q3 (confirm group B played the traveler), game duration / Q1、Q3（B グループが旅人だったことの確認）、局の所要時間 |
| The `cites` of each sentence of the ending epilogue (event IDs and event summaries); the `cites` of each sentence of each character ending (S-032) / 結末エピローグの各文の `cites`（イベント ID とイベントの要約）。各登場人物の結末の各文の `cites`（S-032） | C2, C6 scoring / C2、C6 の採点 |
| Events whose `actor` is a character ID, and events where the player helps a character or makes a promise (including promise state: in progress / kept / broken) / `actor` が登場人物 ID のイベントと、プレイヤーが登場人物を助けたり約束したりしたイベント（約束の状態：進行中 / 守った / 破った を含む） | C4, C5 scoring (Q8) / C4、C5 の採点（Q8） |
| Whether the player talked with セリヌンティウス; whether he is present in the ending set piece / セリヌンティウスと会話したか。結末の演出に彼がいるか | B6 covariate and separate flag (§5, S-053) / B6 の共変量と別の印（§5、S-053） |
| Entry route: telemetry `app_open.entry` (direct / LINE / other), `app_open.inAppBrowser`; whether the microphone could be used: `mic_permission.result` (granted / denied / unavailable) and `reason` (proposed by frontend, waiting for data to add it to data-design 9.3); actual voice share: computed from `talk_turn.inputMode` per `playthroughId`. Filled from moderator notes when telemetry is missing / 入り方：テレメトリーの `app_open.entry`（direct / LINE / その他）、`app_open.inAppBrowser`。マイクが使えたか：`mic_permission.result`（granted / denied / unavailable）と `reason`（フロントエンドの提案で、データが data-design 9.3 に書き込むのを待っている）。実際の音声の比率：`playthroughId` ごとに `talk_turn.inputMode` から計算。テレメトリーが欠けているときは進行役の記録で補う | D4 grouping (§6.2) / D4 のグループ分け（§6.2） |
| Input mode per turn (voice / text), number of recognition corrections / ターンごとの入力方法（音声 / テキスト）、認識の訂正回数 | Q5 |
| Events of saving or sending the ending-card image / 結末カードの画像を保存または送信したイベント | Q4 |
| Events of starting a new game on the spot from the same invite-code account (the new game's identity) / 同じ招待コードのアカウントでその場で新しい局を始めたイベント（新しい局の身分） | Q4 |
| Disconnect, backgrounding and resume events / 切断、バックグラウンドへの切り替え、再開のイベント | Q1 (whether disconnects caused getting stuck) / Q1（切断が詰まった原因か） |
| Number of times 「なぜこうなった？」 and the 記憶帳 were opened / 「なぜこうなった？」と記憶帳を開いた回数 | Interpreting Q2 / Q2 の解釈 |

Exports are by game ID and contain no player utterances, memory text or invite codes; the game ID ↔ participant number mapping exists only in research storage (§3.4).

エクスポートは局 ID 単位で、プレイヤーの発言、記憶の原文、招待コードは含まない。局 ID ↔ 参加者番号の対応は研究用の保管場所にだけある（§3.4）。

## Revision history / 改訂履歴

- 2026-10-11 (v1.1 addendum): all R1 invite links get `openExternalBrowser=1`; the third of R2 who enter from LINE do not (§4.1, §4.2, §8); R1's entry route goes by the observation sheet, since telemetry `entry` will record direct (UX review #115).
  2026-10-11（v1.1 追補）：R1 の招待リンクにはすべて `openExternalBrowser=1` を付け、R2 で LINE から入る 3 分の 1 には付けない（§4.1、§4.2、§8）。R1 の入り方は観察記録表を正とする。テレメトリーの `entry` は direct と記録されるため（UX レビュー #115）。
- 2026-10-10 (v1.1 addendum): added question 4 (R1) to the §6.3 interview: whether the two lines of small text on the trial version's jump page pulled people out of the story, and whether players want to choose for themselves where to spend those three days; the former questions 4〜6 become 5〜7 (references in §3.4, §4.1 and §6.2 updated accordingly).
  2026-10-10（v1.1 追補）：§6.3 のインタビューに第 4 問（R1）を追加：試遊版の飛んだ先のページにある 2 行の小さな文字で物語から引き戻されなかったか、プレイヤーはこの 3 日間をどこで過ごすか自分で選びたいか。元の第 4〜6 問は第 5〜7 問に繰り下げた（§3.4、§4.1、§6.2 の参照も合わせて変更）。
- 2026-10-10 (v1.1 addendum): aligned with UX observation sheet v0.1: added the WHO code, recorded the audio output device per game, asked the voice question aloud after play in R1 and the R2 observation group (S-074) (§4.1, §4.2, §8); storage location is now asked in the middle of M2 (dev-plan Z-10).
  2026-10-10（v1.1 追補）：UX の観察記録表 v0.1 に合わせた：WHO のコードを追加、局ごとに音の出力機器を記録、R1 と R2 の観察グループでプレイ後に声について口頭で聞く（S-074）（§4.1、§4.2、§8）。保管場所は M2 の中盤に聞くことにした（dev-plan Z-10）。
- 2026-10-07 (v1.1 addendum): added pause-card recording per S-072: the moderator records only the count and act per game, no content, no follow-up questions; exceeding 1/20 is reported to PM the same day (§3.4, §4.1, §7, §8).
  2026-10-07（v1.1 追補）：S-072 に従って一時停止カードの記録を追加：進行役は局ごとの回数と第何幕かだけを記録し、内容は記録せず深掘りもしない。1/20 を超えたらその日のうちに PM に伝える（§3.4、§4.1、§7、§8）。
- v1.1 (2026-10-06): changes per the UX review:
  v1.1（2026-10-06）：UX のレビューに従って変更：
  - No live think-aloud; replaced with one short end-of-act question + a review of the recording after play (§4).
    リアルタイムの思考発話はやめ、幕末の短い質問 1 つ + 遊んだ後の録画の振り返りに変更（§4）。
  - The R2 observation group's play time widened to 10〜40 minutes, not cut off when it runs over, 70 minutes for the whole session; the observation group's TS-SF is not pooled with group B.
    R2 の観察グループのプレイ時間を 10〜40 分に広げ、超えても中断せず、全体で 70 分。観察グループの TS-SF は B グループと合算しない。
  - Record the entry route and whether the microphone was usable, and report D4 separately; adopt UX's observation codes; R1 gives only a scenario, no tasks.
    入り方とマイクが使えたかを記録し、D4 は分けて報告する。UX の観察コードを採用。R1 ではシナリオだけを与え、タスクは与えない。
  - B5 and B6 confirmed as メロス and セリヌンティウス, with a covariate added; retention periods aligned with S-035; handling for emotionally unsettled participants added (S-043); ending baselines changed to 5 types (S-034).
    B5、B6 はメロスとセリヌンティウスに確定し、共変量を追加。保存期間を S-035 に合わせた。気持ちが不安定になったときの対応を追加（S-043）。結末の基本形を 5 種類に変更（S-034）。
- v1.0 (2026-10-06): changes per the PM review:
  v1.0（2026-10-06）：PM のレビューに従って変更：
  - Stated where raw data is stored, who can see it and when it is deleted; contact details are stored separately and cannot be matched to questionnaires or logs (§3.4).
    生データの保管場所、閲覧できる人、削除の時期を明記。連絡先は別に保管し、アンケートやログと突き合わせられないようにした（§3.4）。
  - Group B of the controlled experiment is fixed to the traveler; the characters for B5 and B6 await UX confirmation (§5).
    対照実験の B グループは旅人に固定し、B5、B6 の登場人物は UX の確認待ち（§5）。
  - R1 aligned with the M2 slice (§1, §2, §4.2); the comparison quota is only checked for reversals, not reported separately (§5).
    R1 を M2 のスライスに合わせた（§1、§2、§4.2）。対照の割り当ては逆転の有無だけを見て、単独では報告しない（§5）。
  - "Sharing on the spot" = saving or sending the ending-card image (S-026); export fields sent directly to data (§8).
    「その場でのシェア」= 結末カードの画像の保存または送信（S-026）。エクスポートのフィールドはデータに直接送った（§8）。
  - Added Q8 mutual influence (C4, C5, D-012, S-029), D7 "characters have their own ideas" (D-013, S-030), C6 character endings (D-015, S-032) and Q9 "does メロス itself have pull" (screening question 7, E4, interview).
    Q8 互いの影響（C4、C5、D-012、S-029）、D7「登場人物に自分の考えがある」（D-013、S-030）、C6 登場人物の結末（D-015、S-032）、Q9「メロスそのものに魅力があるか」（スクリーニング第 7 問、E4、インタビュー）を追加。
- v0.1 (2026-10-06): first draft.
  v0.1（2026-10-06）：初稿。
