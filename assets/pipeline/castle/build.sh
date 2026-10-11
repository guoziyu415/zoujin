#!/usr/bin/env bash
# One command for the castle (F-14): scene.castle-throne's pack assets/scenes/castle-throne.
#   assets/pipeline/castle/build.sh [final|draft] [out_dir]
# Runs the plaza's steps (../plaza: sky, bake, encode, pack, check) with this scene's frame and light, then lamps.mjs
# adds the full lightmaps (the lamps' own light) and the lamp list to scene.json.
# final (default): writes assets/scenes/castle-throne/build/ and refreshes the committed scene.json.
# draft: 512 lightmaps; writes only out_dir/castle-throne/ (CI uses this to prove the pipeline still runs).
# Needs: BPY_PYTHON = a Python 3.13 with bpy 5.2, numpy and pillow (default python3); `pnpm install` done.
# Optional: PLAZA_OUT = work dir (default: a new temp dir), CASTLE_SCANS = dir of CC0 scans that replace the
# placeholder textures (<key>_<kind>.png|jpg, see castle_tex.py).
set -euo pipefail
Q="${1:-final}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PLAZA="$(cd "$HERE/../plaza" && pwd)"
SCENES="$(cd "$HERE/../../scenes" && pwd)"
OUT="${2:-}"
PY="${BPY_PYTHON:-python3}"
WORK="${PLAZA_OUT:-$(mktemp -d)}"
PACK=castle-throne
case "$Q" in final | draft) ;; *) echo "quality must be final or draft" >&2; exit 2 ;; esac
DEST="${OUT:+$OUT/$PACK}"
DEST="${DEST:-$SCENES/$PACK/build}"
echo "work dir $WORK, output $DEST ($Q)"

export SCENE_INPUTS="assets/pipeline/castle/build.sh,assets/pipeline/castle/castle_tex.py,assets/pipeline/plaza/placeholder_tex.py,assets/pipeline/common/bl.py,assets/pipeline/castle/build_castle.py,assets/pipeline/castle/lamps.mjs"
export SCENE_BUILD="assets/pipeline/castle/build.sh"
export SCENE_ROT_DEG=0 SCENE_MINUS_X_AZ=270   # plan +x = east, no rotation (castle.md 2)
export SCENE_STEM="$PACK" PLAZA_OUT="$WORK" CASTLE_LAYOUT="$SCENES/$PACK/layout.json"
# the night of the promise, 20:30 (beat.05): no sun in the bake (BAKE_SUN_E 0), a moonless sky drawn for the sun just
# under the horizon and scaled down to starlight; the lamps of layout.json are the light
export PLAZA_BAKE_MINUTE=1230 SKY_SUN_ELEV_DEG=-4 E_SKY=0.02 BAKE_SUN_E=0
export BAKE_RES=1024   # 58 x 28 m of ground; the hall's walls and floor are what is seen close

step() { echo "== $1"; }
step "textures"; "$PY" -I "$HERE/castle_tex.py" "$WORK/tex" ${CASTLE_SCANS:+"$CASTLE_SCANS"}
step "scene";  (cd "$WORK" && "$PY" "$HERE/build_castle.py")
step "sky";    (cd "$WORK" && "$PY" "$PLAZA/sky.py")
step "bake";   (cd "$WORK" && "$PY" "$PLAZA/bake.py" -- "$Q")
step "encode"; "$PY" "$PLAZA/encode.py"
step "pack";   node "$PLAZA/pack_scene.mjs" "$WORK" "$CASTLE_LAYOUT" "$DEST"
step "lamps";  node "$HERE/lamps.mjs" "$WORK" "$CASTLE_LAYOUT" "$DEST"
step "check";  node "$PLAZA/check_scene.mjs" "$DEST" "$CASTLE_LAYOUT"

if [ "$Q" = final ] && [ -z "$OUT" ]; then
  cp "$DEST/scene.json" "$SCENES/$PACK/scene.json"
  echo "refreshed $SCENES/$PACK/scene.json"
fi
