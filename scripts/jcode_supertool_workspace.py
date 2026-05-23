#!/usr/bin/env python3
"""Prepare a runnable jcode-hosted Hermes supertool workspace."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JCODE = (
    ROOT / "upstreams" / "jcode"
    if (ROOT / "upstreams" / "jcode").exists()
    else ROOT / ".codex-research" / "jcode"
)
DEFAULT_OUTPUT = ROOT / ".supertool" / "jcode-hermes"
DEFAULT_PATCH = ROOT / "patches" / "jcode" / "register-external-toolset.patch"
DEFAULT_OVERLAY_PATCH = ROOT / "patches" / "jcode" / "register-hermes-native-toolset.patch"
NATIVE_TOOL_DIR = ROOT / "bridges" / "jcode-native-hermes-tool"


LAUNCHER = """#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/supertool.env"

if [[ -x "$ROOT_DIR/jcode/target/debug/jcode" ]]; then
  exec "$ROOT_DIR/jcode/target/debug/jcode" "$@"
fi

exec cargo run --manifest-path "$ROOT_DIR/jcode/Cargo.toml" -- "$@"
"""


README_TEMPLATE = """# jcode Hermes Supertool Workspace

This workspace is a runnable Rust-first Hermes/jcode supertool experiment.
jcode is the host runtime. Hermes capabilities are loaded as native jcode
tools through the patched jcode registry.

Key files:

- `jcode/`: jcode checkout with the generic external-toolset hook and Hermes
  native tool overlay applied.
- `jcode/bridges/jcode-native-hermes-tool/`: copied Hermes-backed jcode Tool
  crate.
- `supertool.env`: exports the Hermes service command used by jcode registry
  auto-registration.
- `run-jcode-supertool.sh`: runs the patched jcode workspace with that env.

Try it:

```bash
./run-jcode-supertool.sh --help
./run-jcode-supertool.sh
```

The registry overlay auto-registers Hermes tools when
`JCODE_HERMES_SERVICE_COMMAND_JSON` or `JCODE_HERMES_SERVICE_COMMAND` is set.
This keeps Hermes features inside jcode's Rust tool loop instead of routing
through a second visible agent.
"""


def _check(name: str, ok: bool, **details: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"name": name, "ok": bool(ok)}
    result.update(details)
    return result


def _run(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _safe_remove_output(output: Path) -> None:
    resolved = output.expanduser().resolve()
    forbidden = {Path("/").resolve(), Path.home().resolve(), ROOT.resolve()}
    if resolved in forbidden or ROOT.resolve() in resolved.parents:
        # Allow removing ROOT/.supertool children, but not the repo itself.
        if not str(resolved).startswith(str((ROOT / ".supertool").resolve())):
            raise ValueError(f"refusing to remove unsafe output path: {resolved}")
    if len(resolved.parts) < 4:
        raise ValueError(f"refusing to remove shallow output path: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def _copy_jcode(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(".git", "target", "graphify-out"),
    )


def _prepare_jcode(
    source: Path,
    destination: Path,
    *,
    mode: str,
) -> tuple[str, subprocess.CompletedProcess[str] | None]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if mode in {"auto", "worktree"} and (source / ".git").exists():
        completed = _run(
            [
                "git",
                "-C",
                str(source),
                "worktree",
                "add",
                "--detach",
                str(destination),
                "HEAD",
            ],
            cwd=destination.parent,
        )
        if completed.returncode == 0:
            return "git_worktree", completed
        if mode == "worktree":
            return "git_worktree_failed", completed

    _copy_jcode(source, destination)
    return "copy", None


def _copy_native_tool(destination: Path) -> None:
    shutil.copytree(
        NATIVE_TOOL_DIR,
        destination,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("target", "__pycache__", "*.pyc"),
    )
    cargo_toml = destination / "Cargo.toml"
    text = cargo_toml.read_text(encoding="utf-8")
    text = text.replace(
        "../../upstreams/jcode/crates/jcode-tool-core",
        "../../crates/jcode-tool-core",
    )
    text = text.replace(
        "../../upstreams/jcode/crates/jcode-tool-types",
        "../../crates/jcode-tool-types",
    )
    cargo_toml.write_text(text, encoding="utf-8")


def _service_command(hermes_root: Path) -> list[str]:
    script = hermes_root / "scripts" / "hermes_service_bridge.py"
    return ["python3", str(script), "stdio"]


def _write_env(output: Path, hermes_root: Path, timeout_ms: int) -> Path:
    env_path = output / "supertool.env"
    service_command = _service_command(hermes_root)
    env_path.write_text(
        "\n".join([
            f"export JCODE_BRIDGE_ROOT={json.dumps(str(hermes_root))}",
            "export JCODE_HERMES_SERVICE_COMMAND_JSON="
            + json.dumps(json.dumps(service_command)),
            f"export JCODE_HERMES_TIMEOUT_MS={json.dumps(str(timeout_ms))}",
            "",
        ]),
        encoding="utf-8",
    )
    return env_path


def _write_launcher(output: Path) -> Path:
    launcher = output / "run-jcode-supertool.sh"
    launcher.write_text(LAUNCHER, encoding="utf-8")
    launcher.chmod(0o755)
    return launcher


def _write_readme(output: Path) -> Path:
    readme = output / "README.md"
    readme.write_text(README_TEMPLATE, encoding="utf-8")
    return readme


def prepare_supertool_workspace(
    *,
    jcode_path: Path,
    output: Path,
    hermes_root: Path,
    patch_path: Path,
    overlay_patch_path: Path,
    mode: str,
    force: bool,
    timeout_ms: int,
    cargo_check: bool,
    target_dir: Path | None,
) -> dict[str, Any]:
    jcode_path = jcode_path.expanduser().resolve()
    output = output.expanduser().resolve()
    hermes_root = hermes_root.expanduser().resolve()
    patch_path = patch_path.expanduser().resolve()
    overlay_patch_path = overlay_patch_path.expanduser().resolve()
    target_dir = target_dir.expanduser().resolve() if target_dir else None

    checks: list[dict[str, Any]] = [
        _check("jcode_checkout:exists", jcode_path.is_dir(), path=str(jcode_path)),
        _check("hermes_root:exists", hermes_root.is_dir(), path=str(hermes_root)),
        _check(
            "service_script:exists",
            (hermes_root / "scripts" / "hermes_service_bridge.py").is_file(),
        ),
        _check("patch:exists", patch_path.is_file(), path=str(patch_path)),
        _check(
            "overlay_patch:exists",
            overlay_patch_path.is_file(),
            path=str(overlay_patch_path),
        ),
        _check("native_tool:exists", NATIVE_TOOL_DIR.is_dir(), path=str(NATIVE_TOOL_DIR)),
    ]
    if not all(item["ok"] for item in checks):
        return {
            "success": False,
            "checks": checks,
            "output": str(output),
            "jcode_path": str(jcode_path),
        }

    if output.exists():
        if not force:
            checks.append(_check(
                "output:available",
                False,
                path=str(output),
                error="output already exists; pass --force to replace it",
            ))
            return {
                "success": False,
                "checks": checks,
                "output": str(output),
                "jcode_path": str(jcode_path),
            }
        _safe_remove_output(output)

    output.mkdir(parents=True, exist_ok=True)
    jcode_destination = output / "jcode"
    prepared_mode, prepare_result = _prepare_jcode(
        jcode_path,
        jcode_destination,
        mode=mode,
    )
    checks.append(_check(
        "jcode_workspace:prepared",
        jcode_destination.is_dir() and prepared_mode != "git_worktree_failed",
        mode=prepared_mode,
        path=str(jcode_destination),
        stdout=(prepare_result.stdout[-4000:] if prepare_result else ""),
        stderr=(prepare_result.stderr[-4000:] if prepare_result else ""),
        returncode=(prepare_result.returncode if prepare_result else 0),
    ))
    if not checks[-1]["ok"]:
        return {
            "success": False,
            "checks": checks,
            "output": str(output),
            "jcode_path": str(jcode_path),
        }

    patch_completed = _run(
        ["git", "apply", "--unidiff-zero", str(patch_path)],
        cwd=jcode_destination,
    )
    checks.append(_check(
        "jcode_patch:applied",
        patch_completed.returncode == 0,
        returncode=patch_completed.returncode,
        stdout=patch_completed.stdout[-4000:],
        stderr=patch_completed.stderr[-4000:],
    ))

    native_destination = jcode_destination / "bridges" / "jcode-native-hermes-tool"
    if patch_completed.returncode == 0:
        _copy_native_tool(native_destination)
    checks.append(_check(
        "native_tool:copied_into_jcode",
        (native_destination / "Cargo.toml").exists()
        and (native_destination / "src" / "lib.rs").exists(),
        path=str(native_destination),
    ))

    overlay_completed = _run(
        ["git", "apply", "--unidiff-zero", str(overlay_patch_path)],
        cwd=jcode_destination,
    )
    checks.append(_check(
        "jcode_overlay_patch:applied",
        overlay_completed.returncode == 0,
        returncode=overlay_completed.returncode,
        stdout=overlay_completed.stdout[-4000:],
        stderr=overlay_completed.stderr[-4000:],
    ))

    env_path = _write_env(output, hermes_root, timeout_ms)
    launcher = _write_launcher(output)
    readme = _write_readme(output)
    env_text = env_path.read_text(encoding="utf-8")
    registry_text = (jcode_destination / "src" / "tool" / "mod.rs").read_text(
        encoding="utf-8",
        errors="replace",
    )
    cargo_text = (jcode_destination / "Cargo.toml").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks.extend([
        _check(
            "env:writes_service_command",
            "JCODE_HERMES_SERVICE_COMMAND_JSON" in env_text,
            path=str(env_path),
        ),
        _check(
            "launcher:writes_runnable_entrypoint",
            os.access(launcher, os.X_OK),
            path=str(launcher),
        ),
        _check("readme:written", readme.exists(), path=str(readme)),
        _check(
            "jcode_registry:auto_registration_configured",
            "JCODE_HERMES_SERVICE_COMMAND_JSON" in registry_text
            and "default_hermes_toolset" in registry_text,
            path=str(jcode_destination / "src" / "tool" / "mod.rs"),
        ),
        _check(
            "jcode_cargo:depends_on_native_hermes_tool",
            'jcode-native-hermes-tool = { path = "bridges/jcode-native-hermes-tool" }'
            in cargo_text,
            path=str(jcode_destination / "Cargo.toml"),
        ),
    ])

    if cargo_check:
        env = os.environ.copy()
        env["JCODE_HERMES_SERVICE_COMMAND_JSON"] = json.dumps(_service_command(hermes_root))
        env["JCODE_HERMES_TIMEOUT_MS"] = str(timeout_ms)
        if target_dir is not None:
            env["CARGO_TARGET_DIR"] = str(target_dir)
        completed = _run(
            ["cargo", "check", "--manifest-path", str(jcode_destination / "Cargo.toml")],
            cwd=jcode_destination,
            env=env,
        )
        checks.append(_check(
            "cargo:check_jcode_workspace",
            completed.returncode == 0,
            returncode=completed.returncode,
            stdout=completed.stdout[-4000:],
            stderr=completed.stderr[-4000:],
            target_dir=(str(target_dir) if target_dir else None),
        ))

    return {
        "success": all(item["ok"] for item in checks),
        "checks": checks,
        "output": str(output),
        "jcode_path": str(jcode_path),
        "jcode_workspace": str(jcode_destination),
        "hermes_root": str(hermes_root),
        "env_file": str(env_path),
        "launcher": str(launcher),
        "service_command": _service_command(hermes_root),
        "usage": [
            f"cd {output}",
            "./run-jcode-supertool.sh --help",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jcode", default=str(DEFAULT_JCODE), help="Path to a jcode checkout.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output workspace directory.")
    parser.add_argument("--hermes-root", default=str(ROOT), help="Hermes or mother-repo root.")
    parser.add_argument("--patch", default=str(DEFAULT_PATCH), help="Generic jcode toolset patch.")
    parser.add_argument(
        "--overlay-patch",
        default=str(DEFAULT_OVERLAY_PATCH),
        help="Hermes auto-registration overlay patch.",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "worktree", "copy"),
        default="auto",
        help="How to materialize the jcode workspace.",
    )
    parser.add_argument("--force", action="store_true", help="Replace an existing output directory.")
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=60_000,
        help="Hermes service timeout exported to the jcode workspace.",
    )
    parser.add_argument(
        "--cargo-check",
        action="store_true",
        help="Run cargo check for the patched jcode workspace.",
    )
    parser.add_argument("--target-dir", help="Optional CARGO_TARGET_DIR for --cargo-check.")
    ns = parser.parse_args(argv)

    report = prepare_supertool_workspace(
        jcode_path=Path(ns.jcode),
        output=Path(ns.output),
        hermes_root=Path(ns.hermes_root),
        patch_path=Path(ns.patch),
        overlay_patch_path=Path(ns.overlay_patch),
        mode=ns.mode,
        force=bool(ns.force),
        timeout_ms=int(ns.timeout_ms),
        cargo_check=bool(ns.cargo_check),
        target_dir=(Path(ns.target_dir) if ns.target_dir else None),
    )
    print(json.dumps(report, indent=2, ensure_ascii=True, sort_keys=True))
    return 0 if report.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
