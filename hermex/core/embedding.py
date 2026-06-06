from __future__ import annotations

import hashlib
import math
import re

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_./:-]+")
_DIMENSIONS = 64


def embed_text(text: str) -> list[float]:
    """Return a deterministic small embedding suitable for local MVP search."""
    vector = [0.0] * _DIMENSIONS
    for token in _TOKEN_RE.findall(text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % _DIMENSIONS
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))
