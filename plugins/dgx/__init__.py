"""dgx plugin — manage NVIDIA DGX Spark inference endpoints from Hermes Agent.

CLI subcommands: setup, status, models, use, endpoint, pull, rm, ps,
                 push, doctor, watch, formation, nim, node

Agent tools: dgx_gpu_status, dgx_pull_model

Note: there is deliberately no agent-callable "run arbitrary command on the
DGX" tool. Free-form remote shell belongs to the host terminal tool (which
routes through the dangerous-command approval gate); duplicating it here
would let a model run unguarded commands on the GPU host over SSH.
"""

from __future__ import annotations

from plugins.dgx.cli import dgx_command, register_cli as _register_dgx_cli
from plugins.dgx.tools import (
    DGX_GPU_STATUS_SCHEMA,
    DGX_PULL_MODEL_SCHEMA,
    handle_dgx_gpu_status,
    handle_dgx_pull_model,
)

_TOOLS = (
    ("dgx_gpu_status",  DGX_GPU_STATUS_SCHEMA,  handle_dgx_gpu_status,  "🖥️"),
    ("dgx_pull_model",  DGX_PULL_MODEL_SCHEMA,  handle_dgx_pull_model,  "📥"),
)


def register(ctx) -> None:
    ctx.register_cli_command(
        name="dgx",
        help="NVIDIA DGX Spark endpoint management",
        setup_fn=_register_dgx_cli,
        handler_fn=dgx_command,
        description=(
            "Manage local GPU inference endpoints on a DGX Spark. "
            "See: hermes dgx setup"
        ),
    )
    for name, schema, handler, emoji in _TOOLS:
        ctx.register_tool(
            name=name,
            toolset="dgx",
            schema=schema,
            handler=handler,
            emoji=emoji,
        )
