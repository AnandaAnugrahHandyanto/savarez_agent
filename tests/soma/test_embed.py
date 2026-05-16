"""Tests for soma.embed — cosine math and Ollama client (mocked)."""

from __future__ import annotations

import math
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from soma.embed import EmbeddingError, OllamaEmbedder, cosine_similarity


class CosineSimilarityTest(unittest.TestCase):
    def test_identical_vectors(self):
        self.assertAlmostEqual(cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]), 1.0)

    def test_opposite_vectors(self):
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [-1.0, 0.0]), -1.0)

    def test_orthogonal_vectors(self):
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)

    def test_length_mismatch_returns_zero(self):
        self.assertEqual(cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0]), 0.0)

    def test_empty_returns_zero(self):
        self.assertEqual(cosine_similarity([], [1.0]), 0.0)
        self.assertEqual(cosine_similarity([0.0, 0.0], [1.0, 1.0]), 0.0)

    def test_known_angle(self):
        # 45° between vectors → cos(45°) = √2/2 ≈ 0.7071
        self.assertAlmostEqual(
            cosine_similarity([1.0, 0.0], [1.0, 1.0]),
            math.sqrt(2) / 2,
            places=6,
        )


class OllamaEmbedderTest(unittest.TestCase):
    def test_posts_correct_payload(self):
        embedder = OllamaEmbedder(url="http://example:11434", model="nomic-embed-text")
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
        fake_resp.raise_for_status.return_value = None

        with patch("soma.embed.requests.post", return_value=fake_resp) as post:
            vec = embedder.embed("hello world")

        self.assertEqual(vec, [0.1, 0.2, 0.3])
        post.assert_called_once()
        url, = post.call_args.args
        self.assertEqual(url, "http://example:11434/api/embeddings")
        self.assertEqual(
            post.call_args.kwargs["json"],
            {"model": "nomic-embed-text", "prompt": "hello world"},
        )

    def test_empty_text_raises(self):
        embedder = OllamaEmbedder()
        with self.assertRaises(EmbeddingError):
            embedder.embed("")
        with self.assertRaises(EmbeddingError):
            embedder.embed("   ")

    def test_missing_embedding_raises(self):
        embedder = OllamaEmbedder()
        fake_resp = MagicMock()
        fake_resp.json.return_value = {}
        fake_resp.raise_for_status.return_value = None
        with patch("soma.embed.requests.post", return_value=fake_resp):
            with self.assertRaises(EmbeddingError):
                embedder.embed("text")


if __name__ == "__main__":
    unittest.main()
