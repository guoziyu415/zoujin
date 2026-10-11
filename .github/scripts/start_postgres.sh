#!/usr/bin/env bash
# CI 的 db job 用：在这个 job 里起一个 PostgreSQL 17 进程（数据目录在 $RUNNER_TEMP，job 结束就没了），
# 建库 zoujin_test，把 DATABASE_URL 写进 $GITHUB_ENV 给后面的步骤。
#   bash .github/scripts/start_postgres.sh        起库
#   bash .github/scripts/start_postgres.sh stop   停库
# 自建机器的镜像（infra/ci-runner/Dockerfile）里已经装了 postgresql-17；GitHub 自带的 Ubuntu 机器上没有 17，
# 这里从 PostgreSQL 官方的 apt 源（PGDG）装。只监听容器或机器自己的 127.0.0.1，用户 zoujin，本机信任登录。
set -euo pipefail

PORT="${PG_PORT:-5432}"
TMP="${RUNNER_TEMP:-$(mktemp -d)}"
DATA="$TMP/pg-data"
SOCK="$TMP/pg-sock"
BIN="${PG_BIN:-/usr/lib/postgresql/17/bin}"

if [ "${1:-start}" = stop ]; then
  if [ -f "$DATA/postmaster.pid" ]; then "$BIN/pg_ctl" -D "$DATA" -m fast -w stop; fi
  rm -rf "$DATA" "$SOCK"
  exit 0
fi

if [ ! -x "$BIN/pg_ctl" ]; then
  echo "== 装 PostgreSQL 17（PGDG）"
  sudo apt-get update -q
  sudo apt-get install -y -q --no-install-recommends postgresql-common
  sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y
  sudo apt-get install -y -q --no-install-recommends postgresql-17
fi

rm -rf "$DATA" "$SOCK"
mkdir -p "$SOCK"
"$BIN/initdb" -D "$DATA" -U zoujin --auth=trust --encoding=UTF8 --locale=C.UTF-8 >/dev/null
"$BIN/pg_ctl" -D "$DATA" -l "$TMP/pg.log" -w -t 60 \
  -o "-c listen_addresses=127.0.0.1 -p $PORT -k $SOCK -c fsync=off" start
"$BIN/createdb" -h 127.0.0.1 -p "$PORT" -U zoujin zoujin_test

URL="postgresql://zoujin:zoujin@127.0.0.1:$PORT/zoujin_test"
if [ -n "${GITHUB_ENV:-}" ]; then echo "DATABASE_URL=$URL" >>"$GITHUB_ENV"; else echo "DATABASE_URL=$URL"; fi
echo "PostgreSQL $("$BIN/postgres" --version | awk '{print $3}') 在 127.0.0.1:$PORT"
