"""共享场景包可由不同管线合并；说明性 note 不得绕过实际结构或 inputs 校验。"""

from __future__ import annotations

import json
import runpy

from zoujin_backend.config import REPO

same_build = runpy.run_path(str(REPO / "infra/deploy/packs.py"))["same_build"]


def test_only_top_level_provenance_note_is_ignored() -> None:
    a = {"note": "village generator", "files": [{"path": "tex/a.ktx2"}], "textures": {"grass": "tex/a.ktx2"}}
    b = {**a, "note": "road generator"}
    assert same_build(json.dumps(a).encode(), json.dumps(b).encode())
    for wrong in (
        {**b, "files": [{"path": "tex/missing.ktx2"}]},
        {**b, "textures": {}},
        {**b, "files": [{"path": "tex/a.ktx2", "note": "nested change"}]},
    ):
        assert not same_build(json.dumps(a).encode(), json.dumps(wrong).encode())


def test_input_hashes_still_require_exact_match() -> None:
    a = {"note": "village generator", "inputs": {"layout": "hash-a"}}
    b = {"note": "road generator", "inputs": {"layout": "hash-b"}}
    assert not same_build(json.dumps(a).encode(), json.dumps(b).encode())
