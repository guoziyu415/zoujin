# zoujin

走进物语（暂名）的代码和设计文档：走进『走れメロス』的 3D 网页世界，用日语语音和书里的人物说话。手机浏览器优先。

- 开发计划：`docs/pm/dev-plan.md`；决定记录：`docs/pm/decisions.md`；PRD：`docs/pm/prd.md`。
- 怎么加东西、怎么评审和合并：`CONTRIBUTING.md`。
- 任务卡：`docs/tasks/`。

## 目录

| 目录                 | 放什么                                                         | 谁负责            |
| -------------------- | -------------------------------------------------------------- | ----------------- |
| `apps/web`           | 网页前端                                                       | 前端              |
| `services/backend`   | 网关、叙事者、mock 服务（一个 Python 包）                      | 后端              |
| `packages/contracts` | 数据契约和接口的 JSON Schema，生成的 Python 和 TypeScript 类型 | 后端、数据        |
| `packages/worldsim`  | 世界状态的共享规则库（`reference/` 是参考实现）                | 数据              |
| `worlds`             | 每本书的世界模型和原文                                         | 数据              |
| `evals`              | 评测集、探针题、安全样本和它们的生成器                         | 数据              |
| `fixtures`           | 测试用的固定数据：模型回放、假 Live 的音频                     | 后端、数据        |
| `assets`             | 美术流水线、素材清单、预算（大文件走 LFS）                     | 前端（UX 定标准） |
| `infra`              | Terraform，只写不跑                                            | 后端              |
| `docs`               | 设计文档、决定、任务卡                                         | 各角色，PM 汇总   |
| `spikes`             | 验证阶段的代码，只作参考                                       | 原作者            |
