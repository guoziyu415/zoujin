#!/usr/bin/env bash
# One command for the execution ground's crowd (F-4): MPFB 2's bodies -> crowd.bin + crowd.json -> check.
#   assets/pipeline/crowd/build.sh [out_dir]
# out_dir (default assets/scenes/syracuse-square/build/crowd): inside the plaza's build, so the scene pack carries the
#   crowd (api-contract 2.1: everything under the scene's directory is in its assetVersion). Writing the default also
#   refreshes the committed manifest assets/scenes/syracuse-square/crowd.json.
# Needs: BPY_PYTHON = a Python 3.13 with bpy 5.2 (as plaza/build.sh; default python3), git, node.
# MPFB 2: fetched at the pinned commit below into a temp dir (git checks the commit id; only its own CC0 data is used,
#   LICENSE.ASSETS.md). Or MPFB_SRC = an MPFB extension directory already on disk (src/mpfb of that commit).
# Optional: CROWD_PREVIEW = a .png path for a render of the three bodies (and <name>-back.png from behind).
set -euo pipefail
MPFB_COMMIT=d0a32e57a7f915cb2f2b95410e2117648c7bbb7e # MPFB 2.0.18
HERE="$(cd "$(dirname "$0")" && pwd)"
SCENE="$(cd "$HERE/../../scenes/syracuse-square" && pwd)"
OUT="${1:-$SCENE/build/crowd}"
PY="${BPY_PYTHON:-python3}"
RES="$(mktemp -d)"
trap 'rm -rf "$RES"' EXIT
mkdir -p "$RES/extensions/user_default"
if [ -n "${MPFB_SRC:-}" ]; then
  cp -R "$MPFB_SRC" "$RES/extensions/user_default/mpfb"
  MPFB_COMMIT=""
else
  git init -q "$RES/mpfb2"
  git -C "$RES/mpfb2" fetch -q --depth 1 https://github.com/makehumancommunity/mpfb2 "$MPFB_COMMIT"
  git -C "$RES/mpfb2" checkout -q FETCH_HEAD
  test "$(git -C "$RES/mpfb2" rev-parse HEAD)" = "$MPFB_COMMIT"
  mv "$RES/mpfb2/src/mpfb" "$RES/extensions/user_default/mpfb"
fi
echo "== bodies"
BLENDER_USER_RESOURCES="$RES" MPFB_COMMIT="$MPFB_COMMIT" "$PY" -I "$HERE/build_crowd.py" -- "$OUT" ${CROWD_PREVIEW:+"$CROWD_PREVIEW"}
echo "== check"
node "$HERE/check_crowd.mjs" "$OUT"
if [ "$OUT" = "$SCENE/build/crowd" ]; then
  cp "$OUT/crowd.json" "$SCENE/crowd.json"
  echo "refreshed $SCENE/crowd.json"
fi
