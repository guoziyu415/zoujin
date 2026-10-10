# assets

美术资产。前端负责，UX 定标准。

- `pipeline/`：建模、减面、压缩、检查的脚本（A-0 试点来的；Blender 脚本和 Node 脚本）。
- `manifest/`：CC0 源素材的下载清单（地址和 sha256）。源素材不进仓库，脚本按清单下载并核对。
- `budgets.json`：资产和打包的预算（frontend-design 10.1、10.6.2，D-019），CI 超了就红。
- 手工改过的 `.blend` 和生成的 `glb`、`ktx2`、贴图、预录音频走 Git LFS（见 `.gitattributes`）。
