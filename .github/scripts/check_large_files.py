"""不在 LFS 里的文件超过 1 MB 就红（dev-plan 2.4）。锁文件除外。

美术大文件按 .gitattributes 走 LFS；有人绕过 LFS 直接提交大文件时，这里拦住。预录音频（assets/voice/）走普通 git
（S-084），同样受 1 MB 管着。
匹配 LFS 规则的路径，进 git 的必须是 LFS 指针：没装 git-lfs 的地方提交 glb，会当普通文件进 git（S-075 ③）。
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


LFS_POINTER = b"version https://git-lfs.github.com/spec/v1"


def not_pointers(paths: set[str]) -> list[str]:
    """匹配 LFS 规则、但 git 里存的不是 LFS 指针的文件（看暂存区里的内容，不看工作区）。"""
    bad = []
    for p in sorted(paths):
        # the first bytes are enough; git-lfs stores an empty file as an empty blob, not a pointer
        with subprocess.Popen(["git", "cat-file", "blob", f":{p}"], stdout=subprocess.PIPE) as proc:
            head = proc.stdout.read(len(LFS_POINTER))
            proc.kill()
        if head and not head.startswith(LFS_POINTER):
            bad.append(p)
    return bad


def main() -> int:
    paths = tracked_files()
    lfs = lfs_paths(paths)
    raw = not_pointers(lfs)
    for p in raw:
        print(f"{p}：匹配 LFS 规则，但进 git 的不是 LFS 指针（没装 git-lfs？生成物不进仓库，S-075）")
    big = []
    for p in paths:
        if p in lfs or Path(p).name in EXEMPT:
            continue
        size = Path(p).stat().st_size if Path(p).is_file() else 0
        if size > LIMIT:
            big.append((p, size))
    for p, size in big:
        if p.startswith("assets/voice/"):
            # 预录音频走普通 git（S-084），一条应该只有几十 KB：超过 1 MB 多半是没转 AAC（WAV 原样进来了）
            print(f"{p}: {size / LIMIT:.1f} MB。预录音频不走 LFS，要用 zoujin-voice 转好的 .m4a（每条远小于 1 MB）")
            continue
        print(f"{p}: {size / LIMIT:.1f} MB，不在 LFS 里（超过 1 MB 的美术和音频文件要按 .gitattributes 走 LFS）")
    if big or raw:
        return 1
    print(f"{len(paths)} 个文件，LFS 之外没有超过 1 MB 的")
    return 0


if __name__ == "__main__":
    sys.exit(main())
