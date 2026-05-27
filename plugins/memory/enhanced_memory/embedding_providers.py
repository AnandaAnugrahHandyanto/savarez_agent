"""Embedding providers for the enhanced-memory plugin.

Supports multiple backends for generating text embeddings:
- Gemini API (Google, default, 3072-dim)
- OpenAI API (1536 or 3072-dim)
- Local sentence-transformers (configurable model and dimensions)

The user chooses via config.yaml:

  plugins:
    enhanced-memory:
      embedding_provider: gemini        # or "openai", "local", "none"
      embedding_model: gemini-embedding-001
      embedding_dims: 3072

For local provider, install: pip install sentence-transformers
"""

from __future__ import annotations

import json
import logging
import os
import struct
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class EmbeddingProvider(ABC):
    """Base class for embedding providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging and config."""

    @property
    @abstractmethod
    def dims(self) -> int:
        """Embedding dimensions."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider can generate embeddings."""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""

    def embed_single(self, text: str) -> list[float]:
        """Convenience: embed one text."""
        return self.embed_texts([text])[0]


# ---------------------------------------------------------------------------
# Gemini provider
# ---------------------------------------------------------------------------

class GeminiEmbedding(EmbeddingProvider):
    """Google Gemini Embedding API (gemini-embedding-001, 3072-dim)."""

    _API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
    BATCH_SIZE = 50
    BATCH_DELAY = 0.2

    def __init__(self, model: str = "gemini-embedding-001",
                 dimensions: int = 3072, api_key: str | None = None):
        self._model = model
        self._dims = dimensions
        self._api_key = api_key or self._resolve_key()
        self._embed_url = f"{self._API_BASE}/{self._model}:embedContent"
        self._batch_url = f"{self._API_BASE}/{self._model}:batchEmbedContents"

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def dims(self) -> int:
        return self._dims

    def is_available(self) -> bool:
        return self._api_key is not None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self._api_key:
            raise RuntimeError("No Gemini API key configured")
        if len(texts) == 1:
            return [self._embed_single(texts[0])]
        return self._embed_batch(texts)

    def _embed_single(self, text: str) -> list[float]:
        payload = {
            "model": f"models/{self._model}",
            "content": {"parts": [{"text": text}]},
        }
        resp = self._api_request(self._embed_url, payload)
        return resp["embedding"]["values"]

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        model_name = f"models/{self._model}"

        for batch_start in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[batch_start:batch_start + self.BATCH_SIZE]
            requests_payload = [
                {"model": model_name, "content": {"parts": [{"text": t}]}}
                for t in batch
            ]
            resp = self._api_request(self._batch_url, {"requests": requests_payload})
            for emb_obj in resp["embeddings"]:
                all_embeddings.append(emb_obj["values"])

            if batch_start + self.BATCH_SIZE < len(texts):
                time.sleep(self.BATCH_DELAY)

        return all_embeddings

    def _api_request(self, url: str, payload: dict) -> Any:
        full_url = f"{url}?key={self._api_key}"
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            full_url, data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode() if exc.fp else ""
            logger.error("Gemini API error %s: %s", exc.code, body[:200])
            raise
        except urllib.error.URLError as exc:
            logger.error("Gemini API network error: %s", exc.reason)
            raise

    @staticmethod
    def _resolve_key() -> str | None:
        for var in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
            val = os.environ.get(var)
            if val:
                return val
        hermes_home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
        env_file = Path(hermes_home) / ".env"
        if env_file.is_file():
            try:
                for line in env_file.read_text().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, _, value = line.partition("=")
                        key, value = key.strip(), value.strip().strip("'\"")
                        if key in ("GOOGLE_API_KEY", "GEMINI_API_KEY") and value:
                            return value
            except OSError:
                pass
        return None


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------

class OpenAIEmbedding(EmbeddingProvider):
    """OpenAI Embedding API (text-embedding-3-small/large/ada-002)."""

    BATCH_SIZE = 100

    def __init__(self, model: str = "text-embedding-3-small",
                 dimensions: int = 1536, api_key: str | None = None,
                 base_url: str | None = None):
        self._model = model
        self._dims = dimensions
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._base_url = (base_url or os.environ.get("OPENAI_BASE_URL", "")
                          or "https://api.openai.com/v1")

    @property
    def name(self) -> str:
        return "openai"

    @property
    def dims(self) -> int:
        return self._dims

    def is_available(self) -> bool:
        return self._api_key is not None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self._api_key:
            raise RuntimeError("No OpenAI API key configured")

        all_embeddings: list[list[float]] = []
        for batch_start in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[batch_start:batch_start + self.BATCH_SIZE]
            payload: dict[str, Any] = {
                "input": batch,
                "model": self._model,
            }
            # Only include dimensions for models that support it
            if self._model.startswith("text-embedding-3"):
                payload["dimensions"] = self._dims

            url = f"{self._base_url}/embeddings"
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                url, data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read().decode())
                for item in sorted(result["data"], key=lambda x: x["index"]):
                    all_embeddings.append(item["embedding"])
            except urllib.error.HTTPError as exc:
                body = exc.read().decode() if exc.fp else ""
                logger.error("OpenAI API error %s: %s", exc.code, body[:200])
                raise
            except urllib.error.URLError as exc:
                logger.error("OpenAI API network error: %s", exc.reason)
                raise

        return all_embeddings


# ---------------------------------------------------------------------------
# Local sentence-transformers provider
# ---------------------------------------------------------------------------

class LocalEmbedding(EmbeddingProvider):
    """Local embedding via sentence-transformers (no API calls).

    Install: pip install sentence-transformers
    """

    def __init__(self, model: str = "all-MiniLM-L6-v2",
                 dimensions: int | None = None, device: str = "cpu"):
        self._model_name = model
        self._device = device
        self._model = None
        self._dims_override = dimensions
        self._actual_dims: int | None = None

    @property
    def name(self) -> str:
        return "local"

    @property
    def dims(self) -> int:
        if self._actual_dims:
            return self._actual_dims
        if self._dims_override:
            return self._dims_override
        # Common defaults
        defaults = {
            "all-MiniLM-L6-v2": 384,
            "all-mpnet-base-v2": 768,
            "nomic-embed-text-v1": 768,
            "BAAI/bge-small-en-v1.5": 384,
            "BAAI/bge-base-en-v1.5": 768,
            "BAAI/bge-large-en-v1.5": 1024,
            "intfloat/e5-small-v2": 384,
            "intfloat/e5-base-v2": 768,
            "intfloat/e5-large-v2": 1024,
            "intfloat/multilingual-e5-large": 1024,
        }
        return defaults.get(self._model_name, 384)

    def is_available(self) -> bool:
        try:
            import sentence_transformers  # noqa: F401
            return True
        except ImportError:
            return False

    def _ensure_model(self) -> None:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(
                    self._model_name, device=self._device
                )
                # Get actual dimensions from model
                test = self._model.encode(["test"])
                self._actual_dims = len(test[0])
                logger.info(
                    "Loaded local embedding model %s (%d dims, device=%s)",
                    self._model_name, self._actual_dims, self._device,
                )
            except Exception as exc:
                logger.error("Failed to load local model %s: %s", self._model_name, exc)
                raise

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._ensure_model()
        embeddings = self._model.encode(texts, show_progress_bar=False)
        return [emb.tolist() for emb in embeddings]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

# Known provider configs with sensible defaults
PROVIDER_DEFAULTS: dict[str, dict[str, Any]] = {
    "gemini": {"class": GeminiEmbedding, "model": "gemini-embedding-001", "dims": 3072},
    "openai": {"class": OpenAIEmbedding, "model": "text-embedding-3-small", "dims": 1536},
    "openai-large": {"class": OpenAIEmbedding, "model": "text-embedding-3-large", "dims": 3072},
    "local": {"class": LocalEmbedding, "model": "all-MiniLM-L6-v2", "dims": 384},
    "local-multilingual": {"class": LocalEmbedding, "model": "intfloat/multilingual-e5-large", "dims": 1024},
}


def create_embedding_provider(config: dict[str, Any]) -> EmbeddingProvider | None:
    """Create an embedding provider from plugin config.

    Config keys:
        embedding_provider: "gemini" | "openai" | "local" | "none"
        embedding_model: model name (overrides default)
        embedding_dims: dimensions (overrides default)
        embedding_api_key: explicit API key
        embedding_base_url: for OpenAI-compatible APIs
        embedding_device: for local models ("cpu", "cuda", "mps")

    Returns None if provider is "none" or unavailable.
    """
    provider_name = config.get("embedding_provider", "gemini").lower().strip()

    if provider_name == "none" or provider_name == "disabled":
        logger.info("Semantic search disabled by config")
        return None

    defaults = PROVIDER_DEFAULTS.get(provider_name, {})
    provider_class = defaults.get("class")
    default_model = defaults.get("model", "")
    default_dims = defaults.get("dims", 384)

    model = config.get("embedding_model", default_model)
    dims = int(config.get("embedding_dims", default_dims))
    api_key = config.get("embedding_api_key")

    if provider_name in ("gemini",):
        return GeminiEmbedding(model=model, dimensions=dims, api_key=api_key)

    elif provider_name in ("openai", "openai-large"):
        base_url = config.get("embedding_base_url")
        return OpenAIEmbedding(
            model=model, dimensions=dims,
            api_key=api_key, base_url=base_url,
        )

    elif provider_name in ("local", "local-multilingual"):
        device = config.get("embedding_device", "cpu")
        return LocalEmbedding(model=model, dimensions=dims, device=device)

    else:
        # Try to treat as a known provider anyway
        logger.warning("Unknown embedding provider '%s', trying as local", provider_name)
        device = config.get("embedding_device", "cpu")
        return LocalEmbedding(model=provider_name, dimensions=dims, device=device)
