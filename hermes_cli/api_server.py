"""
Standalone HTTP API server for Hermes Agent.

Starts the OpenAI-compatible API server adapter without requiring the full
gateway.  This is the handler for ``hermes server``.

Usage:
    hermes server                       # Start on http://127.0.0.1:8642
    hermes server --port 9000           # Custom port
    hermes server --host 0.0.0.0        # Bind to all interfaces (requires API key)
    hermes server --key my-secret-key   # Set API key inline
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)


def run_api_server(
    host: str = "127.0.0.1",
    port: int = 8642,
    key: str = "",
    cors_origins: str = "",
    model_name: str = "",
    verbose: int = 0,
    quiet: bool = False,
) -> None:
    """Start the API server in the foreground and block until interrupted.

    This creates an :class:`APIServerAdapter` directly, bypassing the full
    gateway runner.  The adapter owns its own ``aiohttp`` server and
    ``AIAgent`` instances — no other platform adapters are started.
    """
    # Logging setup — mirrors gateway/run.py conventions
    from hermes_logging import setup_logging
    from hermes_constants import get_hermes_home

    hermes_home = get_hermes_home()
    setup_logging(hermes_home=hermes_home, mode="gateway")

    # Optional stderr handler
    if quiet:
        pass  # no stderr
    else:
        stderr_level = {0: logging.WARNING, 1: logging.INFO}.get(verbose, logging.DEBUG)
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(stderr_level)
        stderr_handler.setFormatter(logging.Formatter("%(levelname)-8s %(name)s: %(message)s"))
        logging.getLogger().addHandler(stderr_handler)

    # Check dependency
    from gateway.platforms.api_server import check_api_server_requirements
    if not check_api_server_requirements():
        print(
            "\naiohttp is required for the API server.\n"
            "Install it with:  pip install aiohttp\n"
        )
        sys.exit(1)

    # Resolve key from flag → env → empty (local-only mode)
    resolved_key = key or os.getenv("API_SERVER_KEY", "")

    # Build a minimal PlatformConfig for the adapter
    from gateway.config import Platform, PlatformConfig

    extra = {}
    if resolved_key:
        extra["key"] = resolved_key
    if cors_origins:
        extra["cors_origins"] = cors_origins
    if model_name:
        extra["model_name"] = model_name
    extra["host"] = host
    extra["port"] = port

    platform_config = PlatformConfig(enabled=True, extra=extra)

    # Banner
    print("┌─────────────────────────────────────────────────────────┐")
    print("│           ⚕ Hermes API Server Starting...               │")
    print("├─────────────────────────────────────────────────────────┤")
    print(f"│  Endpoint:  http://{host}:{port}/v1                     ")
    print(f"│  Auth:      {'API key required' if resolved_key else 'No auth (localhost only)'}                          ")
    print("│  Press Ctrl+C to stop                                   │")
    print("└─────────────────────────────────────────────────────────┘")
    print()

    asyncio.run(_run_adapter(platform_config))


async def _run_adapter(platform_config) -> None:
    """Create the adapter, start it, and wait for shutdown signal."""
    from gateway.platforms.api_server import APIServerAdapter

    adapter = APIServerAdapter(platform_config)

    # Connect (starts the aiohttp server)
    success = await adapter.connect()
    if not success:
        logger.error("API server failed to start")
        sys.exit(1)

    # Wait for Ctrl+C / SIGTERM
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _signal_handler():
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    try:
        await stop_event.wait()
    finally:
        print("\nShutting down API server...")
        await adapter.cancel_background_tasks()
        await adapter.disconnect()
        print("API server stopped.")


def server_command(args) -> None:
    """CLI entry point for ``hermes server``."""
    run_api_server(
        host=getattr(args, "host", "127.0.0.1"),
        port=getattr(args, "port", 8642),
        key=getattr(args, "key", ""),
        cors_origins=getattr(args, "cors_origins", ""),
        model_name=getattr(args, "model_name", ""),
        verbose=getattr(args, "verbose", 0),
        quiet=getattr(args, "quiet", False),
    )
