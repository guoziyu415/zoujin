"""Print the local spend ledger: uv run python -m zj_spike.ledger"""

from collections import defaultdict

from . import common


def main() -> None:
    data = common._load()
    by: dict = defaultdict(float)
    for e in data["entries"]:
        by[" ".join(e["what"].split()[:2])] += e["usd"]
    print(f"账本：{common.LEDGER_PATH}")
    for k, v in sorted(by.items(), key=lambda kv: -kv[1]):
        print(f"  {k:24s} ${v:.4f}")
    print(f"合计 ${data['total_usd']:.4f} / 上限 ${common.BUDGET_USD:.2f}（按公开价目估算；以控制台账单为准）")


if __name__ == "__main__":
    main()
