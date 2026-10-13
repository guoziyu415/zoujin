# B-6b Pre-recorded lines for the remaining characters and set-piece lines for the four acts / B-6b 残りの登場人物の事前収録セリフと 4 幕の固定演出のセリフ

| Item / 項目 | Content / 内容 |
|---|---|
| Card written by / カード作成 | Backend 2, 2026-10-11 (one page, no review, D-037) / バックエンド 2、2026-10-11（1 ページ、レビューなし、D-037） |
| Phase / フェーズ | `docs/pm/dev-plan.md` 0a, 0b step 7 "Pre-recorded lines for the remaining characters" (D-039) / `docs/pm/dev-plan.md` 0a、0b 第 7 ステップ「残りの登場人物の事前収録セリフ」（D-039） |
| Depends on / 依存 | B-6's (#82, #92, #160, #163) generation script `zoujin-voice`; #180 (the 6 lines for five characters, `--world`). The four acts' set pieces wait for data's full world model (W-2, step 13) / B-6（#82、#92、#160、#163）の生成スクリプト `zoujin-voice`。#180（5 人の 6 セリフ、`--world`）。4 幕の固定演出はデータの完全な世界モデル（W-2、第 13 ステップ）を待つ |
| Depended on by / 被依存 | B-18 (wiring the remaining 5 talkable characters into the narrator and voice, step 8): the manifest's `prerecorded` for these five characters; the unified evals at step 26 / B-18（残り 5 人の会話できる登場人物をナレーターと音声につなぐ、第 8 ステップ）：manifest の `prerecorded` をこの 5 人に与える。第 26 ステップのまとめての評価 |
| Execution / 実行 | Backend 2 writes the code; real generation happens only on zg's Mac (the Mac only generates content, it does not verify). It goes on the Google ledger and runs within the approved budget (D-034), with a per-item cap of $2; report the spend to PM / バックエンド 2 がコードを書く。本番の生成は zg の Mac だけで行う（Mac は内容を生成するだけで、検証はしない）。Google の台帳で、承認済みの枠内で実行する（D-034）。項目ごとの上限は $2。使った額を PM に報告する |

## What to do / やること

1. **The 6 lines for five characters** (the king, Selinuntius, the sister, the groom, Philostratus — 王、セリヌンティウス、妹、花婿、フィロストラトス; the table in ux-design 16.2, voices per D-025 and D-036):
   **5 人の登場人物の 6 セリフ**（王、セリヌンティウス、妹、花婿、フィロストラトス。ux-design 16.2 の表、声は D-025、D-036 に従う）：
   - The source file and generation plan are already in #180. On the Mac, run `--resume` on a copy of the run directory from the slice run (from #203 onward `--world` is not needed); it reads only these five characters' 30 lines and 10 ref lines (135 takes in all, read as written), and lines already read are not read again.
     ソースファイルと生成計画は #180 に既にある。Mac でスライスのときの実行ディレクトリのコピーを使って `--resume` を実行する（#203 以降は `--world` は不要）。この 5 人の 30 セリフと 10 の ref（合計 135 テイク、書かれたとおりに読む）だけを読み、読み終えたものは読み直さない。
   - Automatic checks follow backend-design 3.6 and the B-6 card. Before the real run, UX had already shortened the four aizuchi (相槌) of three morae or more to two morae (#202). The first real run ($0.2026, 49/58): Selinuntius's 「……そうか。」 exceeded 0.5 s and was changed to 「うむ。」; the groom's 「はあ。」「ええ。」, Philostratus's 「はい。」 and the king's 「……ほう。」 had a low pitch ratio (breathy voice), and the king's 「……聞こえぬ。」 did not match the fallback transcription, so these keys got the direction 「息を混ぜず、地声で」; only these lines are re-read (D-038).
     自動検査は backend-design 3.6 と B-6 のカードに従う。3 拍以上の相槌 4 つは、本番実行の前に UX が 2 拍に変えた（#202）。最初の本番実行（$0.2026、49/58）：セリヌンティウスの「……そうか。」が 0.5 秒を超えたので「うむ。」に変えた。花婿の「はあ。」「ええ。」、フィロストラトスの「はい。」、王の「……ほう。」は音高の比率が低く（息の混じった声）、王の「……聞こえぬ。」は補完の文字起こしと合わなかったので、これらのキーに「息を混ぜず、地声で」の演技指示を加えた。これらのセリフだけを読み直す（D-038）。
   - Loudness: the target loudness for these five characters is written into the source file from the free-conversation loudness measured on the refs; changing it only re-exports, without re-reading.
     ラウドネス：この 5 人の目標ラウドネスは ref で測った自由会話のラウドネスに従ってソースファイルに書く。変えても書き出し直すだけで、読み直さない。
2. **Recordings into the repo**: the release's m4a files and `voices.json` go into `assets/voice/hashire-merosu/`. `test_manifest`'s check is changed to compare against the world model written in the source file. In the slice, these five characters cannot be talked to, so the manifest still does not give them `prerecorded`. Once W-2 is merged, the source file's `world` changes to the full version, and the manifest gives all seven characters.
   **録音をリポジトリに入れる**：release の m4a と `voices.json` を `assets/voice/hashire-merosu/` に入れる。`test_manifest` の検査は、ソースファイルに書いた世界モデルと比べるように変える。スライスではこの 5 人と話せないので、manifest は引き続き彼らに `prerecorded` を与えない。W-2 がマージされたら、ソースファイルの `world` を完全版に変え、manifest は 7 人に与える。
3. **The four acts' set pieces**: once W-2 adds `setPieces` for the throne room (王座の間), the village and the journey home, the source file assigns voices to the new speakers (passersby other than the guards and the crowd follow the candidates in ux-design 16.1), with scene directions per UX's copy table (U-2). Run `--resume` with the same run directory, reading only the new lines.
   **4 幕の固定演出**：W-2 が王座の間、村、帰り道の `setPieces` を加えたら、ソースファイルで新しい話し手に声を割り当て（警吏と群衆以外の通行人は ux-design 16.1 の候補に従う）、場面の説明は UX の文言表（U-2）に従う。同じ実行ディレクトリで `--resume` を実行し、新しいセリフだけを読む。

## Out of scope / やらないこと

- Do not re-read the 28 lines the slice already passed (D-038).
  スライスで既に合格した 28 件は読み直さない（D-038）。
- Do not make a separate listening page, and do not wait for zg to listen (D-036, D-039). UX's numbers for length, loudness, pitch and speaking rate follow the lines in the B-6 card and are produced by the automatic checks.
  別に試聴ページは作らず、zg が聞くのも待たない（D-036、D-039）。UX が長さ、ラウドネス、音高、話す速さを測る数値は B-6 のカードの基準に従い、自動検査で出す。

## Done / 完了

- Step 7: the five characters' recordings and `voices.json` are merged into main, with all automatic checks passing.
  第 7 ステップ：5 人の録音と `voices.json` が main にマージされ、自動検査がすべて通る。
- The four acts' set pieces: once W-2 is merged, a separate PR is opened and merged into main.
  4 幕の固定演出：W-2 がマージされた後に別の PR を開き、main にマージする。
