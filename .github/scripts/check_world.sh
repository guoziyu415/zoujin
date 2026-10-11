#!/usr/bin/env bash
# 世界模型、评测集的校验和「生成物一致」（dev-plan 2.4）。从仓库根目录跑：
#   bash .github/scripts/check_world.sh
# 重新生成以后 git diff 必须为空：生成出来的文件不能手改，改编写源再重跑。
# 工具从 W-1 的包 zoujin_worldsim import 推演规则，要用装了 workspace 的 Python（先 uv sync）。
# E-0 接上评测运行器以后，这里改调包里的入口。
set -euo pipefail

PY="${PYTHON:-.venv/bin/python}"
W=worlds/hashire-merosu/1.0.0-draft
REF=packages/worldsim/reference

echo "== 世界模型：build_world（含 23 个情景 + 原作 = 24 次推演）"
"$PY" -I "$REF/build_world.py" --src "$W/world.src.json" \
  --text worlds/hashire-merosu/sources/melos_plain.txt --out "$W/world.json" \
  --report "$W/report.md" --scenarios "$W/scenarios.json"

echo "== 切片版世界模型（S-077）：从完整版生成，再 build_world（情景同完整版）"
S=worlds/hashire-merosu/1.0.0-slice
"$PY" -I "$S/make_slice.py"
"$PY" -I "$REF/build_world.py" --src "$S/world.src.json" \
  --text worlds/hashire-merosu/sources/melos_plain.txt --out "$S/world.json" \
  --report "$S/report.md" --scenarios "$W/scenarios.json"

echo "== 世界模型：评审表"
"$PY" -I "$REF/review_sheet.py" --world "$W/world.json" --out "$W/REVIEW.md"

echo "== 评测种子：重新生成"
"$PY" -I evals/gen_seeds.py evals/seeds

echo "== 评测种子：check_evals"
"$PY" -I "$REF/check_evals.py" --world "$W/world.json" --scenarios "$W/scenarios.json" \
  --cases evals/seeds --personas evals/personas.json

echo "== 第二〜四幕的用例和画像（清单第 14、15 步，evals/acts/actN）：重新生成和 check_evals"
for d in evals/acts/act*/; do
  "$PY" -I "$d/cases.py"
  if compgen -G "$d/E*.jsonl" > /dev/null; then
    "$PY" -I "$REF/check_evals.py" --world "$W/world.json" --scenarios "$W/scenarios.json" --cases "$d" \
      --personas evals/personas.json evals/acts/act*/personas.json
  fi
done

echo "== 切片用例（S-077 ⑨）：重新生成和 check_evals（切片版世界模型，模拟局 E7-101〜110 用同一份画像）"
"$PY" -I evals/gen_slice.py evals/slice
"$PY" -I "$REF/check_evals.py" --world "$S/world.json" --scenarios "$W/scenarios.json" --cases evals/slice \
  --personas evals/personas.json

echo "== 防剧透探针：重新生成和 check_probes"
"$PY" -I evals/gen_probes.py evals/probes/s3_spoiler_probes.json
"$PY" -I "$REF/check_probes.py" --world "$W/world.json" --probes evals/probes/s3_spoiler_probes.json
"$PY" -I evals/gen_probes.py evals/probes/s3_spoiler_probes_2.json --set 2
"$PY" -I "$REF/check_probes.py" --world "$W/world.json" --probes evals/probes/s3_spoiler_probes_2.json \
  --existing evals/probes/s3_spoiler_probes.json --existing spikes/backend/zj_spike/data/s3_scenarios.json
"$PY" -I evals/gen_probe_knows.py evals/probes/s3_probe_knows.json

echo "== 安全样本：重新生成"
"$PY" -I evals/gen_selfharm.py evals/safety/s4_selfharm.jsonl
"$PY" -I evals/gen_selfharm_holdout.py evals/safety/s4_selfharm_holdout.jsonl --public evals/safety/s4_selfharm.jsonl

echo "== S-2 公开样例：重新生成"
"$PY" -I evals/gen_s2_dev.py evals/s2/s2_dev.jsonl

echo "== worldsim 的黄金文件：用参考实现重新生成"
"$PY" -I packages/worldsim/tests/golden/gen_golden.py

echo "== 生成物一致"
GENERATED=(worlds evals packages/worldsim/tests/golden)
if ! git diff --exit-code --stat -- "${GENERATED[@]}"; then
  echo "重新生成以后和仓库里的不一样：生成出来的文件被手改过，或者改了编写源没重跑。" >&2
  git diff -- "${GENERATED[@]}" | head -200 >&2
  exit 1
fi
echo "生成物一致"
