"""A2A (Agent2Agent) protocol server for Hermes Agent.

Exposes the Hermes ``AIAgent`` as an A2A-compliant remote agent so any
A2A-speaking client or peer agent can discover it (via the Agent Card) and
delegate tasks over JSON-RPC + SSE. Sibling to ``acp_adapter`` (editor
integration over stdio) and ``mcp_serve`` (tools over MCP).

Run it with ``hermes-a2a`` or ``python -m a2a_adapter``. See
``.plans/a2a-protocol.md`` for the design.
"""
