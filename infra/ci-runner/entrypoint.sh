#!/usr/bin/env bash
# 容器的入口，以 root 起。runner 的目录 /home/runner/actions-runner 是命名卷，注册信息和 runner 的自动更新都留在
# 卷里（Docker 的虚拟机里，不在 Mac 的文件夹里）。
#   register  第一次：用 RUNNER_TOKEN（注册令牌，一小时有效，setup.sh 现取现传）把 runner 注册到 RUNNER_REPO
#   run       默认：封连接，丢权限，跑 runner 等 job（容器要 --cap-add NET_ADMIN）
#   其他      原样执行（setup.sh 用来查是不是已经注册过）
set -euo pipefail
cd /home/runner/actions-runner

# 换成 runner 用户：不能再提权（no_new_privs），能力全部丢掉，NET_ADMIN 也没了，所以 job 改不回下面的规则
as_runner() {
  exec setpriv --reuid=runner --regid=runner --init-groups \
    --inh-caps=-all --ambient-caps=-all --bounding-set=-all --no-new-privs \
    env HOME=/home/runner USER=runner LOGNAME=runner "$@"
}

# 只让容器出公网：到 Mac 本机（host.docker.internal 等）、Docker 的虚拟机、局域网的连接一律拒绝，
# 只留 Docker 的 DNS 的 53 端口。任何一步失败就不起 runner（宁可 CI 停，也不在没封的容器里跑 PR 的代码）。
firewall() {
  local ipt=iptables ip6t=ip6tables
  if ! iptables -L OUTPUT -n >/dev/null 2>&1; then ipt=iptables-legacy ip6t=ip6tables-legacy; fi
  "$ipt" -F OUTPUT
  "$ipt" -A OUTPUT -o lo -j ACCEPT
  for ns in $(awk '/^nameserver/ {print $2}' /etc/resolv.conf); do
    case "$ns" in *:*) continue ;; esac
    "$ipt" -A OUTPUT -d "$ns" -p udp --dport 53 -j ACCEPT
    "$ipt" -A OUTPUT -d "$ns" -p tcp --dport 53 -j ACCEPT
  done
  local nets="0.0.0.0/8 10.0.0.0/8 100.64.0.0/10 169.254.0.0/16 172.16.0.0/12 192.0.0.0/24 192.168.0.0/16 198.18.0.0/15 224.0.0.0/3"
  local hosts=""
  for name in host.docker.internal gateway.docker.internal; do
    hosts="$hosts $( (getent ahostsv4 "$name" || true) | awk '{print $1}' | sort -u | tr '\n' ' ')"
  done
  for n in $nets $hosts; do "$ipt" -A OUTPUT -d "$n" -j REJECT; done
  # IPv6 只留本机回环；容器有回环以外的 IPv6 地址却装不上规则，就不起 runner
  if "$ip6t" -L OUTPUT -n >/dev/null 2>&1; then
    "$ip6t" -F OUTPUT
    "$ip6t" -A OUTPUT -o lo -j ACCEPT
    "$ip6t" -A OUTPUT -j REJECT
  elif [ -r /proc/net/if_inet6 ] && awk '$6 != "lo" {found = 1} END {exit !found}' /proc/net/if_inet6; then
    echo "有 IPv6 地址但 ip6tables 用不了" >&2
    exit 1
  fi
  # 自检：按规则本身查（Mac 上的服务没开时，连不上也说明不了什么）
  for h in $hosts; do
    "$ipt" -C OUTPUT -d "$h" -j REJECT || { echo "防火墙没生效：没有拒绝 $h 的规则" >&2; exit 1; }
  done
  echo "已封：Mac 本机、Docker 虚拟机、局域网；只出公网"
}

case "${1:-run}" in
  register)
    : "${RUNNER_TOKEN:?register 要 RUNNER_TOKEN}"
    : "${RUNNER_REPO:?register 要 RUNNER_REPO（owner/name）}"
    as_runner ./config.sh --unattended --replace \
      --url "https://github.com/${RUNNER_REPO}" \
      --token "$RUNNER_TOKEN" \
      --name "${RUNNER_NAME:-zoujin-mac}" \
      --labels zoujin-mac \
      --work _work
    ;;
  run)
    test -f .runner || { echo "还没注册：先跑 setup.sh" >&2; exit 1; }
    firewall
    # 每个 job 跑完清工作目录和临时目录（job-done.sh）
    export ACTIONS_RUNNER_HOOK_JOB_COMPLETED=/usr/local/bin/job-done.sh
    as_runner ./run.sh
    ;;
  *)
    exec "$@"
    ;;
esac
