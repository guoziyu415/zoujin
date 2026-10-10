# S1 · 手机浏览器里能走的一个场景

技术验证，不算正式代码。目的是用真机帧率回答三个问题：手机浏览器里 3D 场景能不能稳定跑；WebGPU 和 WebGL2 哪个更合适；解像度、人数、阴影各要花多少帧。

- 测试页（claude.ai 私有页面，只有 zg 能打开）：https://claude.ai/artifact/Hy5hYj3mki7K8CriSx1W3H
- 源码：`index.html`（页面）、`robot.glb`（meshopt 压缩后的角色模型，页面里内嵌了一份 base64）
- 发布方式：claude.ai Artifact。只是私有测试页，不是产品部署，不涉及 Google Cloud、域名或密钥。

## 页面里有什么

- 场景：程序生成的锡拉库萨广场（两圈房子、北侧神殿、喷泉、橄榄树、市场摊位、远山），傍晚的低角度太阳和雾。房子、树、柱子都用 InstancedMesh，一类物件一次 draw call。
- 角色：three.js 官方示例的 RobotExpressive（CC0），主角 1 个 + 路人 0/6/12/24 个，各自在广场里闲逛（Idle / Walking / Wave）。
- 操作：左下虚拟摇杆移动，拖动画面转视角，桌面可用 WASD。走近路人会出现「押して話す」按钮，按下记录「按下到画面反馈」的延迟。
- 设置：GPU API（WebGPU 优先 / WebGL2 固定）、解像度（1 / 1.5 / 端末上限 2）、人数、阴影。
- 自动计测：主角沿固定路线自动走，8 种设置各测 12 秒（预热 3 秒），记录 fps 中位数、帧时间 p95/p99、超过 34ms 的帧占比、draw calls、三角形数，并保存到页面的数据库（collection `runs`），前端线程用 ArtifactData 读取。

## 已经得到的结论（容器内无头 Chromium，软件渲染，只看功能和数量，不看帧率）

| 项 | 数值 | 含义 |
|---|---|---|
| 13 个机器人 + 阴影 | 约 330–346 draw calls / 6.5 万三角形 | 三角形很少，但 draw call 已超过手机预算。原因是这个模型由 13 个子网格组成，阴影还要再画一遍。正式角色必须是 1 个蒙皮网格、最多 2 个材质 |
| 模型压缩 | 464KB → 183KB（gltf-transform optimize + meshopt，-60%） | 资产流水线用 meshopt 有效 |
| 打包体积（Vite 8.3 + React 19.3 + R3F 9.8 + three 0.186.1） | 应用外壳 58KB；3D 分块 WebGL 版 209KB、WebGPU 版 349KB（均为 brotli） | WebGPU 版多 140KB 传输、多约 690KB 要解析的 JS，需要真机证明它值得 |

## 等真机回答

1. iPhone（iOS 26）上 WebGPU 和 WebGL2 的 p95 帧时间对比
2. 解像度 1.5 和 2 的差距（决定默认 DPR）
3. 24 人和 12 人、影あり和影なし的差距（决定人数和阴影预算）
4. 按下说话按钮到画面反馈的延迟

## 局限

- Artifact 的页面跑在 claude.ai 的 iframe 里，和正式网页比多一层框架；数值偏保守。
- Artifact 不允许麦克风，所以语音链路要另做 S2（需要真正的网页环境）。
- 程序生成的场景比正式美术简单，正式场景的三角形和贴图会更多。
