"""Import-boundary gate for the standalone ContextOps/ESE core.

The core package must not import any host runtime — neither the surrounding
agent runtime, nor its plugins, nor its message gateway, nor its task board.
This test AST-parses every ``.py`` file under ``src/contextops_ese`` and
fails closed if any ``import`` / ``from ... import`` statement names a
forbidden top-level module.
"""

from __future__ import annotations

import ast
from pathlib import Path

_CORE_SRC = Path(__file__).resolve().parents[1] / "src" / "contextops_ese"

# Top-level module names the standalone core must never import from.
_FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "hermes",
        "hermes_dogfood",
        "plugins",
        "gateway",
        "kanban",
        "contextops",  # the legacy in-repo namespace; core stays standalone
    }
)


def _iter_import_roots(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".", 1)[0]
        elif isinstance(node, ast.ImportFrom):
            # ``from .x import y`` -> module is ``x`` (relative); skip relatives.
            if node.level and not node.module:
                continue
            if node.level:
                # Relative imports stay inside the package; that's fine.
                continue
            if node.module:
                yield node.module.split(".", 1)[0]


def test_core_package_has_no_forbidden_imports() -> None:
    violations: list[str] = []
    for path in sorted(_CORE_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for root in _iter_import_roots(tree):
            if root in _FORBIDDEN_IMPORT_ROOTS:
                rel = path.relative_to(_CORE_SRC.parents[1])
                violations.append(f"{rel}: forbidden import root {root!r}")
    assert not violations, "core package imports forbidden roots:\n" + "\n".join(
        sorted(set(violations))
    )
