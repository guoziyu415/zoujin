"""查已知不能出现的值有没有漏进仓库（可选，PR 和推到 main 时都跑）。

值来自 Actions secret KNOWN_IDS（一行一个：项目 ID、项目号、账单 ID 等），只在 CI 的环境变量里，
不进仓库、不打印：命中时只报文件和行号。没设这个 secret 就跳过。
"""

import os
import subprocess
import sys


def main() -> int:
    values = [v.strip().lower() for v in os.environ.get("KNOWN_IDS", "").splitlines() if v.strip()]
    if not values:
        print("没有设 KNOWN_IDS，跳过")
        return 0
    out = subprocess.run(["git", "ls-files", "-z"], check=True, capture_output=True).stdout
    hits = 0
    for path in (p for p in out.decode().split("\0") if p):
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                for n, line in enumerate(f, 1):
                    low = line.lower()
                    for i, v in enumerate(values, 1):
                        if v in low:
                            print(f"{path}:{n}: 命中第 {i} 个已知值")
                            hits += 1
        except (IsADirectoryError, FileNotFoundError):
            continue
    if hits:
        print(f"共 {hits} 处。把这些值从文件里去掉；已经推上去的，告诉 PM。")
        return 1
    print(f"查了 {len(values)} 个已知值，没有命中")
    return 0


if __name__ == "__main__":
    sys.exit(main())
