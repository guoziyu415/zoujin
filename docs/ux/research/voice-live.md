# Research: Gemini Live voice, audio limits in iPhone Safari, precedents for voice-first games / 調査：Gemini Live の音声、iPhone Safari の音声の制約、音声ファーストのゲームの先例

Compiled by the UX thread on 2026-10-06 (searched by the research assistant, reviewed by UX). Every fact carries a source number, with URLs at the end; "inference" marks a guess, not something the source says. Backend and frontend can cite this directly; where it agrees with the conclusions of backend-design.md section 3.2, the argument is not repeated.

UX スレッドが 2026-10-06 に整理（調査アシスタントが検索し、UX が査読）。すべての事実に出典番号を付け、URL は末尾にまとめた。「推測」は推測であり、出典の記述ではない。バックエンドとフロントエンドはそのまま引用してよい。backend-design.md 3.2 節の結論と一致する部分は論証を繰り返していない。


All sources were checked on 2026-10-06. Each fact is followed by a source number; URLs and publication/update dates are listed together at the end. Content marked "inference" is not in the sources; I inferred it.

すべての出典の確認日は 2026-10-06。各事実の後ろに出典番号を付け、URL と公開日・更新日は末尾にまとめて載せた。「推測」と記した内容は出典には書かれておらず、私が推論したもの。

---

## 1. Gemini Live API (status as of October 2026) / Gemini Live API（2026 年 10 月時点）

### 1.1 Current models / 現行のモデル
| Model ID / モデル ID | Status / 状態 | Key points / 要点 |
|---|---|---|
| `gemini-3.8-live` | Stable, released 2026-09-15 / Stable、2026-09-15 リリース | Officially positioned as "the default choice for most low-latency voice agents"; `thinkingLevel` is not configurable; asynchronous function calls default to `NON_BLOCKING`; input limit 131,072 tokens / 公式の位置づけは「ほとんどの低遅延音声エージェントのデフォルトの選択」。`thinkingLevel` は設定不可。非同期の関数呼び出しはデフォルトで `NON_BLOCKING`。入力上限は 131,072 トークン [G1][G2][G9] |
| `gemini-3.8-live-extended-thinking` | Marked Stable on the Gemini API, while the Cloud blog says private preview on Enterprise (the two disagree) / Gemini API では Stable、Cloud ブログでは Enterprise の private preview（2 か所の記述が食い違う） | Stronger reasoning; thinking can be set to low/medium/high; it speaks while reasoning and first says verbal cues like "Let me check that…" / 推論が強い。thinking は low/medium/high に設定できる。推論しながら話し、まず "Let me check that…" のような口頭の合図を言う [G2][G3][G14][G15] |
| `gemini-3.1-flash-live-preview` | Legacy preview | No support for affective dialog, proactive audio or asynchronous function calls / affective dialog、proactive audio、非同期の関数呼び出しに非対応 [G2][G3][G7] |
| `gemini-2.5-flash-native-audio-preview-12-2025` | Existing users only / 既存ユーザーのみ | Old model / 旧モデル [G2] |

**Two key changes in 3.8 Live** (from the official model card) [G1]:
- 「Affective dialogue is removed from the API」: the affective adaptation switch has been removed.
- 「Proactive audio is now permanently enabled. Setting `proactive_audio: false` returns an error」: the model may not respond when it judges an utterance has nothing to do with it, and this behavior can't be turned off [G4].
- Also, `turn_complete=true` unconditionally interrupts the reply being generated. So when text input is sent, whatever the NPC is saying gets cut off.

**3.8 Live の 2 つの重要な変化**（公式の model card より）[G1]：
- 「Affective dialogue is removed from the API」：感情に合わせて応答を変えるスイッチは削除された。
- 「Proactive audio is now permanently enabled. Setting `proactive_audio: false` returns an error」：モデルはある発話が自分と無関係だと判断すると応答しないことがあり、この動作はオフにできない [G4]。
- また、`turn_complete=true` は生成中の応答を無条件に中断する。そのため文字入力を送った瞬間、NPC が話している途中の言葉は切られる。

**On the Vertex AI side**: the Google Cloud docs URLs have moved to "Gemini Enterprise Agent Platform", and the navigation lists Gemini 3.8 Live [G16]. The Cloud blog (2026-09-24) announced Gemini 3.8 Live with Live Avatar GA, with US/EU endpoints and support for 97 languages [G15]. I couldn't fetch the body of the Vertex pages, so **the model ID, region and voice list need to be confirmed by hand in the console**. Also, developer forum posts from May to August 2026 say 3.1 Flash Live never came to Vertex [G17].

**Vertex AI 側**：Google Cloud のドキュメントの URL は「Gemini Enterprise Agent Platform」に移り、ナビゲーションに Gemini 3.8 Live が載っている [G16]。Cloud ブログ（2026-09-24）は Gemini 3.8 Live with Live Avatar の GA を発表し、US/EU のエンドポイントと 97 言語に対応するとした [G15]。Vertex のページ本文は取得できなかったので、**モデル ID、リージョン、音声の一覧はコンソールで人の手で確認する必要がある**。また、2026 年 5 月〜8 月の開発者フォーラムの投稿によれば、3.1 Flash Live は Vertex に来なかった [G17]。

### 1.2 Japanese and voices / 日本語と声
- **Language**: the live-guide lists 99 languages, including `ja` [G3] (the Cloud blog says 97 [G15]). Native audio models 「automatically choose the appropriate language and don't support explicitly setting the language code」[G3]. The official advice is to write 「RESPOND IN {LANG}. YOU MUST RESPOND UNMISTAKABLY IN {LANG}.」 in the system instruction [G5][G10].
  **言語**：live-guide には `ja` を含む 99 言語が載っている [G3]（Cloud ブログでは 97 言語 [G15]）。native audio のモデルは「automatically choose the appropriate language and don't support explicitly setting the language code」[G3]。公式には system instruction に「RESPOND IN {LANG}. YOU MUST RESPOND UNMISTAKABLY IN {LANG}.」と書くよう勧めている [G5][G10]。
- **Prebuilt voices**: the Live API 「supports any of the voices available for our TTS models」[G3], 30 in total, Puck by default [G10][G11]. The genders and characteristics in the table below come from the Firebase docs:
  **プリセットの声**：Live API は「supports any of the voices available for our TTS models」[G3]。全部で 30 種類、デフォルトは Puck [G10][G11]。下の表の性別と特徴は Firebase のドキュメントによる：

| Male voices / 男性の声 | Female voices / 女性の声 |
|---|---|
| Achird(Friendly) Algenib(Gravelly) Algieba(Smooth) Alnilam(Firm) Charon(Informative) Enceladus(Breathy) Fenrir(Excitable) Iapetus(Clear) Orus(Firm) Puck(Upbeat) Rasalgethi(Informative) Sadachbia(Lively) Sadaltager(Knowledgeable) Schedar(Even) Umbriel(Easy-going) Zubenelgenubi(Casual) | Achernar(Soft) Aoede(Breezy) Autonoe(Bright) Callirrhoe(Easy-going) Despina(Smooth) Erinome(Clear) Gacrux(Mature) Kore(Firm) Laomedeia(Upbeat) Leda(Youthful) Pulcherrima(Forward) Sulafat(Warm) Vindemiatrix(Gentle) Zephyr(Bright) |

- **A different voice per character**: the voice goes in `speechConfig.voiceConfig.prebuiltVoiceConfig.voiceName` [G3]. The setup message is 「to be sent in the first (and only in the first)」 client message [G6], so **one session can only use one voice, and switching characters means opening a new session** (inference). Known pitfall: with an ephemeral token, putting speechConfig into the token has no effect. A Google employee replied on 2026-09-14 that it has to go in the client's setup message [G18]. Since you go through a Cloud Run proxy, writing the setup on the server is enough.
  **登場人物ごとに声を変える**：声は `speechConfig.voiceConfig.prebuiltVoiceConfig.voiceName` に書く [G3]。setup メッセージは「to be sent in the first (and only in the first)」client message [G6] なので、**1 つのセッションでは 1 つの声しか使えず、人物を替えるには新しいセッションを開く必要がある**（推測）。既知の落とし穴：ephemeral token を使う場合、speechConfig を token に書いても効かない。Google の社員が 2026-09-14 に、client の setup メッセージに入れる必要があると回答している [G18]。皆さんは Cloud Run のプロキシを通すので、サーバー側で setup を書けばよい。
- **Tone, age, accent**: the official docs only describe how to write a persona in the best practices, plus 「when specifying an accent, also specify the output language」[G5]. TTS models have a `style` field and inline tags to control style [G11]; the Live API has no equivalent field, so it can only be done via the system instruction (inference). There is no official evaluation of how natural each of the 30 voices sounds in Japanese, so **each one must be auditioned in AI Studio**.
  **口調、年齢、なまり**：公式は best practices で persona の書き方と「なまりを指定するときは出力言語も指定する」ことを書いているだけ [G5]。TTS モデルには `style` フィールドと行内タグがあり、スタイルを制御できる [G11]。Live API には対応するフィールドがないため、system instruction に頼るしかない（推測）。30 種類の声それぞれの日本語の自然さについて公式の評価は公開されておらず、**AI Studio で 1 つずつ試聴する必要がある**。

### 1.3 Turn detection and interruption (barge-in) / ターン検出と割り込み（barge-in）
- **Automatic VAD (default)**: under `automaticActivityDetection` you can set `startOfSpeechSensitivity` (HIGH/LOW), `endOfSpeechSensitivity` (HIGH/LOW), `prefixPaddingMs` and `silenceDurationMs`. The official advice is a silenceDurationMs of 500–800ms; shorter values 「often cause fragmented audio」[G3][G6].
  **自動 VAD（デフォルト）**：`automaticActivityDetection` の下で `startOfSpeechSensitivity`（HIGH/LOW）、`endOfSpeechSensitivity`（HIGH/LOW）、`prefixPaddingMs`、`silenceDurationMs` を設定できる。公式は silenceDurationMs を 500–800ms にするよう勧めており、それより短いと「often cause fragmented audio」[G3][G6]。
- **Manual mode (suits push-to-talk)**: after setting `disabled: true`, the client sends `activityStart` / `activityEnd` [G3].
  **手動方式（プッシュトゥトークに向く）**：`disabled: true` にすると、クライアントが `activityStart` / `activityEnd` を送る [G3]。
- **Interruption behavior**: `activityHandling` defaults to `START_OF_ACTIVITY_INTERRUPTS`, so the model is interrupted as soon as the user starts speaking; it can also be set to `NO_INTERRUPTION` [G6]. On interruption the server returns `serverContent.interrupted: true`; generated content not yet sent is discarded, and the part already sent stays in the history [G3]. The official docs require that the client 「must immediately discard your client-side audio buffer」[G5].
  **割り込みの動作**：`activityHandling` のデフォルトは `START_OF_ACTIVITY_INTERRUPTS` で、ユーザーが話し始めるとすぐモデルを中断する。`NO_INTERRUPTION` にもできる [G6]。中断されるとサーバーは `serverContent.interrupted: true` を返し、まだ送っていない生成内容は破棄され、送信済みの部分は履歴に残る [G3]。公式はクライアントに「must immediately discard your client-side audio buffer」ことを求めている [G5]。
- The default of `turnCoverage` for 3.1 and later is `TURN_INCLUDES_AUDIO_ACTIVITY_AND_ALL_VIDEO` [G6].
  3.1 以降の `turnCoverage` のデフォルト値は `TURN_INCLUDES_AUDIO_ACTIVITY_AND_ALL_VIDEO` [G6]。
- VAD and latency are both improved in 3.8 Live (a customer, Specs, quoted in the Cloud blog) [G15].
  3.8 Live では VAD と遅延がどちらも改善された（Cloud ブログにある顧客 Specs の引用）[G15]。

### 1.4 Transcription / 文字起こし
- How to turn it on: add `inputAudioTranscription` / `outputAudioTranscription` to the setup. The language of the output transcription is 「inferred from the model's response」[G3].
  有効にする方法：setup に `inputAudioTranscription` / `outputAudioTranscription` を加える。出力の文字起こしの言語は「inferred from the model's response」[G3]。
- Transcriptions arrive incrementally with the server content (「Incremental server update」), but are 「sent independently of the other server messages and there is no guaranteed ordering」[G6]. In other words, aligning subtitles with audio has to be done by the client (inference).
  文字起こしは server content とともに差分で届く（「Incremental server update」）が、「sent independently of the other server messages and there is no guaranteed ordering」[G6]。つまり字幕と音声の同期はクライアントが自分で行う必要がある（推測）。
- The API reference adds several new fields to `AudioTranscriptionConfig` [G6]:
  API reference では `AudioTranscriptionConfig` にいくつかのフィールドが追加された [G6]：
  - `languageCodes` (BCP-47 hints)
    `languageCodes`（BCP-47 のヒント）
  - `customVocabulary` (can hold proper nouns like メロス／ディオニス／セリヌンティウス／シラクス)
    `customVocabulary`（メロス／ディオニス／セリヌンティウス／シラクスのような固有名詞を入れられる）
  - `wordTimestamp`, `diarization`
    `wordTimestamp`、`diarization`
  - `mode`: `VERBATIM` or `SMART` (SMART removes filler words)
    `mode`：`VERBATIM` または `SMART`（SMART は口癖やつなぎ言葉を取り除く）

  Whether all of these fields take effect on 3.8 Live needs to be tested.

  これらのフィールドが 3.8 Live ですべて有効かどうかは、実際に試す必要がある。
- Known issues: / 既知の問題：
  - The input transcription can differ from what the model actually understood (e.g. "wifi doesn't work" transcribed as "wife isn't well"). The forum has reports from 2026-03 to 09, covering 2.5, 3.1 and 3.8. The community's conclusion: **use transcriptions only for display, never to drive logic** [G19].
    入力の文字起こしは、モデルが実際に理解した内容と異なることがある（たとえば "wifi doesn't work" と言ったのに "wife isn't well" と文字起こしされる）。フォーラムには 2026-03 から 09 まで報告があり、2.5、3.1、3.8 に及ぶ。コミュニティの結論は、**文字起こしは表示にだけ使い、ロジックの駆動には使わない** [G19]。
  - On 2.5, when someone talks continuously for more than 20–40 seconds, transcriptions are delayed or lost [G20].
    2.5 では、20–40 秒以上続けて話すと文字起こしが遅れたり欠けたりする [G20]。

### 1.5 Latency (no official milliseconds) / 遅延（公式のミリ秒値はない）
Google's launch materials only say "ultra-low latency" and give no figure in milliseconds [G1][G13][G14]. The only numbers available are third-party reports:

Google の発表資料は "ultra-low latency" と言うだけで、ミリ秒の数値は示していない [G1][G13][G14]。見つかる数字はすべて第三者の報告：
- 3.1 Flash Live with the Google Search tool on: 3–3.5 seconds total latency; with it off, about 100ms to the first chunk and 1–1.5 seconds total (LiveKit community, 2026-04-03) [G21].
  3.1 Flash Live で Google Search ツールをオンにすると全体の遅延は 3–3.5 秒。オフにすると最初のチャンクまで約 100ms、全体で 1–1.5 秒（LiveKit コミュニティ、2026-04-03）[G21]。
- 2.5 native audio: 5–6 seconds end to end (forum, 2026-02 to 03) [G22].
  2.5 native audio はエンドツーエンドで 5–6 秒（フォーラム、2026-02〜03）[G22]。
- Official streaming advice: send audio in 20–40ms chunks, don't buffer 1 second; resample microphone capture to 16kHz; output is 24kHz [G5][G8].
  公式のストリーミングの推奨：音声は 20–40ms ごとに送り、1 秒分バッファしない。マイクの入力は 16kHz にリサンプリングする。出力は 24kHz [G5][G8]。

**Conclusion: first-chunk latency must be measured on an iPhone.**

**結論：最初のチャンクまでの遅延は iPhone の実機で測る必要がある。**

### 1.6 Session length, billing, safety, tools / セッションの長さ、課金、安全性、ツール
| Item / 項目 | Value / 値 |
|---|---|
| Audio-only session (uncompressed) / 音声のみのセッション（圧縮なし） | 15 minutes; 2 minutes for audio + video / 15 分。音声＋映像は 2 分 [G4] |
| Single connection / 1 本の接続 | About 10 minutes; a `GoAway` (with `timeLeft`) arrives before it disconnects / 約 10 分。切断前に `GoAway`（`timeLeft` 付き）が届く [G4] |
| Session resumption | The handle is valid for 2 hours after the session ends / handle はセッション終了後 2 時間有効 [G4] |
| Long conversations / 長い会話 | Context window compression (sliding window + trigger token threshold) / context window compression（スライディングウィンドウ＋トリガーのトークンしきい値）[G4] |
| Audio token rate / 音声のトークンレート | About 25 tokens/second / 約 25 トークン/秒 [G5] |
| Price (same for 3.8 Live / Extended / 3.1) / 価格（3.8 Live / Extended / 3.1 で同じ） | Audio input $3/1M (≈$0.005/minute), audio output $12/1M (≈$0.018/minute), text input $0.75, text output $4.50, with a free tier / 音声入力 $3/1M（≈$0.005/分）、音声出力 $12/1M（≈$0.018/分）、テキスト入力 $0.75、テキスト出力 $4.50、無料枠あり [G12] |
| Ephemeral token | Expires after 30 minutes by default, 1-minute window to open a new session, v1beta only, config can be locked with `liveConnectConstraints` / デフォルトで 30 分で失効、新規セッションを開ける時間枠は 1 分、v1beta のみ対応、`liveConnectConstraints` で設定を固定できる [G23] |
| Function calls / 関数呼び出し | Supported. Under `NON_BLOCKING`, results can be returned with `INTERRUPT` / `WHEN_IDLE` / `SILENT` / 対応。`NON_BLOCKING` では結果を返すときに `INTERRUPT` / `WHEN_IDLE` / `SILENT` を選べる [G7] |
| Cloud Run WebSocket | **Request timeout defaults to 5 minutes**, up to 60 minutes; session affinity is only best effort; the client must handle reconnection itself / **リクエストのタイムアウトはデフォルト 5 分**、最長 60 分。session affinity はベストエフォートにすぎない。再接続はクライアントが自分で処理する必要がある [G24] |

---

## 2. Limits of iPhone Safari / mobile web / iPhone Safari・モバイルウェブの制約

| Issue / 問題 | Facts / 事実 | Sources / 出典 |
|---|---|---|
| Does the microphone permission prompt keep coming back? / マイクの許可ダイアログは何度も出るか | Website settings have Ask / Deny / Allow, Ask by default. A WebKit engineer said calling gUM without user interaction 「usually ends up triggering a prompt in Safari, except if users opt-in to always grant」. In 2025-06 a developer reported that an SPA on the same origin intermittently re-prompts on route changes / ウェブサイト設定は Ask / Deny / Allow に分かれ、デフォルトは Ask。WebKit のエンジニアは、ユーザー操作なしに gUM を呼ぶと「usually ends up triggering a prompt in Safari, except if users opt-in to always grant」と述べた。2025-06 には、同じ origin の SPA がルートを切り替えると断続的にダイアログが再表示されるという開発者の報告がある | [I1][I2][I3] |
| AudioContext must be resumed inside a user gesture / AudioContext はユーザー操作の中で resume する必要がある | 「Create or resume context from inside a user gesture」 | [I4] |
| Switching away from the page or locking the screen / ページを離れる・画面をロックする | On iOS Safari the AudioContext enters the `interrupted` state and has to be `resume()`d by hand / iOS Safari では AudioContext が `interrupted` 状態になり、手動で `resume()` する必要がある | [I5] |
| Silent switch / 消音スイッチ | Web Audio is muted by the silent switch (`<audio>` is not). Since iOS 17 this can be bypassed with `navigator.audioSession.type = "playback"` / Web Audio は消音スイッチでミュートされる（`<audio>` はされない）。iOS 17 以降は `navigator.audioSession.type = "playback"` で回避できる | [I6][I7] |
| Speaker output gets quieter and goes to the earpiece once the mic is on / マイクを有効にするとスピーカーの音が小さくなり受話口から出る | WebKit bug 218012: after the microphone is granted, sound is routed to the earpiece and the volume drops sharply. Reported from Safari 14 through iOS 18.6, latest comment 2026-05. The workaround is to set `play-and-record` before capture and switch back to `playback` after, but it "only works sometimes" / WebKit bug 218012：マイクを許可すると音声が受話口に回され、音量が急に下がる。Safari 14 から iOS 18.6 まで報告があり、最新のコメントは 2026-05。回避策は、収録前に `play-and-record` にして、収録が終わったら `playback` に戻すことだが、「効くのは時々」 | [I8] |
| A serious bug in iOS 26.3–26.6 / iOS 26.3–26.6 の深刻なバグ | After the system audio daemon resets, gUM permanently reports `NotAllowedError`; reloading the page doesn't recover it, only restarting Safari does. Data from a telehealth platform: about 20% of iPhone visits hit this, and 64% of those didn't recover. Fixed, backported to 26.x on 2026-09-08, and included in the Safari 27.2 beta release notes / システムの音声デーモンがリセットされると、gUM が恒久的に `NotAllowedError` を返し、ページを再読み込みしても戻らず、Safari を再起動するしかない。ある遠隔医療プラットフォームのデータでは、iPhone からのアクセスの約 20% がこの問題に遭遇し、そのうち 64% は回復しなかった。修正済みで、2026-09-08 に 26.x へバックポートされ、Safari 27.2 beta のリリースノートに載っている | [I9][I10] |
| Safari 27.0 (2026-09-14) / Safari 27.0（2026-09-14） | Fixed 「WebProcess AudioSession to remain active while microphone capture is live」 / 「WebProcess AudioSession to remain active while microphone capture is live」を修正 | [I11] |
| Echo cancellation, noise suppression / エコーキャンセル、ノイズ抑制 | `echoCancellation` is Baseline (since 2020); `noiseSuppression` support is limited, so detect it first with `getSupportedConstraints()` / `echoCancellation` は Baseline（2020 年から）。`noiseSuppression` の対応は限られるので、まず `getSupportedConstraints()` で確認する | [I12][I13] |
| Background and lock screen / バックグラウンドとロック画面 | Reports say locking the screen or minimizing fires the WebSocket's onclose immediately (2022); iOS suspends an app shortly after it goes to the background (Apple DTS); the LiveKit community reported in 2026-07 that the microphone is suspended after switching apps, and recommends an explicit "Join Audio" button to unlock audio / 画面のロックや最小化で WebSocket の onclose がすぐに発火するという報告がある（2022）。iOS はアプリがバックグラウンドに入ると間もなく一時停止させる（Apple DTS）。LiveKit コミュニティは 2026-07 に、アプリを切り替えるとマイクが一時停止されると報告し、明示的な「Join Audio」ボタンで音声のロックを解除するやり方を勧めている | [I14][I15][I16] |
| Long-pressing a button brings up text selection or a menu / ボタンを長押しすると文字選択やメニューが出る | `-webkit-touch-callout: none` turns off the long-press menu; `user-select` needs the `-webkit-` prefix on Safari; `touch-action: manipulation` removes double-tap zoom (`none` hurts accessibility) / `-webkit-touch-callout: none` で長押しメニューを無効にする。Safari では `user-select` に `-webkit-` 接頭辞が必要。`touch-action: manipulation` でダブルタップのズームをなくす（`none` にするとアクセシビリティに影響する） | [I17][I18][I19] |
| AudioWorklet | Supported since iOS Safari 14.5 / iOS Safari 14.5 から対応 | [I20] |

---

## 3. Precedents in voice-first games / AI NPCs / 音声ファーストのゲーム・AI NPC の先例

| Title / 作品 | Input / 入力方式 | Status cues, latency handling / 状態の表示、遅延への対処 | Mishearing and jailbreaks / 聞き間違いと脱獄 | Reception / 評判 |
|---|---|---|---|---|
| **Whispers from the Star** (Anuttacon, 2025-08-14, PC) / （Anuttacon、2025-08-14、PC） | Voice only in the video-call segments; typing allowed in the messaging-app segments [U2]. Players asked to "not have to press the end button anymore", which suggests tap to start, tap to end [U4] / ビデオ通話のパートは音声のみ、メッセージアプリのパートでは文字入力もできる [U2]。プレイヤーが「もう end ボタンを押さなくていいように」と求めていることから、タップで開始・タップで終了と推測される [U4] | Runs in the cloud; audio and video drift out of sync, and latency is unstable / クラウドで動作し、音声と映像がずれ、遅延が安定しない [U3] | When the player stops mid-sentence, Stella asks follow-up questions, but players can't tell whether she didn't hear clearly or the character answered that way on purpose [U5]. On sensitive topics the content filter breaks her character [U6] / 話の途中で止まると Stella が聞き返す。ただし、聞き取れなかったのか、キャラクターがわざとそう答えたのかプレイヤーには区別がつかない [U5]。デリケートな話題ではコンテンツフィルターのせいでキャラが崩れる [U6] | 80% positive on Steam (1,663 reviews) [U1]; criticism centers on repetition, too many follow-up questions, aimless small talk and the lack of a text mode / Steam の好評率 80%（1,663 件）[U1]。批判は繰り返し、聞き返しの多さ、目的のない雑談、文字モードの欠如に集中している [U3][U4][U6] |
| **Suck Up!** (Proxima, since 2023, Steam version 2025-10-01) / （Proxima、2023 年から、Steam 版 2025-10-01） | The player speaks for real, NPCs respond to "tone and strategy", with ChatGPT on the backend / プレイヤーが実際に話し、「口調と作戦」に応じて反応する。バックエンドは ChatGPT [U7] | No public information found / 公開情報は見つからなかった | Streamers became popular by "finding ways to break the NPCs" / 配信者は「NPC を壊す方法を探す」ことで人気になった [U8] | 63% positive (210 reviews) / 好評率 63%（210 件）[U7] |
| **Vaudeville** (Bumblebee, EA in 2023, full release 2025-11-28) / （Bumblebee、2023 年 EA、2025-11-28 正式版） | Typing or speaking both work / 文字入力でも音声でもよい [U9] | Not found / 見つからなかった | Big streamers deliberately tried to break the NPCs / 大物配信者がわざと NPC を壊そうとした [U10] | 48% positive (283 reviews) / 好評率 48%（283 件）[U9] |
| **Fortnite AI Darth Vader** (2025-05-16) / （2025-05-16） | A dedicated "Conversational AI" key binding, and a Vader button on the HUD / 専用の「Conversational AI」キーが割り当てられ、HUD に Vader のボタンがある [U11][U12] | Not found / 見つからなかった | Within hours of launch it was coaxed into swearing and slurs; Epic 「pushed a hot fix within 30 minutes」; under-13s need parental permission / 公開から数時間で、汚い言葉や差別的な言葉を言うよう誘導された。Epic は「pushed a hot fix within 30 minutes」。13 歳未満は保護者の許可が必要 [U13][U14] | Lots of buzz, but the safety incident was public too / 大きな話題になったが、安全上の事故も公になった |
| **Fortnite Persona (UEFN AI NPCs, experimental release 2026-04-16)** / **Fortnite Persona（UEFN AI NPC、2026-04-16 実験版）** | Voice chat / ボイスチャット [U15] | Officially admits 「LLM response times are slower than we expect of the final release」 / 公式に「LLM response times are slower than we expect of the final release」と認めている | A safety layer on top of the model; characters for medical use, romantic companionship or bypassing safety mechanisms are prohibited; the conversation is cleared every match / モデルの外側に安全レイヤーがある。医療、恋愛パートナー、安全機構の回避を目的とするキャラクターは禁止。1 試合ごとに会話をリセットする [U15][U16] | Experimental stage / 実験段階 |
| **Ubisoft NEO NPC** (GDC 2024, Inworld + NVIDIA) / （GDC 2024、Inworld + NVIDIA） | Voice / 音声 | A relationship meter on screen / 画面に関係値のバーがある [U17] | On off-topic requests, Bloom first catches it with a quip, then steers the conversation back to the mission / 本筋から外れた要求には、Bloom がまず気の利いた一言で受け止めてから、話を任務に戻す [U18] | Testers felt "the guardrails are too heavy and the goals too scattered" / 試遊した人の評価は「ガードレールが重すぎ、目標が散漫すぎる」 [U18] |
| **Ubisoft Teammates** (2025-11-21) / （2025-11-21） | Voice commands / 音声コマンド | Not found / 見つからなかった | The narrative director said they use "fences" so NPCs improvise within a set range / ナラティブディレクターは、"fences" を使って NPC が決められた範囲内で即興するようにしていると述べた [U19] | A few hundred people took part in the closed test / クローズドテストに数百人が参加 |
| **PUBG Ally** (NVIDIA ACE, 2026) / （NVIDIA ACE、2026） | Voice / 音声 | Runs on-device for "predictable response times"; a behavior tree handles instant reactions, the LLM handles slow thinking / 「予測できる応答時間」のために端末上で動かす。行動ツリーが即時の反応を、LLM が遅い思考を担う [U20] | Only one map and one mode are open, to narrow the domain / マップ 1 つ、モード 1 つだけを公開して領域を絞っている | — |

**Research basis for conversational latency**:
- Across 10 languages, the average gap between turns differs by about 250ms; **Japanese averages only 7ms**, the shortest, while Danish is about 500ms [R1][R2].
- When the gap exceeds 700ms, the share of "refusal, reluctance" responses rises noticeably; in other words, the silence itself starts to carry meaning [R3].
- Japanese speakers use backchannels (aizuchi) noticeably more often than Americans [R4].
- What the voice agent industry says: typical human response time is about 500ms, and 1,500ms voice-to-voice is an "important target" [R5].

**会話の遅延に関する研究の裏づけ**：
- 10 言語でのターン間の間隔の平均は約 250ms の差があり、**日本語の平均はわずか 7ms** で最も短い。デンマーク語は約 500ms [R1][R2]。
- 間隔が 700ms を超えると、「拒否・気乗りしない」タイプの応答の割合が明らかに上がる。つまり沈黙そのものが意味を帯び始める [R3]。
- 日本人の相槌の頻度はアメリカ人よりはっきり高い [R4]。
- 音声エージェント業界の言い分：人間の典型的な応答時間は約 500ms で、voice-to-voice 1,500ms が「重要な目標」[R5]。

---

## 4. Voice UX best practices / 音声 UX のベストプラクティス

**Trade-offs between the three capture modes**:
- **Push-to-talk (PTT)**: turn detection is unambiguous, but it is 「quite different from a natural conversation」[R5].
- **Tap to toggle**: less effort than holding; the turn ends with a second tap or by VAD.
- **Open microphone**: the most natural, but can trigger by mistake. OpenAI's semantic VAD uses eagerness to trade off between "waiting for the user to finish" and "jumping in" [R6]; Gemini recommends 500–800ms of silence [G3].
- **Never voice alone**: voice must be an optional input, with a non-voice alternative [R7]. Whispers from the Star was heavily criticized for its inadequate text mode [U2][U6].

**3 つの収音方式の取捨**：
- **押している間だけ話す（PTT）**：ターンの判定はあいまいにならないが、「quite different from a natural conversation」[R5]。
- **タップで切り替え**：押し続けるより楽。終了は 2 回目のタップか VAD で決まる。
- **常時マイク**：最も自然だが、誤作動の恐れがある。OpenAI の semantic VAD は eagerness で「ユーザーが話し終えるのを待つ」と「話をさえぎる」の間を調整する [R6]。Gemini は無音を 500–800ms にするよう勧めている [G3]。
- **音声だけに頼らない**：音声は任意の入力でなければならず、音声以外の代替手段が必要 [R7]。Whispers from the Star は文字モードが不十分なことで大いに批判された [U2][U6]。

**Showing "what was heard"**: Alexa's principle is "Always show what was heard to enable correction" [R8]. But Gemini's transcription may not match what the model actually understood [G19].

**「何が聞こえたか」を表示する**：Alexa の原則は "Always show what was heard to enable correction" [R8]。ただし Gemini の文字起こしは、モデルが実際に理解した内容と一致しないことがある [G19]。

**Confirm key actions**: Alexa recommends explicit confirmation for high-consequence actions and implicit or contextual confirmation for low-consequence ones [R8]. Google's error handling adds hints step by step and exits gracefully after 3 no-matches in a row [R9].

**重要な操作は確認する**：Alexa は、影響の大きい操作には明示的な確認を、影響の小さい操作には暗黙的または文脈による確認を勧めている [R8]。Google のエラー処理は段階的にヒントを増やし、no-match が 3 回続いたらうまく終了する [R9]。

**Subtitles (XAG 104)**: show the name when the speaker changes; at most 40 characters per line (English); at most 2 lines; background opacity adjustable from 0–100%; can be toggled at any time [R10]. I found no standard for characters per line in Japanese; I suggest testing with about 20 full-width characters (inference).

**字幕（XAG 104）**：話者が変わるときは名前を表示する。1 行は 40 文字以内（英語）。最大 2 行。背景の不透明度は 0–100% で調整できる。いつでもオン・オフできる [R10]。日本語の 1 行あたりの文字数の基準は見つからなかった。全角約 20 文字で自分たちで試すことを勧める（推測）。

---

## 5. UX recommendations (everything below is a recommendation) / UX の提案（以下はすべて提案）

1. **Default to push-to-talk, offer tap-to-toggle in settings**, with the open microphone only as an experimental option.
   **デフォルトは押している間だけ話す方式にし、設定でタップ切り替えを用意する**。常時マイクは実験的な選択肢にとどめる。
   - Implementation: turn off automatic VAD; send `activityStart` on press and `activityEnd` on release.
     実装：自動 VAD をオフにする。押したときに `activityStart`、離したときに `activityEnd` を送る。
   - Keep `START_OF_ACTIVITY_INTERRUPTS`: pressing interrupts the NPC immediately, **and clears the local playback buffer at once**, without waiting for the server's `interrupted`.
     `START_OF_ACTIVITY_INTERRUPTS` は残す：押した瞬間に NPC を中断し、**同時にローカルの再生バッファをすぐに空にする**。サーバーの `interrupted` を待たない。
   - Reason: this avoids Japanese aizuchi falsely triggering interruptions, speaker echo making the NPC interrupt itself (inference), and the ambiguity of proactive audio not responding; it also reduces input billing.
     理由：日本語の相槌による誤った割り込み、スピーカーのエコーで NPC が自分自身を中断すること（推測）、proactive audio が応答しないことによるあいまいさを避けられる。入力の課金も減る。
2. **Four states, plus a "no response" state**: idle → listening (AudioWorklet level waveform) → thinking → speaking (subtitles streaming in). Within **200ms** of releasing the button the character must react visibly (a nod, a glance up), because Japanese turn gaps are extremely short [R1]. Past about 700ms, play that character's pre-recorded aizuchi (「うむ…」「ほう」) [R3]; these are pre-generated with the TTS model and the same voiceName so the timbre matches (inference: the voice names are shared between the two [G3][G11]). If there's still no response after about 6 seconds, show 「もう一度話す／文字で送る」.
   **4 つの状態に「無応答」の状態を加える**：待機 → 聞き取り（AudioWorklet のレベル波形）→ 考え中 → 発話（字幕がストリーミングで出る）。ボタンを離してから **200ms 以内**に人物が目に見える反応（うなずく、目を上げる）をする必要がある。日本語のターン間の間隔は極めて短いからだ [R1]。約 700ms を超えたら、その人物の事前収録の相槌（「うむ…」「ほう」）を流す [R3]。この相槌は TTS モデルと同じ voiceName で事前に生成し、声色をそろえる（推測：両者の voice 名は共通 [G3][G11]）。約 6 秒たっても応答がなければ「もう一度話す／文字で送る」を表示する。
3. **One Live session per character**: each with its own voiceName and system instruction (period-appropriate tone, first person, 「RESPOND IN JAPANESE」, and guardrails written along the lines of Bloom's "catch it, then steer back" handling of off-topic talk). Open the session early as the player approaches the character to hide the handshake time (inference). Story state is written back to the game via function calls; transcription results don't go into logic.
   **1 人の登場人物に 1 つの Live セッション**：それぞれに voiceName と system instruction を設定する（時代に合った口調、一人称、「RESPOND IN JAPANESE」、ガードレールは Bloom の「まず受け止めてから戻す」という脱線への対処を参考に書く）。人物に近づいたら先にセッションを確立し、ハンドシェイクの時間を隠す（推測）。物語の状態は関数呼び出しでゲームに書き戻し、文字起こしの結果はロジックに入れない。
4. **Casting suggestions (need to be confirmed by listening)**:
   **配役の提案（試聴での確認が必要）**：
   - メロス: Puck or Fenrir
     メロス：Puck または Fenrir
   - 王ディオニス: Algenib or Charon
     王ディオニス：Algenib または Charon
   - セリヌンティウス: Iapetus or Achird
     セリヌンティウス：Iapetus または Achird
   - 妹: Leda
     妹：Leda
   - Old man, narration: Rasalgethi or Gacrux
     老人、ナレーション：Rasalgethi または Gacrux
   - We could build a "cast list" page so the judges can audition each voice.
     「キャスト表」のページを作り、審査員が 1 つずつ試聴できるようにしてもよい。
5. **Show what was heard**: show `inputTranscription` in a pale bubble; tapping it opens text input prefilled with the transcription. Add character and place names to `customVocabulary` (needs testing).
   **聞こえた内容を表示する**：`inputTranscription` を淡い色の吹き出しで表示し、タップすると文字入力に切り替わって文字起こしが入った状態になる。`customVocabulary` に人名・地名を入れる（要実測）。
6. **Explicit confirmation for key story moments**: e.g. "handing over セリヌンティウス as a hostage", "accepting the king's terms"; the model triggers a function call, the UI shows a confirmation card, and saying 「はい」 aloud also confirms.
   **重要な筋は明示的に確認する**：たとえば「セリヌンティウスを人質に差し出す」「王の条件を受け入れる」。モデルが関数呼び出しを発し、UI に確認カードを出す。声で「はい」と言っても確認できる。
7. **Guarding against breaking character and jailbreaks**: guardrails in the system instruction; server-side output filtering; logging. Vader's lesson is that people will try to break the NPCs on launch day [U13].
   **キャラ崩れと脱獄を防ぐ**：system instruction にガードレールを書く。サーバー側で出力をフィルタする。ログを記録する。Vader の教訓は、公開当日から NPC を壊そうとする人が出るということ [U13]。
8. **iOS startup flow**: a single 「はじめる」 button, and in that one tap do the following in order:
   **iOS の起動フロー**：「はじめる」ボタンを 1 つ置き、その 1 回のタップの中で次を順に行う：
   - Create or resume the AudioContext
     AudioContext を作成または resume する
   - Set `navigator.audioSession.type`
     `navigator.audioSession.type` を設定する
   - Call gUM once
     gUM を 1 回呼ぶ
   - Open the WebSocket
     WebSocket を確立する

   Then handle these cases:

   そのあとで次のケースに対処する：
   - Listen for `visibilitychange` and `interrupted`, show 「タップして再開」, and reconnect with the resumption handle.
     `visibilitychange` と `interrupted` を監視し、「タップして再開」を表示して、resumption handle で再接続する。
   - Recommend headphones (avoids the earpiece routing and echo problems).
     イヤホンの使用を勧める（受話口へのルーティングとエコーの問題を避ける）。
   - When gUM reports `NotAllowedError` but the permission is actually granted, prompt the user to restart Safari and switch straight to text input [I9].
     gUM が `NotAllowedError` を返すのに権限は実際には許可されている場合、Safari の再起動を促し、すぐに文字入力に切り替える [I9]。
   - Add `-webkit-user-select:none; -webkit-touch-callout:none; touch-action:manipulation` to the talk button.
     話すボタンに `-webkit-user-select:none; -webkit-touch-callout:none; touch-action:manipulation` を付ける。
9. **Server side**: raise the Cloud Run request timeout to 60 minutes; handle `GoAway`; turn on context compression for sessions over 15 minutes [G4][G24].
   **サーバー側**：Cloud Run のリクエストタイムアウトを 60 分にする。`GoAway` を処理する。15 分を超えるセッションでは context compression を有効にする [G4][G24]。
10. **Subtitles**: give speaker names colors; at most 2 lines; stream them in and align them with audio playback progress; add furigana to rare words (邪智暴虐 etc.).
    **字幕**：話者名に色を付ける。最大 2 行。ストリーミングで表示し、音声の再生位置に合わせる。難しい語（邪智暴虐 など）には振り仮名を付ける。

---

## Sources (all checked on 2026-10-06) / 出典（すべて 2026-10-06 に確認）
- [G1] ai.google.dev/gemini-api/docs/models/gemini-3.8-live (updated 2026-09-15 / 2026-09-15 更新)
- [G2] ai.google.dev/gemini-api/docs/models (2026-10-01)
- [G3] ai.google.dev/gemini-api/docs/live-guide (2026-09-18)
- [G4] ai.google.dev/gemini-api/docs/live-session (2026-09-15)
- [G5] ai.google.dev/gemini-api/docs/live-api/best-practices (2026-09-15)
- [G6] ai.google.dev/api/live (2026-09-04)
- [G7] ai.google.dev/gemini-api/docs/live-tools (2026-09-15)
- [G8] ai.google.dev/gemini-api/docs/live (undated / 日付なし)
- [G9] ai.google.dev/gemini-api/docs/changelog (9-15 entry / 9-15 の項目)
- [G10] firebase.google.com/docs/ai-logic/live-api/configuration (2026-10-01)
- [G11] ai.google.dev/gemini-api/docs/speech-generation (2026-10-01)
- [G12] ai.google.dev/gemini-api/docs/pricing (checked 2026-10-06 / 2026-10-06 に確認)
- [G13] blog.google/innovation-and-ai/technology/developers-tools/build-with-gemini-3-1-flash-live/ (2026-03-26)
- [G14] androidheadlines.com/2026/09/google-launches-gemini-3-8-live-audio-models.html (2026-09-15); thurrott.com/a-i/google-gemini-a-i/341685/ (2026-09-15)
- [G15] cloud.google.com/blog/products/ai-machine-learning/gemini-3-8-live-with-live-avatar-is-now-generally-available (2026-09-24)
- [G16] docs.cloud.google.com/gemini-enterprise-agent-platform/models/maas/google (body could not be read / 本文は読み取れず)
- [G17] discuss.ai.google.dev/t/…eu-region-availability/144429 (2026-05 to 08 / 2026-05〜08)
- [G18] discuss.ai.google.dev/t/bug-voicename-configuration-is-silently-ignored…/179065 (2026-08-20, official reply 09-14 / 2026-08-20、公式回答 09-14)
- [G19] discuss.ai.google.dev/t/…input-audio-transcription-returns-incorrect-text…/128300 (2026-03 to 09 / 2026-03〜09)
- [G20] discuss.ai.google.dev/t/…delays-or-missing-input-audio-transcription-events/110732 (2025-12 to 2026-01 / 2025-12〜2026-01)
- [G21] community.livekit.io/t/how-to-fix-latency-3-secs-of-gemini-3-1-flash-live/766 (2026-04-03)
- [G22] discuss.ai.google.dev/t/live-api-5-6-second-response-latency/123254 (2026-02-16)
- [G23] ai.google.dev/gemini-api/docs/ephemeral-tokens (2026-09-15)
- [G24] docs.cloud.google.com/run/docs/triggering/websockets (2026-09-30)
- [I1] lists.w3.org/Archives/Public/public-webrtc-logs/2020Mar/0214.html (2020-03-30)
- [I2] ios.gadgethacks.com/how-to/customize-camera-microphone-location-permissions-for-specific-websites-ios-13s-safari-0198476/ (iOS 13 era / iOS 13 の頃)
- [I3] developer.apple.com/forums/thread/788518 (2025-06)
- [I4] developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Best_practices (2026-08-27)
- [I5] developer.mozilla.org/en-US/docs/Web/API/BaseAudioContext/state (2025-07-24)
- [I6] bugs.webkit.org/show_bug.cgi?id=237322 (reported 2022, comments in 2024-09 / 2022 年報告、2024-09 にコメントあり)
- [I7] developer.mozilla.org/en-US/docs/Web/API/Audio_Session_API (2026-08-19)
- [I8] bugs.webkit.org/show_bug.cgi?id=218012 (reported 2020, latest comment 2026-05-20 / 2020 年報告、最新コメント 2026-05-20)
- [I9] bugs.webkit.org/show_bug.cgi?id=319706 (2026-07-17, backported 2026-09-08 / 2026-07-17、2026-09-08 にバックポート)
- [I10] developer.apple.com/documentation/safari-release-notes/safari-27_2-release-notes (2026-09-16)
- [I11] developer.apple.com/documentation/safari-release-notes/safari-27-release-notes (2026-09-14)
- [I12] developer.mozilla.org/en-US/docs/Web/API/MediaTrackSettings/echoCancellation
- [I13] developer.mozilla.org/en-US/docs/Web/API/MediaTrackConstraints/noiseSuppression
- [I14] bugs.webkit.org/show_bug.cgi?id=247943 (2022–2024)
- [I15] developer.apple.com/forums/thread/716118 (2022-09)
- [I16] community.livekit.io/t/…background-audio-suspension-for-ios-users/1649 (2026-07)
- [I17] developer.mozilla.org/en-US/docs/Web/CSS/-webkit-touch-callout
- [I18] developer.mozilla.org/en-US/docs/Web/CSS/user-select (2026-04-20)
- [I19] developer.mozilla.org/en-US/docs/Web/CSS/touch-action (2026-04-20)
- [I20] caniuse.com/mdn-api_audioworklet
- [U1] store.steampowered.com/app/3730100/
- [U2] steamcommunity.com/app/3730100/discussions/0/608668111724477736/ (2025-08-15)
- [U3] 36kr.com/p/3428919332048259 (2025-08-19)
- [U4] vaporlens.app/app/3730100/whispers_from_the_star.md (summary of player reviews / プレイヤーレビューのまとめ)
- [U5] steamcommunity.com/app/3730100/discussions/0/506216918922069229/ (2025-10-18)
- [U6] blog.soullink.io/whispers-from-the-star-review/ (2026-07-01)
- [U7] store.steampowered.com/app/2726370/Suck_Up/
- [U8] knowyourmeme.com/memes/subcultures/suck-up
- [U9] store.steampowered.com/app/2240920/Vaudeville/
- [U10] knowyourmeme.com/memes/subcultures/vaudeville-video-game
- [U11] beebom.com/how-to-talk-to-darth-vader-ai-in-fortnite/ (2025-05-16)
- [U12] thespike.gg/fortnite/beginner-guides/star-wars-vader-ai
- [U13] foxnews.com/tech/epic-games-debuts-voice-interactive-darth-vader-fortnite-its-already-being-tricked-swearing (2025-05-17)
- [U14] nintendolife.com/news/2025/05/fortnite-turns-to-the-dark-side-with-ai-darth-vader-voice-and-of-course-its-been-swearing (2025-05)
- [U15] fortnite.com/news/bring-npcs-to-life-with-ai-powered-conversations (2026-04-16)
- [U16] dev.epicgames.com/documentation/fortnite/developing-personas-overview-in-unreal-editor-for-fortnite
- [U17] videogameschronicle.com/news/ubisoft-shows-off-ai-powered-game-characters-at-gdc-the-game-world-actually-listens (2024-03-19)
- [U18] wccftech.com/inworld-ai-npc-gdc-2024-hands-on-nvidia-and-ubisoft-show-a-glimpse-of-the-future/ (2024-03-30)
- [U19] news.ubisoft.com/en-us/article/3mWlITIuWuu0MoVuR6o8ps/ (2025-11-21)
- [U20] developer.nvidia.com/blog/how-krafton-built-pubg-ally-a-co-playable-character-powered-by-nvidia-ace/ (2026-06-25)
- [R1] nationalgeographic.com/science/article/pregnant-pauses-and-rapid-fire-how-do-different-cultures-take-turns-to-talk (2009-06-19)
- [R2] forms.mpi.nl/node/50939 (Stivers et al., PNAS 2009, 106(26))
- [R3] eprints.whiterose.ac.uk/116177 (Kendrick & Torreira, Discourse Processes 2015)
- [R4] cambridge.org/core/journals/language-in-society/article/abs/backchannels-across-cultures-a-study-of-americans-and-japanese1/B26AC3C44C237B9A380A5494EA5693ED (White, 1989)
- [R5] voiceaiandvoiceagents.com (2026-06 updated edition / 2026-06 更新版)
- [R6] developers.openai.com/api/docs/guides/realtime-vad
- [R7] gameaccessibilityguidelines.com/ensure-that-speech-input-is-not-required-and-included-only-as-a-supplementary-alternative-input-method/
- [R8] developer.amazon.com/en-US/alexa/alexa-haus/design-principles/be-trustworthy
- [R9] developers.google.com/assistant/conversation-design/errors (2024-09-18)
- [R10] learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/104 (2026-03-04)

**Not yet verified**:
- The body of the Vertex AI pages couldn't be fetched, so the model ID, region and voice list for 3.8 Live on Vertex are not verified.
- No clear source was found on whether Whispers from the Star and Suck Up! use push-to-talk or tap-to-toggle.
- Whether the new transcription fields such as `customVocabulary` take effect on 3.8 Live needs testing.

**まだ確認できていない内容**：
- Vertex AI のページ本文を取得できなかったため、Vertex 上の 3.8 Live のモデル ID、リージョン、音声の一覧は確認していない。
- Whispers from the Star と Suck Up! が押している間だけ話す方式なのかタップ切り替えなのか、はっきりした出典は見つからなかった。
- `customVocabulary` などの新しい文字起こしフィールドが 3.8 Live で有効かどうかは、実測が必要。
