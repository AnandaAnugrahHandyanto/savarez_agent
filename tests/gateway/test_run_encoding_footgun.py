"""Regression guard: gateway/run.py must not use bare read_text()/write_text().

On Windows (and any host where ``locale.getpreferredencoding()`` is not UTF-8 —
cp1252 on US locales, GBK/CP936 on Chinese locales, etc.), ``Path.read_text()``
and ``Path.write_text()`` without an explicit ``encoding=`` use the locale
codec. In the ``hermes update``-over-gateway flow this surfaces as:

* ``UnicodeEncodeError`` when writing the user's reply (emoji / CJK) to the
  ``.update_response`` file, and
* ``UnicodeDecodeError`` / mojibake when reading the update subprocess's
  captured UTF-8 stdout.

Both are ``UnicodeError`` subclasses, so the surrounding ``except OSError``
guards do NOT catch them — the gateway command handler / update-stream
coroutine crashes. ``ruff``'s PLW1514 and ``scripts/check-windows-footguns.py``
both miss these because they don't resolve ``.read_text``/``.write_text`` on a
variable/attribute receiver.

This static guard enforces that every encoding-sensitive text call in
gateway/run.py passes an explicit ``encoding=``. Mirrors the AST-guard style of
``tests/tools/test_windows_compat.py``.
"""

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RUN_PY = PROJECT_ROOT / "gateway" / "run.py"

_ENCODING_SENSITIVE = {"read_text", "write_text"}


def _calls_without_encoding(filepath: Path) -> list[tuple[int, str]]:
    """Return (lineno, method) for read_text/write_text calls lacking encoding=."""
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(filepath))
    offenders: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr not in _ENCODING_SENSITIVE:
            continue
        if any(kw.arg == "encoding" for kw in node.keywords):
            continue
        offenders.append((node.lineno, func.attr))
    return offenders


def test_run_py_has_no_bare_read_write_text():
    if not RUN_PY.exists():
        pytest.skip("gateway/run.py not found")
    offenders = _calls_without_encoding(RUN_PY)
    assert not offenders, (
        "gateway/run.py has read_text()/write_text() calls without an explicit "
        'encoding= (Windows cp1252/GBK footgun). Add encoding="utf-8":\n'
        + "\n".join(f"  run.py:{ln}  .{attr}()" for ln, attr in offenders)
    )
