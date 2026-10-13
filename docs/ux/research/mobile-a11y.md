# Research: 3D controls in mobile browsers, accessibility, Japanese typography, waiting, microphone permission, age ratings / 調査：スマホブラウザでの 3D 操作、アクセシビリティ、日本語組版、待ち時間、マイク権限、年齢区分

Compiled by the UX thread on 2026-10-06 (searched by the research assistant, reviewed by UX). Every fact has a source; "inference" marks a guess, not something the source says. ux-design.md cites the conclusions here. The frontend can use them directly.

UX スレッドが 2026-10-06 に整理（調査アシスタントが検索し、UX が査読）。すべての事実に出典を付けている。「推測」は推測であり、出典の記述ではない。ux-design.md はここの結論を引用している。フロントエンドはそのまま使ってよい。

## 1. Movement and camera in mobile 3D / スマホ 3D の移動とカメラ

- **How people hold phones**: Hoober observed more than 1,300 people: 49% hold the phone in one hand, 36% cradle it in one hand and tap with the other, 15% use both hands. About 75% of interactions are done with the thumb, and the comfortable thumb zone is roughly the bottom third of the screen. [A List Apart](https://alistapart.com/article/how-we-hold-our-gadgets/)　About 94% of the time the phone is held upright (MOVR 2019Q2). [J.D. Power](https://www.jdpower.com/business/resources/new-trend-mobile-video-advertising-all-about-going-vertical)
  **スマホの持ち方**：Hoober は 1,300 人以上を観察した。片手持ちが 49%、片手で支えてもう一方の手でタップするのが 36%、両手が 15%。操作の約 75% は親指で行われ、楽に届く親指の範囲は画面下部の約 1/3。[A List Apart](https://alistapart.com/article/how-we-hold-our-gadgets/)　約 94% の時間は縦向きで持たれている（MOVR 2019Q2）。[J.D. Power](https://www.jdpower.com/business/resources/new-trend-mobile-video-advertising-all-about-going-vertical)
- **Precedents for portrait 3D**: / **縦画面 3D の先例**：
  - Monument Valley: tap once and the character walks there; there is no free camera. [Wikipedia](https://en.wikipedia.org/wiki/Monument_Valley_(video_game))
    Monument Valley：一度タップするとキャラクターがそこまで歩く。自由カメラはない。[Wikipedia](https://en.wikipedia.org/wiki/Monument_Valley_(video_game))
  - Animal Crossing Pocket Camp: tap a target to walk there, tap a resident to start a conversation. [Nintendo Life](https://www.nintendolife.com/news/2017/10/feature_our_first_steps_in_animal_crossing_pocket_camp)
    Animal Crossing Pocket Camp：目標をタップするとそこへ歩き、住民をタップすると会話が始まる。[Nintendo Life](https://www.nintendolife.com/news/2017/10/feature_our_first_steps_in_animal_crossing_pocket_camp)
- **Landscape, two thumbs**: Sky uses the left half of the screen for movement and the right half for the camera. [Gamezebo](https://www.gamezebo.com/reviews/sky-children-of-the-light-review-an-auditory-and-visual-masterpiece-that-were-blessed-to-have-on-mobile/)　Genshin is criticized as hard to control on small screens. [Android Central](https://www.androidcentral.com/genshin-impact-review)
  **横画面・両手の親指**：Sky は画面の左半分で移動、右半分でカメラを操作する。[Gamezebo](https://www.gamezebo.com/reviews/sky-children-of-the-light-review-an-auditory-and-visual-masterpiece-that-were-blessed-to-have-on-mobile/)　原神は小さな画面では操作しにくいと評されている。[Android Central](https://www.androidcentral.com/genshin-impact-review)
- **Supporting both orientations**: Elder Scrolls: Blades supports both, at 20–60% more UI work. They simplified the portrait UI, testing showed it was easier to use, and in the end the landscape UI was changed to match. [UESP](https://content2.uesp.net/wiki/General:Building_the_Interface_of_The_Elder_Scrolls:_Blades_in_Landscape_and_Portrait)
  **縦横両対応**：Elder Scrolls: Blades は両方に対応し、UI の作業量は 20–60% 増えた。縦画面の UI を簡素化したところテストで使いやすいとわかり、結果として横画面もそれに合わせて変えた。[UESP](https://content2.uesp.net/wiki/General:Building_the_Interface_of_The_Elder_Scrolls:_Blades_in_Landscape_and_Portrait)
- **Apple HIG (games)**: if players can tap things in the scene directly, don't add virtual buttons on top. Primary controls ≥44pt, secondary controls ≥28pt. Don't cover the Home indicator; put secondary controls at the top of the screen. Default text size 17pt, minimum 11pt. [HIG Game controls](https://developer.apple.com/tutorials/data/design/human-interface-guidelines/game-controls.json), [HIG Designing for games](https://developer.apple.com/tutorials/data/design/human-interface-guidelines/designing-for-games.json)
  **Apple HIG（ゲーム）**：シーン内のものを直接タップできるなら、仮想ボタンを重ねない。主要なコントロールは 44pt 以上、副次的なコントロールは 28pt 以上。ホームインジケーターを覆わず、副次的なコントロールは画面上部に置く。標準の文字サイズは 17pt、最小 11pt。[HIG Game controls](https://developer.apple.com/tutorials/data/design/human-interface-guidelines/game-controls.json)、[HIG Designing for games](https://developer.apple.com/tutorials/data/design/human-interface-guidelines/designing-for-games.json)
- **Precedents on the web**: / **ウェブでの先例**：
  - Messenger (Abeto, 2025-09): a WebGL browser game that runs smoothly even on low-end Android; NPCs you can talk to have a triangle marker over their heads. [Wikipedia](https://en.wikipedia.org/wiki/Messenger_(video_game)), [Buttonmusher](https://buttonmusher.substack.com/p/exploring-a-planet-from-an-er-waiting)
    Messenger（Abeto、2025-09）：WebGL のブラウザゲームで、ローエンドの Android でも滑らかに動く。話しかけられる NPC の頭上には三角形のマークがある。[Wikipedia](https://en.wikipedia.org/wiki/Messenger_(video_game))、[Buttonmusher](https://buttonmusher.substack.com/p/exploring-a-planet-from-an-er-waiting)
  - Bruno Simon's new portfolio: lowers the graphics quality automatically on phones; assets are compressed with KTX2 / Draco. [Awwwards](https://www.awwwards.com/brunos-portfolio-case-study.html)
    Bruno Simon の新しいポートフォリオ：スマホでは自動で画質を下げ、アセットは KTX2 / Draco で圧縮している。[Awwwards](https://www.awwwards.com/brunos-portfolio-case-study.html)
- **iOS Safari limitations**: / **iOS Safari の制約**：
  - Safe areas: use `viewport-fit=cover` together with `env(safe-area-inset-*)`. [WebKit](https://webkit.org/blog/7929/designing-websites-for-iphone-x/)
    セーフエリアは `viewport-fit=cover` と `env(safe-area-inset-*)` を組み合わせる。[WebKit](https://webkit.org/blog/7929/designing-websites-for-iphone-x/)
  - Updates to `dvh` are throttled, so it jumps. [web.dev](https://web.dev/blog/viewport-units)
    `dvh` の更新は間引かれるため、値が飛ぶ。[web.dev](https://web.dev/blog/viewport-units)
  - In iOS 26 the bottom toolbar became a floating bar that covers content. [9to5Mac](https://9to5mac.com/2025/09/15/iphone-ios-26-safari-new-compact-design/), [Apple Forums](https://developer.apple.com/forums/thread/800798)
    iOS 26 では下部ツールバーがフローティング式になり、コンテンツに重なる。[9to5Mac](https://9to5mac.com/2025/09/15/iphone-ios-26-safari-new-compact-design/)、[Apple Forums](https://developer.apple.com/forums/thread/800798)
  - iPhone does not support the Fullscreen API. [Apple Forums](https://developer.apple.com/forums/thread/770080)
    iPhone は Fullscreen API に対応していない。[Apple Forums](https://developer.apple.com/forums/thread/770080)
  - `touch-action:none` disables zooming, which is bad for low-vision users. [MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/touch-action)
    `touch-action:none` はズームを無効にするため、ロービジョンのユーザーに不親切。[MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/touch-action)
  - `-webkit-touch-callout:none` turns off the long-press menu. [MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/-webkit-touch-callout)
    `-webkit-touch-callout:none` で長押しメニューを無効にできる。[MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/-webkit-touch-callout)

## 2. Accessibility / アクセシビリティ

- **Game Accessibility Guidelines**:
  **Game Accessibility Guidelines**：
  - Basic level: speech must not be the only input method; all important speech needs subtitles; information must not be conveyed by sound alone; volumes are adjustable separately. [GAG](https://gameaccessibilityguidelines.com/ensure-that-speech-input-is-not-required-and-included-only-as-a-supplementary-alternative-input-method/), [GAG Basic](https://gameaccessibilityguidelines.com/basic/)
    Basic レベル：音声を唯一の入力手段にしない。重要な音声にはすべて字幕を付ける。音だけで情報を伝えない。音量は個別に調整できる。[GAG](https://gameaccessibilityguidelines.com/ensure-that-speech-input-is-not-required-and-included-only-as-a-supplementary-alternative-input-method/)、[GAG Basic](https://gameaccessibilityguidelines.com/basic/)
  - Intermediate level: don't force players to hold buttons down; offer a toggle. [GAG](https://gameaccessibilityguidelines.com/avoid-provide-alternatives-to-requiring-buttons-to-be-held-down/)　Also show who is speaking and offer a progress summary. [GAG Intermediate](https://gameaccessibilityguidelines.com/intermediate/)
    Intermediate レベル：ボタンの長押しを強制せず、切り替え式を用意する。[GAG](https://gameaccessibilityguidelines.com/avoid-provide-alternatives-to-requiring-buttons-to-be-held-down/)　さらに、誰が話しているかを示し、進行状況のまとめを用意する。[GAG Intermediate](https://gameaccessibilityguidelines.com/intermediate/)
- **Xbox Accessibility Guidelines**:
  **Xbox Accessibility Guidelines**：
  - XAG 104: subtitles can be enlarged to 200%, background opacity is adjustable, at most 2 lines, the speaker's name is shown when the speaker changes, on by default. [XAG 104](https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/104)
    XAG 104：字幕は 200% まで拡大でき、背景の不透明度を調整でき、最大 2 行、話者が変わるときは名前を表示し、初期状態でオン。[XAG 104](https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/104)
  - XAG 102: contrast 4.5:1; when text sits on a busy background, measure at the worst spot. [XAG 102](https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/102)
    XAG 102：コントラスト比 4.5:1。複雑な背景の上に文字を置くときは、最も条件の悪い位置で測る。[XAG 102](https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/102)
  - XAG 116: dialogue and tutorial text must stay on screen until the player advances it. [XAG 116](https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/116)
    XAG 116：会話とチュートリアルの文字は、プレイヤーが進めるまで表示し続ける。[XAG 116](https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/116)
  - XAG 119: anywhere players can communicate by voice, text input must be available instead. [XAG 119](https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/119)
    XAG 119：音声でやりとりできる場面では、必ず文字入力で代替できるようにする。[XAG 119](https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/119)
- **WCAG 2.2** ([original](https://www.w3.org/TR/WCAG22/)):
  **WCAG 2.2**（[原文](https://www.w3.org/TR/WCAG22/)）：
  - 2.5.8: tap targets ≥24px.
    2.5.8：タップ対象は 24px 以上。
  - 2.5.7: anything done by dragging needs a non-drag alternative, e.g. rotating the camera or dragging the map.
    2.5.7：ドラッグでできる操作には、ドラッグしない代替手段を用意する。例：カメラの回転、地図のドラッグ。
  - 2.2.1: no countdown when answering a character, and recording must not stop automatically after a few seconds of silence.
    2.2.1：登場人物に答えるときにカウントダウンを設けない。数秒の無音で自動的に録音を止めてもいけない。
  - 2.2.2: content that advances automatically must be pausable.
    2.2.2：自動で進むコンテンツは一時停止できるようにする。
  - 2.3.3: animations triggered by interaction must be able to be turned off, via `prefers-reduced-motion`.
    2.3.3：操作で起きるアニメーションは `prefers-reduced-motion` でオフにできるようにする。
  - 1.2: both speech and video need subtitles; what players say themselves is echoed back as text too.
    1.2：音声にも動画にも字幕を付ける。プレイヤー自身の発話も文字で表示する。
  - 1.4.4: no loss of function when text is enlarged to 200%.
    1.4.4：文字を 200% に拡大しても機能が失われない。
  - 3.3.x: explain recognition failures in text; recognition results can be edited before sending; school mode needs no password.
    3.3.x：認識に失敗したら文字で説明する。認識結果は編集してから送信できる。学校モードではパスワードを使わない。
- **Reduced motion**: what makes people sick is zooming, rotation, parallax and motion in peripheral vision. Replace these with simple animations rather than deleting them outright. [WebKit](https://webkit.org/blog/7551/responsive-design-for-motion/)
  **動きを減らす**：酔いの原因になるのは、拡大縮小、回転、視差、周辺視野での動き。これらは丸ごと削除するのではなく、単純なアニメーションに置き換える。[WebKit](https://webkit.org/blog/7551/responsive-design-for-motion/)
- **Canvas and screen readers**: place a "parallel DOM" next to the canvas that maps interactive objects to buttons, and set `aria-hidden` on the canvas itself. [Quorum](https://quorumlanguage.com/tutorials/accessibility/accessibleGraphicsWebGL.html)
  **canvas とスクリーンリーダー**：canvas の横に「並列 DOM」を置き、操作できるオブジェクトをボタンに対応させる。canvas 自体には `aria-hidden` を設定する。[Quorum](https://quorumlanguage.com/tutorials/accessibility/accessibleGraphicsWebGL.html)
- **Japanese subtitles (Netflix guidelines)**: horizontal text at most 13 characters per line, at most 2 lines; reading speed 4 characters/second (7 characters/second for SDH subtitles). Furigana is usually only given on first appearance; children's programs give it every time. [Netflix](https://partnerhelp.netflixstudios.com/hc/en-us/articles/215767517-Japanese-Timed-Text-Style-Guide)
  **日本語字幕（Netflix の規定）**：横書きは 1 行 13 文字以内、最大 2 行。読む速さは 4 文字/秒（SDH 字幕は 7 文字/秒）。振り仮名は通常初出のときだけ付け、子ども向け番組では毎回付ける。[Netflix](https://partnerhelp.netflixstudios.com/hc/en-us/articles/215767517-Japanese-Timed-Text-Style-Guide)

## 3. Japanese typography / 日本語組版

- Digital Agency design system: body text from 16px, in principle no smaller than 14px, line height ≥1.5. [DADS](https://design.digital.go.jp/foundations/typography/)
  デジタル庁デザインシステム：本文は 16px から、原則として 14px 未満にしない。行の高さは 1.5 以上。[DADS](https://design.digital.go.jp/foundations/typography/)
- JLReq: horizontal text at most about 40 characters per line. [JLReq](https://w3c.github.io/jlreq/?lang=en)
  JLReq：横書きは 1 行最大約 40 文字。[JLReq](https://w3c.github.io/jlreq/?lang=en)
- Furigana: `<ruby>` is partially supported. Safari 18.2 added `ruby-align` and `ruby-overhang`. [caniuse](https://caniuse.com/ruby), [WebKit](https://webkit.org/blog/16301/webkit-features-in-safari-18-2/)
  振り仮名：`<ruby>` は部分的に対応している。Safari 18.2 で `ruby-align`、`ruby-overhang` が追加された。[caniuse](https://caniuse.com/ruby)、[WebKit](https://webkit.org/blog/16301/webkit-features-in-safari-18-2/)
- Vertical text: it produces leftward horizontal scrolling and punctuation orientation is unreliable, so it only suits fixed layouts. [berlysia 2026](https://speakerdeck.com/berlysia/burikaigi2026-use-vertical-writing-on-a-site-or-create-a-vertical-writing-site)
  縦書き：左方向への横スクロールが生じ、記号の向きも安定しないため、固定レイアウトにしか向かない。[berlysia 2026](https://speakerdeck.com/berlysia/burikaigi2026-use-vertical-writing-on-a-site-or-create-a-vertical-writing-site)
- Fonts: Google Fonts slices its Japanese fonts by `unicode-range` and downloads them on demand, about 80% less than downloading the whole font. [Google Developers Blog](https://developers.googleblog.com/google-fonts-launches-japanese-support/)
  フォント：Google Fonts の日本語フォントは `unicode-range` で分割され、必要な分だけダウンロードされる。フォント全体よりダウンロード量が約 80% 少ない。[Google Developers Blog](https://developers.googleblog.com/google-fonts-launches-japanese-support/)

## 4. Waiting and loading / 待ち時間と読み込み

- Nielsen's three thresholds: 0.1 s, 1 s, 10 s. [NN/g](https://www.nngroup.com/videos/3-response-time-limits-interaction-design/)
  Nielsen の 3 つのしきい値：0.1 秒、1 秒、10 秒。[NN/g](https://www.nngroup.com/videos/3-response-time-limits-interaction-design/)
- Progress indicators: use a looping animation for 2–10 seconds and a percentage beyond 10 seconds. People who see progress are willing to wait about 3 times longer. [NN/g](https://www.nngroup.com/articles/progress-indicators/)
  進捗表示：2–10 秒ならループするアニメーション、10 秒を超えるならパーセント表示。進捗が見える人は約 3 倍長く待ってくれる。[NN/g](https://www.nngroup.com/articles/progress-indicators/)
- Doherty threshold: give feedback within 400ms. [Laws of UX](https://lawsofux.com/doherty-threshold/)
  Doherty のしきい値：400ms 以内にフィードバックを返す。[Laws of UX](https://lawsofux.com/doherty-threshold/)
- Long AI tasks: show the steps, the elapsed time and intermediate output; past 1 minute, assume the user has left and notify them when it finishes. [UX Tigers](https://www.uxtigers.com/post/progress-indicators)
  AI の長いタスク：手順、経過時間、途中の成果物を表示する。1 分を超えたらユーザーはもう離れたものとみなし、完了時に通知する。[UX Tigers](https://www.uxtigers.com/post/progress-indicators)

## 5. Microphone permission / マイク権限

- Ask when the user acts and there is context; explain the purpose on an explainer screen first, and offer an alternative. [web.dev](https://web.dev/articles/permissions-best-practices)　After Google Meet added an explainer screen, the first-time grant rate rose by 14%. [web.dev](https://web.dev/case-studies/google-meet-permissions-best-practices)
  ユーザーが操作し、文脈があるときに求める。先に説明画面で用途をはっきり伝え、代替手段も用意する。[web.dev](https://web.dev/articles/permissions-best-practices)　Google Meet は説明画面を加えたあと、初回の許可率が 14% 上がった。[web.dev](https://web.dev/case-studies/google-meet-permissions-best-practices)
- When the user denies it, `NotAllowedError` is thrown; inside an iframe it needs `allow="microphone"`. [MDN](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
  ユーザーが拒否すると `NotAllowedError` が投げられる。iframe に入れる場合は `allow="microphone"` が必要。[MDN](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
- Restoring the microphone on iOS: / iOS でマイクを戻す方法：
  - For this site only: 「ぁあ」 in the address bar → 「Webサイトの設定」 → 「マイク」. [MacRumors](https://www.macrumors.com/how-to/access-website-settings-in-safari/)
    このサイトだけ変える：アドレスバーの「ぁあ」→「Webサイトの設定」→「マイク」。[MacRumors](https://www.macrumors.com/how-to/access-website-settings-in-safari/)
  - For all sites: 「設定 → アプリ → Safari → マイク」. [Yembo](https://help.yembo.ai/en/articles/10770972-enabling-permissions-ios)
    すべてのサイトを変える：「設定 → アプリ → Safari → マイク」。[Yembo](https://help.yembo.ai/en/articles/10770972-enabling-permissions-ios)
  - iOS 26 moved many of these entry points into 「•••」; **confirm on a real iOS 26 device before launch**. [AOL](https://www.aol.com/news/ios-26-took-away-safari-153400146.html)
    iOS 26 では多くの入口が「•••」の中に移された。**リリース前に iOS 26 の実機で確認すること**。[AOL](https://www.aol.com/news/ios-26-took-away-safari-153400146.html)

## 6. Age ratings and minors / 年齢区分と未成年者

- CERO ratings are A / B12 / C15 / D17 / Z18, and the criteria are not public. [PlayStation JP](https://www.playstation.com/ja-jp/legal/ratings/)　Its ethics rules prohibit "extremely cruel" bloodshed and dismemberment. [cvxfreak](https://cvxfreak.substack.com/p/japans-cero-age-rating-system-and)
  CERO の区分は A / B12 / C15 / D17 / Z18 で、判定基準は公開されていない。[PlayStation JP](https://www.playstation.com/ja-jp/legal/ratings/)　倫理規定は「著しく残酷な」流血や身体の切断を禁じている。[cvxfreak](https://cvxfreak.substack.com/p/japans-cero-age-rating-system-and)
- 2026 APPI amendment: published 2026-07-17. Consent for children under 16 now goes to the legal guardian, and a new duty to make efforts for the child's "best interests" is added; the effective date is set by Cabinet Order (at the latest around 2028). [PPC](https://www.ppc.go.jp/news/press/2026/260717/), [長島・大野・常松](https://www.nagashima.com/publications/publication20260423-1/)
  個人情報保護法の 2026 年改正：2026-07-17 公布。16 歳未満の同意は法定代理人から得るよう改められ、「最善の利益」の努力義務が新設された。施行日は政令で定める（遅くとも 2028 年頃）。[PPC](https://www.ppc.go.jp/news/press/2026/260717/)、[長島・大野・常松](https://www.nagashima.com/publications/publication20260423-1/)
- MEXT: the Generative AI Guidelines Ver.2.0 require checking a service's age restrictions first and, in principle, not entering personal information; the 4th edition of the notes on education data (2026-04) requires keeping only the data that is needed. [MEXT PDF](https://www.mext.go.jp/content/20260423-mxt_syoto01-000028144_01.pdf)
  文部科学省：生成 AI ガイドライン Ver.2.0 は、まずサービスの年齢制限を確認し、原則として個人情報を入力しないことを求めている。教育データの留意事項第 4 版（2026-04）は、必要なデータだけを保存することを求めている。[MEXT PDF](https://www.mext.go.jp/content/20260423-mxt_syoto01-000028144_01.pdf)
- Student devices in GIGA phase 2: ChromeOS 60%, iPadOS 31%, Windows 10%. [helentech](https://helentech.jp/news-71040/)
  GIGA 第 2 期の児童生徒用端末：ChromeOS 60%、iPadOS 31%、Windows 10%。[helentech](https://helentech.jp/news-71040/)
- Age confirmation: ask neutrally, with no default value, and without implying "too young means you can't play". [FTC](https://www.ftc.gov/business-guidance/resources/complying-coppa-frequently-asked-questions)
  年齢確認：中立的な聞き方をし、初期値を設けず、「幼すぎると遊べない」とほのめかさない。[FTC](https://www.ftc.gov/business-guidance/resources/complying-coppa-frequently-asked-questions)

## Still to verify on real devices / まだ実機で確認が必要なこと

- Where the website settings entry point is in iOS 26;
  iOS 26 でウェブサイト設定の入口がどこにあるか。
- Whether Safari supports `permissions.query({name:'microphone'})`;
  Safari が `permissions.query({name:'microphone'})` に対応しているか。
- The actual tappable area of bottom buttons under the floating toolbar;
  フローティングツールバーの下で、下部のボタンが実際にタップできる範囲。
- Whether the volume and output channel of voice playback change while the microphone is on (inference).
  マイクがオンのとき、音声再生の音量や出力チャンネルが変わるかどうか（推測）。
