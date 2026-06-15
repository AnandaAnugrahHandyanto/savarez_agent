"""``hermes a2a`` subcommand parser.

Sibling to ``hermes_cli/subcommands/acp.py``. Handler injected to avoid
importing ``main``. The actual server lives in ``a2a_adapter.entry``.
"""

from __future__ import annotations

from typing import Callable

from hermes_cli.subcommands._shared import add_accept_hooks_flag


def build_a2a_parser(subparsers, *, cmd_a2a: Callable) -> None:
    """Attach the ``a2a`` subcommand to ``subparsers``."""
    a2a_parser = subparsers.add_parser(
        "a2a",
        help="Run Hermes Agent as an A2A (Agent2Agent) server",
        description=(
            "Start Hermes Agent as an A2A server so other agents can discover "
            "it (via the Agent Card at /.well-known/agent-card.json) and "
            "delegate tasks over JSON-RPC + SSE."
        ),
    )
    add_accept_hooks_flag(a2a_parser)
    a2a_parser.add_argument(
        "--host",
        default=None,
        help="Bind host (default 127.0.0.1). Use 0.0.0.0 to expose on the "
        "network — the endpoint is UNAUTHENTICATED, so put it behind a "
        "reverse proxy or auth layer.",
    )
    a2a_parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Bind port (default 9100).",
    )
    a2a_parser.add_argument(
        "--public-url",
        default=None,
        help="Base URL advertised in the Agent Card (default http://<host>:<port>/).",
    )
    a2a_parser.add_argument(
        "--version",
        action="store_true",
        dest="a2a_version",
        help="Print Hermes A2A version and exit",
    )
    a2a_parser.add_argument(
        "--check",
        action="store_true",
        help="Verify A2A dependencies and adapter imports, then exit",
    )
    a2a_parser.set_defaults(func=cmd_a2a)
