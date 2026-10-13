# M2 vertical slice model spend estimate (for dev-plan Z-8) / M2 垂直スライスのモデル費用見積もり（dev-plan Z-8 向け）

Data, 2026-10-11 (recomputed after D-028 and D-029). **All figures are estimates**; replace them with actual ledger numbers once M2's first batch has run. All tables come from [m2_budget.py](m2_budget.py) (`python3 -I m2_budget.py`); if you change an assumption, rerun it instead of editing numbers by hand.

データ担当、2026-10-11（D-028・D-029 以降に再計算）。**すべて〔推算〕**で、M2 の最初のバッチを実行したら台帳の実数に置き換える。表はすべて [m2_budget.py](m2_budget.py) で算出している（`python3 -I m2_budget.py`）。前提を変えたら再実行し、数字を手で直さない。

## Conclusions / 結論

1. **Google ledger: about $40 for M2, within the $50 cap (D-027).** Since D-028, Google is left with only Live voice, pre-recorded lines, the text replies that stand in for Live as characters in evals and simulated playthroughs (S-085 ①, kept at Google), and Model Armor (S-085 ②).

   **Google 台帳：M2 で約 $40、上限 50 ドル以内（D-027）。** D-028 以降、Google に残るのは Live の音声、事前収録セリフ、評価と模擬プレイで Live の代わりに登場人物を演じるテキスト応答（S-085 ①、Google に残す）、Model Armor（S-085 ②）だけ。
2. **Claude ledger: depends on which tier the narrator uses.** Sonnet throughout, per B-8, is about $121, over the $100 cap (D-029); moving extraction to Haiku is about $109, still over; moving both extraction and checks to Haiku is about $77, within the cap. Most of the money goes to the narrator in slice evals (about $48 on Sonnet) and the two kinds of simulated playthrough (about $33).

   **Claude 台帳：ナレーターにどのティアを使うか次第。** B-8 どおりすべて Sonnet なら約 $121 で、上限 100 ドル（D-029）を超える。抽出を Haiku にすると約 $109 でまだ超える。抽出とチェックの両方を Haiku にすると約 $77 で上限内。費用の大半はスライス評価のナレーター（Sonnet で約 $48）と 2 種類の模擬プレイ（約 $33）。
3. **So the tier for extraction and checks has to be decided within M2; it can't wait for M3.** Per B-8, S-2 and the first slice eval pass each run once more on Haiku (already counted in the tables; one slice eval pass costs about $8 on Sonnet and about $3.5 on Haiku). If Haiku is no worse, switch. If it is worse, keep Sonnet and run fewer of the later prompt-tuning and gate passes, or PM takes the actual ledger numbers to zg and asks for more.

   **だから抽出とチェックのティアは M2 のうちに決める必要があり、M3 まで待てない。** B-8 どおり、S-2 と最初のスライス評価をそれぞれ Haiku でもう 1 回ずつ実行する（表に計上済み。スライス評価 1 回分は Sonnet で約 $8、Haiku で約 $3.5）。Haiku で劣らなければ切り替える。劣るなら Sonnet のままにして、後のプロンプト調整と合格判定の回数を減らすか、PM が台帳の実数を持って zg に増額を頼む。
4. **M3 does not fit at the current way of running** (see "M3 extrapolation" below): the 200 playthroughs for diversity cost about $180–330 on Claude for the narrator and AI player, plus about $120 on Google for character replies. Before M3 starts, decide separately on the number and length of playthroughs, or on whether to switch the character replies in simulated playthroughs.

   **今の回し方では M3 は収まらない**（下の「M3 の外挿」）：多様性確認の 200 プレイで、ナレーターと AI プレイヤーに Claude 約 $180〜330、登場人物の応答に Google 約 $120。M3 開始前に、プレイ数とプレイの長さ、または模擬プレイの人物応答を切り替えるかどうかを別途決める。

## Basis / 算定基準

- **Unit prices**: Claude reads `evals/config/claude-prices.json` (moved into `packages/llm` after B-8; the repo holds only one copy); Google follows [pricing-2026-10-06.md](pricing-2026-10-06.md).
  **単価**：Claude は `evals/config/claude-prices.json` を読む（B-8 以降は `packages/llm` に移動。リポジトリ内に 1 部だけ）。Google は [pricing-2026-10-06.md](pricing-2026-10-06.md) による。
- **One call**: the tokens for each step on the B-8 card (the world-model prefix of about 17,000 tokens is cached; Haiku counts 30% more), written in `STEPS` in [cost_model.py](cost_model.py).
  **1 回の呼び出し**：B-8 カードの各ステップのトークン数（世界モデルのプレフィックス約 1.7 万トークンはキャッシュ経由、Haiku は 30% 多く数える）。[cost_model.py](cost_model.py) の `STEPS` に書いてある。
- **One full slice eval pass**: counted case by case from `evals/slice`. Which model steps each kind of step calls is written in `EVAL_MIX` in `m2_budget.py`, multiplied by each case's `runs`. Eval utterances mostly target the narrator, so the ratios are higher than in a whole playthrough: 0.8 extractions and 1.04 checks per line. One full pass is 39 cases, 169 runs, 252 steps and 125 scoring calls.
  **スライス評価 1 回分**：`evals/slice` をケースごとに数える。ステップの種類ごとにどのモデルステップを呼ぶかは `m2_budget.py` の `EVAL_MIX` に書き、各ケースの `runs` を掛ける。評価の発話はほとんどナレーターを狙うので、通しのプレイより比率が高い：1 発話あたり抽出 0.8 回、チェック 1.04 回。1 回分で 39 ケース、169 回、252 ステップ、採点 125 回。
- **Cache**: evals and simulated playthroughs run one after another, so the cache for a given prefix stays warm. Frequently called prompts (extraction, check, rewrite) write the cache once per full pass; infrequent ones (地の文 narration, end-of-act plan, world tick) write it once per case (the runs of one case go back to back); in simulated playthroughs the end-of-act plan and the ending write it once per playthrough. (Estimate: whether two prompts with different effort or thinking settings can share one cache will show up in `cache_read_input_tokens` in the B-8 mini test.)
  **キャッシュ**：評価と模擬プレイは 1 つずつ続けて実行するので、同じプレフィックスのキャッシュは温まったまま。よく呼ぶプロンプト（抽出、チェック、書き換え）は 1 回分につき 1 回キャッシュを書く。あまり呼ばないもの（地の文、幕末のプラン、世界の進行）はケースごとに 1 回書く（同じケースの複数回は続けて実行する）。模擬プレイでは幕末のプランとエンディングがプレイごとに 1 回書く。〔推算：effort や思考の設定が違う 2 つのプロンプトが 1 つのキャッシュを共有できるかは、B-8 の小テストで `cache_read_input_tokens` を見ればわかる〕
- **Scoring**: Opus 5.5 (effort low). Measured over 150 calibration calls: input 951–1,234 tokens, average 1,035; output (thinking can't be turned off and counts as output) average 102, max 220; about $0.006 per call. Slice transcripts are longer than the calibration samples, so assume 1,500 in and 150 out; via Batch that is about $0.005.
  **採点**：Opus 5.5（effort low）。キャリブレーションで 150 回実測：入力 951〜1,234 トークン、平均 1,035。出力（思考はオフにできず、出力に含まれる）平均 102、最大 220。1 回約 $0.006。スライスの対話記録はキャリブレーションのサンプルより長いので、入力 1,500・出力 150 で計算し、Batch 経由で約 $0.005。
- **Character replies** (Gemini 3.8 Flash, text mode): about $0.015 per call, converted from two S-068 measurements with the scoring cost taken out.
  **人物の応答**（Gemini 3.8 Flash テキストモード）：1 回約 $0.015。S-068 の 2 回の実測から換算し、採点分を差し引いた。
- **Before the tier is chosen**, follow B-8's order: tune the check prompt with Sonnet; run S-2 and the first slice eval pass once each on Sonnet and on Haiku. The three columns differ only in what comes after the choice: the 4.5 eval passes for prompt tuning and gating, and the two kinds of simulated playthrough.
  **ティア決定前**は B-8 の順序どおり：チェックプロンプトの調整は Sonnet で行い、S-2 と最初のスライス評価は Sonnet と Haiku で 1 回ずつ。3 列の違いは決定後の部分だけ：プロンプト調整と合格判定の 4.5 回分の評価、2 種類の模擬プレイ。
- Each ledger gets another 30% on top: reruns, retries triggered by time limits, and resuming after the Mac disconnects.
  各台帳にさらに 30% を上乗せ：再実行、時間制限による再試行、Mac の切断後の再開。

## Claude ledger (cap $100, D-029) / Claude 台帳（上限 100 ドル、D-029）

| Who / 担当 | Item / 項目 | Volume / 量 | Sonnet (per B-8) / Sonnet（B-8 どおり） | Extraction on Haiku / 抽出を Haiku に | Extraction and check on Haiku / 抽出・チェックを Haiku に |
|---|---|---|---:|---:|---:|
| Data / データ | Judge calibration / 審査員のキャリブレーション | 50 items × 3 already spent; after the J23 and J24 rubric change, retest 2 items × 3 / 50 件 × 3 回は支出済み。J23・J24 の細則変更後に 2 件 × 3 回を再テスト | $1.0 | $1.0 | $1.0 |
| Data / データ | S-2 holdout set (Sonnet, then one Haiku pass) / S-2 ホールドアウトセット（Sonnet、続けて Haiku で 1 回） | 50 items × 3, one pass per tier / 50 件 × 3 回、両ティアで 1 回ずつ | $2.9 | $2.9 | $2.9 |
| Data / データ | Slice eval: narrator / スライス評価：ナレーター | 39 cases; one full Sonnet pass, one Haiku comparison pass, 4.5 passes for prompt tuning and gating / 39 ケース。Sonnet で 1 回分、比較用に Haiku で 1 回分、プロンプト調整と合格判定で 4.5 回分 | $48.0 | $42.8 | $27.4 |
| Data / データ | Slice eval: scoring / スライス評価：採点 | 125 per pass × 6.5 passes, via Batch / 1 回分 125 回 × 6.5 回分、Batch 経由 | $3.7 | $3.7 | $3.7 |
| Data / データ | Persona simulated playthroughs / ペルソナ模擬プレイ | 11 personas × 2 playthroughs, about 15 turns each, including the AI player / 11 ペルソナ × 2 プレイ、1 プレイ約 15 ターン、AI プレイヤー込み | $16.4 | $14.6 | $10.3 |
| Data / データ | E1 jailbreak sample expansion / E1 脱獄サンプルの拡充 | Very small / ごく少量 | $1.0 | $1.0 | $1.0 |
| Backend / バックエンド | B-8 mini test / B-8 小テスト | 7 prompts × 20 calls (B-8) / 7 種のプロンプト × 20 回（B-8） | $1.0 | $1.0 | $1.0 |
| Backend / バックエンド | Check prompt tuning (before the tier is chosen, on Sonnet) / チェックプロンプトの調整（ティア決定前、Sonnet で） | 10 public items × 3 × 5 rounds / 公開の 10 件 × 3 回 × 5 ラウンド | $2.7 | $2.7 | $2.7 |
| Backend / バックエンド | S-5 simulated playthroughs / S-5 模擬プレイ | 10 playthroughs × 40 turns, including the AI player / 10 プレイ × 40 ターン、AI プレイヤー込み | $16.4 | $14.1 | $9.0 |
| | Subtotal / 小計 | | **$93** | **$84** | **$59** |
| | Plus 30% / 30% 上乗せ | | **about $121 / 約 $121** | **about $109 / 約 $109** | **about $77 / 約 $77** |

## Google ledger (cap $50, D-027) / Google 台帳（上限 50 ドル、D-027）

| Who / 担当 | Item / 項目 | Volume / 量 | Cost / 費用 |
|---|---|---|---:|
| Backend / バックエンド | B-6 pre-recorded lines / B-6 事前収録セリフ | D-027 | $0.2 |
| Data / データ | Slice eval: character replies / スライス評価：人物の応答 | 164 per pass × 6.5 passes / 1 回分 164 回 × 6.5 回分 | $16.0 |
| Data / データ | Persona simulated playthroughs: character replies / ペルソナ模擬プレイ：人物の応答 | 22 playthroughs × 15 turns / 22 プレイ × 15 ターン | $4.9 |
| Backend / バックエンド | S-5 simulated playthroughs: character replies / S-5 模擬プレイ：人物の応答 | 10 playthroughs × 40 turns / 10 プレイ × 40 ターン | $6.0 |
| Backend / バックエンド | Live self-test (a few internal playthroughs once the gateway is connected) / Live の自己テスト（ゲートウェイ接続後、内部で数プレイ） | 10 playthroughs × 20 minutes / 10 プレイ × 20 分 | $3.8 |
| Backend / バックエンド | Model Armor (once connected, second layer) / Model Armor（接続後、第 2 層） | Free up to 2 million tokens a month / 月 200 万トークンまで無料 | $0.0 |
| | Subtotal / 小計 | | **$31** |
| | Plus 30% / 30% 上乗せ | | **about $40 / 約 $40** |

The Live self-test is an estimated placeholder: once the backend gateway (B-5) is connected, play a few internal playthroughs with real voice. Model Armor (S-085 ②, still the second layer) is free for the first 2 million tokens each month and $0.10 per million tokens after that (Google's pricing page, checked 2026-10-11); evals and simulated playthroughs during development use a few hundred thousand tokens a month, so it counts as 0. The S-068 anti-spoiler retest finished on 10-10 (about $15, in the old spike's ledger); it came out of the earlier one-off $30 batch and does not count against D-027's $50.

Live の自己テストは推算の仮置き：バックエンドのゲートウェイ（B-5）がつながったら、内部で実際の声を使って数プレイ遊ぶ。Model Armor（S-085 ②、引き続き第 2 層）は毎月最初の 200 万トークンが無料で、その後は 100 万トークンあたり $0.10（Google の料金ページ、2026-10-11 確認）。開発期の評価と模擬プレイは月に数十万トークン程度なので 0 とする。S-068 のネタバレ防止の再テストは 10-10 に実行済み（約 $15、旧 spike の台帳）で、以前の単発の 30 ドル枠から出しており、D-027 の 50 ドルには含めない。

## M3 extrapolation (outside M2's two caps) / M3 の外挿（M2 の 2 つの上限には含めない）

| Item / 項目 | Volume / 量 | Ledger / 台帳 | Sonnet (per B-8) / Sonnet（B-8 どおり） | Extraction on Haiku / 抽出を Haiku に | Extraction and check on Haiku / 抽出・チェックを Haiku に |
|---|---|---|---:|---:|---:|
| Seeds: narrator and scoring / シード：ナレーターと採点 | 88 cases (E7 personas counted separately) × 2 passes, 295 scoring calls per pass / 88 ケース（E7 のペルソナは別計算）× 2 回分、採点は 1 回分 295 回 | Claude | $29 | $24 | $9 |
| Seeds: character replies / シード：人物の応答 | Same as above / 同上 | Google | $12 | $12 | $12 |
| 200-playthrough diversity: narrator and AI player / 200 プレイの多様性：ナレーターと AI プレイヤー | 200 playthroughs × 40 turns / 200 プレイ × 40 ターン | Claude | $328 | $282 | $180 |
| 200-playthrough diversity: character replies / 200 プレイの多様性：人物の応答 | 200 playthroughs × 40 turns / 200 プレイ × 40 ターン | Google | $120 | $120 | $120 |

If M2 uses its caps in full, about $100 of Claude budget remains, and no column fits 200 playthroughs. Options before M3 starts: run fewer playthroughs or shorten each one; run the whole narrator on Haiku (about $0.32 per playthrough, of which the Sonnet AI player is about $0.19; about $64 for 200, and less if the AI player also moves to Haiku); move the character replies in simulated playthroughs to Claude too (this departs from B-8's reason for keeping them at Google: the characters measured would no longer be the model players actually talk to, so they could only show the ending distribution, not tone or spoilers). PM decides with M2's actual numbers in hand.

M2 で上限を使い切ると Claude の枠は約 100 ドル残るが、どの列でも 200 プレイは収まらない。M3 開始前に取れる手：プレイ数を減らすか 1 プレイを短くする。ナレーターをすべて Haiku にする（1 プレイ約 $0.32、うち Sonnet の AI プレイヤーが約 $0.19。200 プレイで約 $64、AI プレイヤーも Haiku にすればさらに少ない）。模擬プレイの人物応答も Claude にする（B-8 が Google に残した理由から外れる：測る人物がプレイヤーが実際に話すモデルではなくなるので、エンディングの分布は見られても口調やネタバレは見られない）。PM が M2 の実数を持って決める。

## Compared with the 10-10 version / 10-10 版との比較

| Ledger / 台帳 | 10-10 (narrator on Google) / 10-10（ナレーターは Google） | 10-11 (after D-028) / 10-11（D-028 以降） |
|---|---:|---:|
| Google | about $85–95 / 約 $85〜95 | about $40 / 約 $40 |
| Claude | about $31 / 約 $31 | about $77–121 / 約 $77〜121 |

The narrator moved from Google to Claude, and the two ledgers' combined total is about the same; the increase on the Claude side is the narrator that used to be on the Google side. This version also sizes the extraction input by the world-model prefix measured in B-8 (about 17,000 tokens; it used to be 3,000, which was too low), and counts evals case by case from the slice cases (previously estimated as "about 230 turns").

ナレーターを Google から Claude に移したので、2 つの台帳の合計はほぼ同じ。Claude 側の増加分は、もともと Google 側にあったナレーターの分。さらにこの版では、抽出の入力を B-8 で測った世界モデルのプレフィックス（約 1.7 万トークン。以前は 3,000 で計算しており少なすぎた）で見積もり、評価はスライスのケースを 1 件ずつ数えた（以前は「約 230 ターン」で見積もり）。

## Recommendations / 提案

- Each ledger has its own cap, and both must be passed explicitly when running (`--max-google-usd 50`, `--max-claude-usd 100`); both accumulate across all runs. A run stops automatically at the cap, and stops at the first 429 (likewise Claude's 529); both can `--resume`.
  台帳ごとに上限があり、実行時は両方とも明示的に指定する（`--max-google-usd 50`、`--max-claude-usd 100`）。どちらもすべての実行を通して累計する。上限に達すると自動で止まり、最初の 429 で止まる（Claude の 529 も同様）。どちらも `--resume` できる。
- Both ledgers are recorded in the same ledger file on the Mac (`ZJ_LEDGER`, JSONL). Each line has `provider`, `use`, `kind`, `model` (for Claude, the tier name plus version, not the model ID), `usage`, `costUsd`, `at` and `item`. `use` is set by the path the call belongs to: narrator steps, safety classification, memory, ending, Live and pre-recorded lines are `product` (even when run inside an eval); the judge and the AI player are `eval`. S-5's per-playthrough cost adds up only `product`. The ledger records neither request or response content nor project IDs.
  2 つの台帳は Mac 上の同じ台帳ファイル（`ZJ_LEDGER`、JSONL）に記録する。各行に `provider`、`use`、`kind`、`model`（Claude はティア名とバージョンを書き、モデル ID は書かない）、`usage`、`costUsd`、`at`、`item` を持つ。`use` は呼び出しがどの経路に属するかで付ける：ナレーターの各ステップ、安全分類、記憶、エンディング、Live、事前収録セリフは `product`（評価内で実行しても同じ）、審査員と AI プレイヤーは `eval`。S-5 のプレイ単位のコストは `product` だけを合計する。台帳にはリクエストと応答の内容もプロジェクト ID も書かない。
- Run the cheap items first: judge calibration (done; actual spend about $0.93, agreement 148/150), the B-8 mini test (about $1), S-2 on both tiers (about $3), and the first slice eval pass on both tiers (about $12 plus scoring). Afterwards PM compares the actual ledger numbers with this table, then decides which tier extraction and checks use.
  安いものから先に実行する：審査員のキャリブレーション（実行済み、実費約 $0.93、一致率 148/150）、B-8 小テスト（約 $1）、S-2 の両ティア（約 $3）、最初のスライス評価の両ティア（約 $12 と採点）。終わったら PM が台帳の実数をこの表と照らし合わせ、抽出とチェックのティアを決める。
- Narrator calls in evals are not time-sensitive, so they could later go through Batch (half price). That needs the runner to send them in batches by step; decide whether it's worth it after E-0's live mode is connected.
  評価でのナレーター呼び出しは急がないので、将来は Batch（半額）にできる。ランナーがステップごとにまとめて送る必要があるので、E-0 の live がつながってから見合うかを判断する。
- Not handed to a model: self-harm samples are still written by hand and rechecked by UX (S-069); holdout samples are never used to tune prompts (the S-2 measurement on Haiku is the holdout set's second use, and both uses run frozen prompts).
  モデルに任せないもの：自傷サンプルは従来どおり手書きで、UX が見直す（S-069）。ホールドアウトサンプルはプロンプト調整に使わない（S-2 を Haiku で測る回はホールドアウトセットの 2 回目の使用で、2 回とも凍結したプロンプトを使う）。
- Every real model call in evals and simulated playthroughs is saved as a replay, scoring included, so CI won't have to spend money later.
  評価と模擬プレイの実モデル呼び出しはすべてリプレイとして保存し、採点も保存するので、以降の CI では費用がかからない。
