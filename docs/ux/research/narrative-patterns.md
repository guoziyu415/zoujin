# Research: visualizing consequences in interactive narrative, time pressure, memory UI, sharing endings, AI narrative products, onboarding for voice play / 調査：インタラクティブな物語における結果の可視化、時間的プレッシャー、記憶の UI、エンディングの共有、AI 物語プロダクト、音声プレイのオンボーディング

Compiled by the UX thread on 2026-10-06 (searched by the research assistant, reviewed by UX). Every fact has a source; "inference" marks a guess, not something the source says. ux-design.md cites the conclusions here.

UX スレッドが 2026-10-06 に整理（調査アシスタントが検索し、UX が査読）。すべての事実に出典を付けている。「推測」は推測であり、出典の記述ではない。ux-design.md はここの結論を引用している。


Note: every fact has a source URL. Items marked "inference" are my own judgment. The body text is in English and Japanese; game titles and quotes keep their original language.

注記：すべての事実に出典の URL を付けている。「推測」と記したものは私自身の判断。本文は英語と日本語で書き、ゲーム名と引用は原文のまま残す。

---

## 1. How to visualize consequences and branches / 結果と分岐の可視化

**Detroit: Become Human flowchart / Detroit: Become Human のフローチャート**
- At the end of each chapter a flowchart shows how the player's choices in that chapter drove the story, along with what share of players worldwide made the same choice. One reviewer specifically mentions reaching an ending that "only 1% of players" got, and also the hundreds of locked nodes in the chart. https://www.rogerebert.com/features/brilliant-ambitious-detroit-become-human-challenges-way-we-play-games
  各章の終わりにフローチャートが表示され、その章でのプレイヤーの選択がどう物語を進めたかと、世界中のプレイヤーのうち何割が同じ選択をしたかがわかる。あるレビュアーは「プレイヤーの 1% しか」到達していないエンディングを引き当てたことに特に触れ、図の中に未解放のノードが何百もあることにも言及している。https://www.rogerebert.com/features/brilliant-ambitious-detroit-become-human-challenges-way-we-play-games
- The flowchart can be viewed both during a chapter and right after it, and players can go back to certain nodes and choose again. GamesRadar+ praised it as "the new gold standard for meaningful choice". GameSpot, on the other hand, felt the flowchart's explanations "hurt immersion" and wanted to be able to turn them off. https://en.wikipedia.org/wiki/Detroit:_Become_Human
  フローチャートは章の途中でも終了直後でも見られ、いくつかのノードに戻って選び直すこともできる。GamesRadar+ は「意味のある選択の新たな黄金基準」と称賛した。一方 GameSpot はフローチャートの説明が「没入感を損なう」と考え、オフにできるようにしてほしいとした。https://en.wikipedia.org/wiki/Detroit:_Become_Human
- David Cage admitted that hiding the untaken branches in earlier games was "probably not a good decision". Detroit draws every branch (untaken ones only appear as locked nodes), and it really did get players to replay; the goal was for at least 30% of players to see every branch. https://www.playstationlifestyle.net/2019/07/15/detroit-become-human-flowchart/amp/
  David Cage は、以前の作品で選ばなかった分岐を隠したのは「おそらく良い判断ではなかった」と認めた。Detroit はすべての分岐を描き（通っていない分岐はロックされたノードとしてだけ表示）、実際にプレイヤーを再プレイに向かわせた。目標は少なくとも 30% のプレイヤーにすべての分岐を見てもらうことだった。https://www.playstationlifestyle.net/2019/07/15/detroit-become-human-flowchart/amp/

**Telltale "X will remember that" / Telltale の "X will remember that"**
- This is a prompt that pops up when a character's attitude changes; it can be turned off in "Minimal" mode. https://en.wikipedia.org/wiki/The_Walking_Dead_(video_game)
  キャラクターの態度が変わったときに出る通知で、「Minimal」モードではオフにできる。https://en.wikipedia.org/wiki/The_Walking_Dead_(video_game)
- The criticism centers on the promise not being kept: whatever the player says to Clementine "doesn't really matter", and most branches flow back into the main line. https://www.denofgeek.com/games/the-walking-dead-false-promises-telltale/
  批判は約束が果たされていない点に集中している。プレイヤーが Clementine に何を言っても「実は関係ない」し、分岐の大半は本筋に戻ってしまう。https://www.denofgeek.com/games/the-walking-dead-false-promises-telltale/

**Life is Strange**
- After each chapter you can see what share of other players picked each option in that chapter. https://steamcommunity.com/app/319630/discussions/0/617328415076647103
  各章のあと、その章の各選択肢を他のプレイヤーがどんな割合で選んだかを見られる。https://steamcommunity.com/app/319630/discussions/0/617328415076647103
- Rewinding time lets players see the result of the choice in front of them first, but decisions from past chapters can't be changed. https://gameluster.com/?p=13782
  時間の巻き戻しで、目の前の選択肢の結果を先に見られるが、過去の章での決定は変えられない。https://gameluster.com/?p=13782
- The ending is a binary choice, "save the town or save Chloe", and some players were very disappointed, feeling all their earlier choices had been for nothing. https://www.gameinformer.com/b/features/archive/2015/10/27/coming-to-terms-with-life-is-strange-s-finale.aspx
  エンディングは「町を救うか Chloe を救うか」の二択で、一部のプレイヤーはひどく失望し、それまでの選択がすべて無駄になったと感じた。https://www.gameinformer.com/b/features/archive/2015/10/27/coming-to-terms-with-life-is-strange-s-finale.aspx

**Until Dawn**
- The moment a key decision is made, the game immediately tells you "this will cause a butterfly effect". Totems give premonitions of futures that can still be changed. Reviewers felt this gives every action "an almost paralyzing sense of dread", and that the dread is exactly what the game wants. https://unwinnable.com/2015/08/28/the-dread-of-knowing-in-until-dawn-uw58/
  重要な決定をした瞬間、ゲームはすぐに「これはバタフライエフェクトを起こす」と告げる。トーテムは変えられる未来の予兆を見せる。レビュアーは、これがあらゆる行動に「身動きできなくなるほどの恐怖感」をまとわせ、その恐怖こそゲームの狙いだと考えた。https://unwinnable.com/2015/08/28/the-dread-of-knowing-in-until-dawn-uw58/
- Some reviews felt most choices in the first half meant nothing; Destructoid called it a "gimmick" outright. https://en.wikipedia.org/wiki/Until_Dawn
  前半の選択の大半は無意味だとするレビューもあり、Destructoid ははっきり「ギミック」と呼んだ。https://en.wikipedia.org/wiki/Until_Dawn

**Knowledge graphs instead of branch charts / 分岐図の代わりに知識グラフ**
- **Outer Wilds ship's log**: can be viewed by location or as a web of clue relationships. "Learning new things is the only feedback the player gets." https://en.wikipedia.org/wiki/Outer_Wilds Players say it hints that "there's more to explore here", giving no quest markers yet never leaving them lost. https://steamcommunity.com/app/753640/discussions/0/2518023667592336699
  **Outer Wilds の宇宙船のログ**：場所ごとにも、手がかりの関係網としても見られる。「新しいことを知ることがプレイヤーの得る唯一のフィードバック」。https://en.wikipedia.org/wiki/Outer_Wilds プレイヤーによれば、ログは「ここにはまだ探索できるものがある」と示してくれ、クエストマーカーはないのに迷わせない。https://steamcommunity.com/app/753640/discussions/0/2518023667592336699
- **Return of the Obra Dinn**: deductions are only confirmed in batches of three correct ones, to stop players from brute-force guessing, though skilled players can still exploit it. https://filmstories.co.uk/?p=83249
  **Return of the Obra Dinn**：推理は 3 つ正解するごとにまとめて確定する。プレイヤーの総当たりを防ぐためだが、熟練したプレイヤーはそれでも抜け道を見つけられる。https://filmstories.co.uk/?p=83249
- **13 Sentinels**: "Analysis" mode organizes events and characters into an index, and a flowchart lets players jump between scenes. Some reviews say the plot is hard to follow and has too much jargon. https://en.wikipedia.org/wiki/13_Sentinels:_Aegis_Rim
  **13 Sentinels**：「Analysis」モードはイベントと人物を索引にまとめ、フローチャートと組み合わせてシーン間を移動できる。物語が追いにくく、用語が多すぎるというレビューもある。https://en.wikipedia.org/wiki/13_Sentinels:_Aegis_Rim
- **Heaven's Vault**: translated texts land on a timeline menu, but entries pile up until the menu is "almost unusable". https://www.slantmagazine.com/games/heavens-vault-review/
  **Heaven's Vault**：翻訳したテキストはタイムラインのメニューに載るが、項目がどんどん溜まり、メニューは「ほとんど使えない」状態になる。https://www.slantmagazine.com/games/heavens-vault-review/
- **The Stanley Parable**: the narrator reacts on the spot to the player's disobedience. The reviewer's summary: without branches, the narrator is just packaging; without the narrator, the branches mean nothing. https://media.gdcvault.com/GDC2014/GameNarrativeReview/Daily_Sean_TheStanleyParable.pdf
  **The Stanley Parable**：ナレーターがプレイヤーの反抗にその場で反応する。レビュアーのまとめでは、分岐がなければナレーターはただの包装で、ナレーターがいなければ分岐にも意味がない。https://media.gdcvault.com/GDC2014/GameNarrativeReview/Daily_Sean_TheStanleyParable.pdf
- **80 Days**: has a live feed showing the routes other players are currently taking. https://inklestudios.com/80days
  **80 Days**：他のプレイヤーがいま進んでいるルートを表示するリアルタイムのフィードがある。https://inklestudios.com/80days

**Transferable patterns / 応用できるパターン**
1. **A light hint in the moment, the full chart at the end of the chapter.** In the moment, only tell the player "something has changed" (like Until Dawn or Telltale), and save the full causal chain for the end of a chapter or day (like Detroit). (Inference) The 連鎖反応マップ normally shows only the first hop; distant consequences like "→ Selinuntius will be executed" are revealed at the dusk reckoning, to avoid spoilers.
   **その場では軽い通知、章末に完全な図。** その場では「何かが変わった」とだけ伝え（Until Dawn や Telltale のように）、完全な因果の連鎖は章や 1 日の終わりに広げる（Detroit のように）。「推測」連鎖反応マップは普段は最初の 1 段だけを表示し、「→ セリヌンティウスが処刑される」のような遠い結果は黄昏の清算のときに明かして、ネタバレを避ける。
2. **Draw unknown nodes as locked or as question marks, without content.** Detroit and Outer Wilds both reveal only the shape of the chart, not its content, which creates curiosity without spoilers.
   **未知のノードはロックや疑問符で描き、内容は書かない。** Detroit も Outer Wilds も図の形だけを見せて内容は見せず、好奇心を生みつつネタバレしない。
3. **If you say "will remember", you have to deliver.** Telltale is the cautionary example. (Inference) Every chain hint must be something that can be cited later (every line of the ending citing what the player did is exactly this loop).
   **「覚えている」と言うなら必ず果たす。** Telltale は反面教師。「推測」連鎖の通知はどれも、あとで引用できるものでなければならない（エンディングの一文一文がプレイヤーのしたことを引用するのは、まさにこの循環）。
4. **The chart must be filterable by character, day and place.** Heaven's Vault's lesson is that without filters the menu clogs up.
   **図は人物、日、場所で絞り込めるようにする。** Heaven's Vault の教訓は、絞り込みがないとメニューが詰まってしまうこと。

---

## 2. Time pressure / 時間的プレッシャー

- **Majora's Mask**: a 72-hour cycle, about 54 minutes of real time. A clock is always on screen, and NPCs follow fixed schedules. The Song of Time returns to the first day, the Inverted Song slows time down, and Double Time skips ahead. The Bombers' Notebook uses timelines to show when each character is around. Reviews widely praised the design, though some reviewers were so annoyed by the repeated restarts that they nearly quit. https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Majora%27s_Mask
  **Majora's Mask**：72 時間で 1 周し、現実では約 54 分。画面には常に時計があり、NPC は決まった日程で動く。Song of Time で 1 日目に戻り、Inverted Song で時間を遅くし、Double Time で時間を飛ばす。Bombers' Notebook はタイムラインで各キャラクターがいつどこにいるかを示す。設計は広く称賛されたが、繰り返しのやり直しにうんざりして投げ出しかけたレビュアーもいた。https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Majora%27s_Mask
  - The original design was 7 days. Eiji Aonuma said a week was "tiring to replay" and players couldn't remember who was where on which day, so it became 3 days. https://zeldauniverse.net/2019/05/07/zeldas-study-majoras-mask-was-originally-planned-to-have-a-weeklong-cycle/
    当初の設計は 7 日だった。青沼英二は 1 週間では「繰り返し遊ぶのが疲れる」し、誰が何日にどこにいるかをプレイヤーが覚えられないと述べ、3 日に変えた。https://zeldauniverse.net/2019/05/07/zeldas-study-majoras-mask-was-originally-planned-to-have-a-weeklong-cycle/
  - The 3DS remake lets you skip to any full hour, the notebook tracks almost every character, and save points became permanent saves. It was judged to have refined the structure without breaking the premise. https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Majora%27s_Mask_3D
    3DS のリメイク版では任意の正時へ飛べるようになり、ノートはほぼすべてのキャラクターを追跡し、セーブポイントは恒久セーブに変わった。前提を壊さずに構造を磨き上げたと評価された。https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Majora%27s_Mask_3D
  - Players are split: some "always feel I should be optimizing", some feel "it isn't really timing you, it's just a loop", and some feel the clock "makes the world more alive". https://www.zeldadungeon.net/forum/threads/does-majoras-mask-stress-you-out.69460/
    プレイヤーの意見は二極化している。「いつも効率を詰めなきゃと感じる」人もいれば、「実は時間を計っているわけではなく、ただのループ」と感じる人も、時計が「世界をより生き生きさせる」と感じる人もいる。https://www.zeldadungeon.net/forum/threads/does-majoras-mask-stress-you-out.69460/
- **Pentiment**: each day is split into work, prayer and meal periods; one long conversation uses up a period, and if you question the wrong person there's no time to go back. GameSpot disliked that "even having dinner with someone costs time", seeing it as punishing curiosity. https://www.gamespot.com/reviews/pentiment-review/1900-6417998/ Josh Sawyer's view is that RPGs are at their best when players "can control a lot, but not everything". https://www.gamedeveloper.com/design/pentiment-director-emphasizes-the-importance-of-rpg-players-not-controlling-everything
  **Pentiment**：1 日が仕事、祈り、食事などの時間帯に分かれ、長い会話 1 回で 1 つの時間帯を使い切る。間違った相手を調べると戻る時間がない。GameSpot は「人と夕食をとるだけでも時間がかかる」点を好まず、好奇心への罰だと考えた。https://www.gamespot.com/reviews/pentiment-review/1900-6417998/ Josh Sawyer は、RPG が最も良い状態なのはプレイヤーが「多くを制御できるが、すべては制御できない」ときだと考えている。https://www.gamedeveloper.com/design/pentiment-director-emphasizes-the-importance-of-rpg-players-not-controlling-everything
- **The Last Express**: runs in real time at 6 times real speed. When paused you can rewind to any moment; characters have their own schedules, and you miss what happens elsewhere at the same time. https://en.wikipedia.org/wiki/The_Last_Express
  **The Last Express**：現実の 6 倍の速さでリアルタイムに進む。一時停止すると任意の時点まで巻き戻せる。キャラクターはそれぞれ日程を持ち、同じ時刻に別の場所で起きることは見逃す。https://en.wikipedia.org/wiki/The_Last_Express
- **Dead Rising**: 72 in-game hours is about 6 real hours, each mission has its own timer, and the original allowed only one save; reviews criticized the save system and progression as unforgiving. https://en.wikipedia.org/wiki/Dead_Rising_(video_game) The Deluxe Remaster added autosave, and save points can fast-forward time. https://news.xbox.com/en-us/2024/09/19/dead-rising-deluxe-remaster-changes-improvements/
  **Dead Rising**：ゲーム内の 72 時間は現実の約 6 時間で、ミッションごとに個別のタイマーがある。オリジナル版はセーブが 1 つしかできず、レビューはセーブの仕組みと進行の寛容さのなさを批判した。https://en.wikipedia.org/wiki/Dead_Rising_(video_game) Deluxe Remaster ではオートセーブが加わり、セーブポイントで時間を早送りできる。https://news.xbox.com/en-us/2024/09/19/dead-rising-deluxe-remaster-changes-improvements/
- **Outer Wilds**: after 22 minutes the supernova goes off and everything resets; only the log is kept. https://en.wikipedia.org/wiki/Outer_Wilds
  **Outer Wilds**：22 分後に超新星爆発が起きてすべてリセットされ、ログだけが残る。https://en.wikipedia.org/wiki/Outer_Wilds
- **Frostpunk**: public sentiment is measured on two gauges, Hope and Discontent; small compromises in the Book of Laws snowball, mirroring "gradual normalization"; the developers deliberately end the game at its climax, "like a novel". https://en.wikipedia.org/wiki/Frostpunk
  **Frostpunk**：民心を Hope と Discontent の 2 つのゲージで測る。法典の小さな妥協が雪だるま式に膨らみ、「段階的な常態化」に対応している。開発者は意図的にクライマックスでゲームを終わらせ、「小説のように」している。https://en.wikipedia.org/wiki/Frostpunk

**Transferable patterns / 応用できるパターン**
1. **Time is spent by actions, in coarse periods, not in real time.** (Inference) Play sessions in a mobile browser are fragmented, which suits Pentiment's period system. A "deep talk" costs a period while small talk is free, avoiding what GameSpot called punishing curiosity.
   **時間は行動で消費し、粗い時間帯で区切り、リアルタイムにはしない。** 「推測」スマホブラウザのプレイセッションは細切れなので、Pentiment の時間帯制が合う。「じっくり話す」と 1 時間帯を使い、挨拶は無料にして、GameSpot の言う「好奇心への罰」を避ける。
2. **State the cost before time is spent.** (Inference) For example, "talking on with him will take you to dusk": the equivalent of Majora's clock plus the notebook, so players can anticipate it rather than having time suddenly taken away.
   **時間を使う前に代償を伝える。** 「推測」たとえば「このまま話し込むと黄昏になる」。Majora の時計と日程ノートに相当し、突然時間を差し引かれるのではなく、プレイヤーが予測できるようにする。
3. **There must be a safety net.** The Song of Time, the Outer Wilds loop and the Dead Rising remaster's autosave all turn "failure" into "knowledge". The player's remark that "it isn't really timing you" is the key to easing anxiety.
   **セーフティネットを用意する。** Song of Time、Outer Wilds のループ、Dead Rising リメイク版のオートセーブは、どれも「失敗」を「知識」に変えている。プレイヤーの言う「実は時間を計っているわけではない」が、不安を和らげる鍵。
4. **Notebook-style NPC schedules**, so that Melos's run and the time of the king's execution can be reasoned about and intercepted.
   **日程ノート式の NPC 時間表**で、メロスの走りと王の処刑の時刻を推理でき、先回りして止めに行けるようにする。

---

## 3. Character memory and relationship UI / 登場人物の記憶と関係の UI

- **Hades**: Kasavin's method: "What would these characters talk about, what would they notice? Add those interactions." The system itself is simple; it just keeps adding new conditions to check. https://gamespot.com/articles/hades-writer-explains-script-philosophy-after-player-discovers-incredible-detail/1100-6482650/ He compares the effect to "someone noticing you got a haircut or new shoes". https://www.screenhub.com.au/news-article/features/digital/jini-maxwell/hades-greg-kasavin-breaks-down-supergiants-unique-approach-to-narrative-262459
  **Hades**：Kasavin のやり方は「この人物たちは何を話し、何に気づくだろうか？ そのやりとりを足す」。仕組み自体は単純で、新しい判定条件を足し続けるだけ。https://gamespot.com/articles/hades-writer-explains-script-philosophy-after-player-discovers-incredible-detail/1100-6482650/ 彼はこの効果を「髪を切ったことや新しい靴に誰かが気づいてくれる」ことにたとえている。https://www.screenhub.com.au/news-article/features/digital/jini-maxwell/hades-greg-kasavin-breaks-down-supergiants-unique-approach-to-narrative-262459
- **Baldur's Gate 3**: approval changes pop up in the top left during dialogue, and otherwise in a box similar to a quest update. Approval has 7 tiers, each with a text description. Companions must be nearby for approval to change. https://bg3.wiki/wiki/Approval PC Gamer's complaint about save-scumming: "How did saying *that* lead to *that*? That's not what I meant at all!" https://tech.yahoo.com/general/articles/were-save-scumming-baldurs-gate-234103643.html
  **Baldur's Gate 3**：会話中は好感度の変化が左上に出て、普段はクエスト更新に似た枠で表示される。好感度は 7 段階で、段階ごとに文章の説明がある。仲間が近くにいないと好感度は変わらない。https://bg3.wiki/wiki/Approval PC Gamer のロードし直しへの愚痴：「*あの一言*がどうして*あんなこと*になるんだ？ そんなつもりじゃなかった！」https://tech.yahoo.com/general/articles/were-save-scumming-baldurs-gate-234103643.html
- **Disco Elysium**: "say something stupid and they'll remember; help someone and they'll remember that too". Repeated words and deeds become Thoughts, which take 30 minutes to 3 days of in-game time to "internalize". https://gamebanshee.com/39hc9
  **Disco Elysium**：「ばかなことを言えば覚えているし、人を助ければそれも覚えている」。繰り返した言動は Thought になり、「内面化」するのにゲーム内時間で 30 分から 3 日かかる。https://gamebanshee.com/39hc9
- **Persona 5**: the Confidant relationship system is tied to the day/night calendar, with Palace deadlines running at the same time. https://en.wikipedia.org/wiki/Persona_5
  **Persona 5**：コープ（Confidant）の関係システムは昼夜のカレンダーと結びつき、同時にパレスの期限もある。https://en.wikipedia.org/wiki/Persona_5
- **ChatGPT memory**: the entry point is "Settings > Personalization > Memory"; memories can be edited directly, or you can choose "don't bring this up again". Deleting a conversation doesn't delete the memories created from it. Temporary chats don't create memories. https://help.openai.com/en/articles/8590148-memory-faq
  **ChatGPT のメモリ**：入口は「設定 > パーソナライズ > メモリ」で、直接編集することも「今後この話題に触れない」を選ぶこともできる。会話を削除しても、その会話から作られたメモリは消えない。一時チャットではメモリは作られない。https://help.openai.com/en/articles/8590148-memory-faq
- **Character.AI**: in May 2026 Story Memory replaced the old 400-character memory box, accessed from a notebook icon at the top of the chat. The paid tier has automatically captured Facts, but a wrongly captured fact keeps affecting replies until the user fixes it by hand. There is also "Memory Usage" showing current memory use, and long-pressing a message can Pin its original text. User opinion is split; some paying users say the automatic memory "isn't very good". https://www.roborhythms.com/character-ai-adds-chat-memories/
  **Character.AI**：2026 年 5 月に Story Memory が従来の 400 文字の記憶欄に取って代わり、入口はチャット上部のノートのアイコン。有料プランには自動で取り込まれる Facts があるが、誤って取り込まれるとユーザーが手で直すまで応答に影響し続ける。ほかに現在の記憶の使用量を示す「Memory Usage」があり、メッセージを長押しすると原文を Pin できる。ユーザーの評価は二極化しており、自動記憶は「あまり良くない」と言う有料ユーザーもいる。https://www.roborhythms.com/character-ai-adds-chat-memories/
- **Replika**: the Memory tab lets you add memories by hand, and liking a memory reinforces it. The official help warns that deleting memories affects its ability to recall details. https://help.replika.com/hc/en-us/articles/37208679176077-How-does-Replika-s-memory-work
  **Replika**：Memory タブで記憶を手動で追加でき、「いいね」でその記憶を強められる。公式は、記憶を削除すると細部を思い出す力に影響すると注意している。https://help.replika.com/hc/en-us/articles/37208679176077-How-does-Replika-s-memory-work
- **Privacy UX guidance**: Google PAIR recommends showing users "what data about you was collected and what it is used for", telling them whether they can delete or reset it, and giving "because you…" explanations. https://pair.withgoogle.com/chapter/People%20+%20AI%20Guidebook%20-%20Explainability%20+%20Trust.pdf Mozilla reviewed 11 romantic AI apps, and more than half did not allow data to be deleted. https://www.euronews.com/2024/02/14/stealing-hearts-data-and-privacy-why-you-should-be-careful-of-ai-partners
  **プライバシー UX のガイド**：Google PAIR は、「あなたについてどんなデータを集め、何に使うのか」をユーザーに示し、削除やリセットができるかを伝え、「あなたが……したので」という形の説明をすることを勧めている。https://pair.withgoogle.com/chapter/People%20+%20AI%20Guidebook%20-%20Explainability%20+%20Trust.pdf Mozilla が恋愛 AI アプリ 11 本を評価したところ、半数以上がデータの削除を認めていなかった。https://www.euronews.com/2024/02/14/stealing-hearts-data-and-privacy-why-you-should-be-careful-of-ai-partners

**Transferable patterns / 応用できるパターン**
1. **The witness rule.** Borrow BG3's "only counts if nearby". (Inference) Each memory in the 記憶帳 is labeled with its source: seen firsthand, heard from someone, or village rumor. This is consistent with the world's logic and also explains "how does he know".
   **目撃のルール。** BG3 の「近くにいるときだけ数える」を取り入れる。「推測」記憶帳の記憶ごとに出所を記す：自分の目で見た、人から聞いた、村のうわさ。世界の論理にかない、「なぜ彼が知っているのか」の説明にもなる。
2. **Write memories in the character's voice and link them to the original moment.** Hades-style "being noticed" plus PAIR's "because you…". For example: 「セリヌンティウスは覚えている——あの夜、あなたが隣に座っていたことを（第2日・夜）」 ("Selinuntius remembers: that night you sat beside him (Day 2, night)").
   **記憶は登場人物の口調で書き、元の瞬間にリンクする。** Hades 式の「気づいてもらえる」と PAIR の「あなたが……したので」の組み合わせ。例：「セリヌンティウスは覚えている——あの夜、あなたが隣に座っていたことを（第2日・夜）」。
3. **Delete "story facts" and "verbatim data" separately.** ChatGPT shows these two layers need to be managed separately. (Inference) Deleting the recorded audio or transcript of what was said doesn't have to delete the story fact. Either let the player choose, or tell them clearly "after deletion he will forget this" (see Replika's warning).
   **「物語上の事実」と「発話そのもののデータ」は別々に削除する。** ChatGPT は、この 2 層を分けて管理すべきことを示している。「推測」発話の録音や文字起こしを消しても、物語上の事実まで消す必要はない。プレイヤーにどちらかを選ばせるか、「削除すると彼はこのことを忘れる」とはっきり伝える（Replika の注意書きを参考に）。
4. **Prevent "that's not what I meant".** When the narrative agent turns speech into events, it should first do a light confirmation, e.g. "Do you mean to stop Melos?", before writing it into the causal graph. (Inference) This addresses the root cause of BG3 save-scumming.
   **「そんなつもりじゃなかった」を防ぐ。** 物語エージェントが音声をイベントに変えるときは、因果グラフに書き込む前に「メロスを止めたいのですか？」のような軽い確認をする。「推測」これは BG3 でロードし直しが起きる根本原因への対策になる。

---

## 4. Endings, recaps and sharing / エンディング、振り返り、共有

- **Detroit**: the end-of-chapter flowchart plus global percentages; "only 1%" is itself something to show off. (Same source as above, RogerEbert.)
  **Detroit**：章末のフローチャートと世界全体の割合。「わずか 1%」はそれ自体が自慢の種になる。（出典は上と同じ、RogerEbert）
- **Frostpunk**: the ending passes moral judgment on the player ("Was it worth it?"). Players complain the judgment only looks at which laws were passed, not at the survival rate: "Where exactly did I cross the line?" https://steamcommunity.com/app/323190/discussions/0/1696045708654961998
  **Frostpunk**：エンディングはプレイヤーに道徳的な判定を下す（"Was it worth it?"）。プレイヤーは、判定が制定した法律だけを見て生存率を見ないと不満を言う：「いったいどこで一線を越えたんだ？」 https://steamcommunity.com/app/323190/discussions/0/1696045708654961998
- **Undertale**: even a reset doesn't wash away the consequences of the genocide route, so players stop treating the world as a playground without consequences. https://reporter.rit.edu/5437/culture/undertale-and-permanent-consequences-in-video-games
  **Undertale**：リセットしても虐殺ルートの結果は消えないため、プレイヤーは世界を結果のない遊び場とみなさなくなる。https://reporter.rit.edu/5437/culture/undertale-and-permanent-consequences-in-video-games
- **NieR:Automata Ending E**: players can sacrifice their own save data to help strangers. https://www.siliconsasquatch.com/blog/2017/12/27/goty-2017-best-moment
  **NieR:Automata のエンディング E**：プレイヤーは自分のセーブデータを犠牲にして見知らぬプレイヤーを助けられる。https://www.siliconsasquatch.com/blog/2017/12/27/goty-2017-best-moment
- **Spotify Wrapped**: in 2019 intern Jewel Ham turned it into a Stories format, and users started sharing it like a "horoscope". https://www.refinery29.com/en-us/2020/12/10208481/jewel-ham-artist-spotify-wrapped-internship In 2022, 16 "Listening Personality" types were added. https://newsroom.spotify.com/2022-11-30/everything-you-need-to-know-about-2022-wrapped/ The design team said "there's nowhere to hide in Wrapped, you have to own it", and personalized motion graphics were the core of that edition. https://www.itsnicethat.com/features/spotify-wrapped-campaign-identity-2022-graphic-design-301122
  **Spotify Wrapped**：2019 年にインターンの Jewel Ham が Stories 形式に変え、ユーザーは「星占い」のように共有し始めた。https://www.refinery29.com/en-us/2020/12/10208481/jewel-ham-artist-spotify-wrapped-internship 2022 年には 16 種類の「Listening Personality」が加わった。https://newsroom.spotify.com/2022-11-30/everything-you-need-to-know-about-2022-wrapped/ デザインチームは「Wrapped には隠れる場所がない、自分のものとして引き受けるしかない」と語り、パーソナライズされたモーショングラフィックスがこの版の核だった。https://www.itsnicethat.com/features/spotify-wrapped-campaign-identity-2022-graphic-design-301122
- **Duolingo Year in Review**: the top 10% of users by XP accounted for more than half of the shares, so the team added "learner style" personas so ordinary users would also have something to show off. https://blog.duolingo.com/year-in-review-behind-the-scenes
  **Duolingo の年間振り返り**：XP 上位 10% のユーザーがシェアの半分以上を占めていたため、チームは「学習スタイル」のペルソナを加え、普通のユーザーにも見せびらかせるものを用意した。https://blog.duolingo.com/year-in-review-behind-the-scenes
- **Bandersnatch**: 94% of viewers actively made choices. Netflix tracked the choice ratio at every node; the train ending was the hardest to reach. The protagonist Stefan resists the viewer's choices, which keeps the character consistent. https://www.hollywoodreporter.com/live-feed/black-mirror-team-complexity-bandersnatch-netflix-data-1213270
  **Bandersnatch**：視聴者の 94% が自分で選択をした。Netflix は各ノードの選択の割合を追跡し、列車のエンディングが最も到達しにくかった。主人公 Stefan は視聴者の選択に抵抗し、それによってキャラクターの一貫性を保っている。https://www.hollywoodreporter.com/live-feed/black-mirror-team-complexity-bandersnatch-netflix-data-1213270

**Transferable patterns / 応用できるパターン**
1. **One card carries identity, rarity and beauty together.** Identity is a title (like Listening Personality), rarity is "only 12% of people…", beauty comes from generated personalized visuals, and the format is 9:16 Stories.
   **1 枚のカードに、アイデンティティ、希少性、美しさを同時に載せる。** アイデンティティは称号（Listening Personality のようなもの）、希少性は「わずか 12% の人だけが……」、美しさは生成できるパーソナライズされたビジュアルから生まれ、形式は 9:16 の Stories。
2. **Everyone has one rare thing.** Only the players with the best numbers can show off a ranking (Duolingo's top 10% effect). (Inference) Pick the rarest thing from each player's route and put it on the card.
   **誰にでも 1 つは珍しい点がある。** 順位を見せびらかせるのは数字の最も良いプレイヤーだけ（Duolingo の上位 10% 現象）。「推測」各プレイヤーのルートから最も珍しい出来事を選び、カードに載せる。
3. **Verdicts need evidence.** Frostpunk's lesson: an ending verdict must cite specific actions, and judge along multiple dimensions. Your design of "every epilogue line cites the player's actions" avoids exactly this problem.
   **判定には証拠を添える。** Frostpunk の教訓：エンディングの判定は具体的な行動を引用し、評価軸は多様でなければならない。「エピローグの一文一文がプレイヤーの行動を引用する」という皆さんの設計は、まさにこの問題を避けられる。
4. **With two endings, avoid "a final binary choice that makes everything before it pointless"** (Life is Strange's problem). The world ending can be settled by the original story's causal convergence, while the personal ending accumulates all of the player's choices.
   **2 つのエンディングでは「最後の二択でそれまでが無駄になる」ことを避ける**（Life is Strange の問題）。世界のエンディングは原作の因果の収束で決め、個人のエンディングはプレイヤーのすべての選択を積み上げる。

---

## 5. AI-native narrative products and research / AI ネイティブな物語プロダクトと研究

**c.ai Books (launched 2026-04-16) / c.ai Books（2026-04-16 公開）**
- Three ways to play: Book Arc follows the original, Go off script improvises freely, and community-made AU adaptations. There is also TapTale, "coming soon", offering pre-written options besides typing. Free users get only a few turns. https://blog.character.ai/cai-books/
  遊び方は 3 つ：原作に沿う Book Arc、自由に展開する Go off script、コミュニティが作った AU 翻案。さらに「近日公開」の TapTale は、タイピングのほかに書かれた選択肢を用意する。無料ユーザーは少ないターン数しか使えない。https://blog.character.ai/cai-books/
- The library has 20-plus public-domain books from Project Gutenberg. https://www.creativeainews.com/blog/character-ai-books-playable-classic-literature/
  ライブラリにはグーテンベルクのパブリックドメインの本が 20 冊以上ある。https://www.creativeainews.com/blog/character-ai-books-playable-classic-literature/
- The flow is "pick a book → pick who you are → start chatting". Testers point out it is text-only with no voice, and "no continuity between sessions". https://medium.com/activated-thinker/the-childhood-dream-of-talking-to-book-characters-just-became-real-4c85d5196a9b
  流れは「本を選ぶ → 自分が誰かを選ぶ → 話し始める」。体験者は、文字だけで音声がなく、「セッション間の連続性がない」と指摘している。https://medium.com/activated-thinker/the-childhood-dream-of-talking-to-book-characters-just-became-real-4c85d5196a9b
- Media coverage is set against ongoing safety controversies. https://www.digitaltrends.com/computing/character-ai-turns-books-into-roleplay-bots-amid-ongoing-safety-concerns/ Since 2025-11-25, c.ai has banned minors from talking with chatbots. https://en.wikipedia.org/wiki/Character.ai
  報道の背景には安全性をめぐる論争が続いていることがある。https://www.digitaltrends.com/computing/character-ai-turns-books-into-roleplay-bots-amid-ongoing-safety-concerns/ c.ai は 2025-11-25 から未成年者がチャットボットと会話することを禁止している。https://en.wikipedia.org/wiki/Character.ai
- (Inference) Where we can differentiate: voice, 3D scenes, persistent memory, the causal graph, ending cards.
  「推測」差別化できる点：音声、3D シーン、永続的な記憶、因果グラフ、エンディングカード。

**Other products / ほかのプロダクト**
- **Hidden Door** (launched 2025-08): has an omniscient AI Narrator; story cards can be shared across stories; the catalog includes Pride and Prejudice and The Wizard of Oz. https://getcoai.com/news/hidden-door-launches-ai-role-playing-platform-with-creator-revenue-sharing
  **Hidden Door**（2025-08 公開）：全知の AI Narrator がいて、ストーリーカードは物語をまたいで共有できる。作品には Pride and Prejudice や Wizard of Oz がある。https://getcoai.com/news/hidden-door-launches-ai-role-playing-platform-with-creator-revenue-sharing
- **AI Dungeon**: officially admits the AI can only look back over limited context, and recommends Memory, retry and edit as remedies. https://help.aidungeon.io/faq/why-does-the-ai-forget-or-mix-things-up Players complain about repetition and about dead characters showing up again. https://reddit.birdcat.cafe/r/AIDungeon/comments/1iw583o/ai_dungeon_got_worst
  **AI Dungeon**：AI は限られたコンテキストしか振り返れないと公式に認め、Memory、リトライ、編集で補うよう勧めている。https://help.aidungeon.io/faq/why-does-the-ai-forget-or-mix-things-up プレイヤーは繰り返しや、死んだキャラクターがまた現れることに不満を言っている。https://reddit.birdcat.cafe/r/AIDungeon/comments/1iw583o/ai_dungeon_got_worst
- **Inworld Origins**: off-topic questions get deflected by NPCs; latency makes lines overlap. https://www.axios.com/2023/08/07/inworld-ai-origins-demo Another tester said the characters "talk too much and don't stop when interrupted". https://newatlas.com/games/inworld-origins-ai-npc After trying two AI NPC demos, PC Gamer concluded: "You can say anything, but you can't do anything." https://www.pcgamer.com/gaming-industry/i-tried-two-demos-of-machine-learning-ai-npcs-and-they-didnt-convince-me-the-ai-will-lead-to-anything-that-immersive-sims-like-deus-ex-havent-already-done-better/
  **Inworld Origins**：本筋から外れた質問は NPC にかわされる。遅延のせいでセリフが重なる。https://www.axios.com/2023/08/07/inworld-ai-origins-demo 別の体験者は、キャラクターが「しゃべりすぎで、割り込んでも止まらない」と述べた。https://newatlas.com/games/inworld-origins-ai-npc PC Gamer は AI NPC のデモを 2 本試して、「何でも言えるが、何もできない」と結論づけた。https://www.pcgamer.com/gaming-industry/i-tried-two-demos-of-machine-learning-ai-npcs-and-they-didnt-convince-me-the-ai-will-lead-to-anything-that-immersive-sims-like-deus-ex-havent-already-done-better/
- **Whispers from the Star** (2025-08-14): you communicate by voice, text or video call. At launch it had 92% positive on Steam (202 reviews). https://www.notebookcheck.net/Steam-launch-New-interactive-fiction-game-debuts-to-Very-Positive-reviews-may-divide-gamers-over-heavy-AI-integration.1087821.0.html The Steam page now shows 1,663 reviews, 80% positive. https://store.steampowered.com/app/3730100 Eurogamer Germany gave it only 20/100, saying it "quickly becomes mediocre and collects lots of data"; users complain that Stella, supposedly an expert, relies on the player's guidance for everything. https://www.metacritic.com/game/whispers-from-the-star/
  **Whispers from the Star**（2025-08-14）：音声、文字、ビデオ通話でやりとりできる。公開時の Steam の好評率は 92%（202 件のレビュー）。https://www.notebookcheck.net/Steam-launch-New-interactive-fiction-game-debuts-to-Very-Positive-reviews-may-divide-gamers-over-heavy-AI-integration.1087821.0.html 現在の Steam ページは 1,663 件のレビューで好評率 80%。https://store.steampowered.com/app/3730100 Eurogamer ドイツ版は 20/100 しか付けず、「すぐに平凡になり、しかも大量のデータを集める」とした。専門家のはずの Stella がかえって何でもプレイヤーの指示に頼る、というユーザーの不満もある。https://www.metacritic.com/game/whispers-from-the-star/
- **Lessons from Façade**: the system failed to understand the player about 30% of the time, and the drama manager's deflection lines held the experience together. Players deliberately role-played as zombies or aliens to probe the system's limits. https://grandtextauto.soe.ucsc.edu/2008/03/18/ep-86-learning-from-facade
  **Façade の教訓**：システムは約 30% の時間プレイヤーを理解できず、ドラママネージャーのはぐらかしのセリフで体験を支えていた。プレイヤーはわざとゾンビや宇宙人を演じて、システムの限界を試した。https://grandtextauto.soe.ucsc.edu/2008/03/18/ep-86-learning-from-facade

**Research (2025-2026) / 研究（2025-2026）**
- **Dramamancer** (2026-01): authors define storylets (pairs of events and outcomes), and an interpretation module judges whether the player's action triggered an event's condition. https://arxiv.org/html/2601.18785
  **Dramamancer**（2026-01）：作者が storylet（イベントと結果の組）を定義し、解釈モジュールがプレイヤーの行動がイベントの条件を満たしたかを判定する。https://arxiv.org/html/2601.18785
- **ACL 2025 paper "Towards Enhanced Immersion and Agency for LLM-based Interactive Drama"**: each reflection changes at most one plot point. One recorded failure mode is "script leakage": the global agent doing the reflection can see the whole script, which led characters to reveal later plot early. Another failure mode is hallucinating scenes that don't exist. https://arxiv.org/html/2502.17878v2
  **ACL 2025 の論文「Towards Enhanced Immersion and Agency for LLM-based Interactive Drama」**：1 回の振り返りで変える筋は最大 1 つ。記録された失敗の 1 つは「台本の漏洩」で、振り返りを担う全体エージェントが台本全体を見られるため、キャラクターが後の筋を先に口にしてしまった。もう 1 つの失敗は、存在しない場面を幻覚で作り出すこと。https://arxiv.org/html/2502.17878v2
- **Evaluating LLMs from a narrative-planning perspective** (2025-06): LLMs are weak at character intentions and dramatic conflict, and improve markedly when connected to a symbolic planner. https://arxiv.org/html/2506.10161v1
  **物語プランニングの観点からの LLM 評価**（2025-06）：LLM は登場人物の意図や劇的な対立が苦手で、記号的なプランナーとつなぐと明らかに改善する。https://arxiv.org/html/2506.10161v1
- **Moral RolePlay** (2025-11): the less moral a character is, the less convincingly LLMs play it; deceptive and manipulative traits are the hardest. https://arxiv.org/abs/2511.04962v1 The matching user complaint is that c.ai villains apologize halfway through and "go soft". https://www.roborhythms.com/character-ai-bots-too-wholesome/
  **Moral RolePlay**（2025-11）：不道徳なキャラクターほど LLM は似せて演じられない。欺瞞や操作の特性が最も難しい。https://arxiv.org/abs/2511.04962v1 対応するユーザーの不満は、c.ai の悪役が途中で謝り「穏やかになる」こと。https://www.roborhythms.com/character-ai-bots-too-wholesome/
- **Sycophancy**: in April 2025 OpenAI rolled back an update because GPT-4o was excessively flattering. https://www.axios.com/2025/07/07/ai-sycophancy-chatbots-mental-health
  **迎合の問題**：2025 年 4 月、OpenAI は GPT-4o のお世辞が過剰だったためアップデートを取り消した。https://www.axios.com/2025/07/07/ai-sycophancy-chatbots-mental-health
- **Symbolically Scaffolded Play** (N=10, a voice detective game): there was no significant difference between high-constraint and low-constraint prompts; players mainly noticed surface issues such as latency. https://arxiv.org/html/2510.25820v1 Another study found that a "be concise, don't overact" prompt works. https://arxiv.org/html/2510.13586v1
  **Symbolically Scaffolded Play**（N=10、音声の探偵ゲーム）：制約の強いプロンプトと弱いプロンプトの間に有意な差はなく、プレイヤーが主に気づいたのは遅延のような表面的な問題だった。https://arxiv.org/html/2510.25820v1 別の研究では、「簡潔に、大げさに演じない」というプロンプトが効果的だった。https://arxiv.org/html/2510.13586v1

**Transferable patterns / 応用できるパターン**
1. **Give the causal graph only to the narrative agent, not to NPCs.** Each NPC only gets the part "it knows", which prevents script leakage and spoilers.
   **因果グラフは物語エージェントにだけ渡し、NPC には渡さない。** 各 NPC は「自分が知っている」部分だけを受け取り、台本の漏洩とネタバレを防ぐ。
2. **Hand causal simulation to the symbolic layer (your causal graph) and let the LLM handle only expression.** This matches the neuro-symbolic research findings above.
   **因果のシミュレーションは記号層（皆さんの因果グラフ）に任せ、LLM は表現だけを担う。** 上のニューロシンボリック研究の結論に対応している。
3. **The tyrant Dionys needs dedicated villain constraints and evals.** (Inference) Otherwise he will very likely go soft halfway through, as the Moral RolePlay results show.
   **暴君ディオニスには専用の悪役の制約と評価が必要。** 「推測」さもないと途中で軟化する可能性が高い。Moral RolePlay の結果がそれを示している。
4. **Keep lines short, make them interruptible, and tell the player "what saying what can change".** This avoids what PC Gamer called "say anything but do nothing".
   **セリフは短く、割り込めるようにし、「何を言えば何が変わるか」をプレイヤーに伝える。** PC Gamer の言う「何でも言えるが何もできない」を避けられる。

---

## 6. Onboarding for free-form voice play / 自由な音声プレイのオンボーディング

- **The NPC asks first**: Whispers from the Star opens with Stella asking in a panic, "How do I get out of this escape pod?". Reviews also warn that the game requires good English. https://www.gamestar.de/artikel/scifi-survival-whsipers-from-the-star-steam-ausprobiert,3437962.html
  **NPC が先に質問する**：Whispers from the Star は、Stella が慌てて「どうすれば脱出ポッドから出られるの？」と尋ねるところから始まる。レビューは、このゲームには高い英語力が必要だとも注意している。https://www.gamestar.de/artikel/scifi-survival-whsipers-from-the-star-steam-ausprobiert,3437962.html
- **Alexa voice design guide**: end with a question to cue the user that it's their turn to speak; offer clear options ("Brie or Gouda?") instead of asking "What would you like?"; give example phrasings when the user asks for help; when it doesn't understand, rephrase the question instead of repeating it verbatim. https://developer.amazon.com/fr/designing-for-voice/what-alexa-says/
  **Alexa の音声デザインガイド**：質問で終えて、ユーザーに話す番だと知らせる。「何がいいですか？」ではなく、はっきりした選択肢を出す（「ブリーとゴーダ、どちら？」）。助けを求められたら例となる言い方を示す。聞き取れなかったときは同じ文をくり返さず、言い方を変えて聞き直す。https://developer.amazon.com/fr/designing-for-voice/what-alexa-says/
- **Prompt starters**: give 3-4 concrete starter prompts. Don't write empty lines like "Ask me anything", and tuck them away once returning users have used them. https://aiuxplayground.com/pattern/prompt-starters
  **プロンプトの書き出し例（Prompt starters）**：具体的な書き出しの例を 3〜4 個示す。「Ask me anything」のような中身のない言葉は書かず、慣れたユーザーが使ったあとはしまう。https://aiuxplayground.com/pattern/prompt-starters
- **Empty states in AI products** (UX Collective, 2026-05): recommends illustrative examples, clear verbs, disclosing limits up front, and designing a moment where the user "accidentally gets something done". The author says first-session churn is about 70%; I did not verify this figure, it is the author's claim. https://uxdesign.cc/the-death-of-the-empty-state-in-ai-products-2026-e11439fbb688
  **AI プロダクトの空の状態**（UX Collective、2026-05）：手本となる例、はっきりした動詞、制限の事前開示、そして「うっかり何かを成し遂げてしまう」瞬間を設計することを勧めている。著者は初回セッションの離脱率を約 70% としているが、この数字は検証しておらず、著者の主張である。https://uxdesign.cc/the-death-of-the-empty-state-in-ai-products-2026-e11439fbb688
- **Other approaches**: c.ai's TapTale offers pre-written options besides typing (same source as above, the official c.ai blog); Event[0] has players type to talk with an AI whose attitude changes with how the player treats it. https://en.wikipedia.org/wiki/Event_0
  **ほかのやり方**：c.ai の TapTale はタイピングのほかに書かれた選択肢を用意する（出典は上と同じ、c.ai 公式ブログ）。Event[0] ではプレイヤーが文字を打って AI と会話し、AI の態度はプレイヤーの接し方で変わる。https://en.wikipedia.org/wiki/Event_0

**Transferable patterns / 応用できるパターン**
1. **Identity decides the first line.** (Inference) The stonemason's apprentice is asked by the master right at the start, "Are you taking the stone to town today?"; the shepherd boy is asked about a lost sheep. The NPC asks first and offers two or three concrete options.
   **身分が最初の一言を決める。** 「推測」石工の弟子は始まってすぐ親方に「今日は町へ石を届けに行くか？」と聞かれ、羊飼いの少年ははぐれた羊のことを聞かれる。NPC が先に質問し、具体的な選択肢を 2、3 個添える。
2. **Put context-aware hint cards next to the voice button.** One or two lines, changing with the scene, fading out once used. For example, by the river: "Ask him why he's in such a hurry".
   **音声ボタンの横に状況に応じたヒントカードを置く。** 1〜2 文で、シーンに合わせて変わり、使ったら消える。たとえば川辺では「なぜそんなに急いでいるのか聞いてみる」。
3. **A safe first move.** (Inference) Within the first 5 minutes, design one small action that lights up the first line on the 連鎖反応マップ, e.g. carrying a message for Selinuntius. Let the player "get one thing done" first, then understand the system.
   **安全な最初の一手。** 「推測」最初の 5 分以内に小さな行動を 1 つ用意し、連鎖反応マップに最初の 1 本の線が灯るようにする。たとえばセリヌンティウスの伝言を届ける。プレイヤーにまず「何か 1 つやり遂げて」もらい、それから仕組みを理解してもらう。
4. **When it doesn't understand, catch it in the character's voice and ask again in different words.** Learn from Façade and Alexa. Also state the boundaries at the start: "Your words can change people's choices, but not the weather or the gods."
   **聞き取れなかったときは登場人物の口調で受け止め、言い方を変えて聞き直す。** Façade と Alexa に学ぶ。同時に、冒頭で境界をはっきり示す：「あなたの言葉は人々の選択を変えられるが、天気や神々は変えられない。」

---

**What I couldn't verify this time**: Pi's memory interface, Mass Effect, Persona's rank-up animation, the specific interaction of the Heaven's Vault timeline, how Pentiment presents its endings. None of these are written up above.

**今回確認できなかった内容**：Pi の記憶インターフェース、Mass Effect、Persona のランクアップ演出、Heaven's Vault のタイムラインの具体的な操作、Pentiment のエンディングの見せ方。いずれも上では取り上げていない。
