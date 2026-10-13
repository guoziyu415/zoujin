# How to add things to this repository / このリポジトリへの追加方法

The development-phase plan is in `docs/pm/dev-plan.md`; where there is a conflict, it and `docs/pm/decisions.md` take precedence.

開発フェーズの計画は `docs/pm/dev-plan.md` にある。食い違いがあれば、それと `docs/pm/decisions.md` を優先する。

## Task cards and branches / タスクカードとブランチ

- Large coding work is written as a task card under `docs/tasks/<phase>/<number>.md`. The card is carried out by the role that wrote it, in its own project thread (D-023).
  大きなコーディング作業はタスクカードにして `docs/tasks/<フェーズ>/<番号>.md` に置く。カードは書いた役割が自分のプロジェクトスレッドで実施する（D-023）。
- One card, one PR; if it is too big, split it into several PRs and state the order on the card. Branch names start with the card number, e.g. `c-1-api-schemas`.
  1 カード 1 PR。大きすぎる場合は複数の PR に分け、順序をカードに書く。ブランチ名はカード番号で始める（例：`c-1-api-schemas`）。
- Before opening a PR, run the checks CI requires locally (see "Local checks" below).
  PR を開く前に、CI が要求するチェックをローカルで実行しておく（下の「ローカルチェック」を参照）。

## Review / レビュー

- Every PR needs green CI, plus review by the **two roles** named on the card (dev-plan 2.3):
  すべての PR は CI がすべて成功していることに加え、カードに書かれた**二つの役割**のレビューが必要（dev-plan 2.3）：
  - Changes to `packages/contracts` must be reviewed by backend, frontend and data.
    `packages/contracts` を変更する場合は、バックエンド・フロントエンド・データの三者が見る。
  - Changes touching PRD acceptance numbers must also be reviewed by PM.
    PRD の受け入れ数値に触れる場合は、PM も見る。
- All threads share one identity on GitHub, so the GitHub "Approve" cannot be used. Write the review as a PR comment whose first line is one of the following:
  すべてのスレッドは GitHub 上で同一の身元になるため、GitHub の「Approve」は使えない。レビューは PR コメントとして書き、1 行目は次のいずれかに固定する：
  - `Approved · <role> · <first 7 chars of commit>`
    `承認 · <役割> · <コミット先頭 7 桁>`
  - `Changes requested · <role>`, followed by an item-by-item list of what to change.
    `要修正 · <役割>`。その下に、直す点を 1 つずつ書く。
- If more commits are pushed after a review, the reviewer confirms again with one line on the new commit.
  レビュー後にさらにコミットが push された場合、レビュアーは新しいコミットで 1 行確認し直す。
- The UX thread cannot comment on PRs (blocked by its permission check), so UX cannot be a PR reviewer. When UX needs to change a document in the repo, put the revised file in the project folder `ux/pr-drafts/` (same paths as in the repo) and PM opens the PR; for review, find two roles that can comment on the PR, and UX confirms the content in a message.
  UX スレッドは PR にコメントできない（権限チェックで止められる）ため、UX は PR のレビュアーになれない。UX がリポジトリ内のドキュメントを直したいときは、直したファイルをプロジェクトフォルダの `ux/pr-drafts/`（パスはリポジトリと同じ）に置き、PM が PR を開く。レビューは PR にコメントできる二つの役割に頼み、UX は内容をメッセージで確認する。
- If a dispute is unresolved after 3 rounds, PM decides; product questions go to zg via PM.
  議論が 3 ラウンドで決着しない場合は PM が決める。プロダクトの問題は PM 経由で zg に聞く。

## Merging (D-024) / マージ（D-024）

Before merging, the role thread that wrote the card checks four things; if all are met, squash-merge into main without waiting for zg:

マージの前に、カードを書いた役割のスレッドが次の四点を確認する。すべて満たしていれば、zg を待たずに squash して main にマージする：

1. CI is fully green on the latest commit of the PR.
   PR の最新コミットで CI がすべて成功している。
2. Both roles named on the card have approved on that commit (all three for contract changes; plus PM when PRD numbers are touched).
   カードに書かれた二つの役割が、そのコミットでレビューを通している（契約変更は三者、PRD の数値に触れる場合は PM も加える）。
3. There is no unresolved "Changes requested".
   未対応の「要修正」がない。
4. The PR contains no deployment, spending or real-model calls.
   PR にデプロイ、課金、本物のモデル呼び出しが含まれていない。

Deleting the branch after merging cannot be done from a project thread (the API returns 403), so leave the branch for now.

マージ後のブランチ削除はプロジェクトスレッドからはできない（API が 403 を返す）ため、ブランチはひとまず残しておく。

Merged does not mean live. Spending money and every deployment require zg's explicit consent first, asked separately each time. The GitHub free plan cannot enable branch protection on private repositories, so this gate relies on whoever merges to check it.

マージは公開を意味しない。課金とすべてのデプロイには、事前に zg の明確な同意が必要で、毎回個別に確認する。GitHub 無料プランの非公開リポジトリではブランチ保護を有効にできないため、この関門はマージする人自身が確認することで成り立つ。

## What stays out of the repository / リポジトリに入れないもの

Deployment URLs, project IDs, project numbers, billing IDs, keys, passwords, tokens, test codes, invitation codes, and zg's real name and Mac username and paths. CI's gitleaks catches some of these; what it misses depends on the author and the reviewer.

デプロイ先の URL、プロジェクト ID、プロジェクト番号、請求 ID、鍵、パスワード、トークン、テストコード、招待コード、そして zg の本名と Mac のユーザー名・パス。CI の gitleaks が一部を検出するが、検出できないものは書く人とレビューする人が確認する。

Holdout samples that have not been used yet also stay out of the repository; keep them in the project folder under `data/evals/holdout/` and move them in after they have been used once.

まだ使っていない留出サンプルもリポジトリには入れない。プロジェクトフォルダの `data/evals/holdout/` に置き、一度使ってから取り込む。

## Real models / 本物のモデル

Real models are called only on zg's Mac (credentials exist only there). Project threads and CI always use fake models and recorded replays, and tests have no network. For evaluations that need a real model, write the script and the budget and hand them to the Mac through coordination (dev-plan 2.5).

本物のモデルは zg の Mac でのみ呼び出す（認証情報は Mac にしかない）。プロジェクトスレッドと CI では常に偽モデルと録画済みのリプレイを使い、テストはネットワークなしで行う。本物のモデルが必要な評価は、スクリプトと予算を書いて、調整を経て Mac に渡して実行する（dev-plan 2.5）。

## Local checks / ローカルチェック

```bash
# Python (Python 3.13 + uv) / Python（Python 3.13 + uv）
uv sync --all-packages
uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest
bash .github/scripts/check_world.sh   # World model, 24 playthroughs, eval seeds, generated files consistent / 世界モデル、24 回の推演、評価シード、生成物の一致

# Node (Node 24 + pnpm, install with corepack enable) / Node（Node 24 + pnpm、corepack enable で導入）
pnpm install
pnpm lint && pnpm format:check && pnpm typecheck
```
