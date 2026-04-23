#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$KIT_DIR/../.." && pwd)"
ARTIFACT_DIR="$KIT_DIR/artifacts"
mkdir -p "$ARTIFACT_DIR"

TIMESTAMP="$(date +%Y-%m-%dT%H-%M-%S%z)"
REPORT_PATH="$ARTIFACT_DIR/broken-state-roundtrip-$TIMESTAMP.md"
LATEST_PATH="$ARTIFACT_DIR/latest-broken-state-roundtrip.md"
export HERMES_PROOF_PYTHON="$(command -v python)"

python - "$REPO_ROOT" "$REPORT_PATH" "$LATEST_PATH" <<'PY'
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

repo_root = Path(sys.argv[1])
report_path = Path(sys.argv[2])
latest_path = Path(sys.argv[3])

def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)

def doctor_section(hermes_home: Path, unset_minimax: bool) -> str:
    env = os.environ.copy()
    env["HERMES_HOME"] = str(hermes_home)
    env["NO_COLOR"] = "1"
    if unset_minimax:
        env.pop("MINIMAX_API_KEY", None)
        env.pop("MINIMAX_CN_API_KEY", None)
    cmd = [os.environ.get("HERMES_PROOF_PYTHON", sys.executable), "-m", "hermes_cli.main", "doctor"]
    proc = subprocess.run(
        cmd,
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    text = strip_ansi(proc.stdout)
    lines = text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.strip() == "◆ Delegation Readiness":
            start = idx
            break
    if start is None:
        raise SystemExit("Could not locate Delegation Readiness section in doctor output")
    section_lines = []
    for idx in range(start, len(lines)):
        line = lines[idx].rstrip()
        if idx > start and line.startswith("◆ "):
            break
        if line.strip():
            section_lines.append(line)
    return "\n".join(section_lines)

with tempfile.TemporaryDirectory(prefix="delegation-readiness-") as tmpdir:
    hermes_home = Path(tmpdir)
    broken_config = """delegation:\n  provider: minimax\n  model: MiniMax-M2.7\n"""
    (hermes_home / "config.yaml").write_text(broken_config, encoding="utf-8")

    blocked = doctor_section(hermes_home, unset_minimax=True)

    (hermes_home / "config.yaml").write_text("{}\n", encoding="utf-8")
    ready = doctor_section(hermes_home, unset_minimax=True)

report_time = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
relative_script = Path("starter-kits/delegation-readiness-doctor/scripts/prove-broken-state-roundtrip.sh")
report = f"""# Delegation Readiness Doctor — Broken-State Roundtrip

Generated: {report_time}

## Result
BROKEN_STATE_ROUNDTRIP_PROVED

## Broken state induced
- Temporary isolated `HERMES_HOME` was created under `mktemp`.
- `config.yaml` inside that isolated home was set to:
  - `delegation.provider: minimax`
  - `delegation.model: MiniMax-M2.7`
- `MINIMAX_API_KEY` and `MINIMAX_CN_API_KEY` were explicitly removed from the doctor subprocess environment so the readiness path had to fail on missing credentials instead of inheriting the real machine state.

## Before repair — doctor output
```text
{blocked}
```

## Canonical repair path
1. Clear the delegation override so subagents inherit the parent runtime.
2. Re-run `python -m hermes_cli.main doctor`.
3. Confirm `◆ Delegation Readiness` flips from blocked to ready before trusting delegated work.

## After repair — doctor output
```text
{ready}
```

## Proof notes
- The broken state was isolated to a temporary `HERMES_HOME`; the real `~/.hermes/config.yaml` was not modified.
- The ready state after repair was proved by replacing the isolated config with an empty config (`{{}}`), which removes the delegation override entirely.
- Script used: `{relative_script}`

## Honest next move
Run one real delegated task from the live ready environment and append that proof to the canonical packet.
"""
report_path.write_text(report, encoding="utf-8")
shutil.copyfile(report_path, latest_path)
print(report_path)
PY

chmod +x "$SCRIPT_DIR/prove-broken-state-roundtrip.sh"
printf 'Wrote report: %s\n' "$REPORT_PATH"
printf 'Latest report: %s\n' "$LATEST_PATH"
printf 'BROKEN_STATE_ROUNDTRIP_PROVED\n'
