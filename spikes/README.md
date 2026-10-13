# spikes

Code from the validation phase, moved over as-is for reference only; it is not checked against product rules (excluded from ruff, mypy, eslint and prettier).

検証フェーズのコード。そのまま移したもので参考用のみ。製品ルールのチェック対象外（ruff、mypy、eslint、prettier からは除外）。

- `backend/`: backend technical validation (has its own pyproject and uv.lock, still run separately on the Mac; tests depend on Google libraries and are not in CI). B-0 and the Live proxy were moved from here.
  バックエンドの技術検証（独自の pyproject と uv.lock を持ち、Mac で従来どおり単独実行。テストは Google のライブラリに依存するため CI には入れない）。B-0 と Live プロキシはここから移した。
- `frontend/`: scripts for the S1 walking test page (T-002), S2 voice, S7 realistic plaza, and the A-0 stand-in pipeline. F-1 and F-2 were moved from here.
  S1 歩行テストページ（T-002）、S2 音声、S7 写実的な広場、A-0 代役パイプラインのスクリプト。F-1、F-2 はここから移した。
