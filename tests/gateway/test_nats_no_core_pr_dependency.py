"""Stage 2 resilience invariants for the NATS plugin.

Pins the plugin's structural independence from Core-PR-territory symbols so
the plugin can be copied into a stock NousResearch/hermes-agent checkout and
load + register cleanly there. See master plan §4 (Dependency Points A & B)
and §7 Stage 2.

Three assertions:
  1. ``test_nats_adapter_has_no_top_level_core_pr_imports`` — AST scan of
     adapter.py + _approval.py: no top-level imports of forbidden Core-PR
     symbols from ``gateway.platforms.base`` or ``tools.approval``.
  2. ``test_nats_register_has_transport_authed_feature_guard`` — AST scan
     of adapter.py: any ``transport_authed`` reference must sit inside a
     ``try``/``except`` block (feature-detection guard).
  3. ``test_nats_module_imports_without_sdk`` — AST scan of adapter.py:
     the top-level ``synadia_ai.*`` + ``nats`` imports must sit inside a
     ``try``/``except ImportError`` block, so the module loads on a venv
     that lacks the Synadia SDKs (the §4 Stage 2 smoke-check invariant).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ADAPTER_PATH = _REPO_ROOT / "plugins" / "platforms" / "nats" / "adapter.py"
_APPROVAL_PATH = _REPO_ROOT / "plugins" / "platforms" / "nats" / "_approval.py"

_FORBIDDEN_BASE_SYMBOLS = {
    "request_interaction",
    "dispatch_approval_via_request_interaction",
    "adapter_supports_request_interaction",
    "_format_approval_prompt",
    "_parse_approval_reply",
}
_FORBIDDEN_APPROVAL_SYMBOLS = {
    "get_current_approval_entry_id",
    "_current_approval_entry_id",
}


def _top_level_imports(tree: ast.Module):
    """Yield (module_str, name_str) for every top-level ``from X import Y`` and ``import X``.

    Only walks Module.body — does NOT descend into functions / classes /
    try-blocks, so function-local lazy imports are explicitly allowed.
    """
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                yield module, alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, alias.name


@pytest.mark.parametrize("path", [_ADAPTER_PATH, _APPROVAL_PATH], ids=["adapter", "_approval"])
def test_nats_adapter_has_no_top_level_core_pr_imports(path: Path) -> None:
    """Plugin must not top-level-import any Core-PR-territory symbol."""
    tree = ast.parse(path.read_text())
    offenses = []
    for module, name in _top_level_imports(tree):
        if module == "gateway.platforms.base" and name in _FORBIDDEN_BASE_SYMBOLS:
            offenses.append(f"{path.name}: top-level `from gateway.platforms.base import {name}`")
        if module == "tools.approval" and name in _FORBIDDEN_APPROVAL_SYMBOLS:
            offenses.append(f"{path.name}: top-level `from tools.approval import {name}`")
    assert not offenses, (
        "Found top-level imports of Core-PR-territory symbols — these must be "
        "vendored into plugins/platforms/nats/_approval.py or guarded behind a "
        "function-local lazy import.\n  " + "\n  ".join(offenses)
    )


def test_nats_register_has_transport_authed_feature_guard() -> None:
    """Any ``transport_authed`` reference in adapter.py must sit inside a try-block."""
    tree = ast.parse(_ADAPTER_PATH.read_text())

    # Build child→parent map so we can walk ancestors of a node.
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    def _inside_try(node: ast.AST) -> bool:
        cur = parents.get(node)
        while cur is not None:
            if isinstance(cur, ast.Try):
                return True
            cur = parents.get(cur)
        return False

    offenses = []
    for node in ast.walk(tree):
        # Keyword argument:  ctx.register_platform(..., transport_authed=True)
        if isinstance(node, ast.keyword) and node.arg == "transport_authed":
            if not _inside_try(node):
                offenses.append(f"line {node.value.lineno}: keyword `transport_authed=` outside try-block")
        # String literal:  "transport_authed" — caught for completeness
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value == "transport_authed":
            if not _inside_try(node):
                offenses.append(f"line {node.lineno}: literal 'transport_authed' outside try-block")

    assert not offenses, (
        "Found unguarded `transport_authed` references — these must sit inside "
        "a try/except TypeError block per master plan §4 Dependency Point B.\n  "
        + "\n  ".join(offenses)
    )


def test_nats_module_imports_without_sdk() -> None:
    """Adapter's synadia_ai.* + nats imports must be guarded by try/except ImportError.

    The §4 Stage 2 smoke check ``python -c "from plugins.platforms.nats import register"``
    runs on the reference clone where the Synadia SDKs are not installed — without
    the guard, the import would raise ``ModuleNotFoundError`` and the plugin would
    be unloadable.
    """
    tree = ast.parse(_ADAPTER_PATH.read_text())

    sdk_module_prefixes = ("synadia_ai", "nats")

    # Find every top-level Try node and check whether its body contains any sdk import.
    guarded_targets: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.Try):
            continue
        if not any(
            isinstance(h, ast.ExceptHandler)
            and isinstance(h.type, ast.Name) and h.type.id == "ImportError"
            for h in node.handlers
        ):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Import):
                for alias in child.names:
                    if any(alias.name == p or alias.name.startswith(p + ".") for p in sdk_module_prefixes):
                        guarded_targets.add(alias.name)
            elif isinstance(child, ast.ImportFrom):
                mod = child.module or ""
                if any(mod == p or mod.startswith(p + ".") for p in sdk_module_prefixes):
                    for alias in child.names:
                        guarded_targets.add(f"{mod}.{alias.name}")

    assert guarded_targets, (
        "No guarded top-level Try block containing synadia_ai.* / nats imports "
        "with an ImportError handler was found. The Stage 2 smoke check requires "
        "these imports to be wrapped so the module loads on a venv without the "
        "Synadia SDKs installed."
    )
    # Sanity: the guard must actually contain BOTH families (nats and synadia_ai).
    assert any(t.startswith("synadia_ai") for t in guarded_targets), (
        f"Guarded imports cover {sorted(guarded_targets)} but no synadia_ai import is guarded."
    )
    assert any(t == "nats" or t.startswith("nats.") for t in guarded_targets), (
        f"Guarded imports cover {sorted(guarded_targets)} but no `nats` (nats-py) import is guarded."
    )
