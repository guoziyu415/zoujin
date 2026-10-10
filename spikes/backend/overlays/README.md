# 补丁（只给 Mac 上已有的包用）

| 文件 | 用于哪个包 | 做什么 |
|---|---|---|
| `s4_v3_holdout.py`（sha256 前 12 位 c1539412e70b） | 只用于 41f261e10137 | 加 v3 提示和数据的 25 条留出样本，跑两次 `s4 --classify-only`（主集、留出集）。由 `build_s4_v3_holdout.py` 生成，不要手改。 |

之后的新包本身就有 v3 和 `--holdout`（`uv run python -m zj_spike.s4_model_armor --classify-only --holdout PATH`），不再需要这个补丁；拿它跑新包会报 TypeError（新的 `load_samples` 多了 `holdout=` 参数）。
