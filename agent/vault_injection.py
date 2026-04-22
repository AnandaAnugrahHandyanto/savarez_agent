"""Vault injection — auto-load Obsidian vault files into the system prompt.

Reads working-context.md and user-profile.md from a configured vault path
at session start and injects them into the system prompt alongside Layer 1
memory (MEMORY.md / USER.md). This is a structural fix for vault neglect:
the agent no longer needs to remember to read these files — they're injected
automatically, the same way Layer 1 memory is.

The vault is Layer 3 in the memory architecture. Files injected here are
read-only in the system prompt (frozen at session start). Mid-session
writes to vault files require the read_file/write_file tools or the
memory-vault skill.

Config (in config.yaml under 'vault'):
  enabled: true          # enable vault injection
  path: /path/to/vault   # absolute path to the Obsidian vault root

Files read (relative to vault path):
  Agent-Hermes/working-context.md   — what the agent is actively doing
  Agent-Shared/user-profile.md      — who the user is (durable facts)

If either file doesn't exist or is empty, it's silently skipped.
If the vault path doesn't exist or isn't configured, vault injection is
silently disabled.
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Character limits for vault injection blocks (to prevent prompt bloat)
WORKING_CONTEXT_CHAR_LIMIT = 4000
USER_PROFILE_CHAR_LIMIT = 4000

SEPARATOR = "\u2550" * 46  # ═ same as memory_tool uses


def _read_vault_file(path: Path, char_limit: int) -> Optional[str]:
    """Read a vault file and return its content, or None if missing/empty.

    Truncates with a notice if the file exceeds char_limit.
    """
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8").strip()
    except (OSError, IOError) as e:
        logger.debug("Could not read vault file %s: %s", path, e)
        return None

    if not content:
        return None

    # Strip YAML frontmatter (same as prompt_builder does for context files)
    content = _strip_yaml_frontmatter(content)

    if not content:
        return None

    if len(content) > char_limit:
        truncated = content[:char_limit]
        # Find last newline to avoid cutting mid-line
        last_nl = truncated.rfind("\n")
        if last_nl > char_limit // 2:
            truncated = truncated[:last_nl]
        content = truncated + f"\n[... truncated at {char_limit} chars ...]"

    return content


def _strip_yaml_frontmatter(content: str) -> str:
    """Remove optional YAML frontmatter (--- delimited) from content."""
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            body = content[end + 4:].lstrip("\n")
            return body if body else content
    return content


def build_vault_system_prompt(vault_path: str) -> str:
    """Build the vault injection block for the system prompt.

    Reads working-context.md and user-profile.md from the vault and formats
    them with headers matching the style of Layer 1 memory blocks.

    Returns an empty string if vault is disabled, path is missing, or
    all files are empty.
    """
    if not vault_path:
        return ""

    vault_root = Path(vault_path)
    if not vault_root.is_dir():
        logger.debug("Vault path does not exist or is not a directory: %s", vault_path)
        return ""

    parts = []

    # Read working-context.md (agent's current state)
    wc_path = vault_root / "Agent-Hermes" / "working-context.md"
    wc_content = _read_vault_file(wc_path, WORKING_CONTEXT_CHAR_LIMIT)
    if wc_content:
        header = "VAULT: WORKING CONTEXT (what you're doing right now)"
        parts.append(f"{SEPARATOR}\n{header}\n{SEPARATOR}\n{wc_content}")

    # Read user-profile.md (shared user profile)
    up_path = vault_root / "Agent-Shared" / "user-profile.md"
    up_content = _read_vault_file(up_path, USER_PROFILE_CHAR_LIMIT)
    if up_content:
        header = "VAULT: USER PROFILE (durable facts from Obsidian vault)"
        parts.append(f"{SEPARATOR}\n{header}\n{SEPARATOR}\n{up_content}")

    return "\n\n".join(parts)