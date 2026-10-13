#!/usr/bin/env bash
# Installs or updates CI's self-hosted runner on zg's Mac (README.md). Needs: Docker Desktop running, gh logged in (repo admin).
# zg の Mac に CI のセルフホストランナーをインストール・更新する（README.md）。必要なもの：Docker Desktop が起動していること、gh にログイン済み（リポジトリ管理者）。
#   bash infra/ci-runner/setup.sh
# Safe to rerun: rebuilds the image and replaces the old container; does not register again if already registered.
# The registration token is fetched right before use, never printed or written to a file.
# 何度実行してもよい：イメージを再ビルドし、古いコンテナを置き換える。登録済みなら再登録しない。登録トークンは使う直前に取得し、
# 出力もファイルへの書き込みもしない。
set -euo pipefail

REPO="${RUNNER_REPO:-guoziyu415/zoujin}"
HERE="$(cd "$(dirname "$0")" && pwd)"
IMAGE=zoujin-ci-runner:latest
VOLUME=zoujin-ci-runner
NAME=zoujin-ci-runner
PLATFORM=linux/amd64

docker info >/dev/null

echo "== runner version (latest actions/runner release) / runner のバージョン（actions/runner の最新 release）"
VER="$(gh api repos/actions/runner/releases/latest --jq .tag_name)"
VER="${VER#v}"
SHA="$(gh api repos/actions/runner/releases/latest --jq .body |
  sed -n 's/.*<!-- BEGIN SHA linux-x64 -->\([0-9a-f]\{64\}\)<!-- END SHA linux-x64 -->.*/\1/p' | head -1)"
test -n "$SHA" || { echo "No linux-x64 sha256 found in the release notes / release の説明に linux-x64 の sha256 が見つからない" >&2; exit 1; }
echo "$VER"

echo "== Building image $IMAGE ($PLATFORM) / イメージ $IMAGE をビルド（$PLATFORM）"
docker build --platform "$PLATFORM" --build-arg RUNNER_VERSION="$VER" --build-arg RUNNER_SHA256="$SHA" \
  -t "$IMAGE" "$HERE"

docker volume create "$VOLUME" >/dev/null
run_once() { docker run --rm --platform "$PLATFORM" -v "$VOLUME:/home/runner/actions-runner" "$@"; }

if run_once "$IMAGE" test -f /home/runner/actions-runner/.runner; then
  echo "== Already registered, skipping registration / 登録済みのため登録をスキップ"
else
  echo "== Registering to $REPO (label zoujin-mac) / $REPO に登録（ラベル zoujin-mac）"
  RUNNER_TOKEN="$(gh api -X POST "repos/$REPO/actions/runners/registration-token" --jq .token)" \
    run_once -e RUNNER_TOKEN -e RUNNER_REPO="$REPO" "$IMAGE" register
fi

echo "== Starting container $NAME (starts with Docker, mounts no Mac folders; NET_ADMIN is only for the entrypoint to block connections and is dropped before the runner starts) / コンテナ $NAME を起動（Docker と一緒に起動し、Mac のフォルダは一切マウントしない。NET_ADMIN はエントリポイントが接続を遮断するためだけに使い、runner の起動前に捨てる）"
docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" --platform "$PLATFORM" --restart unless-stopped --cap-add NET_ADMIN \
  -v "$VOLUME:/home/runner/actions-runner" "$IMAGE" run >/dev/null

sleep 15
docker logs --tail 5 "$NAME"
gh api "repos/$REPO/actions/runners" --jq '.runners[] | "\(.name) \(.status) \([.labels[].name] | join(","))"'
