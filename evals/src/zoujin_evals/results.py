"""Shape of the results: each check of each run of each case is one of pass, fail or skip (E-0 card item 2), and a skip
carries its reason.

結果の形：各ケースの各回の各チェックは合格・不合格・スキップのいずれか（E-0 カード第 2 条）で、スキップには理由が付く。
"""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

type Status = Literal["pass", "fail", "skip"]
type SkipCode = Literal["not-implemented", "needs-live-model", "replay-missing", "no-character-text", "timeout"]


class Skip(TypedDict):
    code: SkipCode
    # not-implemented: name of the step or query that is not implemented
    # not-implemented：未実装のステップまたはクエリの名前
    name: NotRequired[str]


class CheckResult(TypedDict):
    # which item in expect.deterministic, from 1; 0 for the judge
    # expect.deterministic の何番目か（1 から）。採点は 0
    index: int
    type: str  # the check's type; "judge" for the judge / チェックの type。採点は "judge"
    status: Status
    reason: NotRequired[str]  # why it failed (English / Japanese) / 不合格の理由（英語 / 日本語）
    skip: NotRequired[Skip]
    # judge: 1–5 (the rubric and pass condition are in the case's expect.judge)
    # 採点：1〜5（rubric と合格条件はケースの expect.judge にある）
    score: NotRequired[int]


class RunResult(TypedDict):
    run: int  # which run, from 1 / 何回目か（1 から）
    # One failing check means fail; no fail but some skip means skip; only all passing means pass.
    # 不合格が 1 つでもあれば不合格。不合格がなくスキップがあればスキップ。すべて合格して初めて合格。
    status: Status
    checks: list[CheckResult]
    judge: NotRequired[CheckResult]
    # this run did not complete at all: replay missing or stale, timeout
    # この回はまるごと完了しなかった：リプレイが無いか期限切れ、タイムアウト
    skip: NotRequired[Skip]
    # the backend raised an exception other than "not implemented": this run counts as failed
    # バックエンドが「未実装」以外の例外を投げた：この回は不合格とする
    error: NotRequired[str]
    traceIds: list[str]
    # simulated game: this game's ID (S-5's report script matches the ledger by it)
    # シミュレーション局：この局の ID（S-5 のレポートスクリプトはこれで台帳と照合する）
    playthroughId: NotRequired[str | None]
    # statistics of the simulated game (player.sim_stats) / シミュレーション局の統計（player.sim_stats）
    sim: NotRequired[dict[str, Any]]


class CaseResult(TypedDict):
    id: str
    suite: str
    title: str
    mode: str
    runs: int
    # has deletion steps (deleteMemory / deletePlaythrough): E6's hard metric counts only these cases
    # 削除ステップがある（deleteMemory / deletePlaythrough）：E6 の厳格な指標はこれらのケースだけを数える
    deletes: NotRequired[bool]
    # whole case skipped: the backend has not implemented setup or some step (the same every time, so only the first
    # run is tried)
    # ケースまるごとスキップ：バックエンドが setup かあるステップを未実装（毎回同じなので最初の 1 回だけ試す）
    skip: NotRequired[Skip]
    results: NotRequired[list[RunResult]]


class SkipCheck(Exception):
    """The check cannot be judged: skip it, with a reason.

    チェックが判定できない：理由付きでスキップする。
    """

    def __init__(self, skip: Skip) -> None:
        super().__init__(skip)
        self.skip = skip


def not_implemented(name: str) -> SkipCheck:
    return SkipCheck({"code": "not-implemented", "name": name})


def skip_label(s: Skip) -> tuple[str, str]:
    """How the report writes it, in English and in Japanese.

    レポートでの書き方（英語、日本語）。
    """
    match s["code"]:
        case "not-implemented":
            name = s.get("name", "?")
            return f"backend not implemented ({name})", f"バックエンド未実装（{name}）"
        case "needs-live-model":
            return "needs a real model", "実モデルが必要"
        case "replay-missing":
            return "replay missing or stale", "リプレイが無いか期限切れ"
        case "no-character-text":
            return "no character text", "原文なし"
        case "timeout":
            return "timeout", "タイムアウト"


def run_status(checks: list[CheckResult], judge: CheckResult | None = None) -> Status:
    """Nothing judged at all (a judge-only case run with deterministic checks only) is also a skip.

    何も判定されなかった場合（採点だけのケースを決定的チェックだけで実行したとき）もスキップ。
    """
    statuses = [c["status"] for c in checks] + ([judge["status"]] if judge else [])
    if "fail" in statuses:
        return "fail"
    return "skip" if "skip" in statuses or not statuses else "pass"
