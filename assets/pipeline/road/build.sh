#!/usr/bin/env bash
# One command for the road's river (F-10): both packs (road-river-calm = act 2 at 05:15, road-river-flood = act 4 at
# 11:45), the shared roadside pack road-common, and the scene.road-river index and merged layout.
#   assets/pipeline/road/build.sh [final|draft] [out_dir]
# Runs the plaza's steps (../plaza: sky, bake, encode, pack, check) once per state with this scene's frame and light,
# then merge_river.mjs moves the shared textures into road-common (../common/roadside.mjs: the fixed key table) and
# writes assets/scenes/road-river/.
# final (default): writes assets/scenes/<pack>/build/ and refreshes the committed manifests (the packs' scene.json,
#   road-common/pack.json, road-river/{scene,index}.json).
# draft: 512 lightmaps; writes only out_dir/<pack>/ (CI uses this to prove the pipeline still runs and reproduces).
# Needs: BPY_PYTHON = a Python 3.13 with bpy 5.2, numpy and pillow (default python3); `pnpm install` done.
# Optional: PLAZA_OUT = work dir (default: a new temp dir), ROAD_SCANS = dir of CC0 scans that replace the
# placeholder textures (<key>_<kind>.png|jpg, see ../common/road_tex.py).
set -euo pipefail
Q="${1:-final}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PLAZA="$(cd "$HERE/../plaza" && pwd)"
SCENES="$(cd "$HERE/../../scenes" && pwd)"
OUT="${2:-}"
PY="${BPY_PYTHON:-python3}"
WORK="${PLAZA_OUT:-$(mktemp -d)}"
case "$Q" in final | draft) ;; *) echo "quality must be final or draft" >&2; exit 2 ;; esac
dest() { if [ -n "$OUT" ]; then echo "$OUT/$1"; else echo "$SCENES/$1/build"; fi; }
echo "work dir $WORK, output ${OUT:-$SCENES/<pack>/build} ($Q)"

# what pack_scene.mjs records as this scene's own inputs (in place of the plaza's build.sh and scene script)
export SCENE_INPUTS="assets/pipeline/road/build.sh,assets/pipeline/common/road_tex.py,assets/pipeline/plaza/placeholder_tex.py,assets/pipeline/common/bl.py,assets/pipeline/road/build_road_river.py,assets/pipeline/road/merge_river.mjs,assets/pipeline/common/roadside.mjs,assets/pipeline/common/small_tex.mjs"
export SCENE_BUILD="assets/pipeline/road/build.sh"
export SCENE_ROT_DEG=0 SCENE_MINUS_X_AZ=270   # plan +x = east, no rotation (homeward-road.md 0)
export BAKE_RES=1024   # 80 m of ground at 8 cm a texel; the sun's shadows are drawn live, the bake is sky light and occlusion

step() { echo "== $1"; }
step "textures"; "$PY" -I "$HERE/../common/road_tex.py" "$WORK/tex" ${ROAD_SCANS:+"$ROAD_SCANS"}

# per state: the bake minute, the sky, the direct sun the bake uses (the page's sun.ts at that height: SUN_E 6,
# kelvinRGB(sunKelvin(e)) in sRGB as the plaza's 18:30 colour is); RIVER_STATE goes to the scene script only
state_env() {
  case "$1" in
    # 05:15: the sun 2.8° up, behind the 7° east ridge, so no direct light in the valley (BAKE_SUN_E 0); the sky drawn
    # for the sun at -1.5° (earth shadow, pink band, homeward-road.md 1.5), same direction
    calm) echo "PLAZA_BAKE_MINUTE=315 SKY_SUN_ELEV_DEG=-1.5 E_SKY=0.35 AEROSOL=2.5 BAKE_SUN_E=0" ;;
    # 11:45: the sun 71.8° up, 5500 K; the air washed by the rain (less aerosol)
    flood) echo "PLAZA_BAKE_MINUTE=705 E_SKY=1.1 AEROSOL=1.2 BAKE_SUN_E=6 BAKE_SUN_RGB=1,0.931,0.872" ;;
  esac
}

for STATE in calm flood; do
  PACK="road-river-$STATE"
  W="$WORK/$STATE"
  mkdir -p "$W"
  ln -sfn "$WORK/tex" "$W/tex"
  (
    # shellcheck disable=SC2046
    export $(state_env "$STATE")
    export PLAZA_OUT="$W" SCENE_STEM="$PACK"
    step "$PACK: scene"; (cd "$W" && RIVER_STATE="$STATE" "$PY" "$HERE/build_road_river.py")
    step "$PACK: sky";   (cd "$W" && "$PY" "$PLAZA/sky.py")
    step "$PACK: bake";  (cd "$W" && "$PY" "$PLAZA/bake.py" -- "$Q")
    step "$PACK: encode"; "$PY" "$PLAZA/encode.py"
    step "$PACK: pack";  node "$PLAZA/pack_scene.mjs" "$W" "$SCENES/$PACK/layout.json" "$(dest "$PACK")"
    node "$HERE/../common/small_tex.mjs" "$W" "$(dest "$PACK")"
  )
done

step "merge (road-common, scene.road-river)"
# a final build adds to the committed road-common (the village's keys stay listed even when its build dir is not here)
if [ "$Q" = final ] && [ -z "$OUT" ] && [ ! -f "$(dest road-common)/pack.json" ]; then
  mkdir -p "$(dest road-common)"; cp "$SCENES/road-common/pack.json" "$(dest road-common)/pack.json"
fi
node "$HERE/merge_river.mjs" "$(dest road-river-calm)" "$(dest road-river-flood)" "$(dest road-common)" "$(dest road-river)"
step "check"
for PACK in road-river-calm road-river-flood; do
  node "$PLAZA/check_scene.mjs" "$(dest "$PACK")" "$SCENES/$PACK/layout.json"
done
node "$HERE/check_road.mjs" "$(dest road-common)" "$(dest road-river-calm)" "$(dest road-river-flood)" "$(dest road-river)"

if [ "$Q" = final ] && [ -z "$OUT" ]; then
  cp "$(dest road-common)/pack.json" "$SCENES/road-common/pack.json"
  for PACK in road-river-calm road-river-flood; do cp "$(dest "$PACK")/scene.json" "$SCENES/$PACK/scene.json"; done
  cp "$(dest road-river)/scene.json" "$(dest road-river)/index.json" "$SCENES/road-river/"
  echo "refreshed the manifests in $SCENES/{road-common,road-river-calm,road-river-flood,road-river}"
fi
