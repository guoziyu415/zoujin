# apps/web

网页前端（React + three.js，手机浏览器优先）。前端负责。设计见 `docs/frontend/frontend-design.md`，任务卡见 `docs/tasks/m2-0/F-2.md`。

现在有的是 F-2b 的世界屏幕：写实的锡拉库萨广场（第一屏是 S7 的西南角构图），点地面走过去、点人走到对方面前、拖动转镜头，太阳和影子跟着世界时钟走。数据来自本卡的假 store（`src/three/dev/fakeStore.ts`），F-0 换成真的 store 和服务端推送；对话界面、时钟条这些在 F-0 / F-1。

## 跑起来

场景的生成物不进仓库，先生成一次广场（`assets/pipeline/plaza/README.md`），默认写到 `assets/scenes/syracuse-square/build/`：

```sh
pnpm assets:plaza draft            # 草稿档光照图，几分钟；正式档不带参数，约半小时
pnpm --filter @zoujin/web dev      # http://127.0.0.1:5173/
```

场景在别的目录时设 `ZOUJIN_SCENE_ROOT=<目录>`（读 `<目录>/syracuse-square/`）。

- `?dev`：拖时钟、放一遍日落（18:00 → 19:10）、开关石匠作坊、看帧时间和 draw call。给团队用，不给玩家。
- `?test`：挂上 `window.__zoujin`（`src/three/dev/testHook.ts`），Playwright 用它定时钟、摆固定机位、让玩家走到某处。

操作：点地面走、点人走到他面前；横向拖动转镜头；桌面上 WASD / 方向键走，按住 Shift 跑。

## 检查

```sh
pnpm --filter @zoujin/web test          # 单元测试（导航网格、太阳）；有场景生成物时也查每个位置点都走得到
pnpm --filter @zoujin/web build
pnpm --filter @zoujin/web check:bundle  # 外壳 ≤ 120 KB、3D 分块 ≤ 250 KB（brotli，assets/budgets.json）
pnpm --filter @zoujin/web e2e           # 先 build；无头 Chromium + 软件渲染，截图在 test-results/shots/
```

e2e 查的是 F-2 卡的验收：第一屏和 S7 第一屏构图一致，时钟从 18:00 推到 18:55 时王城墙上的影子线往上走，draw call 不超预算，跟随镜头的取景合 UX 的数字（人物高度、地平线位置），走进刑场时 store 正好收到一次移动，作坊在玩家还在里面时关上也走得出来，控制台没有错误。已经装了 Chromium 的机器用 `PW_CHROMIUM=<路径>` 指过去，不用再下载。CI（`.github/workflows/web.yml`）用草稿档生成广场并缓存，截图作为构件上传。

## 代码在哪

- `src/screens/WorldScreen.tsx`：世界屏幕（单独一个分块，外壳保持小）。
- `src/three/World.tsx`：分两步加载场景（能走的几何先到，贴图和遮蔽后到），然后灯光、玩家、镜头、后处理。
- `src/three/scene/`：场景清单、加载、平面坐标和 glTF 坐标的换算、第一屏机位。
- `src/three/nav/navmesh.ts`：读 `nav.json`，A* 加拉直路径、贴地、沿墙滑。
- `src/three/Lighting.tsx`、`sun.ts`、`shaderPatches.ts`、`PostFX.tsx`：S7 的「只烘遮蔽」光照（实时太阳和影子、物理天空、雾）和后处理。
- `src/three/Player.tsx`、`CameraRig.tsx`、`rig.ts`：玩家、镜头（第一屏的固定机位，玩家第一次走动或转镜头后滑到 UX 的跟随镜头：后 9 m、高 3.5 m、往下约 12.5°；对话时越肩；减少动态效果时直切）和它们共用的每帧状态。
