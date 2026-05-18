"""Regression test for issue #27719.

The eager rate-limit fallback path in ``agent.conversation_loop`` calls
``_pool_may_recover_from_rate_limit``, which is defined in ``run_agent``.
Prior to the fix, the helper was referenced but never imported inside
``agent/conversation_loop.py`` -- triggering ``NameError`` whenever the
primary provider returned a 429/quota error and a fallback chain was
configured (e.g. DeepSeek exhausted, OpenRouter fallback).
"""

from __future__ import annotations

import ast
from pathlib import Path

import agent.conversation_loop as conversation_loop


def _call_site_uses_lazy_import() -> bool:
    src = Path(conversation_loop.__file__).read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "run_agent":
            for alias in node.names:
                if alias.name == "_pool_may_recover_from_rate_limit":
                    return True
    return False


def test_pool_recover_helper_is_importable_from_run_agent():
    from run_agent import _pool_may_recover_from_rate_limit

    assert callable(_pool_may_recover_from_rate_limit)
    assert _pool_may_recover_from_rate_limit(None) is False


def test_conversation_loop_imports_pool_recover_helper():
    # Guards against #27719 regressing: the symbol must be referenced via
    # an explicit `from run_agent import _pool_may_recover_from_rate_limit`
    # so the eager-fallback codepath never raises NameError again.
    assert _call_site_uses_lazy_import(), (
        "agent/conversation_loop.py must import "
        "_pool_may_recover_from_rate_limit from run_agent (issue #27719)."
    )
