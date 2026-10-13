# S-1b: deployment plan for iPhone 4G measurement v0.7 / S-1b：iPhone 4G 実測のためのデプロイ計画 v0.7

> Written by backend. **zg chose A (`pm/decisions.md` D-017); the consent covers this one test only**, with three conditions (section 4, "D-017's three conditions"). On 10-07 we tried three times, and all three stopped at `up`; `open` was never run, no public address ever existed, and each was deleted the same day: the first time, the non-root user could not read the code in the image; the second time the service was fine, but the script's private check used `/healthz`, which Cloud Run reserves; the third time the service account could not connect to Live in the cloud (see the revision history and results-s1 8.3). Testing again needs zg's consent, including the two items new in v0.7 (section 4 "APIs to enable" and the service-account row). Deployment addresses, test codes and credentials never go into the repo, documents or chat. Run instructions: `mac-s1b-run.md`.
> Merged with frontend's spike S2 (`frontend/frontend-design.md` section 16).
>
> バックエンドが作成。**zg は A を選んだ（`pm/decisions.md` D-017）。同意は今回のテスト 1 回だけが対象**で、3 つの条件付き（第 4 節「D-017 の 3 つの条件」）。10-07 に 3 回試し、3 回とも `up` で止まった。`open` は実行しておらず、公開アドレスが出たことは一度もなく、毎回当日中に削除した：1 回目はイメージ内のコードを非 root ユーザーが読めなかった。2 回目はサービスは正常だったが、スクリプトの非公開チェックが Cloud Run の予約している `/healthz` を使っていた。3 回目はサービスアカウントがクラウド上で Live に接続できなかった（改訂履歴と results-s1 8.3 を参照）。再テストには zg の同意が必要で、v0.7 で新たに加えた 2 項目（第 4 節「追加で有効にする API」とサービスアカウントの行）も含む。デプロイ先のアドレス、テストコード、認証情報はリポジトリ、ドキュメント、チャットに入れない。実行手順：`mac-s1b-run.md`。
> フロントエンドの spike S2（`frontend/frontend-design.md` 第 16 節）を統合した。

## 1. zg's decision (D-017) / 1. zg の決定（D-017）

Measuring on iPhone 4G needs an HTTPS address a phone can open. zg chose **A: temporarily run a Cloud Run service in the 物語 (Monogatari) GCP project and delete it the same day after testing**. Reason: the path is the same as the real launch (phone → Tokyo → Live in the US), so the S-017 acceptance numbers (median ≤ 1.8 seconds, p95 ≤ 3 seconds) apply directly. Not chosen: B, a tunnel from the Mac (the numbers would include the home network and could not be used for acceptance); C, not testing on phones.

iPhone の 4G で実測するには、スマホで開ける HTTPS のアドレスが必要。zg は **A：物語 (Monogatari) の GCP プロジェクトに一時的に Cloud Run のサービスを立て、テストした当日に削除する**を選んだ。理由：経路が本番と同じ（スマホ → 東京 → 米国の Live）なので、S-017 の受け入れ確認の数値（中央値 ≤ 1.8 秒、p95 ≤ 3 秒）をそのまま使える。選ばなかったもの：B は Mac からトンネルを開く（数値に自宅のネットワークが含まれ、受け入れ確認に使えない）。C はスマホでテストしない。

## 2. Why it has to be a public address / 2. なぜ公開アドレスが必要か

- Web pages on an iPhone can use the microphone only over HTTPS; `localhost` counts as secure only in the Mac's own browser.
  iPhone のウェブページは HTTPS でなければマイクを使えない。`localhost` が安全とみなされるのは Mac 自身のブラウザの中だけ。
- What we are testing is 4G (Wi-Fi off), so the phone has to connect from the outside network.
  テストするのは 4G（Wi-Fi オフ）なので、スマホは外部のネットワークから接続しなければならない。
- Whether the LINE in-app browser can use the microphone, and whether the WebSocket handshake carries the cookie, can only be tested on a real address (frontend sections 2 and 7).
  LINE のアプリ内ブラウザでマイクが使えるか、WebSocket のハンドシェイクに Cookie が付くかは、実際のアドレスでしかテストできない（フロントエンドの第 2、7 節）。

## 3. Two parts; the first needs no deployment / 3. 2 段に分け、第 1 段はデプロイ不要

| Part / 段 | Where / どこで | Deployment needed? / デプロイが必要か | What is tested / 何をテストするか |
|---|---|---|---|
| Part 1 / 第 1 段 | zg's Mac: both the proxy and the test page run on `localhost`, opened in Safari / Chrome on the Mac / zg の Mac：プロキシとテストページはどちらも `localhost` で動かし、Mac の Safari / Chrome で開く | No / 不要 | Capture, downsampling, playback, local stop of playback on barge-in (frontend S-014's three numbers); server-side release-to-first-audio; whether the protocol flows smoothly / 収録、ダウンサンプリング、再生、割り込み時のローカルでの再生停止（フロントエンド S-014 の 3 つの数値）。サーバー側の離してから最初の音まで。プロトコルが滑らかに流れるか |
| Part 2 / 第 2 段 | Cloud Run (option A) / Cloud Run（選択肢 A） | **Needs zg's consent / zg の同意が必要** | The checklist in section 5 / 第 5 節のチェックリスト |

Part 1 is run by Claude on the Mac (same as T-003) and needs no extra consent; the commands are in `README.md` "Step 5b: S-1b first part". Part 2 is asked about only after part 1 passes.

第 1 段は Mac 上の Claude が実行し（T-003 と同じ）、追加の同意は不要。コマンドは `README.md` の「ステップ 5b：S-1b 第一段」にある。第 2 段は第 1 段が通ってから聞く。

## 4. How part 2 works (option A) / 4. 第 2 段のやり方（選択肢 A）

**What will be created (all deleted after testing) / 作成されるもの（テスト後にすべて削除）:**

| Thing / もの | Settings / 設定 |
|---|---|
| 1 Cloud Run service with a random name (`s-` plus 8 characters, generated on the Mac at deploy time, recorded in `~/.zoujin-spike/s1b-service`) / Cloud Run のサービス 1 つ。名前はランダム（`s-` に 8 文字、デプロイ時に Mac 上で生成し、`~/.zoujin-spike/s1b-service` に記録） | asia-northeast1; at most 1 instance, at most 4 connections; minimum 0 (no cost when idle); request timeout 60 minutes; no database, no mounted storage; no traffic tags / asia-northeast1。インスタンスは最大 1、接続は最大 4。最小 0（使っていないときは費用がかからない）。リクエストのタイムアウト 60 分。データベースにはつながず、ストレージもマウントしない。トラフィックタグは使わない |
| 1 image repository `spike-images` (Artifact Registry) / イメージリポジトリ `spike-images` 1 つ（Artifact Registry） | Built with Docker on the Mac (`linux/amd64`) and pushed here; no Cloud Build / Mac 上の Docker でビルドし（`linux/amd64`）、ここにプッシュする。Cloud Build は使わない |
| 1 service account `s1b-proxy` / サービスアカウント `s1b-proxy` 1 つ | **Only** `roles/aiplatform.user` (to call Gemini Live); do not use the default Compute service account (it has editor permissions). This is one change to G-7 "no service accounts during validation", because a cloud service must have an identity. From v0.7, zg's own account gets one more role on this service account, "Service Account Token Creator", used only for `sacheck` before deployment (connecting to Live once on the Mac as this identity, without creating keys); this role is attached to the service account, and disappears with it when `down` deletes the service account / **`roles/aiplatform.user` だけ**を付与（Gemini Live を呼ぶため）。デフォルトの Compute サービスアカウントは使わない（編集者の権限を持っているため）。これは G-7「検証段階ではサービスアカウントを作らない」に対する 1 か所の変更で、クラウドのサービスには必ず ID が必要なため。v0.7 から、zg 自身のアカウントにこのサービスアカウント上の「サービス アカウント トークン作成者」ロールを 1 つ追加する。デプロイ前の `sacheck`（Mac 上でこの ID として Live に 1 回接続する、鍵は作らない）だけに使う。このロールはサービスアカウントに付いているので、`down` でサービスアカウントを削除すると一緒に消える |

**APIs to enable (4) / 追加で有効にする API（4 つ）:** Cloud Run, Artifact Registry, IAM, and, new in v0.7, IAM Service Account Credentials (`sacheck` goes through it to borrow the service account's identity; without it, this request would be billed to the 日々の森 project written in zg's login file). None of them cost anything.

Cloud Run、Artifact Registry、IAM、そして v0.7 で追加した IAM Service Account Credentials（`sacheck` がサービスアカウントの ID を借りるときにこれを通る。有効にしないと、このリクエストは zg のログインファイルに書かれた 日々の森 のプロジェクトに計上される）。いずれも無料。

**What runs in the service / サービスで動かすもの:**

- Backend's voice proxy: a subset of api-contract section 3 (`hello` / `welcome`, `focus` / `session_ready`, `activity_start` / `activity_end`, upstream and downstream audio frames, `transcript`, `interrupted`, `turn_complete` with `serverReleaseToFirstAudioMs`). The subset is used so that the frontend test page's code can later go straight into the product.
  バックエンドの音声プロキシ：api-contract 第 3 節の一部（`hello` / `welcome`、`focus` / `session_ready`、`activity_start` / `activity_end`、上り・下りの音声フレーム、`transcript`、`interrupted`、`serverReleaseToFirstAudioMs` 付きの `turn_complete`）。この一部を使うのは、フロントエンドのテストページのコードを後でそのまま製品に残せるようにするため。
- Frontend's S2 test page, same-origin with the proxy (as in the real launch).
  フロントエンドの S2 テストページ。プロキシと同一オリジン（本番と同じ）。
- One character (メロス, with the voice chosen in S-1 `casting`) and a fixed short persona; no narrator, no world state. Voiding a turn is not supported (it needs the narrator).
  登場人物 1 人（メロス、S-1 の `casting` で選んだ声）と固定の短い人物設定。ナレーターも世界状態もない。ターンの取り消しには対応しない（ナレーターが必要なため）。

**How D-017's three conditions are met / D-017 の 3 つの条件の満たし方:**

1. **The URL is random and cannot be guessed**: a Cloud Run URL consists of the service name and the project number, and the service name is randomly generated on every deployment; no traffic tags (the first deployment cannot use 0% traffic anyway, so we use "private first" instead, see the release order below).
   **URL はランダムで推測できない**：Cloud Run の URL はサービス名とプロジェクト番号からなり、サービス名はデプロイのたびにランダムに生成する。トラフィックタグは使わない（初回のデプロイではそもそも 0% トラフィックにできないので、「まず非公開」で代える。下の公開の順序を参照）。
2. **No product name and no zg name in the URL, page, response headers or error text**: the service name is random; the cookie name is `sid`; no `Server` response header is sent; the placeholder page says only 「準備中です。」; all errors are generic short Japanese phrases. The offline self-check verifies item by item that the page, response headers, cookies and WebSocket errors contain neither the product's working name nor "zoujin". The frontend test page's title and text follow this rule too (frontend has been told). The image repository, service account and local directory do not appear in the URL, and the first two also have neutral names now.
   **URL、ページ、レスポンスヘッダー、エラーの文言に製品名と zg の名前を出さない**：サービス名はランダム。Cookie 名は `sid`。`Server` レスポンスヘッダーは送らない。プレースホルダーのページは「準備中です。」だけ。エラーはすべて汎用的な日本語の短文。オフラインの自己チェックで、ページ、レスポンスヘッダー、Cookie、WebSocket のエラーに製品の仮称も「zoujin」も含まれないことを項目ごとに確認済み。フロントエンドのテストページのタイトルと文言もこのルールに従う（フロントエンドに伝達済み）。イメージリポジトリ、サービスアカウント、ローカルのディレクトリは URL に出ず、前の 2 つも中立的な名前に変えた。
3. **A one-time test code**: see access protection below.
   **使い捨てのテストコード**：下のアクセス保護を参照。

**Access protection / アクセス保護:**

- **One-time test code** (12 characters, about 59 bits of randomness): generated on the Mac and written to `~/.zoujin-spike/s1b-code` (readable only by zg), not shown on screen; the service stores only a salted hash. Entered when the iPhone first opens the page, and exchanged for an `HttpOnly; Secure; SameSite=Lax` cookie (12 hours). 5 wrong attempts from the same address lock it for 10 minutes; 100 wrong attempts in total stop logins altogether.
  **使い捨てのテストコード**（12 文字、約 59 ビットのランダム性）：Mac 上で生成して `~/.zoujin-spike/s1b-code` に書き込み（zg だけが読める）、画面には表示しない。サービスにはソルト付きのハッシュだけを保存する。iPhone で初めて開いたときに入力し、`HttpOnly; Secure; SameSite=Lax` の Cookie（12 時間）に交換する。同じアドレスから 5 回間違えると 10 分ロック、全体で累計 100 回間違えるとログインを停止する。
- Without the cookie: every endpoint other than the page returns 401, and a WebSocket is closed with `4001` right after connecting (consistent with api-contract section 4), so nothing is received. Wrong `Origin`: both login and the WebSocket handshake are rejected (403).
  Cookie がない場合：ページ以外のエンドポイントはすべて 401、WebSocket は接続直後に `4001` で閉じる（api-contract 第 4 節と同じ）ので、何も受け取れない。`Origin` が正しくない場合：ログインも WebSocket のハンドシェイクも拒否する（403）。
- After opening, Cloud Run allows anonymous access (a phone browser cannot carry a Google identity), so protection relies on the two points above, the same approach as the real version's invite code + cookie.
  公開後は Cloud Run のレベルで匿名アクセスを許可する（スマホのブラウザは Google の ID を持てない）ので、保護は上の 2 点に頼る。本番版の招待コード + Cookie と同じやり方。
- **Usage caps**: when cumulative spend inside the service reaches 3 USD, voice is stopped (pushing `degraded`); each connection lasts at most 30 minutes; voice is stopped on the first quota error (429).
  **使用量の上限**：サービス内の累計費用が 3 米ドルに達したら音声を止める（`degraded` を送る）。1 接続は最長 30 分。最初のクォータエラー（429）で音声を止める。
- No voice or text is stored. Service logs record only timings, sizes and spend, not subtitle content (checked by the offline self-check). The address is written only to `~/.zoujin-spike/s1b-url`, and the script does not print it.
  音声もテキストも保存しない。サービスのログには時間、サイズ、費用だけを書き、字幕の内容は書かない（オフラインの自己チェックで確認済み）。アドレスは `~/.zoujin-spike/s1b-url` にだけ書き、スクリプトは表示しない。

**Release order (zg's rules) / 公開の順序（zg の規範）:**

When Cloud Run creates a new service, the first revision cannot be set to 0% traffic, so "0% traffic" is replaced by "private": the first deployment is a private service that only zg's Google identity can access, which is equivalent to not being open to the public. Script `s1b_deploy.sh`, each step run separately:

Cloud Run で新しいサービスを作るとき、最初のリビジョンはトラフィック 0% に設定できないので、「0% トラフィック」は「非公開」で代える：初回は zg の Google アカウントだけがアクセスできる非公開のサービスとしてデプロイし、一般に公開しないのと同じ効果を得る。スクリプトは `s1b_deploy.sh` で、各ステップを個別に実行する：

1. `prepare`: enable 4 APIs, create the image repository and the service account. `sacheck`: on the Mac, connect to Live once as the service account (no speech, no cost), trying every 20 seconds for up to 7 minutes; `up` is allowed only after it connects. `build`: build the image on the Mac, first run a check locally with the network cut off as the non-root user the service actually uses (it can read all code and the page, and `/health` and the page both return 200), and push only if it passes (docker login uses a 1-hour temporary token and logs out after pushing, without changing docker's permanent settings).
   `prepare`：4 つの API を有効にし、イメージリポジトリとサービスアカウントを作る。`sacheck`：Mac 上でサービスアカウントとして Live に 1 回接続する（話さず、費用なし）。20 秒ごとに試し、最大 7 分。接続できてはじめて `up` できる。`build`：Mac 上でイメージをビルドし、まずローカルでネットワークを切って、サービスが実際に使う非 root ユーザーとしてチェックを 1 回行い（すべてのコードとページを読め、`/health` もページも 200）、通った場合だけプッシュする（docker のログインには 1 時間の一時トークンを使い、プッシュ後にログアウトし、docker の恒久的な設定は変えない）。
2. `up`: deploy as a private service → confirm access without a Google identity is rejected → smoke-test with zg's identity: without the cookie REST returns 401 and WebSocket 4001, a wrong test code gives 401, login and WebSocket initiated from another site give 403, the correct test code logs in, and both lines get a voice reply.
   `up`：非公開のサービスとしてデプロイ → Google の ID を持たないアクセスが拒否されることを確認 → zg の ID でスモークテスト：Cookie がないとき REST は 401、WebSocket は 4001、間違ったテストコードは 401、ほかのサイトから始めたログインと WebSocket は 403、正しいテストコードでログインでき、2 つの発話のどちらにも音声で返答がある。
3. `open`: open public access → check once more that anonymous access is rejected.
   `open`：公開アクセスを開く → 匿名アクセスが拒否されることをもう一度確認する。
4. zg tests with the iPhone (section 5).
   zg が iPhone でテストする（第 5 節）。
5. `logs`: pull the timing fields back into `out/s1b/` (keeping only timestamps and timing fields, no project ID or address).
   `logs`：計測のフィールドを `out/s1b/` に取り込む（タイムスタンプと計測のフィールドだけを残し、プロジェクト ID とアドレスは含まない）。
6. `down`: **delete the same day** the service, image repository and service account, confirm the old address returns 404, and delete the local test code and address files. The 4 enabled APIs cost nothing and are kept.
   `down`：サービス、イメージリポジトリ、サービスアカウントを**当日中に削除**し、元のアドレスが 404 を返すことを確認し、ローカルのテストコードとアドレスのファイルを削除する。有効にした 4 つの API は費用がかからないので残す。

**How the address gets to the iPhone / アドレスを iPhone に渡す方法:** send it from the Mac to the iPhone with AirDrop or Universal Clipboard. The address and the test code are never pasted into chat or written into documents.

AirDrop か「ユニバーサルクリップボード」で Mac から iPhone に送る。アドレスとテストコードはチャットに貼らず、ドキュメントにも書かない。

**Cost (estimated) / 費用（推計）:** Live about 40〜60 turns, 0.5〜1 USD; Cloud Run and image storage together under 0.1 USD. Counted against the validation phase's 20 USD cap; the 3 USD cap inside the service is a second safeguard.

Live は約 40〜60 ターンで 0.5〜1 米ドル。Cloud Run とイメージの保存を合わせて 0.1 米ドル未満。検証段階の上限 20 米ドルに計上する。サービス内の 3 米ドルの上限は 2 段目の安全策。

**Time / 時間:** preparation and smoke testing on the Mac about 30 minutes (done by Claude on the Mac); zg's iPhone testing about 40 minutes.

Mac 上での準備とスモークテストに約 30 分（Mac 上の Claude が行う）、zg の iPhone でのテストに約 40 分。

## 5. What to test on the iPhone / 5. iPhone で何をテストするか

| # | What / 何を | How / やり方 | Pass criteria / 合格基準 | Who reviews the results / 結果を見る人 |
|---|---|---|---|---|
| 1 | Release to sound (4G) / 離してから音が出るまで（4G） | Wi-Fi off, Safari, say 20 lines to メロス (10 on the speaker, 10 with AirPods) / Wi-Fi をオフにし、Safari でメロスに 20 文話す（スピーカーで 10、AirPods で 10） | End-to-end median ≤ 1.8 s, p95 ≤ 3 s (S-017); frontend's three segments: capture to first upstream packet ≤ 60 ms, first downstream packet to sound ≤ 150 ms / エンドツーエンドの中央値 ≤ 1.8 s、p95 ≤ 3 s（S-017）。フロントエンドの 3 区間：収録から最初の上りパケットまで ≤ 60 ms、最初の下りパケットから音が出るまで ≤ 150 ms | Backend, frontend / バックエンド、フロントエンド |
| 2 | Barge-in / 割り込み | Press to talk while the character is speaking, 10 times / 登場人物が話している間に押して話す、10 回 | Barge-in to playback stop ≤ 200 ms (S-014) / 割り込みから再生停止まで ≤ 200 ms（S-014） | Frontend / フロントエンド |
| 3 | AirPods: microphone always on vs toggled per turn / AirPods：マイク常時オン vs ターンごとにオン・オフ | Switch between the two approaches with the toggle on the page, 5 turns each; record the first upstream packet's latency on switching and the subjective audio quality / ページ上のスイッチで 2 つのやり方を切り替え、それぞれ 5 ターン。切り替え時の最初の上りパケットの遅延と主観的な音質を記録する | Data for deciding F-3 / F-3 の方針を決めるためのデータ | Frontend, UX / フロントエンド、UX |
| 4 | Is there sound with the silent switch on / サイレントスイッチがオンでも音が出るか | Flip to silent and do 2 more turns / サイレントにしてさらに 2 ターン話す | Audible / 聞こえる | Frontend / フロントエンド |
| 5 | Quiet speech (bedtime volume) / 小声（寝る前の音量） | The page's "quiet mode": 5 lines on the phone microphone, 5 on the earphone microphone, fixed sentences in `zj_spike/data/s1b_lines.json` (taken from S-1a, with proper nouns) / ページの「小声モード」：スマホのマイクで 5 文、イヤホンのマイクで 5 文。固定の文は `zj_spike/data/s1b_lines.json`（S-1a から取った、固有名詞を含む文） | Record the character error rate and compare with S-1a at normal volume / 文字誤り率を記録し、S-1a の通常の音量と比較する | Backend, market research / バックエンド、市場調査 |
| 6 | LINE in-app browser / LINE のアプリ内ブラウザ | Open the same address inside LINE / LINE の中で同じアドレスを開く | Record: whether it can get the microphone; whether the handshake carries the cookie (receiving `welcome` with `cookieSeen: true` = yes; closed with `4001` after connecting = no) / 記録：マイクを取得できるか。ハンドシェイクに Cookie が付くか（`welcome` を受け取り、中身が `cookieSeen: true` = 付いた。接続後に `4001` で閉じられた = 付いていない） | Frontend / フロントエンド |
| 7 | Go to the background for 1 minute and come back / 1 分間バックグラウンドに切り替えて戻る | Switch to another app during the conversation / 会話中にほかのアプリに切り替える | One tap restores sound (S-024, the voice part of frontend S6) / 1 回のタップで音が戻る（S-024、フロントエンド S6 の音声部分） | Frontend / フロントエンド |
| 8 | Wi-Fi comparison / Wi-Fi との比較 | Turn Wi-Fi on and say 5 more lines / Wi-Fi をオンにしてさらに 5 文話す | Compare with item 1 / 第 1 項と比較する | Backend / バックエンド |

**When there are no AirPods** (10-07, zg used other earphones): replace every "AirPods" in the table with the earphones zg has at hand, write the actual model in place of "AirPods" in the results, and note whether they are Bluetooth or wired (only in the results record on the Mac, not in the test page or logs). Bluetooth earphones: items 1, 3 and 5 as originally planned; when iOS turns on the microphone, Bluetooth switches to call mode, the same mechanism as AirPods, so item 3's data is still useful for F-3, only with a different model and different latency. Wired earphones: there is no such switch, so item 3 can be skipped or run as usual as a comparison; items 1 and 5 as planned. Item 3 never had a pass line; only record data, and also note any dropouts or echo (frontend). If in item 1 the earphone group exceeds 1.8 seconds because of Bluetooth output latency while the speaker group passes, report the two groups separately and do not retest.

**AirPods がない場合**（10-07、zg は別のイヤホンを使った）：表の「AirPods」はすべて zg の手元のイヤホンに読み替え、結果では「AirPods」を実際の機種名に置き換え、Bluetooth か有線かを明記する（Mac 上の結果の記録にだけ書き、テストページやログには入れない）。Bluetooth のイヤホン：第 1、3、5 項は当初の計画どおり。iOS がマイクをオンにすると Bluetooth は通話モードに切り替わり、これは AirPods と同じ仕組みなので、第 3 項のデータは F-3 にとって引き続き有用。機種が違うので遅延には差が出る。有線のイヤホン：この切り替えがないので、第 3 項は飛ばすか、比較として通常どおり実行する。第 1、5 項は計画どおり。第 3 項にはもともと合格ラインがなく、データを記録するだけ。音切れやエコーがあればそれも記録する（フロントエンド）。第 1 項でイヤホンのグループが Bluetooth の出力遅延のために 1.8 秒を超え、スピーカーのグループは合格した場合、2 つのグループを分けて報告し、再テストはしない。

The test page (frontend, `frontend/spikes/s2-voice/`) does its own timing, shows the results on the page, and also writes them to the service logs via `POST /v1/telemetry` (accepting only numbers and fixed short English words, e.g. `{turnId, item:"t5", mode:"quiet-phone", clientReleaseToAudibleMs, cerPct}`); the server-side numbers for items 1, 2 and 8 are written to the logs too. After testing, `s1b_deploy.sh logs` pulls them all back in one go.

テストページ（フロントエンド、`frontend/spikes/s2-voice/`）は自分で計測し、結果をページに表示し、`POST /v1/telemetry` でサービスのログにも書く（数字と固定の英単語だけを受け付ける。例：`{turnId, item:"t5", mode:"quiet-phone", clientReleaseToAudibleMs, cerPct}`）。第 1、2、8 項のサーバー側の数字も同時にログに書く。テスト後に `s1b_deploy.sh logs` で一度に取り込む。

## 6. Option B (Mac tunnel), if chosen / 6. 選択肢 B（Mac のトンネル）を選んだ場合

Run the same proxy and test page on the Mac and give it a public HTTPS address through a temporary tunnel; the test code, cookie and usage caps are all the same. No new GCP APIs and no service account needed. Downsides: the numbers include the home upstream network and cannot be used for S-017 acceptance; the Mac must stay on without sleeping; the tunnel provider is also a third party. After testing, close the tunnel and the address stops working.

Mac 上で同じプロキシとテストページを動かし、一時的なトンネルで公開の HTTPS アドレスを与える。テストコード、Cookie、使用量の上限はすべて同じ。GCP の新しい API を有効にする必要も、サービスアカウントを作る必要もない。欠点：数値に自宅の上りネットワークが含まれ、S-017 の受け入れ確認に使えない。Mac をスリープさせずにずっと起動しておく必要がある。トンネルの提供元も第三者。テスト後にトンネルを閉じれば、そのアドレスは無効になる。

## 7. Who does what / 7. 誰が何をするか

| Who / 誰 | What / 何を | Status / 状態 |
|---|---|---|
| Backend / バックエンド | Voice proxy `zj_spike/s1b_proxy.py`, `s1b/Dockerfile`, deploy script `s1b_deploy.sh`, offline self-check `tests/test_s1b.py` / 音声プロキシ `zj_spike/s1b_proxy.py`、`s1b/Dockerfile`、デプロイスクリプト `s1b_deploy.sh`、オフラインの自己チェック `tests/test_s1b.py` | **Written**: 10 self-check items pass (a real local server + a fake Live: login, cookie, Origin, rate limiting, barge-in, spend cap, quota stop, no verbatim speech in logs); the deploy script ran the whole flow with a fake gcloud / **作成済み**：自己チェック 10 項目に合格（本物のローカルサーバー + 偽の Live：ログイン、Cookie、Origin、レート制限、割り込み、費用の上限、クォータでの停止、ログに発言そのものがない）。デプロイスクリプトは偽の gcloud で全体の流れを通した |
| Frontend / フロントエンド | S2 test page `frontend/spikes/s2-voice/` (wired to the protocol subset above, with timing, toggles, quiet mode and result display); automatically put into `page/` when packaging / S2 テストページ `frontend/spikes/s2-voice/`（上のプロトコルの一部につなぎ、計測、スイッチ、小声モード、結果表示を備える）。パッケージ化のときに自動で `page/` に入れる | Frontend agreed, being written / フロントエンドが同意し、作成中 |
| Claude on the Mac / Mac 上の Claude | Per `mac-s1b-run.md`: part 1 can be done any time; part 2 waits until zg says "start the 4G test" / `mac-s1b-run.md` に従う：第 1 段はいつでもできる。第 2 段は zg が「4G テスト開始」と言うのを待つ | — |
| PM | Record D-017; remind zg when it gets to the iPhone step / D-017 を記録する。iPhone のステップになったら zg に知らせる | Recorded / 記録済み |
| zg | Test part 2 with the iPhone; view the address and test code and send them to the iPhone themselves / 第 2 段を iPhone でテストする。アドレスとテストコードは自分で見て、自分で iPhone に送る | — |

zg's consent covers this one test only. When a retest is needed (e.g. after the proxy changes), ask again.

zg の同意は今回のテスト 1 回だけが対象。再テストが必要になったら（例：プロキシを変更した後）、もう一度聞く。

## Revision history / 改訂履歴

- v0.7 (2026-10-07): in the third deployment the smoke test stopped at "session ready": the service account in the cloud was refused when creating a Live session (Live closed the connection, and google-genai reported an APIError), and the original message was not recorded. The most likely cause is that the service account had only just been granted its role and the permission had not taken effect yet (the same package connected with zg's identity), but this cannot be confirmed. Changed so that: the proxy writes the upstream error's close code, status and original message into the service logs, removing project ID, project number, URLs and accounts before writing; what is sent to the phone gains only one fixed category word; when `up`'s smoke test fails, the script shows these log lines; a new `sacheck` connects to Live once on the Mac as the service account before deployment, and `up` is allowed only after it connects. For this, `prepare` enables one more API and gives zg the token creator role on the service account.
  v0.7（2026-10-07）：3 回目のデプロイでスモークテストが「セッション準備完了」で止まった：クラウド上のサービスアカウントが Live のセッションを作ろうとして拒否された（Live が接続を閉じ、google-genai が APIError を報告）が、元のメッセージは記録されていなかった。最も可能性が高い原因は、サービスアカウントに権限を付与した直後でまだ反映されていなかったこと（同じパッケージは zg の ID ではつながった）だが、確認はできない。次のように変更：プロキシは上流のエラーのクローズコード、ステータス、元のメッセージをサービスのログに書き、書く前にプロジェクト ID、プロジェクト番号、URL、アカウントを取り除く。スマホに送るものには固定の分類語が 1 つ増えるだけ。`up` のスモークテストが通らないときは、スクリプトがこれらのログの行を表示する。新たに `sacheck` を追加し、デプロイ前に Mac 上でサービスアカウントとして Live に 1 回接続し、つながった場合だけ `up` を許可する。このため `prepare` で API を 1 つ追加で有効にし、zg にサービスアカウント上のトークン作成者ロールを付与する。
- v0.6 (2026-10-07): in the second deployment the service was fine and really private (anonymous access to `/` gave 403), but `up` checked anonymous rejection on `/healthz`; Cloud Run reserves paths ending in z and returns 404 at its frontend, so the check could never pass, and the script stopped by the rules and ran down. Changed so that: the health check path is now `/health`; `up` checks that `/` gives 401/403, and `down` checks that `/` gives 404; the offline tests add one check: none of the proxy's routes or the paths the script probes end in z or start with `/_ah/`. We also went through the whole of up, open and down against Cloud Run frontend behavior and fixed three places that could misjudge: ① a new service, the public setting and deleting a service all take time to take effect at Google's frontend, so the URL checks in up, open and down now poll every 10 seconds (up waits up to 80 seconds for 401/403, and stops at once on 200, which means it is not private; open waits up to 3 minutes for an anonymous page load to give 200, then checks that nothing can be done without the test code; down waits up to 2 minutes for 404); ② a newly created service account's permission to call Gemini can take a few minutes to take effect, so if up's smoke test fails only on the voice items while all access-protection items pass, it waits 2 minutes and runs the whole set again, re-running only this once; ③ `http_code` outputs "000000" when it cannot connect, changed to "000".
  v0.6（2026-10-07）：2 回目のデプロイではサービスは正常で、確かに非公開だった（`/` への匿名アクセスは 403）が、`up` は匿名アクセスの拒否を `/healthz` で確認していた。Cloud Run は z で終わるパスを予約しており、フロントエンドで 404 を返すので、チェックは絶対に通らず、スクリプトはルールどおり止まって down した。次のように変更：ヘルスチェックのパスを `/health` にした。`up` は `/` が 401/403 であること、`down` は `/` が 404 であることを確認する。オフラインのテストに 1 項目追加：プロキシのルートとスクリプトが確認するパスは、どれも z で終わらず、`/_ah/` で始まらない。さらに up、open、down 全体を Cloud Run のフロントエンドの挙動と照らし合わせ、誤判定しうる 3 か所を直した：① 新しいサービス、公開設定、サービスの削除はいずれも Google のフロントエンドで反映されるまで時間がかかるので、up、open、down の URL チェックはすべて 10 秒ごとに問い合わせるようにした（up は最大 80 秒、401/403 になるまで待つ。200 が出たらすぐ止める、非公開でないことを意味するため。open は最大 3 分、匿名でページを開いて 200 になるまで待ち、その後テストコードなしでは何もできないことを確認する。down は最大 2 分、404 になるまで待つ）。② 新しく作ったサービスアカウントが Gemini を呼ぶ権限は反映まで数分かかることがあるので、up のスモークテストで音声の項目だけが通らずアクセス保護がすべて通った場合、2 分待って全体をもう一度実行する。再実行はこの 1 回だけ。③ 接続できないとき `http_code` が「000000」を出力するので、「000」に変えた。
- v0.5 (2026-10-07): the 10-07 deployment failed at `up`: the script's `umask 077` made the files in the build directory 600/700, so the image, running as a non-root user, could not read the code. Fix: `chmod -R a+rX` after copying the build directory; before pushing, `build` runs `selfcheck` locally with the network cut off as the service user; the offline tests add these two items.
  v0.5（2026-10-07）：10-07 のデプロイは `up` で失敗した：スクリプトの `umask 077` によってビルドディレクトリ内のファイルが 600/700 になり、非 root ユーザーで動くイメージがコードを読めなかった。修正：ビルドディレクトリをコピーした後に `chmod -R a+rX`。`build` はプッシュの前にローカルでネットワークを切ってサービスユーザーとして `selfcheck` を実行する。オフラインのテストにこの 2 項目を追加した。
- v0.4 (2026-10-07): zg has no AirPods, so section 5 adds what to do "when there are no AirPods" (Bluetooth as originally planned, wired skips item 3).
  v0.4（2026-10-07）：zg は AirPods を持っていないので、第 5 節に「AirPods がない場合」のやり方を追加（Bluetooth は当初の計画どおり、有線は第 3 項を飛ばす）。
- v0.3 (2026-10-06): changes per D-017 (zg chose A): random service name, no traffic tags; neutral names for the image repository and service account; no product name in the cookie name, placeholder page or response headers; per frontend's feedback, section 5 adds the two groups of sentences for quiet mode, the AirPods toggle, `cookieSeen`, and the pass lines for frontend's three segments; run instructions in `mac-s1b-run.md`.
  v0.3（2026-10-06）：D-017（zg が A を選択）に従って変更：サービス名をランダムにし、トラフィックタグを使わない。イメージリポジトリとサービスアカウントを中立的な名前に変更。Cookie 名、プレースホルダーのページ、レスポンスヘッダーに製品名を出さない。フロントエンドの意見に従い、第 5 節に小声モードの 2 組の文、AirPods のスイッチ、`cookieSeen`、フロントエンドの 3 区間の合格ラインを追加。実行手順は `mac-s1b-run.md`。
- v0.2 (2026-10-06): code written; "0% traffic" changed to "private first" (a new Cloud Run service cannot have 0% traffic); WebSocket without a cookie changed to close with 4001 after connecting; usage cap changed to 3 USD of spend.
  v0.2（2026-10-06）：コードを作成。「0% トラフィック」を「まず非公開」に変更（Cloud Run の新しいサービスは 0% トラフィックにできない）。Cookie のない WebSocket は接続後に 4001 で閉じるように変更。使用量の上限を費用 3 米ドルに変更。
- v0.1 (2026-10-06): first draft.
  v0.1（2026-10-06）：初稿。
