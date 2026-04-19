import hashlib
import math
import re
from collections import Counter

from .config import get_settings

settings = get_settings()


class EmbeddingService:
    def __init__(self) -> None:
        self.dim = settings.embedding_dim

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[a-zA-Z0-9_\-]{2,}", text.lower())

    def embed(self, text: str) -> list[float]:
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * self.dim

        counter = Counter(tokens)
        vec = [0.0] * self.dim
        total = sum(counter.values())

        for token, count in counter.items():
            h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dim
            sign = -1.0 if (h >> 1) & 1 else 1.0
            vec[idx] += sign * (count / total)

        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0:
            return vec
        return [v / norm for v in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
