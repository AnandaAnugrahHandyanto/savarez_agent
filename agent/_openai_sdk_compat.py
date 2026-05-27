"""OpenAI SDK compatibility shims.

Surgical, idempotent monkey-patches applied at import time so we can stay
on a pinned ``openai`` version (see ``pyproject.toml`` — other releases
trigger a pydantic-core segfault) while working around bugs that only
surface against the chatgpt.com ``backend-api/codex`` endpoint.

Currently installs one guard:

* :func:`install_codex_responses_output_guard` — coerces
  ``Response.output is None`` to ``[]`` before
  ``openai.lib._parsing._responses.parse_response`` iterates it.
  chatgpt.com emits early streaming snapshots where ``output`` is
  ``null``; the SDK iterates without a None-guard at
  ``_parsing/_responses.py:61`` (called from
  ``lib/streaming/responses/_responses.py:360`` inside
  ``accumulate_event``), which crashes the entire ``for event in stream``
  loop *before* our own normalizers in ``run_codex_stream`` /
  ``_normalize_codex_response`` get a chance to run.

  Because ``streaming/responses/_responses.py`` does
  ``from ..._parsing._responses import parse_response``, the symbol is
  bound in two namespaces; both must be patched.
"""

from __future__ import annotations

import functools
import logging
from typing import Any

logger = logging.getLogger(__name__)

_PATCH_MARKER = "_hermes_codex_output_none_guard"


def _wrap_parse_response(original: Any) -> Any:
    """Return a wrapper that coerces ``response.output is None`` → ``[]``.

    The wrapped ``parse_response`` is keyword-only in current openai
    releases, but we look in positional args too so a future signature
    change cannot break us.
    """

    @functools.wraps(original)
    def _guarded_parse_response(*args: Any, **kwargs: Any) -> Any:
        try:
            resp = kwargs.get("response")
            if resp is None and args:
                resp = args[-1]
            if resp is not None and getattr(resp, "output", _MISSING) is None:
                try:
                    resp.output = []
                except Exception:
                    # Pydantic model could reject direct assignment in some
                    # configs; swallow so we still defer to the original
                    # and surface its (clearer) error instead of ours.
                    logger.debug(
                        "codex output None-guard: could not coerce response.output to []",
                        exc_info=True,
                    )
        except Exception:
            logger.debug(
                "codex output None-guard: pre-call inspection failed; "
                "passing through to original parse_response",
                exc_info=True,
            )
        return original(*args, **kwargs)

    setattr(_guarded_parse_response, _PATCH_MARKER, True)
    return _guarded_parse_response


_MISSING = object()


def install_codex_responses_output_guard() -> None:
    """Patch ``parse_response`` in both namespaces.

    Idempotent: re-invocation is a no-op once the marker attribute is
    present. Defensive: if the openai layout changes and the target
    modules/symbols disappear, we log at DEBUG and bail without raising —
    a future SDK that fixed this upstream should not break Hermes
    startup.
    """
    try:
        import openai.lib._parsing._responses as _origin_mod  # type: ignore
        import openai.lib.streaming.responses._responses as _streaming_mod  # type: ignore
    except Exception:
        logger.debug(
            "codex output None-guard: openai SDK modules not importable; skipping",
            exc_info=True,
        )
        return

    for mod in (_origin_mod, _streaming_mod):
        try:
            current = getattr(mod, "parse_response", None)
            if current is None:
                logger.debug(
                    "codex output None-guard: %s has no parse_response attribute; skipping",
                    getattr(mod, "__name__", repr(mod)),
                )
                continue
            if getattr(current, _PATCH_MARKER, False):
                continue
            mod.parse_response = _wrap_parse_response(current)  # type: ignore[attr-defined]
        except Exception:
            logger.debug(
                "codex output None-guard: failed to patch %s",
                getattr(mod, "__name__", repr(mod)),
                exc_info=True,
            )
