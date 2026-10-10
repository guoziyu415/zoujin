#!/usr/bin/env bash
# One command for the Syracuse plaza (F-2): textures -> Blender scene -> sky -> lightmap bake -> encode -> pack -> check.
#   assets/pipeline/plaza/build.sh [final|draft] [out_dir]
# final (default): 2048 lightmaps, 30-40 min on 4 cores; writes assets/scenes/syracuse-square/build/ and refreshes
#   the committed manifest assets/scenes/syracuse-square/scene.json.
# draft: 512 lightmaps, about 1 min of baking; writes only out_dir (CI uses this to prove the pipeline still runs).
# Needs: BPY_PYTHON = a Python 3.13 with bpy 5.2, numpy and pillow (default python3); `pnpm install` done.
# Optional: PLAZA_OUT = work dir (default: a new temp dir), PLAZA_SCANS = dir of CC0 scans that replace the
# placeholder textures (<key>_<kind>.png|jpg, see placeholder_tex.py).
set -euo pipefail
Q="${1:-final}"
HERE="$(cd "$(dirname "$0")" && pwd)"
SCENE="$(cd "$HERE/../../scenes/syracuse-square" && pwd)"
OUT="${2:-$SCENE/build}"
PY="${BPY_PYTHON:-python3}"
export PLAZA_OUT="${PLAZA_OUT:-$(mktemp -d)}"
case "$Q" in final | draft) ;; *) echo "quality must be final or draft" >&2; exit 2 ;; esac
echo "work dir $PLAZA_OUT, output $OUT ($Q)"

step() { echo "== $1"; }
step "textures"; "$PY" -I "$HERE/placeholder_tex.py" "$PLAZA_OUT/tex" ${PLAZA_SCANS:+"$PLAZA_SCANS"}
step "scene";    (cd "$PLAZA_OUT" && "$PY" "$HERE/build_plaza.py")
step "sky";      (cd "$PLAZA_OUT" && "$PY" "$HERE/sky.py")
step "bake";     (cd "$PLAZA_OUT" && "$PY" "$HERE/bake.py" -- "$Q")
step "encode";   "$PY" "$HERE/encode.py"
step "pack";     node "$HERE/pack_scene.mjs" "$PLAZA_OUT" "$SCENE/layout.json" "$OUT"
step "check";    node "$HERE/check_scene.mjs" "$OUT" "$SCENE/layout.json"
if [ "$Q" = final ] && [ "$OUT" = "$SCENE/build" ]; then
  cp "$OUT/scene.json" "$SCENE/scene.json"
  echo "refreshed $SCENE/scene.json"
fi
