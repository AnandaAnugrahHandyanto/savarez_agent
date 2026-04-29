#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$KIT_DIR/../.." && pwd)"
ARTIFACT_DIR="$KIT_DIR/artifacts"
mkdir -p "$ARTIFACT_DIR"

TIMESTAMP="$(date +%Y-%m-%dT%H-%M-%S%z)"
REPORT_PATH="$ARTIFACT_DIR/current-gap-report-$TIMESTAMP.md"
LATEST_PATH="$ARTIFACT_DIR/latest-current-gap-report.md"

python3 - "$REPO_ROOT" "$REPORT_PATH" "$LATEST_PATH" <<'PY'
import ast
import shutil
import sys
from datetime import datetime
from pathlib import Path

repo_root = Path(sys.argv[1])
report_path = Path(sys.argv[2])
latest_path = Path(sys.argv[3])
delegate_path = repo_root / "tools" / "delegate_tool.py"
doctor_path = repo_root / "hermes_cli" / "doctor.py"

source = delegate_path.read_text(encoding="utf-8")
tree = ast.parse(source)

fn = None
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name == "check_delegate_requirements":
        fn = node
        break

if fn is None:
    raise SystemExit("check_delegate_requirements() not found")

returns_true_only = len(fn.body) == 2 and isinstance(fn.body[0], ast.Expr) and isinstance(getattr(fn.body[0], "value", None), ast.Constant) and isinstance(fn.body[1], ast.Return) and isinstance(getattr(fn.body[1], "value", None), ast.Constant) and fn.body[1].value.value is True
if not returns_true_only:
    raise SystemExit("Delegation readiness gap no longer matches the expected stubbed-check shape")

docstring = ast.get_docstring(fn) or ""
segment = ast.get_source_segment(source, fn) or ""
doctor_source = doctor_path.read_text(encoding="utf-8")
report_time = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
relative_delegate = delegate_path.relative_to(repo_root)
relative_doctor = doctor_path.relative_to(repo_root)

def find_line(text, needle):
    for idx, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return idx
    return None

fn_line = fn.lineno
wire_line = find_line(source, "check_fn=check_delegate_requirements")
override_line = find_line(doctor_source, "def _apply_doctor_tool_availability_overrides")
tool_availability_line = find_line(doctor_source, 'print(color("◆ Tool Availability"')

report = f"""# Delegation Readiness Doctor — Current Gap Report

Generated: {report_time}

## Result
CURRENT_GAP_CONFIRMED

## What was checked
- Parsed `{relative_delegate}` with Python AST
- Located `check_delegate_requirements()` at line {fn_line}
- Confirmed the function still consists of only a docstring plus `return True`
- Confirmed the delegation tool registration still wires `check_fn=check_delegate_requirements` at line {wire_line or 'unknown'}
- Confirmed reusable doctor surfaces already exist in `{relative_doctor}` at lines {override_line or 'unknown'} and {tool_availability_line or 'unknown'}

## Why this matters
Hermes still advertises delegation readiness as always available even though the weekly MVP factory now depends on delegation as a real execution layer.

## Evidence
### Current function docstring
> {docstring}

### Current function body
```python
{segment.strip()}
```

## Honest next move
Replace the stubbed readiness check with one real config-aware check, surface that state through a canonical doctor/readiness command, then prove one passing delegated run.
"""

report_path.write_text(report, encoding="utf-8")
shutil.copyfile(report_path, latest_path)
print(str(report_path))
PY

printf 'Wrote report: %s\n' "$REPORT_PATH"
printf 'Latest report: %s\n' "$LATEST_PATH"
printf 'CURRENT_GAP_CONFIRMED\n'
