"""真实 Bash 控制流、假的 gcloud：访问状态未知时关闭，匿名门禁未通过时不能标记部署完成。"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path

import pytest
from zoujin_backend.config import REPO

SERVICE = {"metadata": {"name": "test-gateway", "annotations": {}}}
STUB = r"""
GW=test-gateway NR=test-narrator IMAGE=test-image CANDIDATE=test-image
PA=(--project=test-only)
gcloud() {
  case "$1 ${2:-} ${3:-}" in
    'run services list') [[ "$FAIL_LIST" == 0 ]] || return 71; printf '%s' "$SERVICE_JSON" ;;
    'run services get-iam-policy') [[ "$FAIL_POLICY" == 0 ]] || return 72; printf '%s' "$POLICY_JSON" ;;
    'auth print-identity-token ') [[ "$FAIL_TOKEN" == 0 ]] || return 73; printf '%s' "$TOKEN" ;;
    *) return 99 ;;
  esac
}
guard() { :; }
run() { printf 'TRAFFIC\n'; }
url_of() { printf 'http://example.invalid\n'; }
sleep() { :; }
save() { printf 'SAVED %s\n' "$1"; }
ANON_COUNT=0
smoke() {
  if [[ "$1" == anon ]]; then
    ANON_COUNT=$((ANON_COUNT + 1))
    printf 'attempt\n' >>"$STATE/attempts"
    [[ $ANON_COUNT -ge $ANON_PASS_AT ]]
  else
    printf 'FULL_SMOKE\n'
  fi
}
"""


def shell(tmp_path: Path, command: str, **overrides: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "ZJ_DEPLOY_DIR": str(tmp_path),
        "SERVICE_JSON": json.dumps([SERVICE]),
        "POLICY_JSON": '{"bindings":[]}',
        "FAIL_LIST": "0",
        "FAIL_POLICY": "0",
        "FAIL_TOKEN": "0",
        "TOKEN": "test-only-identity",
        "ANON_PASS_AT": "1",
        **overrides,
    }
    script = f"source {shlex.quote(str(REPO / 'infra/deploy/deploy.sh'))}\n{STUB}\n{command}\n"
    return subprocess.run(["bash", "-c", script], env=env, text=True, capture_output=True, timeout=5)


@pytest.mark.parametrize(
    "overrides",
    [
        {"FAIL_LIST": "1"},
        {"FAIL_POLICY": "1"},
        {"SERVICE_JSON": "not-json"},
        {"SERVICE_JSON": "[{}]"},
        {"POLICY_JSON": "not-json"},
        {"POLICY_JSON": '{"bindings":[{"members":"allUsers"}]}'},
    ],
)
def test_unknown_access_never_becomes_private_or_changes_traffic(tmp_path: Path, overrides: dict[str, str]) -> None:
    result = shell(tmp_path, "cmd_promote", **overrides)
    assert result.returncode != 0
    assert "TRAFFIC" not in result.stdout and "SAVED DEPLOYED" not in result.stdout


@pytest.mark.parametrize("member", ["allUsers", "allAuthenticatedUsers"])
def test_public_members_are_blocked_by_the_privacy_lock(tmp_path: Path, member: str) -> None:
    (tmp_path / "privacy-lock.json").write_text("{}")
    policy = json.dumps({"bindings": [{"role": "roles/run.invoker", "members": [member]}]})
    result = shell(tmp_path, "cmd_promote", POLICY_JSON=policy)
    assert result.returncode != 0 and "TRAFFIC" not in result.stdout


@pytest.mark.parametrize("v2", [False, True])
def test_disabled_invoker_check_is_public_even_without_public_members(tmp_path: Path, v2: bool) -> None:
    (tmp_path / "privacy-lock.json").write_text("{}")
    service = json.loads(json.dumps(SERVICE))
    if v2:
        service["invokerIamDisabled"] = True
    else:
        service["metadata"]["annotations"]["run.googleapis.com/invoker-iam-disabled"] = "true"
    result = shell(tmp_path, "cmd_promote", SERVICE_JSON=json.dumps([service]))
    assert result.returncode != 0 and "TRAFFIC" not in result.stdout


def test_successful_empty_list_is_allowed_only_before_first_up(tmp_path: Path) -> None:
    result = shell(tmp_path, "privacy_check allow-missing", SERVICE_JSON="[]", FAIL_POLICY="1")
    assert result.returncode == 0
    assert shell(tmp_path, "cmd_promote", SERVICE_JSON="[]").returncode != 0


@pytest.mark.parametrize("overrides", [{"FAIL_TOKEN": "1"}, {"TOKEN": ""}])
def test_private_access_requires_a_valid_identity_token(tmp_path: Path, overrides: dict[str, str]) -> None:
    assert shell(tmp_path, "gateway_bearer", **overrides).returncode != 0
    assert shell(tmp_path, "gateway_bearer").stdout == "test-only-identity"


def test_six_failed_anonymous_checks_stop_before_full_smoke_or_deployed(tmp_path: Path) -> None:
    result = shell(tmp_path, "cmd_promote", ANON_PASS_AT="7")
    assert result.returncode != 0
    assert "FULL_SMOKE" not in result.stdout and "SAVED DEPLOYED" not in result.stdout
    assert (tmp_path / "attempts").read_text().splitlines() == ["attempt"] * 6


def test_successful_sixth_check_allows_full_smoke_and_deployed(tmp_path: Path) -> None:
    result = shell(tmp_path, "cmd_promote", ANON_PASS_AT="6")
    assert result.returncode == 0
    assert "FULL_SMOKE" in result.stdout and "SAVED DEPLOYED" in result.stdout
    assert (tmp_path / "attempts").read_text().splitlines() == ["attempt"] * 6
