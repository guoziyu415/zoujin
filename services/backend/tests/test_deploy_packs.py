"""Shared scene packs can be merged from different pipelines; an explanatory note must not bypass validation of the
actual structure or inputs.

共有のシーンパックは別々のパイプラインからマージできる。説明用の note で実際の構造や inputs の検証を回避してはならない。
"""

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
