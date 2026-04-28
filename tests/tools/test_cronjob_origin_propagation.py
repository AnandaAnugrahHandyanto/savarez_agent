"""Regression test for cron origin=None bug (fork commit fix-2026-04-28).

Background: After security/H-1 (`154a6a06`) made ContextVar the single source
for session scope, gateway stopped writing `os.environ` for chat_id/platform.
But `loop.run_in_executor(None, run_sync)` does NOT propagate ContextVars to
thread-pool workers, so tools running in the agent thread saw `None` and
created cron jobs with `origin=None` — making them undeliverable.

Fix: wrap the agent run with `contextvars.copy_context().run()` at every
thread boundary (gateway → agent run_sync, agent → tool ThreadPoolExecutor).

This test pins the propagation pattern so a future refactor that drops
`copy_context()` will fail loudly instead of silently breaking origin tagging.
"""

import asyncio
import concurrent.futures
import contextvars

import pytest

from tools.cronjob_tools import _origin_from_env
from tools.session_context import clear_session, set_session


def setup_function():
    clear_session()


def teardown_function():
    clear_session()


def test_origin_naive_thread_loses_context():
    """Without copy_context, ContextVar default leaks into thread."""
    set_session(platform="slack", chat_id="D0NAIVE")
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        result = ex.submit(_origin_from_env).result()
    assert result is None, "Naive submit should NOT see parent ContextVar"


def test_origin_copy_context_thread_preserves_session():
    """With copy_context, thread sees parent's ContextVar values."""
    set_session(platform="slack", chat_id="D0FIXED", chat_name="dm")
    ctx = contextvars.copy_context()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        result = ex.submit(ctx.run, _origin_from_env).result()
    assert result is not None
    assert result["chat_id"] == "D0FIXED"
    assert result["platform"] == "slack"


@pytest.mark.asyncio
async def test_origin_run_in_executor_naive_loses_context():
    """run_in_executor without copy_context — ContextVar lost in thread pool."""
    set_session(platform="slack", chat_id="D0EXEC_NAIVE")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _origin_from_env)
    assert result is None


@pytest.mark.asyncio
async def test_origin_run_in_executor_with_copy_context():
    """run_in_executor wrapped in copy_context.run preserves ContextVar."""
    set_session(platform="slack", chat_id="D0EXEC_FIXED")
    loop = asyncio.get_event_loop()
    ctx = contextvars.copy_context()
    result = await loop.run_in_executor(None, ctx.run, _origin_from_env)
    assert result is not None
    assert result["chat_id"] == "D0EXEC_FIXED"
