"""
Skill hash pinning — integrity verification for approved skills.

After skills_guard approves a skill, its content hash is recorded.
Before a skill is loaded into the system prompt, the hash is verified.
If the content has changed since the last approved scan, the skill is
flagged as tampered and excluded from the prompt.

This prevents TOCTOU attacks where an agent modifies a skill between
the security scan and the next prompt build.
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Hash pin store lives alongside the skills directory.
_PIN_FILE: Optional[Path] = None
_pins: dict[str, str] = {}  # skill_name → hash


def _get_pin_file() -> Path:
    global _PIN_FILE
    if _PIN_FILE is None:
        from hermes_cli.config import get_hermes_home
        _PIN_FILE = get_hermes_home() / "skills" / ".skill_hashes.json"
    return _PIN_FILE


def _load_pins() -> dict[str, str]:
    global _pins
    pin_file = _get_pin_file()
    if pin_file.exists():
        try:
            _pins = json.loads(pin_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Failed to load skill hash pins: %s", e)
            _pins = {}
    return _pins


def _save_pins() -> None:
    pin_file = _get_pin_file()
    try:
        pin_file.parent.mkdir(parents=True, exist_ok=True)
        pin_file.write_text(json.dumps(_pins, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to save skill hash pins: %s", e)


def pin_skill(skill_name: str, skill_dir: Path) -> str:
    """Record the content hash of an approved skill. Returns the hash."""
    from tools.skills_guard import content_hash
    h = content_hash(skill_dir)
    if not _pins:
        _load_pins()
    _pins[skill_name] = h
    _save_pins()
    logger.debug("Pinned skill %s → %s", skill_name, h)
    return h


def unpin_skill(skill_name: str) -> None:
    """Remove pin for a deleted skill."""
    if not _pins:
        _load_pins()
    if skill_name in _pins:
        del _pins[skill_name]
        _save_pins()


def verify_skill(skill_name: str, skill_dir: Path) -> bool:
    """Verify a skill's content matches its pinned hash.

    Returns True if:
    - The skill has no pin (unpinned skills are allowed — only agent-created
      skills get pinned, builtins don't)
    - The hash matches

    Returns False if:
    - The skill has a pin and the hash doesn't match (tampered)
    """
    if not _pins:
        _load_pins()
    pinned_hash = _pins.get(skill_name)
    if pinned_hash is None:
        return True  # No pin → not an agent-created skill, allow
    from tools.skills_guard import content_hash
    current = content_hash(skill_dir)
    if current != pinned_hash:
        logger.warning(
            "Skill %s failed integrity check: pinned=%s current=%s (tampered?)",
            skill_name, pinned_hash, current,
        )
        return False
    return True
