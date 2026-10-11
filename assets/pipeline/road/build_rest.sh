#!/usr/bin/env bash
# One command for the homeward road's other stops (F-15): road-pass-day (act 4, 14:00), road-spring-day (act 4,
# 15:45), road-field-day (act 4, 18:30, a run), the run segments road-run-r1, -r2, -r2s, -r3 and act 2's
# road-run-night; then merge_rest.mjs moves their shared textures into road-common (../common/roadside.mjs: the fixed
# key table, the same bytes the river and the village bring) and writes assets/scenes/<scene>/{index,scene}.json for
# scene.road-pass, -spring, -field. The river has its own build.sh; neither touches the other's packs.
#   assets/pipeline/road/build_rest.sh [final|draft] [out_dir]
# final (default): writes assets/scenes/<pack>/build/ and refreshes the committed manifests (the packs' scene.json,
#   road-common/pack.json, the three scenes' index.json and scene.json).
# draft: 512 lightmaps; writes only out_dir/<pack>/ (CI uses this to prove the pipeline still runs and reproduces).
# Needs: BPY_PYTHON = a Python 3.13 with bpy 5.2, numpy and pillow (default python3); `pnpm install` done.
# Optional: PLAZA_OUT = work dir (default: a new temp dir), ROAD_SCANS = dir of CC0 scans that replace the
# placeholder textures, ROAD_PACKS = only these packs (space-separated; the merge and the checks then cover only
# them, and nothing committed is refreshed).
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

COMMON_INPUTS="assets/pipeline/road/build_rest.sh,assets/pipeline/road/rest_tex.py,assets/pipeline/common/road_tex.py,assets/pipeline/plaza/placeholder_tex.py,assets/pipeline/common/bl.py,assets/pipeline/road/roadkit.py,assets/pipeline/road/merge_rest.mjs,assets/pipeline/common/roadside.mjs,assets/pipeline/common/small_tex.mjs"
export SCENE_BUILD="assets/pipeline/road/build_rest.sh"
export SCENE_ROT_DEG=0   # no rotation: each pack's plan +x direction goes to the sun scripts as SCENE_MINUS_X_AZ
export BAKE_RES=1024   # 80 m of ground at 8 cm a texel; the sun's shadows are drawn live, the bake is sky light and occlusion

step() { echo "== $1"; }
step "textures"; "$PY" -I "$HERE/rest_tex.py" "$WORK/tex" ${ROAD_SCANS:+"$ROAD_SCANS"}

# per pack: its script (and what the script reads), the azimuth of plan -x (homeward-road.md 0.2: +x points along
# the road towards Syracuse), the bake minute, the sky, the direct sun the bake uses (the page's sun.ts at that height:
# SUN_E 6, kelvinRGB(sunKelvin(e)) in sRGB as the plaza's 18:30 colour is)
pack_env() {
  case "$1" in
    # 14:00: the afternoon's hard sun, white highlights, heat haze far off (2.5)
    road-pass-day) echo "SCRIPT=build_road_pass.py SCENE_MINUS_X_AZ=260 PLAZA_BAKE_MINUTE=840 E_SKY=1.1 AEROSOL=1.6 BAKE_SUN_E=6 BAKE_SUN_RGB=1,0.931,0.872" ;;
    # 15:45: between the 15:00 glare and the 16:30 warmth (3.4)
    road-spring-day) echo "SCRIPT=build_road_spring.py SCENE_MINUS_X_AZ=280 PLAZA_BAKE_MINUTE=945 E_SKY=1.0 AEROSOL=1.8 BAKE_SUN_E=6 BAKE_SUN_RGB=1,0.86,0.72" ;;
    # 18:30: the sun right behind the runners, low and red (4.3)
    road-field-day) echo "SCRIPT=build_road_run.py RUN=field SCENE_MINUS_X_AZ=294 PLAZA_BAKE_MINUTE=1110 E_SKY=0.9 AEROSOL=2.2 BAKE_SUN_E=6 BAKE_SUN_RGB=1,0.58,0.32" ;;
    # the short runs (5): the middle of each segment's hours; their sun is drawn live
    road-run-r1) echo "SCRIPT=build_road_run.py RUN=r1 SCENE_MINUS_X_AZ=265 PLAZA_BAKE_MINUTE=775 E_SKY=1.1 AEROSOL=1.3 BAKE_SUN_E=6 BAKE_SUN_RGB=1,0.931,0.872" ;;
    road-run-r2) echo "SCRIPT=build_road_run.py RUN=r2 SCENE_MINUS_X_AZ=270 PLAZA_BAKE_MINUTE=870 E_SKY=1.1 AEROSOL=1.7 BAKE_SUN_E=6 BAKE_SUN_RGB=1,0.931,0.872" ;;
    road-run-r2s) echo "SCRIPT=build_road_run.py RUN=r2s SCENE_MINUS_X_AZ=270 PLAZA_BAKE_MINUTE=885 E_SKY=1.1 AEROSOL=1.7 BAKE_SUN_E=6 BAKE_SUN_RGB=1,0.931,0.872" ;;
    road-run-r3) echo "SCRIPT=build_road_run.py RUN=r3 SCENE_MINUS_X_AZ=287 PLAZA_BAKE_MINUTE=1015 E_SKY=1.0 AEROSOL=1.9 BAKE_SUN_E=6 BAKE_SUN_RGB=1,0.8,0.62" ;;
    # act 2's night road (5.1): no moon, no lamp; baked under the deep blue before dawn, the page darkens it further
    road-run-night) echo "SCRIPT=build_road_run.py RUN=night SCENE_MINUS_X_AZ=275 PLAZA_BAKE_MINUTE=290 SKY_SUN_ELEV_DEG=-6 E_SKY=0.12 AEROSOL=2.0 BAKE_SUN_E=0" ;;
    *) echo "unknown pack $1" >&2; exit 2 ;;
  esac
}
ALL="road-pass-day road-spring-day road-field-day road-run-r1 road-run-r2 road-run-r2s road-run-r3 road-run-night"
PACKS="${ROAD_PACKS:-$ALL}"

for PACK in $PACKS; do
  W="$WORK/$PACK"
  mkdir -p "$W"
  ln -sfn "$WORK/tex" "$W/tex"
  (
    ENV_LINE="$(pack_env "$PACK")"
    # shellcheck disable=SC2046,SC2086
    export $ENV_LINE
    # what pack_scene.mjs records as this pack's own inputs (in place of the plaza's build.sh and scene script)
    export SCENE_INPUTS="$COMMON_INPUTS,assets/pipeline/road/$SCRIPT"
    export PLAZA_OUT="$W" SCENE_STEM="$PACK"
    step "$PACK: scene"; (cd "$W" && "$PY" "$HERE/$SCRIPT")
    step "$PACK: sky";   (cd "$W" && "$PY" "$PLAZA/sky.py")
    step "$PACK: bake";  (cd "$W" && "$PY" "$PLAZA/bake.py" -- "$Q")
    step "$PACK: encode"; "$PY" "$PLAZA/encode.py"
    step "$PACK: pack";  node "$PLAZA/pack_scene.mjs" "$W" "$SCENES/$PACK/layout.json" "$(dest "$PACK")"
    node "$HERE/../common/small_tex.mjs" "$W" "$(dest "$PACK")"
  )
done

DIRS=(); for PACK in $PACKS; do DIRS+=("$(dest "$PACK")"); done
step "merge (road-common, the road scenes)"
# a final build adds to the committed road-common (the river's and the village's keys stay listed)
if [ "$Q" = final ] && [ -z "$OUT" ] && [ ! -f "$(dest road-common)/pack.json" ]; then
  mkdir -p "$(dest road-common)"; cp "$SCENES/road-common/pack.json" "$(dest road-common)/pack.json"
fi
node "$HERE/merge_rest.mjs" "$(dest road-common)" "$(dest "{}")" "${DIRS[@]}"
step "check"
for PACK in $PACKS; do
  node "$PLAZA/check_scene.mjs" "$(dest "$PACK")" "$SCENES/$PACK/layout.json"
done
node "$HERE/check_rest.mjs" "$(dest road-common)" "$(dest "{}")" "${DIRS[@]}"

if [ "$Q" = final ] && [ -z "$OUT" ] && [ -z "${ROAD_PACKS:-}" ]; then
  cp "$(dest road-common)/pack.json" "$SCENES/road-common/pack.json"
  for PACK in $PACKS; do cp "$(dest "$PACK")/scene.json" "$SCENES/$PACK/scene.json"; done
  for S in road-pass road-spring road-field; do
    mkdir -p "$SCENES/$S"
    cp "$(dest "$S")/scene.json" "$(dest "$S")/index.json" "$SCENES/$S/"
  done
  echo "refreshed the manifests in $SCENES (road-common, the packs, the road scenes)"
fi
