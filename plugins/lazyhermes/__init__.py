from __future__ import annotations

from pathlib import Path

from . import core


def register(ctx) -> None:
    base = Path(__file__).resolve().parent

    ctx.register_hook("pre_llm_call", core.pre_llm_call)

    ctx.register_command(
        "ulw-plan",
        core.command_ulw_plan,
        description="Create a durable Ultrawork implementation plan",
        args_hint='"what to build"',
    )
    ctx.register_command(
        "ultrawork-plan",
        core.command_ulw_plan,
        description="Alias for /ulw-plan",
        args_hint='"what to build"',
    )
    ctx.register_command(
        "ulw",
        core.command_ulw,
        description="Start an Ultrawork run and execute the task immediately",
        args_hint='"task" [--completion-promise TEXT] [--strategy reset|continue]',
    )
    ctx.register_command(
        "ulw-loop",
        core.command_ulw_loop,
        description="Start an Ultrawork run and execute the task immediately",
        args_hint='"task" [--completion-promise TEXT] [--strategy reset|continue]',
    )
    ctx.register_command(
        "ultrawork-loop",
        core.command_ulw_loop,
        description="Alias for /ulw-loop",
        args_hint='"task" [--completion-promise TEXT] [--strategy reset|continue]',
    )
    ctx.register_command(
        "start-work",
        core.command_start_work,
        description="Open or dry-run a LazyHermes plan against a workspace",
        args_hint="[plan-name] [--worktree PATH] [--dry-run]",
    )

    ctx.register_skill(
        "ultrawork",
        base / "skills" / "ultrawork" / "SKILL.md",
        "Hermes-native Ultrawork execution discipline.",
    )
    ctx.register_skill(
        "rules",
        base / "skills" / "rules" / "SKILL.md",
        "Read and apply repo-local Hermes guidance files.",
    )
    ctx.register_skill(
        "lsp",
        base / "skills" / "lsp" / "SKILL.md",
        "Use Hermes' native LSP diagnostics and symbol tooling.",
    )
