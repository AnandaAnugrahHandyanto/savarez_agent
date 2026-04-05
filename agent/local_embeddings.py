"""Local embedding support via Ollama for zero-cost, low-latency vector operations.

Uses Ollama's /api/embeddings endpoint with lightweight models like nomic-embed-text
(137M params, sub-50ms on Apple Silicon). Falls back to OpenAI API if Ollama is
unavailable.

Setup:
    ollama pull nomic-embed-text    # ~275MB download, one-time

Usage:
    from agent.local_embeddings import get_embedding_provider
    provider = get_embedding_provider()
    embedding = provider.embed("some text")
"""

from __future__ import annotations

import logging
import os
import time
from typing import List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_OLLAMA_MODEL = "nomic-embed-text"
_DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"

# Cache the Ollama availability check to avoid repeated HTTP calls
_ollama_available: Optional[bool] = None
_ollama_checked_at: float = 0.0
_OLLAMA_CHECK_INTERVAL = 300.0  # Re-check every 5 minutes


def _is_ollama_available(base_url: str = _DEFAULT_OLLAMA_BASE_URL) -> bool:
    """Check if Ollama is running and responsive."""
    global _ollama_available, _ollama_checked_at

    now = time.time()
    if now - _ollama_checked_at < _OLLAMA_CHECK_INTERVAL and _ollama_available is not None:
        return _ollama_available

    _ollama_checked_at = now

    try:
        import httpx
        resp = httpx.get(f"{base_url}/api/tags", timeout=2.0)
        _ollama_available = resp.status_code == 200
    except Exception:
        try:
            import urllib.request
            req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                _ollama_available = resp.status == 200
        except Exception:
            _ollama_available = False

    return _ollama_available


def embed_via_ollama(
    text: str,
    model: str = _DEFAULT_OLLAMA_MODEL,
    base_url: str = _DEFAULT_OLLAMA_BASE_URL,
) -> Optional[List[float]]:
    """Embed text using Ollama's local embedding API.

    Returns the embedding vector, or None on failure.
    """
    if not _is_ollama_available(base_url):
        return None

    try:
        import httpx
        response = httpx.post(
            f"{base_url}/api/embeddings",
            json={"model": model, "prompt": text[:8000]},
            timeout=30.0,
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("embedding")
        logger.debug("Ollama embedding returned status %d", response.status_code)
        return None
    except ImportError:
        # Fall back to urllib if httpx not available
        try:
            import json
            import urllib.request
            payload = json.dumps({"model": model, "prompt": text[:8000]}).encode("utf-8")
            req = urllib.request.Request(
                f"{base_url}/api/embeddings",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("embedding")
        except Exception as e:
            logger.debug("Ollama embedding via urllib failed: %s", e)
            return None
    except Exception as e:
        logger.debug("Ollama embedding failed: %s", e)
        return None


def embed_via_openai(
    text: str,
    model: str = "openai/text-embedding-3-small",
) -> Optional[List[float]]:
    """Embed text via OpenAI/OpenRouter API. Returns None if unavailable."""
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.embeddings.create(
            model=model,
            input=text[:8000],
        )
        return response.data[0].embedding
    except Exception as e:
        logger.debug("OpenAI embedding failed: %s", e)
        return None


class EmbeddingProvider:
    """Unified embedding provider with local-first fallback to cloud.

    Tries Ollama first (free, fast), falls back to OpenAI if unavailable.
    Tracks which backend was used for cache compatibility (different models
    produce different-dimension embeddings).
    """

    def __init__(
        self,
        ollama_model: str = _DEFAULT_OLLAMA_MODEL,
        ollama_base_url: str = _DEFAULT_OLLAMA_BASE_URL,
        openai_model: str = "openai/text-embedding-3-small",
        prefer_local: bool = True,
    ):
        self._ollama_model = ollama_model
        self._ollama_base_url = ollama_base_url
        self._openai_model = openai_model
        self._prefer_local = prefer_local
        self._last_backend: Optional[str] = None

    @property
    def last_backend(self) -> Optional[str]:
        """Which backend was used for the most recent embedding ('ollama' or 'openai')."""
        return self._last_backend

    @property
    def model_id(self) -> str:
        """A string identifying the current embedding model for cache keying."""
        if self._prefer_local and _is_ollama_available(self._ollama_base_url):
            return f"ollama/{self._ollama_model}"
        return self._openai_model

    def embed(self, text: str) -> Optional[List[float]]:
        """Embed text using the best available backend.

        Returns the embedding vector, or None if all backends fail.
        """
        if self._prefer_local:
            result = embed_via_ollama(text, self._ollama_model, self._ollama_base_url)
            if result is not None:
                self._last_backend = "ollama"
                return result

        result = embed_via_openai(text, self._openai_model)
        if result is not None:
            self._last_backend = "openai"
            return result

        self._last_backend = None
        return None

    def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Embed multiple texts. Currently sequential — suitable for <100 items."""
        return [self.embed(text) for text in texts]


# Module-level singleton
_provider: Optional[EmbeddingProvider] = None


def get_embedding_provider() -> EmbeddingProvider:
    """Get the global embedding provider singleton."""
    global _provider
    if _provider is None:
        ollama_model = os.getenv("HERMES_EMBEDDING_MODEL", _DEFAULT_OLLAMA_MODEL)
        ollama_base = os.getenv("OLLAMA_BASE_URL", _DEFAULT_OLLAMA_BASE_URL)
        prefer_local = os.getenv("HERMES_PREFER_LOCAL_EMBEDDINGS", "true").lower() in ("true", "1", "yes")
        _provider = EmbeddingProvider(
            ollama_model=ollama_model,
            ollama_base_url=ollama_base,
            prefer_local=prefer_local,
        )
    return _provider
