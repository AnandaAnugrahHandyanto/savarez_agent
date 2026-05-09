"""Regression: tests importing UNIX-only stdlib modules must use
``pytest.importorskip`` so collection on Windows doesn't hard-fail
before any test runs (#22420).
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _module_level_imports(body: str) -> set[str]:
    """Return module names imported at module scope.

    Uses ``ast`` so aliases (``import pwd as _pwd``), inline comments
    (``import pwd  # noqa``) and trailing whitespace are all detected.
    """
    tree = ast.parse(body)
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".", 1)[0])
    return names


def test_gateway_service_uses_importorskip_for_pwd():
    body = _read(REPO_ROOT / "tests" / "hermes_cli" / "test_gateway_service.py")
    top = _module_level_imports(body)
    assert "pwd" not in top, (
        "test_gateway_service.py must not import `pwd` at module top — "
        "use `pwd = pytest.importorskip('pwd')` so Windows can skip the file."
    )
    assert 'pytest.importorskip("pwd")' in body


def test_file_sync_back_uses_importorskip_for_fcntl():
    body = _read(REPO_ROOT / "tests" / "tools" / "test_file_sync_back.py")
    top = _module_level_imports(body)
    assert "fcntl" not in top, (
        "test_file_sync_back.py must not import `fcntl` at module top — "
        "use `fcntl = pytest.importorskip('fcntl')` so Windows can skip the file."
    )
    assert 'pytest.importorskip("fcntl")' in body
