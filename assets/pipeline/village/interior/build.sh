#!/usr/bin/env bash
# One command for the room inside Melos's house (F-11 range 1, 6): the village's sub-pack village-interior.
#   assets/pipeline/village/interior/build.sh [final|draft] [out_dir]
# textures (../../plaza/placeholder_tex.py), the 11:00 sky (../../plaza/sky.py, for the day set), interior.py (the room,
# its lightmap layout, the day and feast bakes, the export), pack_interior.mjs (interior.glb, KTX2, pack.json).
# final (default): writes assets/scenes/village-interior/build/ and refreshes the committed pack.json.
# draft: 128 lightmaps, few samples; writes only out_dir/village-interior/ (proves the pipeline runs).
# Needs: BPY_PYTHON = a Python 3.13 with bpy 5.2, numpy and pillow (default python3); `pnpm install` done in
# assets/pipeline. Optional: PLAZA_OUT = work dir (default: a new temp dir).
set -euo pipefail
Q="${1:-final}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PLAZA="$(cd "$HERE/../../plaza" && pwd)"
SCENES="$(cd "$HERE/../../../scenes" && pwd)"
OUT="${2:-}"
PY="${BPY_PYTHON:-python3}"
WORK="${PLAZA_OUT:-$(mktemp -d)}"
PACK=village-interior
case "$Q" in final | draft) ;; *) echo "quality must be final or draft" >&2; exit 2 ;; esac
DEST="${OUT:+$OUT/$PACK}"
DEST="${DEST:-$SCENES/$PACK/build}"
echo "work dir $WORK, output $DEST ($Q)"
export PLAZA_OUT="$WORK" SCENE_ROT_DEG=0 SCENE_MINUS_X_AZ=270   # the village's frame: plan +x east, no rotation
export PLAZA_BAKE_MINUTE=660 E_SKY=1.1   # the day set's sky: 11:00, clear (Melos asleep from 10:30)

step() { echo "== $1"; }
step "textures"; "$PY" -I "$PLAZA/placeholder_tex.py" "$WORK/tex"
step "sky";      (cd "$WORK" && "$PY" "$PLAZA/sky.py")
step "room";     (cd "$WORK" && "$PY" "$HERE/interior.py" -- "$Q")
step "pack";     node "$HERE/pack_interior.mjs" "$WORK" "$DEST"

if [ "$Q" = final ] && [ -z "$OUT" ]; then
  mkdir -p "$SCENES/$PACK"
  cp "$DEST/pack.json" "$SCENES/$PACK/pack.json"
  echo "refreshed $SCENES/$PACK/pack.json"
fi
