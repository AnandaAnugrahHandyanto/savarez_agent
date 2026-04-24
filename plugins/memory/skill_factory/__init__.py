"""Skill Factory memory provider.

Local-only procedural memory that watches successful delegations and turns
repeated workflows into draft SKILL.md files under the active Hermes profile.

This provider is intentionally conservative:
- no external API calls
- no automatic skill installation
- draft-only output under $HERMES_HOME/skill_factory/
- non-primary contexts are ignored
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)

_DEFAULT_MIN_HITS = 3
_DEFAULT_MAX_EXAMPLES = 5
_DEFAULT_DRAFT_DIR = "skill_factory/drafts"
_DEFAULT_STATE_DIR = "skill_factory"
_DEFAULT_CONFIG_FILE = "skill_factory.json"
_SUCCESS_RE = re.compile(
    r"\b(complete|completed|done|implemented|fixed|resolved|created|updated|passed|approved|success|successful)\b",
    re.IGNORECASE,
)
_STOPWORDS = {
    "the", "a", "an", "to", "for", "on", "with", "and", "or", "of", "in", "into",
    "from", "by", "about", "please", "help", "create", "implement", "fix", "add", "update",
    "make", "build", "set", "design", "draft", "write", "review", "task", "workflow",
    "agent", "skill", "skills", "session", "subagent", "delegation", "result", "results",
}


@dataclass
class _FingerprintRecord:
    count: int = 0
    first_seen: str = ""
    last_seen: str = ""
    task: str = ""
    result: str = ""
    draft_path: str = ""
    session_ids: List[str] = field(default_factory=list)
    examples: List[Dict[str, str]] = field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _slugify(text: str, *, max_len: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    if not slug:
        slug = "workflow"
    return slug[:max_len].rstrip("-") or "workflow"


def _normalize_text(text: str) -> str:
    text = re.sub(r"[`*_>#\[\]{}()\-—–:;,.!?/\\|\"'<>]+", " ", text.lower())
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _fingerprint(task: str) -> str:
    words = []
    for token in _normalize_text(task).split():
        if token in _STOPWORDS:
            continue
        if len(token) < 3:
            continue
        words.append(token)
    if not words:
        words = [token for token in _normalize_text(task).split() if len(token) >= 3]
    if not words:
        return "workflow"
    return "-".join(words[:6])


def _task_title(task: str) -> str:
    cleaned = re.sub(r"\s+", " ", task).strip()
    if not cleaned:
        return "Reusable Workflow"
    pieces = cleaned.split()
    return " ".join(pieces[:10]).strip().rstrip(".:;,") or "Reusable Workflow"


def _looks_successful(task: str, result: str) -> bool:
    haystack = f"{task}\n{result}".strip()
    if not haystack:
        return False
    return bool(_SUCCESS_RE.search(haystack)) or len(result.strip()) >= 20


def _load_json_file(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        logger.debug("Failed to read %s", path, exc_info=True)
    return dict(default)


class SkillFactoryMemoryProvider(MemoryProvider):
    """Conservative local skill accumulator.

    The provider records successful delegated workflows and emits draft skill
    documents once a fingerprint repeats enough times.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._session_id = ""
        self._hermes_home = Path.home() / ".hermes"
        self._config: Dict[str, Any] = self._default_config()
        self._state: Dict[str, Any] = self._default_state()
        self._state_path = self._hermes_home / _DEFAULT_STATE_DIR / "state.json"
        self._draft_dir = self._hermes_home / _DEFAULT_DRAFT_DIR
        self._enabled = True
        self._agent_context = "primary"
        self._platform = ""

    # ------------------------------------------------------------------
    # MemoryProvider lifecycle
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "skill_factory"

    def is_available(self) -> bool:
        return True

    def initialize(self, session_id: str, **kwargs) -> None:
        with self._lock:
            self._session_id = session_id or ""
            hermes_home = kwargs.get("hermes_home")
            if hermes_home:
                self._hermes_home = Path(hermes_home).expanduser()
            self._agent_context = str(kwargs.get("agent_context") or "primary")
            self._platform = str(kwargs.get("platform") or "")
            self._config = self._load_config()
            self._enabled = bool(self._config.get("enabled", True))
            self._draft_dir = self._resolve_draft_dir(self._config.get("draft_dir", _DEFAULT_DRAFT_DIR))
            self._state_path = self._resolve_state_path(self._config.get("state_dir", _DEFAULT_STATE_DIR))
            self._state = self._load_state()
            self._draft_dir.mkdir(parents=True, exist_ok=True)
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._flush_state()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return []

    def on_delegation(self, task: str, result: str, *, child_session_id: str = "", **kwargs) -> None:
        if not self._should_record():
            return
        if not _looks_successful(task, result):
            return
        with self._lock:
            fingerprint = _fingerprint(task)
            record = self._get_record(fingerprint)
            timestamp = _now_iso()
            record.count += 1
            if not record.first_seen:
                record.first_seen = timestamp
            record.last_seen = timestamp
            record.task = task.strip() or record.task
            record.result = result.strip() or record.result
            if child_session_id and child_session_id not in record.session_ids:
                record.session_ids.append(child_session_id)
            record.examples.append({
                "task": task.strip(),
                "result": result.strip(),
                "session_id": child_session_id,
                "timestamp": timestamp,
            })
            record.examples = record.examples[-int(self._config.get("max_examples", _DEFAULT_MAX_EXAMPLES)):]
            self._save_record(fingerprint, record)
            self._flush_state()
            if self._config.get("auto_write", True) and record.count >= int(self._config.get("min_hits", _DEFAULT_MIN_HITS)):
                self._write_draft(fingerprint, record)

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        if not self._should_record():
            return
        with self._lock:
            self._flush_state()
            # Re-write any drafts whose record count crossed the threshold.
            if not self._config.get("auto_write", True):
                return
            min_hits = int(self._config.get("min_hits", _DEFAULT_MIN_HITS))
            for fingerprint, raw in list(self._state.get("records", {}).items()):
                try:
                    record = self._record_from_dict(raw)
                    if record.count >= min_hits:
                        self._write_draft(fingerprint, record)
                except Exception:
                    logger.debug("Failed to finalize draft for %s", fingerprint, exc_info=True)

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        config_path = Path(hermes_home).expanduser() / _DEFAULT_CONFIG_FILE
        existing = _load_json_file(config_path, {})
        existing.update(values)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "enabled",
                "description": "Enable local skill drafting for repeated successful delegations.",
                "default": True,
                "required": False,
            },
            {
                "key": "auto_write",
                "description": "Write draft SKILL.md files automatically once a workflow repeats enough times.",
                "default": True,
                "required": False,
            },
            {
                "key": "min_hits",
                "description": "How many successful repeats are needed before a draft skill is created.",
                "default": _DEFAULT_MIN_HITS,
                "required": False,
            },
            {
                "key": "max_examples",
                "description": "How many examples to keep in each draft and state record.",
                "default": _DEFAULT_MAX_EXAMPLES,
                "required": False,
            },
            {
                "key": "draft_dir",
                "description": "Directory under HERMES_HOME where draft skills are written.",
                "default": _DEFAULT_DRAFT_DIR,
                "required": False,
            },
            {
                "key": "state_dir",
                "description": "Directory under HERMES_HOME where skill-factory state is stored.",
                "default": _DEFAULT_STATE_DIR,
                "required": False,
            },
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _default_config() -> Dict[str, Any]:
        return {
            "enabled": True,
            "auto_write": True,
            "min_hits": _DEFAULT_MIN_HITS,
            "max_examples": _DEFAULT_MAX_EXAMPLES,
            "draft_dir": _DEFAULT_DRAFT_DIR,
            "state_dir": _DEFAULT_STATE_DIR,
        }

    @staticmethod
    def _default_state() -> Dict[str, Any]:
        return {"version": 1, "records": {}}

    def _load_config(self) -> Dict[str, Any]:
        config_path = self._hermes_home / _DEFAULT_CONFIG_FILE
        data = _load_json_file(config_path, self._default_config())
        cfg = self._default_config()
        cfg.update({k: v for k, v in data.items() if v is not None})
        try:
            cfg["min_hits"] = max(2, min(10, int(cfg.get("min_hits", _DEFAULT_MIN_HITS))))
        except Exception:
            cfg["min_hits"] = _DEFAULT_MIN_HITS
        try:
            cfg["max_examples"] = max(1, min(10, int(cfg.get("max_examples", _DEFAULT_MAX_EXAMPLES))))
        except Exception:
            cfg["max_examples"] = _DEFAULT_MAX_EXAMPLES
        cfg["enabled"] = bool(cfg.get("enabled", True))
        cfg["auto_write"] = bool(cfg.get("auto_write", True))
        cfg["draft_dir"] = str(cfg.get("draft_dir", _DEFAULT_DRAFT_DIR))
        cfg["state_dir"] = str(cfg.get("state_dir", _DEFAULT_STATE_DIR))
        return cfg

    def _load_state(self) -> Dict[str, Any]:
        state = _load_json_file(self._state_path, self._default_state())
        if "records" not in state or not isinstance(state.get("records"), dict):
            state["records"] = {}
        return state

    def _flush_state(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(self._state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _resolve_draft_dir(self, draft_dir: str) -> Path:
        path = Path(draft_dir).expanduser()
        if not path.is_absolute():
            path = self._hermes_home / path
        return path

    def _resolve_state_path(self, state_dir: str) -> Path:
        path = Path(state_dir).expanduser()
        if not path.is_absolute():
            path = self._hermes_home / path
        return path / "state.json"

    def _should_record(self) -> bool:
        return self._enabled and self._agent_context in {"primary", "flush", "cli", "gateway"}

    def _get_record(self, fingerprint: str) -> _FingerprintRecord:
        records = self._state.setdefault("records", {})
        raw = records.get(fingerprint)
        if isinstance(raw, dict):
            return self._record_from_dict(raw)
        return _FingerprintRecord()

    @staticmethod
    def _record_from_dict(raw: Dict[str, Any]) -> _FingerprintRecord:
        return _FingerprintRecord(
            count=int(raw.get("count", 0) or 0),
            first_seen=str(raw.get("first_seen", "") or ""),
            last_seen=str(raw.get("last_seen", "") or ""),
            task=str(raw.get("task", "") or ""),
            result=str(raw.get("result", "") or ""),
            draft_path=str(raw.get("draft_path", "") or ""),
            session_ids=list(raw.get("session_ids", []) or []),
            examples=list(raw.get("examples", []) or []),
        )

    def _save_record(self, fingerprint: str, record: _FingerprintRecord) -> None:
        self._state.setdefault("records", {})[fingerprint] = {
            "count": record.count,
            "first_seen": record.first_seen,
            "last_seen": record.last_seen,
            "task": record.task,
            "result": record.result,
            "draft_path": record.draft_path,
            "session_ids": record.session_ids,
            "examples": record.examples,
        }

    def _draft_path_for(self, fingerprint: str, record: _FingerprintRecord) -> Path:
        slug = _slugify(fingerprint)
        title = _task_title(record.task or fingerprint)
        name_slug = _slugify(title, max_len=36)
        filename = "SKILL.md"
        return self._draft_dir / f"{slug}" / filename

    def _write_draft(self, fingerprint: str, record: _FingerprintRecord) -> None:
        draft_path = self._draft_path_for(fingerprint, record)
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        title = _task_title(record.task or fingerprint)
        skill_name = _slugify(title, max_len=50)
        if not skill_name.endswith("-skill"):
            skill_name = f"{skill_name}-skill"
        summary = self._summarize_result(record.result)
        examples = self._format_examples(record.examples)
        content = f"""---
name: {skill_name}
description: Auto-generated draft skill from repeated successful workflows: {summary}
version: 0.1.0
metadata:
  hermes:
    tags: [reference, skill-factory, procedural-memory, draft]
    source: local-skill-factory
    fingerprint: {fingerprint}
---

# {title}

## When to use
- Use this workflow when the same task pattern has been completed successfully multiple times.
- Generated automatically from repeated delegations.
- Review before promoting into `~/.hermes/skills/`.

## Procedure
1. Reproduce the successful workflow with the same prerequisites.
2. Follow the captured steps below.
3. Validate the outcome with the same success criteria.
4. Promote this draft only after human review.

## Captured pattern
- Fingerprint: `{fingerprint}`
- Repeats observed: {record.count}
- First seen: {record.first_seen}
- Last seen: {record.last_seen}

## Evidence
{examples}

## Notes
- This is intentionally draft-only.
- It is local to this Hermes profile.
- No automatic installation or prompt injection happens from this file.

## Suggested verification
- Re-run the same task against a fresh session.
- Confirm the success signal matches the captured evidence.
- Patch this draft if a missing step or pitfall appears.
"""
        draft_path.write_text(content, encoding="utf-8")
        record.draft_path = str(draft_path)
        self._save_record(fingerprint, record)

    def _summarize_result(self, result: str) -> str:
        result = re.sub(r"\s+", " ", (result or "").strip())
        if not result:
            return "successful workflow"
        return result[:180]

    def _format_examples(self, examples: List[Dict[str, str]]) -> str:
        if not examples:
            return "- No examples captured yet."
        lines = []
        for idx, item in enumerate(examples, 1):
            task = re.sub(r"\s+", " ", item.get("task", "").strip())
            result = re.sub(r"\s+", " ", item.get("result", "").strip())
            lines.append(f"- Example {idx}: task=`{task[:120]}`")
            if result:
                lines.append(f"  - result=`{result[:180]}`")
        return "\n".join(lines)


def register(ctx) -> None:
    """Register the skill-factory memory provider."""
    ctx.register_memory_provider(SkillFactoryMemoryProvider())
