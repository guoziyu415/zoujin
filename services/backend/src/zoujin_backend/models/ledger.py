"""The ledger (B-2 card "ledger", dev-plan Z-8): real clients check it before every call and record to it after. Since
B-8 the ledger class lives in the shared package `zoujin_llm.ledger` (the same class for the narrator and the data
team's judge); what remains here is how the Google ledger is written and its prices.

- One JSONL file: both ledgers, E-0 live and the judge all record into the same file with the same kind of line (see
  `zoujin_llm.ledger`): Z-8's caps are shared by the backend's prompt tuning, S-2, evals and S-5, and the total cap is
  compared with the cumulative amount already in the file plus this call, not just this run.
- Before a call, the cap is checked with the estimated cost (estimated from the input length and the output cap, on the
  high side); when reached, `BudgetStop` is raised and this call is not sent; after a call, the actual cost is recorded.
- The total cap counts only that provider's own lines; the per-item cap is checked only when `item` is given: the same
  item across both ledgers (data #49).
- Every line carries `use`: the narrator's steps, pre-recorded lines and Live are "product", also when run in an eval
  (S-5's per-playthrough cost adds up only product).

台帳（B-2 カード「台帳」、dev-plan Z-8）：実クライアントは呼び出しのたびに事前に確認し、事後に記録する。B-8 から台帳の
クラスは共用パッケージ `zoujin_llm.ledger` にあり（ナレーターとデータ担当の審査員で同じクラス）、ここには Google
の台帳の書き方と単価を残している。

- JSONL ファイルは 1 つ。2 つの台帳、E-0 live、審査員はすべて同じファイルに同じ種類の行で記録する（`zoujin_llm.ledger`
  の説明を参照）：Z-8 の上限はバックエンドのプロンプト調整、S-2、評価、S-5 で共用し、総上限はファイルにすでにある累計に
  今回の分を足して比べる。今回の実行分だけではない。
- 呼び出し前は見積もり費用（入力の長さと出力の上限から見積もり、高め）で上限を判定し、達したら `BudgetStop` を投げて
  今回は送らない。呼び出し後は実際の費用を記録する。
- 総上限はそのプロバイダ自身の行だけを数える。項目ごとの上限は `item` が与えられたときだけ判定する：同じ item の 2 つの
  台帳の合計（データ #49）。
- 各行に `use` が付く：ナレーターの各ステップ、事前収録セリフ、Live は "product"。評価の中で実行しても同じ（S-5 の
  1 周回あたりのコストは product だけを足す）。
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from zoujin_llm import Ledger as _Ledger

from zoujin_backend.config import PRICES, REGIONAL_MARKUP

PROVIDER = "google"


def cost_usd(model: str, usage: Mapping[str, int], *, regional: bool) -> float:
    """Cost = usage × price (config.PRICES). Thinking tokens count as output; cache-hit input is charged at the cached
    price.

    費用 = 使用量 × 単価（config.PRICES）。思考トークンは出力として数え、
    キャッシュにヒットした入力はキャッシュ単価で数える。
    """
    p = PRICES[model]
    cached = usage.get("cachedTokens", 0)
    fresh = max(0, usage.get("inputTokens", 0) - cached)
    out = usage.get("outputTokens", 0) + usage.get("thoughtTokens", 0)
    usd = (fresh * p["input"] + cached * p["cachedInput"] + out * p["output"]) / 1_000_000
    return usd * (REGIONAL_MARKUP if regional else 1.0)


class Ledger(_Ledger):
    """The Google ledger (the shared ledger class with provider google). The constructor arguments are the same as in
    B-2; B-6's pre-recorded lines also use it.

    Google の台帳（共用の台帳クラスで、provider は google）。コンストラクタの引数は B-2 のときと同じで、B-6 の事前収録
    セリフもこれを使う。
    """

    def __init__(
        self,
        path: Path,
        max_total_usd: float,
        max_item_usd: float | None = None,
        item: str | None = None,
        use: str = "product",
    ) -> None:
        super().__init__(path, PROVIDER, max_total_usd, max_item_usd, item, use)

    def spent(self, item: str | None = None) -> float:
        """Without item: the Google ledger's cumulative cost (total cap). With item: this item's cost across both
        ledgers (per-item cap).

        item なし：Google の台帳の累計（総上限）。item あり：この項目の 2 つの台帳を合わせた費用（項目ごとの上限）。
        """
        return self.spent_total() if item is None else self.spent_on(item)
