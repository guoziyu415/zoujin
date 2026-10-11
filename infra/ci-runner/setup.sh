#!/usr/bin/env bash
# 在 zg 的 Mac 上装、更新 CI 的自建机器（README.md）。要：Docker Desktop 开着，gh 已登录（仓库管理员）。
#   bash infra/ci-runner/setup.sh
# 重复跑没关系：重新构建镜像、换掉旧容器；已经注册过就不再注册。注册令牌现取现用，不打印、不写文件。
set -euo pipefail

REPO="${RUNNER_REPO:-guoziyu415/zoujin}"
HERE="$(cd "$(dirname "$0")" && pwd)"
IMAGE=zoujin-ci-runner:latest
VOLUME=zoujin-ci-runner
NAME=zoujin-ci-runner
PLATFORM=linux/amd64

docker info >/dev/null

echo "== runner 版本（actions/runner 最新 release）"
VER="$(gh api repos/actions/runner/releases/latest --jq .tag_name)"
VER="${VER#v}"
SHA="$(gh api repos/actions/runner/releases/latest --jq .body |
  sed -n 's/.*<!-- BEGIN SHA linux-x64 -->\([0-9a-f]\{64\}\)<!-- END SHA linux-x64 -->.*/\1/p' | head -1)"
test -n "$SHA" || { echo "release 说明里没找到 linux-x64 的 sha256" >&2; exit 1; }
echo "$VER"

echo "== 构建镜像 $IMAGE（$PLATFORM）"
docker build --platform "$PLATFORM" --build-arg RUNNER_VERSION="$VER" --build-arg RUNNER_SHA256="$SHA" \
  -t "$IMAGE" "$HERE"

docker volume create "$VOLUME" >/dev/null
run_once() { docker run --rm --platform "$PLATFORM" -v "$VOLUME:/home/runner/actions-runner" "$@"; }

if run_once "$IMAGE" test -f /home/runner/actions-runner/.runner; then
  echo "== 已经注册过，跳过注册"
else
  echo "== 注册到 $REPO（标签 zoujin-mac）"
  RUNNER_TOKEN="$(gh api -X POST "repos/$REPO/actions/runners/registration-token" --jq .token)" \
    run_once -e RUNNER_TOKEN -e RUNNER_REPO="$REPO" "$IMAGE" register
fi

echo "== 启动容器 $NAME（随 Docker 启动，不挂 Mac 的任何文件夹）"
docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" --platform "$PLATFORM" --restart unless-stopped \
  -v "$VOLUME:/home/runner/actions-runner" "$IMAGE" run >/dev/null

sleep 15
docker logs --tail 5 "$NAME"
gh api "repos/$REPO/actions/runners" --jq '.runners[] | "\(.name) \(.status) \([.labels[].name] | join(","))"'
