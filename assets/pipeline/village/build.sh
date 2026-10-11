#!/usr/bin/env bash
# One command for the village (F-11): the pack scene.village (first visit: the clear day's light at 10:00), its
# share of the roadside pack road-common.
#   assets/pipeline/village/build.sh [final|draft] [out_dir]
# Runs the plaza's steps (../plaza: sky, bake, encode, pack, check) with this scene's frame and light, the way the road
# does (../road/build.sh); between the bake and the pack merge_inst.mjs adds the instanced wheat, sheaves, vines and
# sheep; then ../common/roadside.mjs moves the shared textures into road-common, and check_village.mjs checks it all.
# final (default): writes assets/scenes/village/build/ (and road-common/build/) and refreshes the committed manifests
#   (village/scene.json, road-common/pack.json).
# draft: 512 lightmaps; writes only out_dir/<pack>/ (CI uses this to prove the pipeline still runs and reproduces).
# Needs: BPY_PYTHON = a Python 3.13 with bpy 5.2, numpy and pillow (default python3); `pnpm install` done.
# Optional: PLAZA_OUT = work dir (default: a new temp dir), ROAD_SCANS = dir of CC0 scans that replace the
# placeholder textures (<key>_<kind>.png|jpg, see ../common/road_tex.py).
set -euo pipefail
Q="${1:-final}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PLAZA="$(cd "$HERE/../plaza" && pwd)"
COMMON="$(cd "$HERE/../common" && pwd)"
SCENES="$(cd "$HERE/../../scenes" && pwd)"
OUT="${2:-}"
PY="${BPY_PYTHON:-python3}"
WORK="${PLAZA_OUT:-$(mktemp -d)}"
case "$Q" in final | draft) ;; *) echo "quality must be final or draft" >&2; exit 2 ;; esac
dest() { if [ -n "$OUT" ]; then echo "$OUT/$1"; else echo "$SCENES/$1/build"; fi; }
PACK=village
echo "work dir $WORK, output ${OUT:-$SCENES/<pack>/build} ($Q)"

# what pack_scene.mjs records as this scene's own inputs (in place of the plaza's build.sh and scene script)
export SCENE_INPUTS="assets/pipeline/village/build.sh,assets/pipeline/common/road_tex.py,assets/pipeline/plaza/placeholder_tex.py,assets/pipeline/common/bl.py,assets/pipeline/village/build_village.py,assets/pipeline/village/merge_inst.mjs,assets/pipeline/common/roadside.mjs,assets/pipeline/common/small_tex.mjs,assets/pipeline/village/zones.mjs"
export SCENE_BUILD="assets/pipeline/village/build.sh"
export SCENE_ROT_DEG=0 SCENE_MINUS_X_AZ=270   # plan +x = east, no rotation (village.md 1)
export BAKE_RES=1024   # 90 x 70 m of ground; the sun's shadows are drawn live, the bake is sky light and occlusion
# day 1, 10:00 (village.md 5.1): the sun at 116°, 58° up, clear; 5400 K-ish (sun.ts at that height) in sRGB
export PLAZA_BAKE_MINUTE=600 E_SKY=1.0 AEROSOL=1.6 BAKE_SUN_E=6 BAKE_SUN_RGB=1,0.925,0.86
export PLAZA_OUT="$WORK" SCENE_STEM="$PACK"

step() { echo "== $1"; }
mkdir -p "$WORK"
step "textures"; "$PY" -I "$COMMON/road_tex.py" "$WORK/tex" ${ROAD_SCANS:+"$ROAD_SCANS"}
step "scene";  (cd "$WORK" && "$PY" "$HERE/build_village.py")
step "sky";    (cd "$WORK" && "$PY" "$PLAZA/sky.py")
step "bake";   (cd "$WORK" && "$PY" "$PLAZA/bake.py" -- "$Q")
step "instances"; node "$HERE/merge_inst.mjs" "$WORK" "$PACK"
step "encode"; "$PY" "$PLAZA/encode.py"
step "pack";   node "$PLAZA/pack_scene.mjs" "$WORK" "$SCENES/$PACK/layout.json" "$(dest "$PACK")"
node "$HERE/zones.mjs" "$SCENES/$PACK/layout.json" "$(dest "$PACK")"
node "$COMMON/small_tex.mjs" "$WORK" "$(dest "$PACK")"
step "share (road-common)"
# a final build adds to the committed road-common (the road's keys stay listed even when its build dir is not here)
if [ "$Q" = final ] && [ -z "$OUT" ] && [ ! -f "$(dest road-common)/pack.json" ]; then
  mkdir -p "$(dest road-common)"; cp "$SCENES/road-common/pack.json" "$(dest road-common)/pack.json"
fi
node "$COMMON/roadside.mjs" "$(dest road-common)" "assets/pipeline/village/build.sh (roadside.mjs)" "$(dest "$PACK")"
step "check"
node "$PLAZA/check_scene.mjs" "$(dest "$PACK")" "$SCENES/$PACK/layout.json"
node "$HERE/check_village.mjs" "$(dest road-common)" "$(dest "$PACK")"

if [ "$Q" = final ] && [ -z "$OUT" ]; then
  cp "$(dest "$PACK")/scene.json" "$SCENES/$PACK/scene.json"
  cp "$(dest road-common)/pack.json" "$SCENES/road-common/pack.json"
  echo "refreshed the manifests in $SCENES/{$PACK,road-common}"
fi
