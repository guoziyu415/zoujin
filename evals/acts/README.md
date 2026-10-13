# Cases and personas for Acts 2-4 (checklist steps 14, 15) / 第二〜四幕のケースとペルソナ（チェックリスト第 14、15 ステップ）

Act 1 lives in `evals/seeds` (authoring source `evals/gen_seeds.py`, data engineering). Acts 2, 3 and 4 each have one directory, each written by one thread, and no thread edits another's directory:

第一幕は `evals/seeds` にある（編集元は `evals/gen_seeds.py`、データエンジニアリング）。第二、三、四幕にはそれぞれ 1 つのディレクトリがあり、それぞれ 1 つのスレッドが書く。他のスレッドのディレクトリは編集しない。

| Directory / ディレクトリ | Act / 幕 | Case ID / ケース ID | Persona ID / ペルソナ ID |
|---|---|---|---|
| `act2/` | Act 2「その夜」(t 1440〜2280: night road, river, the watchful royal city) / 第二幕「その夜」（t 1440〜2280：夜道、川、寝ずの番の王城） | `E1-201`〜`E8-299` | `persona.a2-…` |
| `act3/` | Act 3「村の二日」(t 1980〜4900: village, wedding, heavy rain; the hostage in the city) / 第三幕「村の二日」（t 1980〜4900：村、婚礼、大雨；市中の人質） | `E1-301`〜`E8-399` | `persona.a3-…` |
| `act4/` | Act 4「三日目」(t 4590〜5520: river, pass, spring, field road, execution ground) / 第四幕「三日目」（t 4590〜5520：川、峠、泉、野の道、刑場） | `E1-401`〜`E8-499` | `persona.a4-…` |

- Only edit `cases.py` in your own directory: `CASES` (cases, written like `gen_seeds.py`, helpers in `helpers.py`) and `PERSONAS` (simulated-session personas, same format as `evals/personas.json`: id, role, goal, style). `E*.jsonl` and `personas.json` are generated outputs.
  自分のディレクトリの `cases.py` だけを編集する：`CASES`（ケース。書き方は `gen_seeds.py` と同じ、helpers は `helpers.py`）と `PERSONAS`（シミュレーションセッションのペルソナ。形式は `evals/personas.json` と同じ：id、role、goal、style）。`E*.jsonl` と `personas.json` は生成物。
- Suites E1〜E8 mean the same as in `evals/README.md`. Write checkpoints as beats or moments within this act (`sc.canon@beat.NN`, `sc.canon@t=NNNN`); simulated sessions' `setup.persona` uses your own persona. The world model is the full version `worlds/hashire-merosu/1.0.0-draft` (contract 1.14, W-2).
  スイート E1〜E8 の意味は `evals/README.md` と同じ。チェックポイントはこの幕内のビートまたは時刻で書く（`sc.canon@beat.NN`、`sc.canon@t=NNNN`）。シミュレーションセッションの `setup.persona` は自分のペルソナを使う。世界モデルは完全版 `worlds/hashire-merosu/1.0.0-draft`（契約 1.14、W-2）。
- Validation (from the repo root, run `uv sync` first): `bash .github/scripts/check_world.sh`. It regenerates the three acts' files, runs check_evals against the full version, and finally requires the generated outputs to match what is committed: it passes only with 0 errors and "生成物一致" (generated outputs consistent).
  検証（リポジトリのルートから、先に `uv sync`）：`bash .github/scripts/check_world.sh`。三幕のファイルを再生成し、完全版に対して check_evals を実行し、最後に生成物がコミット済みのものと一致することを要求する：エラー 0 かつ「生成物一致」で初めて合格。
- D-040 is the earlier decision to pause real evaluation. On 2026-10-12 the user authorized resuming the real four-act text evaluation and B-22 simulation; judge calibration and pre-recorded voice remain on hold. For the bounded-batch commands and evidence-retention requirements, see the R1 section of `evals/README.md`.
  D-040 は実評価を一時停止した以前の決定。2026-10-12 にユーザーが実際の四幕テキスト評価と B-22 シミュレーションの再開を承認した。評価者のキャリブレーションと事前録音音声は引き続き保留。限定バッチのコマンドと証跡保存の要件は `evals/README.md` の R1 部分を参照。
- `helpers.write` explicitly sets `var.act.current=act.N` for non-persona cases. Checkpoint time advancement and original-work facts do not automatically choose the player's end-of-act destination for them; without this setting, Act 4 prompts would still see Act 1. This does not change character knowledge, causality or ending classification. Persona cases always play from the official opening.
  `helpers.write` は非ペルソナのケースに対して `var.act.current=act.N` を明示的に設定する。チェックポイントによる時間の進行と原作の事実は、幕末の行き先をプレイヤーに代わって自動的に選ぶことはない。この設定がないと、第四幕のプロンプトが第一幕のままになる。ここで人物の知識、因果、結末の分類は変わらない。ペルソナのケースは常に正式な開幕からプレイする。
