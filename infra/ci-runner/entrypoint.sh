#!/usr/bin/env bash
# The container's entrypoint, started as root. The runner directory /home/runner/actions-runner is a named volume; the
# registration and the runner's auto-updates stay in the volume (inside Docker's VM, not in a folder on the Mac).
# コンテナのエントリポイントで、root で起動する。runner のディレクトリ /home/runner/actions-runner は名前付きボリュームで、登録情報と
# runner の自動更新はボリューム内に残る（Docker の仮想マシン内であり、Mac のフォルダではない）。
#   register  First time: register the runner to RUNNER_REPO with RUNNER_TOKEN (registration token, valid one hour,
#             fetched by setup.sh right before use)
#             初回：RUNNER_TOKEN（登録トークン、有効期限 1 時間、setup.sh が使う直前に取得して渡す）で runner を RUNNER_REPO に登録
#   run       Default: block connections, drop privileges, run the runner and wait for jobs (container needs --cap-add NET_ADMIN)
#             デフォルト：接続を遮断し、権限を捨て、runner を動かしてジョブを待つ（コンテナには --cap-add NET_ADMIN が必要）
#   other     Run as is (setup.sh uses this to check whether it is already registered)
#   その他    そのまま実行（setup.sh が登録済みかどうかの確認に使う）
set -euo pipefail
cd /home/runner/actions-runner

# Switch to the runner user: no further privilege escalation (no_new_privs), all capabilities dropped including NET_ADMIN,
# so jobs cannot undo the rules below
# runner ユーザーに切り替える：権限昇格は不可（no_new_privs）、ケーパビリティはすべて捨て NET_ADMIN もなくなるので、
# ジョブは下のルールを元に戻せない
as_runner() {
  exec setpriv --reuid=runner --regid=runner --init-groups \
    --inh-caps=-all --ambient-caps=-all --bounding-set=-all --no-new-privs \
    env HOME=/home/runner USER=runner LOGNAME=runner "$@"
}

# Let the container reach only the public internet: connections to the Mac itself (host.docker.internal etc.), Docker's
# VM and the LAN are all rejected, leaving only port 53 to Docker's DNS. If any step fails the runner does not start
# (better to stop CI than to run PR code in an unsealed container).
# コンテナからはインターネットにだけ出られるようにする：Mac 本体（host.docker.internal など）、Docker の仮想マシン、LAN への接続は
# すべて拒否し、Docker の DNS の 53 番ポートだけを残す。どこかの手順が失敗したら runner は起動しない
# （遮断されていないコンテナで PR のコードを実行するより、CI を止めるほうがよい）。
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
  # IPv6: allow only loopback; if the container has a non-loopback IPv6 address but the rules cannot be installed, do not start the runner
  # IPv6 はループバックだけを許可する。コンテナにループバック以外の IPv6 アドレスがあるのにルールを入れられなければ、runner は起動しない
  if "$ip6t" -L OUTPUT -n >/dev/null 2>&1; then
    "$ip6t" -F OUTPUT
    "$ip6t" -A OUTPUT -o lo -j ACCEPT
    "$ip6t" -A OUTPUT -j REJECT
  elif [ -r /proc/net/if_inet6 ] && awk '$6 != "lo" {found = 1} END {exit !found}' /proc/net/if_inet6; then
    echo "There is an IPv6 address but ip6tables is unavailable / IPv6 アドレスがあるのに ip6tables が使えない" >&2
    exit 1
  fi
  # Self-check against the rules themselves (when the Mac's services are not running, a failed connection proves nothing)
  # 自己チェック：ルールそのものを確認する（Mac のサービスが動いていないときは、つながらなくても何の証明にもならない）
  for h in $hosts; do
    "$ipt" -C OUTPUT -d "$h" -j REJECT || { echo "Firewall not in effect: no rule rejecting $h / ファイアウォールが効いていない：$h を拒否するルールがない" >&2; exit 1; }
  done
  echo "Blocked: the Mac itself, Docker VM, LAN; public internet only / 遮断済み：Mac 本体、Docker の仮想マシン、LAN。インターネットにだけ出られる"
}

case "${1:-run}" in
  register)
    : "${RUNNER_TOKEN:?register needs RUNNER_TOKEN / register には RUNNER_TOKEN が必要}"
    : "${RUNNER_REPO:?register needs RUNNER_REPO (owner/name) / register には RUNNER_REPO（owner/name）が必要}"
    as_runner ./config.sh --unattended --replace \
      --url "https://github.com/${RUNNER_REPO}" \
      --token "$RUNNER_TOKEN" \
      --name "${RUNNER_NAME:-zoujin-mac}" \
      --labels zoujin-mac \
      --work _work
    ;;
  run)
    test -f .runner || { echo "Not registered yet: run setup.sh first / まだ登録されていない：先に setup.sh を実行すること" >&2; exit 1; }
    firewall
    # After each job, clear the work and temp directories (job-done.sh)
    # ジョブが終わるたびに作業ディレクトリと一時ディレクトリを空にする（job-done.sh）
    export ACTIONS_RUNNER_HOOK_JOB_COMPLETED=/usr/local/bin/job-done.sh
    as_runner ./run.sh
    ;;
  *)
    exec "$@"
    ;;
esac
