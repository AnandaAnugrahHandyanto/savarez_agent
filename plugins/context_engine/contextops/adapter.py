"""Fail-closed Hermes adapter for the standalone ContextOps/ESE core.

Config contract (under ``context.contextops`` in Hermes config.yaml)::

    context:
      engine: compressor
      contextops:
        enabled: false
        package: contextops_ese
        storage_root: ~/.hermes/contextops
        preview: true
        inject: false
        max_context_pack_chars: 4000
        include_raw_transcript: false
        include_raw_ids: false
        include_paths: false

Every degraded state (disabled, core package absent, invalid input schema,
unsafe core output, storage error) resolves to ``build_preview`` returning
``None`` — the adapter never raises into its caller and never injects.

TODO(#contextops): wire a real read-only call site once roadmap Milestone 8
is approved. Until then this is a preview-only skeleton.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# --- Adapter-owned leak gate -------------------------------------------------
# These patterns are intentionally a *self-contained* copy of the core leak
# categories. The adapter must not rely solely on ``contextops_ese`` to scrub
# its own output: if the core validator regresses (or is monkeypatched away),
# this gate still keeps unsafe core output from reaching Hermes. It is the
# adapter's last line of defence and depends on nothing in the core package.
_ADAPTER_LEAK_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Raw transcript / chat-turn role markers.
    re.compile(r"(?im)^\s*(?:user|assistant|system|human|ai|tool|developer)\s*:"),
    re.compile(r"<\|?(?:im_start|im_end|endoftext|eot_id)\|?>|\[/?INST\]|<<SYS>>"),
    # Provider request/response payload JSON shapes.
    re.compile(
        r'"(?:messages|choices|role|content|tool_calls|finish_reason'
        r'|stop_reason|completion|usage|prompt_tokens|completion_tokens)"\s*:'
    ),
    # Credential / secret-like keys and assignments.
    re.compile(
        r"(?i)\b(?:api[_-]?keys?|apikey|secrets?|passwords?|passwd|bearer"
        r"|access[_-]?tokens?|auth[_-]?tokens?|refresh[_-]?tokens?"
        r"|client[_-]?secret|private[_-]?key|credentials?)\b"
    ),
    re.compile(r"(?i)\b(?:token|key|secret|password|pwd)\b\s*[=:]\s*\S"),
    # Token-looking values: AWS / OpenAI / GitHub / Slack tokens, JWTs, long hex.
    re.compile(
        r"\bAKIA[0-9A-Z]{16}\b|\bsk-[A-Za-z0-9]{16,}\b|\bghp_[A-Za-z0-9]{20,}\b"
        r"|\bxox[baprs]-[A-Za-z0-9-]{10,}\b"
        r"|\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{2,}\b"
        r"|\b[0-9a-fA-F]{32,}\b"
    ),
    # Raw message/session/id field names and id-shaped values.
    re.compile(
        r"(?i)\b(?:raw_id|message_id|msg_id|session_id|sess_id|chat_id"
        r"|thread_id|conversation_id|conv_id|user_id|event_id)\b"
    ),
    re.compile(
        r"(?i)\b(?:msg|sess|session|message|conversation|conv)[-_][a-z0-9]*\d[a-z0-9]*\b"
    ),
    # Absolute POSIX paths, user-home (~/...), Windows drive paths.
    re.compile(r"(?:^|\s)(?:/[^\s/]|~/|[A-Za-z]:[\\/])"),
)
# An opaque ref carries only a hex digest — never a raw id, path, or payload.
_ADAPTER_REF_TOKEN_RE = re.compile(r"ref:[0-9a-f]{6,64}\Z")


def _adapter_output_is_unsafe(preview: dict[str, Any]) -> bool:
    """Independently re-scan a serialized preview dict for leaks.

    Returns ``True`` (caller fails closed) on any unsafe string, non-string
    field, or non-opaque ref. Deliberately calls into nothing from the core
    package so it stays a genuine defence-in-depth check.
    """

    for field in ("id", "restore", "avoid", "refs"):
        value = preview.get(field)
        items = value if isinstance(value, list) else [value]
        for item in items:
            if not isinstance(item, str) or not item or not item.isprintable():
                return True
            if any(p.search(item) for p in _ADAPTER_LEAK_PATTERNS):
                return True
    for ref in preview.get("refs", []):
        if not isinstance(ref, str) or not _ADAPTER_REF_TOKEN_RE.fullmatch(ref.strip()):
            return True
    return False

# Fail-safe defaults — a harness must opt in explicitly to change any of these.
_DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": False,
    "package": "contextops_ese",
    "storage_root": "~/.hermes/contextops",
    "preview": True,
    "inject": False,
    "max_context_pack_chars": 4000,
    "include_raw_transcript": False,
    "include_raw_ids": False,
    "include_paths": False,
}


def default_config() -> dict[str, Any]:
    """Return a copy of the fail-safe ``context.contextops`` config block."""

    return dict(_DEFAULT_CONFIG)


def _import_core():
    """Import the standalone ``contextops_ese`` core, or ``None`` if absent.

    Isolated into its own function so the optional dependency stays optional
    and so tests can simulate an uninstalled core.
    """

    try:
        import contextops_ese  # noqa: F401

        return contextops_ese
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("contextops_ese core unavailable: %s", exc)
        return None


class ContextOpsAdapter:
    """Thin, read-only bridge from Hermes evidence to a ContextOps preview."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        merged = default_config()
        if isinstance(config, dict):
            merged.update({k: v for k, v in config.items() if k in merged})
        self.config = merged

    @property
    def should_inject(self) -> bool:
        """Whether the pack may be injected — always ``False`` in this skeleton.

        Injection requires both ``inject`` config and a future approved call
        site; the skeleton has no call site, so this is hard-wired off.
        """

        return False

    @property
    def active(self) -> bool:
        """``True`` only if explicitly enabled *and* the core is importable."""

        if not self.config.get("enabled", False):
            return False
        return _import_core() is not None

    def _storage_root(self) -> Path | None:
        """Resolve the storage root defensively; never writes, never raises.

        A preview-only adapter still treats an impossible storage location as a
        degraded state: later productization may read/write there, so fail
        closed now instead of normalizing a bad path into a successful preview.
        """

        try:
            root = Path(str(self.config["storage_root"])).expanduser()
            if root.exists() and not root.is_dir():
                return None
            if root.parent.exists() and not root.parent.is_dir():
                return None
            return root
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("contextops storage_root unresolved: %s", exc)
            return None

    def build_preview(self, observations: Any) -> dict[str, Any] | None:
        """Build a read-only context pack preview, or ``None`` (fail closed).

        ``observations`` is a list of harness-agnostic dicts with at least
        ``raw_id`` and ``signal`` keys (``raw_text``/``raw_refs`` optional).
        """

        if not self.active:
            return None
        core = _import_core()
        if core is None:
            return None

        try:
            parsed = self._parse_observations(core, observations)
        except (ValueError, TypeError) as exc:
            logger.debug("contextops rejected observation schema: %s", exc)
            return None

        if self._storage_root() is None:
            return None

        try:
            cfg = core.PreviewConfig(
                enabled=True,
                preview=bool(self.config.get("preview", True)),
                inject=False,
                max_context_pack_chars=int(self.config.get("max_context_pack_chars", 4000)),
            )
            pack = core.build_context_pack_preview(parsed, cfg)
            preview = self._preview_from_pack(core, pack)
        except Exception as exc:
            # Unsafe input/output (absolute path, token-looking value, raw id, etc.) -> fail closed.
            logger.debug("contextops core declined to build a pack: %s", exc)
            return None

        return preview

    @staticmethod
    def _preview_from_pack(core: Any, pack: Any) -> dict[str, Any]:
        """Convert a core pack to a dict only after an adapter-owned leak gate.

        This duplicates the final safety check at the Hermes boundary so the
        adapter still fails closed if the standalone core regresses or is
        monkeypatched by a test harness.
        """

        if hasattr(core, "assert_pack_safe"):
            core.assert_pack_safe(pack)
        preview = {
            "id": pack.id,
            "restore": list(pack.restore),
            "avoid": list(pack.avoid),
            "refs": list(pack.refs),
            "preview": True,
            "injected": False,
        }
        for field in ("id", "restore", "avoid", "refs"):
            values = preview[field] if isinstance(preview[field], list) else [preview[field]]
            for value in values:
                if not isinstance(value, str):
                    raise ValueError(f"preview {field} contains a non-string value")
                reason = core.scan_unsafe(value) if hasattr(core, "scan_unsafe") else None
                if reason is not None:
                    raise ValueError(f"preview {field} rejected by leak gate: {reason}")
            if field == "refs" and hasattr(core, "assert_ref_safe"):
                for value in values:
                    core.assert_ref_safe(value, "preview ref")
        # Adapter-owned final gate: independent of the core leak validator, so
        # unsafe output cannot reach Hermes even if that validator regresses.
        if _adapter_output_is_unsafe(preview):
            raise ValueError("preview rejected by adapter-owned leak gate")
        return preview

    @staticmethod
    def _parse_observations(core: Any, observations: Any) -> list[Any]:
        if not isinstance(observations, list) or not observations:
            raise ValueError("observations must be a non-empty list")
        parsed = []
        for row in observations:
            if not isinstance(row, dict):
                raise TypeError("each observation must be a mapping")
            raw_id = row.get("raw_id")
            signal = row.get("signal")
            if not isinstance(raw_id, str) or not raw_id.strip():
                raise ValueError("observation requires a non-empty 'raw_id'")
            if not isinstance(signal, str) or not signal.strip():
                raise ValueError("observation requires a non-empty 'signal'")
            raw_refs = row.get("raw_refs", row.get("refs", ()))
            if raw_refs is None:
                raw_refs = ()
            if isinstance(raw_refs, str) or not isinstance(raw_refs, (list, tuple)):
                raise ValueError("observation raw_refs must be a list or tuple of strings")
            if not all(isinstance(ref, str) for ref in raw_refs):
                raise ValueError("observation raw_refs must contain only strings")
            parsed.append(
                core.Observation(
                    raw_id=raw_id,
                    signal=signal,
                    raw_text=str(row.get("raw_text", "")),
                    raw_refs=tuple(raw_refs),
                )
            )
        return parsed
