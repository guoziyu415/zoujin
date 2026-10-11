#!/usr/bin/env bash
# One command for the other characters (F-16): Melos's MPFB build -> each character's .blend -> three versions + clips
# (lod_export.py, as Melos) -> phone formats (compress.mjs) -> check against the character budgets.
#   assets/pipeline/cast/build.sh [name ...]      (names from characters.json, or a variant such as sister-wedding;
#                                                 default: all of them)
# Writes assets/cast/build/<name>/{talk_high,talk_std,walk,anims}.glb (not in git; vite serves them at /cast/) and
# refreshes the committed manifest assets/cast/cast.json (sizes, triangles, sha256 per file).
# Needs:
#   MELOS_BLEND = Melos's MPFB build from the Mac (A-0, melos_v2.blend; project folder
#                 frontend/spikes/a0-melos/mac/; sha256 checked below). The CC0 MPFB system assets every character
#                 shares (eyes, brows, lashes, teeth, tongue, their textures) are packed in it.
#   BPY_PYTHON  = a Python 3.13 with bpy 5.2, numpy and Pillow (default python3), git, node with assets/pipeline's
#                 packages installed.
# MPFB 2 is fetched at the same pinned commit as the crowd (crowd/build.sh), or MPFB_SRC = that extension directory.
# Optional: UAL_GLB = Quaternius's UAL1_Standard.glb (CC0, never in the repo, sha256 checked) -> the mocap clips;
# without it lod_export writes its procedural placeholders.
set -euo pipefail
MPFB_COMMIT=d0a32e57a7f915cb2f2b95410e2117648c7bbb7e # MPFB 2.0.18
MELOS_SHA256=3cbe09375437f542732b1542d9156521bb096683a5e970aa24634473b1a61d36 # melos_v2.blend
UAL_SHA256=69591853d817488edaa8fd9bf8fc1d821eaeaf789f8627b3cd23b41c4ed67997 # Universal Animation Library 1, Standard
HERE="$(cd "$(dirname "$0")" && pwd)"
PIPE="$(cd "$HERE/.." && pwd)"
CAST="$(cd "$HERE/../../cast" && pwd)"
OUT="$CAST/build"
PY="${BPY_PYTHON:-python3}"

sha() { if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1; }
: "${MELOS_BLEND:?set MELOS_BLEND to melos_v2.blend}"
test "$(sha "$MELOS_BLEND")" = "$MELOS_SHA256" || { echo "MELOS_BLEND is not the pinned melos_v2.blend" >&2; exit 1; }
if [ -n "${UAL_GLB:-}" ]; then
  test "$(sha "$UAL_GLB")" = "$UAL_SHA256" || { echo "UAL_GLB is not the pinned UAL1_Standard.glb" >&2; exit 1; }
  export UAL_GLB
fi

RES="$(mktemp -d)"
trap 'rm -rf "$RES"' EXIT
mkdir -p "$RES/extensions/user_default"
if [ -n "${MPFB_SRC:-}" ]; then
  cp -R "$MPFB_SRC" "$RES/extensions/user_default/mpfb"
else
  git init -q "$RES/mpfb2"
  git -C "$RES/mpfb2" fetch -q --depth 1 https://github.com/makehumancommunity/mpfb2 "$MPFB_COMMIT"
  git -C "$RES/mpfb2" checkout -q FETCH_HEAD
  test "$(git -C "$RES/mpfb2" rev-parse HEAD)" = "$MPFB_COMMIT"
  mv "$RES/mpfb2/src/mpfb" "$RES/extensions/user_default/mpfb"
fi

# name -> "character [variant]" (a read loop, not mapfile: the Mac's bash is 3.2)
ALL=()
while IFS= read -r row; do ALL+=("$row"); done < <("$PY" -I -c '
import json, sys
c = json.load(open(sys.argv[1]))["characters"]
for k, v in c.items():
    print(k, k)
    for n in v.get("variants", {}):
        print(n, k, n)
' "$HERE/characters.json")
NAMES=("$@")
for row in "${ALL[@]}"; do
  read -r name id variant <<<"$row"
  if [ ${#NAMES[@]} -gt 0 ] && [[ ! " ${NAMES[*]} " == *" $name "* ]]; then continue; fi
  echo "== $name"
  work="$RES/$name"
  mkdir -p "$work" "$OUT/$name"
  BLENDER_USER_RESOURCES="$RES" "$PY" -I "$HERE/build_cast.py" -- "$MELOS_BLEND" "$id" "$work/$name.blend" ${variant:+"$variant"} \
    > "$work/build.log" 2>&1 || { tail -30 "$work/build.log" >&2; exit 1; }
  grep '^CAST_REPORT ' "$work/build.log" | cut -d' ' -f2- > "$OUT/$name/build_report.json"
  "$PY" -I "$PIPE/lod_export.py" "$work/$name.blend" "$work/raw" > "$work/lod.log" 2>&1 \
    || { tail -30 "$work/lod.log" >&2; exit 1; }
  cp "$work/raw/lod_report.json" "$OUT/$name/"
  node "$PIPE/compress.mjs" "$work/raw" "$work/phone" > "$work/compress.log" 2>&1 \
    || { tail -30 "$work/compress.log" >&2; exit 1; }
  for f in talk_high.glb talk_std.glb walk.glb anims.glb compress_report.json; do cp "$work/phone/$f" "$OUT/$name/"; done
  rm -rf "$work"
done
echo "== check"
node "$HERE/check_cast.mjs" "$OUT" "$CAST/cast.json"
