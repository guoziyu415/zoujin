# 调研：手机浏览器 3D 操作、无障碍、日语排版、等待、麦克风权限、年龄分级

UX 线程 2026-10-06 整理（调研助手检索，UX 审读）。每条事实都附来源；「推断」是推测，不是来源原话。ux-design.md 引用这里的结论。前端可以直接拿去用。

## 1. 手机 3D 的移动和镜头

- **怎么握手机**：Hoober 观察了 1,300 多人：49% 单手握，36% 一手托一手点，15% 双手。约 75% 的操作用拇指完成，省力的拇指区约占屏幕下方 1/3。[A List Apart](https://alistapart.com/article/how-we-hold-our-gadgets/)　约 94% 的时间是竖着拿的（MOVR 2019Q2）。[J.D. Power](https://www.jdpower.com/business/resources/new-trend-mobile-video-advertising-all-about-going-vertical)
- **竖屏 3D 的先例**：
  - Monument Valley：点一下，人物走过去，没有自由镜头。[Wikipedia](https://en.wikipedia.org/wiki/Monument_Valley_(video_game))
  - Animal Crossing Pocket Camp：点目标走过去，点居民开始对话。[Nintendo Life](https://www.nintendolife.com/news/2017/10/feature_our_first_steps_in_animal_crossing_pocket_camp)
- **横屏、双拇指**：Sky 左半屏移动、右半屏镜头。[Gamezebo](https://www.gamezebo.com/reviews/sky-children-of-the-light-review-an-auditory-and-visual-masterpiece-that-were-blessed-to-have-on-mobile/)　Genshin 被评价为小屏上难操作。[Android Central](https://www.androidcentral.com/genshin-impact-review)
- **横竖都支持**：Elder Scrolls: Blades 两种都支持，UI 工作量多 20–60%。他们简化了竖屏 UI，测下来更好用，结果横屏也跟着改了。[UESP](https://content2.uesp.net/wiki/General:Building_the_Interface_of_The_Elder_Scrolls:_Blades_in_Landscape_and_Portrait)
- **Apple HIG（游戏）**：能直接点场景里的东西，就别再加虚拟按钮。主要控件 ≥44pt，次要控件 ≥28pt。不要压住 Home 指示条，次要控件放屏幕上方。默认字号 17pt，最小 11pt。[HIG Game controls](https://developer.apple.com/tutorials/data/design/human-interface-guidelines/game-controls.json)、[HIG Designing for games](https://developer.apple.com/tutorials/data/design/human-interface-guidelines/designing-for-games.json)
- **网页上的先例**：
  - Messenger（Abeto，2025-09）：WebGL 网页游戏，低端 Android 上也流畅；能对话的 NPC 头顶有三角标记。[Wikipedia](https://en.wikipedia.org/wiki/Messenger_(video_game))、[Buttonmusher](https://buttonmusher.substack.com/p/exploring-a-planet-from-an-er-waiting)
  - Bruno Simon 新作品集：手机上自动降画质，资源用 KTX2 / Draco 压缩。[Awwwards](https://www.awwwards.com/brunos-portfolio-case-study.html)
- **iOS Safari 的限制**：
  - 安全区用 `viewport-fit=cover` 配 `env(safe-area-inset-*)`。[WebKit](https://webkit.org/blog/7929/designing-websites-for-iphone-x/)
  - `dvh` 的更新有节流，会跳。[web.dev](https://web.dev/blog/viewport-units)
  - iOS 26 的底部工具栏改成悬浮式，会压住内容。[9to5Mac](https://9to5mac.com/2025/09/15/iphone-ios-26-safari-new-compact-design/)、[Apple Forums](https://developer.apple.com/forums/thread/800798)
  - iPhone 不支持 Fullscreen API。[Apple Forums](https://developer.apple.com/forums/thread/770080)
  - `touch-action:none` 会关掉缩放，对低视力用户不友好。[MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/touch-action)
  - `-webkit-touch-callout:none` 可以关掉长按菜单。[MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/-webkit-touch-callout)

## 2. 无障碍

- **Game Accessibility Guidelines**：
  - Basic 级：语音不能是唯一的输入方式；所有重要的语音都要有字幕；不能只靠声音传达信息；音量分开调。[GAG](https://gameaccessibilityguidelines.com/ensure-that-speech-input-is-not-required-and-included-only-as-a-supplementary-alternative-input-method/)、[GAG Basic](https://gameaccessibilityguidelines.com/basic/)
  - Intermediate 级：不要强制按住按钮，要提供切换式。[GAG](https://gameaccessibilityguidelines.com/avoid-provide-alternatives-to-requiring-buttons-to-be-held-down/)　还要标出是谁在说话、提供进度摘要。[GAG Intermediate](https://gameaccessibilityguidelines.com/intermediate/)
- **Xbox Accessibility Guidelines**：
  - XAG 104：字幕可放大到 200%，背景透明度可调，最多 2 行，换人说话时标名字，默认开启。[XAG 104](https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/104)
  - XAG 102：对比度 4.5:1；文字压在复杂背景上时，按最差的那个位置算。[XAG 102](https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/102)
  - XAG 116：对话和教程的文字要能停留，直到玩家推进。[XAG 116](https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/116)
  - XAG 119：凡是能说话交流的地方，都要能用文字输入代替。[XAG 119](https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/119)
- **WCAG 2.2**（[原文](https://www.w3.org/TR/WCAG22/)）：
  - 2.5.8：点击目标 ≥24px。
  - 2.5.7：拖动能做的事要有不拖动的替代，比如镜头旋转、地图拖动。
  - 2.2.1：回答人物时不设倒计时，也不能沉默几秒就自动停止收音。
  - 2.2.2：自动推进的内容要能暂停。
  - 2.3.3：交互触发的动画要能关，用 `prefers-reduced-motion`。
  - 1.2：语音和视频都要有字幕；玩家自己说的话也要回显。
  - 1.4.4：文字放大到 200% 不丢功能。
  - 3.3.x：识别失败时用文字说明，识别结果可以编辑后再发，学校模式不用密码。
- **减少动态效果**：会让人晕的是缩放、旋转、视差和周边视野里的运动。把它们换成简单的动画，而不是直接删掉。[WebKit](https://webkit.org/blog/7551/responsive-design-for-motion/)
- **canvas 和读屏**：在 canvas 旁放一套「平行 DOM」，把能交互的对象映射成按钮，canvas 本身设 `aria-hidden`。[Quorum](https://quorumlanguage.com/tutorials/accessibility/accessibleGraphicsWebGL.html)
- **日语字幕（Netflix 规范）**：横排每行 ≤13 字，最多 2 行；阅读速度 4 字/秒（SDH 字幕 7 字/秒）。振假名一般只在第一次出现时标，儿童节目每次都标。[Netflix](https://partnerhelp.netflixstudios.com/hc/en-us/articles/215767517-Japanese-Timed-Text-Style-Guide)

## 3. 日语排版

- 数字厅设计系统：正文 16px 起，原则上不小于 14px，行高 ≥1.5。[DADS](https://design.digital.go.jp/foundations/typography/)
- JLReq：横排每行最多约 40 字。[JLReq](https://w3c.github.io/jlreq/?lang=en)
- 振假名：`<ruby>` 部分支持。Safari 18.2 增加了 `ruby-align`、`ruby-overhang`。[caniuse](https://caniuse.com/ruby)、[WebKit](https://webkit.org/blog/16301/webkit-features-in-safari-18-2/)
- 竖排：会产生向左的横向滚动，符号方向也不稳定，只适合固定版面。[berlysia 2026](https://speakerdeck.com/berlysia/burikaigi2026-use-vertical-writing-on-a-site-or-create-a-vertical-writing-site)
- 字体：Google Fonts 的日文字体按 `unicode-range` 切片，按需下载，比整包少下载约 80%。[Google Developers Blog](https://developers.googleblog.com/google-fonts-launches-japanese-support/)

## 4. 等待和加载

- Nielsen 的三个阈值：0.1 秒、1 秒、10 秒。[NN/g](https://www.nngroup.com/videos/3-response-time-limits-interaction-design/)
- 进度指示：2–10 秒用循环动画，超过 10 秒用百分比。看到进度的人愿意多等约 3 倍时间。[NN/g](https://www.nngroup.com/articles/progress-indicators/)
- Doherty 阈值：400ms 内给反馈。[Laws of UX](https://lawsofux.com/doherty-threshold/)
- AI 长任务：显示步骤、已用时间和中间产物；超过 1 分钟就默认用户已经离开，完成时要通知。[UX Tigers](https://www.uxtigers.com/post/progress-indicators)

## 5. 麦克风权限

- 在用户操作、有上下文时再请求，先用说明页讲清用途，并提供替代方式。[web.dev](https://web.dev/articles/permissions-best-practices)　Google Meet 加了说明页后，首次授权率提高了 14%。[web.dev](https://web.dev/case-studies/google-meet-permissions-best-practices)
- 用户拒绝时抛 `NotAllowedError`；放进 iframe 时需要 `allow="microphone"`。[MDN](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
- iOS 上恢复麦克风：
  - 只改这个网站：地址栏「ぁあ」→「Webサイトの設定」→「マイク」。[MacRumors](https://www.macrumors.com/how-to/access-website-settings-in-safari/)
  - 改所有网站：「設定 → アプリ → Safari → マイク」。[Yembo](https://help.yembo.ai/en/articles/10770972-enabling-permissions-ios)
  - iOS 26 把很多入口收进了「•••」，**上线前要在 iOS 26 实机上确认**。[AOL](https://www.aol.com/news/ios-26-took-away-safari-153400146.html)

## 6. 年龄分级和未成年人

- CERO 分 A / B12 / C15 / D17 / Z18，判定标准不公开。[PlayStation JP](https://www.playstation.com/ja-jp/legal/ratings/)　伦理规定禁止「极其残酷」的流血和肢体切断。[cvxfreak](https://cvxfreak.substack.com/p/japans-cero-age-rating-system-and)
- APPI 2026 修订：2026-07-17 公布。16 岁以下的同意改为找法定代理人，并新增「最佳利益」努力义务；施行日由政令定（最晚约 2028 年）。[PPC](https://www.ppc.go.jp/news/press/2026/260717/)、[長島・大野・常松](https://www.nagashima.com/publications/publication20260423-1/)
- 文部科学省：生成式 AI 指南 Ver.2.0 要求先确认服务的年龄限制，原则上不输入个人信息；教育数据留意事项第 4 版（2026-04）要求只保存必要的数据。[MEXT PDF](https://www.mext.go.jp/content/20260423-mxt_syoto01-000028144_01.pdf)
- GIGA 第 2 期学生终端：ChromeOS 60%，iPadOS 31%，Windows 10%。[helentech](https://helentech.jp/news-71040/)
- 年龄确认：用中性方式问，不设默认值，不暗示「太小就不能玩」。[FTC](https://www.ftc.gov/business-guidance/resources/complying-coppa-frequently-asked-questions)

## 还要实机验证的

- iOS 26 里网站设置的入口在哪；
- Safari 支不支持 `permissions.query({name:'microphone'})`；
- 悬浮工具栏下面，底部按钮实际能点的范围；
- 麦克风打开时，语音播放的音量和输出通道会不会变（推断）。
