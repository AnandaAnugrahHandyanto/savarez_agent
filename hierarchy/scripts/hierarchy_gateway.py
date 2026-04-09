#!/usr/bin/env python3
"""hierarchy_gateway — CLI for the Hierarchical Agent Architecture gateway.

Standalone script that manages GatewayHook instances for Hermes profiles.

Usage:
    python hierarchy_gateway.py start <profile>     # Run continuous listener
    python hierarchy_gateway.py process <profile>   # One-shot: process pending
    python hierarchy_gateway.py status              # Show status for all profiles

Logs to both stdout and ~/.hermes/hierarchy/logs/<profile>.log.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Project root — same pattern as hierarchy_manager.py
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

HIERARCHY_DIR = Path.home() / ".hermes" / "hierarchy"
REGISTRY_DB = HIERARCHY_DIR / "registry.db"
IPC_DB = HIERARCHY_DIR / "ipc.db"
LOGS_DIR = HIERARCHY_DIR / "logs"

# ---------------------------------------------------------------------------
# Now safe to import project modules
# ---------------------------------------------------------------------------

from hierarchy.core.integration.chain_store import ChainStore
from hierarchy.core.integration.orchestrator import ChainOrchestrator
from hierarchy.core.registry.profile_registry import ProfileRegistry
from hierarchy.core.ipc.message_bus import MessageBus
from hierarchy.core.ipc.models import Message
from hierarchy.core.workers.subagent_registry import SubagentRegistry
from hierarchy.integrations.hermes.delivery import make_telegram_hook_from_env
from hierarchy.integrations.hermes.gateway_hook import GatewayHook, RegistryAdapter
from hierarchy.integrations.hermes.config import HermesConfig
from hierarchy.integrations.hermes.worker_bridge import WorkerBridge

WORKERS_DIR = HIERARCHY_DIR / "workers"
CHAINS_DB = HIERARCHY_DIR / "chains.db"


def _make_gateway(profile: str, on_message=None) -> GatewayHook:
    """Create a fully-wired GatewayHook for a profile.

    Wires up WorkerBridge, ChainStore, and ChainOrchestrator so that
    incoming TASK_REQUEST messages spawn workers linked to delegation
    chains with full result propagation.
    """
    WORKERS_DIR.mkdir(parents=True, exist_ok=True)

    registry = ProfileRegistry(str(REGISTRY_DB))
    adapter = RegistryAdapter(registry)
    bus = MessageBus(str(IPC_DB), profile_registry=adapter)
    chain_store = ChainStore(db_path=str(CHAINS_DB))

    # Skip PM role validation — any profile (CTO, PM, specialist) needs
    # worker tracking when activated by the gateway.
    def worker_factory(pm_name: str) -> SubagentRegistry:
        return SubagentRegistry(str(WORKERS_DIR))

    orchestrator = ChainOrchestrator(
        registry=registry,
        bus=bus,
        worker_registry_factory=worker_factory,
        chain_store=chain_store,
    )

    bridge = WorkerBridge(
        worker_registry_factory=lambda: SubagentRegistry(str(WORKERS_DIR)),
        workspace_dir=WORKERS_DIR,
        chain_orchestrator=orchestrator,
        pm_profile=profile,
    )

    # Only deliver to owner for user-initiated /talk sessions.
    # The gateway tags payloads with user_talk=True when sent via /talk.
    # Autonomous hierarchy work stays in the hermes IPC inbox.
    delivery_hook = None
    try:
        prof = registry.get_profile(profile)
        is_root = prof is not None and not prof.parent_profile
    except Exception:
        is_root = (profile == "hermes")

    if is_root:
        delivery_hook = make_telegram_hook_from_env()
        if delivery_hook:
            logging.getLogger(__name__).info(
                "Telegram delivery hook enabled for root profile '%s'", profile
            )

    return GatewayHook(
        profile_name=profile,
        on_message=on_message,
        worker_bridge=bridge,
        chain_store=chain_store,
        chain_orchestrator=orchestrator,
        auto_execute=True,
        delivery_hook=delivery_hook,
    )


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(profile_name: Optional[str] = None, verbose: bool = False) -> None:
    """Configure logging to both stdout and (optionally) a per-profile log file.

    Parameters
    ----------
    profile_name : str | None
        When provided, a ``FileHandler`` is added writing to
        ``~/.hermes/hierarchy/logs/<profile>.log``.
    verbose : bool
        If True, set level to DEBUG; otherwise INFO.
    """
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
    ]

    if profile_name is not None:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOGS_DIR / f"{profile_name}.log"
        file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
        handlers.append(file_handler)

    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
    )


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------

_shutdown_event = threading.Event()


def _handle_signal(signum: int, frame: Any) -> None:
    """Set the shutdown event on SIGINT / SIGTERM."""
    sig_name = signal.Signals(signum).name
    logging.getLogger(__name__).info("Received %s — shutting down…", sig_name)
    _shutdown_event.set()


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_start(args: argparse.Namespace) -> int:
    """Start a blocking gateway listener for *profile*.

    Runs continuously, printing incoming messages to stdout, until
    interrupted by SIGINT or SIGTERM.
    """
    profile: str = args.profile
    setup_logging(profile_name=profile, verbose=args.verbose)
    log = logging.getLogger(__name__)

    # Register signal handlers
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    def _print_message(msg: Message) -> None:
        ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"  [{ts}] {msg.message_type.value} from {msg.from_profile} "
            f"→ {msg.to_profile} | priority={msg.priority.value} | "
            f"id={msg.message_id}"
        )
        if msg.payload:
            print(f"    payload: {json.dumps(msg.payload, default=str)}")

    log.info("Starting gateway for profile '%s'…", profile)
    print(f"{'=' * 60}")
    print(f"  GATEWAY — listening for profile: {profile}")
    print(f"  Press Ctrl+C to stop")
    print(f"{'=' * 60}")

    hook = _make_gateway(profile, on_message=_print_message)

    try:
        hook.start()
        log.info("Gateway running. Waiting for messages…")

        # Block until shutdown signal
        while not _shutdown_event.is_set():
            _shutdown_event.wait(timeout=1.0)

    except KeyboardInterrupt:
        pass
    finally:
        log.info("Stopping gateway…")
        hook.close()
        status = hook.get_status()
        stats = status.get("stats", {})
        print(f"\n{'=' * 60}")
        print(f"  Gateway stopped.")
        print(f"  Processed: {stats.get('processed', 0)}")
        print(f"  Errors:    {stats.get('errors', 0)}")
        print(f"{'=' * 60}")

    return 0


def cmd_process(args: argparse.Namespace) -> int:
    """One-shot: process all pending messages for *profile* and exit."""
    profile: str = args.profile
    setup_logging(profile_name=profile, verbose=args.verbose)
    log = logging.getLogger(__name__)

    log.info("One-shot processing for profile '%s'…", profile)
    print(f"{'=' * 60}")
    print(f"  GATEWAY — one-shot process for profile: {profile}")
    print(f"{'=' * 60}")

    def _print_message(msg: Message) -> None:
        ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"  [{ts}] {msg.message_type.value} from {msg.from_profile} "
            f"→ {msg.to_profile} | priority={msg.priority.value} | "
            f"id={msg.message_id}"
        )
        if msg.payload:
            print(f"    payload: {json.dumps(msg.payload, default=str)}")

    with _make_gateway(profile, on_message=_print_message) as hook:
        messages = hook.process_once(limit=args.limit)
        status = hook.get_status()
        stats = status.get("stats", {})

    print(f"\n  Processed: {len(messages)} message(s)")
    print(f"  Errors:    {stats.get('errors', 0)}")

    if not messages:
        print("  (no pending messages)")

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show gateway status for all registered profiles."""
    setup_logging(verbose=args.verbose)
    log = logging.getLogger(__name__)

    if not REGISTRY_DB.exists():
        print("❌ Registry not found. Run hierarchy_manager.py init first.")
        return 1

    print(f"{'=' * 60}")
    print(f"  GATEWAY STATUS")
    print(f"{'=' * 60}")

    registry = ProfileRegistry(str(REGISTRY_DB))
    adapter = RegistryAdapter(registry)
    bus = MessageBus(str(IPC_DB), profile_registry=adapter)

    try:
        profiles = registry.list_profiles()

        if not profiles:
            print("\n  No profiles registered.")
            return 0

        for p in profiles:
            name = p.profile_name
            pending = bus.get_pending_count(name)
            total = len(bus.list_messages(profile_name=name, limit=1000))

            # Check for log file
            log_path = LOGS_DIR / f"{name}.log"
            log_exists = log_path.exists()
            log_size = ""
            if log_exists:
                size_bytes = log_path.stat().st_size
                if size_bytes < 1024:
                    log_size = f"{size_bytes}B"
                elif size_bytes < 1024 * 1024:
                    log_size = f"{size_bytes / 1024:.1f}KB"
                else:
                    log_size = f"{size_bytes / (1024 * 1024):.1f}MB"

            print(f"\n  Profile: {name}")
            print(f"    Role:     {p.role}")
            print(f"    Status:   {p.status}")
            print(f"    Pending:  {pending} message(s)")
            print(f"    Total:    {total} message(s)")
            if log_exists:
                print(f"    Log:      {log_path} ({log_size})")
            else:
                print(f"    Log:      (none)")

    finally:
        bus.close()
        registry.close()

    print(f"\n{'=' * 60}")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="hierarchy_gateway",
        description="Hierarchical Agent Architecture — Gateway CLI",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=False,
        help="Enable debug logging.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand")

    # --- start ---
    p_start = subparsers.add_parser(
        "start",
        help="Start a continuous gateway listener for a profile.",
    )
    p_start.add_argument(
        "profile",
        help="Profile name to listen for (e.g. hermes, cto, pm-hier-arch).",
    )

    # --- process ---
    p_process = subparsers.add_parser(
        "process",
        help="One-shot: process pending messages for a profile and exit.",
    )
    p_process.add_argument(
        "profile",
        help="Profile name to process.",
    )
    p_process.add_argument(
        "-n", "--limit",
        type=int,
        default=50,
        help="Maximum number of messages to process (default: 50).",
    )

    # --- status ---
    subparsers.add_parser(
        "status",
        help="Show gateway status for all profiles.",
    )

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    dispatch = {
        "start": cmd_start,
        "process": cmd_process,
        "status": cmd_status,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
