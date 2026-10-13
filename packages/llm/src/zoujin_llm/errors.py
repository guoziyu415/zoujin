"""Errors shared by both sides. Messages contain only status codes and our own wording, never the original SDK or HTTP
message (which may contain a project ID or fragments of a key).

両者で共用するエラー。メッセージにはステータスコードと自前の文言だけを入れ、SDK や HTTP の元のメッセージ（プロジェクト
ID やキーの断片が含まれうる）は入れない。
"""

from __future__ import annotations

import os
from pathlib import Path


class Stop(Exception):
    """Errors that stop the whole run (the runner does not skip this case, it stops): `BudgetStop`, `RateLimited`.

    実行全体を止めるエラー（ランナーはこのケースをスキップせずに停止する）：`BudgetStop`、`RateLimited`。
    """


class BudgetStop(Stop):
    """The ledger reached its cap (per item or total); this call was not sent.

    台帳が上限（項目ごとまたは合計）に達し、この呼び出しは送られなかった。
    """


class RateLimited(Stop):
    """The model returned 429 or 529 (rate limited, overloaded). Runs on the Mac stop at the first one, with no
    automatic retry (S-079).

    モデルが 429 または 529 を返した（レート制限、過負荷）。Mac 上の実行は最初の 1 回で止まり、自動では再試行しない
    （S-079）。
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        status: int | None = None,
        retry_after: str | None = None,
    ) -> None:
        super().__init__(message)
        self.diagnostics: dict[str, str | int] = {}
        if provider in ("google", "claude"):
            self.diagnostics["provider"] = provider
        if status in (429, 529):
            self.diagnostics["httpStatus"] = status
        # Accept only a number of seconds; do not keep the provider's original text, project, model or any response
        # header.
        # 数字の秒数だけを受け取る。プロバイダの原文、プロジェクト、モデル、任意のレスポンスヘッダーは保存しない。
        if retry_after and retry_after.isascii() and retry_after.isdecimal() and len(retry_after) <= 8:
            self.diagnostics["retryAfterSeconds"] = int(retry_after)


class ModelCallFailed(RuntimeError):
    """The model call failed (another HTTP error, a dropped connection); it is resent once under the time-limit rules.
    The message contains only the HTTP status code.

    モデル呼び出しが失敗した（その他の HTTP エラー、ネットワーク切断）。時間制限の規則に従って 1 回だけ再送する。
    メッセージは HTTP ステータスコードだけ。
    """


class BatchHalted(Stop):
    """Another worker of a bounded eval has stopped; in-flight requests are not cancelled, and no new requests are made.

    上限付き評価の別の worker が停止した。処理中のリクエストは取り消さず、新しいリクエストも出さない。
    """


def check_batch_halt() -> None:
    marker = os.environ.get("ZJ_EVAL_BATCH_HALT")
    if marker and Path(marker).exists():
        raise BatchHalted(
            "Batch halted; keeping this playthrough's evidence and making no more model calls / "
            "バッチは停止した。この周回の証拠を残し、これ以上モデルを呼び出さない"
        )
