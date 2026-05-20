"""Safe ContextPack preview builder for the standalone ContextOps/ESE core.

The builder enforces, by construction, the boundary distinctions:

* **Context pack != transcript** — ``Observation.raw_text`` is never copied
  into the pack; only the caller-derived ``signal`` is, and only after
  passing the safety scrub.
* **Refs are opaque** — raw ids are replaced by deterministic ``ref:<hash>``
  tokens via :func:`safe_ref`.
* **No filesystem leakage** — any signal carrying an absolute path is
  rejected (fail closed) rather than silently scrubbed.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from .contracts import ContextPack, Observation, PreviewConfig
from .safety import assert_pack_safe, assert_text_safe, scan_unsafe

_REF_PREFIX = "ref:"
_REF_HASH_LEN = 12
_MAX_SIGNAL_CHARS = 200


def safe_ref(raw_id: str) -> str:
    """Return a deterministic, opaque ref token for ``raw_id``.

    The raw id never appears in the result, so packs cannot leak provider
    ids, session ids, or message ids downstream.
    """

    cleaned = (raw_id or "").strip()
    if not cleaned:
        raise ValueError("safe_ref requires a non-empty id")
    digest = hashlib.sha1(cleaned.encode("utf-8")).hexdigest()[:_REF_HASH_LEN]
    return f"{_REF_PREFIX}{digest}"


def _scrub_signal(signal: str) -> str:
    """Validate one cognitive signal line, failing closed on unsafe content.

    The full leak gate (transcripts, provider payloads, secrets, raw ids,
    paths) is applied via :func:`contextops_ese.safety.scan_unsafe`.
    """

    text = (signal or "").strip()
    if not text:
        raise ValueError("observation signal must not be empty")
    if len(text) > _MAX_SIGNAL_CHARS:
        raise ValueError(f"signal exceeds {_MAX_SIGNAL_CHARS} chars; summarise upstream")
    return assert_text_safe(text, "signal")


def _reject_unsafe_raw_refs(obs: list[Observation]) -> None:
    """Fail closed if any observation carries a disallowed ``raw_ref``.

    Raw refs are opaque input; an unsafe one (path, provider JSON, secret,
    transcript) must abort the pack rather than be silently dropped.
    """

    for o in obs:
        for ref in o.raw_refs:
            reason = scan_unsafe(str(ref))
            if reason is not None:
                raise ValueError(f"observation raw_ref rejected by leak gate: {reason}")


def _bounded(lines: list[str], budget: int) -> tuple[str, ...]:
    """Trim ``lines`` so their joined length stays within ``budget`` chars."""

    kept: list[str] = []
    used = 0
    for line in lines:
        cost = len(line) + (1 if kept else 0)
        if used + cost > budget:
            break
        kept.append(line)
        used += cost
    return tuple(kept)


def build_context_pack_preview(
    observations: Iterable[Observation],
    config: PreviewConfig | None = None,
    *,
    pack_id: str = "pack-contextops-ese",
) -> ContextPack:
    """Build a safe, read-only :class:`ContextPack` preview.

    Raises ``ValueError`` (fail closed) when given no observations or a
    signal that carries an absolute path or other unsafe content.
    """

    cfg = config or PreviewConfig()
    obs = list(observations)
    if not obs:
        raise ValueError("at least one observation is required to build a pack")

    _reject_unsafe_raw_refs(obs)
    restore = [_scrub_signal(o.signal) for o in obs]
    avoid = [_scrub_signal(s) for s in cfg.avoid_signals] or [
        "do not restore resolved or stale threads as if still live",
    ]
    refs = [safe_ref(o.raw_id) for o in obs]

    # Budget the variable-length sections; pack id always survives.
    budget = max(0, cfg.max_context_pack_chars - len(pack_id))
    restore_b = _bounded(restore, budget // 2)
    avoid_b = _bounded(avoid, budget // 4) or (avoid[0][: max(0, budget // 4)],)
    refs_b = _bounded(refs, budget // 4)

    pack = ContextPack(id=pack_id, restore=restore_b, avoid=avoid_b, refs=refs_b)
    # Mandatory final gate: no unsafe string may ever leave the builder.
    return assert_pack_safe(pack)
