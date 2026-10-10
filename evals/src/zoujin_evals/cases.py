"""读用例：evals/seeds/E*.jsonl，一行一例（格式见 evals/README.md，check_evals 已校验）。"""

from __future__ import annotations

import json
from collections.abc import Collection
from pathlib import Path
from typing import Any


def load_cases(directory: Path, *, suites: Collection[str] = (), ids: Collection[str] = ()) -> list[dict[str, Any]]:
    """按文件名、行的先后读；给了 suites / ids 就只留这些。"""
    files = sorted(directory.glob("E*.jsonl"))
    if not files:
        raise FileNotFoundError(f"{directory} 下没有 E*.jsonl")
    cases = []
    for f in files:
        for ln, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                c = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{f.name}:{ln} 不是合法的 JSON：{e}") from e
            if (not suites or c["suite"] in suites) and (not ids or c["id"] in ids):
                cases.append(c)
    unknown = set(ids) - {c["id"] for c in cases}
    if unknown:
        raise ValueError(f"没有这些用例：{sorted(unknown)}")
    return cases
