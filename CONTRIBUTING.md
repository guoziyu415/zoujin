# 怎么往这个仓库里加东西

开发阶段的计划在 `docs/pm/dev-plan.md`，有冲突以它和 `docs/pm/decisions.md` 为准。

## 任务卡和分支

- 大块编码写成任务卡，放 `docs/tasks/<阶段>/<编号>.md`。卡由写卡的角色在自己的项目线程里做（D-023）。
- 一张卡一个 PR；太大就拆成几个 PR，卡里写明先后。分支名用卡号开头，比如 `c-1-api-schemas`。
- 开 PR 之前，本地先跑过 CI 要的检查（见下面「本地检查」）。

## 评审

- 每个 PR 要 CI 全绿，再加卡上写的**两个角色**评审（dev-plan 2.3）：
  - 改 `packages/contracts` 的，后端、前端、数据三方都要看。
  - 碰到 PRD 验收数字的，PM 也看。
- 所有线程在 GitHub 上是同一个身份，用不了 GitHub 的「批准」。评审写成 PR 评论，第一行固定是下面两种之一：
  - `评审通过 · <角色> · <提交前 7 位>`
  - `要改 · <角色>`，下面逐条写要改什么。
- 评审之后又推了提交，评审人在新提交上再确认一行。
- UX 线程在 PR 上发不了评论（被它的权限检查拦着），所以 UX 当不了 PR 评审人。UX 要改仓库里的文档时，把改好的文件放项目文件夹 `ux/pr-drafts/`（路径和仓库一样），由 PM 开 PR；评审找能在 PR 上评论的两个角色，UX 在消息里确认内容。
- 争议 3 轮还没定，PM 定；产品问题经 PM 问 zg。

## 合并（D-024）

写卡的角色线程在合并前查四件，都满足就 squash 合进 main，不用等 zg：

1. PR 最新的提交上 CI 全绿。
2. 卡上写的两个角色都在这个提交上评审通过（改契约的三方，碰 PRD 数字的加 PM）。
3. 没有没处理的「要改」。
4. PR 里没有部署、花钱和真模型调用。

合并后删分支在项目线程里做不了（API 返回 403），分支先留着。

合并不等于上线。花钱和每次部署都要先得到 zg 的明确同意，每次单独问。GitHub 免费版的私有仓库开不了分支保护，所以这道门靠合并的人自己查。

## 不进仓库的

部署地址、项目 ID、项目号、账单 ID、密钥、密码、令牌、测试码、邀请码，以及 zg 的真名和 Mac 上的用户名、路径。CI 的 gitleaks 会查一部分，查不到的靠写的人和评审的人。

还没用过的留出样本也不进仓库，放项目文件夹的 `data/evals/holdout/`，用过一次再搬进来。

## 真模型

真模型只在 zg 的 Mac 上调（凭证只在 Mac 上）。项目线程和 CI 一律用假模型和录好的回放，测试禁网。需要真模型的评测，写好脚本和预算，经协调交 Mac 跑（dev-plan 2.5）。

## 本地检查

```bash
# Python（Python 3.13 + uv）
uv sync --all-packages
uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest
bash .github/scripts/check_world.sh   # 世界模型、24 次推演、评测种子、生成物一致

# Node（Node 24 + pnpm，用 corepack enable 装）
pnpm install
pnpm lint && pnpm format:check && pnpm typecheck
```
