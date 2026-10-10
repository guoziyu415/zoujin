"""不在 LFS 里的文件超过 1 MB 就红（dev-plan 2.4）。锁文件除外。

美术大文件按 .gitattributes 走 LFS；有人绕过 LFS 直接提交大文件时，这里拦住。
"""

import subprocess
import sys
from pathlib import Path

LIMIT = 1024 * 1024
EXEMPT = {"uv.lock", "pnpm-lock.yaml"}


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], check=True, capture_output=True).stdout
    return [p for p in out.decode().split("\0") if p]


def lfs_paths(paths: list[str]) -> set[str]:
    out = subprocess.run(
        ["git", "check-attr", "-z", "filter", "--stdin"],
        input="\0".join(paths).encode() + b"\0",
        check=True,
        capture_output=True,
    ).stdout.decode()
    parts = out.split("\0")
    return {parts[i] for i in range(0, len(parts) - 2, 3) if parts[i + 2] == "lfs"}


def main() -> int:
    paths = tracked_files()
    lfs = lfs_paths(paths)
    big = []
    for p in paths:
        if p in lfs or Path(p).name in EXEMPT:
            continue
        size = Path(p).stat().st_size if Path(p).is_file() else 0
        if size > LIMIT:
            big.append((p, size))
    for p, size in big:
        print(f"{p}: {size / LIMIT:.1f} MB，不在 LFS 里（超过 1 MB 的美术和音频文件要按 .gitattributes 走 LFS）")
    if big:
        return 1
    print(f"{len(paths)} 个文件，LFS 之外没有超过 1 MB 的")
    return 0


if __name__ == "__main__":
    sys.exit(main())
