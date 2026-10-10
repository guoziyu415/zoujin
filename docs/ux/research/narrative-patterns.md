# 调研：互动叙事里的后果可视化、时间压力、记忆 UI、结局分享、AI 叙事产品、语音新手引导

UX 线程 2026-10-06 整理（调研助手检索，UX 审读）。每条事实都附来源；「推断」是推测，不是来源原话。ux-design.md 引用这里的结论。


说明：每条事实都附了来源 URL。标「推断」的是我自己的判断。正文用中文，游戏名和引语保留原文。

---

## 1. 后果和分支怎么可视化

**Detroit: Become Human 流程图**
- 每章结束时显示一张流程图，列出这一章里玩家的选择怎样一路推进剧情，还能看到全世界有多少比例的玩家做了同样的选择。有评论者特别提到自己打出了一个"只有 1% 玩家"拿到的结局，也提到图里有几百个没解锁的节点。https://www.rogerebert.com/features/brilliant-ambitious-detroit-become-human-challenges-way-we-play-games
- 章节进行中和刚结束时都能看流程图，也可以回到某些节点重新选。GamesRadar+ 称赞它是"有意义选择的新黄金标准"。GameSpot 则认为流程图的说明"损害沉浸感"，希望能关掉。https://en.wikipedia.org/wiki/Detroit:_Become_Human
- David Cage 承认，以前的作品把没走的分支藏起来"大概不是好决定"。Detroit 把所有分支都画出来（没走过的只显示为锁住的节点），结果真的让玩家去重玩，目标是至少 30% 的玩家看遍所有分支。https://www.playstationlifestyle.net/2019/07/15/detroit-become-human-flowchart/amp/

**Telltale "X will remember that"**
- 这是角色态度发生变化时弹出的提示，可以在 "Minimal" 模式里关掉。https://en.wikipedia.org/wiki/The_Walking_Dead_(video_game)
- 批评集中在它的承诺没兑现：玩家对 Clementine 说什么"其实都不重要"，分支大多又汇回主线。https://www.denofgeek.com/games/the-walking-dead-false-promises-telltale/

**Life is Strange**
- 每章结束后能看到其他玩家在本章每个选择上的比例。https://steamcommunity.com/app/319630/discussions/0/617328415076647103
- 时间回溯可以让玩家先看到眼前选项的结果，但过去章节的决定改不了。https://gameluster.com/?p=13782
- 结局是"救小镇还是救 Chloe"的二选一，部分玩家很失望，觉得之前的选择都没用了。https://www.gameinformer.com/b/features/archive/2015/10/27/coming-to-terms-with-life-is-strange-s-finale.aspx

**Until Dawn**
- 关键决定做出的那一刻，游戏马上告诉你"这会产生蝴蝶效应"。图腾会给出可以改变的未来预兆。评论者认为这让每个动作都带上"几乎让人瘫痪的恐惧感"，而且这种恐惧正是游戏想要的。https://unwinnable.com/2015/08/28/the-dread-of-knowing-in-until-dawn-uw58/
- 有评论认为前半段的选择大多没有意义，Destructoid 直接称它"噱头"。https://en.wikipedia.org/wiki/Until_Dawn

**用知识图谱代替分支图**
- **Outer Wilds 飞船日志**：可以按地点看，也可以看成一张线索关系网。"学到新东西是玩家得到的唯一反馈"。https://en.wikipedia.org/wiki/Outer_Wilds 玩家说它会提示"这里还有更多可探索"，不给任务标记但不会让人迷路。https://steamcommunity.com/app/753640/discussions/0/2518023667592336699
- **Return of the Obra Dinn**：推理每对三条才批量确认一次，用来防止玩家暴力试错，不过熟练的玩家仍然能钻空子。https://filmstories.co.uk/?p=83249
- **13 Sentinels**："Analysis" 模式把事件和人物整理成索引，再配合流程图让玩家在场景之间跳转。有评论说剧情难跟、术语太多。https://en.wikipedia.org/wiki/13_Sentinels:_Aegis_Rim
- **Heaven's Vault**：翻译出的文本会落到时间线菜单上，但条目越积越多，菜单"几乎没法用"。https://www.slantmagazine.com/games/heavens-vault-review/
- **The Stanley Parable**：旁白会对玩家的违抗当场作出反应。评论者的总结是：没有分支，旁白只是包装；没有旁白，分支也没有意义。https://media.gdcvault.com/GDC2014/GameNarrativeReview/Daily_Sean_TheStanleyParable.pdf
- **80 Days**：有一个实时动态，显示其他玩家正在走的路线。https://inklestudios.com/80days

**可迁移模式**
1. **当下轻提示，章末给完整图。** 当下只告诉玩家"有东西被改变了"（像 Until Dawn 或 Telltale），完整的因果链留到章节或每天结束时展开（像 Detroit）。「推断」連鎖反応マップ平时只显示第一跳，"→ 塞利农提乌斯会被处刑"这种远端后果等到黄昏结算时再揭示，避免剧透。
2. **未知节点画成锁住或问号，不写内容。** Detroit 和 Outer Wilds 都是只露出图的形状、不露内容，既制造好奇又不剧透。
3. **说"会记住"就必须兑现。** Telltale 是反面教材。「推断」每条连锁提示都要能在后面被引用（结局的每句话引用玩家做过的事，正是这个闭环）。
4. **图要能按人物、天数、地点筛选。** Heaven's Vault 的教训是不筛选就会堵死菜单。

---

## 2. 时间压力

- **Majora's Mask**：72 小时一个循环，现实中大约 54 分钟。屏幕上一直有时钟，NPC 按固定日程行动。Song of Time 回到第一天，Inverted Song 让时间变慢，Double Time 跳过时间。Bombers' Notebook 用时间条显示每个角色什么时候在。评论普遍称赞这个设计，但也有评论者被反复重来烦到差点弃坑。https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Majora%27s_Mask
  - 最初设计是 7 天。青沼英二说一周"重复玩很累"，玩家也记不住谁哪天在哪，所以改成 3 天。https://zeldauniverse.net/2019/05/07/zeldas-study-majoras-mask-was-originally-planned-to-have-a-weeklong-cycle/
  - 3DS 重制版改成可以跳到任意整点，日程本几乎追踪所有角色，存档点也改为永久存档。评价是在不破坏前提的情况下精修了结构。https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Majora%27s_Mask_3D
  - 玩家意见两极：有人觉得"总觉得该去优化效率"，有人觉得"它其实没在计时，只是循环"，也有人觉得时钟"让世界更鲜活"。https://www.zeldadungeon.net/forum/threads/does-majoras-mask-stress-you-out.69460/
- **Pentiment**：每天分成工作、祈祷、吃饭几个时段，一段长对话就会用掉一个时段，查错人就没时间回头。GameSpot 不喜欢"和人吃晚饭也要花时间"，觉得这是在惩罚好奇心。https://www.gamespot.com/reviews/pentiment-review/1900-6417998/ Josh Sawyer 的看法是，RPG 最好的状态是玩家"能控制很多，但控制不了一切"。https://www.gamedeveloper.com/design/pentiment-director-emphasizes-the-importance-of-rpg-players-not-controlling-everything
- **The Last Express**：实时进行，速度是现实的 6 倍。暂停时可以倒回到任意时刻，角色有各自的日程，同一时间别处发生的事会错过。https://en.wikipedia.org/wiki/The_Last_Express
- **Dead Rising**：72 游戏小时约等于现实 6 小时，每个任务单独计时，原版只能存一个档，评论批评存档系统和推进方式不够宽容。https://en.wikipedia.org/wiki/Dead_Rising_(video_game) Deluxe Remaster 加了自动存档，存档点可以快进时间。https://news.xbox.com/en-us/2024/09/19/dead-rising-deluxe-remaster-changes-improvements/
- **Outer Wilds**：22 分钟后超新星爆发，一切重置，只有日志保留下来。https://en.wikipedia.org/wiki/Outer_Wilds
- **Frostpunk**：用 Hope 和 Discontent 两个量表衡量民心；法典里的小妥协会滚雪球，对应"渐进式常态化"；开发者刻意让游戏在高潮处结束，"像小说一样"。https://en.wikipedia.org/wiki/Frostpunk

**可迁移模式**
1. **时间按行动消耗，用粗颗粒时段，不用实时。** 「推断」手机浏览器的游玩会话很碎，适合学 Pentiment 的时段制。"深谈"花一个时段，寒暄免费，避开 GameSpot 说的"惩罚好奇心"。
2. **花时间之前先告诉代价。** 「推断」比如"和他谈下去会到黄昏"，相当于 Majora 的时钟加上日程本：让玩家能预知，而不是被突然扣掉时间。
3. **要有安全网。** Song of Time、Outer Wilds 的循环、Dead Rising 重制版的自动存档，都是把"失败"变成"知识"。玩家说的"它其实没在计时"正是减轻焦虑的关键。
4. **日程本式的 NPC 时间表**，让 Melos 的奔跑和国王的处刑时刻可以被推理、可以去拦截。

---

## 3. 角色记忆和关系 UI

- **Hades**：Kasavin 的方法是："这些角色会聊什么、会注意到什么？就加上这些互动。" 系统本身很简单，只是不断加入新的判断条件。https://gamespot.com/articles/hades-writer-explains-script-philosophy-after-player-discovers-incredible-detail/1100-6482650/ 他把这种效果比作"有人注意到你剪了头发、换了新鞋"。https://www.screenhub.com.au/news-article/features/digital/jini-maxwell/hades-greg-kasavin-breaks-down-supergiants-unique-approach-to-narrative-262459
- **Baldur's Gate 3**：对话中左上角弹出好感变化，平时用类似任务更新的框显示。好感分 7 档，每档有文字描述。同伴必须在附近才会产生好感变化。https://bg3.wiki/wiki/Approval PC Gamer 的读档吐槽："我说了*那句*怎么会导致*那件事*？我根本不是那个意思！" https://tech.yahoo.com/general/articles/were-save-scumming-baldurs-gate-234103643.html
- **Disco Elysium**："说了蠢话他们会记住，帮了人他们也会记住"。重复的言行会变成 Thought，需要 30 分钟到 3 天的游戏内时间来"内化"。https://gamebanshee.com/39hc9
- **Persona 5**：Confidant 关系系统和日夜日历绑在一起，同时有 Palace 的期限。https://en.wikipedia.org/wiki/Persona_5
- **ChatGPT 记忆**：入口是"设置 > 个性化 > 记忆"，可以直接改，也可以选"不要再提这个"。删掉对话不会删掉从这段对话生成的记忆。临时对话不会生成记忆。https://help.openai.com/en/articles/8590148-memory-faq
- **Character.AI**：2026 年 5 月用 Story Memory 取代了原来 400 字的记忆框，入口是聊天顶部的笔记本图标。付费层有自动捕捉的 Facts，但捕捉错了会一直影响回答，直到用户手动改。另有 "Memory Usage" 显示当前记忆占用，长按消息可以 Pin 住原文。用户评价两极，有付费用户说自动记忆"不太行"。https://www.roborhythms.com/character-ai-adds-chat-memories/
- **Replika**：Memory 标签页可以手动添加记忆，点赞能强化某条记忆。官方提醒删除记忆会影响它回忆细节。https://help.replika.com/hc/en-us/articles/37208679176077-How-does-Replika-s-memory-work
- **隐私 UX 指南**：Google PAIR 建议给用户展示"收集了哪些关于你的数据、用于什么"，告诉用户能不能删除或重置，并给出"因为你……"式的解释。https://pair.withgoogle.com/chapter/People%20+%20AI%20Guidebook%20-%20Explainability%20+%20Trust.pdf Mozilla 评测了 11 款恋爱 AI 应用，超过一半不允许删除数据。https://www.euronews.com/2024/02/14/stealing-hearts-data-and-privacy-why-you-should-be-careful-of-ai-partners

**可迁移模式**
1. **见证规则。** 学 BG3 的"在附近才算"。「推断」記憶帳里每条记忆标明来源：亲眼见到、听人说起、还是村里的传闻。这样既合乎世界逻辑，也能解释"他为什么知道"。
2. **用角色口吻写记忆，并链接到原始时刻。** Hades 式的"被注意到"加上 PAIR 的"因为你……"。比如："セリヌンティウスは覚えている——那夜你坐在他身旁（第2日・夜）"。
3. **"故事事实"和"原话数据"分开删。** ChatGPT 证明了这两层要分开管理。「推断」删掉原话录音或转写，不一定要删掉剧情事实。要么让玩家二选一，要么明确告诉玩家"删除后他会忘记这件事"（参考 Replika 的提醒）。
4. **防止"我不是这个意思"。** 叙事 agent 把语音转成事件时，应该先轻量确认一下，比如"你是想拦住 Melos 吗？"，再写入因果图。「推断」这对应 BG3 读档的根源。

---

## 4. 结局、回顾和分享

- **Detroit**：章末流程图加全球比例，"只有 1%"本身就是值得炫耀的点。（来源同上，RogerEbert）
- **Frostpunk**：结局对玩家做道德评判（"Was it worth it?"）。玩家抱怨评判只看颁布了哪些法律，不看存活率："我到底在哪越线了？" https://steamcommunity.com/app/323190/discussions/0/1696045708654961998
- **Undertale**：重置也洗不掉屠杀路线的后果，玩家因此不再把世界当成没有后果的游乐场。https://reporter.rit.edu/5437/culture/undertale-and-permanent-consequences-in-video-games
- **NieR:Automata Ending E**：玩家可以牺牲自己的存档去帮助陌生玩家。https://www.siliconsasquatch.com/blog/2017/12/27/goty-2017-best-moment
- **Spotify Wrapped**：2019 年实习生 Jewel Ham 把它改成 Stories 格式，用户开始把它当"星座运势"来分享。https://www.refinery29.com/en-us/2020/12/10208481/jewel-ham-artist-spotify-wrapped-internship 2022 年加了 16 种 "Listening Personality"。https://newsroom.spotify.com/2022-11-30/everything-you-need-to-know-about-2022-wrapped/ 设计团队说"Wrapped 里无处可藏，你得认领它"，个性化的动态图形是这一版的核心。https://www.itsnicethat.com/features/spotify-wrapped-campaign-identity-2022-graphic-design-301122
- **Duolingo 年度回顾**：XP 前 10% 的用户贡献了超过一半的分享，所以团队加了"学习者风格"人格，让普通用户也有东西可晒。https://blog.duolingo.com/year-in-review-behind-the-scenes
- **Bandersnatch**：94% 的观众主动做了选择。Netflix 追踪了每个节点的选择比例，火车结局最难达成。主角 Stefan 会抵抗观众的选择，以此保持角色一致。https://www.hollywoodreporter.com/live-feed/black-mirror-team-complexity-bandersnatch-netflix-data-1213270

**可迁移模式**
1. **一张卡里同时有身份、稀有度和美感。** 身份是称号（类似 Listening Personality），稀有度是"仅 12% 的人……"，美感来自可生成的个性化视觉，格式用 9:16 的 Stories。
2. **人人都有一个稀有点。** 只有数据最好的玩家才晒得出排名（Duolingo 的前 10% 现象）。「推断」应从每个玩家的路线里挑出最稀有的一件事放在卡面上。
3. **判语要有证据。** Frostpunk 的教训是：结局判语必须引用具体行为，评判维度要多元。你们"每句尾声引用玩家行为"的设计正好可以规避这个问题。
4. **两个结局避免"最终二选一让之前白做"**（Life is Strange 的问题）。世界结局可以由原作的因果收束决定，个人结局则累积玩家的全部选择。

---

## 5. AI 原生叙事产品和研究

**c.ai Books（2026-04-16 上线）**
- 三种玩法：Book Arc 跟随原著、Go off script 自由发挥、社区做的 AU 改编。还有"即将推出"的 TapTale，在打字之外提供预写的选项。免费用户只有少量回合。https://blog.character.ai/cai-books/
- 书库有 20 多本古腾堡公版书。https://www.creativeainews.com/blog/character-ai-books-playable-classic-literature/
- 流程是"选书 → 选你是谁 → 开聊"。体验者指出它只有文字没有语音，而且"不同会话之间没有连续性"。https://medium.com/activated-thinker/the-childhood-dream-of-talking-to-book-characters-just-became-real-4c85d5196a9b
- 媒体报道背景是持续的安全争议。https://www.digitaltrends.com/computing/character-ai-turns-books-into-roleplay-bots-amid-ongoing-safety-concerns/ c.ai 从 2025-11-25 起禁止未成年人与聊天机器人对话。https://en.wikipedia.org/wiki/Character.ai
- 「推断」可以拉开差异的地方：语音、3D 场景、持久记忆、因果图、结局卡。

**其他产品**
- **Hidden Door**（2025-08 上线）：有一个全知的 AI Narrator，故事卡可以跨故事共享，书目包括 Pride and Prejudice 和 Wizard of Oz。https://getcoai.com/news/hidden-door-launches-ai-role-playing-platform-with-creator-revenue-sharing
- **AI Dungeon**：官方承认 AI 只能回看有限的上下文，建议用 Memory、重试、编辑来补救。https://help.aidungeon.io/faq/why-does-the-ai-forget-or-mix-things-up 玩家抱怨重复，以及死掉的角色又冒出来。https://reddit.birdcat.cafe/r/AIDungeon/comments/1iw583o/ai_dungeon_got_worst
- **Inworld Origins**：离题问题会被 NPC 转移开；延迟导致台词重叠。https://www.axios.com/2023/08/07/inworld-ai-origins-demo 另一位体验者说角色"话太多，打断也不停"。https://newatlas.com/games/inworld-origins-ai-npc PC Gamer 试玩两款 AI NPC demo 后的结论是："你可以说任何话，但做不了任何事。"https://www.pcgamer.com/gaming-industry/i-tried-two-demos-of-machine-learning-ai-npcs-and-they-didnt-convince-me-the-ai-will-lead-to-anything-that-immersive-sims-like-deus-ex-havent-already-done-better/
- **Whispers from the Star**（2025-08-14）：可以用语音、文字或视频通话交流。上线时 Steam 好评 92%（202 条评价）。https://www.notebookcheck.net/Steam-launch-New-interactive-fiction-game-debuts-to-Very-Positive-reviews-may-divide-gamers-over-heavy-AI-integration.1087821.0.html 目前 Steam 页面是 1,663 条评价、80% 好评。https://store.steampowered.com/app/3730100 Eurogamer 德国版只给了 20/100，说它"很快变平庸，而且收集大量数据"；有用户抱怨身为专家的 Stella 反而事事依赖玩家指导。https://www.metacritic.com/game/whispers-from-the-star/
- **Façade 的教训**：系统大约 30% 的时间听不懂玩家，靠剧情管理器的偏转话术撑住体验。玩家会故意扮成僵尸、外星人去试探系统的边界。https://grandtextauto.soe.ucsc.edu/2008/03/18/ep-86-learning-from-facade

**研究（2025-2026）**
- **Dramamancer**（2026-01）：作者定义 storylet（事件和结果的配对），由一个解释模块判断玩家的行为是否触发了事件条件。https://arxiv.org/html/2601.18785
- **ACL 2025 论文《Towards Enhanced Immersion and Agency for LLM-based Interactive Drama》**：每次反思最多只改一个情节。记录的失败模式之一是"剧本泄露"：负责反思的全局 agent 能看到整个剧本，结果让角色提前说出了后面的剧情。另一个失败模式是幻觉出不存在的场景。https://arxiv.org/html/2502.17878v2
- **叙事规划视角的 LLM 评测**（2025-06）：LLM 在角色意图和戏剧冲突上表现很弱，接入符号规划器后明显提升。https://arxiv.org/html/2506.10161v1
- **Moral RolePlay**（2025-11）：角色越不道德，LLM 扮演得越不像；欺骗、操纵类特质最难演。https://arxiv.org/abs/2511.04962v1 对应的用户抱怨是 c.ai 的反派会半路道歉、"变温和"。https://www.roborhythms.com/character-ai-bots-too-wholesome/
- **谄媚问题**：2025 年 4 月 OpenAI 因为 GPT-4o 过度奉承而回滚了更新。https://www.axios.com/2025/07/07/ai-sycophancy-chatbots-mental-health
- **Symbolically Scaffolded Play**（N=10，语音侦探游戏）：高约束和低约束 prompt 之间没有显著差异，玩家主要注意到的是延迟这类表层问题。https://arxiv.org/html/2510.25820v1 另一篇研究发现，"简洁、别夸张演"的提示词有效。https://arxiv.org/html/2510.13586v1

**可迁移模式**
1. **因果图只给叙事 agent，不给 NPC。** 每个 NPC 只拿到"它知道的"部分，防止剧本泄露和剧透。
2. **因果推演交给符号层（你们的因果图），LLM 只负责表达。** 这对应上面的神经符号研究结论。
3. **暴君迪奥尼斯需要专门的反派约束和评测。** 「推断」否则他很可能半路软化，Moral RolePlay 的结果说明了这一点。
4. **台词要短，可以打断，并告诉玩家"说什么能改变什么"。** 这样能避开 PC Gamer 说的"说任何话但做不了任何事"。

---

## 6. 自由语音玩法的新手引导

- **NPC 先开口提问**：Whispers from the Star 一开场就是 Stella 惊慌地问"我怎么才能从救生舱出去？"。评论也提醒，这个游戏要求玩家英语很好。https://www.gamestar.de/artikel/scifi-survival-whsipers-from-the-star-steam-ausprobiert,3437962.html
- **Alexa 语音设计指南**：用一个问题结尾，提示用户该说话了；给出明确的选项（"Brie 还是 Gouda？"），不要问"你想要什么？"；求助时给出示例说法；听不懂时换一种说法重问，不要原样重复。https://developer.amazon.com/fr/designing-for-voice/what-alexa-says/
- **提示词起手式（Prompt starters）**：给 3-4 个具体的起手提示。不要写"Ask me anything"这类空话，老用户用过之后要收起来。https://aiuxplayground.com/pattern/prompt-starters
- **AI 产品空状态**（UX Collective，2026-05）：建议用示范性的例子、明确的动词、事先公开限制，并设计一个"不小心就做成了事"的时刻。作者说首会话流失率约 70%，这个数字我没有核实，是作者的说法。https://uxdesign.cc/the-death-of-the-empty-state-in-ai-products-2026-e11439fbb688
- **其他做法**：c.ai 的 TapTale 在打字之外提供预写选项（来源同上，c.ai 官方博客）；Event[0] 让玩家打字与 AI 对话，AI 的态度会随玩家的对待方式变化。https://en.wikipedia.org/wiki/Event_0

**可迁移模式**
1. **身份决定第一句话。** 「推断」石匠学徒一开场就被师傅问"今天去城里送石料吗？"，牧童则被问到走失的羊。NPC 先提问，并带两三个具体选项。
2. **语音按钮旁放情境化的提示卡片。** 一两句话，随场景变化，用过就淡出。比如在河边显示"问问他为什么这么急"。
3. **安全的第一次出手。** 「推断」前 5 分钟就设计一个小动作，在連鎖反応マップ上亮起第一条线，比如帮塞利农提乌斯捎个口信。让玩家先"做成一件事"，再去理解系统。
4. **听不懂时用角色口吻接住，换个说法重问。** 学 Façade 和 Alexa。同时在开场就公开边界："你的话能改变人们的选择，但改变不了天气和神。"

---

**这次没能核实的内容**：Pi 的记忆界面、Mass Effect、Persona 的升级动画、Heaven's Vault 时间线的具体交互、Pentiment 的结局呈现。上面都没有展开写。