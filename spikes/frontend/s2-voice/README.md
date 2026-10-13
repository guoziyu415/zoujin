# S2 Voice Test Page (the frontend half of the S-1b phone test) / S2 音声テストページ（S-1b 実機テストのフロントエンド側）

For the backend's S-1b plan see `backend/spikes/s1b-plan.md`. This page is served by the backend's s1b proxy at the same address; zg opens it on an iPhone (Wi-Fi off) and talks to メロス through 8 test items, and the page times and reports by itself.

バックエンドの S-1b 計画は `backend/spikes/s1b-plan.md` を参照。このページはバックエンドの s1b プロキシが同じアドレスで配信し、zg が iPhone（Wi-Fi オフ）で開いて 8 つのテスト項目でメロスと話す。ページが自分で時間を記録して送信する。

## Directories / ディレクトリ

| Directory / ディレクトリ | Contents / 内容 | In the image? / イメージに含めるか |
|---|---|---|
| `page/` | `index.html`, `app.js`, `capture-worklet.js`, `play-worklet.js` / 同左 | **Yes / 含める**: `ZJ_S1B_STATIC` / `ZJ_S1B_PAGE` point to this directory / `ZJ_S1B_STATIC` / `ZJ_S1B_PAGE` がこのディレクトリを指す |
| `test/` | `fake_serve.py` (the backend's real proxy + a fake Live model), `e2e.mjs` (one run with Chromium's fake microphone) / `fake_serve.py`（バックエンドの実プロキシ + 偽の Live モデル）、`e2e.mjs`（Chromium の偽マイクで 1 回通して実行） | No / 含めない |

The files in `page/` are sent to the phone as is, so per D-017 they stay neutral: title 「音声テスト」, and no product name or zg's name in the page text, file names or comments, only メロス. After changing `page/`, check with the command below:

`page/` のファイルはそのまま携帯に送られるため、D-017 に従って中立に保つ：タイトルは「音声テスト」で、ページの文言、ファイル名、コメントに製品名や zg の名前は入れず、メロスだけを使う。`page/` を変更したら、下のコマンドで確認する：

```
grep -n -i "zoujin\|monogatari\|物語\|zj\|zg\|backend\|api-contract" page/*
```

## What the page does / ページの動作

- Login: `GET /v1/me`; if not logged in, show an input box and `POST /v1/auth/login {inviteCode}`. The test code exists only on zg's Mac and goes in neither chat nor documents.
  ログイン：`GET /v1/me`。未ログインなら入力欄を表示し、`POST /v1/auth/login {inviteCode}` を送る。テストコードは zg の Mac にしかなく、チャットにもドキュメントにも載せない。
- Connection: WebSocket `/v1/playthroughs/s1b/live`, `hello` → `near` + `focus` → `session_ready`, and a `ping` every 20 seconds.
  接続：WebSocket `/v1/playthroughs/s1b/live`、`hello` → `near` + `focus` → `session_ready`。20 秒ごとに `ping`。
- Speaking: hold the talk button for `activity_start`, uplink 16 kHz PCM16 in 20 ms frames (`0x01` + 4-byte turnSeq); release for `activity_end`. Downlink 24 kHz (`0x02`) goes into the AudioWorklet's ring buffer (40 ms pre-buffer).
  発話：話すボタンを押している間 `activity_start`、上りは 16 kHz PCM16 を 20 ms 1 フレーム（`0x01` + 4 バイトの turnSeq）。離すと `activity_end`。下りの 24 kHz（`0x02`）は AudioWorklet のリングバッファに入れる（プリバッファ 40 ms）。
- Barge-in: pressing while a reply is still playing **clears playback locally first** and then tells the server; audio from an old turn is dropped by turnSeq.
  割り込み：返答の再生中に押すと、**まずローカルで再生をクリアして**からサーバーに伝える。古いターンの音声は turnSeq で破棄する。
- Two ways to handle the microphone (item 3): "always on during the conversation" or "on/off per turn"; when opening the mic `navigator.audioSession.type = 'play-and-record'`, and when closing it set back to `playback` (iOS 17+ supports this; browsers that do not are recorded as "unsupported").
  マイクの扱い方 2 通り（項目 3）：「会話中は常時オン」または「ターンごとにオン/オフ」。マイクを開くとき `navigator.audioSession.type = 'play-and-record'`、閉じるとき `playback` に戻す（iOS 17+ 対応。非対応のブラウザは「非対応」と記録する）。
- Item 5 shows the sentences to read quietly: two groups of 5 each from the backend's `zj_spike/data/s1b_lines.json`; when "audio output" is set to speaker use the phone-microphone group, and when set to earphones use the earphone group; the character error rate is computed from the recognized text returned by the server, removing the same characters as the backend's `cerIgnore`.
  項目 5 は小声で読む文を表示する：バックエンドの `zj_spike/data/s1b_lines.json` にある 5 文ずつの 2 グループ。「音の出力」でスピーカーを選んだときは携帯マイクのグループ、イヤホンを選んだときはイヤホンのグループを使う。サーバーが返す認識テキストで文字誤り率を計算し、除去する文字はバックエンドの `cerIgnore` と同じ。
- Item 7: when going to the background and coming back, check audio, microphone and connection, and show 「タップで音を戻す」 when needed.
  項目 7：バックグラウンドに切り替えて戻ったとき、音声、マイク、接続を確認し、必要なら「タップで音を戻す」を表示する。

Each turn records (milliseconds):

各ターンで記録するもの（ミリ秒）：

| Field / フィールド | Meaning / 意味 |
|---|---|
| `clientReleaseToAudibleMs` | **From release to hearing the first sound** (converted with `getOutputTimestamp` to the moment sound is actually produced): the main S-1b metric / **離してから最初の音が聞こえるまで**（`getOutputTimestamp` で実際に音が出る時刻に換算）：S-1b の主指標 |
| `serverReleaseToFirstAudioMs` | Server side: from receiving the release to the model's first audio / サーバー側：離す操作を受け取ってからモデルの最初の音声まで |
| `netMs` | From page release to receiving the first downlink frame, minus the server part; roughly one network round trip / ページが離す操作をしてから最初の下りフレームを受け取るまで、サーバー側の分を引いたもの。ネットワーク 1 往復にほぼ等しい |
| `pressToFirstUpMs`, `firstDownToAudibleMs` | Press to the first uplink frame; first downlink frame to sound / 押してから最初の上りフレームまで、最初の下りフレームから音が出るまで |
| `pressToSilenceMs`, `pressToInterruptedMs` | On barge-in: press to local silence; press to the server confirming the interruption / 割り込み時：押してからローカルで無音になるまで、押してからサーバーが割り込みを確認するまで |
| `underrunCount` | Number of times sound broke up in the middle of a reply / 返答の途中で音が途切れた回数 |
| `micOpenMs`, `connectToReadyMs` | Time to open the mic; tapping "start" to being able to speak / マイクを開くのにかかった時間、「開始」を押してから話せるようになるまで |
| `cerPct` | Character error rate for item 5 / 項目 5 の文字誤り率 |
| `bargeInCount` | 1 = this turn's answer was interrupted by the player pressing to speak (recorded at the moment of pressing, without waiting for playback to end) / 1 = このターンの返答がプレイヤーの押下による発話で割り込まれた（押した時点で記録し、再生の終了を待たない） |
| `extMicCount` | 1 = the microphone in use is not the phone's own (Bluetooth or wired headset), judged automatically from the microphone name, and the name itself is not recorded (it may contain a person's name); 0 = phone microphone / 1 = 使用中のマイクが携帯自体のものではない（Bluetooth または有線のヘッドセット）。マイク名から自動判定し、名前自体は記録しない（人名を含む可能性がある）。0 = 携帯のマイク |

Results are stored in the phone's localStorage (only numbers and test items, **no spoken text**) and also sent via `POST /v1/telemetry` (the proxy keeps only `*Ms`/`*Count`/`*Pct`, turnId/turnSeq and a few short enums). "Copy all results" exports JSON.

結果は携帯の localStorage に保存する（数値とテスト項目だけで、**話した内容のテキストは保存しない**）。同時に `POST /v1/telemetry` で送信する（プロキシは `*Ms`/`*Count`/`*Pct`、turnId/turnSeq と少数の短い列挙値だけを残す）。「全結果をコピー」で JSON を書き出せる。

## Tested in the container (2026-10-06) / コンテナ内でのテスト（2026-10-06）

Using the backend's real `s1b_proxy.py`, with only the Live model replaced by a fake (`test/fake_serve.py`) and Chromium's fake microphone:

バックエンドの実際の `s1b_proxy.py` を使い、Live モデルだけを偽物（`test/fake_serve.py`）に置き換え、Chromium の偽マイクで実施：

- Wrong code → 「コードが違います」; correct code → enters; a WebSocket without login is closed with 4001.
  誤ったコード →「コードが違います」。正しいコード → 入れる。未ログインの WebSocket は 4001 で閉じられる。
- The handshake carried the Cookie; from tapping start to being able to speak took 320–400 ms (the fake model takes 300 ms to open a session).
  ハンドシェイクに Cookie が付いた。開始を押してから話せるようになるまで 320〜400 ms（偽モデルのセッション開始が 300 ms）。
- 3 voice turns, 3 quiet-sentence turns, 1 barge-in and 1 text turn were all recorded; local silence took 34–40 ms.
  音声 3 ターン、小声の文 3 ターン、割り込み 1 回、テキスト 1 ターンがすべて記録された。ローカルでの無音化は 34〜40 ms。
- When the recognized text arrives after `turn_complete`, the character error rate is computed once the text arrives; in the transcript your words are placed before メロス's answer.
  認識テキストが `turn_complete` より遅れて届いたときは、テキストが届いてから文字誤り率を計算する。会話記録ではあなたの発言がメロスの返答より前に並ぶ。
- When the downlink was slowed to slower than real time (24 segments), `underrunCount` = 23.
  下りをリアルタイムより遅くしたとき（24 セグメント）、`underrunCount` = 23。
- Reporting: all 13 events reached the proxy log, with the fields filtered.
  送信：13 件のイベントがすべてプロキシのログに入り、フィールドはフィルタ済み。

**Changes on 2026-10-07** (gaps the backend found after the S-1b 4G test): when the player pressed to speak after the server had finished but the phone was still playing, the previous turn produced no record or only after the 30-second timeout (turns 11, 19 and 26 in the test). The cause was that the record waits for playback to end, while pressing clears playback, so that turn never reached an end. Now the interrupted turn is recorded at the moment of pressing (`bargeInCount: 1`), and if the server has not finished it waits up to 5 seconds for its `turn_complete`; `turn_complete` finds the turn by `turnId`, not only the current one. Also added `extMicCount`, because in the test the "audio output" selection was never changed, so Bluetooth earphones and speaker could not be told apart. Rerunning e2e in the container: both kinds of barge-in (server not finished / finished but still playing) produce a record for the interrupted turn, all 11 rows arrive, and there are no timeouts.

**2026-10-07 の修正**（S-1b の 4G 実機テスト後にバックエンドが見つけた不備）：サーバーが話し終えたのに携帯がまだ再生している最中に押して話すと、前のターンの記録が出ない、または 30 秒のタイムアウト後にだけ出た（テストの第 11、19、26 ターン）。原因は記録が再生の終了を待つのに、押したときに再生をクリアするため、そのターンは終了に到達しなかったこと。今は押した時点で割り込まれたターンを記録し（`bargeInCount: 1`）、サーバーがまだ話し終えていなければ、その `turn_complete` を最長 5 秒待つ。`turn_complete` は現在のターンだけでなく `turnId` でターンを探す。さらに `extMicCount` を追加した。テストでは「音の出力」の選択がずっと切り替えられず、Bluetooth イヤホンとスピーカーを区別できなかったため。コンテナで e2e を再実行：2 種類の割り込み（サーバーが話し終えていない / 話し終えたが再生中）のどちらも割り込まれたターンの記録があり、11 行すべてが届き、タイムアウトはなかった。

The same day per S-073 item 2: the three items "audio output / network / microphone" have no defaults, and the talk button can be pressed only after all three are chosen; the talk button shows the current conditions (e.g. 「押して話す（スピーカー・4G・会話中常時オン）」); changing the microphone to always-on or per-turn during a connection immediately opens or closes the microphone; when the automatically judged microphone source disagrees with "audio output", a hint appears under the settings. When switching test items, the three are cleared and must be chosen again (iPhone Safari cannot obtain the network type, so "network" can only be chosen by hand; the backend's suggestion). "AirPods" became "Bluetooth earphones" (value `bluetooth`). The "other" column of the results table marks "this turn was interrupted" and "headset microphone". e2e also covers: pressing without conditions chosen does not start a turn, and the hint appearing and disappearing.

同日、S-073 ②に従って：「音の出力 / ネットワーク / マイク」の 3 項目にはデフォルトがなく、3 つすべて選んで初めて話すボタンを押せる。話すボタンには現在の条件を表示する（例「押して話す（スピーカー・4G・会話中常時オン）」）。接続中にマイクを常時オンまたはターンごとに切り替えると、すぐにマイクを開閉する。自動判定したマイクの種類が「音の出力」と一致しないときは、設定の下にヒントを出す。テスト項目を切り替えると 3 項目はクリアされ、選び直す必要がある（iPhone Safari はネットワークの種類を取得できないため「ネットワーク」は手動選択のみ。バックエンドの提案）。「AirPods」は「Bluetooth イヤホン」に変更（値は `bluetooth`）。結果表の「その他」欄に「このターンは割り込まれた」「イヤホンのマイク」を表示する。e2e では、条件を選ばずに押してもターンが始まらないこと、ヒントの表示と消去もカバーした。

- No errors in the console (only the 401 from `/v1/me` when not logged in, which is normal).
  コンソールにエラーなし（未ログイン時の `/v1/me` の 401 のみ。正常）。

**Not tested**: real iPhone Safari (audioSession, AirPods, the silent switch, the LINE in-app browser, background recovery) and the real Live model. These can only be covered by zg's hands-on test.

**未テスト**：実機の iPhone Safari（audioSession、AirPods、サイレントスイッチ、LINE アプリ内ブラウザ、バックグラウンドからの復帰）と実際の Live モデル。これらは zg の実機テストでしか確認できない。

## Rerunning in the container or on a Mac / コンテナまたは Mac での再実行

```
pip install google-genai fastapi "uvicorn[standard]"          # same versions as backend/spikes/pyproject.toml / バージョンは backend/spikes/pyproject.toml と同じ
cd test && PYTHONDONTWRITEBYTECODE=1 python fake_serve.py 8091  # test code TEST-TEST-TEST, local machine only / テストコード TEST-TEST-TEST、このマシンのみ
node e2e.mjs http://127.0.0.1:8091/                             # needs playwright / playwright が必要
FAKE_PACE=0.13 python fake_serve.py 8091                        # downlink slower than real time, to see the underrun count / 下りをリアルタイムより遅くして、途切れ回数を確認する
```
