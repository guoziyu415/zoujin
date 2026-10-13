# R1 observation sheet (draft v0.1) / R1 観察記録シート（下書き v0.1）

| Item / 項目 | Content / 内容 |
|---|---|
| Author / 作成者 | UX, 2026-10-10 / UX、2026-10-10 |
| Status / 状態 | **Draft**. When the slice can be played from start to finish, complete the items in section 6 from the actual screens; finalize before the deployment for the first review / **下書き**。スライスを最初から最後まで遊べるようになったら、実際の画面に合わせて第 6 節の項目を補う。最初のレビュー用のデプロイ前に確定する |
| Basis / 根拠 | `market-research/playtest-plan.md` §3.4, §4, §4.2, §6; `ux/ux-design.md` 14.1, 16.1, 17.2; decisions S-027, S-048, S-050, S-072, S-074; `ux/reviews/market-research-v1.0.md` part 2, item 4 (codes) / `market-research/playtest-plan.md` §3.4、§4、§4.2、§6；`ux/ux-design.md` 14.1、16.1、17.2；decisions S-027、S-048、S-050、S-072、S-074；`ux/reviews/market-research-v1.0.md` 第 2 部第 4 項（コード） |

**How to use**: one sheet per session, filled in by the facilitator. This file is only the blank form.

**使い方**：1 セッションにつき 1 枚、モデレーターが記入する。このファイルは空白の用紙だけ。

- Write only the participant ID (P01, P02 …); do not write names, invite codes or URLs, or personal information the player says aloud.
  参加者番号（P01、P02……）だけを書く。名前、招待コード、URL、プレイヤーが口にした個人情報は書かない。
- **Filled-in sheets do not go into `/mnt/project-files`, the code repository or chat**; put them in the research storage the same day (playtest-plan §3.4; where that is, is question Z-9 for zg).
  **記入済みのシートは `/mnt/project-files`、コードリポジトリ、チャットに置かない**。当日のうちに調査の保管場所へ入れる（playtest-plan §3.4。場所は zg への質問 Z-9）。

---

## 1. What the facilitator says (R1 gives only the situation, no tasks) / モデレーターが話すこと（R1 では状況だけを伝え、タスクは与えない）

The flow and timing follow playtest-plan §4.2 (about 50 minutes).

流れと時間配分は playtest-plan §4.2 に従う（約 50 分）。

| When / タイミング | What to say (read verbatim) / 話す内容（そのまま読み上げる） |
|---|---|
| Explanation and consent / 説明と同意 | 「今日試すのはアプリのほうで、あなたではありません。迷ったり、うまくいかなかったりしたところが、いちばん参考になります。」 |
| After the pre-play questionnaire / 試遊前アンケートの後 | Market research's pre-play questionnaire (playtest-plan §6.1), then one spoken question (Q9): 「『走れメロス』と聞いて、遊んでみたいと思いましたか。なぜですか。」 Write the answer down verbatim / マーケットリサーチの試遊前アンケート（playtest-plan §6.1）の後、口頭で 1 問（Q9）：「『走れメロス』と聞いて、遊んでみたいと思いましたか。なぜですか。」答えはそのまま記録する |
| Start of play / 試遊開始 | 「あなたは旅人です。日が暮れる町に着きました。好きなように過ごしてください。」 No further explanation after this / 「あなたは旅人です。日が暮れる町に着きました。好きなように過ごしてください。」以後は説明しない |
| Stuck for 2 minutes or more / 2 分以上行き詰まったとき | Phrase it in terms of the situation, e.g. 「町の人に話しかけてみてもいいですよ」. Do not phrase it in terms of controls (do not say where to tap). **One intervention and the session is recorded as “assisted”** (S-027); in section 3 record STUCK and the exact words of the intervention / 状況に即した言い方にする。例：「町の人に話しかけてみてもいいですよ」。操作の言い方はしない（どこを押すかは言わない）。**1 回でも介入したら、そのセッションは「支援あり」と記録する**（S-027）。第 3 節に STUCK と介入した言葉をそのまま記録する |
| When the end-of-act choice appears / 幕末の選択が出たとき | 「いま、何を考えていましたか。」 Ask only this, and write the answer down verbatim / 「いま、何を考えていましたか。」これだけを聞き、答えはそのまま記録する |
| If the player asks about the pause card / プレイヤーが一時停止カードについて尋ねたとき | 「物語の中の言葉でも出ることがあります。そのまま物語に戻れます。」 Do not explain further, and do not mention what the player said; **this does not count as “assisted”**. If the player is clearly distressed, pause the playtest first, ask whether they want to continue, and show them the helpline list you have at hand (the one checked in ux-design 14.3) / 「物語の中の言葉でも出ることがあります。そのまま物語に戻れます。」それ以上は説明せず、プレイヤーが何を言ったかにも触れない。**「支援あり」には数えない**。プレイヤーが明らかにつらそうなときは、まず試遊を止めて続けるかどうかを尋ね、手元の窓口一覧を見せる（ux-design 14.3 で確認済みのもの） |

During play the facilitator does not talk and does not ask for think-aloud; they only watch and take notes.

試遊中、モデレーターは話さず、思考発話も求めず、見て記録するだけにする。

## 2. Record first for each session / セッションごとに最初に記録すること

| Item / 項目 | Fill in / 記入 |
|---|---|
| Participant ID, date, facilitator / 参加者番号、日付、モデレーター | |
| Phone / スマートフォン | Model only (e.g. iPhone 13 / Android) / 機種だけを記録（例：iPhone 13 / Android） |
| Entry route / 入り方 | □ Opened directly / 直接開いた　□ Via LINE / LINE から入った |
| Microphone / マイク | □ Works / 使える　□ Refused / 拒否した　□ Unavailable / 使えない (e.g. LINE's in-app browser does not allow it / 例：LINE の内蔵ブラウザでは使えない)　Reason / 理由： |
| Audio output / 音声出力 | □ Wired earphones / 有線イヤホン　□ Bluetooth earphones / Bluetooth イヤホン　□ Phone speaker / 本体スピーカー (the voice question in section 4 and D4 are both broken down by this / 第 4 節の声の質問と D4 はどちらもこれで分けて見る) |
| Reached the slice ending / スライスのエンディングに到達 | □ Reached it / 到達した　□ Did not; stopped at / 到達せず、止まった場所： |
| Assisted / 支援あり | □ No / なし　□ Yes, __ interventions / あり、介入 __ 回 |
| **Pause card / 一時停止カード** | Appeared __ times; which act each time: ____ (in the slice write 「一幕」 or 「日没」). Count only the card that stops the story, including the one escalated when the system is unsure a second time in the same session; small hints at the edge of the screen do not count. **Do not record what the player said at that moment, do not ask about it, do not pick this moment when reviewing the recording, and do not write down what was said around it in your notes** (S-072) / 出た回数 __ 回。それぞれ第何幕か：____（スライスでは「一幕」または「日没」と書く）。数えるのは物語を止めるカードだけで、同じセッションで 2 回目に判断がつかなかったときに格上げされたカードも含む。画面の端の小さな案内は数えない。**そのときプレイヤーが何を言ったかは記録せず、問いかけず、録画を振り返るときにこの瞬間は選ばず、その前後の言葉もメモに書かない**（S-072） |

**Timestamps** (recording time mm:ss; where telemetry has it, telemetry wins, and this fills the gaps):

**タイムスタンプ**（録画の時刻 mm:ss。テレメトリにあればテレメトリを優先し、ここでは欠けた分を補う）：

| Moment / 時点 | Time / 時刻 |
|---|---|
| Taps 「はじめる」 / 「はじめる」を押す | |
| First utterance (voice or text) / 初めて話す（声または文字） | |
| First sees a character respond to their own action (first reaction; PRD section 7, p75 ≤ 3 minutes) / 自分の行動に人物が反応するのを初めて見る（最初の反応、PRD 第 7 節 p75 ≤ 3 分） | |
| Opening mutual aid completed (traveler: listens properly to the old man, or walks him to his door; S-048) / 序盤の助け合いの完了（旅人：老爺の話をきちんと聞く、または家の前まで送る。S-048） | |
| The old man introduces you to Melos / 老爺があなたをメロスに引き合わせる | |
| Makes a promise with Melos / メロスと約束を交わす | |
| Jump to sunset on the third day / 三日目の日没へジャンプ | |
| Ending set piece starts / エンディングの演出が始まる | |

## 3. Notes during play / 試遊中の記録

| Recording time / 録画の時刻 | Code / コード | Where, doing what / 場所と行動 | Observed (actions; exact words verbatim) / 見たこと（動作。発言はそのまま） | What the facilitator did / モデレーターの対応 |
|---|---|---|---|---|
| | | | | |

**Codes**:

**コード**：

| Code / コード | What to record / 記録すること | Maps to / 対応 |
|---|---|---|
| STUCK | Where they got stuck, for how long, how they got out, whether the facilitator intervened / 行き詰まった場所、時間、抜け出し方、モデレーターの介入の有無 | Q1 |
| WHY / BOOK | Opens 「なぜこうなった？」 or 記憶帳 on their own; what they were doing before opening it / 自分から「なぜこうなった？」や記憶帳を開く。開く前に何をしていたか | Q2、Q8 |
| WOW / LAUGH | 「おっ」, laughter, moments of surprise / 「おっ」、笑い、驚きの瞬間 | D6 |
| CONFUSE | Confused expressions or remarks / 困惑した表情や発言 | D5 |
| V→T / T→V | Switching between voice and text, and why (surroundings, misrecognition, embarrassed to speak) / 声と文字の切り替えとその理由（周りの環境、聞き間違い、声を出すのが恥ずかしい） | Q5 |
| HELP-GIVE / HELP-ASK | The player helps a character on their own initiative, asks a character for help, or agrees to a character's request / プレイヤーが自分から人物を助ける、人物に助けを求める、または人物の頼みを引き受ける | Q8 |
| GRILLED | Reactions like “they're asking me again” or “they're saying the same thing again” / 「また質問された」「また同じことを言っている」といった反応 | D2、D3 |
| LESSON | Remarks like 「教科書っぽい」 or 「授業みたい」 / 「教科書っぽい」「授業みたい」といった発言 | Q9 |
| AI | The player mentions 「AI」, or is testing the characters (jailbreaks, asking about the setup) / プレイヤーが「AI」に触れる、または人物を試している（脱獄、設定を聞く） | Immersion, safety / 没入、安全 |
| TIME | Looks at the sun band or the deadline on the map; says things like 「間に合うかな」 / 太陽帯や地図上の期限を見る。「間に合うかな」のようなことを言う | S-036 |
| **WHO** | Gets wrong who is speaking: replies to someone who isn't speaking, looks around for the speaker, asks 「今の誰？」. **Record who was taken for whom** (e.g. old man ↔ メロス, character ↔ narrator) / 誰が話しているかを取り違える：話していない人に返事をする、話し手を探して見回す、「今の誰？」と聞く。**誰を誰と取り違えたかを記録する**（例：老爺↔メロス、人物↔ナレーター） | Old man ↔ メロス goes to S-074 ④ (section 4); other mix-ups go to Q5 / 老爺↔メロス は S-074 ④（第 4 節）、それ以外の取り違えは Q5 |

**What UX also watches for** (not codes; if you see it, write one sentence in the “Observed” column):

**UX がついでに見ること**（コードではない。見かけたら「見たこと」の欄に一文書く）：

- Whether aizuchi feel natural, or redundant and make things feel slower (UQ-1).
  相槌が自然に感じられるか、それとも余計で、かえって遅く感じさせるか（UQ-1）。
- When a character walks over to you, whether the player responds (UQ-8).
  人物が近づいてきたとき、プレイヤーが相手をするか（UQ-8）。
- In the transition that jumps to sunset on the third day, whether the player understands that time has passed (S-050).
  三日目の日没へジャンプする場面転換で、プレイヤーが時間が経ったことを理解できるか（S-050）。
- When subtitles are marked 「書き起こし」 or 「（字幕を出せませんでした）」, whether the player notices and whether they are confused (rare; record it when it happens).
  字幕に「書き起こし」や「（字幕を出せませんでした）」が付いたとき、プレイヤーが気づくか、困惑するか（まれなので、出たら記録する）。

## 4. After play / 試遊の後

Order: post-play questionnaire (market research; the questions in §4.2) → **the voice question** → review of the recording → short interview (§6.3). The voice question comes after the questionnaire so it does not influence D1 and the other questions.

順序：試遊後アンケート（マーケットリサーチ、§4.2 の設問）→ **声の質問** → 録画の振り返り → 短いインタビュー（§6.3）。声の質問をアンケートの後に置くのは、D1 などの設問に影響させないため。

**The voice question** (S-074 ④; asked aloud, the facilitator ticks the box):

**声の質問**（S-074 ④、口頭で聞き、モデレーターがチェックする）：

> 「広場で、おじいさんとメロスが同じ場面にいたとき、声だけで、いまどちらが話しているか分かりましたか。」

□ すぐ分かった　□ ときどき迷った　□ 分からなかった　□ 同じ場面で二人の声を聞かなかった（not counted / 集計に含めない）

If they answer 「迷った」 or 「分からなかった」, ask one follow-up: 「どの場面でしたか。」 Note the recording time so you can go back to that moment during the review.

「迷った」か「分からなかった」と答えたら、「どの場面でしたか。」と 1 つだけ追加で聞く。録画の時刻を記録し、振り返りのときにその瞬間へ戻れるようにする。

**How to judge** (agreed by PM, 2026-10-10): if one person answers 「分からなかった」, or an old man ↔ メロス WHO appears in the recordings of two or more people, put the old man and Melos pair on the issue list and change candidates in M3 (ux-design 16.1, item 4). If the answers are only 「ときどき迷った」, UX judges from the screen at that moment and the audio output whether it is a voice problem or the screen not showing who is speaking.

**判定のしかた**（PM 同意済み、2026-10-10）：1 人でも「分からなかった」と答えるか、2 人以上の録画に老爺↔メロス の WHO が出たら、老爺とメロスの組を課題リストに入れ、M3 で候補を替える（ux-design 16.1 第 4 項）。「ときどき迷った」だけのときは、UX がその瞬間の画面と音声出力から、声の問題なのか、画面上で誰が話しているか分からないのかを判断する。

**Review**: pick 2–3 moments of these three kinds to watch again, and ask 「このとき、何を考えていましたか。」

**振り返り**：次の 3 種類の瞬間から 2〜3 個を選んで見返し、「このとき、何を考えていましたか。」と聞く。

- Set pieces at key moments (the promise, sunset, the ending);
  重要な瞬間の演出（約束、日没、エンディング）。
- Where they got stuck;
  行き詰まったところ。
- Moments when they opened the map or 記憶帳.
  地図や記憶帳を開いた瞬間。

Never pick the moment the pause card appeared.

一時停止カードが出た瞬間は選ばない。

## 5. After the session / 終了後

- The facilitator puts the filled-in sheet into the research storage the same day.
  モデレーターは記入済みのシートを当日のうちに調査の保管場所へ入れる。
- Market research tallies pause cards: total count ÷ number of sessions actually played. If it exceeds 1/20, tell PM the same day (playtest-plan §3.4).
  マーケットリサーチが一時停止カードを集計する：合計回数 ÷ 実際に試遊したセッション数。1/20 を超えたら当日中に PM に伝える（playtest-plan §3.4）。
- UX and market research compile the issue list together, ranked “blocker / problem but still playable / minor”, and hand it to PM (playtest-plan §7). The voice question gets its own row: how many people could not tell them apart, on what audio output, at which moment.
  UX とマーケットリサーチで一緒に課題リストをまとめ、「進行不能 / 問題はあるが続けられる / 軽微」の順に並べて PM に渡す（playtest-plan §7）。声の質問は別に 1 行設ける：何人が聞き分けられなかったか、どの音声出力か、どの瞬間か。

## 6. To fill in once the slice can be played to the end / スライスを最後まで遊べるようになったら補うこと

- The slice's actual scene order, and the original Japanese of buttons and panels, added to the timestamps in section 2 and to how “where” is written in section 3.
  スライスの実際のシーンの順序と、ボタンやパネルの日本語の原文を、第 2 節のタイムスタンプと第 3 節の「場所」の書き方に補う。
- The specific screens to prioritize when reviewing.
  振り返りで優先して見返す具体的な画面。
- Whether to ask players to wear earphones at the start: playtest-plan §4.1 says “use your own phone, wear earphones, as close to being at home as possible”; R1 follows this, and without earphones uses the phone speaker and notes it.
  冒頭でプレイヤーにイヤホンを付けてもらうか：playtest-plan §4.1 は「自分のスマートフォンで、イヤホンを付け、なるべく家にいるのと同じように」としている。R1 はこれに従い、イヤホンがなければ本体スピーカーで遊んでもらい、そのことを記録する。
- The R2 observation group is also asked the voice question, judged the same way as R1 (decided by PM on 10-10). R2's same-scene pairs are completed for a full playthrough, and the homeward road フィロストラトス × メロス pair must be asked: the D-025 blind listening did not test this pair, and in the recordings the two voices measure only about 1 semitone apart in pitch (ux-design 16.1).
  R2 の観察グループにも声の質問をし、判定は R1 と同じ（PM が 10-10 に決定）。R2 の同じシーンの組は完全な 1 局分で補い、帰り道の フィロストラトス × メロス は必ず聞く：D-025 のブラインド試聴ではこの組を試しておらず、録音を測ると 2 人の声の高さは約 1 半音しか違わない（ux-design 16.1）。

## Revision history / 改訂履歴

- v0.1 (2026-10-10): draft. The facilitator's exact words, the items to record first for each session (entry route, microphone, audio output, pause card count and which act), timestamps, codes (WHO added), the post-play voice question (S-074 ④), and what to do after the session.
  v0.1（2026-10-10）：下書き。モデレーターの言葉、セッションごとに最初に記録する項目（入り方、マイク、音声出力、一時停止カードの回数と第何幕か）、タイムスタンプ、コード（WHO を追加）、試遊後の声の質問（S-074 ④）、終了後の処理。
  - Same day: per market research's comments, WHO records who was taken for whom, and section 4 counts only old man ↔ メロス; section 1 adds the pre-play questionnaire and the spoken Q9 question; the judging rule has PM's agreement; the R2 observation group is asked too (decided by PM).
    同日：マーケットリサーチの意見に従い、WHO では誰を誰と取り違えたかを記録し、第 4 節では老爺↔メロス だけを数える。第 1 節に試遊前アンケートと Q9 の口頭質問を追加。判定のしかたは PM 同意済み。R2 の観察グループにも聞く（PM 決定）。
