"""Check whether known values that must not appear have leaked into the repo (optional; runs on PRs and pushes to main).

The values come from the Actions secret KNOWN_IDS (one per line: project ID, project number, billing ID, etc.). They
live only in CI environment variables, never in the repo, and are never printed: a hit reports only file and line
number. Skipped if the secret is not set.

リポジトリに含まれてはいけない既知の値が紛れ込んでいないかを調べる（任意。PR と main への push の両方で実行）。

値は Actions secret KNOWN_IDS から来る（1 行に 1 つ：プロジェクト ID、プロジェクト番号、請求先 ID など）。CI の
環境変数にだけ存在し、リポジトリには入れず、出力もしない：ヒットしたときはファイルと行番号だけを報告する。
この secret が未設定ならスキップする。
"""

import os
import subprocess
import sys


def main() -> int:
    values = [v.strip().lower() for v in os.environ.get("KNOWN_IDS", "").splitlines() if v.strip()]
    if not values:
        print("KNOWN_IDS not set, skipping / KNOWN_IDS が未設定のためスキップ")
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
                            print(f"{path}:{n}: matches known value #{i} / 既知の値 #{i} にヒット")
                            hits += 1
        except (IsADirectoryError, FileNotFoundError):
            continue
    if hits:
        print(
            f"{hits} hit(s) in total. Remove these values from the files; if already pushed, tell the PM."
            f" / 合計 {hits} 件。これらの値をファイルから削除すること。すでに push 済みなら PM に伝えること。"
        )
        return 1
    print(f"Checked {len(values)} known value(s), no hits / 既知の値 {len(values)} 件を確認、ヒットなし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
