"""CLI command for the AITuber OnAir Hermes plugin."""

from __future__ import annotations

import argparse
import json

from . import core


def register_cli(subparser: argparse.ArgumentParser) -> None:
    subs = subparser.add_subparsers(dest="aituber_onair_command")

    configure = subs.add_parser("configure", aliases=["setup"], help="Save Hakua bridge settings")
    configure.add_argument("--repo-root", default="")
    configure.add_argument("--model", default="")
    configure.add_argument("--fbx-port", type=int, default=None)
    configure.add_argument("--system-prompt", default="")

    subs.add_parser("status", help="Show AITuber OnAir bridge readiness")

    prepare = subs.add_parser("prepare", help="Prepare Codex SDK character chat")
    prepare.add_argument("--repo-root", default="")
    prepare.add_argument("--no-install-codex-sdk", action="store_true")
    prepare.add_argument("--no-build-chat", action="store_true")
    prepare.add_argument("--build-fbx-app", action="store_true")
    prepare.add_argument("--timeout-seconds", type=int, default=None)

    start = subs.add_parser("start", help="Start the FBX React app")
    start.add_argument("--repo-root", default="")
    start.add_argument("--fbx-port", type=int, default=None)
    start.add_argument("--force", action="store_true")

    stop = subs.add_parser("stop", help="Stop the plugin-managed FBX React app")
    stop.add_argument("--force", action="store_true")

    say = subs.add_parser("say", help="Ask Hakua to reply once through Codex Auth")
    say.add_argument("prompt", nargs="*")
    say.add_argument("--repo-root", default="")
    say.add_argument("--model", default="")
    say.add_argument("--response-length", default="")
    say.add_argument("--timeout-seconds", type=int, default=None)

    smoke = subs.add_parser("smoke", help="Run a short Hakua readiness prompt")
    smoke.add_argument("--repo-root", default="")
    smoke.add_argument("--timeout-seconds", type=int, default=None)

    subparser.set_defaults(func=aituber_onair_command)


def aituber_onair_command(args: argparse.Namespace) -> int:
    command = getattr(args, "aituber_onair_command", None)
    if not command:
        print("usage: hermes aituber-onair {configure,status,prepare,start,stop,say,smoke}")
        return 2
    if command in {"configure", "setup"}:
        return _print(
            core.save_hakua_config(
                {
                    "repo_root": getattr(args, "repo_root", ""),
                    "model": getattr(args, "model", ""),
                    "fbx_port": getattr(args, "fbx_port", None),
                    "system_prompt": getattr(args, "system_prompt", ""),
                }
            )
        )
    if command == "status":
        return _print(core.status())
    if command == "prepare":
        return _print(
            core.prepare(
                {
                    "repo_root": getattr(args, "repo_root", ""),
                    "install_codex_sdk": not getattr(args, "no_install_codex_sdk", False),
                    "build_chat": not getattr(args, "no_build_chat", False),
                    "build_fbx_app": getattr(args, "build_fbx_app", False),
                    "timeout_seconds": getattr(args, "timeout_seconds", None),
                }
            )
        )
    if command == "start":
        return _print(
            core.start_fbx_app(
                {
                    "repo_root": getattr(args, "repo_root", ""),
                    "fbx_port": getattr(args, "fbx_port", None),
                    "force": getattr(args, "force", False),
                }
            )
        )
    if command == "stop":
        return _print(core.stop_fbx_app({"force": getattr(args, "force", False)}))
    if command == "say":
        return _print(
            core.run_hakua_once(
                {
                    "prompt": " ".join(getattr(args, "prompt", [])).strip(),
                    "repo_root": getattr(args, "repo_root", ""),
                    "model": getattr(args, "model", ""),
                    "response_length": getattr(args, "response_length", ""),
                    "timeout_seconds": getattr(args, "timeout_seconds", None),
                }
            )
        )
    if command == "smoke":
        payload = json.loads(
            core.handle_smoke(
                {
                    "repo_root": getattr(args, "repo_root", ""),
                    "timeout_seconds": getattr(args, "timeout_seconds", None),
                }
            )
        )
        return _print(payload)
    print("unknown aituber-onair command")
    return 2


def _print(payload: dict) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 1
