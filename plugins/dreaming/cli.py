"""CLI commands for the Dreaming plugin.

Provides ``hermes dream`` slash commands:

    hermes dream run      — run a dreaming cycle now
    hermes dream status   — show dreaming status and recent activity
    hermes dream enable   — enable dreaming
    hermes dream disable  — disable dreaming
"""

from __future__ import annotations

import logging
from argparse import Namespace
from typing import Any, Dict, List, Optional

from plugins.dreaming import (
    is_enabled,
    run_dreaming_cycle,
    _get_dreams_path,
    _get_memory_md_path,
    _get_last_user_activity,
    _is_user_quiet,
    _get_config,
)

logger = logging.getLogger(__name__)


def register_cli(subparser):
    """Register dream CLI subcommands."""
    dream_parser = subparser.add_parser(
        "dream",
        help="Manage the Dreaming memory consolidation system",
        description="Run, inspect, and configure automatic memory consolidation.",
    )
    sub = dream_parser.add_subparsers(dest="dream_command")

    # dream run
    run_p = sub.add_parser("run", help="Run a dreaming cycle now")
    run_p.add_argument("--force", action="store_true", help="Skip user-activity quiet check")
    run_p.add_argument("--verbose", "-v", action="store_true", help="Detailed output")

    # dream status
    sub.add_parser("status", help="Show dreaming status and recent activity")

    # dream diary
    diary_p = sub.add_parser("diary", help="Show recent dream diary entries")
    diary_p.add_argument("--limit", "-n", type=int, default=5, help="Number of entries to show")

    # dream enable / disable
    sub.add_parser("enable", help="Enable dreaming in config")
    sub.add_parser("disable", help="Disable dreaming in config")


def dream_command(args: Namespace) -> None:
    """Dispatch dream subcommands."""
    cmd = getattr(args, "dream_command", None)

    if cmd == "run" or cmd is None:
        _cmd_run(args)
    elif cmd == "status":
        _cmd_status()
    elif cmd == "diary":
        _cmd_diary(args)
    elif cmd == "enable":
        _cmd_enable()
    elif cmd == "disable":
        _cmd_disable()


def _cmd_run(args: Namespace) -> None:
    force = getattr(args, "force", False)
    verbose = getattr(args, "verbose", False)

    print("🌙 Starting dreaming cycle...")
    if not force and _is_user_quiet():
        print("   User is quiet — proceeding.")
    elif force:
        print("   Forced run — skipping quiet check.")

    result = run_dreaming_cycle(force=force, verbose=verbose)

    if result is None:
        print("   Skipped: user is active or dreaming is disabled.")
        return

    print(f"   ✅ Cycle complete!")
    print(f"   Light: {result.light_count} candidates staged")
    print(f"   REM:   {len(result.rem_themes)} themes found")
    print(f"   Deep:  {len(result.deep_promoted)} promoted, {len(result.deep_skipped)} skipped")

    if result.deep_promoted:
        print(f"\n   Promoted memories:")
        for p in result.deep_promoted:
            print(f"     • {p[:100]}")


def _cmd_status() -> None:
    cfg = _get_config()
    enabled = is_enabled()
    last_active = _get_last_user_activity()
    quiet = _is_user_quiet()
    dreams_path = _get_dreams_path()
    memory_path = _get_memory_md_path()

    print("🌙 Dreaming Status")
    print(f"   Enabled:     {'yes' if enabled else 'no'}")
    print(f"   Frequency:   {cfg.get('frequency', '0 3 * * *')}")
    print(f"   Quiet mins:  {cfg.get('quiet_minutes', 60)}")
    print(f"   Lookback:    {cfg.get('lookback_days', 7)} days")
    print(f"   Threshold:   {cfg.get('promotion_threshold', 0.6)}")
    print(f"   Last active: {last_active or 'unknown'}")
    print(f"   User quiet:  {'yes' if quiet else 'no'}")
    print(f"   Dreams file: {dreams_path} ({'exists' if dreams_path.exists() else 'not yet'})")
    print(f"   Memory file: {memory_path} ({'exists' if memory_path.exists() else 'not yet'})")


def _cmd_diary(args: Namespace) -> None:
    dreams_path = _get_dreams_path()
    if not dreams_path.exists():
        print("No dream diary found yet. Run a dreaming cycle first: hermes dream run")
        return

    content = dreams_path.read_text(encoding="utf-8")
    # Split into entries by the ## Dream Cycle header
    entries = content.split("## Dream Cycle")
    if entries:
        entries = ["## Dream Cycle" + e for e in entries[1:]]  # skip preamble

    limit = getattr(args, "limit", 5)
    entries = entries[-limit:]

    if not entries:
        print("Dream diary is empty.")
        return

    print(f"🌙 Dream Diary (last {len(entries)} entries):")
    print()
    for entry in entries:
        print(entry.strip())
        print()


def _cmd_enable() -> None:
    _update_config("enabled", True)
    print("✅ Dreaming enabled. Restart the gateway to activate.")


def _cmd_disable() -> None:
    _update_config("enabled", False)
    print("✅ Dreaming disabled.")


def _update_config(key: str, value: Any) -> None:
    """Update a single dreaming config key in config.yaml."""
    try:
        from hermes_cli.config import load_config, save_config
        config = load_config()
        plugins = config.setdefault("plugins", {})
        entries = plugins.setdefault("entries", {})
        dreaming = entries.setdefault("dreaming", {})
        cfg = dreaming.setdefault("config", {})
        cfg[key] = value
        save_config(config)
        print(f"   Config updated: dreaming.{key} = {value}")
    except Exception as e:
        print(f"   Error updating config: {e}")
