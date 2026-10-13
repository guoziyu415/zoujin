#!/usr/bin/env bash
# Checks for the world model and eval sets, plus "generated files match" (dev-plan 2.4). Run from the repo root:
# 世界モデルと評価セットの検査、および「生成物が一致する」の確認（dev-plan 2.4）。リポジトリのルートから実行：
#   bash .github/scripts/check_world.sh
# After regenerating, git diff must be empty: generated files must not be hand-edited; change the source and rerun.
# 再生成後の git diff は空でなければならない：生成物は手で編集せず、編集元を変えて再実行する。
# The tools import the simulation rules from W-1's package zoujin_worldsim, so use a Python with the workspace installed (run uv sync first).
# ツールは W-1 のパッケージ zoujin_worldsim からシミュレーションのルールを import するので、workspace をインストールした Python を使う（先に uv sync）。
# Once E-0 hooks up the eval runner, this will call the package's entry point instead.
# E-0 で評価ランナーがつながったら、ここはパッケージのエントリポイントを呼ぶように変える。
set -euo pipefail

PY="${PYTHON:-.venv/bin/python}"
W=worlds/hashire-merosu/1.0.0-draft
REF=packages/worldsim/reference

echo "== World model: build_world (23 scenarios + the original = 24 simulations) / 世界モデル：build_world（シナリオ 23 本 + 原作 = シミュレーション 24 回）"
"$PY" -I "$REF/build_world.py" --src "$W/world.src.json" \
  --text worlds/hashire-merosu/sources/melos_plain.txt --out "$W/world.json" \
  --report "$W/report.md" --scenarios "$W/scenarios.json"

echo "== Slice world model (S-077): generate from the full version, then build_world (same scenarios as the full version) / スライス版世界モデル（S-077）：完全版から生成し、build_world（シナリオは完全版と同じ）"
S=worlds/hashire-merosu/1.0.0-slice
"$PY" -I "$S/make_slice.py"
"$PY" -I "$REF/build_world.py" --src "$S/world.src.json" \
  --text worlds/hashire-merosu/sources/melos_plain.txt --out "$S/world.json" \
  --report "$S/report.md" --scenarios "$W/scenarios.json"

echo "== World model: review sheet / 世界モデル：レビューシート"
"$PY" -I "$REF/review_sheet.py" --world "$W/world.json" --out "$W/REVIEW.md"

echo "== Eval seeds: regenerate / 評価シード：再生成"
"$PY" -I evals/gen_seeds.py evals/seeds

echo "== Eval seeds: check_evals / 評価シード：check_evals"
"$PY" -I "$REF/check_evals.py" --world "$W/world.json" --scenarios "$W/scenarios.json" \
  --cases evals/seeds --personas evals/personas.json

echo "== Cases and personas for acts 2-4 (checklist steps 14, 15; evals/acts/actN): regenerate and check_evals / 第二〜四幕のケースとペルソナ（チェックリスト手順 14、15、evals/acts/actN）：再生成と check_evals"
for d in evals/acts/act*/; do
  "$PY" -I "$d/cases.py"
  if compgen -G "$d/E*.jsonl" > /dev/null; then
    "$PY" -I "$REF/check_evals.py" --world "$W/world.json" --scenarios "$W/scenarios.json" --cases "$d" \
      --personas evals/personas.json evals/acts/act*/personas.json
  fi
done

echo "== Slice cases (S-077 ⑨): regenerate and check_evals (slice world model; simulated runs E7-101-110 use the same personas) / スライスのケース（S-077 ⑨）：再生成と check_evals（スライス版世界モデル、模擬プレイ E7-101〜110 は同じペルソナを使う）"
"$PY" -I evals/gen_slice.py evals/slice
"$PY" -I "$REF/check_evals.py" --world "$S/world.json" --scenarios "$W/scenarios.json" --cases evals/slice \
  --personas evals/personas.json

echo "== Anti-spoiler probes: regenerate and check_probes / ネタバレ防止プローブ：再生成と check_probes"
"$PY" -I evals/gen_probes.py evals/probes/s3_spoiler_probes.json
"$PY" -I "$REF/check_probes.py" --world "$W/world.json" --probes evals/probes/s3_spoiler_probes.json
"$PY" -I evals/gen_probes.py evals/probes/s3_spoiler_probes_2.json --set 2
"$PY" -I "$REF/check_probes.py" --world "$W/world.json" --probes evals/probes/s3_spoiler_probes_2.json \
  --existing evals/probes/s3_spoiler_probes.json --existing spikes/backend/zj_spike/data/s3_scenarios.json
"$PY" -I evals/gen_probe_knows.py evals/probes/s3_probe_knows.json

echo "== Safety samples: regenerate / 安全性サンプル：再生成"
"$PY" -I evals/gen_selfharm.py evals/safety/s4_selfharm.jsonl
"$PY" -I evals/gen_selfharm_holdout.py evals/safety/s4_selfharm_holdout.jsonl --public evals/safety/s4_selfharm.jsonl

echo "== S-2 public samples: regenerate / S-2 公開サンプル：再生成"
"$PY" -I evals/gen_s2_dev.py evals/s2/s2_dev.jsonl

echo "== worldsim golden files: regenerate with the reference implementation / worldsim のゴールデンファイル：参照実装で再生成"
"$PY" -I packages/worldsim/tests/golden/gen_golden.py

echo "== Generated files match / 生成物の一致"
GENERATED=(worlds evals packages/worldsim/tests/golden)
if ! git diff --exit-code --stat -- "${GENERATED[@]}"; then
  echo "After regenerating, the files differ from the repo: generated files were hand-edited, or a source was changed without rerunning. / 再生成後にリポジトリの内容と一致しない：生成物が手で編集されたか、編集元を変えたのに再実行していない。" >&2
  git diff -- "${GENERATED[@]}" | head -200 >&2
  exit 1
fi
echo "Generated files match / 生成物が一致"
