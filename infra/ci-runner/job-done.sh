#!/usr/bin/env bash
# runner 的 job 完成钩子：清掉这个 job 的工作目录（检出的代码、生成物）和临时目录。
# 下载过的工具和包缓存（_work/_tool、~/.cache）留着，下次快一些；它们只来自公开的源。
set -u
for d in "${GITHUB_WORKSPACE:-}" "${RUNNER_TEMP:-}"; do
  if [ -n "$d" ] && [ -d "$d" ]; then
    find "$d" -mindepth 1 -delete 2>/dev/null || true
  fi
done
exit 0
