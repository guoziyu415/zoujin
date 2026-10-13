#!/usr/bin/env bash
# For the CI db job: starts a PostgreSQL 17 process inside this job (data directory in $RUNNER_TEMP, gone when the job ends),
# creates the database zoujin_test and writes DATABASE_URL to $GITHUB_ENV for later steps.
# CI の db ジョブ用：このジョブ内で PostgreSQL 17 プロセスを起動し（データディレクトリは $RUNNER_TEMP、ジョブ終了で消える）、
# データベース zoujin_test を作成して、後続のステップ用に DATABASE_URL を $GITHUB_ENV に書き込む。
#   bash .github/scripts/start_postgres.sh        start the database / DB を起動
#   bash .github/scripts/start_postgres.sh stop   stop the database / DB を停止
# The self-hosted runner image (infra/ci-runner/Dockerfile) already has postgresql-17; GitHub's hosted Ubuntu runners lack 17,
# so it is installed here from PostgreSQL's official apt repo (PGDG). Listens only on the container's or machine's own
# 127.0.0.1, user zoujin, trust auth locally.
# セルフホストランナーのイメージ（infra/ci-runner/Dockerfile）には postgresql-17 がインストール済み。GitHub 提供の Ubuntu ランナーには 17 がないので、
# ここで PostgreSQL 公式の apt リポジトリ（PGDG）からインストールする。コンテナまたはマシン自身の 127.0.0.1 だけで待ち受け、
# ユーザーは zoujin、ローカルは trust 認証。
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
  echo "== Installing PostgreSQL 17 (PGDG) / PostgreSQL 17 をインストール（PGDG）"
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
echo "PostgreSQL $("$BIN/postgres" --version | awk '{print $3}') at 127.0.0.1:$PORT / 127.0.0.1:$PORT で稼働中"
