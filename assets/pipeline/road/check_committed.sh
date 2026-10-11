#!/usr/bin/env bash
# The committed manifests of the road's other stops (F-15), without building: every pack (check_scene.mjs: budgets,
# spots against layout.json, the world models), its share of road-common and each scene's index and merged layout
# (check_rest.mjs). Seconds. The river is checked by check_road.mjs.
#   assets/pipeline/road/check_committed.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SCENES="$ROOT/assets/scenes"
PACKS="road-pass-day road-spring-day road-field-day road-run-r1 road-run-r2 road-run-r2s road-run-r3 road-run-night"
DIRS=()
for p in $PACKS; do
  node "$ROOT/assets/pipeline/plaza/check_scene.mjs" "$SCENES/$p"
  DIRS+=("$SCENES/$p")
done
node "$ROOT/assets/pipeline/road/check_rest.mjs" "$SCENES/road-common" "$SCENES/{}" "${DIRS[@]}"
