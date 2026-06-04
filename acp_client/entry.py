"""CLI entry for the Hermes ACP client subsystem.

Self-test paths:

    python -m acp_client --check     # verify acp + acp_client import cleanly
    python -m acp_client --version   # print Hermes version

The ``--run-kanban-task`` path is the explicitly gated Phase-2 outbound runner:
it is only spawned by the Kanban dispatcher after the ACP transport env and the
``HERMES_ACP_ALLOW_LAUNCH=1`` launch guard both resolve to ACP.
"""

from __future__ import annotations

import argparse
import sys


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="hermes-acp-client",
        description="Self-test and gated outbound runner for the Hermes ACP client subsystem.",
    )
    parser.add_argument("--version", action="store_true", help="Print Hermes version and exit")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the acp dependency and acp_client modules import, then exit",
    )
    parser.add_argument(
        "--run-kanban-task",
        metavar="TASK_ID",
        help="Run one claimed Kanban task through the gated ACP outbound lane",
    )
    parser.add_argument(
        "--workspace",
        help="Workspace path for --run-kanban-task (defaults to HERMES_KANBAN_WORKSPACE)",
    )
    parser.add_argument(
        "--backend",
        default="claude",
        help="ACP backend registry key for --run-kanban-task (default: claude)",
    )
    return parser.parse_args(argv)


def _run_check() -> None:
    import acp  # noqa: F401

    from acp_client.connection import OutboundConnection  # noqa: F401
    from acp_client.event_translator import EventTranslator  # noqa: F401
    from acp_client.outbound_session import OutboundSessionManager  # noqa: F401
    from acp_client.permission_relay import PermissionRelay  # noqa: F401
    from acp_client.transport_registry import TransportRegistry  # noqa: F401

    print("Hermes ACP client check OK")


def _print_version() -> None:
    from hermes_cli import __version__ as hermes_version

    print(hermes_version)


async def _run_kanban_task(task_id: str, *, workspace: str | None, backend: str) -> int:
    """Run a claimed Kanban task through ACP and write the result back."""
    import os

    from acp_client.kanban_runner import ProgressWriter, build_launch_plan, run_acp_lane
    from hermes_cli import kanban_db as kb

    workspace = workspace or os.environ.get("HERMES_KANBAN_WORKSPACE") or os.getcwd()
    run_id_raw = os.environ.get("HERMES_KANBAN_RUN_ID")
    expected_run_id = int(run_id_raw) if run_id_raw and run_id_raw.isdigit() else None

    base_env = dict(os.environ)
    plan = build_launch_plan(workspace=workspace, backend=backend, env=base_env, strict=True)
    with kb.connect_closing() as conn:
        prompt = kb.build_worker_context(conn, task_id)

    decision = await run_acp_lane(
        plan,
        workspace=workspace,
        prompt_text=prompt,
        progress=ProgressWriter(workspace),
        allow_launch=True,
        base_env=base_env,
    )

    metadata = {
        "transport": "acp",
        "backend": plan.backend,
        "writeback_reason": decision.reason,
    }
    with kb.connect_closing() as conn:
        if decision.action == "complete":
            ok = kb.complete_task(
                conn,
                task_id,
                result=decision.summary,
                summary=decision.summary,
                metadata=metadata,
                expected_run_id=expected_run_id,
            )
        else:
            ok = kb.block_task(
                conn,
                task_id,
                reason=f"ACP lane blocked: {decision.reason}\n\n{decision.summary}",
                expected_run_id=expected_run_id,
            )
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.version:
        _print_version()
        return
    if args.check:
        _run_check()
        return
    if args.run_kanban_task:
        import asyncio

        raise SystemExit(
            asyncio.run(
                _run_kanban_task(
                    args.run_kanban_task,
                    workspace=args.workspace,
                    backend=args.backend,
                )
            )
        )
    # No server mode — print usage and exit non-zero so callers do not mistake a
    # bare invocation for a running transport.
    print(
        "acp_client is library-first; use --check or --run-kanban-task in a "
        "dispatcher-gated context.",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
