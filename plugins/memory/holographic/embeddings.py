"""Optional embedding providers for holographic memory understanding."""

from __future__ import annotations

from array import array
import logging
import math
import os
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


def vector_to_bytes(values: Iterable[float]) -> bytes:
    payload = array("f", [float(value) for value in values])
    return payload.tobytes()


def bytes_to_vector(data: bytes | None) -> list[float]:
    if not data:
        return []
    payload = array("f")
    payload.frombytes(data)
    return list(payload)


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    left_values = list(left)
    right_values = list(right)
    if not left_values or not right_values or len(left_values) != len(right_values):
        return 0.0

    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for left_value, right_value in zip(left_values, right_values):
        dot += left_value * right_value
        left_norm += left_value * left_value
        right_norm += right_value * right_value

    if left_norm <= 0.0 or right_norm <= 0.0:
        return 0.0

    return dot / (math.sqrt(left_norm) * math.sqrt(right_norm))


class EmbeddingProvider:
    name = "none"

    def is_available(self) -> bool:
        return False

    def embed_many(self, texts: list[str]) -> list[Optional[list[float]]]:
        return [None for _ in texts]

    def embed_one(self, text: str) -> Optional[list[float]]:
        return self.embed_many([text])[0]


class NoopEmbeddingProvider(EmbeddingProvider):
    name = "none"


class OpenAIEmbeddingProvider(EmbeddingProvider):
    name = "openai"

    def __init__(
        self,
        *,
        model: str = "text-embedding-3-small",
        api_key: str = "",
        base_url: str = "",
        dimensions: int | None = None,
        timeout: float = 8.0,
    ) -> None:
        self.model = model
        self.api_key = (
            api_key
            or os.environ.get("HOLOGRAPHIC_OPENAI_API_KEY", "")
            or os.environ.get("OPENAI_API_KEY", "")
        )
        self.base_url = (
            base_url
            or os.environ.get("HOLOGRAPHIC_OPENAI_BASE_URL", "")
            or os.environ.get("OPENAI_BASE_URL", "")
        )
        self.dimensions = dimensions
        self.timeout = timeout
        self._client = None

    def is_available(self) -> bool:
        if not self.model:
            return False
        if not (self.api_key or self.base_url):
            return False
        try:
            from openai import OpenAI  # noqa: F401
        except Exception:
            return False
        return True

    def _get_client(self):
        if self._client is not None:
            return self._client

        from openai import OpenAI

        kwargs = {"timeout": self.timeout}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = OpenAI(**kwargs)
        return self._client

    def embed_many(self, texts: list[str]) -> list[Optional[list[float]]]:
        if not texts or not self.is_available():
            return [None for _ in texts]

        try:
            client = self._get_client()
            kwargs = {
                "model": self.model,
                "input": texts,
            }
            if self.dimensions and self.model.startswith("text-embedding-3"):
                kwargs["dimensions"] = self.dimensions
            response = client.embeddings.create(**kwargs)
            return [list(item.embedding) for item in response.data]
        except Exception as exc:
            logger.debug("OpenAI embedding request failed: %s", exc)
            return [None for _ in texts]


def build_embedding_provider(config: dict | None = None) -> EmbeddingProvider:
    cfg = config or {}
    provider_name = (cfg.get("semantic_provider") or cfg.get("embedding_provider") or "none").strip().lower()
    if provider_name == "openai":
        dimensions = cfg.get("semantic_dimensions")
        return OpenAIEmbeddingProvider(
            model=str(cfg.get("semantic_model") or "text-embedding-3-small"),
            api_key=str(cfg.get("semantic_api_key") or ""),
            base_url=str(cfg.get("semantic_base_url") or ""),
            dimensions=int(dimensions) if dimensions not in (None, "", "0") else None,
            timeout=float(cfg.get("semantic_timeout_seconds", 8.0)),
        )
    return NoopEmbeddingProvider()
