## Card / カード

<!-- Example / 例：docs/tasks/m2-0/C-1.md -->

## What was done / 実施内容

## How it was verified / 検証方法

<!-- Which checks were run locally and the results; for anything touching PRD numbers, write the measured value / ローカルで実行したチェックとその結果。PRD の数値に関わる場合は実測値を書く -->

## Review / レビュー

<!-- The two roles named on the card; changes to packages/contracts need all three parties; add PM when touching PRD numbers / カードに書かれた 2 つのロール。packages/contracts の変更は三者すべて。PRD の数値に関わる場合は PM を追加 -->

- [ ] Role 1 / ロール 1:
- [ ] Role 2 / ロール 2:

Write the review as a PR comment whose first line is fixed as `Review approved / レビュー承認 · <role> · <first 7 characters of the commit> / <ロール> · <コミットの先頭 7 文字>` or `Changes requested / 要修正 · <role> / <ロール>`. For the four things to check before merging, see `CONTRIBUTING.md`.

レビューは PR コメントとして書き、1 行目は固定で上記のいずれかの形式にする。マージ前に確認する 4 点は `CONTRIBUTING.md` を参照。

- [ ] No deployment, spending or real model calls / デプロイ、課金、実モデル呼び出しがない
- [ ] No addresses, project IDs, billing IDs, keys, test codes, invite codes or real names / アドレス、プロジェクト ID、請求 ID、鍵、テストコード、招待コード、本名がない
