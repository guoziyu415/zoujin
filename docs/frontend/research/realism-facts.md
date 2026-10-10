# 写实路线事实核查（走进物语 / 前端）

调研日 2026-10-06。标签：〔官方〕官方文档、源码、厂商；〔第三方〕社区、媒体、论文、代理商博客；〔估算〕本文推算。找不到的数据写"未找到"。"源码"指我下载的 npm 包 three@0.186.1 与 @sparkjsdev/spark@2.3.1。

## A. 高斯泼溅（GS）在移动浏览器

### A1 Spark（sparkjsdev/spark）
- 版本：最新 2.3.1（npm，2026-10-01）。2.0.0（2026-04-14）引入 LoD；2.2.0（2026-09-11）适配 three r186+，排序约快 20%；2.3.0（2026-09-29）加按需渲染。https://registry.npmjs.org/@sparkjsdev/spark ；https://github.com/sparkjsdev/spark/releases/tag/v2.2.0 〔官方〕
- 格式：PLY（含压缩 PLY）、SPZ、SPLAT、KSPLAT、SOG；2.0 起新增可流式 .RAD（64K splat 一块，列存 + Gzip，可随机寻址，先显示 64K 粗略版）。https://github.com/sparkjsdev/spark ；https://www.worldlabs.ai/blog/spark-2.0（2026-04-14）〔官方〕
- 与 three 网格合成：splat 默认在透明 pass 画；depthTest=true（会被不透明网格正确遮挡），depthWrite=false（官方说开了效果不好）。文档没提阴影投射/接收，也没提受光。https://sparkjs.dev/docs/spark-renderer/ 〔官方〕
- LoD 默认预算（源码 defaultSplatTarget）：iOS 1.5M，Android 1M，Vision Pro 750K，Quest 500K，桌面 2.5M。注意：2026-04 的博客写"手机 500K"，以现行源码为准。https://sparkjs.dev/docs/lod-getting-started/ 〔官方〕
- 分页显存池（源码）：iOS 默认 96 页 × 65,536 = 6.29M splat，每个 16 B，约等于 **96 MiB GPU**，JS 端还有同样大的 Uint32Array（约 96 MiB）。桌面 256 页，约 256 MiB。可以用 maxPagedSplats 调小。〔官方源码；MiB 换算〔估算〕〕
- 每 splat 存储：PackedSplats 16 B；加 SH1 +8 B，SH2 +16 B，SH3 +16 B，全带最多 56 B。https://sparkjs.dev/docs/packed-splats/ 〔官方〕
- 性能指南：iPhone 1–3M splat；约 1M 起 CPU（变换和排序）成为瓶颈；要关掉 WebGLRenderer 的 antialias（MSAA 对 splat 没好处，开销大）。没有 fps 表。https://sparkjs.dev/docs/performance/ 〔官方〕
- three.js 自带 GS：r186（2026-09-08）新增 GaussianSplat 对象，加上 PLY/SPLAT/KSPLAT/SPZ 加载器和 glTF 扩展。GPU 计数排序；只能用 WebGPURenderer（forceWebGL 也行），WebGLRenderer 不行；注释自称"minimal renderer"，没有 LoD 和流式加载。源码 examples/jsm/objects/GaussianSplat.js 〔官方〕

### A2 实测性能
- WebSplatter 论文（2026-02-03）：iPhone 15 Pro Max Safari，bicycle 场景 1,063,091 splat。antimatter15/splat（WebGL）50.5 ms（约 20 fps），web-splat（WebGPU）45.7 ms，WebSplatter 38.5 ms（约 26 fps）。分辨率未注明。https://arxiv.org/html/2602.03207v1 〔第三方-论文〕
- Babylon.js（2026-02-16~19）：iPhone 15 Pro 和 iPhone SE2 上 GS 30–40 fps；关 MSAA 换 FXAA 后 60 fps（splat 数未给）。团队解释：高 DPI 加大量混合 overdraw，MSAA 带宽撑不住。https://forum.babylonjs.com/t/gaussian-splat-low-performance-on-ios-devices-vs-android/62455 〔第三方，含官方成员回复〕
- PlayCanvas：全局 splat 预算默认 1M；建议移动 1M、桌面 3M+；填充率是主要瓶颈。https://developer.playcanvas.com/user-manual/gaussian-splatting/building/performance 〔官方〕。SuperSplat：桌面"约 4M 高帧率"（2026-03-11）。https://blog.playcanvas.com/new-in-supersplat-walk-mode-streamed-lod-and-easy-upload 〔官方〕
- Utsubo 指南（2026-09-24）：移动建议 200–500K splat、30–45 fps，移动端文件 15–30 MB。https://www.utsubo.com/blog/gaussian-splatting-guide 〔第三方〕
- iPhone 12/13/14 的 GS fps 公开数据：未找到。

### A3 文件大小
- 原始 PLY（SH3）：62 个 float32 = 248 B/splat（PlayCanvas 不算法线，记 232 B），约 250 MB/百万。SH0 约 56–68 B/splat〔估算，14–17 个 float〕。https://blog.playcanvas.com/compressing-gaussian-splats/（2023-12-05）〔官方〕
- PlayCanvas 压缩 PLY：16 B/splat（丢掉 SH）。同上〔官方〕
- SPZ（Niantic，MIT，v4 用 ZSTD）：比 PLY 小约 10×。https://github.com/nianticlabs/spz 〔官方〕。按规格推算：SH3 约 64 B、SH0 约 20 B/splat（熵压缩前）〔估算〕
- SOG（PlayCanvas，WebP 纹理）：比 PLY 小约 15–20×。实例：教堂 4M splat，PLY 约 1 GB → 55 MB（约 14 B/splat）。https://developer.playcanvas.com/user-manual/gaussian-splatting/formats/sog/ ；https://blog.playcanvas.com/playcanvas-adopts-sogs-for-20x-3dgs-compression（2025-05-15）〔官方〕
- 场景规模：3DGS 原论文实拍场景 1–5M Gaussians；平均大小 Mip-NeRF360 734 MB，Tanks&Temples 411 MB。https://arxiv.org/pdf/2308.04079（2023）〔第三方-论文〕
- World Labs Marble（AI 生成世界）：可导出约 2M 或约 500K splat（SPZ/PLY）和 10–20 万三角的碰撞网格；导出要付费 Standard 计划，商用权在 Pro 计划。https://docs.worldlabs.ai/marble/export/specs ；https://docs.worldlabs.ai/marble/export/gaussian-splat 〔官方〕
- 广场/街道级：没有权威的单一数字。估 2–6M splat，SOG 约 30–85 MB，SPZ（SH3）约 50–150 MB；压到移动版 0.5–1M splat 后 SOG 约 7–14 MB〔估算〕。

### A4 限制
- 光照烘焙在训练结果里，不响应动态光；到 2026 年主流插件仍没有正确的 splat 阴影；splat 自身没有碰撞。https://www.strayspark.studio/blog/gaussian-splatting-unreal-engine-5-capture-to-game-pipeline（2026-04-17）〔第三方〕
- PlayCanvas 把 splat 做成游戏（2026-04-22）：用 splat-transform 体素化，再 marching cubes 生成 .collision.glb 当碰撞；角色采样一张约 40 KB 的"亮度网格"来匹配环境明暗；没有动态阴影。https://blog.playcanvas.com/turning-a-gaussian-splat-into-a-videogame/ 〔官方〕
- 重光照：Niantic Spatial（2026-09）离线批量重光照（黎明、雨、雾等），只给申请通过的合作方，不是自助 API；平面、尖角、玻璃效果差。https://radiancefields.com/niantic-spatial-launches-gaussian-splat-relighting（2026-09-19）〔第三方报道〕
- Spark SplatEdit：可以在 SDF 区域里对颜色做 MULTIPLY/ADD，模拟"简单灯光"（这是调色，不是物理重光照）。https://sparkjs.dev/docs/splat-editing/ 〔官方〕
- 排序与 overdraw：每帧要按深度排序全部 splat（PlayCanvas 文档）；Spark 在 worker 里用 CPU 排序。splat 全部是半透明混合，Apple GPU 的 HSR 剔不掉重叠片元（见 C1 Apple 说明），所以 overdraw 高。〔官方〕
- GPU 内存：Spark 不带 SH 约 16 MB/百万，带 SH3 约 56 MB/百万，另加排序和索引缓冲〔官方数字 + 估算〕。

### A5 "三天里傍晚→日落→夜"用 GS 现实吗
- 判断〔估算〕：每个时段都要单独采集/生成并单独下载一套（3–4 套）；也可以用全局调色或 SplatEdit 近似，但夜里的灯笼、火光照不亮 splat；角色在 splat 地面上的影子要另做假阴影（blob 或贴花）。如果昼夜变化是叙事核心，GS 当主环境风险高；适合单一时段的远景或"名场面"背景。

## B. three.js 写实渲染（移动端）

### B1 材质成本
- 源码注释：Standard 比 Lambert/Phong "somewhat more computationally expensive"；Physical "higher performance cost, per pixel"，各效果默认关闭，开一个加一份开销。three r186 src/materials 〔官方〕
- Transmission：要多渲染一张全场景 RT（MSAA samples ≥ 4）；可以用 renderer.transmissionResolutionScale 降分辨率。three r186 WebGLRenderer.js 〔官方〕
- 论坛：Physical 特性不开时和 Standard 一样贵；clearcoat、sheen"较便宜"，transmission"较贵"；手机上全屏 Standard 都可能太贵。https://discourse.threejs.org/t/meshphysicalmaterial-can-i-measure-how-much-more-expensive-it-is/60398（2024-01-17）〔第三方〕
- 手机上按 ms 计的材质基准：未找到。

### B2 IBL / HDR
- PMREM 尺寸（源码）：cubeSize = 等距柱状图宽度 / 4；RT 为 3·cubeSize × 4·cubeSize、RGBA HalfFloat（8 B/px），生成时有 2 张（含 ping-pong）。2k HDR 每张约 25 MB，1k HDR 每张约 6.3 MB〔源码 + 估算〕。
- 手机上 PMREM 生成耗时：未找到实测。
- HDR 文件：Poly Haven venice_sunset .hdr 1k 1.44 MB，2k 5.72 MB，4k 22.8 MB；2k .exr 4.76 MB。https://api.polyhaven.com/files/venice_sunset 〔官方〕
- Ultra HDR（带 gain map 的 JPEG）：示例 1.5 MB .hdr → 122 KB（约 12×）。https://discourse.threejs.org/t/ultrahdr-three/60548（2024-01-21）〔第三方〕。three 内置 UltraHDRLoader，默认 HalfFloatType。https://threejs.org/docs/pages/UltraHDRLoader.html 〔官方〕
- Needle FastHDR（预滤波的 KTX2）：自称 4k EXR 生成 PMREM 时峰值 >250 MB；它的方案省 95% GPU 内存，加载 1.4 s，EXR 要 8.5 s。https://cloud.needle.tools/articles/fasthdr-environment-maps 〔第三方-厂商自述〕

### B3 烘焙光照
- lightMap 和 aoMap 用 texture.channel 选 UV（0=uv，1=uv1…）；文档写明"需要第二套 UV"；lightMap 一般是线性色彩空间、浮点（.exr/.hdr）。three r186 MeshStandardMaterial.js、Texture.js 〔官方〕
- 工具：Blender Cycles Bake；three 自带 ProgressiveLightMap（WebGL）和 ProgressiveLightMapGPU（WebGPU），可在浏览器里累积。〔官方〕
- 案例：Half-Life 风格场景全部用烘焙阴影，纹理图集 512² 235 KB，阴影图集 512² 9.8 KB，iPhone 和安卓 60 fps。https://discourse.threejs.org/t/half-life-inspired-scene-and-how-i-made-it-happen/20115（2020-10-25）〔第三方〕
- 实时阴影：移动端阴影贴图建议 512–1024。https://www.utsubo.com/blog/threejs-best-practices-100-tips（2026-09-11）〔第三方〕

### B4 KTX2 与显存
- 未压缩 RGBA8：1024² = 4 MiB（含 mip 5.3 MiB）；2048² = 16 MiB（含 mip 21.3 MiB）〔估算：4 B/px × 4/3〕。
- iPhone 上的 KTX2Loader（r186 源码）：UASTC 转 ASTC 4×4（1 B/px：1024² 1.33 MiB、2048² 5.3 MiB，含 mip）；ETC1S 转 ETC2 RGB（0.5 B/px：1024² 0.67 MiB、2048² 2.7 MiB），有 alpha 时转 ETC2 RGBA（1 B/px）。〔源码 + 估算〕
- 文件体积：ETC1S 约 0.3–3 bpp；UASTC 在显存里 8 bpp，要靠 RDO+zstd 才压小；新的 XUASTC 约 1.15–3.5 bpp（典型 2.25）。https://github.com/BinomialLLC/basis_universal（v2.5）〔官方〕
- 用法：UASTC 给法线、ORM 这类高细节纹理，ETC1S 给大色块和 basecolor；最大 2048²。实例：StainedGlassLamp 文件 13→10 MB，GPU 96→21 MB。https://github.com/KhronosGroup/3D-Formats-Guidelines/blob/main/KTXArtistGuide.md 〔官方〕
- 支持率：iOS 上 WebGL2 ASTC 扩展 99.94%。https://web3dsurvey.com/webgl2/extensions/WEBGL_compressed_texture_astc 〔第三方〕。ETC2 本来就是 WebGL2 核心格式。

### B5 Tone mapping
- r186 有 ACESFilmic、AgX（基于 Filament/Blender 的实现，Rec.2020 原色）、Neutral（Khronos PBR Neutral）。three r186 constants.js 〔官方〕
- ACES：亮色明显去饱和，色相会偏；部分鲜艳色（亮黄、亮绿、亮蓝）输出不出来。Neutral：中性光下保住 baseColor 的色相和饱和度，高光用去饱和代替。https://modelviewer.dev/examples/tone-mapping 〔官方-Google model-viewer〕
- AgX：过曝区域处理更好，亮色"像真实相机一样走向白色"（Blender 4.0，2023-11）。https://developer.blender.org/docs/release_notes/4.0/color_management/ 〔官方〕

### B6 后处理
- iPhone 上 bloom、SMAA、SSAO、DOF、LUT 的实测 ms：未找到可靠数据。
- N8AO：半分辨率快 2–4×；深度感知上采样固定约 1 ms；移动建议用 Performance 档（8 个 AO 样本、4 个降噪样本）。https://github.com/N8python/n8ao 〔官方-作者〕
- 填充率：iPhone 12 屏幕 2532×1170（约 2.96 MP）〔官方 https://support.apple.com/en-us/111876 〕；DPR 限到 2 时约 1.3 MP，每个全屏 pass 少 56% 像素〔估算〕。
- MSAA 在高 DPI 加大量混合时很贵（见 A2 Babylon）；Utsubo 建议移动端关 MSAA、后处理半分辨率、合并 pass。〔第三方〕
- WebGPURenderer：r183（2026-02-18）把 PostProcessing 改名为 RenderPipeline。https://app.cinevva.com/news/2026-03-18-threejs-r183-render-pipeline 〔第三方〕。r186 自带 TSL 节点有 Bloom、GTAO、SSAO、SSGI、SSR、DepthOfField、SMAA、FXAA、TRAA、TAAU、FSR1、Lut3D、SSS（屏幕空间阴影）等。源码 examples/jsm/tsl/display/ 〔官方〕
- Safari 26（2025-09-15）在 iOS 默认开启 WebGPU。https://webkit.org/blog/17333/webkit-features-in-safari-26-0/ 〔官方〕。2026-06-07 有 79% 的 iPhone 运行 iOS 26。https://macrumors.com/2026/06/09/ios-26-adoption-stats-wwdc/ 〔第三方转述 Apple〕

### B7 实际站点预算
- Utsubo（2026-09-11）：移动约 100 draw calls、<10 万顶点；纹理 ≤2048；DPR ≤2；4096² RGBA 约 64 MiB（含 mip 85 MiB）。https://www.utsubo.com/blog/threejs-best-practices-100-tips 〔第三方〕
- Codrops SINGULARITY（2025-02-11）：27 个 mesh、4 万三角、资源合计 2.1 MB；移动 DPR 上限 1.5。https://tympanus.net/codrops/2025/02/11/building-efficient-three-js-scenes-optimize-performance-while-maintaining-quality/ 〔第三方〕
- iOS 崩溃案例：模型从 18 MB/19 万面减到 1.29 MB/4.5 万面后稳定。https://forum.babylonjs.com/t/ios-crashing-issue-severe/32981（2022-08）〔第三方〕
- "写实 three.js 站点 + 手机端完整预算"的公开拆解：未找到。

## C. 写实角色

### C1 预算
- MetaHuman 官方 LOD：头部顶点 LOD0 24,000 → LOD3 2,500；身体 LOD0 30,500 → LOD3 1,507；头部关节 713（LOD0）→ 26（LOD7）；669 个 blendshape 只在 LOD0；移动推荐 LOD3、贴图 ≤2048、头发用发片（cards）。https://dev.epicgames.com/documentation/metahuman/platform-support-and-lod-specifications-for-metahumans?lang=en-US 〔官方〕
- Ready Player Me Hero Character 规范（已停服，只作参考）：≤30,000 三角，贴图 ≤1024²，单张 ≤2 MB，总计 ≤10 MB，每顶点 ≤4 个骨骼权重，支持 ARKit 和 Oculus visemes。https://docs.readyplayer.me/asset-creation-guide/reference/hero-character 〔官方〕
- 面部：ARKit 52 个 blendshape 加 Oculus 15 个 viseme（TalkingHead 要求两者都有）。https://github.com/met4citizen/TalkingHead 〔第三方-开源〕
- 头发与 alpha：Apple GPU 推荐的绘制顺序是不透明 → alpha test/discard → 半透明；混合或 discard 会迫使 HSR 刷新、增加 overdraw。https://developer.apple.com/videos/play/wwdc2020/10602/（WWDC20）〔官方〕
- 本项目建议：近真人（不到毛孔级）主角 2–4 万三角，4–5 个材质（皮肤、眼、头发、衣服、牙舌），贴图 1024–2048 KTX2，约 60–70 根骨骼加 52 个 blendshape〔估算〕。

### C2 制作管线
- Ready Player Me：Netflix 于 2025-12-19 宣布收购，2026-01-31 停服，API 和 SDK 失效。https://ryanschultz.com/tag/ready-player-me/ ；https://genies.com/blog/ready-player-me-shutdown 〔第三方〕
- MetaHuman：2025-06-04 起可以用在任何引擎/DCC（含商用），受 UE EULA 约束；年收入 <100 万美元免费；不得用来训练 AI。https://www.cgchannel.com/2025/06/you-can-now-sell-metahumans-or-use-them-in-unity-or-godot/ 〔第三方〕；"can be used with any engine"：https://www.metahuman.com/en-US/license 〔官方〕。Web/three.js 没有单独提到；没有官方 glTF 导出，要经 UE/Blender 转换；移动 LOD3 没有 blendshape〔估算〕。
- MPFB/MakeHuman：核心资产（base mesh、targets、skins）是 CC0，可闭源商用；第三方资产另算；插件代码的 GPL 不约束导出的模型。https://static.makehumancommunity.org/mpfb/faq/use_in_closed_source.html 〔官方〕
- Character Creator（Reallusion）：内容要带 Export License 才能导出；"不得公开下载或使用"。这是约 2015 年的帖子，Web 发布前要向 Reallusion 确认。https://forum.reallusion.com/PrintTopic335621.aspx 〔官方论坛〕
- Avaturn：以 iframe 方式给 three.js 输出 GLB；T2 头型支持 ARKit blendshape 和 visemes；TalkingHead 说它非商用免费。https://docs.avaturn.me/docs/integration/bodies/ 〔官方〕
- VRoid：动漫风，不符合写实要求。

### C3 皮肤
- three 没有专门的皮肤 SSS：WebGL 有 SubsurfaceScatteringShader 示例，WebGPU 有 MeshSSSNodeMaterial，两者都是 Barré-Brisebois（GDC 2011）的"透光"近似，每个直射光多几条 ALU 运算，不加 pass。three r186 源码〔官方〕。按 ms 计的成本：未找到。
- 屏幕空间可分离 SSS：three 没有内置（源码里没找到）〔官方〕。

### C4 口型
- 音频驱动：HeadAudio（MIT）用 MFCC 加高斯原型分类，输出 15 个 Oculus viseme，端到端约 50 ms，每块 <0.1 ms，模型约 14 kB。https://github.com/kyr0/HeadAudio 〔第三方-开源〕
- wawa-lipsync（MIT）：用 Web Audio AnalyserNode 实时输出 viseme。https://cdn.jsdelivr.net/npm/wawa-lipsync@0.0.2/README.md 〔第三方〕
- 文本时间戳驱动：TalkingHead 把词级时间戳映射成 viseme。〔第三方〕
- 只用振幅驱动下颌：最便宜，但只有张合；日语五个元音用 aa/E/I/O/U viseme 就能覆盖大部分口型〔估算〕。

## D. 移动 Safari 约束

### D1 GPU 与内存
- Geekbench 6 Metal 分数：iPhone 12（A14，4 核 GPU）12,405；13：14,568；13 Pro：17,047；14：16,320；15：18,430；15 Pro：22,838；16：25,930；17：35,291。iPhone 13 约为 12 的 1.17×，15 约 1.5×，15 Pro 约 1.8×。https://browser.geekbench.com/ios-benchmarks（2026-10 访问）〔第三方〕
- Safari 内存上限：Apple 没有公开数字。社区证据：Babylon 核心成员说标签页约 1.2 GB 时"已经非常接近上限"（2022）https://forum.babylonjs.com/t/ios-crashing-issue-severe/32981 〔第三方〕；Unity 用户在 iPhone 11 上约 880 MB 前后崩溃（2024-11）https://discussions.unity.com/t/webgl-ios-unity-sometimes-reloads-after-startup/1541942 〔第三方〕；WebKit bug 300782（2025-10-15）：纹理多的 WebGL 页面在内存压力下循环重载，JS 收不到 OOM 错误。https://bugs.webkit.org/show_bug.cgi?id=300782 〔官方 bug 库〕
- 建议 JS 加 GPU 总量控制在约 500 MB 以内〔估算〕。

### D2 日本移动网速
- Ookla：日本移动下载中位数 51.95 Mbps（2025-01，含 4G 和 5G）。https://datareportal.com/reports/digital-2025-japan 〔第三方转述 Ookla〕
- Opensignal（2026-01~03）：总体下载 SoftBank 65.1、au 60.7、docomo 55.7、楽天 39.6 Mbps；连上 5G 时 123–159 Mbps。https://insights.opensignal.com/reports/2026/04/japan/mobile-network-experience 〔第三方〕
- 纯 4G 中位数：未找到（两家都不单列）。
- 下载时间〔估算，不含 TLS、延迟、解码〕：按 50 Mbps，4 MB 0.64 s / 10 MB 1.6 s / 20 MB 3.2 s；按保守的 10 Mbps（弱 4G），3.2 s / 8 s / 16 s。

## 对我们的含义
1. 用 GS 当主环境，和"三天里傍晚→日落→夜"的光照叙事冲突：光照烘焙在 splat 里，没有能自助用的实时重光照；每个时段要一整套数据（下载 ×3–4），角色阴影和碰撞也要另做代理网格。建议 GS 最多用在单一时段的远景或名场面，主环境用网格加烘焙光照。
2. 如果要试 GS：iPhone 按 0.5–1M splat 设计。iPhone 15 Pro Max 跑 1.06M splat 实测只有 20–26 fps，iPhone 12 只会更低。压成 SOG/SPZ 后每个场景约 7–14 MB；Spark 在 iOS 默认的分页池约 96 MiB GPU 加 96 MiB JS，要调小。
3. 写实感最划算的来源：烘焙 lightmap/AO、好的 IBL、AgX 或 Neutral tone mapping、调色 LUT。不靠 transmission（多一张全场景 RT）、屏幕空间 AO 或 SSR。
4. 时间变化的做法〔估算〕：每个时段一套烘焙 lightmap（2048² ASTC 每张约 5.3 MiB 显存），加一张环境图（Ultra HDR JPG 只有百 KB 级），切换时段时做混合。
5. 纹理全部用 KTX2：UASTC 给法线/ORM（iPhone 上 1 B/px），ETC1S 给 basecolor（0.5 B/px），比未压缩 RGBA8 省 4–8× 显存。
6. 内存红线：iOS 没有官方上限，社区证据是约 0.9–1.2 GB 就崩溃或重载。自定预算：JS 加 GPU ≤500 MB，单场景纹理 ≤200 MB〔估算〕。
7. 以 iPhone 12 为 GPU 基线（Metal 分数约为 iPhone 15 的 2/3）：DPR 上限 2（可在 1.5–2 间动态调），关 MSAA，后处理合并成 1–2 个 pass（bloom + LUT + FXAA/SMAA），AO 用烘焙的。
8. 角色：近真人主角 2–4 万三角、4–5 个材质、1024–2048 KTX2、ARKit 52 blendshape 加 15 个 viseme；头发用 alpha test 发片，按"不透明 → alpha test → 半透明"排序；皮肤用透光近似。RPM 已停服；MPFB（CC0）授权最干净；MetaHuman 授权可用，但要自己转 glTF，而且 LOD3 没有 blendshape。
9. 口型：日语可以用音频驱动 viseme（HeadAudio 约 50 ms 延迟）或预先生成时间戳，比只用振幅自然，开销可忽略。
10. 下载：日本移动中位数 50–65 Mbps（含 5G），10 MB 约 1.6 s，弱 4G（10 Mbps）约 8 s；首屏 ≤10 MB、每章节流式加载 ≤20 MB 是合理目标〔估算〕。iOS 26 上 WebGPU 可用（79% 的 iPhone），但必须保留 WebGL2 兜底；three 自带的 GS 只支持 WebGPURenderer。

## 3DMark（把 zg 的手机推到 iPhone 12 用，2026-10-06 加）

- Wild Life Extreme：iPhone 12 2131 分（压力测试稳定度 74%）；iPhone 15 Pro Max 3570 分；iPhone 16 Pro Max 4264 分。16 Pro Max 约为 12 的 2.0 倍。UL 官方数据库：https://benchmarks.ul.com/hardware/phone/Apple+iPhone+12+review 、https://benchmarks.ul.com/en/hardware/phone/Apple+iPhone+16+Pro+Max+review 、https://benchmarks.ul.com/en/hardware/phone/Apple+iPhone+15+Pro+Max+review 〔第三方：UL〕
- ~~iOS 18.7 + 440×956 pt 的屏幕只能是 iPhone 16 Pro Max~~（错，2026-10-06 更正）：zg 的手机是 iPhone 17 Pro Max（zg 说的）。iOS 26 起 Safari 的 UA 把系统版本冻结在 iOS 18 的最后一个版本号，所以 UA 里的 18_x 不能说明是 iOS 18：https://51degrees.com/blog/apple-ios26-safari26-user-agent-string-device-detection 〔第三方〕
- iPhone 17 Pro Max：Wild Life Extreme 5405 分、Steel Nomad Light 2463 分（稳定度 76%）：https://benchmarks.ul.com/en/hardware/phone/Apple+iPhone+17+Pro+Max+review 〔第三方：UL〕。约为 iPhone 12 的 2.5 倍，加 iPhone 12 降频 1.35 → 推算系数 3.4。GSMArena 测到 17 Pro Max 6010 分（不同测法，取 UL）。
- iPhone 上 `gl.finish()` 不等 GPU：S7 第一次实测里正在掉帧的配置也只量到 3ms〔实测〕。
