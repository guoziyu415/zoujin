"""Shared helpers for the 走进物语 backend spikes.

Rules (pm/decisions.md D-011):
  - Everything runs in the new 走进物语 GCP project given by ZJ_PROJECT, never in 日々の森's project.
    Credentials are zg's own application-default login; the quota project is forced to ZJ_PROJECT
    in code, so the shared ADC file and the default gcloud configuration are never modified.
  - No API keys. Only model calls; no databases, services or buckets are created.
    The one config object we create (a Model Armor template) is named zoujin-* and deleted at the end.
  - Calls that accept labels carry app=zoujin-spike.
  - Spend is tracked locally from usage metadata and every script stops at the budget cap (US$20).
  - Serial, one call at a time; the first quota error (429 / RESOURCE_EXHAUSTED) stops the run.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

LABELS = {"app": "zoujin-spike"}

# Published list prices in USD per 1M tokens, checked 2026-10-06. We use the
# post-introductory price for gemini-3.8-flash so the estimate errs high.
PRICES = {
    "live": {"in_text": 0.75, "in_audio": 3.00, "out_text": 4.50, "out_audio": 12.00},
    "flash": {"in": 1.50, "out": 7.50},
    "model_armor": {"in": 0.10},
}

LEDGER_PATH = Path(os.environ.get("ZJ_LEDGER", Path.home() / ".zoujin-spike" / "ledger.json"))
BUDGET_USD = float(os.environ.get("ZJ_BUDGET_USD", "20"))


class BudgetExceeded(RuntimeError):
    pass


class QuotaHit(RuntimeError):
    """Raised on the first 429 / RESOURCE_EXHAUSTED. Never retried."""


@dataclass(frozen=True)
class Settings:
    project: str
    live_location: str
    text_location: str
    armor_location: str
    live_model: str
    text_model: str
    out_dir: Path


def settings() -> Settings:
    project = os.environ.get("ZJ_PROJECT")
    if not project:
        sys.exit("没有设置 ZJ_PROJECT。请先执行：export ZJ_PROJECT=你的项目ID（见 README 第 5 步）")
    out = Path(os.environ.get("ZJ_OUT", Path.cwd() / "out"))
    out.mkdir(parents=True, exist_ok=True)
    return Settings(
        project=project,
        live_location=os.environ.get("ZJ_LIVE_LOCATION", "us-central1"),
        text_location=os.environ.get("ZJ_TEXT_LOCATION", "global"),
        armor_location=os.environ.get("ZJ_ARMOR_LOCATION", "us-central1"),  # Tokyo has no multi-language detection (results-s1.md §6)
        live_model=os.environ.get("ZJ_LIVE_MODEL", "gemini-3.8-live"),
        text_model=os.environ.get("ZJ_TEXT_MODEL", "gemini-3.8-flash"),
        out_dir=out,
    )


def credentials():
    """zg's application-default credentials with the quota project forced to ZJ_PROJECT.

    The ADC file may name 日々の森's project as its quota project; overriding it here keeps
    every request billed and rate-limited in the 走进物语 project without editing that file.
    On Cloud Run (S-1b only) the service account already belongs to that project, and forcing a
    quota project there would need an extra permission, so it is left alone.

    With ZJ_IMPERSONATE_SA set (S-1b `sacheck`, on the Mac), zg's login only asks for a short-lived token of that
    service account; the model calls then carry the service account's identity and no quota project, exactly as on
    Cloud Run. No key is created.
    """
    import google.auth

    on_cloud_run = bool(os.environ.get("K_SERVICE"))
    creds, _ = google.auth.default(
        scopes=[CLOUD_PLATFORM],
        quota_project_id=None if on_cloud_run else settings().project,
    )
    target = os.environ.get("ZJ_IMPERSONATE_SA")
    if target and not on_cloud_run:
        from google.auth import impersonated_credentials

        return impersonated_credentials.Credentials(source_credentials=creds, target_principal=target,
                                                    target_scopes=[CLOUD_PLATFORM], lifetime=3600)
    return creds


CLOUD_PLATFORM = "https://www.googleapis.com/auth/cloud-platform"


def redact(text: object, project: str | None = None) -> str:
    """An upstream error message made safe for logs and the team: no project ID or number, address or account."""
    t = re.sub(r"https?://\S+", "[url]", str(text))
    t = re.sub(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", "[account]", t)
    if project:
        t = t.replace(project, "[project]")
    t = re.sub(r"projects/[^/\s'\"]+", "projects/[project]", t)
    t = re.sub(r"\d{6,}", "[number]", t)
    return t[:300]


def upstream_error(exc: BaseException) -> dict:
    """Close code / status / redacted message of a failed model call, for the service log (S-1b part 2: the third
    attempt failed with a bare APIError and nothing else to go on)."""
    code = getattr(exc, "code", None)
    status = getattr(exc, "status", None)
    text = getattr(exc, "details", None)
    if not isinstance(text, str):
        text = getattr(exc, "message", None) or str(exc)
    return {"upstreamCode": code if isinstance(code, int) and not isinstance(code, bool) else None,
            "upstreamStatus": status if isinstance(status, str) and re.fullmatch(r"[A-Z_]{1,40}", status) else None,
            "upstreamMessage": redact(text, os.environ.get("ZJ_PROJECT"))}


def upstream_kind(exc: BaseException) -> str:
    """One fixed word for what kind of upstream failure this was; the only part the phone is told."""
    code = getattr(exc, "code", None)
    text = f"{getattr(exc, 'status', None) or ''} {exc}".upper()
    if is_quota_error(exc):
        return "quota"
    if code in (401, 403) or "PERMISSION" in text or "UNAUTHENTICATED" in text:
        return "permission"
    if code == 404 or "NOT_FOUND" in text or "NOT FOUND" in text:
        return "not_found"
    if code == 1008:
        return "policy"
    if code in (400, 1007) or "INVALID" in text:
        return "invalid"
    if code in (500, 502, 503, 504, 1006, 1011) or "UNAVAILABLE" in text:
        return "unavailable"
    return "other"


def genai_client(location: str):
    from google import genai

    s = settings()
    return genai.Client(enterprise=True, project=s.project, location=location, credentials=credentials())


# ---------------------------------------------------------------- budget ledger


def _load() -> dict:
    if LEDGER_PATH.exists():
        return json.loads(LEDGER_PATH.read_text())
    return {"total_usd": 0.0, "entries": []}


def spent() -> float:
    return float(_load()["total_usd"])


def check_budget(reserve_usd: float = 0.05) -> None:
    """Refuse to start another call if it could cross the cap."""
    total = spent()
    if total + reserve_usd >= BUDGET_USD:
        raise BudgetExceeded(f"spent ${total:.4f} of ${BUDGET_USD:.2f}; stopping")


def charge(usd: float, what: str) -> float:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = _load()
    data["total_usd"] = round(float(data["total_usd"]) + usd, 6)
    data["entries"].append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "usd": round(usd, 6), "what": what})
    LEDGER_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    if data["total_usd"] >= BUDGET_USD:
        raise BudgetExceeded(f"spent ${data['total_usd']:.4f} of ${BUDGET_USD:.2f}; stopping")
    return data["total_usd"]


def live_usage_cost(usage) -> float:
    """Price one Live usage_metadata block. Unknown modalities are priced at the higher rate."""
    if usage is None:
        return 0.0
    p = PRICES["live"]
    cost = 0.0
    details_in = usage.prompt_tokens_details or []
    if details_in:
        for d in details_in:
            rate = p["in_text"] if str(d.modality).endswith("TEXT") else p["in_audio"]
            cost += (d.token_count or 0) * rate
    else:
        cost += (usage.prompt_token_count or 0) * p["in_audio"]
    details_out = usage.response_tokens_details or []
    if details_out:
        for d in details_out:
            rate = p["out_text"] if str(d.modality).endswith("TEXT") else p["out_audio"]
            cost += (d.token_count or 0) * rate
    else:
        cost += (usage.response_token_count or 0) * p["out_audio"]
    cost += (usage.thoughts_token_count or 0) * p["out_text"]
    return cost / 1_000_000


def flash_usage_cost(usage) -> float:
    if usage is None:
        return 0.0
    p = PRICES["flash"]
    out = (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)
    return ((usage.prompt_token_count or 0) * p["in"] + out * p["out"]) / 1_000_000


# ---------------------------------------------------------------- 429 handling


def is_quota_error(exc: BaseException) -> bool:
    text = f"{type(exc).__name__} {exc}"
    code = getattr(exc, "code", None)
    markers = ("429", "RESOURCE_EXHAUSTED", "ResourceExhausted", "TooManyRequests", "quota exceeded", "Quota exceeded")
    return code == 429 or any(m in text for m in markers)


def stop_on_quota(exc: BaseException) -> None:
    if is_quota_error(exc):
        raise QuotaHit(f"quota error, stopping all spike calls: {exc}") from exc


def banner(title: str) -> None:
    print(f"\n=== {title} ===  (spent so far ${spent():.4f} / ${BUDGET_USD:.2f})", flush=True)


# ---------------------------------------------------------------- results


def percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile; None for an empty list."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100 * len(ordered)))
    return ordered[rank - 1]


def summarize_ms(values: list[float]) -> dict:
    vals = [v for v in values if v is not None]
    if not vals:
        return {"n": 0}
    return {
        "n": len(vals),
        "min": min(vals),
        "p50": percentile(vals, 50),
        "p90": percentile(vals, 90),
        "p95": percentile(vals, 95),
        "max": max(vals),
    }


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str))


def run(main) -> None:
    """Run an async main and turn our two stop conditions into a clear message and exit code."""
    try:
        asyncio.run(main())
    except BudgetExceeded as e:
        print(f"\n[停止] 已到预算上限：{e}。结果已写到 out/，账本在 {LEDGER_PATH}。", file=sys.stderr)
        sys.exit(3)
    except QuotaHit as e:
        print(f"\n[停止] 遇到配额限制（429），按规则立即停止，不重试：{e}", file=sys.stderr)
        sys.exit(4)
    except KeyboardInterrupt:
        print("\n[停止] 手动中断。", file=sys.stderr)
        sys.exit(130)
