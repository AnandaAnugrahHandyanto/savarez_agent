"""Built-in AgentLair inbox-drain hook.

Drains the AgentLair inbox **synchronously** during gateway startup so that
the agent has deterministic state before it begins planning. Unread messages
are fetched, formatted into a prompt, and processed by a one-shot AIAgent
before the gateway accepts the first user message.

Configuration
-------------
AGENTLAIR_API_KEY    — required; hook is a no-op without it.
AGENTLAIR_FROM       — claimed inbox address (e.g. publisher@agentlair.dev).
                       Messages addressed to this address are drained.

Skipping
--------
The hook silently returns (no error) when:
  - AGENTLAIR_API_KEY is not set
  - AGENTLAIR_FROM is not set
  - The inbox is empty

Design note
-----------
Unlike the boot-md hook, this handler does NOT spawn a background thread.
It awaits the inbox fetch and the agent run directly so that startup blocks
until the drain completes. This matches voidborne-d's guidance (issue #344):
"do the initial drain synchronously in kickoff() — it gives deterministic
state before planning starts."
"""

import logging
import os

logger = logging.getLogger("hooks.agentlair-inbox-drain")


def _build_drain_prompt(messages: list[dict]) -> str:
    lines = [
        "You are processing pending inbox messages for this agent's AgentLair "
        "address. For each message: read it, decide whether it requires a reply "
        "or action, and act accordingly using available tools.\n",
        f"There are {len(messages)} unread message(s):\n",
    ]
    for i, msg in enumerate(messages, 1):
        lines.append(
            f"--- Message {i} ---\n"
            f"From:    {msg.get('from', '(unknown)')}\n"
            f"Subject: {msg.get('subject', '(no subject)')}\n"
            f"ID:      {msg.get('message_id', '')}\n"
            f"Date:    {msg.get('received_at', '')}\n"
        )
    lines.append(
        "\nProcess each message. If nothing requires a reply or action, "
        "respond with only: [SILENT]"
    )
    return "\n".join(lines)


async def handle(event_type: str, context: dict) -> None:
    """Drain the AgentLair inbox synchronously on gateway:startup."""
    api_key = os.environ.get("AGENTLAIR_API_KEY", "")
    address = os.environ.get("AGENTLAIR_FROM", "")

    if not api_key:
        logger.debug("agentlair-inbox-drain: AGENTLAIR_API_KEY not set, skipping")
        return
    if not address:
        logger.debug("agentlair-inbox-drain: AGENTLAIR_FROM not set, skipping")
        return

    # Import here to avoid circular imports at module load time
    from tools.agentlair_tool import drain_inbox

    logger.info("agentlair-inbox-drain: checking inbox for %s", address)
    messages = drain_inbox(address)

    if not messages:
        logger.info("agentlair-inbox-drain: inbox empty, nothing to do")
        return

    logger.info(
        "agentlair-inbox-drain: %d unread message(s) — processing synchronously",
        len(messages),
    )

    try:
        from run_agent import AIAgent

        prompt = _build_drain_prompt(messages)
        agent = AIAgent(
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            max_iterations=30,
        )
        result = agent.run_conversation(prompt)
        response = result.get("final_response", "")
        if response and "[SILENT]" not in response:
            logger.info("agentlair-inbox-drain: completed — %s", response[:200])
        else:
            logger.info("agentlair-inbox-drain: completed (nothing to report)")
    except Exception as exc:
        logger.error("agentlair-inbox-drain: agent run failed: %s", exc)
