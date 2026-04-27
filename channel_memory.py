"""Channel-level persistent memory for Hermes/Sacha.

Each Slack channel gets its own MEMORY.md in /home/hermes/projects/<name>/.
Memory is loaded at the start of each session and updated at session end.
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PROJECTS_DIR = Path(os.getenv("HERMES_PROJECTS_DIR", "/home/hermes/projects"))
GLOBAL_AGENTS = PROJECTS_DIR / "AGENTS.md"
MAX_MEMORY_LINES = 150


def _load_routing_table() -> dict:
    """Parse the routing table from global AGENTS.md. Returns {channel_id: project_name}."""
    mapping = {}
    if not GLOBAL_AGENTS.exists():
        return mapping
    try:
        content = GLOBAL_AGENTS.read_text(encoding="utf-8")
        for line in content.splitlines():
            match = re.search(
                r'\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|[^|]+\|\s*`/home/hermes/projects/([^/]+)/AGENTS\.md`',
                line
            )
            if match:
                channel_id = match.group(2)
                project_name = match.group(3)
                mapping[channel_id] = project_name
    except Exception as e:
        logger.warning("[ChannelMemory] Failed to parse routing table: %s", e)
    return mapping


def get_project_for_channel(channel_id: str) -> Optional[str]:
    """Return the project name for a Slack channel ID, or None."""
    return _load_routing_table().get(channel_id)


def load_channel_memory(channel_id: str) -> str:
    """Load channel memory content. Returns empty string if none exists."""
    project = get_project_for_channel(channel_id)
    if not project:
        return ""
    mem_path = PROJECTS_DIR / project / "MEMORY.md"
    if not mem_path.exists():
        return ""
    try:
        content = mem_path.read_text(encoding="utf-8").strip()
        return content
    except Exception as e:
        logger.warning("[ChannelMemory] Failed to load memory for %s: %s", project, e)
        return ""


def save_channel_memory(channel_id: str, content: str) -> bool:
    """Write channel memory content."""
    project = get_project_for_channel(channel_id)
    if not project:
        return False
    mem_path = PROJECTS_DIR / project / "MEMORY.md"
    try:
        mem_path.write_text(content, encoding="utf-8")
        logger.info("[ChannelMemory] Saved memory for project %s (%d chars)", project, len(content))
        return True
    except Exception as e:
        logger.warning("[ChannelMemory] Failed to save memory for %s: %s", project, e)
        return False


def build_channel_memory_prompt(channel_id: str) -> str:
    """Build a system prompt section with channel memory, if any exists."""
    memory = load_channel_memory(channel_id)
    project = get_project_for_channel(channel_id)
    if not memory or not project:
        return ""

    agents_path = PROJECTS_DIR / project / "AGENTS.md"
    agents_content = ""
    if agents_path.exists():
        try:
            agents_content = agents_path.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    parts = [f"\n\n## Contexte projet: {project}"]
    if agents_content:
        parts.append(agents_content)
    parts.append(f"\n## Memoire du channel (persistante entre les threads):\n{memory}")
    parts.append(
        "\n[System: La memoire ci-dessus est partagee entre tous les threads de ce channel. "
        "A la fin de cette conversation, les informations importantes seront automatiquement "
        "sauvegardees dans la memoire du channel.]"
    )
    return "\n\n".join(parts)


def auto_setup_channel(channel_id: str, channel_name: str) -> Optional[str]:
    """Auto-create project structure for a new channel. Returns project name or None."""
    if not channel_name or channel_name.startswith("D"):
        return None

    existing = get_project_for_channel(channel_id)
    if existing:
        return existing

    clean_name = re.sub(r'[^a-z0-9_-]', '-', channel_name.lower().strip('#'))
    project_dir = PROJECTS_DIR / clean_name

    try:
        project_dir.mkdir(parents=True, exist_ok=True)

        agents_path = project_dir / "AGENTS.md"
        if not agents_path.exists():
            agents_path.write_text(
                f"# {clean_name} — Contexte Projet\n\n"
                f"## Description\n"
                f"Projet {clean_name} (channel Slack: #{channel_name})\n\n"
                f"## Stack\n- A completer\n\n"
                f"## Priorites\n- A completer\n",
                encoding="utf-8",
            )

        mem_path = project_dir / "MEMORY.md"
        if not mem_path.exists():
            mem_path.write_text(
                f"# Memoire — {clean_name}\n\n"
                f"> Memoire persistante du channel #{channel_name}. "
                f"Mise a jour automatiquement.\n\n"
                f"## Historique\n"
                f"- {datetime.now(timezone.utc).strftime('%Y-%m-%d')} : Channel cree\n",
                encoding="utf-8",
            )

        _add_to_routing_table(channel_id, channel_name, clean_name)
        _add_to_free_response(channel_id)
        _add_to_routing_skill(clean_name)

        logger.info("[ChannelMemory] Auto-created project '%s' for channel %s", clean_name, channel_id)
        return clean_name

    except Exception as e:
        logger.error("[ChannelMemory] Failed to auto-setup channel %s: %s", channel_id, e)
        return None


def _add_to_routing_table(channel_id: str, channel_name: str, project_name: str):
    """Add a channel to the global AGENTS.md routing table."""
    if not GLOBAL_AGENTS.exists():
        return
    content = GLOBAL_AGENTS.read_text(encoding="utf-8")
    if channel_id in content:
        return
    new_row = f"| `#{project_name}` | `{channel_id}` | Projet {project_name} | `/home/hermes/projects/{project_name}/AGENTS.md` |"
    content = content.replace(
        "| DM / `#general`",
        f"{new_row}\n| DM / `#general`",
    )
    if f"projects/{project_name}/" not in content:
        content += f"\n- `projects/{project_name}/` — Projet {project_name}"
    GLOBAL_AGENTS.write_text(content, encoding="utf-8")


def _add_to_free_response(channel_id: str):
    """Add channel to slack.free_response_channels in config.yaml.

    Uses YAML to reliably read the current value from the slack section,
    then does a targeted text replacement to preserve the file's formatting.
    The old regex-based approach matched the first `free_response_channels:`
    occurrence (which could be in another section like `discord:`) and
    doubled the indentation on each call, producing invalid YAML.
    """
    from hermes_constants import get_hermes_home
    config_path = get_hermes_home() / "config.yaml"
    if not config_path.exists():
        return
    try:
        content = config_path.read_text(encoding="utf-8")
        if channel_id in content:
            return

        import yaml as _yaml
        data = _yaml.safe_load(content) or {}

        slack_cfg = data.get("slack", {})
        current = str(slack_cfg.get("free_response_channels", "") or "")
        new_val = f"{current},{channel_id}" if current else channel_id

        # Text replacement: find the exact existing line under the slack section
        # and update only its value, preserving indentation and file structure.
        # We search for the slack section first to avoid touching other sections
        # (e.g. discord) that may also have a free_response_channels key.
        import re as _re
        slack_match = _re.search(r'^slack:[ \t]*\n', content, _re.MULTILINE)
        if slack_match:
            # Grab the slack block: lines starting with whitespace after `slack:`
            after_slack = content[slack_match.end():]
            block_end = _re.search(r'^\S', after_slack, _re.MULTILINE)
            slack_block = after_slack[:block_end.start()] if block_end else after_slack

            frc_match = _re.search(
                r'^([ \t]*free_response_channels:[ \t]*)(.*?)$',
                slack_block, _re.MULTILINE,
            )
            if frc_match:
                old_line = frc_match.group(0)
                new_line = frc_match.group(1) + new_val
                new_block = slack_block.replace(old_line, new_line, 1)
                content = content[:slack_match.end()] + new_block + (after_slack[block_end.start():] if block_end else "")
                config_path.write_text(content, encoding="utf-8")
                return

        # Fallback: slack section or its free_response_channels key not found.
        # Append a minimal slack block so the channel still works.
        logger.warning("[ChannelMemory] slack.free_response_channels not found; appending to config")
        content = content.rstrip("\n") + f"\nslack:\n  free_response_channels: {new_val}\n"
        config_path.write_text(content, encoding="utf-8")
    except Exception as e:
        logger.warning("[ChannelMemory] Failed to update free_response_channels: %s", e)


def _add_to_routing_skill(project_name: str):
    """Add project to the routing skill."""
    from hermes_constants import get_hermes_home
    skill_path = get_hermes_home() / "skills" / "project-management" / "project-context-routing.md"
    if not skill_path.exists():
        return
    try:
        content = skill_path.read_text(encoding="utf-8")
        if project_name in content:
            return
        new_line = f'#{project_name}     → read_file("/home/hermes/projects/{project_name}/AGENTS.md") + read_file("/home/hermes/projects/{project_name}/MEMORY.md")'
        content = content.replace(
            "DM / general",
            f"{new_line}\nDM / general",
        )
        skill_path.write_text(content, encoding="utf-8")
    except Exception as e:
        logger.warning("[ChannelMemory] Failed to update routing skill: %s", e)


def build_memory_update_prompt(channel_id: str, conversation_history: list) -> Optional[str]:
    """Build a prompt for the flush agent to update channel memory."""
    project = get_project_for_channel(channel_id)
    if not project:
        return None

    current_memory = load_channel_memory(channel_id)
    mem_path = PROJECTS_DIR / project / "MEMORY.md"

    return (
        f"[System: Mise a jour de la memoire du channel pour le projet '{project}'.\n\n"
        f"Fichier memoire: {mem_path}\n\n"
        f"Contenu actuel de la memoire:\n```\n{current_memory}\n```\n\n"
        f"Revois la conversation ci-dessus et mets a jour la memoire du channel:\n"
        f"1. Ajoute les decisions, faits et informations importants decouverts\n"
        f"2. Retire les informations obsoletes ou redondantes\n"
        f"3. Garde la memoire concise (max {MAX_MEMORY_LINES} lignes)\n"
        f"4. Utilise des bullet points dates (YYYY-MM-DD)\n"
        f"5. Preserve la structure existante (sections)\n\n"
        f"Utilise write_file pour sauvegarder le fichier mis a jour a: {mem_path}\n"
        f"Ne reponds PAS a l'utilisateur. Mets juste a jour le fichier memoire.]"
    )
