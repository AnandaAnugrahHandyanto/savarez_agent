"""Marketing Agent Factory plugin.

MVP is dry-run-only: it registers one agent tool and one CLI command for
isolated brand profiles, campaign planning, approval queues, scheduling,
dry-run publishing, analytics feedback, and audit logs. Any real channel
integration must remain behind explicit approval and dry-run gates.
"""

from __future__ import annotations

from plugins.marketing_factory.cli import marketing_command, register_cli
from plugins.marketing_factory.tools import MARKETING_FACTORY_SCHEMA, handle_marketing_factory


def register(ctx) -> None:
    ctx.register_tool(
        name="marketing_factory",
        toolset="productivity",
        schema=MARKETING_FACTORY_SCHEMA,
        handler=handle_marketing_factory,
        check_fn=lambda: True,
        emoji="📣",
    )
    ctx.register_cli_command(
        name="marketing-factory",
        help="Dry-run marketing agent factory (brands, campaigns, approvals, schedules, audit)",
        setup_fn=register_cli,
        handler_fn=marketing_command,
        description="Operate the dry-run-first Marketing Agent Factory for isolated app marketing pipelines.",
    )
