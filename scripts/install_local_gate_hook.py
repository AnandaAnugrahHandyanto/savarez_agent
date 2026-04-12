#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path


MANAGED_MARKER = "# Managed by scripts/install_local_gate_hook.py"
HOOK_BODY = f"""#!/usr/bin/env bash
set -euo pipefail
{MANAGED_MARKER}

repo_root=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [ -z "${{repo_root:-}}" ]; then
  exit 0
fi
cd "$repo_root"

if [ ! -f "scripts/validate_gate.py" ]; then
  exit 0
fi

if [ ! -d ".hermes-gate" ] && [ ! -f "scripts/write_gate.py" ]; then
  exit 0
fi

python_bin="${{HERMES_GATE_PYTHON:-}}"
if [ -z "${{python_bin:-}}" ] && [ -x "$repo_root/venv/bin/python" ]; then
  python_bin="$repo_root/venv/bin/python"
elif [ -z "${{python_bin:-}}" ] && [ -x "$repo_root/.venv/bin/python" ]; then
  python_bin="$repo_root/.venv/bin/python"
else
  python_bin="${{python_bin:-python3}}"
fi

exec "$python_bin" scripts/validate_gate.py --gate-file "${{HERMES_GATE_FILE:-.hermes-gate/gate.json}}"
"""


def git_output(*args: str, allow_empty: bool = False, cwd: Path | None = None) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        if allow_empty:
            return ""
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def ensure_repo_root() -> Path:
    return Path(git_output("rev-parse", "--show-toplevel"))


def resolve_hooks_dir(repo_root: Path, override: str | None) -> Path:
    if override:
        return Path(override).expanduser().resolve()

    hooks_path = git_output("config", "--get", "core.hooksPath", allow_empty=True, cwd=repo_root)
    if hooks_path:
        hooks_dir = Path(hooks_path).expanduser()
        if not hooks_dir.is_absolute():
            hooks_dir = repo_root / hooks_dir
        return hooks_dir.resolve()

    git_hooks_path = git_output("rev-parse", "--git-path", "hooks", cwd=repo_root)
    hooks_dir = Path(git_hooks_path)
    if not hooks_dir.is_absolute():
        hooks_dir = repo_root / hooks_dir
    return hooks_dir.resolve()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Install the managed local gate pre-push hook")
    p.add_argument("--hooks-dir", help="Override hooks directory (default: git core.hooksPath or .git/hooks)")
    p.add_argument("--hook-name", default="pre-push")
    p.add_argument("--force", action="store_true", help="Overwrite an unmanaged existing hook")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = ensure_repo_root()
    hooks_dir = resolve_hooks_dir(repo_root, args.hooks_dir)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / args.hook_name

    if hook_path.exists():
        existing = hook_path.read_text(encoding="utf-8")
        if MANAGED_MARKER not in existing and not args.force:
            print(
                f"refusing to overwrite unmanaged hook: {hook_path} (use --force)",
                file=sys.stderr,
            )
            return 1

    hook_path.write_text(HOOK_BODY, encoding="utf-8")
    hook_path.chmod(0o755)
    print(hook_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
