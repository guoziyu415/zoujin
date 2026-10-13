#!/usr/bin/env bash
# The runner's job-completed hook: clears this job's work directory (checked-out code, generated files) and temp directory.
# runner のジョブ完了フック：このジョブの作業ディレクトリ（チェックアウトしたコード、生成物）と一時ディレクトリを空にする。
# Downloaded tools and package caches (_work/_tool, ~/.cache) are kept to make the next run faster; they come only from public sources.
# ダウンロード済みのツールとパッケージのキャッシュ（_work/_tool、~/.cache）は次回を速くするために残す。これらは公開ソースからしか来ない。
set -u
for d in "${GITHUB_WORKSPACE:-}" "${RUNNER_TEMP:-}"; do
  if [ -n "$d" ] && [ -d "$d" ]; then
    find "$d" -mindepth 1 -delete 2>/dev/null || true
  fi
done
exit 0
