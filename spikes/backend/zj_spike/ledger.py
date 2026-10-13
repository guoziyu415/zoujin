"""Print the local spend ledger: uv run python -m zj_spike.ledger"""

from collections import defaultdict

from . import common


def main() -> None:
    data = common._load()
    by: dict = defaultdict(float)
    for e in data["entries"]:
        by[" ".join(e["what"].split()[:2])] += e["usd"]
    print(f"Ledger / 台帳: {common.LEDGER_PATH}")
    for k, v in sorted(by.items(), key=lambda kv: -kv[1]):
        print(f"  {k:24s} ${v:.4f}")
    print(
        f"Total / 合計 ${data['total_usd']:.4f}, cap / 上限 ${common.BUDGET_USD:.2f} "
        "(estimated from public list prices; the console bill is authoritative / 公開価格による概算。正確な金額はコンソールの請求を参照)"
    )


if __name__ == "__main__":
    main()
