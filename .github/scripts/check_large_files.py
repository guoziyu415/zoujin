"""Fail when a file outside LFS is larger than 1 MB (dev-plan 2.4). Lock files are exempt.

Large art files go through LFS per .gitattributes; this catches anyone committing a large file while bypassing LFS.
Pre-recorded lines (assets/voice/) go through plain git (S-084) and are subject to the same 1 MB limit.
Paths matching an LFS rule must enter git as LFS pointers: a glb committed where git-lfs is not installed would enter
git as a regular file (S-075 ③).

LFS 外のファイルが 1 MB を超えたら失敗にする（dev-plan 2.4）。ロックファイルは除外。

大きな美術ファイルは .gitattributes に従って LFS を通す。LFS を迂回して大きなファイルをコミットした場合にここで止める。
事前収録セリフ（assets/voice/）は通常の git を通る（S-084）が、同じく 1 MB の制限を受ける。
LFS ルールに一致するパスは、LFS ポインタとして git に入らなければならない：git-lfs をインストールしていない環境で glb を
コミットすると、通常のファイルとして git に入ってしまう（S-075 ③）。
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
    """Files that match an LFS rule but are not stored in git as LFS pointers (checks the index, not the worktree).

    LFS ルールに一致するのに、git に LFS ポインタとして保存されていないファイル
    （作業ツリーではなくインデックスの内容を見る）。
    """
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
        print(
            f"{p}: matches an LFS rule, but what entered git is not an LFS pointer"
            " (git-lfs not installed? generated files stay out of the repo, S-075)"
            " / LFS ルールに一致するが、git に入ったものが LFS ポインタではない"
            "（git-lfs 未インストール？生成物はリポジトリに入れない、S-075）"
        )
    big = []
    for p in paths:
        if p in lfs or Path(p).name in EXEMPT:
            continue
        size = Path(p).stat().st_size if Path(p).is_file() else 0
        if size > LIMIT:
            big.append((p, size))
    for p, size in big:
        if p.startswith("assets/voice/"):
            # Pre-recorded lines go through plain git (S-084) and each should be only tens of KB: over 1 MB usually
            # means it was not converted to AAC (the WAV came in as is)
            # 事前収録セリフは通常の git を通る（S-084）。1 本数十 KB のはずで、1 MB 超はたいてい AAC に変換していない
            # （WAV がそのまま入った）
            print(
                f"{p}: {size / LIMIT:.1f} MB. Pre-recorded lines do not use LFS; use the .m4a converted by"
                " zoujin-voice (each well under 1 MB)"
                f" / {size / LIMIT:.1f} MB。事前収録セリフは LFS を使わない。zoujin-voice で変換した .m4a を使うこと"
                "（1 本あたり 1 MB を大きく下回る）"
            )
            continue
        print(
            f"{p}: {size / LIMIT:.1f} MB, not in LFS (art and audio files over 1 MB must go through LFS per"
            " .gitattributes) / LFS に入っていない（1 MB を超える美術・音声ファイルは .gitattributes に従って LFS を"
            "通すこと）"
        )
    if big or raw:
        return 1
    print(f"{len(paths)} files, none over 1 MB outside LFS / {len(paths)} ファイル、LFS 外に 1 MB 超はなし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
