"""CLI command for the QuestFrame Hermes plugin."""

from __future__ import annotations

import argparse
import json

from . import core


def register_cli(subparser: argparse.ArgumentParser) -> None:
    subs = subparser.add_subparsers(dest="questframe_command")

    setup = subs.add_parser("setup", help="Save QuestFrame bridge paths")
    setup.add_argument("--launcher-exe", default="")
    setup.add_argument("--unity-python", default="")
    setup.add_argument("--vcc-project-root", action="append", default=[])

    subs.add_parser("status", help="Show QuestFrame bridge readiness")

    preflight = subs.add_parser("preflight", help="Run FH6VR preflight")
    preflight.add_argument("--launcher-exe", default="")
    preflight.add_argument("--report-path", default="")
    preflight.add_argument("--timeout-seconds", type=int, default=None)

    session = subs.add_parser(
        "session-readiness", help="Run FH6VR OpenXR session-readiness probe"
    )
    session.add_argument("--launcher-exe", default="")
    session.add_argument("--timeout-seconds", type=int, default=None)

    unity_scan = subs.add_parser("unity-scan", help="Scan Unity/VCC projects")
    unity_scan.add_argument("--project-path", default="")
    unity_scan.add_argument("--max-projects", type=int, default=None)

    subparser.set_defaults(func=questframe_command)


def questframe_command(args: argparse.Namespace) -> int:
    command = getattr(args, "questframe_command", None)
    if not command:
        print("usage: hermes questframe {setup,status,preflight,session-readiness,unity-scan}")
        return 2
    if command == "setup":
        return _print(
            core.save_setup_values(
                {
                    "launcher_exe": getattr(args, "launcher_exe", ""),
                    "unity_python": getattr(args, "unity_python", ""),
                    "vcc_project_roots": getattr(args, "vcc_project_root", []) or [],
                }
            )
        )
    if command == "status":
        return _print(core.status())
    if command == "preflight":
        return _print(
            core.run_launcher(
                "preflight",
                launcher_exe=getattr(args, "launcher_exe", "") or None,
                extra_args=_preflight_args(getattr(args, "report_path", "")),
                timeout_seconds=getattr(args, "timeout_seconds", None),
            )
        )
    if command == "session-readiness":
        return _print(
            core.run_launcher(
                "session-readiness-selftest",
                launcher_exe=getattr(args, "launcher_exe", "") or None,
                extra_args=["--json"],
                timeout_seconds=getattr(args, "timeout_seconds", None),
            )
        )
    if command == "unity-scan":
        return _print(
            core.scan_unity_projects(
                project_path=getattr(args, "project_path", "") or None,
                max_projects=getattr(args, "max_projects", None),
            )
        )
    print(f"unknown command: {command}")
    return 2


def _preflight_args(report_path: str) -> list[str]:
    args = ["--json"]
    if report_path:
        args.extend(["--write-report", report_path])
    return args


def _print(data: dict) -> int:
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if data.get("ok") else 1
