# packages/worldsim

世界状态的共享规则库：初始状态、应用 effects、到点的节拍。叙事者、评测和数据的工具都用这一套规则。数据负责，后端评审。

- `reference/`：项目文件夹 `data/spikes/pipeline/` 原样搬来的参考实现，CI 现在用它校验世界模型和推演。
- `src/zoujin_worldsim/`：W-1 把参考实现整理成的包。移植时发现像 bug 的地方不在移植里改，回参考实现改。
