"""Only the explicitly authorized, password-checked release may serve reviewers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def authorized(record: dict[str, Any], service: dict[str, Any], gateway: str) -> bool:
    try:
        container = service["spec"]["template"]["spec"]["containers"][0]
        status = service["status"]
        env = {item["name"]: item for item in container.get("env", [])}
        secret = env["ZJ_SITE_PASSWORD"]["valueFrom"]["secretKeyRef"]
        annotations = service["metadata"].get("annotations", {})
        return bool(
            record["kind"] == "password-gated-reviewer-access"
            and record["gateway"] == gateway == service["metadata"]["name"]
            and record["image"] == container["image"]
            and record["revision"] == status["latestReadyRevisionName"]
            and record["passwordSecret"] == secret["name"] == "zj-site-password"
            and secret.get("key")
            and record["gateChecks"] == "passed"
            and str(annotations.get("run.googleapis.com/invoker-iam-disabled", False)).lower() != "true"
            and not service.get("invokerIamDisabled", False)
            and sum(item.get("percent", 0) for item in status["traffic"]) == 100
            and any(
                item.get("percent") == 100 and item.get("revisionName") == record["revision"]
                for item in status["traffic"]
            )
            and not any(item.get("tag") for item in status["traffic"])
        )
    except (KeyError, TypeError, IndexError, AttributeError):
        return False


if __name__ == "__main__":
    try:
        record = json.loads(Path(sys.argv[1]).read_text())
        service = json.load(sys.stdin)
        ok = authorized(record, service, sys.argv[2])
    except (OSError, ValueError, IndexError):
        ok = False
    sys.exit(0 if ok else 1)
