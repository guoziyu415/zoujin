# R-1 anti-spoiler validation / R-1 ネタバレ防止の検証

This page records the anti-spoiler part of steps 14 and 26 of `app-team/pm/deferred-steps.md`. Blind-labeling calibration of the judges and generating/listening to pre-recorded voice are still outside this scope. Raw lines, the call ledger and the full evidence stay only on the local machine and do not go into the repo or the public site.

このページは `app-team/pm/deferred-steps.md` の第 14、26 ステップのうちネタバレ防止の部分を記録する。審査員のブラインドラベリングによるキャリブレーションと、事前収録音声の生成・試聴は今回の範囲外のまま。生のセリフ、呼び出しの台帳、完全な証拠はローカルにのみ置き、リポジトリや公開サイトには入れない。

## Question inventory and historical evidence / 問題の在庫と過去の証拠

| Question set / 問題セット | Character-moment scenarios / 登場人物・時点のシナリオ | Questions / 問題数 |
| --- | ---: | ---: |
| S-3 original questions `s3_scenarios.json` / S-3 元の問題 `s3_scenarios.json` | 5 | 50 |
| `s3_spoiler_probes.json` | 25 | 258 |
| `s3_spoiler_probes_2.json` | 21 | 189 |
| Total / 合計 | 51 | 497 |

There are 497 distinct "character × moment × question" combinations, covering all 7 characters in the world model who can be talked to; deduplicated by sentence alone, there are 361 sentences. These are not 497 mutually distinct texts, nor 497 complete game runs. The two probe files each cover 13 `after` values, and together with the original questions they cover 22 distinct `after` values.

異なる「登場人物 × 時点 × 質問」の組み合わせは 497 あり、世界モデルで会話できる登場人物 7 人全員をカバーする。文だけで重複を除くと 361 文になる。互いに異なる 497 のテキストでも、497 の完全なゲームの流れでもない。2 つの probe ファイルはそれぞれ 13 の `after` をカバーし、元の問題と合わせて異なる `after` は 22 になる。

The historical run `20261011-152340` covered only the first 308 questions × 2 passes, 616 replies in total. The two full re-judging rounds added no generation coverage; `20261012-003853` completed only 129/616. The 14 E2 flags of the old s092.2 involve 12 questions; an existing UX file confirmed that the sister saying 「心配でたまらない」 while not knowing the deadline is a real overstep of knowledge, and the other 13 are false positives under the established rules. This time, unfinished re-judging and summaries under the old judging method are not treated as the current version passing.

過去の `20261011-152340` は最初の 308 問 × 2 回のみで、返答は計 616。2 回の完全な再判定は生成のカバレッジを増やしていない。`20261012-003853` は 129/616 しか完了していない。旧 s092.2 の E2 フラグ 14 件は 12 問に関わり、既存の UX ファイルで、そのうち妹が期限を知らないのに「心配でたまらない」と言ったものは実際に知識の境界を越えていると確認され、残り 13 件は既定のルールの下での誤検出とされた。今回、未完了の再判定や旧判定法による集計を現行バージョンの合格とはみなさない。

## Two actual call paths / 2 つの実際の呼び出し経路

- `spikes/backend/zj_spike/s3_runtime.py` uses the production `gateway.brief.build` and `GeminiLive.open/respond`, sends real text turns and receives the Live audio transcription; audio is not persisted. The eval's Google text `reply` stand-in was not treated as Live.
  `spikes/backend/zj_spike/s3_runtime.py` は本番の `gateway.brief.build` と `GeminiLive.open/respond` を使い、実際のテキストのターンを送って Live の音声の文字起こしを受け取る。音声は永続化しない。評価用の Google テキスト `reply` の代用品を Live として扱ってはいない。
- `s3_narrate.py` uses the production `actions.narrate → Pipeline.call → ClaudeText` and records the raw model text and the final delivered text. Fixed fallbacks caused by timeouts or length filtering are counted separately and do not count as the model passing.
  `s3_narrate.py` は本番の `actions.narrate → Pipeline.call → ClaudeText` を使い、モデルの原文と最終的に配信したテキストを記録する。タイムアウトや長さのフィルタによる固定のフォールバックは別に数え、モデルの合格には数えない。
- `s3_action_runtime.py` separately retests narration with the production `eval_api.setup/act`, extraction, validation and an independent local database transaction; `Decision` or `Checked` are not hand-built. The checkpoint is explicitly set to `act.3`; it is still not a complete run from the opening to an ending.
  `s3_action_runtime.py` は別途、本番の `eval_api.setup/act`、抽出、検証、独立したローカルデータベースのトランザクションでナレーションを再テストする。`Decision` や `Checked` を手で組み立ててはいない。チェックポイントは明示的に `act.3` に設定しており、やはり開幕からエンディングまでの完全な流れではない。

Both are **conditional probes at a fixed moment**: they apply the original's beat effects according to the probe's `after`, and place the character being talked to and the traveler at the given location. They do not simulate navigation between acts, character reachability, database commits, continuous dialogue or gateway output monitoring; the default `act.1` is only the identity context of a fixed fixture. The explicit wedding regression uses `act.3`. The real reachable four-act flow and the 200 games are covered by another group of evals in R-1.

どちらも**固定時点の条件付きプローブ**：probe の `after` に従って原作のビートの効果を適用し、指定の場所に会話相手の登場人物と旅人を置く。幕間の移動、登場人物への到達可能性、データベースのコミット、連続した会話、ゲートウェイの出力監視はシミュレーションしていない。デフォルトの `act.1` は固定フィクスチャの身元コンテキストにすぎない。明示的な婚礼の回帰テストは `act.3` を使う。四幕の実際に到達可能な流れと 200 局は、R-1 の別の評価群が担当する。

After the final fix, the Live context and the scoring context export the character's current persona, knowledge set, restricted first-hand facts and events that have not happened from the same `SimState`; the existing s092.3 dual-judge method is unchanged. After the model flags something, a separate agent reading is still needed, and the original verdicts are neither overwritten nor deleted. This is not human blind-labeling calibration, and it cannot guarantee that no utterance will ever leak.

最終修正後、Live と採点のコンテキストは同じ `SimState` から、登場人物の現在の人物設定、知っていることの集合、制限された実体験の事実、まだ起きていない出来事を導出する。既存の s092.3 の二重判定法は変えていない。モデルがフラグを立てた後は、別途 agent による読み込みが必要で、元の判定は上書きも削除もしない。これは人間のブラインドラベリングによるキャリブレーションではなく、どんな発話でも絶対に漏れないと保証するものでもない。

## Fixes / 修正

1. The production Live prompt now includes the rules on hearsay, other people's inner thoughts and relative dates that the existing text prompt already had. `brief.situation_facts` adds the first-hand moment (「今朝、昨日」 and so on) only to facts that have passed the knowledge and forgetting filters; a fact's `trueFrom` must correspond to a beat actually experienced. **The full `beat.summary` or `variant.summary` is not passed**: the original's narration may say in advance that the rain lasts until the next day, or spell out other people's inner thoughts, and that cannot be treated as known to the current character. Beats freely rewritten without an established variant get no summary of the original. The scoring `lived` uses the same safe fact projection directly.
   本番の Live プロンプトに、既存のテキストプロンプトにある伝聞、他人の内心、相対的な日付のルールを補った。`brief.situation_facts` は、知識と忘却のフィルタを通過した事実にだけ実体験の時点（「今朝、昨日」など）を補う。事実の `trueFrom` は実際に体験したビートに対応していなければならない。**完全な `beat.summary` や `variant.summary` は渡さない**：原作の語りは雨が翌日まで続くことを先に述べたり、他人の内心を書いたりすることがあり、それを現在の登場人物が知っているものとして扱えない。既定の変種がなく自由に書き換えたビートには、原作の要約を補わない。採点の `lived` は同じ安全な事実の投影をそのまま使う。
2. The narration prompt states clearly that "partial" only means the current action was not fully completed, and must not roll back beats that have already happened. The narration request adds the defined concrete action intent and the summaries of candidates that passed validation, excluding rejected candidates, so that a vague `help` is not interpreted on its own as persuading or making an agreement.
   ナレーションのプロンプトで、「partial」は現在のアクションが完全には完了していないことだけを指し、すでに起きたビートを巻き戻してはならないと明記した。ナレーションのリクエストに、定義済みの具体的なアクションの意図と、検証を通過した候補の要約を加え、却下された候補は除外して、漠然とした `help` を説得や約束と勝手に解釈しないようにした。
3. The root task fixes the location projection: a leftover `var.<character>.location`, if present, is projected according to the authoritative `state.locations`, so that a character's location does not contradict itself within the same request.
   ルートのタスクで位置の投影を修正した：残っている `var.<登場人物>.location` があれば、正となる `state.locations` に従って投影し、同じリクエスト内で登場人物の位置が矛盾しないようにした。
4. Live and the text reply both restrict false premises: the player's 「this rain」 cannot stand in for what the character has seen with their own eyes; hypotheticals are always answered as hypotheticals, without supplying causes such as the bridge being washed away, and without asserting the opposite out of nowhere. Rain backed by first-hand experience may still be acknowledged.
   Live とテキストの reply の両方で誤った前提を制限した：プレイヤーの「この雨」は登場人物が自分の目で見たものの代わりにならない。仮定は常に仮定として答え、橋が流されたといった原因を補わず、根拠なく反対の事実を断言することもしない。実体験の根拠がある雨は引き続き認めてよい。
5. The new runner limits the number of questions and concurrency, and resuming from a checkpoint is bound to the question set, the actual prompt, the model configuration and the source fingerprint; empty transcriptions and failures do not count as passing. Review keeps the original prompt stored at generation time, verifies the original reply, prompt, state and world hash, and does not backfill a later prompt version as the generation version. When usage is missing, the ledger uses a conservative estimate, flagged separately, and it cannot all be called actual billed amounts. Each question records `requestId` and the status and duration of each Live and dual-judge attempt; a timeout retry still keeps the first cost, 429 stops the run, and a successful retry is not written as two successes. `--stop-file` lets the current call finish and then stops dispatching.
   新しいランナーは問題数と並列数を制限し、中断箇所からの再開は問題セット、実際のプロンプト、モデル設定、ソースのフィンガープリントに紐づける。空の文字起こしや失敗は合格に数えない。再審査は生成時に保存した元のプロンプトを残し、元の返答、プロンプト、状態、世界のハッシュを検証し、後のプロンプトのバージョンを生成時のバージョンとして遡って記入しない。使用量が欠けているときは、台帳は保守的な見積もりを使って別途マークし、すべてを実際の請求額とは呼べない。各問題で `requestId` と、Live と二重判定の各試行の状態と所要時間を記録する。タイムアウトのリトライでも最初の費用は残し、429 では停止し、成功したリトライを 2 回の成功として書かない。`--stop-file` を使うと、現在の呼び出しを終えてから配信を止められる。

## Review of the 497 old results and intermediate evidence from the fixes / 旧結果 497 件の再審査と修正の中間証拠

`runtime-full` actually completed 497/497 with no empty replies; under the existing E2 criteria there were 4 flags, plus 1 character-immersion flag. All 5 were read one by one:

`runtime-full` は実際に 497/497 を完了し、空の返答はなかった。既存の E2 の基準ではフラグが 4 件、ほかに登場人物の没入感に関するフラグが 1 件。5 件すべてを 1 件ずつ読んだ：

- The sister agreeing 「it's still raining」 at the wedding's 真昼: confirmed that a false premise was taken as a current fact; this is a target of this fix.
  婚礼の真昼に妹が「雨はまだ降っている」に同調した：誤った前提が現在の事実として扱われたと確認。今回の修正の対象。
- The king guessing that the hostage is doubting and regretting at this moment: kept as a knowledge-boundary risk; the dual-judge flag was not wiped into a pass.
  王が人質はこの時点で疑い、後悔していると推測した：知識の境界のリスクとして残す。二重判定のフラグを合格に書き換えてはいない。
- The king repeating the wedding rumor, and the friend expressing a wish to embrace at their reunion: no new secret or definite future event, leaning toward false positives; the original flags are kept.
  王が婚礼の噂を繰り返した件と、友が再会時に抱き合いたいという気持ちを述べた件：新たな秘密や確定した未来の出来事はなく、誤検出寄り。元のフラグは残す。
- The king repeating the player's 「物語」 and saying he does not know the ending: kept as an immersion observation; no ending was leaked.
  王がプレイヤーの「物語」を繰り返し、結末は知らないと言った件：没入感の観察として残す。結末は漏れていない。

These 497 generations and the old verdicts used the full beat summaries, and independent review found that the summaries themselves may contain how long the rain will last or other people's private motives. So the old statistics are only historical results and **cannot serve as proof that the final new version passes in full**; the generation-side source fingerprint is not backfilled, and the new context is not backfilled into old records.

この 497 件の生成と旧判定は完全なビートの要約を使っており、独立した再審査で、要約自体に未来の雨の続く長さや他人の私心が含まれうることがわかった。したがって旧統計は過去の結果にすぎず、**最終的な新バージョンの全量合格の証明にはできない**。生成側のソースのフィンガープリントを後から補うことはせず、新しいコンテキストを旧記録に遡って記入することもしない。

The first weather regression was planned at 84 items; after 14 were done we found that 「what if there were no bridge」 had been turned into a supplied cause, 「the bridge was washed away」, and stopped on our own to fix it; 1 more in-flight call was interrupted with an unknown result, and 69 were never started. The old replies, failures and any costs that may have been incurred are kept. Two subsequent 6-item pilots recorded, respectively, one recurrence of the weather problem and, after the examples were strengthened, no recurrence on the original question; they serve only as evidence of the fixing process, and we do not claim a pass based on repeatedly resampling the original question.

最初の天気の回帰テストは当初 84 件の予定だったが、14 件を終えた時点で「もし橋がなかったら」が「橋が流された」という原因の補足に変わっていることに気づき、自主的に止めて修正した。ほかに実行中だった呼び出し 1 件は中断され結果は不明、69 件は未開始。旧返答、失敗、発生した可能性のある費用は残す。その後の 6 件の pilot 2 回は、それぞれ天気の問題の再発 1 回と、例を補強した後に元の問題で再発しなかったことを記録した。これは修正過程の証拠としてのみ扱い、元の問題を繰り返しサンプリングしたことを根拠に合格とは主張しない。

The independent control set `premise-final-60` has completed 20 questions × 3 runs, 7 characters, 12 scenarios: the original 5 flags, wording variants of the weather and bridge hypotheticals, a positive control for actual rain, rain that has just started not being able to predict when it will stop, not knowing another person's private motives in the same scene, negative controls for characters in another place, and a historical control for the sister not knowing the deadline. The questions are saved in `spikes/backend/zj_spike/data/r1_premise_controls.json`. It used the tightened fact projection, a new directory and a new fingerprint; 60/60 completed, all 180 calls succeeded on the first try, with no empty transcriptions, missing usage or runtime errors, and every reply was read one by one.

独立した対照セット `premise-final-60` は 20 問 × 3 回、登場人物 7 人、シナリオ 12 を完了した：元のフラグ 5 件、天気と橋の仮定の言い回しの変種、実際に雨が降っている場合の陽性対照、降り始めたばかりの雨がいつ止むかは予知できないこと、同じ場面で他人の私心は知り得ないこと、別の場所にいる登場人物の陰性対照、妹が期限を知らないことの過去の対照。問題は `spikes/backend/zj_spike/data/r1_premise_controls.json` に保存している。引き締めた事実の投影、新しいディレクトリ、新しいフィンガープリントを使い、60/60 を完了。呼び出し 180 回はすべて初回で成功し、空の文字起こし、使用量の欠落、実行エラーはなく、すべての返答を 1 件ずつ読んだ。

The original and variant questions with the false weather premise, 12 runs in total, and the original and variant bridge hypotheticals, 9 runs in total, did not recur; the positive control with known rain was allowed to acknowledge the current rain, and with the stopping time unknown, the original's future duration was not disclosed. But the king's original question still had 2 E2 flags (items 47 and 48), which concretely supplied that the hostage is doubting his friend or feels abandoned; the old failures and original verdicts are kept in full. In addition, item 22's transcription ends at a fragment, and item 24 first says it rained during the wedding vows and then retracts itself by saying it does not know when the rain started; these are recorded as completeness and temporal-consistency observations respectively, not disguised as spoilers or as overall quality passing. There is no old-version comparison on the same question, so we cannot assert that the new rules caused them.

天気の誤った前提の元の問題と変種は計 12 回、橋の仮定の元の問題と変種は計 9 回で、再発しなかった。雨が既知の陽性対照では現在の雨を認めることが許され、止む時刻が未知の場合は原作の未来の持続時間を開示しなかった。しかし王の元の問題にはまだ E2 フラグが 2 件（第 47、48 件）あり、人質が友を疑っている、あるいは見捨てられたと思っていると具体的に補っていた。旧失敗と元の判定はすべて残す。ほかに、第 22 件は文字起こしが語句の途中で終わり、第 24 件は婚礼の誓いのときに雨が降っていたと言ってから、いつ降り始めたかは知らないと自ら撤回した。それぞれ完全性と時間の一貫性の観察として記録し、ネタバレや品質の全面合格に偽装しない。同じ問題の旧バージョンとの対照がないので、新しいルールが原因だとは断定できない。

## Limited fix for persona beliefs and knowledge permissions / 人物設定の信念と知識の権限に関する限定的な修正

The king's original persona, "believes he sees through other people", is in tension with the knowledge restrictions. This time all the original traits, goals, tone and sample lines are kept; one sentence is added after the Live / reply rules and after the Live persona section to draw the distinction: his view of others is his own belief, not evidence that he knows their actual inner thoughts; he may still express generalized pessimism about human nature, trust or distrust. Characters are not uniformly turned into mechanically answering "I don't know".

王の元の人物設定「他人を見抜いていると自負している」は、知識の制限と緊張関係にある。今回は元の traits、goals、口調、セリフのサンプルをすべて残し、Live / reply のルールと Live の人物設定の節の後に、区別を示す一文を加えた：他人に対する見方は自分の信念であり、相手の実際の内心を知っている証拠ではない。一般化された人間性への悲観、信頼や不信は引き続き表現してよい。登場人物を一律に機械的に「知らない」と答えるようにはしない。

The first isolated candidate, `king-final-15`, only strengthened the ban on specific unknown inner thoughts in the leading rules; after completing 5/15, item 3 clearly recurred, so it ended at the stop point and 10 were not started. The second candidate, `king-final-15-v2`, puts the belief/knowledge distinction after the persona and fully completed the pre-fixed 5 questions × 3 runs: the original question, a rewording, a positive control of the king's suspicion of human nature, a known start of the rain, and an unknown end of the rain. The questions are saved in `spikes/backend/zj_spike/data/r1_king_controls.json`.

最初の隔離した候補 `king-final-15` は、前置きのルールで具体的な未知の内心の禁止を強めただけで、5/15 を終えたところで第 3 件が明確に再発したため、停止点で終了し、10 件は未開始。2 番目の候補 `king-final-15-v2` は信念と知識の区別を人物設定の後に置き、事前に固定した 5 問 × 3 回を完全に終えた：元の問題、言い換え、王の人間性への猜疑の陽性対照、既知の雨の降り始め、未知の雨の止み時。問題は `spikes/backend/zj_spike/data/r1_king_controls.json` に保存している。

The second candidate completed 15/15, all 45 calls succeeded on the first try, and the existing s092.3 dual judge gave **0 flags**. Every item was read one by one, and an independent reviewer re-checked the first 6 against S-092 / S-095: **no confirmed E2, with 1 pragmatic dispute kept**. Item 1, aimed at the stonemason, 「Wouldn't he doubt his friend?」, can be read as the king's generalized rhetorical question, but may also make the player think of a specific doubt; it states no time, count, or that the doubt has happened, so it is not silently upgraded to a definite leak. Items 2, 4 and 6, concrete emotional guesses with hedging words, did not hit the list of unknown facts; they are recorded only as wording observations, and not all guesses are banned. The king's generalized-pessimism positive control was kept 3/3; the known start of the rain was acknowledged 3/3, and the unknown end of the rain was not predicted 3/3.

2 番目の候補は 15/15 を完了し、呼び出し 45 回はすべて初回で成功し、既存の s092.3 の二重判定は **0 flags**。すべてを 1 件ずつ読み、独立したレビュアーが S-092 / S-095 に照らして最初の 6 件を再審査した：**確認された E2 はなく、語用論上の争点 1 件を残す**。第 1 件の石工に向けた「友を疑わないとでもいうのか」は王の一般化された反語とも読めるが、プレイヤーに特定の疑いを連想させる可能性もある。時点、回数、すでに起きたことは言っていないので、黙って確定した漏洩に格上げはしない。第 2、4、6 件の、不確かさを示す語を伴う具体的な感情の推測は未知の事実のリストに当たらず、言い回しの観察としてだけ記録し、推測をすべて禁止することはしない。王の一般化された悲観の陽性対照は 3/3 で保たれ、既知の雨の降り始めは 3/3 で認め、未知の雨の止み時は 3/3 で予知しなかった。

This limited fix accepts the second candidate and does not keep repeating the original question until it reaches zero; **it does not mean reaching the 1% ceiling threshold for a formal release measured by independent question count**, and still less does it offset the 2 flags in the old 60 items or the first candidate's failure. Judge calibration, a full holdout question set and acceptance checks on how the voice sounds have still not been done.

今回の限定的な修正は 2 番目の候補を採用し、元の問題をゼロになるまで繰り返すことはしない。**独立した問題数で正式リリースの 1% 上限の閾値に達したことを意味せず**、まして旧 60 件のフラグ 2 件や最初の候補の失敗を相殺するものでもない。審査員のキャリブレーション、完全なホールドアウトの問題セット、音声の聞こえ方の受け入れ確認はまだ行っていない。

The candidates ran in a private copy of the source, isolated from the four-game eval running at the time; we verified that the 12 actually imported modules, the REPO path, the prompts and the source fingerprint all came from the copy, and the old generation fingerprints were not rewritten. `king-final-15-v2/isolation-verification.json`, `metadata.json` and `agent-review.json` keep the original evidence. After the user asked to stop real games and CI, we confirmed that the batch and workers had exited, lifted the freeze, and synced the three candidate files unchanged into the main tree; per-file hashes match the tested copy. The reply prompt version of the synthetic `b0-minimal.jsonl` was re-recorded; 9 brief tests, 2 replay tests and the brief Ruff check passed. Real models and the full CI were not restarted. The fallback of reviewing before voicing is in `spoiler-preflight-design.md` in the same directory; it is only a design record, not implemented and not counted as done.

候補は非公開のソースのコピーで実行し、当時実行中の 4 局の評価から隔離した。実際にインポートされた 12 モジュール、REPO パス、プロンプト、ソースのフィンガープリントがすべてコピー由来であることを確認し、旧生成のフィンガープリントは書き換えていない。`king-final-15-v2/isolation-verification.json`、`metadata.json`、`agent-review.json` に元の証拠を残している。ユーザーが実対局と CI の停止を求めた後、バッチと worker が終了したことを確認し、凍結を解除して、3 つの候補ファイルをそのままメインのツリーに同期した。ファイルごとのハッシュはテスト済みのコピーと一致する。合成の `b0-minimal.jsonl` の reply プロンプトのバージョンを記録し直した。brief のテスト 9 件、replay のテスト 2 件、brief の Ruff チェックに合格。実モデルと完全な CI は再開していない。審査してから発声する後手は同じディレクトリの `spoiler-preflight-design.md` にあり、設計記録にすぎず、未実装で完了にも数えない。

## Narration regression and fixture boundaries / ナレーションの回帰テストとフィクスチャの境界

All 66 items of `narrate-final` returned model text, with no fixed fallback. Reading them one by one found that item 42 still wrote that the 花婿 had not yet agreed although he already had; further checking found that this item is `partial + empty checked`, a combination the production `status_of` never produces. The original result is kept as a fixture stress test; this group is not written up as all passing, and we do not add more story summary to production requests on this basis. The runner has changed a generic `help` with no verified candidate to `refused`.

`narrate-final` の 66 件はすべてモデルのテキストを返し、固定のフォールバックはなかった。1 件ずつ読むと、第 42 件ではまだ、花婿がすでに承諾しているのにまだ頷いていないと書かれていた。さらに調べると、この件は `partial + 空の checked` で、本番の `status_of` ではこの組み合わせは生じない。元の結果はフィクスチャのストレステストとして残し、この群をすべて合格とは書かず、これを根拠に本番のリクエストにストーリーの要約を増やすこともしない。ランナーでは、検証済みの候補がない汎用の `help` を `refused` に変更した。

The production database regression `action-runtime` ran 12 times: the wedding-preparation button was actually `done` 3 times; generic help after he agreed, helping the king who is not present, and sending an expired preparation button after he agreed were each actually `refused` 3 times. All 12 had real model narration with no fixed fallback; neither the raw text nor the state before and after commit showed the 花婿 going back on his word. Actual `partial` was not covered, so we do not claim to cover all action outcomes on this basis. The earlier 3 runs of `narrate-groom-verified` were only prompt probes with hand-made candidates and are counted separately from these 12 real transactions.

本番データベースの回帰テスト `action-runtime` は計 12 回：婚礼の準備ボタンは 3 回とも実際に `done`。承諾後の汎用的な手伝い、その場にいない王を手伝う、承諾後に期限切れの準備ボタンを送る、はそれぞれ 3 回とも実際に `refused`。12 回すべてに実際のモデルのナレーションがあり、固定のフォールバックはなく、原文にもコミット前後の状態にも花婿が約束を翻すことは現れなかった。実際の `partial` はカバーしておらず、これを根拠にすべてのアクションの結果をカバーしたとは主張しない。それ以前の `narrate-groom-verified` の 3 回は手作りの候補によるプロンプトのプローブにすぎず、この 12 回の実際のトランザクションとは別に数える。

Independent review keeps one content observation: item 12 explains the refusal of the expired button with 「支度はもう調い」, but the state only makes clear that the 花婿 has agreed, and does not separately record that the preparations are all complete. This is a refusal reason supplied without direct state backing, so the 12 items cannot all be called content passes; it did not roll back the fact that he agreed, disclose a key future event, or change persistent state. This time we are not expanding the production narration context on this basis.

独立した再審査では内容の観察を 1 件残している：第 12 件は期限切れのボタンが拒否された理由を「支度はもう調い」と説明しているが、状態として明確なのは花婿が承諾したことだけで、準備がすべて整ったことは別に記録されていない。これは直接の状態の根拠がない拒否理由の補足であり、12 件をまとめて内容がすべて合格とは言えない。承諾済みの事実を巻き戻したり、未来の重要な出来事を開示したり、永続的な状態を変えたりはしていない。今回これを根拠に本番のナレーションのコンテキストを広げることはしない。

## Local rerun / ローカルでの再実行

Use the root workspace's real-model dependencies (`uv sync --all-packages --extra real`), and load credentials and model variables from the existing private configuration without writing them into the repo. Required: `ZJ_VERTEX_PROJECT`, `ZJ_VERTEX_LOCATION`, `ANTHROPIC_API_KEY`, `ZJ_CLAUDE_SONNET`, `ZJ_CLAUDE_HAIKU` and the cumulative `ZJ_CLAUDE_LEDGER`. First run without `--confirm` to see the bounded estimate, then execute; for this authorized task the per-item guard is $100 and the cumulative guard is $10,000, and neither is an infinite loop.

ルートの workspace の実モデル用の依存（`uv sync --all-packages --extra real`）を使い、既存の非公開設定から認証情報とモデルの変数を読み込み、リポジトリには書き込まない。必要なのは `ZJ_VERTEX_PROJECT`、`ZJ_VERTEX_LOCATION`、`ANTHROPIC_API_KEY`、`ZJ_CLAUDE_SONNET`、`ZJ_CLAUDE_HAIKU` と累積の `ZJ_CLAUDE_LEDGER`。まず `--confirm` を付けずに有限の見積もりを見てから実行する。承認された今回のタスクでは、1 項目の保護上限が $100、累積の保護上限が $10,000 で、いずれも無限ループではない。

```bash
PYTHONPATH=spikes/backend uv run --package zoujin-backend --extra real python -m zj_spike.s3_runtime \
  --out "$HOME/.zoujin/out/deferred-20261012/spoiler/new-run" --concurrency 4 --confirm

# Only review existing Live replies, without generating again; the source replies' state/brief must match.
# 既存の Live の返答を審査するだけで、再生成しない。元の返答の state/brief は一致している必要がある。
PYTHONPATH=spikes/backend uv run --package zoujin-backend --extra real python -m zj_spike.s3_runtime \
  --out "$HOME/.zoujin/out/deferred-20261012/spoiler/new-review" \
  --replies-from "$HOME/.zoujin/out/deferred-20261012/spoiler/new-run" --confirm

PYTHONPATH=spikes/backend uv run --package zoujin-backend --extra real python -m zj_spike.s3_narrate \
  --out "$HOME/.zoujin/out/deferred-20261012/spoiler/new-narrate" --confirm
```

The evidence root directory for this run is `$HOME/.zoujin/out/deferred-20261012/spoiler/`. `runtime-full` keeps the initial generations and original verdicts; it did not capture the complete generation-side source fingerprint, which is explicitly unknown and cannot be backfilled with later code hashes. Later review directories record the source/judge fingerprints and the hashes of the original reply files independently. `narrate` and `narrate-recheck` are evidence from the fixing process; the final restricted-fact-projection regression uses `premise-final-60`; the earlier `weather-fixed-84`, `premise-fixed-pilot` and `premise-fixed-pilot-v2` are all kept as intermediate evidence.

今回の証拠のルートディレクトリは `$HOME/.zoujin/out/deferred-20261012/spoiler/`。`runtime-full` は最初の生成と元の判定を残している。生成側の完全なソースのフィンガープリントは取得しておらず、この項目は明確に不明で、後のコードのハッシュで遡って埋めることはできない。その後の再審査ディレクトリは、ソース/審査員のフィンガープリントと元の返答ファイルのハッシュを独立して記録している。`narrate`、`narrate-recheck` は修正過程の証拠。最終的な制限付きの事実投影の回帰テストは `premise-final-60` を使う。それ以前の `weather-fixed-84`、`premise-fixed-pilot`、`premise-fixed-pilot-v2` はすべて中間証拠として残している。
