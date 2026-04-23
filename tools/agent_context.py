"""Context variable for the currently-running AIAgent.

Plugin-registered tool handlers (via ``PluginContext.register_tool``) do NOT
receive ``parent_agent`` in their ``**kwargs`` — only the built-in
``delegate_task`` tool gets that, via a hardcoded dispatch path in
``run_agent.py`` (see ``AIAgent._dispatch_delegate_task``). Every other tool
goes through ``model_tools.handle_function_call``, which doesn't thread the
agent through.

This module lets plugin handlers opt into accessing the currently-running
agent by calling :func:`get_current_agent`. ``run_agent.py`` wraps each
``handle_function_call`` dispatch with :func:`current_agent` so plugin tools
can access ``self`` via context — enabling them to call
``_build_child_agent(parent_agent=get_current_agent(), ...)`` to spawn
children with per-call model / provider overrides that the global
``delegation.model`` config can't express.

Usage (in a plugin handler)::

    from tools.agent_context import get_current_agent
    from tools.delegate_tool import _build_child_agent, _run_single_child

    def delegate_to_compose_handler(args, **kw):
        agent = get_current_agent()
        if agent is None:
            return "Error: no parent agent in context"
        child = _build_child_agent(
            task_index=0, goal=args["goal"], context=args.get("context"),
            toolsets=[], model="anthropic/claude-sonnet-4.6",
            max_iterations=5, task_count=1, parent_agent=agent,
            override_provider="openrouter",
            override_api_key=os.environ["OPENROUTER_API_KEY"],
            role="leaf",
        )
        return _run_single_child(task_index=0, goal=args["goal"],
                                 child=child, parent_agent=agent)

The contextvar is scoped per-call via :func:`current_agent`, which is
contextvars-safe for async + threads when used with ``copy_context()``
at spawn boundaries (as ``_run_single_child``'s thread pool already does).

Why a new module rather than adding a kwarg to ``handle_function_call``:
backward compatibility. Third-party code and plugins calling
``handle_function_call`` directly (e.g. ``hermes chat`` CLI paths, test
harnesses) keep working unchanged.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator, Optional

_current_agent: ContextVar[Optional[Any]] = ContextVar(
    "hermes_current_agent", default=None,
)


def get_current_agent() -> Optional[Any]:
    """Return the AIAgent currently dispatching a tool call, or ``None``.

    Returns ``None`` when called outside a ``handle_function_call`` dispatch
    (e.g. at module import, from a test that didn't enter the context, or
    from a plugin's ``register()`` callback). Plugin handlers should always
    guard against this and return a clear error to the caller.
    """
    return _current_agent.get()


@contextmanager
def current_agent(agent: Any) -> Iterator[None]:
    """Bind *agent* as the current agent for the duration of the ``with`` block.

    Safe under exceptions (the contextvar is always reset in ``finally``).
    Nestable — inner scopes override outer for their duration.
    """
    token = _current_agent.set(agent)
    try:
        yield
    finally:
        _current_agent.reset(token)
