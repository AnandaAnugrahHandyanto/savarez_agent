"""CLI handlers for ``hermes secrets protonpass ...``.

Subcommands:
    setup    -- interactive wizard: install pass-cli, store token, pick vault
    status   -- show current config + binary
    sync     -- fetch now, report what changed
    disable  -- turn off
    install  -- just download the binary
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agent.secret_sources import protonpass as pp
from hermes_cli.config import get_env_path, load_config, save_config, save_env_value
from hermes_cli.secret_prompt import masked_secret_prompt


def register_cli(parent_parser: argparse.ArgumentParser) -> None:
    sub = parent_parser.add_subparsers(dest="secrets_pp_command")

    setup = sub.add_parser("setup", help="Interactive wizard")
    setup.add_argument("--vault-name", help="Pre-select a vault name")
    setup.add_argument("--access-token", help="Provide token non-interactively")
    setup.set_defaults(func=cmd_setup)

    status = sub.add_parser("status", help="Show config + binary")
    status.set_defaults(func=cmd_status)

    sync = sub.add_parser("sync", help="Fetch secrets now")
    sync.add_argument("--apply", action="store_true", help="Export to env (default: dry-run)")
    sync.set_defaults(func=cmd_sync)

    disable = sub.add_parser("disable", help="Turn off integration")
    disable.set_defaults(func=cmd_disable)

    install = sub.add_parser("install", help="Download pass-cli binary")
    install.add_argument("--force", action="store_true", help="Re-download")
    install.set_defaults(func=cmd_install)


def cmd_setup(args: argparse.Namespace) -> int:
    console = Console()
    console.print(Panel.fit(
        "[bold]Proton Pass setup[/bold]\n\n"
        "Create a Personal Access Token (PAT) via "
        "[cyan]pass-cli pat create[/cyan] or the Proton Pass web app.\n"
        "The token starts with [cyan]pst_[/cyan] -- it cannot be retrieved later.\n\n"
        "See: https://proton.me/blog/pass-access-tokens",
        border_style="cyan",
    ))

    # Step 1: binary
    console.print()
    console.print("[bold]Step 1[/bold]  Install pass-cli")
    try:
        binary = pp.find_passcli(install_if_missing=False)
        if binary is None:
            console.print("  Downloading...")
            binary = pp.install_passcli()
        console.print(f"  [green]OK[/green] {binary} ({_version(binary)})")
    except Exception as exc:  # noqa: BLE001
        console.print(f"  [red]Install failed: {exc}[/red]")
        return 1

    # Step 2: token
    console.print()
    console.print("[bold]Step 2[/bold]  Access token")
    cfg = load_config()
    pp_cfg = cfg.setdefault("secrets", {}).setdefault("protonpass", {})
    token_env = pp_cfg.get("access_token_env", "PROTON_PASS_ACCESS_TOKEN")

    token = (args.access_token or "").strip()
    if not token:
        token = masked_secret_prompt(f"  Paste token ({token_env}): ").strip()
    if not token:
        console.print("  [red]Empty, aborting.[/red]")
        return 1
    if not token.startswith("pst_"):
        console.print("  [yellow]Warning: doesn't start with 'pst_'[/yellow]")

    save_env_value(token_env, token)
    os.environ[token_env] = token
    console.print(f"  [green]OK[/green] saved as {token_env}")

    # Step 3: vault
    console.print()
    vault_name = args.vault_name or ""
    if not vault_name:
        console.print("[bold]Step 3[/bold]  Pick a vault")
        vaults = _list_vaults(binary, token, console)
        if not vaults:
            return 1
        table = Table(show_header=True, header_style="bold")
        table.add_column("#", style="cyan", width=4)
        table.add_column("Name")
        for i, v in enumerate(vaults, 1):
            table.add_row(str(i), v.get("name", "?"))
        console.print(table)
        while True:
            choice = console.input(f"  Select [1-{len(vaults)}]: ").strip()
            try:
                idx = int(choice)
            except ValueError:
                continue
            if 1 <= idx <= len(vaults):
                vault_name = vaults[idx - 1].get("name", "")
                break
    console.print(f"  [green]OK[/green] vault: {vault_name}")

    # Step 4: test
    console.print()
    console.print("[bold]Step 4[/bold]  Test fetch")
    try:
        secrets, warnings = pp.fetch_protonpass_secrets(
            access_token=token, vault_name=vault_name, binary=binary, use_cache=False,
        )
    except Exception as exc:  # noqa: BLE001
        console.print(f"  [red]Failed: {exc}[/red]")
        return 1

    if not secrets:
        console.print("  [yellow]No secrets retrieved. Check vault has login items "
                       "with env-var titles.[/yellow]")
    else:
        table = Table(show_header=True, header_style="bold")
        table.add_column("Name", style="cyan")
        table.add_column("Status")
        for key in sorted(secrets):
            table.add_row(key, "[green]found[/green]")
        console.print(table)
    for w in warnings:
        console.print(f"  [yellow]{w}[/yellow]")

    # Save config
    pp_cfg.update({"enabled": True, "vault_name": vault_name})
    pp_cfg.setdefault("access_token_env", token_env)
    pp_cfg.setdefault("cache_ttl_seconds", 300)
    pp_cfg.setdefault("override_existing", True)
    pp_cfg.setdefault("auto_install", True)
    save_config(cfg)

    console.print()
    console.print("[green]Enabled.[/green]  "
                   "Run [cyan]hermes secrets protonpass status[/cyan] for details.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    console = Console()
    cfg = load_config()
    pp_cfg = (cfg.get("secrets") or {}).get("protonpass") or {}

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("", style="bold")
    table.add_column("")
    table.add_row("Enabled", _yn(pp_cfg.get("enabled")))
    table.add_row("Token env", pp_cfg.get("access_token_env", "PROTON_PASS_ACCESS_TOKEN"))
    table.add_row("Token set", _yn(os.environ.get(pp_cfg.get("access_token_env", "PROTON_PASS_ACCESS_TOKEN"))))
    table.add_row("Vault", pp_cfg.get("vault_name", "(unset)"))
    table.add_row("Override", _yn(pp_cfg.get("override_existing")))
    table.add_row("Cache TTL", str(pp_cfg.get("cache_ttl_seconds", 300)))

    binary = pp.find_passcli(install_if_missing=False)
    table.add_row("Binary", f"{binary} ({_version(binary)})" if binary else "[yellow]not installed[/yellow]")

    console.print(Panel(table, title="Proton Pass", border_style="cyan"))
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    console = Console()
    cfg = load_config()
    pp_cfg = (cfg.get("secrets") or {}).get("protonpass") or {}
    if not pp_cfg.get("enabled"):
        console.print("[yellow]Disabled. Run `hermes secrets protonpass setup`.[/yellow]")
        return 1

    token_env = pp_cfg.get("access_token_env", "PROTON_PASS_ACCESS_TOKEN")
    token = os.environ.get(token_env, "").strip()
    if not token:
        console.print(f"[red]{token_env} not set.[/red]")
        return 1
    vault_name = pp_cfg.get("vault_name", "")
    if not vault_name:
        console.print("[red]No vault configured.[/red]")
        return 1

    try:
        secrets, warnings = pp.fetch_protonpass_secrets(
            access_token=token, vault_name=vault_name, use_cache=False,
        )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Failed: {exc}[/red]")
        return 1

    if not secrets:
        console.print("[yellow]No secrets.[/yellow]")
        return 0

    override = bool(pp_cfg.get("override_existing")) or args.apply
    applied = 0
    table = Table(show_header=True, header_style="bold")
    table.add_column("Name", style="cyan")
    table.add_column("Action")
    for key in sorted(secrets):
        if key == token_env:
            table.add_row(key, "[dim]skip (bootstrap)[/dim]")
            continue
        already = bool(os.environ.get(key))
        if already and not override:
            table.add_row(key, "[dim]skip (exists)[/dim]")
            continue
        if args.apply:
            os.environ[key] = secrets[key]
            applied += 1
            table.add_row(key, "[green]exported[/green]")
        else:
            table.add_row(key, "[green]would export[/green]")
    console.print(table)

    if not args.apply:
        console.print("\n  Dry-run. Use [cyan]--apply[/cyan] to export.")
    else:
        console.print(f"\n  [green]Exported {applied}.[/green]")
    return 0


def cmd_disable(args: argparse.Namespace) -> int:
    cfg = load_config()
    cfg.setdefault("secrets", {}).setdefault("protonpass", {})["enabled"] = False
    save_config(cfg)
    Console().print("[green]Disabled.[/green]  Token left in .env.")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    console = Console()
    try:
        path = pp.install_passcli(force=bool(args.force))
        console.print(f"[green]OK[/green] {path} ({_version(path)})")
        return 0
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Failed: {exc}[/red]")
        return 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _yn(b: object) -> str:
    return "[green]yes[/green]" if b else "[dim]no[/dim]"


def _version(binary: Path) -> str:
    try:
        res = subprocess.run(
            [str(binary), "--version"], capture_output=True, text=True, timeout=5,
        )
        if res.returncode == 0:
            return (res.stdout or res.stderr).strip().splitlines()[0]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "version unknown"


def _list_vaults(binary: Path, token: str, console: Console) -> Optional[list]:
    try:
        proc = pp._run_passcli(
            binary, ["vault", "list", "--output", "json"], access_token=token, timeout=15,
        )
    except RuntimeError as exc:
        console.print(f"  [red]{exc}[/red]")
        return None
    if proc.returncode != 0:
        console.print(f"  [red]{(proc.stderr or proc.stdout).strip()[:200]}[/red]")
        return None
    try:
        data = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return []
    return [v for v in data if isinstance(v, dict) and v.get("name")]
