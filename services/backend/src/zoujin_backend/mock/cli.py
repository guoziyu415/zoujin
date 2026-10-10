"""`uv run zoujin-mock`：在本机起 mock 服务。"""

from __future__ import annotations

import argparse
import logging

import uvicorn

from zoujin_backend.mock.app import create_app
from zoujin_backend.mock.core import DEFAULT_SCENARIO, Config


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="zoujin-mock", description="api-contract 的 mock 服务（B-1）")
    p.add_argument("--host", default="127.0.0.1", help="默认只听本机；容器里用 0.0.0.0")
    p.add_argument("--port", type=int, default=8787)
    p.add_argument("--speed", type=float, default=1.0, help="剧本的等待乘这个数：0 = 不等（CI），2 = 两倍慢")
    p.add_argument("--scenario", default=DEFAULT_SCENARIO, help="开局用的剧本，之后可以 POST /__mock/scenario 换")
    p.add_argument(
        "--allow-origin",
        action="append",
        default=[],
        metavar="ORIGIN",
        help="同源以外还放行的 Origin，例 http://localhost:5173（前端开发服务器不走代理时）",
    )
    p.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"])
    args = p.parse_args(argv)
    if args.speed < 0:
        p.error("--speed 不能是负数")
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(name)s %(levelname)s %(message)s")
    config = Config(speed=args.speed, scenario=args.scenario, allow_origins=tuple(args.allow_origin))
    uvicorn.run(create_app(config), host=args.host, port=args.port, log_level=args.log_level, ws="websockets-sansio")
