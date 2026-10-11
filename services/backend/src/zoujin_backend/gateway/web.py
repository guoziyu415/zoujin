"""部署时网关同源发前端（B-23）：不上负载均衡和 CDN，前端构建、场景包和 API 走同一个地址。

- `/scenes/<assetVersion>/<目录>/…`：manifest 引用的场景包（`ZJ_SCENE_PACKS`，B-7），地址带版本，长缓存；
- `/assets/…`：vite 构建出来的带 hash 的文件，长缓存；
- 其余 GET：`ZJ_WEB_DIST` 里有这个文件就发（不长缓存），没有就回 `index.html`（前端自己的路由）；
- `/v1`、`/internal` 下没挂的地址照旧回第 5 节的 404，不回页面。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from zoujin_backend.gateway.core import Gateway

IMMUTABLE = "public, max-age=31536000, immutable"
NO_CACHE = "no-cache"
TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".webp": "image/webp",
    ".jpg": "image/jpeg",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".wasm": "application/wasm",
    ".glb": "model/gltf-binary",
    ".ktx2": "image/ktx2",
    ".bin": "application/octet-stream",
    ".m4a": "audio/mp4",
}
API_PREFIXES = ("v1", "internal")


def media_type(path: Path) -> str:
    return TYPES.get(path.suffix.lower(), "application/octet-stream")


def under(top: Path, rel: str) -> Path | None:
    """`top` 下的一个文件；走出 `top`（`..`、符号链接）、不是文件都是 None。"""
    if not rel:
        return None
    path = (top / rel).resolve()
    return path if top in path.parents and path.is_file() else None


def router(dist: Path) -> APIRouter:
    top = dist.resolve()
    index = top / "index.html"
    r = APIRouter()

    @r.get("/scenes/{version}/{folder}/{rel:path}", include_in_schema=False)
    async def scene(request: Request, version: str, folder: str, rel: str) -> Response:
        gw: Gateway = request.app.state.gw
        path = gw.manifest.scene_file(version, folder, rel) if gw.manifest is not None else None
        if path is None:
            return Response(status_code=404)
        return FileResponse(path, media_type=media_type(path), headers={"Cache-Control": IMMUTABLE})

    @r.get("/{rel:path}", include_in_schema=False)
    async def page(rel: str) -> Response:
        if rel.split("/", 1)[0] in API_PREFIXES:
            raise StarletteHTTPException(404)
        path = under(top, rel)
        if path is not None:
            cache = IMMUTABLE if rel.startswith("assets/") else NO_CACHE
            return FileResponse(path, media_type=media_type(path), headers={"Cache-Control": cache})
        if "." in rel.rsplit("/", 1)[-1] or not index.is_file():
            return Response(status_code=404)  # 要的是文件（有扩展名）而没有：不拿页面顶
        return FileResponse(index, media_type=TYPES[".html"], headers={"Cache-Control": NO_CACHE})

    return r
