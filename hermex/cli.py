from __future__ import annotations

import argparse

import uvicorn

from hermex.config import load_config
from hermex.mcp.server import create_mcp_app
from hermex.proxy.server import create_proxy_app


def main() -> None:
    parser = argparse.ArgumentParser(prog="hermex")
    subparsers = parser.add_subparsers(dest="command", required=True)

    proxy_parser = subparsers.add_parser("proxy", help="Run the Anthropic-compatible LLM proxy")
    proxy_parser.add_argument("--host", default="127.0.0.1")
    proxy_parser.add_argument("--port", type=int, default=8747)

    mcp_parser = subparsers.add_parser("mcp", help="Run the static Hermex MCP tools")
    mcp_parser.add_argument("--host", default="127.0.0.1")
    mcp_parser.add_argument("--port", type=int, default=8748)

    args = parser.parse_args()
    config = load_config()
    if args.command == "proxy":
        uvicorn.run(create_proxy_app(config), host=args.host, port=args.port)
    elif args.command == "mcp":
        uvicorn.run(create_mcp_app(config), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
