"""Narration receives what was attempted and only results which passed validation."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import cast

from zoujin_backend.ids import IdGen
from zoujin_backend.models.text import FakeText
from zoujin_backend.narrator.actions import Decision, Outcome, narrate
from zoujin_backend.narrator.core import Narrator
from zoujin_backend.narrator.pipeline import Pipeline, Spend
from zoujin_backend.narrator.rules import Checked
from zoujin_worldsim import initial_state

from .conftest import SCHEMAS
from .test_brief import BOOK


def test_partial_narration_gets_specific_action_and_excludes_rejected_result() -> None:
    model = FakeText()
    pipeline = Pipeline(model, SCHEMAS, IdGen())
    narrator = cast(Narrator, SimpleNamespace(pipeline=pipeline))
    attempted = "花婿の婚礼の支度を手伝う"
    completed = "花婿の家へ衣裳を運んだ"
    rejected = "花婿の婚礼を取りやめた"
    decision = Decision(
        "affordance",
        "help",
        "char.groom",
        affordance={"label": attempted},
        checked=[
            Checked({"summary": completed}, [], {"status": "downgraded"}),
            Checked({"summary": rejected}, [], {"status": "rejected"}),
        ],
    )
    asyncio.run(
        narrate(
            narrator,
            BOOK,
            initial_state(BOOK.world, "role.traveler"),
            decision,
            Outcome("partial", 0, None, []),
            Spend(),
            {},
        )
    )
    kind, request = model.calls[-1]
    assert kind == "narrate"
    assert request["act"]["intendedAction"] == attempted
    assert request["act"]["completedActions"] == [completed]
    assert rejected not in str(request["act"])
