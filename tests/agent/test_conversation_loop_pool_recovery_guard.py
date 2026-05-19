"""Regression guard for #28268/#28254-style bugs: conversation loop must
resolve rate-limit pool recovery helper via _ra().

`agent/conversation_loop.py` is extracted from `run_agent.AIAgent` and uses
`_ra()` to lazily resolve symbols that production code or tests patch on
`run_agent`. Referencing `_pool_may_recover_from_rate_limit` directly in this
module raises NameError at runtime because the helper lives in `run_agent.py`.
"""

from __future__ import annotations


def test_conversation_loop_routes_pool_recovery_helper_through_ra():
    import inspect

    from agent import conversation_loop

    src = inspect.getsource(conversation_loop)
    assert "_pool_may_recover_from_rate_limit" in src
    assert "_ra()._pool_may_recover_from_rate_limit(" in src, (
        "agent/conversation_loop.py must resolve _pool_may_recover_from_rate_limit "
        "via _ra() to avoid NameError and preserve patch semantics."
    )

