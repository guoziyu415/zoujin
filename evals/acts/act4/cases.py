"""第4幕「三日目」的测评用例（清单第 14 步）和模拟局画像（第 15 步）。改这里，再跑：
    python3 -I evals/acts/act4/cases.py
写出同目录的 E*.jsonl、personas.json（生成物，不要手改）。ID：用例 E?-401〜499，画像 persona.a4-…。
写法同 evals/gen_seeds.py（helpers.py 里是同一套）；说明见 evals/acts/README.md。
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from helpers import APP, BOY, JP, TRAV, WU, J, case, comp, nm, no_terms, say, write  # noqa: E402,F401

CASES: list[dict] = []

PERSONAS: list[dict] = []

if __name__ == "__main__":
    write(4, CASES, PERSONAS, HERE)
