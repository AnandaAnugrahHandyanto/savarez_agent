"""Cerebras provider profile."""

import json
import logging
import urllib.request

from providers import register_provider
from providers.base import ProviderProfile

logger = logging.getLogger(__name__)


class CerebrasProfile(ProviderProfile):
    """Cerebras Inference API provider."""

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        """Fetch available models from Cerebras API."""
        if not api_key:
            return None
        try:
            req = urllib.request.Request("https://api.cerebras.ai/v1/models")
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
            logger.debug("fetch_models(cerebras): %s", exc)
            return None


cerebras = CerebrasProfile(
    name="cerebras",
    aliases=("cerebras-inference",),
    api_mode="chat_completions",
    env_vars=("CEREBRAS_API_KEY",),
    base_url="https://api.cerebras.ai/v1",
    auth_type="api_key",
    default_aux_model="llama3.1-8b",
)

register_provider(cerebras)