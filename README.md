# 物語 (Monogatari)

Code and design docs for 物語 (Monogatari): step into the 3D web world of 『走れメロス』 and talk with the characters in the book using spoken Japanese. Mobile browser first.

物語 (Monogatari) のコードと設計ドキュメント。『走れメロス』の 3D ウェブ世界に入り、日本語の音声で本の登場人物と話します。モバイルブラウザ優先。

- Development plan: `docs/pm/dev-plan.md`; decision log: `docs/pm/decisions.md`; PRD: `docs/pm/prd.md`.
  開発計画：`docs/pm/dev-plan.md`、決定記録：`docs/pm/decisions.md`、PRD：`docs/pm/prd.md`。
- How to add things, and how to review and merge: `CONTRIBUTING.md`.
  追加の仕方、レビューとマージの手順：`CONTRIBUTING.md`。
- Task cards: `docs/tasks/`.
  タスクカード：`docs/tasks/`。

## Directories / ディレクトリ

| Directory / ディレクトリ | Contents / 内容 | Owner / 担当 |
| --- | --- | --- |
| `apps/web` | Web frontend / ウェブフロントエンド | Frontend / フロントエンド |
| `services/backend` | Gateway, narrator, mock service (one Python package) / ゲートウェイ、ナレーター、モックサービス（Python パッケージ 1 つ） | Backend / バックエンド |
| `packages/contracts` | JSON Schemas for data contracts and interfaces, plus generated Python and TypeScript types / データ契約とインターフェースの JSON Schema、生成された Python と TypeScript の型 | Backend, Data / バックエンド、データ |
| `packages/worldsim` | Shared rules library for world state (`reference/` is the reference implementation) / 世界状態の共有ルールライブラリ（`reference/` は参考実装） | Data / データ |
| `worlds` | World model and source text for each book / 本ごとの世界モデルと原文 | Data / データ |
| `evals` | Eval sets, probe questions, safety samples, and their generators / 評価セット、プローブ問題、安全性サンプルとそのジェネレーター | Data / データ |
| `fixtures` | Fixed test data: model replays, audio for the fake Live / テスト用の固定データ：モデルのリプレイ、偽 Live の音声 | Backend, Data / バックエンド、データ |
| `assets` | Art pipeline, asset manifests, budgets (large files via LFS) / アートパイプライン、素材リスト、予算（大きなファイルは LFS） | Frontend (UX sets standards) / フロントエンド（UX が基準を定める） |
| `infra` | Terraform, written but not run / Terraform（書くだけで実行しない） | Backend / バックエンド |
| `docs` | Design docs, decisions, task cards / 設計ドキュメント、決定、タスクカード | All roles, PM consolidates / 各ロール、PM が集約 |
| `spikes` | Code from the validation phase, for reference only / 検証フェーズのコード（参考のみ） | Original authors / 元の作者 |
