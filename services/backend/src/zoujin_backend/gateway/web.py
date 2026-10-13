"""When deployed, the gateway serves the frontend from the same origin (B-23): no load balancer or CDN; the frontend
build, scene packs and the API share one address.

- `/scenes/<assetVersion>/<dir>/…`: scene packs referenced by the manifest (`ZJ_SCENE_PACKS`, B-7); the address
  carries the version, cached long;
- `/assets/…`: hashed files built by vite, cached long;
- any other GET: serve the file if `ZJ_WEB_DIST` has it (not cached long), otherwise `index.html` (the frontend's own
  routing);
- unmounted addresses under `/v1` and `/internal` still answer with the section 5 404, not the page.

デプロイ時はゲートウェイが同一オリジンでフロントエンドを配信する（B-23）：ロードバランサーも CDN も使わず、
フロントエンドのビルド、シーンパック、API が同じアドレスを通る。

- `/scenes/<assetVersion>/<ディレクトリ>/…`：manifest が参照するシーンパック（`ZJ_SCENE_PACKS`、B-7）。アドレスに
  バージョンが入るので長期キャッシュ；
- `/assets/…`：vite がビルドしたハッシュ付きのファイル。長期キャッシュ；
- それ以外の GET：`ZJ_WEB_DIST` にそのファイルがあれば配信し（長期キャッシュしない）、なければ `index.html`
  （フロントエンド自身のルーティング）；
- `/v1`、`/internal` の下でマウントされていないアドレスは、ページではなく従来どおり第 5 節の 404 を返す。
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
    """A file under `top`; None if it escapes `top` (`..`, symlinks) or isn't a file.

    `top` の下のファイル。`top` の外に出る（`..`、シンボリックリンク）か、ファイルでなければ None。
    """
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
        path = next(
            (
                p
                for m in [*gw.manifests.values(), *gw.history_manifests.values()]
                if (p := m.scene_file(version, folder, rel))
            ),
            None,
        )
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
            # A file was asked for (it has an extension) and isn't there: don't answer with the page instead.
            # ファイル（拡張子あり）を求められたのに無い：代わりにページを返さない。
            return Response(status_code=404)
        return FileResponse(index, media_type=TYPES[".html"], headers={"Cache-Control": NO_CACHE})

    return r
