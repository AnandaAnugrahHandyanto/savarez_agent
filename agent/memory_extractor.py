"""
Automatic Memory Extraction — post-response hook that extracts durable memories.

Cannibalized from Claude Code (services/extractMemories/) and adapted for Hermes:
- Uses auxiliary_client (cheap model) instead of a forked full agent
- Pre-injects manifest of existing memories to prevent duplicates
- Processes only messages since last extraction (cursor tracking)
- Lightweight: structured JSON output, no tool calls needed

Triggered after every N assistant responses (configurable via extract_interval).
"""

import json
import logging
import threading
import time
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Extraction prompt — adapted from Claude Code + HiveMind quality scoring
# ---------------------------------------------------------------------------

_EXTRACTION_PROMPT = """\
You are a memory extraction system. Review the recent conversation and extract \
any durable facts worth remembering long-term.

EXISTING MEMORIES (do NOT duplicate these):
{manifest}

RECENT CONVERSATION:
{recent_messages}

EXTRACT memories that are:
- User preferences, corrections, or personal details (type: "preference" or "correction")
- Environment facts: OS, tools, project structure, installed software (type: "project")
- Conventions, workflow patterns, or recurring instructions (type: "preference")
- Pointers to external systems, URLs, credentials locations (type: "reference")
- Corrections to previous agent behavior (type: "correction")

DO NOT extract:
- Task progress, session outcomes, or temporary state
- Facts easily re-derived from files or commands
- Anything already captured in existing memories above
- Raw data, code snippets, or verbose technical details

For each memory worth saving, output a JSON object on its own line:
{{"target": "memory"|"user", "type": "preference"|"correction"|"project"|"reference"|"general", "content": "concise fact"}}

If nothing is worth saving, output exactly: NONE

Output ONLY the JSON lines or NONE, no other text."""


def extract_memories_background(
    recent_messages: List[Dict],
    memory_store,
    auxiliary_client=None,
    model: str = None,
    session_id: str = None,
):
    """Run memory extraction in a background thread.

    Args:
        recent_messages: Last N messages from the conversation.
        memory_store: MemoryStore instance (with engine for SQLite mode).
        auxiliary_client: AuxiliaryClient for cheap LLM calls. If None, skipped.
        model: Model name override for the extraction call.
        session_id: Current session ID for attribution.
    """
    if auxiliary_client is None:
        logger.debug("No auxiliary_client — skipping memory extraction")
        return

    engine = getattr(memory_store, 'engine', None) or getattr(memory_store, '_engine', None)
    if engine is None:
        logger.debug("No MemoryEngine — skipping memory extraction (flat mode)")
        return

    def _extract():
        try:
            _do_extraction(recent_messages, engine, auxiliary_client, model, session_id)
        except Exception as e:
            logger.warning("Memory extraction failed: %s", e)

    t = threading.Thread(target=_extract, daemon=True, name="memory-extractor")
    t.start()


def _do_extraction(
    recent_messages: List[Dict],
    engine,
    auxiliary_client,
    model: str = None,
    session_id: str = None,
):
    """Perform the actual extraction (runs in background thread)."""
    start = time.monotonic()

    # Build manifest of existing memories for dedup
    manifest = engine.get_manifest()

    # Format recent messages for the prompt
    formatted = _format_messages(recent_messages, max_chars=8000)
    if not formatted.strip():
        return

    prompt = _EXTRACTION_PROMPT.format(
        manifest=manifest,
        recent_messages=formatted,
    )

    # Call auxiliary LLM
    try:
        response = auxiliary_client.call_llm(
            prompt=prompt,
            system_message="You extract structured memories from conversations. Output JSON lines only.",
            model=model,
            max_tokens=1024,
            temperature=0.1,
        )
    except Exception as e:
        logger.debug("Extraction LLM call failed: %s", e)
        return

    if not response or not response.strip():
        return

    response = response.strip()
    if response.upper() == "NONE":
        logger.debug("Memory extraction: nothing to save")
        return

    # Parse JSON lines
    saved = 0
    for line in response.split("\n"):
        line = line.strip()
        if not line or line.upper() == "NONE":
            continue

        # Strip markdown code fences if model wraps output
        if line.startswith("```"):
            continue

        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        target = entry.get("target", "memory")
        mem_type = entry.get("type", "general")
        content = entry.get("content", "").strip()

        if not content or target not in ("memory", "user"):
            continue

        result = engine.add(
            content=content,
            target=target,
            type=mem_type,
            source="extraction",
            session_id=session_id,
        )
        if result.get("success"):
            saved += 1
            logger.debug("Auto-extracted [%s/%s]: %s", target, mem_type, content[:60])

    elapsed = time.monotonic() - start
    if saved:
        logger.info("Memory extraction: saved %d entries in %.1fs", saved, elapsed)


def _format_messages(messages: List[Dict], max_chars: int = 8000) -> str:
    """Format messages for the extraction prompt, truncating to budget."""
    lines = []
    total = 0
    # Process in reverse (most recent first) then reverse back
    for msg in reversed(messages):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, list):
            # Handle multipart content (text blocks)
            parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    parts.append(part.get("text", ""))
                elif isinstance(part, str):
                    parts.append(part)
            content = " ".join(parts)

        if not content or role == "system":
            continue

        # Truncate individual messages
        if len(content) > 1000:
            content = content[:1000] + "..."

        line = f"[{role}] {content}"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        total += len(line)

    lines.reverse()
    return "\n\n".join(lines)
