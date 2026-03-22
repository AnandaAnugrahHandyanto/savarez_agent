"""Shared interactive Kasia setup helpers for Hermes CLI entrypoints."""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DEFAULT_KASIA_INDEXER_URL = "https://indexer.kasia.fyi"
DEFAULT_KASIA_NODE_WBORSH_URL = "wss://wrpc.kasia.fyi"
DEFAULT_KASIA_NETWORK = "mainnet"
DEFAULT_KASIA_FEE_POLICY = "priority"
_TRUE_VALUES = {"true", "1", "yes"}


@dataclass(frozen=True, slots=True)
class KasiaSetupIO:
    get_env_value: Callable[[str], Optional[str]]
    save_env_value: Callable[[str, str], None]
    prompt: Callable[[str, Optional[str], bool], str]
    prompt_yes_no: Callable[[str, bool], bool]
    print_info: Callable[[str], None]
    print_success: Callable[[str], None]
    print_warning: Callable[[str], None]
    print_error: Callable[[str], None]


def is_kasia_configured(get_env_value: Callable[[str], Optional[str]]) -> bool:
    """Return True when any Kasia configuration has been set."""
    return any(
        [
            get_env_value("KASIA_ENABLED"),
            get_env_value("KASIA_SEED_PHRASE"),
            get_env_value("KASIA_INDEXER_URL"),
            get_env_value("KASIA_INDEXER_URLS"),
            get_env_value("KASIA_NODE_WBORSH_URL"),
            get_env_value("KASIA_NODE_WBORSH_URLS"),
        ]
    )


def validate_kasia_seed_phrase(seed_phrase: str) -> tuple[bool, str | None]:
    """Validate Kasia/Kaspa mnemonic structure with a lightweight Node check."""
    normalized = " ".join(str(seed_phrase or "").strip().split())
    if not normalized:
        return False, "Kasia seed phrase cannot be empty."

    word_count = len(normalized.split(" "))
    if word_count not in {12, 24}:
        return False, "Kasia seed phrase should contain 12 or 24 words."

    env = dict(os.environ)
    env["KASIA_SEED_TO_VALIDATE"] = normalized
    validator = (
        "import { Mnemonic } from './scripts/kasia-bridge/lib/kaspa_sdk.js'; "
        "new Mnemonic(process.env.KASIA_SEED_TO_VALIDATE || '');"
    )

    try:
        subprocess.run(
            ["node", "--input-type=module", "-e", validator],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except FileNotFoundError:
        logger.warning("Skipping full Kasia seed validation because Node is unavailable")
    except subprocess.TimeoutExpired:
        logger.warning("Skipping full Kasia seed validation because Node timed out")
    except subprocess.CalledProcessError:
        return (
            False,
            "Kasia seed phrase is not a valid Kasia/Kaspa mnemonic. Please check the words and try again.",
        )

    return True, None


def prompt_kasia_seed_phrase(
    *,
    get_env_value: Callable[[str], Optional[str]],
    prompt: Callable[[str, Optional[str], bool], str],
    print_info: Callable[[str], None],
    print_error: Callable[[str], None],
    validate_seed_phrase: Callable[[str], tuple[bool, str | None]] = validate_kasia_seed_phrase,
) -> str:
    """Prompt for a Kasia seed phrase, reusing any stored value when kept."""
    existing_seed = get_env_value("KASIA_SEED_PHRASE") or None
    print_info("🔒 Seed phrase input is hidden as you type.")
    if existing_seed:
        print_info("   Press Enter to keep the current stored seed phrase.")

    while True:
        seed_phrase = prompt(
            "Kasia seed phrase",
            default=existing_seed,
            password=True,
        )
        if not seed_phrase:
            return ""
        if existing_seed and seed_phrase == existing_seed:
            return seed_phrase

        is_valid, error = validate_seed_phrase(seed_phrase)
        if is_valid:
            return " ".join(seed_phrase.strip().split())

        print_error(error or "Invalid Kasia seed phrase.")


def run_kasia_setup_prompts(
    io: KasiaSetupIO,
    *,
    prompt_seed_phrase: Callable[[], str],
    announce_enabled: bool = True,
) -> None:
    """Prompt for Kasia settings and persist them through the provided callbacks."""
    io.save_env_value("KASIA_ENABLED", "true")
    if announce_enabled:
        io.print_success("Kasia enabled")

    seed_phrase = prompt_seed_phrase()
    if seed_phrase:
        io.save_env_value("KASIA_SEED_PHRASE", seed_phrase)
        io.print_success("Kasia seed phrase saved")

    indexer_url = io.prompt(
        "Kasia indexer URL",
        default=io.get_env_value("KASIA_INDEXER_URL") or DEFAULT_KASIA_INDEXER_URL,
        password=False,
    )
    if indexer_url:
        io.save_env_value("KASIA_INDEXER_URL", indexer_url.rstrip("/"))
        io.print_success("Kasia indexer URL saved")

    node_url = io.prompt(
        "Kaspa node URL",
        default=io.get_env_value("KASIA_NODE_WBORSH_URL") or DEFAULT_KASIA_NODE_WBORSH_URL,
        password=False,
    )
    if node_url:
        io.save_env_value("KASIA_NODE_WBORSH_URL", node_url)
        io.print_success("Kaspa node URL saved")

    network = io.prompt(
        "Kasia network",
        default=io.get_env_value("KASIA_NETWORK") or DEFAULT_KASIA_NETWORK,
        password=False,
    )
    if network:
        io.save_env_value("KASIA_NETWORK", network)

    kns_url = io.prompt(
        "Kasia KNS API URL",
        default=io.get_env_value("KASIA_KNS_URL") or None,
        password=False,
    )
    if kns_url:
        io.save_env_value("KASIA_KNS_URL", kns_url.rstrip("/"))
        io.print_success("Kasia KNS API URL saved")

    fee_policy = io.prompt(
        "Kasia fee policy",
        default=io.get_env_value("KASIA_FEE_POLICY") or DEFAULT_KASIA_FEE_POLICY,
        password=False,
    )
    if fee_policy:
        io.save_env_value("KASIA_FEE_POLICY", fee_policy)

    io.print_info("🔒 Security: decide who can handshake and message Hermes over Kasia")
    allow_all_default = _is_truthy(io.get_env_value("KASIA_ALLOW_ALL_USERS"))
    allow_all = io.prompt_yes_no(
        "Allow all Kasia users to message Hermes?",
        allow_all_default,
    )
    if allow_all:
        io.save_env_value("KASIA_ALLOW_ALL_USERS", "true")
        io.save_env_value("KASIA_ALLOWED_USERS", "")
        io.print_info("⚠️  Any Kasia address can now interact with Hermes.")
    else:
        io.save_env_value("KASIA_ALLOW_ALL_USERS", "false")
        allowed_users = io.prompt(
            "Allowed Kasia addresses (comma-separated, leave empty to set later)",
            default=io.get_env_value("KASIA_ALLOWED_USERS") or None,
            password=False,
        )
        if allowed_users:
            cleaned = ",".join(
                item.strip() for item in allowed_users.split(",") if item.strip()
            )
            io.save_env_value("KASIA_ALLOWED_USERS", cleaned)
            io.print_success("Kasia allowlist configured")
        else:
            io.print_warning(
                "No Kasia allowlist set yet. Add KASIA_ALLOWED_USERS later before opening access."
            )

    io.print_info("📬 Home Channel: where Hermes delivers cron job results and cross-platform messages.")
    io.print_info("   You can also set this later with /sethome in your Kasia chat.")
    home_channel = io.prompt(
        "Kasia home channel address (leave empty to set later)",
        default=io.get_env_value("KASIA_HOME_CHANNEL") or None,
        password=False,
    )
    if home_channel:
        io.save_env_value("KASIA_HOME_CHANNEL", home_channel.strip())
        io.print_success("Kasia home channel saved")


def kasia_summary_lines(
    get_env_value: Callable[[str], Optional[str]],
) -> list[str]:
    """Return a stable, operator-facing Kasia summary."""
    lines = [
        f"Indexer: {get_env_value('KASIA_INDEXER_URL') or '(not set)'}",
        f"Node: {get_env_value('KASIA_NODE_WBORSH_URL') or '(not set)'}",
        f"Network: {get_env_value('KASIA_NETWORK') or DEFAULT_KASIA_NETWORK}",
        f"Fee policy: {get_env_value('KASIA_FEE_POLICY') or DEFAULT_KASIA_FEE_POLICY}",
    ]
    kns_url = get_env_value("KASIA_KNS_URL")
    if kns_url:
        lines.append(f"KNS API: {kns_url}")
    return lines


def _is_truthy(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in _TRUE_VALUES
