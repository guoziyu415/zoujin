#!/usr/bin/env bash
# 世界模型、评测集的校验和「生成物一致」（dev-plan 2.4）。从仓库根目录跑：
#   bash .github/scripts/check_world.sh
# 重新生成以后 git diff 必须为空：生成出来的文件不能手改，改编写源再重跑。
# W-1 把 reference/ 整理成包、E-0 接上评测运行器以后，这里改调包里的入口。
set -euo pipefail

PY="${PYTHON:-python3}"
W=worlds/hashire-merosu/1.0.0-draft
REF=packages/worldsim/reference

echo "== 世界模型：build_world（含 23 个情景 + 原作 = 24 次推演）"
"$PY" -I "$REF/build_world.py" --src "$W/world.src.json" \
  --text worlds/hashire-merosu/sources/melos_plain.txt --out "$W/world.json" \
  --report "$W/report.md" --scenarios "$W/scenarios.json"

echo "== 世界模型：评审表"
"$PY" -I "$REF/review_sheet.py" --world "$W/world.json" --out "$W/REVIEW.md"

echo "== 评测种子：重新生成"
"$PY" -I evals/gen_seeds.py evals/seeds

echo "== 评测种子：check_evals"
"$PY" -I "$REF/check_evals.py" --world "$W/world.json" --scenarios "$W/scenarios.json" \
  --cases evals/seeds --personas evals/personas.json

echo "== 防剧透探针：重新生成和 check_probes"
# gen_probes.py 和 s2_check.py 按项目文件夹的旧布局找 worldsim（data/spikes/pipeline），
# 这里用 PYTHONPATH 指到 reference/，所以这两条不加 -I（W-1 以后改成装好的包）。
PYTHONPATH="$REF" "$PY" evals/gen_probes.py evals/probes/s3_spoiler_probes.json
"$PY" -I "$REF/check_probes.py" --world "$W/world.json" --probes evals/probes/s3_spoiler_probes.json

echo "== 安全样本：重新生成"
"$PY" -I evals/gen_selfharm.py evals/safety/s4_selfharm.jsonl
"$PY" -I evals/gen_selfharm_holdout.py evals/safety/s4_selfharm_holdout.jsonl --public evals/safety/s4_selfharm.jsonl

echo "== S-2 公开样例：重新生成"
PYTHONPATH="$REF" "$PY" evals/gen_s2_dev.py evals/s2/s2_dev.jsonl

echo "== 生成物一致"
if ! git diff --exit-code --stat -- worlds evals; then
  echo "重新生成以后和仓库里的不一样：生成出来的文件被手改过，或者改了编写源没重跑。" >&2
  git diff -- worlds evals | head -200 >&2
  exit 1
fi
echo "生成物一致"
