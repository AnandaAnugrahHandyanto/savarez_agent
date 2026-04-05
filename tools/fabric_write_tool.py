#!/usr/bin/env python3
"""
fabric_write -- subagent memory persistence

Lets subagents write key findings to MEMORY.md before completing.
Unlike the full memory tool, this is append-only and rate-limited.

Guardrails:
  - Append-only: no read, replace, or remove
  - 3 writes max per subagent execution
  - 400 chars max per entry
  - Same injection/exfiltration scanning as memory_tool
  - Silently unavailable when the parent has no memory store

Entries are tagged "[subagent:TOPIC]" so they're identifiable and
easy for the parent to review or clean up.

Design note: this tool writes directly to disk via a fresh MemoryStore.
The MemoryStore.add() call re-reads from disk under a file lock before
appending, so concurrent parent + subagent writes are safe.
"""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Hard limits applied per subagent instance.
_MAX_WRITES_PER_SUBAGENT = 3
_MAX_CONTENT_CHARS = 400
_MAX_TOPIC_CHARS = 60


def fabric_write(
    topic: str,
    content: str,
    agent=None,
) -> str:
    """
    Append a finding to MEMORY.md on behalf of a subagent.

    topic:   Short label for the finding (e.g. "root_cause", "config_path").
             Becomes part of the MEMORY.md entry tag.
    content: The finding text. Keep it compact -- this goes into the
             parent's memory and will be injected into future sessions.
    agent:   The calling agent instance. Used to track per-subagent write count
             and to access the memory store path.
    """
    # Rate limiting: track writes on the calling agent object
    if agent is not None:
        write_count = getattr(agent, "_fabric_write_count", 0)
        if write_count >= _MAX_WRITES_PER_SUBAGENT:
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        f"fabric_write limit reached ({_MAX_WRITES_PER_SUBAGENT} writes "
                        "per subagent). Summarize remaining findings in your final response."
                    ),
                },
                ensure_ascii=False,
            )

    # Validate inputs
    topic = (topic or "").strip()
    content = (content or "").strip()

    if not topic:
        return json.dumps(
            {"success": False, "error": "topic cannot be empty."},
            ensure_ascii=False,
        )
    if not content:
        return json.dumps(
            {"success": False, "error": "content cannot be empty."},
            ensure_ascii=False,
        )
    if len(topic) > _MAX_TOPIC_CHARS:
        return json.dumps(
            {
                "success": False,
                "error": (
                    f"topic too long ({len(topic)} chars, max {_MAX_TOPIC_CHARS}). "
                    "Use a short label."
                ),
            },
            ensure_ascii=False,
        )
    if len(content) > _MAX_CONTENT_CHARS:
        return json.dumps(
            {
                "success": False,
                "error": (
                    f"content too long ({len(content)} chars, max {_MAX_CONTENT_CHARS}). "
                    "Trim to the essential finding."
                ),
            },
            ensure_ascii=False,
        )

    # Scan for injection/exfiltration payloads (same rules as memory_tool)
    try:
        from tools.memory_tool import _scan_memory_content
        scan_error = _scan_memory_content(content)
        if scan_error:
            return json.dumps({"success": False, "error": scan_error}, ensure_ascii=False)
        scan_error = _scan_memory_content(topic)
        if scan_error:
            return json.dumps({"success": False, "error": f"topic: {scan_error}"}, ensure_ascii=False)
    except Exception as e:
        logger.warning("fabric_write: content scan failed: %s", e)

    # Format and write the entry
    entry = f"[subagent:{topic}] {content}"

    try:
        from tools.memory_tool import MemoryStore
        store = MemoryStore()
        result = store.add("memory", entry)
    except Exception as exc:
        logger.error("fabric_write: MemoryStore.add failed: %s", exc)
        return json.dumps(
            {"success": False, "error": f"Failed to write to memory: {exc}"},
            ensure_ascii=False,
        )

    # Increment write counter on success
    if result.get("success") and agent is not None:
        agent._fabric_write_count = getattr(agent, "_fabric_write_count", 0) + 1
        writes_used = agent._fabric_write_count
        writes_remaining = _MAX_WRITES_PER_SUBAGENT - writes_used
        result["writes_remaining"] = writes_remaining

    return json.dumps(result, ensure_ascii=False)


def check_fabric_write_requirements() -> bool:
    """fabric_write has no external requirements -- always available."""
    return True


# =============================================================================
# OpenAI Function-Calling Schema
# =============================================================================

FABRIC_WRITE_SCHEMA = {
    "name": "fabric_write",
    "description": (
        "Persist a key finding to the parent agent's memory (MEMORY.md) before completing. "
        "Use this for discoveries that will matter in future sessions -- root causes, "
        "non-obvious configuration facts, decisions that constrain future work.\n\n"
        "WHEN TO USE:\n"
        "- You identified a root cause (e.g. 'the Render deploy fails because of missing "
        "REDIS_URL in production env')\n"
        "- You discovered a non-obvious fact about the system (e.g. 'DB migrations must "
        "run before the app starts or the health check fails')\n"
        "- You found a config path, credential location, or dependency that isn't obvious "
        "from the codebase\n"
        "- The parent would need to re-investigate to find this again\n\n"
        "WHEN NOT TO USE:\n"
        "- Routine task progress ('completed 5 of 10 files')\n"
        "- Information already covered in your final summary\n"
        "- Temporary state that won't matter next session\n\n"
        "LIMITS:\n"
        "- 3 writes max per task\n"
        "- 400 chars max per entry\n"
        "- topic should be a short snake_case label (e.g. 'root_cause', 'auth_config')\n\n"
        "Entries appear in the parent's memory with a [subagent:TOPIC] tag."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": (
                    "Short label for this finding (snake_case, max 60 chars). "
                    "Examples: 'root_cause', 'db_migration_order', 'env_config_path'."
                ),
            },
            "content": {
                "type": "string",
                "description": (
                    "The finding to persist. Max 400 chars. "
                    "Be specific -- include service names, file paths, error messages, "
                    "or constraint details as relevant."
                ),
            },
        },
        "required": ["topic", "content"],
    },
}


# --- Registry ---
from tools.registry import registry

registry.register(
    name="fabric_write",
    toolset="fabric",
    schema=FABRIC_WRITE_SCHEMA,
    handler=lambda args, **kw: fabric_write(
        topic=args.get("topic", ""),
        content=args.get("content", ""),
        agent=kw.get("parent_agent"),
    ),
    check_fn=check_fabric_write_requirements,
    emoji="🧵",
)
