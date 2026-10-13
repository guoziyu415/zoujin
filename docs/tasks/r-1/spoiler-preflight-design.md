# Review high-risk turns before voicing them: design record / 高リスクのターンは審査してから発声する：設計記録

Status: not implemented, not verified, and not counted among R-1's completed items. With this limited fix, under the current S-092 / S-095 there is no confirmed new E2, only one remaining pragmatic dispute, so we are not expanding the voice pipeline on that basis, given its obvious latency cost. This document keeps the fallback from S-068⑤ / S-086⑦: if a formal rerun still fails, turns in which the player asks about the future are reviewed before they are voiced. An after-the-fact `monitor` cannot take back sound that has already played, and cannot offset a leak that has already happened.

状態：未実装・未検証で、R-1 の完了項目には数えない。今回の限定的な修正では、現行の S-092 / S-095 に照らして確認された新しい E2 はなく、語用論上の争点が 1 件残るだけなので、それを根拠に遅延コストが明らかな音声パイプラインを拡張することはしない。この文書は S-068⑤ / S-086⑦ の後手を残しておくもの：正式な再実行でもなお不合格なら、プレイヤーが未来について尋ねたターンは審査してから発声する。事後の `monitor` では出てしまった音声を取り消せず、すでに起きた漏洩を相殺することもできない。

## What existing code can be reused / 既存コードで再利用できるもの

- `gateway/ws.py::Turn` already has the in-memory-only `pcm_out`, the current transcription and the cancel/void state; `_stream` is the single outlet for audio and character subtitles.
  `gateway/ws.py::Turn` にはメモリ上のみの `pcm_out`、現在の文字起こし、キャンセル/無効化の状態がすでにある。`_stream` は音声と登場人物の字幕の唯一の出口。
- `models/gemini_live.py::_answer` provides audio, transcription, end and usage events. The normal path sends chunk by chunk; the original model usage should be billed as usual even if the content is ultimately not delivered.
  `models/gemini_live.py::_answer` は音声、文字起こし、終了、使用量のイベントを提供する。通常経路はチャンクごとに送信する。元のモデルの使用量は、内容が最終的に配信されなくても通常どおり計上すべき。
- `gateway/fallback.py::BufferedTranscriber` can transcribe the player's audio independently; `fallback_text` can fill in the transcription of a character's audio. Both already handle timeouts and cost, but extra calls add latency and expense.
  `gateway/fallback.py::BufferedTranscriber` はプレイヤーの音声を独立して文字起こしできる。`fallback_text` は登場人物の音声の文字起こしを補える。どちらもタイムアウトとコストの処理はあるが、呼び出しを増やすと遅延と費用が増える。
- `narrator/pipeline.py::Pipeline.call` already has model requests, JSON schema, extra validation, timeouts, bounded retries and spend; its infrastructure can be reused with new formal classification/review operations added. The spike judge scripts cannot be moved straight into production dependencies.
  `narrator/pipeline.py::Pipeline.call` にはモデルリクエスト、JSON schema、追加の検証、タイムアウト、有限回のリトライ、費用がすでにある。基盤は再利用でき、正式な分類/再審査の操作を新設する。spike の審査スクリプトをそのまま本番の依存に持ち込んではならない。
- `brief.situation_facts` is already filtered by character knowledge, forgetting and first-hand experience, so it can serve as same-source context for what may be disclosed. The omniscient list of unknowns/future goes only to the server-side reviewer, never to the character generator.
  `brief.situation_facts` は登場人物の知識、忘却、実体験ですでに絞り込まれているので、開示してよい内容の同一ソースのコンテキストとして使える。全知の未知/未来のリストはサーバー側の再審査器にだけ渡し、キャラクター生成器には渡さない。

## Assumptions that cannot be reused directly / そのままでは使えない前提

Currently `_answer` outputs audio first and only outputs the player's `input_final` after `turnComplete` and the transcription wrap-up. So deciding only once `_stream` has received the player's final transcript is already too late; we cannot claim that the existing code merely makes high-risk speech slower. `t.flowing` is the safety-review gate that pauses consumption of that same event stream; it cannot be cleared to wait for the final transcript later in the stream, or the two may wait on each other.

現在 `_answer` は先に音声を出力し、`turnComplete` と文字起こしの締めくくりの後で初めてプレイヤーの `input_final` を出力する。したがって `_stream` がプレイヤーの確定文を受け取ってから判断するのでは遅すぎる。既存のコードで高リスクの音声だけを遅くできるとは主張できない。`t.flowing` は同じイベントストリームの消費を一時停止する安全審査のゲートであり、これを解除してストリームの後方の確定文を待つことはできない。さもないと互いに待ち合う可能性がある。

A normal text turn already has the player's original text when it starts, so it can be classified first. For voice there are two real options:

通常のテキストのターンは開始時点でプレイヤーの原文があるので、先に分類できる。音声には現実的な選択肢が 2 つある：

1. After the player releases the talk button, transcribe and classify independently first, then decide whether to stream the reply or hold it back. This can reuse the transcriber, but every voice turn bears the transcription/classification latency.
   話し終えてボタンを離した後、まず独立して文字起こしと分類を行い、その後で返答をストリーミング送信するか保留するかを決める。文字起こし器は再利用できるが、すべての音声ターンが文字起こし/分類の遅延を負う。
2. Keep reading all Live events into a bounded private buffer, and route once the player's final transcription arrives. The implementation is smaller, but with the current event order even normal speech may only be voiced after the full answer is in.
   Live のすべてのイベントを上限付きの非公開バッファに読み続け、プレイヤーの最終的な文字起こしが来てからルーティングする。実装は小さいが、現在のイベント順序では通常の音声も回答が揃うまで発声されない可能性がある。

To really add latency only to high-risk speech, the input-transcription timing would need to change, or a separate early-transcription route would be needed, with safety proven by the actual event order and accuracy; we cannot promise low risk on the strength of unstable half-sentence transcriptions alone. This needs its own evaluation and is not something to implement in passing this round.

本当に高リスクの音声だけに遅延を加えるには、入力の文字起こしのタイミングを変えるか、独立した早期の文字起こしルートが必要で、実際のイベント順序と精度で安全性を証明しなければならない。不安定な文の途中の文字起こしだけを頼りに低リスクを約束することはできない。これは別途評価が必要で、今回ついでに実装するものではない。

## Boundary of the minimal closed loop / 最小の閉ループの境界

The router only identifies whether what is asked involves a concrete future outcome, an event the character did not witness, or someone else's secret; it does not judge whether the character's attitude is negative. 「Do you trust people?」 and 「Did the stonemason ever doubt his friend?」 must be kept apart. When the decision is uncertain, the turn goes to review. Sources of known facts should keep the fact ID, the character and their current state, so that normal answers about current facts are supported.

ルーターが識別するのは、尋ねられた内容が未来の具体的な結果、本人が体験していない出来事、他人の秘密に関わるかどうかだけで、登場人物の態度が否定的かどうかは判断しない。「人を信じるか」と「石工は友を疑ったことがあるか」は分けて扱う。判定が不確かなときは再審査に回す。既知の事実のソースには fact ID、登場人物、その時点の状態を残し、現在の事実についての通常の回答を支えられるようにする。

On a high-risk turn the model events are drained continuously in the background, and the audio, the character's partial subtitles, the final transcript and `turn_complete` are all held back. Once the full text has arrived it is reviewed against the formal knowledge boundary; only if it is allowed is the **same** reviewed audio/subtitle content delivered in its original order. We must not check one piece of text and then let Live freely generate a different piece of audio, nor hold back only the audio while the subtitles leak first. The buffer needs upper limits on bytes, duration and total timeout, and is neither stored in the database nor written to logs.

高リスクのターンでは、バックグラウンドでモデルのイベントを drain し続け、音声、登場人物の途中の字幕、確定文、`turn_complete` はすべて送信を保留する。全文が揃ったら正式な知識の境界に沿って再審査し、許可された場合に限り、審査済みの**同一の**音声/字幕を元の順序で配信する。あるテキストを確認しておいて Live に別の音声を自由に生成させてはならず、音声だけを保留して字幕を先に漏らしてもならない。バッファにはバイト数、時間長、総タイムアウトの上限が必要で、データベースにも保存せず、ログにも書かない。

The review blocks only concrete unknown facts, outcomes that have not happened yet, and misplaced points in time; a character's own beliefs, wishes and resolve, and generalized emotional speculation that does not hit a specific secret, are still allowed. The dual-judge examples of pragmatic ambiguity this time show that "hooking up the same judge again" is no guarantee in itself; the new production gate must be validated independently with a limited set of labeled inputs and fault cases, and we must not claim the judges are calibrated.

再審査が止めるのは、具体的な未知の事実、まだ起きていない結果、時点の取り違えだけ。登場人物自身の信念、願い、決意、また特定の秘密に当たらない一般化された感情の推測は引き続き許される。今回の二重判定で語用論上あいまいな例が示したように、「同じ judge をもう一度つなぐ」こと自体は保証にならない。新しい本番ゲートは、ラベル付きの限られた入力と障害で独立に検証しなければならず、審査員がキャリブレーション済みだと称してはならない。

Refusal, missing transcription, timeout, 429 or invalid output must never let unreviewed audio through; reuse the existing text-fallback capability to generate and review replacement text, or end in a recoverable no-reply. The first version does not resample indefinitely, nor does it force the character to read the replacement text aloud. A discarded original reply must not enter recent dialogue, persisted utterances, memory or async narration input; a Live session that has remembered the bad reply must be closed/rebuilt. Costs are still recorded; a retry must be bound to the original turn and must not overwrite a failure or submit twice.

拒否、文字起こしの欠落、タイムアウト、429、無効な出力のいずれでも、未審査の音声を通してはならない。既存のテキストへのフォールバック機能を再利用して代替テキストを生成・審査するか、回復可能な無回答で終える。初版では無限に再サンプリングせず、代替テキストを登場人物に読み上げさせることも強制しない。破棄した元の返答を、直近の会話、永続化した発話、記憶、非同期のナレーション入力に入れてはならない。悪い返答を覚えてしまった Live セッションは閉じて作り直す必要がある。費用は引き続き記録し、リトライは元のターンに紐づけ、失敗を上書きしたり二重に提出したりしてはならない。

## What must be verified before and after implementation / 実装の前後に必ず検証すること

- Event-level tests: zero delivery of high-risk original audio/subtitles before allow; low-risk text still delivered chunk by chunk; `turn_complete` not sent early; the character's last transcription matches the reviewed text.
  イベントレベルのテスト：allow の前に高リスクの元の音声/字幕がゼロ件しか配信されないこと。低リスクのテキストは引き続きチャンクごとに配信されること。`turn_complete` が早く送られないこと。登場人物の最後の文字起こしが審査済みテキストと一致すること。
- The private buffer is destroyed on cancel, switching characters, voiding, disconnect and safety pause; it must not be sent late in the next turn or after reconnecting; a failed review must not enter `_finish`'s path for filling in the final transcript.
  キャンセル、登場人物の切り替え、無効化、切断、安全のための一時停止で非公開バッファを破棄すること。次のターンや再接続後に後から送ってはならない。審査に失敗したものが `_finish` の確定文補完の経路に入ってはならない。
- Known/unknown fact comparisons, positive controls on general views of human nature, negative controls on future outcomes and paraphrases, voice final transcript arriving after the audio, missing transcription, timeout, 429, buffer limit; each failure is fully billed and Live generation is not repeated.
  既知/未知の事実の対照、一般的な人間観の陽性対照、未来の結果と言い換えの陰性対照、音声の確定文が音声より遅れる場合、文字起こしの欠落、タイムアウト、429、バッファ上限。いずれの失敗も費用を完全に計上し、Live の生成を繰り返さないこと。
- Actually measure first-audio and total latency for normal/high-risk turns, the share of classifications leaking into the normal path, voice/text quality, and call cost. The current Live timings from the limited 15 items are not a production first-audio baseline and cannot be used to promise performance for the new path.
  通常/高リスクのターンの最初の音声までの遅延と総遅延、分類が通常経路に漏れる割合、音声/テキストの品質、呼び出し費用を実測する。現在の限られた 15 件の Live の所要時間は本番の最初の音声のベースラインではなく、新しい経路の性能を約束する根拠にはならない。

Start with offline event and state invariants, then run a fixed, limited real comparison set; if things still leak, keep the original failures and re-examine the routing and the knowledge basis, rather than continuing to tune by sampling on the two original questions.

まずオフラインのイベントと状態の不変条件を固め、その後で固定された限定的な実際の対照セットを実行する。それでも漏れる場合は、元の失敗を残してルーティングと知識の根拠を見直し、元の 2 問でサンプリングしながら調整を続けることはしない。
