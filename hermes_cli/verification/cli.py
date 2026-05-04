from __future__ import annotations

import argparse
import json
from pathlib import Path

from hermes_cli.verification.commands import run_command_check
from hermes_cli.verification.discovery import DEFAULT_FAMILY_MAP, discover_commands
from hermes_cli.verification.repo_state import collect_repo_state
from hermes_cli.verification.report import VerificationCheck, VerificationReport


def build_report(
    *,
    repo: str | Path,
    task_type: str | None,
    commands: list[str],
    output: str | Path,
    timeout_seconds: float,
    family_map_path: str | Path | None = DEFAULT_FAMILY_MAP,
) -> VerificationReport:
    repo_path = Path(repo).expanduser().resolve()
    output_path = Path(output).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    repo_state = collect_repo_state(repo_path)
    report = VerificationReport(
        repo=repo_state.repo,
        task_type=task_type,
        branch=repo_state.branch,
        sha=repo_state.sha,
        dirty=repo_state.dirty,
        changed_files=repo_state.changed_files,
    )
    for limitation in repo_state.limitations:
        report.add_limitation(limitation)

    discovered = discover_commands(
        repo=repo_path,
        explicit_commands=commands,
        family_map_path=family_map_path,
    )
    if not discovered:
        report.add_check(
            VerificationCheck(
                name="command checks",
                kind="command",
                status="not_run",
                message="No verification commands supplied or discovered",
            )
        )
        report.add_limitation("No verification commands ran")
        return report

    command_logs_dir = output_path / "logs"
    for discovered_command in discovered:
        check, artifact = run_command_check(
            name=discovered_command.name,
            command=discovered_command.command,
            cwd=repo_path,
            output_dir=command_logs_dir,
            timeout_seconds=timeout_seconds,
        )
        check.message = (
            f"source={discovered_command.source}"
            if check.message is None
            else f"{check.message}; source={discovered_command.source}"
        )
        report.add_check(check)
        report.add_artifact(artifact)
    return report


def write_report(report: VerificationReport, output: str | Path) -> tuple[Path, Path]:
    output_path = Path(output).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "verification.json"
    markdown_path = output_path / "verification.md"
    json_path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(report.to_markdown(), encoding="utf-8")
    return json_path, markdown_path


def run_verify(
    *,
    repo: str | Path,
    task_type: str | None = None,
    commands: list[str] | None = None,
    output: str | Path,
    timeout_seconds: float = 300,
    family_map_path: str | Path | None = DEFAULT_FAMILY_MAP,
) -> int:
    report = build_report(
        repo=repo,
        task_type=task_type,
        commands=commands or [],
        output=output,
        timeout_seconds=timeout_seconds,
        family_map_path=family_map_path,
    )
    _, markdown_path = write_report(report, output)
    print(markdown_path)
    return 1 if report.status == "failed" else 0


def add_verify_parser(subparsers) -> None:
    parser = subparsers.add_parser(
        "verify",
        help="Run verification checks and write evidence reports",
        description="Run repo verification checks and write verification.json/verification.md artifacts.",
    )
    parser.add_argument("--repo", required=True, help="Repository path to verify")
    parser.add_argument("--task-type", default=None, help="Task type label, e.g. web-ui or mobile-ui")
    parser.add_argument(
        "--command",
        dest="verify_commands",
        action="append",
        default=[],
        help="Verification command to run. May be supplied multiple times.",
    )
    parser.add_argument("--output", required=True, help="Output directory for verification artifacts")
    parser.add_argument(
        "--timeout",
        type=float,
        default=300,
        help="Timeout per command in seconds (default: 300)",
    )
    parser.set_defaults(func=cmd_verify)


def cmd_verify(args: argparse.Namespace) -> None:
    raise SystemExit(
        run_verify(
            repo=args.repo,
            task_type=args.task_type,
            commands=args.verify_commands,
            output=args.output,
            timeout_seconds=args.timeout,
        )
    )
