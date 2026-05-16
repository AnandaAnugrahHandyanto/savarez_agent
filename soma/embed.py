"""Ollama embedding client + cosine similarity.

Soma uses local Ollama embeddings (nomic-embed-text by default) so the
memory pool can detect semantic duplicates across languages without a
cloud round-trip. ~100 ms per call on CPU.

The embedder is sync; call it from an asyncio context via
asyncio.to_thread().
"""

from __future__ import annotations

import math
import os
from typing import Sequence

import requests


DEFAULT_URL = os.environ.get("SOMA_OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("SOMA_EMBED_MODEL", "nomic-embed-text")


class EmbeddingError(RuntimeError):
    """Raised when Ollama returns no usable embedding."""


class OllamaEmbedder:
    """Single-purpose Ollama embedding client.

    Talks to /api/embeddings. The store calls this once per write and
    once per query — no batching needed at our memory scale (<150).
    """

    def __init__(
        self,
        *,
        url: str = DEFAULT_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = 30.0,
    ):
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def embed(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise EmbeddingError("cannot embed empty text")
        resp = requests.post(
            f"{self.url}/api/embeddings",
            json={"model": self.model, "prompt": text},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        vec = data.get("embedding") or []
        if not vec:
            raise EmbeddingError(f"ollama returned no embedding: {data!r}")
        return [float(x) for x in vec]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity in [-1.0, 1.0]. Returns 0.0 on length mismatch or zero vector."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))
