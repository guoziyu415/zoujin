"""Generating the pre-recorded lines (B-6): read aloud with the character's own Live voice, keep one of three takes
after automatic checks, and emit the voice manifest `voices.json`.

- `spec`: source file `services/backend/voice/<book>.json` + world model → the list of recordings to make.
- `audio`: PCM analysis (length, truncation), silence trimming, peak limiting, encoding (ffmpeg).
- `checks`: automatic checks and take selection (backend-design 3.6).
- `models`: real and fake implementations of read-aloud (Live) and transcript backfill.
- `cli`: the `zoujin-voice` script (prints the estimated cost first; only calls models with `--confirm`).

事前収録セリフの生成（B-6）：人物が Live で使うのと同じ声で読み上げ、3 テイクから 1 つを自動検査で選び、
音声マニフェスト `voices.json` を出力する。

- `spec`：元ファイル `services/backend/voice/<book>.json` + 世界モデル → 生成する録音の一覧。
- `audio`：PCM の解析（長さ、途切れ）、無音のトリム、ピーク制限、エンコード（ffmpeg）。
- `checks`：自動検査とテイクの選択（backend-design 3.6）。
- `models`：読み上げ（Live）と文字起こしの補完の本実装・偽実装。
- `cli`：`zoujin-voice` スクリプト（まず見積もり費用を表示し、`--confirm` を付けたときだけ呼び出す）。
"""
