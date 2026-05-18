"""Local preflight assembly for CMH subprocess wrappers.

This module intentionally does not execute subprocesses. It only checks halt
flags, resolves binaries, verifies static flag evidence, checks envelope budget,
and assembles argv tuples for later wrapper layers.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable

from agent.cmh_subprocess.envelope import check_budget, load_envelope_state
from agent.cmh_subprocess.flags import (
    CLAUDE_REQUIRED_FLAGS,
    CODEX_REQUIRED_FLAGS_UNRESOLVED,
    validate_flags,
)
from agent.cmh_subprocess.halt_flags import is_halted
from agent.cmh_subprocess.result import PreflightResult

CLAUDE_HELP_EVIDENCE = """
Usage: claude [options] [prompt]
  -p, --print                                       Print response and exit
  --max-budget-usd <amount>                         Maximum dollar amount to spend on API calls
  --output-format <format>                          Output format
  --no-session-persistence                          Disable session persistence
"""

BinaryResolver = Callable[[str], str | None]


def default_binary_resolver(binary_name: str) -> str | None:
    """Resolve a binary name using PATH without executing the binary."""
    return shutil.which(binary_name)


def prepare_claude_print_invocation(
    prompt: str,
    *,
    binary_resolver: BinaryResolver = default_binary_resolver,
    help_text: str = CLAUDE_HELP_EVIDENCE,
    priority: bool = False,
    max_budget_usd: str = "0.01",
    output_format: str = "text",
) -> PreflightResult:
    """Preflight a safe Claude print invocation without running Claude.

    Order is intentionally fixed: halt, binary, flags, budget, argv assembly.
    """
    halted = is_halted("cowork_headless")
    if halted.halted:
        return PreflightResult(
            status="halted",
            ok=False,
            message=halted.message,
            details={"active_flag": halted.active_flag},
        )

    binary = binary_resolver("claude")
    if not binary:
        return PreflightResult(
            status="missing_binary",
            ok=False,
            message="Required claude binary was not found on PATH",
        )

    flags = validate_flags("claude", help_text, required_flags=CLAUDE_REQUIRED_FLAGS)
    if not flags.ok:
        return PreflightResult(
            status="missing_required_flag",
            ok=False,
            message="Claude help evidence is missing required flags: "
            + ", ".join(flags.missing_required_flags),
            details={
                "missing_required_flags": flags.missing_required_flags,
                "available_flags": flags.available_flags,
            },
        )

    budget = check_budget(load_envelope_state(), "anthropic_max", priority=priority)
    if not budget.allowed:
        return PreflightResult(
            status=budget.reason,
            ok=False,
            message=(
                f"Claude envelope budget blocked: used {budget.used} "
                f"of cap {budget.cap}"
            ),
            details={
                "used": budget.used,
                "cap": budget.cap,
                "available": budget.available,
            },
        )

    argv = (
        binary,
        "--print",
        "--max-budget-usd",
        max_budget_usd,
        "--output-format",
        output_format,
        "--no-session-persistence",
        prompt,
    )
    return PreflightResult(
        status="ready",
        ok=True,
        message="Claude print invocation preflight passed",
        argv=argv,
        details={
            "budget_reason": budget.reason,
            "used": budget.used,
            "cap": budget.cap,
            "available": budget.available,
        },
    )


def prepare_codex_print_invocation(
    prompt: str,
    *,
    binary_resolver: BinaryResolver = default_binary_resolver,
    priority: bool = False,
) -> PreflightResult:
    """Preflight a Codex invocation without running Codex.

    Order is intentionally fixed: halt, binary, budget, unresolved flag gate.
    """
    del prompt  # Codex argv shape is intentionally unresolved in this foundation task.

    halted = is_halted("codex_auto_dispatch")
    if halted.halted:
        return PreflightResult(
            status="halted",
            ok=False,
            message=halted.message,
            details={"active_flag": halted.active_flag},
        )

    binary = binary_resolver("codex")
    if not binary:
        return PreflightResult(
            status="missing_binary",
            ok=False,
            message="Required codex binary was not found on PATH",
        )

    budget = check_budget(load_envelope_state(), "chatgpt_pro", priority=priority)
    if not budget.allowed:
        return PreflightResult(
            status=budget.reason,
            ok=False,
            message=(
                f"Codex envelope budget blocked: used {budget.used} "
                f"of cap {budget.cap}"
            ),
            details={
                "used": budget.used,
                "cap": budget.cap,
                "available": budget.available,
            },
        )

    return PreflightResult(
        status="missing_verified_flags",
        ok=False,
        message="Codex subprocess flags are not yet verified for safe argv assembly",
        details={"required_flags": list(CODEX_REQUIRED_FLAGS_UNRESOLVED)},
    )
