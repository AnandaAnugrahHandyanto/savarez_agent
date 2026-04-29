"""Eval 018: ContextCompressor symbol fully renamed to ContextCompactor in agent/.

Walks every .py file under agent/, asserts no `ContextCompressor` matches and
that `ContextCompactor` appears in at least one file (i.e., the rename
actually happened — empty files would otherwise trivially pass).
"""

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AGENT_DIR = REPO_ROOT / "agent"

_OLD = re.compile(r"\bContextCompressor\b")
_NEW = re.compile(r"\bContextCompactor\b")


def _iter_agent_py_files() -> list[Path]:
    return [p for p in AGENT_DIR.rglob("*.py") if "__pycache__" not in p.parts]


def test_no_compressor_references() -> None:
    offenders: list[str] = []
    daedalus_count = 0
    for py in _iter_agent_py_files():
        text = py.read_text(encoding="utf-8", errors="replace")
        if _OLD.search(text):
            offenders.append(str(py.relative_to(REPO_ROOT)))
        if _NEW.search(text):
            daedalus_count += 1
    assert not offenders, (
        f"`ContextCompressor` still referenced in: {offenders}"
    )
    assert daedalus_count >= 1, (
        "Rename did not introduce `ContextCompactor` anywhere in agent/"
    )
