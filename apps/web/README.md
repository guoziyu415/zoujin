# apps/web

网页前端（React + three.js，手机浏览器优先）。前端负责。设计见 `docs/frontend/frontend-design.md`，任务卡见 `docs/tasks/m2-0/F-0.md`、`F-2.md`。

现在有两块：

- **外壳（F-0）和语音（F-1）**：邀请码 → 封面 → 选身份 → 世界屏幕的 HUD（字幕、时钟条、近くの人、文字输入、说话键、轻反馈、断线横幅、回来时的「タップして続ける」），对着 B-1 的 mock 走完一轮对话。样式是占位的，视觉和文案定稿是 UX 的卡。
- **3D 广场（F-2b、F-2c、F-2d）**：世界屏幕下面是写实的锡拉库萨广场（第一屏是 S7 的西南角构图），读和 HUD 同一套 store：点地面走过去、点人走到他跟前开始对话、拖动转镜头，太阳和影子跟着世界时钟走，人物站在服务端说的位置点、换位置点时走过去。跨地点发 `move`，走近人物发 `near`、走远发 `far`，和正在说话的人走远了就结束对话。

## 跑起来

场景的生成物不进仓库，先生成一次广场（`assets/pipeline/plaza/README.md`），默认写到 `assets/scenes/syracuse-square/build/`：

```sh
pnpm assets:plaza draft            # 草稿档光照图，几分钟；正式档不带参数，约半小时
pnpm --filter @zoujin/web dev      # http://127.0.0.1:5173/
```

场景在别的目录时设 `ZOUJIN_SCENE_ROOT=<目录>`（读 `<目录>/syracuse-square/`）。

外壳要接口：开发服务器和 `vite preview` 把 `/v1`（含 WebSocket）、`/__mock`、`/assets/voice` 转给 `ZOUJIN_API`（默认 `http://127.0.0.1:8787`，B-1 的 mock）。在仓库根起 mock，邀请码是 `mock`：

```sh
uv run --all-packages zoujin-mock --scenario full-turn   # 一轮完整的对话；剧本见 fixtures/sessions/
```

不带参数是外壳（路由：`/login`、`/`、`/roles`、`/play/<局>`、`/ending/<局>`）。

- `?world`：只有 3D 广场，没有接口，世界是本地的一份（`src/three/dev/sandbox.ts`）。
- `?dev`：同上，再加一个面板：拖时钟、放一遍日落（18:00 → 19:10）、开关石匠作坊、看帧时间和 draw call。给团队用，不给玩家。
- `?test`：挂上 `window.__zoujin`（`src/three/dev/testHook.ts`），Playwright 用它定时钟、摆固定机位、让玩家走到某处、找点哪里能点到地面或人物。画质固定在 L1，每次画面一样；`?test&quality=auto` 照玩家那样跑起始档自测和升降档。和 `?world` 一起用是只有广场；单用时进外壳，走到世界屏幕时挂上（Playwright 也可以在页面脚本前设 `window.__zoujinTest = true`）。只测 HUD 的检查设 `window.__zoujinNo3d = true`，世界屏幕不加载 3D。
- `?quality=L0`〜`L3`：固定一级画质，不自测、不升降。
- `?crowd=20`：在刑场站 20 个群众（F-4，`src/three/crowd/`），和 `?world` 一起用。结局演出接上以前只有这个开关会加载群众那一块。
- `?measure`：计测页（见下面「画质」）。

操作：点地面走、点人走到他跟前（能说话的人同时开始对话）；横向拖动转镜头；桌面上 WASD / 方向键走，按住 Shift 跑。

## 画质（F-2c，frontend-design 10.6.3）

四级：L0 兜底（解像度 1.25，关泛光和 MSAA，阴影 1024）、L1 标准（1.5，全开，阴影 2048）、L2 高（2，软阴影，后台下 2048 贴图）、L3 最高（设备原生，最多 3）。调色和暗角每级都在同一遍里做，换级颜色不变。

- 起始档：进场时在屏幕外画一个固定的测试场景（PBR、天空、雾、2048 阴影、泛光、MSAA），按 S7 的加压法测一帧 GPU 耗时，按像素比推到每一级，取「L1 ≤ 25 ms、L2 / L3 ≤ 12 ms」里最高的一级；测不出就从 L1 开始（`src/three/quality/probe.ts`、`levels.ts`）。
- 升降档（`governor.ts`，单元测试喂假的帧时间）：每 5 秒看 p95，连续两次超过本级预算（L0 / L1 34 ms，L2 / L3 20 ms，和遥测直方图的边界一致）降一级，解像度马上变，其余等下一次镜头切换。升档只在镜头切换和进出对话时：本级 30 秒都在预算内、降档后过了 60 秒，并且 30 帧的 2 倍加压还在 60 帧左右，就在下一次切换时升一级。加压只在画面不动时做（镜头 10 帧没动：硬切以后、玩家还没走；推镜头和第一屏的滑动里不做，忙的时候也不做），镜头一动就停，这次不算；没过的话要重新攒 30 秒，再失败等 60、120、240 秒（UX 对 F-2c 的评审：过不了加压的手机不能让玩家看见那一秒的 30 帧）。一局降两次锁住上限。低电量模式（Safari 锁 30 帧、自测说 GPU 很空）按 30 帧的预算算，不升。
- 遥测（`src/telemetry/telemetry.ts` 先排队，F-0 的网络层批量发）：`quality_changed`（起始级带 `probeGpuMs`，到 L2 / L3 带 `assetMbps`；`lowPower`、`locked` 两种不换级，`from` = `to`），每 10 秒一条 `perf_sample`（9 格直方图）。

**计测页**：`?measure`，或者发成 claude.ai 私有页面在手机上开（不用部署）。先显示进场时自测的结果和它选的档，点「开始计测」后每一级沿 S7 的路线走 6.5 秒记帧时间，再停在 S7 的加压机位把同一帧画 2、4、8…32 遍，算一帧的 GPU 耗时。然后拍泛光的对照图（UX 对 F-2c 的评审）：L0 和 L1 各两张，18:45 在太阳落进西门的那条线上朝门看，和夜里一处火光（广场还没有火，计测页上放一个发光小球加暖色点光源当替身）。最后给一张表、四张图和一段 JSON。在 claude.ai 私有页面里多一个「保存结果」按钮：图存进页面的 assets，数字和图的编号存进页面的 db（`runs/<id>`），前端直接读，不用复制；不在私有页面里就照旧复制 JSON。`?measure&looks` 只拍图、不计时（检查机位用）。发成私有页面：

```sh
ZOUJIN_SCENE_ROOT=<场景目录> pnpm --filter @zoujin/web exec vite build --base ./ --outDir <临时目录>/dist
node apps/web/scripts/measure_artifact.mjs <临时目录>/dist <临时目录>/page   # 再把 page/index.html 连同其余文件发布
```

页面托管只认常见的网页类型，所以 `.glb`、`.ktx2`、`.wasm` 以 base64 放在脚本里，由一个小的 fetch 垫片交给加载器；这个页面上的加载时间含解码，只看帧时间和 GPU 耗时。要用「保存结果」，发布时给页面声明 `db` 和 `assets` 两项能力。

## 检查

```sh
pnpm --filter @zoujin/web test          # 单元测试（网络层、导航网格、太阳、升降档、直方图）；有场景生成物时也查每个位置点都走得到
pnpm --filter @zoujin/web build
pnpm --filter @zoujin/web check:bundle  # 外壳 ≤ 120 KB、3D 分块 ≤ 250 KB（brotli，assets/budgets.json）
pnpm --filter @zoujin/web e2e           # 先 build；自己起 mock 和 preview；无头 Chromium + 软件渲染，截图在 test-results/shots/
```

`f0.spec.ts` 对着 mock 查 F-0 卡的验收：邀请码、401 回邀请码页（WebSocket 4001 和 REST 都查）、开局 409（続きから / 新しく始める）、文字一轮（字幕、轻反馈、时钟 +10分）、断网 5 秒再连（断线期间判完的 commit 补发一次，不重复不丢）、不认识的消息类型不报错。每个测试先 `POST /__mock/reset`。组件不直接碰 WebSocket 由 ESLint 查（`no-restricted-globals`，只有 `src/net/` 能用）。

e2e 还查 F-2 卡的验收（`world.spec.ts`）和画质（`quality.spec.ts`：自测选了档、升降档开始工作、遥测的形状对，L0 / L1 / L2 第一屏几块区域的平均颜色差 ≤ 6/255）。`world.spec.ts` 查的是：第一屏和 S7 第一屏构图一致，时钟从 18:00 推到 18:55 时王城墙上的影子线往上走，draw call 不超预算，跟随镜头的取景合 UX 的数字（人物高度、地平线位置），走进刑场时 store 正好收到一次移动，作坊在玩家还在里面时关上也走得出来，控制台没有错误。已经装了 Chromium 的机器用 `PW_CHROMIUM=<路径>` 指过去，不用再下载。CI（`.github/workflows/web.yml`）用草稿档生成广场并缓存，截图作为构件上传。

## 代码在哪

- `src/app/`：外壳、路由（History API，不引路由包）、TanStack Query 的 REST 数据。
- `src/net/`：REST（`rest.ts`）、一局一条 WebSocket（`live.ts`：hello、ping、退避重连、关闭码）、消息写进 store（`session.ts`：commit 按序号应用和去重、缺号补拉、断线前没送到的一轮重发、轻反馈）、组件调的动作（`play.ts`）。
- `src/stores/`：zustand 的 world / player / voice / ui（frontend-design 第 6 节）。
- `src/screens/`：登录、封面、选身份、世界、结局（占位）；`src/ui/hud/`：世界屏幕的 HUD；`src/ui/copy.ts`：用到的日语文案（照 `docs/ux/copy-ja.md` 的键）。
- `src/telemetry/`：排队（`telemetry.ts`）和批量发送（`flush.ts`，每 10 秒，页面隐藏时 keepalive）。
- `src/screens/WorldScreen.tsx`：3D 广场（单独一个分块，外壳保持小）。
- `src/three/World.tsx`：分两步加载场景（能走的几何先到，贴图和遮蔽后到），然后灯光、玩家、镜头、后处理。
- `src/three/scene/`：场景清单、加载、平面坐标和 glTF 坐标的换算、第一屏机位。
- `src/three/nav/navmesh.ts`：读 `nav.json`，A* 加拉直路径、贴地、沿墙滑。
- `src/three/Lighting.tsx`、`sun.ts`、`shaderPatches.ts`、`PostFX.tsx`：S7 的「只烘遮蔽」光照（实时太阳和影子、物理天空、雾）和后处理。
- `src/three/quality/`：画质四级、起始档自测、升降档、帧时间直方图；`src/three/post.ts`：后处理链（PostFX 和自测共用）；`src/screens/MeasureScreen.tsx`：计测页。
- `src/three/Player.tsx`、`CameraRig.tsx`、`rig.ts`：玩家、镜头（第一屏的固定机位，玩家第一次走动或转镜头后滑到 UX 的跟随镜头：后 9 m、高 3.5 m、往下约 12.5°；对话时越肩；减少动态效果时直切）和它们共用的每帧状态。
