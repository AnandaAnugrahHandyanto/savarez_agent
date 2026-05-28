"""Mistral provider profile."""

import json
import logging
import urllib.request

from providers import register_provider
from providers.base import ProviderProfile

logger = logging.getLogger(__name__)


class MistralProfile(ProviderProfile):
    """Mistral AI provider."""

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        """Fetch available models from Mistral API."""
        if not api_key:
            return None
        try:
            req = urllib.request.Request("https://api.mistral.ai/v1/models")
            req.add_header("Authorization", f"Bearer {api_key}")
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
            return [
                m["id"]
                for m in data.get("data", [])
                if isinstance(m, dict) and "id" in m
            ]
        except Exception as exc:
            logger.debug("fetch_models(mistral): %s", exc)
            return None


mistral = MistralProfile(
    name="mistral",
    aliases=("mistral-ai",),
    api_mode="chat_completions",
    env_vars=("MISTRAL_API_KEY",),
    base_url="https://api.mistral.ai/v1",
    auth_type="api_key",
    default_aux_model="mistral-large-latest",
)

register_provider(mistral)