#!/usr/bin/env bash
# 容器的入口。runner 的目录 /home/runner/actions-runner 是命名卷，注册信息和 runner 的自动更新都留在卷里（Docker
# 的虚拟机里，不在 Mac 的文件夹里）。
#   register  第一次：用 RUNNER_TOKEN（注册令牌，一小时有效，setup.sh 现取现传）把 runner 注册到 RUNNER_REPO
#   run       默认：跑 runner，等 job
#   其他      原样执行（setup.sh 用来查是不是已经注册过）
set -euo pipefail
cd /home/runner/actions-runner

case "${1:-run}" in
  register)
    : "${RUNNER_TOKEN:?register 要 RUNNER_TOKEN}"
    : "${RUNNER_REPO:?register 要 RUNNER_REPO（owner/name）}"
    ./config.sh --unattended --replace \
      --url "https://github.com/${RUNNER_REPO}" \
      --token "$RUNNER_TOKEN" \
      --name "${RUNNER_NAME:-zoujin-mac}" \
      --labels zoujin-mac \
      --work _work
    ;;
  run)
    test -f .runner || { echo "还没注册：先跑 setup.sh" >&2; exit 1; }
    # 每个 job 跑完清工作目录和临时目录（job-done.sh）
    export ACTIONS_RUNNER_HOOK_JOB_COMPLETED=/usr/local/bin/job-done.sh
    exec ./run.sh
    ;;
  *)
    exec "$@"
    ;;
esac
