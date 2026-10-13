"""Reading cases: evals/seeds/E*.jsonl, one case per line (format in evals/README.md, already validated by
check_evals).

ケースの読み込み：evals/seeds/E*.jsonl、1 行 1 例（形式は evals/README.md、check_evals で検証済み）。
"""

from __future__ import annotations

import json
from collections.abc import Collection
from pathlib import Path
from typing import Any


def load_cases(directory: Path, *, suites: Collection[str] = (), ids: Collection[str] = ()) -> list[dict[str, Any]]:
    """Read in order of file name and line; when suites / ids are given, keep only those.

    ファイル名と行の順に読む。suites / ids が与えられたらそれだけを残す。
    """
    files = sorted(directory.glob("E*.jsonl"))
    if not files:
        raise FileNotFoundError(f"No E*.jsonl under {directory} / {directory} の下に E*.jsonl がない")
    cases = []
    for f in files:
        for ln, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                c = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{f.name}:{ln} is not valid JSON / 正しい JSON ではない: {e}") from e
            if (not suites or c["suite"] in suites) and (not ids or c["id"] in ids):
                cases.append(c)
    unknown = set(ids) - {c["id"] for c in cases}
    if unknown:
        raise ValueError(f"No such cases / そのようなケースはない: {sorted(unknown)}")
    return cases
