"""Image-gen wrapper provider — codex primary with gemini fallback.

Hermes' built-in ``image_gen.provider`` config is a single value, not a
list. To get "try openai-codex first, fall back to gemini if it fails"
behavior, we register a synthetic provider that internally chains the
two. Set ``image_gen.provider: codex-with-gemini-fallback`` in
``config.yaml`` to use it.

Failures classified as ``auth_required``, ``rate_limited``, or
``api_error`` trigger fallback. Failures like ``invalid_argument`` or
``content_filter`` do NOT — those are user-side issues that the next
provider would also reject. ``empty_response`` and ``io_error`` DO
trigger fallback (transient enough to be worth a retry on the other
backend).

The wrapper looks up its inner providers from the image_gen registry
at call time, so plugin discovery order doesn't matter.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
)

logger = logging.getLogger(__name__)


PRIMARY_NAME = "openai-codex"
FALLBACK_NAME = "gemini"

_FAILOVER_ERROR_TYPES = {
    "auth_required",
    "rate_limited",
    "api_error",
    "empty_response",
    "io_error",
    "missing_dependency",
}


def _get_provider(name: str):
    try:
        from agent.image_gen_registry import get_provider
        return get_provider(name)
    except Exception as exc:
        logger.debug("registry lookup for %s failed: %s", name, exc)
        return None


class CodexWithGeminiFallbackProvider(ImageGenProvider):
    """Tries openai-codex; on a recoverable error, retries via gemini."""

    @property
    def name(self) -> str:
        return "codex-with-gemini-fallback"

    @property
    def display_name(self) -> str:
        return "OpenAI Codex (primary) → Gemini (fallback)"

    def is_available(self) -> bool:
        primary = _get_provider(PRIMARY_NAME)
        fallback = _get_provider(FALLBACK_NAME)
        return bool(
            (primary and primary.is_available())
            or (fallback and fallback.is_available())
        )

    def list_models(self) -> List[Dict[str, Any]]:
        return []

    def default_model(self) -> Optional[str]:
        return None

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Codex → Gemini fallback",
            "badge": "wrapper",
            "tag": ("Routes to openai-codex first, falls back to gemini on "
                    "auth/rate-limit/api errors. Configure each backend "
                    "separately."),
            "env_vars": [],
        }

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        attempts: List[Dict[str, Any]] = []

        primary = _get_provider(PRIMARY_NAME)
        if primary is None:
            attempts.append({
                "provider": PRIMARY_NAME,
                "error": "provider not registered",
                "error_type": "provider_not_registered",
            })
        else:
            try:
                result = primary.generate(prompt, aspect_ratio=aspect_ratio, **kwargs)
            except Exception as exc:
                logger.debug("primary %s raised: %s", PRIMARY_NAME, exc)
                result = error_response(
                    error=f"{PRIMARY_NAME} raised: {exc}",
                    error_type="api_error",
                    provider=PRIMARY_NAME,
                    aspect_ratio=aspect_ratio,
                )
            if isinstance(result, dict) and result.get("success"):
                result.setdefault("extra", {})["fallback_chain"] = [PRIMARY_NAME]
                return result
            attempts.append({
                "provider": PRIMARY_NAME,
                "error": (result or {}).get("error"),
                "error_type": (result or {}).get("error_type"),
            })
            if (result or {}).get("error_type") not in _FAILOVER_ERROR_TYPES:
                # User-side / non-retryable error — don't try fallback.
                return result

        fallback = _get_provider(FALLBACK_NAME)
        if fallback is None:
            return error_response(
                error=(f"Primary {PRIMARY_NAME} failed and fallback "
                       f"{FALLBACK_NAME} is not registered. Attempts: {attempts}"),
                error_type="provider_not_registered",
                provider=self.name,
                aspect_ratio=aspect_ratio,
            )

        try:
            result = fallback.generate(prompt, aspect_ratio=aspect_ratio, **kwargs)
        except Exception as exc:
            logger.debug("fallback %s raised: %s", FALLBACK_NAME, exc)
            result = error_response(
                error=f"{FALLBACK_NAME} raised: {exc}",
                error_type="api_error",
                provider=FALLBACK_NAME,
                aspect_ratio=aspect_ratio,
            )

        if isinstance(result, dict) and result.get("success"):
            result.setdefault("extra", {})["fallback_chain"] = [
                PRIMARY_NAME, FALLBACK_NAME]
            return result

        attempts.append({
            "provider": FALLBACK_NAME,
            "error": (result or {}).get("error"),
            "error_type": (result or {}).get("error_type"),
        })
        return error_response(
            error=("All image_gen providers failed. "
                   + "; ".join(f"{a['provider']}: {a.get('error_type')} "
                               f"({a.get('error')})" for a in attempts)),
            error_type="all_providers_failed",
            provider=self.name,
            aspect_ratio=aspect_ratio,
        )


def register(ctx) -> None:
    ctx.register_image_gen_provider(CodexWithGeminiFallbackProvider())
