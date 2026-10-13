"""Reviewer authorization must not unlock another image or an unprotected revision."""

from __future__ import annotations

import copy
import importlib.util

import pytest
from zoujin_backend.config import REPO

spec = importlib.util.spec_from_file_location("reviewer_access", REPO / "infra/deploy/reviewer_access.py")
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

RECORD = {
    "kind": "password-gated-reviewer-access",
    "gateway": "test-gateway",
    "image": "test-image",
    "revision": "test-revision",
    "passwordSecret": "zj-site-password",
    "gateChecks": "passed",
}
SERVICE = {
    "metadata": {"name": "test-gateway"},
    "spec": {
        "template": {
            "spec": {
                "containers": [
                    {
                        "image": "test-image",
                        "env": [
                            {
                                "name": "ZJ_SITE_PASSWORD",
                                "valueFrom": {"secretKeyRef": {"name": "zj-site-password", "key": "latest"}},
                            }
                        ],
                    }
                ]
            }
        }
    },
    "status": {
        "latestReadyRevisionName": "test-revision",
        "traffic": [{"percent": 100, "revisionName": "test-revision"}],
    },
}


def test_only_verified_release_is_authorized() -> None:
    assert module.authorized(RECORD, SERVICE, "test-gateway")
    assert not module.authorized(RECORD, SERVICE, "another-gateway")
    assert not module.authorized({}, SERVICE, "test-gateway")


@pytest.mark.parametrize("change", ["image", "revision", "password", "tag", "traffic", "iam"])
def test_unreviewed_or_unprotected_changes_require_private_iam(change: str) -> None:
    service = copy.deepcopy(SERVICE)
    container = service["spec"]["template"]["spec"]["containers"][0]
    if change == "image":
        container["image"] = "untested-image"
    elif change == "revision":
        service["status"]["latestReadyRevisionName"] = "old-revision"
    elif change == "password":
        container["env"] = []
    elif change == "tag":
        service["status"]["traffic"].append({"tag": "old", "revisionName": "old-unprotected-revision"})
    elif change == "traffic":
        service["status"]["traffic"][0]["percent"] = 99
    else:
        service["metadata"]["annotations"] = {"run.googleapis.com/invoker-iam-disabled": "true"}
    assert not module.authorized(RECORD, service, "test-gateway")
