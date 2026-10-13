# Questions for zg to decide (open-questions.md) / zg が決める問い（open-questions.md）

Maintained by: PM. Only things that only zg can decide go here (product direction, external commitments, spending money, whether to do something). Each entry includes PM's recommendation and reasoning.
Once zg decides: mark it "Decided" here, also write it into `decisions.md`, then notify the roles involved.
Last updated: 2026-10-06 (Q-010 decided: create a new GCP project; Q-002 confirmed; added Q-011 and Q-012, both to be asked before public launch)

管理：PM。zg にしか決められないこと（プロダクトの方向性、対外的な約束、お金を使うこと、やるかどうか）だけを置く。各項目に PM の推奨と理由を付ける。
zg が決めたら：ここに「決定」と記し、同時に `decisions.md` に書き、関係するロールに知らせる。
最終更新：2026-10-06（Q-010 決定：GCP プロジェクトを新設。Q-002 確認済み。Q-011、Q-012 を追加、どちらも公開前に改めて聞く）

## Things you need to do yourself (not decisions, but operations only you can do) / あなた自身に作業してもらうこと（決定ではなく、あなたにしかできない操作）

### T-001 Get the team the full text of 『走れメロス』 / T-001 チームが『走れメロス』の原文全文を入手できるようにする

**Done (2026-10-06)**: data engineering downloaded the original text through your Mac (source edition 「太宰治全集3」 ちくま文庫); you do not need to do anything else.

**完了（2026-10-06）**：データエンジニアリングがあなたの Mac 経由で原文をダウンロードした（底本「太宰治全集3」ちくま文庫）。あなたがすることはもうない。

### T-002 Open frontend's S1 test page on your iPhone and tap 「全部測る」 once / T-002 iPhone でフロントエンドの S1 テストページを開き、「全部測る」を 1 回タップする

Frontend has made a test page with a plaza scene you can walk around in on a phone (only you can open it), used to measure real-device frame rate; it takes about 2 minutes, and results are saved back to the page automatically. Frontend will ask you directly in its thread; this is only a summary.

フロントエンドが、スマホの中で歩ける広場のシーンのテストページを作った（開けるのはあなただけ）。実機のフレームレートを測るためのもので、約 2 分、結果は自動でページに保存される。フロントエンドが自分のスレッドで直接お願いするので、ここはまとめにすぎない。

### T-003 Create a new GCP project for 物語 (Monogatari) and run technical validation such as voice (you chose "create a new project", decisions D-011) / T-003 物語 (Monogatari) 用に GCP プロジェクトを新設し、音声などの技術検証を行う（あなたは「新規プロジェクト」を選択済み、decisions D-011）

**The commands are already written**: "What zg needs to do" in `backend/spikes/README.md`; the script bundle is `backend/spikes/dist/zoujin-spike.zip` (unzip it into `~/Developer/` after downloading).

**コマンドはすでに書いてある**：`backend/spikes/README.md` の「zg がすること」。スクリプト一式は `backend/spikes/dist/zoujin-spike.zip`（ダウンロード後 `~/Developer/` に展開する）。

1. Create a gcloud configuration used only for 物語 (Monogatari) (without changing 日々の森's default settings), create a new project, and link billing. The project ID and billing account ID stay only in your terminal.
   物語 (Monogatari) 専用の gcloud 設定を作り（日々の森のデフォルト設定は変えない）、プロジェクトを新設し、請求先を紐づける。プロジェクト ID と請求先アカウント ID はあなたのターミナルにだけ残す。
2. Enable 3 APIs: Vertex AI, Model Armor, Budgets.
   API を 3 つ有効にする：Vertex AI、Model Armor、予算。
3. Set a monthly budget alert of 5,000 yen (email only; it does not stop anything automatically).
   毎月 5,000 円の予算アラートを設定する（メールが届くだけで、自動では止まらない）。
4. Offline self-check (free), then try calling `gemini-3.8-live` (under 0.05 USD).
   オフラインの自己チェック（無料）をしてから、`gemini-3.8-live` の呼び出しを試す（0.05 米ドル未満）。
5. Run the validation: running everything costs about 2〜3 USD; the scripts keep their own ledger, stop automatically at 20 USD, and stop immediately on rate limiting.
   検証を実行する：全部実行して約 2〜3 米ドル。スクリプトが自分で台帳をつけ、20 米ドルで自動停止し、レート制限に当たったらすぐ止まる。

You do steps 0〜3 yourself (downloading and unzipping the script bundle, creating the project, linking billing, setting the budget alert). **For steps 4 and 5 you chose (2026-10-06): Claude on the Mac runs them while you watch.** After step 3, say "start the validation" in the "check the computer's development environment" thread. When it finishes, that thread sends the key numbers to backend and PM, and hands the `out/` archive to the PM thread.
Not needed now: creating a database, a load balancer or an API Key. Real-device voice testing on a phone over 4G needs a temporary deployment; backend writes a separate plan, and PM asks you separately.

第 0〜3 ステップ（スクリプト一式のダウンロードと展開、プロジェクトの作成、請求先の紐づけ、予算アラートの設定）はあなた自身が行う。**第 4、5 ステップはあなたが選んだとおり（2026-10-06）：Mac 上の Claude があなたの見ている前で実行する。** 第 3 ステップが終わったら、「パソコンの開発環境の確認」スレッドで「検証開始」と一言伝える。そちらで実行が終わったら、主な数値をバックエンドと PM に送り、`out/` の圧縮ファイルを PM スレッドに渡す。
今は不要：データベース、ロードバランサ、API Key の作成。スマホの 4G での音声の実測には一時的なデプロイが必要なので、バックエンドが別に方式を書き、PM が個別にあなたに聞く。

### T-005 For the phone 4G voice test, which way should the iPhone get a temporary address? / T-005 スマホの 4G での音声の実測で、どの方法で iPhone に一時的なアドレスを渡すか？

**Decided (2026-10-06): A, a temporary cloud service.** Your conditions: random URL, no product name or your name shown, password required. Recorded in decisions.md D-017. After the Mac-browser part passes, you will be asked to test on the iPhone.
Plan: `backend/spikes/s1b-plan.md`. A phone web page needs an HTTPS address to use the microphone, and the 4G test must connect in from the outside network; per section 9 of the handoff document and D-011 this counts as deployment and needs your explicit consent.

**決定（2026-10-06）：A、一時的なクラウドサービス。** あなたの条件：URL はランダム、プロダクト名とあなたの名前を出さない、パスワードが必要。decisions.md D-017 に記録した。Mac のブラウザでの部分が合格したら、iPhone でテストしてもらう。
方式：`backend/spikes/s1b-plan.md`。スマホのウェブページでマイクを使うには HTTPS のアドレスが必要で、4G の実測は外部ネットワークから接続しなければならない。引き継ぎ文書の第 9 節と D-011 によりこれはデプロイに当たり、あなたの明確な同意が必要。

- **A. Temporarily open a Cloud Run service in the 物語 (Monogatari) project (recommended)**: the same path as the production launch, so the numbers can directly serve as S-017 acceptance; needs 3 more APIs enabled (Cloud Run, Artifact Registry, IAM) and a service account that can only call Gemini (changing "no service accounts in the validation phase"); everything is deleted the same day after testing. About 0.5〜1 USD, counted against the 20 USD cap.
  **A. 物語 (Monogatari) のプロジェクトに一時的に Cloud Run のサービスを開く（推奨）**：正式公開と同じ経路なので、数値をそのまま S-017 の受け入れ確認に使える。API を 3 つ追加で有効にし（Cloud Run、Artifact Registry、IAM）、Gemini だけを呼べるサービスアカウントを作る（「検証段階ではサービスアカウントを作らない」を変更）。テスト後その日のうちにすべて削除する。約 0.5〜1 米ドルで、20 米ドルの上限に計上する。
- B. A temporary tunnel from the Mac: no new APIs, but the numbers include the home network and are only for reference; the Mac has to stay on.
  B. Mac から一時的なトンネルを開く：新しい API は不要だが、数値に家のネットワークが含まれるので参考にしかならない。Mac はずっと起動しておく必要がある。
- C. Do not test on the phone for now: no deployment; no answers for AirPods, LINE's in-app browser or 4G latency.
  C. 当面スマホではテストしない：デプロイはしない。AirPods、LINE のアプリ内ブラウザ、4G の遅延のいずれも答えが出ない。

Whichever is chosen, first do the Mac-browser part that needs no deployment. Before deployment, Claude on the Mac shows each command before running it; the address and one-time test code stay only on your Mac and do not go into chats; your consent covers only this one test.

どれを選んでも、まずデプロイ不要の Mac のブラウザでの部分を行う。デプロイの前に、Mac 上の Claude がコマンドを 1 つずつ表示してから実行する。アドレスと使い捨てのテストコードはあなたの Mac にだけあり、チャットには入れない。あなたの同意はこの 1 回のテストだけが対象。

### T-004 (no rush, optional) Have 3〜5 people around you try UX's prototype / T-004（急がない、任意）身近な 3〜5 人に UX のプロトタイプを試してもらう

UX wants to do the earliest playtest round (R0): using the prototype above, with UX beside them voicing the characters, to see whether the UI is understandable and how push-to-talk feels. No cost, about 15 minutes per person. If it is convenient, tell PM; if not, wait until the vertical slice is done.

UX は最も早い試遊の回（R0）を行いたい：上記のプロトタイプを使い、UX がそばで声で登場人物を演じ、UI がわかるか、押して話す操作の感触を見る。費用はかからず、1 人約 15 分。都合がよければ PM に伝え、難しければ垂直スライスができてから試す。

## Need to decide now (affects how the design phase is scheduled) / 今すぐ決める必要があるもの（設計フェーズの段取りに影響する）

(Q-001, Q-002 and Q-010 are all decided.)

（Q-001、Q-002、Q-010 はすべて決定済み。）

### Q-001 Enter the 5th Agentic AI Hackathon on 10/15? / Q-001 10/15 の第 5 回 Agentic AI Hackathon に参加するか？

**Decided (2026-10-06): A, not entering this time.** Recorded in decisions.md D-010.
You said "no rush on time, quality first". Submitting to the hackathon requires, by 2026-10-15 23:59, a URL deployed on Google Cloud that judges can play on a phone, plus a 3-minute video; that is 9 days from now, and the design documents are not even finished yet.

**決定（2026-10-06）：A、今回は参加しない。** decisions.md D-010 に記録済み。
あなたは「時間は急がない、品質第一」と言った。ハッカソンへの提出には、2026-10-15 23:59 までに、Google Cloud にデプロイされ審査員がスマホで遊べる URL と、3 分の動画が必要。今日から 9 日で、今はまだ設計文書すら完成していない。

| Option / 選択肢 | What happens / どうなるか |
|---|---|
| A. Skip this one and work at a quality pace (**recommended**) / A. 今回は参加せず、品質のペースで作る（**推奨**） | The design phase is not rushed; once done, look for the next suitable contest or release directly; the parts of the handoff document prepared for judges (judge Q&A, governance demo) remain useful / 設計フェーズを急がず、終わってから次の適切なコンテストを探すか直接リリースする。引き継ぎ文書の審査向けに用意した内容（審査の Q&A、ガバナンスのデモ）はそのまま役に立つ |
| B. Submit a small but complete slice / B. 小さくても完結したスライスを提出する | Only one scene, one character, one chain reaction, one ending; it must be a subset of the production version, with no throwaway code; it would take up the whole team for the next 9 days / シーン 1 つ、登場人物 1 人、連鎖反応 1 回、エンディング 1 つだけを作る。正式版の部分集合でなければならず、使い捨てのコードは書かない。チーム全員の今後 9 日を使う |
| C. Push hard to finish the full first version / C. 全力で初版を完成させる | Conflicts with "quality first"; not recommended / 「品質第一」と矛盾し、推奨しない |

Reasons for recommending A: finishing design, review, development, deployment and a video within 9 days could only be done by cutting quality, and this product's value lies precisely in things that need polish: "causality that makes sense, natural voice, smooth 3D on phones". Judging by when past rounds started (2024-12, 2025-04, 2025-08, 2025-12; see handoff.md "past winners"), there is a round about every 4 months, so missing this one is not costly (inferred: the 6th round has not been announced yet).

A を推奨する理由：9 日で設計、レビュー、開発、デプロイ、動画を終えるには品質を削るしかない。一方、このプロダクトの価値はまさに「筋の通った因果、自然な音声、スマホでなめらかな 3D」といった磨き込みが必要なところにある。過去の開始時期（2024-12、2025-04、2025-08、2025-12、handoff.md「過去の受賞」を参照）を見ると約 4 か月ごとに開かれており、今回を逃すコストは高くない（推測：第 6 回はまだ発表されていない）。

### Q-010 Open a GCP project now for technical validation? / Q-010 今すぐ GCP プロジェクトを開いて技術検証を行うか？

**Decided (2026-10-06): validate now, creating a new GCP project for 物語 (Monogatari).** Recorded in decisions.md D-011; what you need to do is in T-003.
Backend wants to use real Gemini calls to validate a few things that make or break the design: latency, interruption and naturalness of Japanese voice, whether the 7 characters' voices can be told apart, whether the narrator's self-check is accurate, whether characters spoil the original, and how much each game actually costs.

**決定（2026-10-06）：今すぐ検証し、物語 (Monogatari) 用に GCP プロジェクトを新設する。** decisions.md D-011 に記録済み。あなたがすることは T-003 を参照。
バックエンドは実際の Gemini の呼び出しで、設計の成否を決めるいくつかのことを検証したい：日本語の音声の遅延、割り込み、自然さ、7 人の登場人物の声を聞き分けられるか、ナレーターの自己チェックは正確か、登場人物が原作をネタバレしないか、1 局に実際いくらかかるか。

| Option / 選択肢 | What happens / どうなるか |
|---|---|
| A. Open it now, with a validation budget cap of 20 USD (**recommended**) / A. 今すぐ開き、検証の予算上限は 20 米ドル（**推奨**） | The numbers in design v1.0 are finalized with measurements; if voice does not meet the bar, we can switch approaches early (backend already has a cascaded approach ready) / 設計 v1.0 の数値を実測で確定できる。音声が基準に届かなければ早めに方式を替えられる（バックエンドはカスケード方式を用意済み） |
| B. Wait until design v1.0 is written / B. 設計 v1.0 を書き終えてから開く | Latency, cost and spoiler thresholds in the design are only estimates, and finding problems late means more rework / 設計の中の遅延、コスト、ネタバレの閾値はどれも見積もりにすぎず、問題の発見が遅れるほど手戻りが大きい |

Reasons for recommending A: voice is the core of the whole experience and the most likely to fall short; with a 20 USD cap, validating first is cheaper than writing the full design on estimates. Validation-phase spending is mainly model calls, capped at 20 USD; fixed monthly fees such as databases and load balancers (about 30〜70 USD per month in total, [estimate]) will be asked of you separately when we actually deploy.

A を推奨する理由：音声は体験全体の核であり、最も基準に届かない可能性が高いところでもある。上限 20 米ドルなら、見積もりで設計一式を書き上げるより先に検証した方が安くつく。検証段階の費用は主にモデルの呼び出しで、上限は 20 米ドル。データベースやロードバランサといった固定の月額費用（合計で月約 30〜70 米ドル、〔推算〕）は、実際にデプロイするときに改めて個別に聞く。

### Q-002 Who is the primary user of the first version? / Q-002 初版の主なユーザーは誰か？

**Decided (2026-10-06): confirmed by zg ("No problem").** Recorded in decisions.md S-022.
The primary users are Japanese adults aged 18〜34 who already enjoy "step into the story" entertainment, such as chatting with AI characters, 推し活, マダミス, リアル脱出ゲーム and ノベルゲーム. The first version is for ages 18 and up; middle-school students and Japanese teachers go to phase two; overseas Japanese learners are not targeted in the first version.
Reasons (research.md §1):

**決定（2026-10-06）：zg が確認（「問題ない」）。** decisions.md S-022 に記録。
主なユーザーは、すでに「物語に入る」系の娯楽を楽しんでいる 18〜34 歳の日本の成人で、例えば AI キャラクターとのチャット、推し活、マダミス、リアル脱出ゲーム、ノベルゲーム。初版の対象は 18 歳以上。中学生と国語の教師は第 2 段階に回す。海外の日本語学習者は初版では対象にしない。
理由（research.md §1）：

- "Having read 『走れメロス』" is a shared premise of almost all Japanese people (it is in the 2nd-year middle-school textbook, studied by about 1.03 million people a year), so it cannot be used to segment people.
  「『走れメロス』を読んだことがある」は日本人のほぼ全員に共通する前提なので（中 2 の教科書にあり、毎年約 103 万人が学ぶ）、人を区別するためには使えない。
- The people really close to us are young adults who already spend money on "taking part in a story" and often use AI chat: generative AI usage among 15〜24-year-olds is 83.1%; one マダミス session costs 2,500〜8,500 yen.
  本当に私たちに近いのは、すでに「物語への参加」にお金を払い、AI チャットもよく使う若い成人：15〜24 歳の生成 AI の利用率は 83.1%。マダミスは 1 回 2,500〜8,500 円。
- If minors are included in the first version, governance, privacy and a teacher panel would all have to be done together, making the scope much larger.
  未成年を初版に入れると、ガバナンス、プライバシー、教師用パネルを一緒に作る必要があり、範囲がずっと大きくなる。

## To decide during the design phase (PM gives a recommendation first, and asks you to decide once the relevant roles' proposals are in) / 設計フェーズ中に決めるもの（PM がまず推奨を出し、関係するロールの案が出てからあなたに決めてもらう）

### Q-003 Product name / Q-003 プロダクトの名前

The current working title is a Chinese name ("Step into the Story"), and the Japanese market needs a Japanese name. Market research has given 3 candidates (market-research/positioning.md §7):

現在の仮称は中国語の名前（「物語の中へ」の意）で、日本市場には日本語の名前が必要。市場調査が 3 つの候補を出した（market-research/positioning.md §7）：

- **フミイリ** (recommended): 「踏み入る」 + 「文」, a coined word, easy to say; the meaning is not obvious, so it needs a subtitle, e.g. 「フミイリ ―『走れメロス』に入る」.
  **フミイリ**（推奨）：「踏み入る」+「文」の造語で、言いやすい。意味がわかりにくいのでサブタイトルが必要。例：「フミイリ ―『走れメロス』に入る」。
- ヨミイル (conditional): 「読み入る」; it sounds close to ヨミウリ, medium trademark risk.
  ヨミイル（条件付き）：「読み入る」。読みがヨミウリに近く、商標のリスクは中程度。
- ページのむこう (conditional): sounds like an everyday phrase, better suited as a subtitle.
  ページのむこう（条件付き）：よくある言い回しのようで、サブタイトルの方が向いている。

**Note: none of the trademarks have been checked yet.** Market research's environment cannot open J-PlatPat. Before deciding on a name, someone must use J-PlatPat's 「称呼検索」 to check classes 9, 41 and 42, or ask a 弁理士 to check.
This does not block design; PM will ask you to choose at a suitable time, and the trademark will be checked before you choose.

**注意：商標はまだ 1 つも調べていない。** 市場調査の環境では J-PlatPat を開けない。名前を決める前に、誰かが J-PlatPat の「称呼検索」で第 9、41、42 類を調べるか、弁理士に調べてもらう必要がある。
設計は止めない。PM が適切なときにあなたに選んでもらい、選ぶ前に商標を調べる。

### Q-004 3D art style and character voices / Q-004 3D の画風と登場人物の声

**Art direction decided (2026-10-06): high-definition, stunning, realistic** (decisions D-016). After seeing the three stylized samples A 絵本 / B 木版 / C 影絵, you chose realistic.
Next step: UX and frontend build a sample in the realistic direction, measure frame rate and load time on iPhone, then bring the visuals and numbers to you to decide two things: the final degree of realism; and whether to raise the minimum supported device and loosen the size of a single scene for the sake of image quality.

**画風の方向は決定（2026-10-06）：高精細、息をのむほど、写実的**（decisions D-016）。A 絵本／B 木版／C 影絵 の 3 つの様式化サンプルを見て、あなたは写実を選んだ。
次のステップ：UX とフロントエンドが写実方向のサンプルを作り、iPhone でフレームレートと読み込み時間を測り、画面と数値を持ってあなたに 2 つのことを決めてもらう：最終的な写実の度合い。画質のために対応する最低機種を上げ、1 シーンのサイズを緩めるかどうか。

- 2026-10-06 progress: the S7 realistic sample has been published, and zg tested it once on their own iPhone 17 Pro Max (almost everything pinned at 60 fps, which cannot be extrapolated to an iPhone 12); after frontend adds a load-test version, zg will be asked to test once more. UX has looked at the visuals: the sunset is too white, the backlit fog washes out, and noon and dusk cannot be told apart; frontend is tuning. zg newly raised (frontend thread, 14:3xZ): "Different iPhones, different configurations, different effects; my 17 pro max can go a bit higher" → an option is added to the choice card: baseline iPhone 12 at tier B, with strong devices automatically upgrading to tier C's effects (cost: the art is made at the highest tier and then exported to lower versions, increasing the workload and strong devices' downloads).
  2026-10-06 の進捗：S7 の写実のサンプルを公開し、zg が自分の iPhone 17 Pro Max で 1 回テストした（ほぼすべて 60 fps に張り付いており、iPhone 12 の結果は推測できない）。フロントエンドが負荷テスト版を加えたら、zg にもう一度テストしてもらう。UX が画面を見たところ、夕日が白っぽく、逆光の霧が白く飛び、正午と夕方の区別がつかないので、フロントエンドが調整している。zg が新たに提起（フロントエンドスレッド、14:3xZ）：「iPhone ごとに構成も効果も違う。自分の 17 pro max はもう少し高くていい」→ 選択カードに選択肢を 1 つ加える：基準の iPhone 12 は段階 B、性能の高い端末は自動で段階 C の効果に上げる（代償：美術は最高段階で作ってから低い版を書き出すので、作業量と性能の高い端末のダウンロード量が増える）。
- **The visuals half is decided (2026-10-06 22:28Z, D-019)**: zg chose "tier B + strong-device upgrade" on the card. Still to do: measure once on an old iPhone (12〜14) when available, replacing the iPhone 12 estimates with measurements.
  **画面の半分は決定（2026-10-06 22:28Z、D-019）**：zg がカードで「段階 B + 高性能端末の引き上げ」を選んだ。残り：古い iPhone（12〜14）が手に入ったら 1 回実測し、iPhone 12 の推算値を実測値に置き換える。

**The voice half is decided (2026-10-10, D-025)**: zg chose the seven characters' voices on the blind-listening page, both same-scene pairs were "can tell apart", and zg said "The voices are fine". The three untested pairs are handed to the R1 observation sheet. Both halves of Q-004 are decided.
The voice half (the earlier process follows): wait until after listening in backend's voice validation (S-1) before asking you to decide.

**声の半分は決定（2026-10-10、D-025）**：zg がブラインド試聴ページで 7 人の登場人物の声を選び、同じ場面の 2 組はどちらも「聞き分けられる」で、zg：「声は問題ない」。テストしていない 3 組は R1 の観察シートに回す。Q-004 は両方の半分とも決定した。
声の半分（以下はそれまでの経緯）：バックエンドの音声検証（S-1）で試聴してから、あなたに決めてもらう。

- 2026-10-06 progress: in S-1, 19 voices returned no text; it turned out the text for long lines arrived late, not that the voices were broken (all 12 questions of the s3 scenario using Iapetus had text), and the new package fixes it. When casting is rerun with the new package, besides the candidates in ux-design §16, UX's fallback combinations are also included (ux/casting-fallback.md, 7 of them, about 0.15 USD), and a blind-listening pair 「刑場：老爺 vs 王」 is added. Risk: if none of the candidates for 妹 sounds 16 years old, you will be asked to decide with the listening results.
  2026-10-06 の進捗：S-1 で 19 の声がテキストを返さなかったが、長いセリフのテキストが遅れて届いていたためで、声が壊れていたのではないとわかった（Iapetus を使った s3 のシナリオの 12 問にはすべてテキストがあった）。新しいパッケージで修正済み。新しいパッケージで casting を再実行するときは、ux-design §16 の候補に加えて UX の予備の組み合わせ（ux/casting-fallback.md、7 つ、約 0.15 米ドル）も入れ、ブラインド試聴の組「刑場：老爺 vs 王」を加える。リスク：妹の候補がどれも 16 歳らしく聞こえなければ、試聴の結果を持ってあなたに決めてもらう。
- 2026-10-07 progress: the cause of the missing text was found; it occurs only in the test-only "read this line verbatim" setting (one session per line 41/42, consecutive reading 21/42); when characters speak as themselves, all 42 turns had text, and together with s3's 150 free-dialogue questions, 192 turns had 0 missing. In the product all character speech uses the speaking-as-themselves setting, and fill-in transcription is not the main path (word error rate p90 33〜56%). Confirmed by backend and recorded as S-071. The blind-listening conclusions are unaffected.
  2026-10-07 の進捗：テキストがない原因がわかった。テスト用の「このセリフをそのまま読む」設定でだけ起きる（1 文 1 セッション 41/42、続けて読む 21/42）。登場人物が自分として話すときは 42 ターンすべてにテキストがあり、s3 の自由な会話 150 問を合わせて 192 ターンで欠落 0。プロダクトでは登場人物の発話はすべて自分として話す設定を使い、補完の文字起こしは主経路にしない（文字誤り率 p90 33〜56%）。バックエンドが確認し、S-071 として記録した。ブラインド試聴の結論には影響しない。

### Q-005 Whether to formally add a school / education positioning (teacher panel) / Q-005 学校 / 教育向けの位置づけ（教師用パネル）を正式に加えるか

Recommendation: no teacher panel in the first version, focusing on adults; content rating and not collecting personal information are still done (the PRD already lists them as P0), so turning to education later will not mean starting over. Reason: with minors as primary users, governance, privacy and a teacher panel would all have to be in the first version, making the scope much larger, which conflicts with "small scope, done well".
**New constraint (S-060)**: as long as Gemini is used, an educational version aimed at middle-school students cannot be made, unless we switch model vendor or negotiate separate terms with Google.
Market research's evidence supports this recommendation: 国語 has no free national digital teaching materials, digital textbooks are only formalized from fiscal 2030, and schools purchase on annual budgets. So education fits phase two, with a version "teachers can try for free directly in class" to acquire users (research.md §1.4).

推奨：初版では教師用パネルは作らず、成人を主な対象とする。コンテンツのレーティングや個人情報を集めないことは従来どおり行う（PRD で P0 に挙げ済み）ので、後で教育に向かうときに一から作り直す必要はない。理由：未成年を主なユーザーにすると、ガバナンス、プライバシー、教師用パネルをすべて初版に入れる必要があり、範囲がずっと大きくなり、「範囲を小さく、作り込む」と矛盾する。
**新たな制約（S-060）**：Gemini を使う限り、中学生向けの教育版は作れない。モデルの提供元を替えるか、Google と別途条項を交渉しない限り。
市場調査の証拠もこの推奨を支持する：国語には国の無料のデジタル教材がなく、デジタル教科書の正式化は 2030 年度で、学校は年度予算で購入する。したがって教育は第 2 段階に回し、「教師が授業でそのまま無料で試せる」版で利用者を獲得するのが適している（research.md §1.4）。

### Q-006 Is an ending short film (Veo) required? / Q-006 エンディングの短編動画（Veo）は必須か

Recommendation: no short film in the first version; the ending uses an in-scene 3D performance + an ending illustration (Nano Banana, about 5 seconds to generate) for the ending card; the short film goes to P2, and could be made into "sent to you afterwards". Backend makes the same recommendation.
Reasons (backend's estimate, [estimate], to be replaced by spike measurements): without a short film a game costs about 1.0〜1.2 USD (150〜180 yen); adding an 8-second short film costs 0.8〜3.2 USD more per game, with a 1〜4 minute wait. The ending is exactly the moment players most want to see the result right away; they should not be made to wait.

推奨：初版では短編動画は作らず、エンディングは 3D のシーン内の演出 + エンディングの挿絵（Nano Banana、生成に約 5 秒）でエンディングカードを作る。短編動画は P2 に回し、「後であなたの手元に届く」形にもできる。バックエンドも同じ提案。
理由（バックエンドの見積もり、〔推算〕、spike の実測で置き換える）：短編動画なしなら 1 局約 1.0〜1.2 米ドル（150〜180 円）。8 秒の短編動画を加えると 1 局あたり 0.8〜3.2 米ドル増え、1〜4 分待つ。エンディングはまさにプレイヤーが結果をすぐ見たい瞬間で、待たせるべきではない。

### Q-007 Business model: who pays / Q-007 ビジネスモデル：誰がお金を払うか

Recommendation: the first version is free; first use human playtests to validate "people want to finish, want to play again, want to share". Later, first validate "buy a book outright + a free prologue of about 5 minutes"; schools and municipalities go to phase two, and partnerships in culture, tourism, publishing and so on are done when the other side comes to us (research.md §3).
Reasons:

推奨：初版は無料にし、まず実際の人の試遊で「最後まで遊びたい、もう一度遊びたい、共有したい」と思われるかを検証する。その後、まず「1 冊買い切り + 約 5 分の無料プロローグ」を検証し、学校と自治体は第 2 段階に回し、文化、観光、出版などとの協業は先方から声がかかったら行う（research.md §3）。
理由：

- Backend estimates about 198 yen per game (S-058); giving away a full game for free would lose money, so the free part can only be a prologue (cut at a narrative endpoint, S-052, about 50 yen per person).
  バックエンドの見積もりでは 1 局約 198 円（S-058）で、1 局まるごと無料で提供すると赤字になるので、無料部分はプロローグに限られる（物語の区切りで切る、S-052、1 人約 50 円）。
- Market research recalculated with this cost (research §3): a paying user playing 3 games costs about 590 yen; selling at 980 yen gives about 40% gross margin, at 1,480 yen about 60% (before payment fees and fixed monthly costs). 980 yen is tight and relies on S-058's cost-cutting levers.
  市場調査がこのコストで再計算した（research §3）：課金ユーザーが 3 局遊ぶと約 590 円。980 円で売れば粗利は約 40%、1,480 円なら約 60%（決済手数料と固定の月額費用は差し引く前）。980 円は厳しく、S-058 のコスト削減の手段に頼ることになる。
- The price is tested first in playtests with four questions, roughly estimated at 980〜1,480 yen per book [inferred, to be tested].
  価格はまず試遊で 4 つの質問で測る。大まかな見積もりは 1 冊 980〜1,480 円〔推測、要テスト〕。
- Being free does not affect any design decision.
  無料であることはどの設計上の決定にも影響しない。

You do not need to decide now; you will be asked once the first version is done and there is playtest data.

今決める必要はない。初版ができて試遊のデータがそろってから聞く。

### Q-008 Human playtests: who and what to test / Q-008 実際の人による試遊：誰に、何を測るか

The plan has been written by market research (market-research/playtest-plan.md, reviewed by PM). Two rounds:

方式は市場調査が書き上げた（market-research/playtest-plan.md、PM がレビュー済み）。2 回に分ける：

- R1: after the vertical slice (M2), 6〜8 people, observed while they play, to find where they get stuck and confused.
  R1：垂直スライス（M2）の後、6〜8 人。そばで観察しながら遊んでもらい、詰まるところと戸惑うところを見つける。
- R2: after the first version (M4), observe 8〜12 people, plus a controlled experiment with ≥ 30 people per group, comparing engagement between "read the original" and "play a game".
  R2：初版（M4）の後、8〜12 人を観察し、さらに各群 ≥ 30 人の対照実験を加え、「原文を読む」と「1 局遊ぶ」の没入の度合いを比べる。

Participants are recruited per Q-002's primary users, only those 18 and over.
What you need to decide (**asked before M2; no need to decide now**): where playtest screen recordings, audio recordings and contact details are stored (market research's playtest-plan §3.4 says who can see them and how long until deletion); the budget for participant compensation (market research's rough estimate is 1,000〜3,000 yen per person for 60 minutes [inferred]); whether to use an outside research firm to recruit (costs money); whether people can be recruited from those around you (acquaintances at most one third).

参加者は Q-002 の主なユーザーに沿って募集し、18 歳以上だけを募る。
あなたに決めてもらうこと（**M2 の前に聞くので、今は決めなくてよい**）：試遊の画面録画、録音、連絡先をどこに保存するか（市場調査の playtest-plan §3.4 に誰が見られるか、いつ削除するかを書いてある）。試遊者への謝礼の予算（市場調査の大まかな見積もりは 1 人 60 分 1,000〜3,000 円〔推測〕）。外部の調査会社を使って人を集めるか（費用がかかる）。あなたの身近な人から募ってよいか（知人は最大 3 分の 1）。

### Q-009 The second book / Q-009 2 冊目の本

Later (candidate: 『銀河鉄道の夜』).

後で考える（候補『銀河鉄道の夜』）。

### Q-011 At public launch, how to handle minors? (asked before launch; no need to decide now) / Q-011 正式公開時、未成年をどう扱うか？（公開前に改めて聞く、今は決めなくてよい）

The first version is only for ages 18 and up, and in the invite-code phase only people 18 and over are invited (decisions S-022). This only needs deciding at public launch.
PM's current recommendation: stay 18 and up only; before entering, add a yes/no confirmation 「18歳以上ですか」, only confirming, without storing age.
Reason: if minors can play, there must be protection for minors and a teacher panel, which is phase two's scope. Character.AI closed open-ended chat to minors in 2025-11.
**New constraint (2026-10-06, decisions S-060)**: Google's terms do not allow Gemini to be used in services directed at people under 18, or likely to be accessed by people under 18. 『走れメロス』 is a middle-school textbook text, so before public launch someone who knows Japanese law and Google's terms must confirm whether a 「18歳以上ですか」 check alone is enough; promotion must also not target students.
**To ask in the same legal review (2026-10-06, S-1 results)**: where players' words are processed. Gemini Live, used for character voices, only has endpoints in the United States and Europe; the safety detection Model Armor does not support multilingual detection including Japanese in Tokyo, so the production version is also in the United States (us-central1, with an official source; see section 6 of `backend/spikes/results-s1.md`). Backend suggests the privacy notice uniformly say 「日本で保存し、音声と文字の処理は米国で行います」. A lawyer needs to confirm: under Japan's Act on the Protection of Personal Information, what notice or consent is needed to send players' words to the United States for processing.

初版の対象は 18 歳以上だけで、招待コードの段階でも 18 歳以上の人だけを招待する（decisions S-022）。正式公開のときに初めて決める必要がある。
PM の現在の推奨：引き続き 18 歳以上だけを対象にする。入る前に「18歳以上ですか」のはい/いいえの確認を加え、確認するだけで年齢は保存しない。
理由：未成年が遊べるなら、未成年の保護と教師用パネルが必要になり、それは第 2 段階の範囲。Character.AI は 2025-11 に未成年向けの自由なチャットを閉じた。
**新たな制約（2026-10-06、decisions S-060）**：Google の条項では、18 歳未満向けのサービス、または 18 歳未満が利用する可能性が高いサービスに Gemini を使うことを認めていない。『走れメロス』は中学の教材なので、正式公開の前に、日本の法律と Google の条項に詳しい人に、「18歳以上ですか」の確認だけで十分か確認してもらう必要がある。宣伝も学生を対象にしてはならない。
**同じ法務確認でさらに聞くこと（2026-10-06、S-1 の結果）**：プレイヤーの言葉がどこで処理されるか。登場人物の音声に使う Gemini Live には米国と欧州のエンドポイントしかない。安全検出の Model Armor は東京では日本語などの多言語検出に対応していないので、正式版も米国に置く（us-central1、公式の出典あり、`backend/spikes/results-s1.md` 第 6 節を参照）。バックエンドはプライバシー説明に一律で「日本で保存し、音声と文字の処理は米国で行います」と書くことを提案している。弁護士に確認してもらう必要がある：日本の個人情報保護法の下で、プレイヤーの言葉を米国に送って処理するには、どのような告知または同意が必要か。

### Q-012 When to open ending share links? (asked before launch; no need to decide now) / Q-012 エンディングの共有リンクをいつ開放するか？（公開前に改めて聞く、今は決めなくてよい）

The first version first does "save the ending card as an image" (decisions S-026). Share links viewable without logging in have already been designed within the privacy boundaries: ending card only, no player words or memories, unguessable links, revocable. Not opened in the invite-code phase; you will be asked together with the public launch.

初版ではまず「エンディングカードを画像として保存」を作る（decisions S-026）。ログインせずに見られる共有リンクはプライバシーの境界に沿ってすでに設計済み：エンディングカードだけで、プレイヤーの言葉や記憶は含まず、リンクは推測できず、取り消せる。招待コードの段階では開かず、正式公開のときに公開と一緒にあなたに聞く。

## Where the handoff document's "open questions" went / 引き継ぎ文書の「未決の問い」の行き先

| Open question in the handoff document / 引き継ぎ文書の未決の問い | Current status / 現在の状態 |
|---|---|
| Product name / プロダクトの名前 | Q-003 |
| List of identities and each identity's starting point / 身元の一覧と各身元の開始地点 | PM has decided 3 identities for the first version (PRD §6.1), awaiting UX review; you can change it directly if you disagree / PM が初版の身元を 3 つに決めた（PRD §6.1）。UX のレビュー待ち。意見があれば直接変えてよい |
| Which 3〜4 scenes in the first version, and which characters can be talked to / 初版でどの 3〜4 シーンを作り、どの登場人物と会話できるか | PM has decided 4 scenes and 7 talkable characters (PRD §6.1), awaiting UX review; you can change it directly if you disagree / PM がシーン 4 つと会話できる登場人物 7 人に決めた（PRD §6.1）。UX のレビュー待ち。意見があれば直接変えてよい |
| Platform / プラットフォーム | Decided: web only, mobile browser first (decisions D-008) / 決定：ウェブのみ、モバイルブラウザ優先（decisions D-008） |
| Art direction and each character's voice / 画風の方向と各登場人物の声 | Q-004 |
| Whether to formally add a school / education positioning / 学校 / 教育向けの位置づけを正式に加えるか | Q-005 (market research's evidence supports "not in the first version") / Q-005（市場調査の証拠は「初版では作らない」を支持） |
| Human playtests: who and what to test / 実際の人による試遊：誰に、何を測るか | Q-008 (plan written; compensation budget asked before M2) / Q-008（方式は作成済み、謝礼の予算は M2 の前に聞く） |
| Whether an ending short film is required / エンディングの短編動画は必須か | Q-006 |
| Business model / ビジネスモデル | Q-007 (first version free; later first validate buying a book outright + a free prologue) / Q-007（初版は無料。後でまず 1 冊買い切り + 無料プロローグを検証） |
| Confirming against the original text "what happens on which day" in the original / 原作で「何日目に何が起きるか」を原文と照らして確認 | No need for you to decide: PM and data engineering check it against the Aozora Bunko text / あなたが決める必要はない：PM とデータエンジニアリングが青空文庫の原文と照合する |
