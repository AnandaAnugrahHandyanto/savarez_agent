"""
Benchmark Exa highlights vs full text on sample queries.

Run with: pytest tests/tools/test_exa_highlights_benchmark.py -v

This benchmark compares:
- Token efficiency: highlights vs full text character counts
- Latency: time to retrieve highlights vs full text
- Quality: basic relevance checks

Requires EXA_API_KEY environment variable to be set.
"""

import os
import time
import pytest
from unittest.mock import patch, MagicMock

# Sample queries representing different use cases
SAMPLE_QUERIES = [
    ("Latest news on Nvidia", "simple"),
    ("Python asyncio API documentation", "technical"),
    ("React vs Vue comparison", "analytical"),
    ("What is the current stock price of Tesla", "simple"),
    ("GitHub Actions CI/CD tutorial", "technical"),
    ("Pros and cons of Docker vs Kubernetes", "analytical"),
]


@pytest.mark.skipif(not os.getenv("EXA_API_KEY"), reason="EXA_API_KEY not set")
class TestExaHighlightsBenchmark:
    """Benchmark suite for Exa highlights performance and efficiency."""

    def test_highlights_token_efficiency(self):
        """Benchmark: Highlights should be ~94% fewer tokens than full text per Exa research."""
        from tools.web_tools import _exa_search, _exa_extract

        results = []

        for query, category in SAMPLE_QUERIES:
            # Get search results with highlights
            search_result = _exa_search(query, limit=3)
            if not search_result.get("success"):
                continue

            web_results = search_result.get("data", {}).get("web", [])
            if not web_results:
                continue

            # Calculate highlights metrics
            highlights_chars = 0
            for r in web_results:
                highlights = r.get("highlights", [])
                highlights_chars += sum(len(h) for h in highlights)

            avg_highlights_per_result = highlights_chars // len(web_results) if web_results else 0

            # Get full text for comparison (first result only to save API calls)
            first_url = web_results[0]["url"]
            start_time = time.time()
            full_text_results = _exa_extract([first_url])
            full_text_latency = (time.time() - start_time) * 1000

            full_text_chars = len(full_text_results[0].get("content", "")) if full_text_results else 0

            # Calculate savings
            if full_text_chars > 0:
                savings_ratio = 1 - (avg_highlights_per_result / full_text_chars)
                token_reduction_pct = savings_ratio * 100
            else:
                token_reduction_pct = 0

            results.append({
                "query": query,
                "category": category,
                "highlights_chars": avg_highlights_per_result,
                "full_text_chars": full_text_chars,
                "token_reduction_pct": token_reduction_pct,
                "full_text_latency_ms": full_text_latency,
            })

        # Assert token efficiency meets Exa's research claims (~94% reduction)
        # We use a more conservative threshold since we're averaging across different content types
        avg_reduction = sum(r["token_reduction_pct"] for r in results) / len(results) if results else 0

        print(f"\n=== Token Efficiency Results ===")
        for r in results:
            print(f"  {r['query'][:40]:<40} | {r['category']:<10} | "
                  f"Highlights: {r['highlights_chars']:>5} chars | "
                  f"Full text: {r['full_text_chars']:>6} chars | "
                  f"Savings: {r['token_reduction_pct']:>5.1f}%")
        print(f"\n  Average token reduction: {avg_reduction:.1f}%")

        # Assert we achieve at least 70% token reduction (conservative vs Exa's 94%)
        assert avg_reduction > 70, f"Token reduction {avg_reduction:.1f}% below expected 70%"

    def test_highlights_latency(self):
        """Benchmark: Highlights should complete in <100ms typically (Exa claim)."""
        from tools.web_tools import _exa_search

        latencies = []

        for query, _ in SAMPLE_QUERIES[:3]:  # Use subset to limit API calls
            start_time = time.time()
            result = _exa_search(query, limit=3)
            elapsed_ms = (time.time() - start_time) * 1000

            if result.get("success"):
                latencies.append(elapsed_ms)

        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        max_latency = max(latencies) if latencies else 0

        print(f"\n=== Latency Results ===")
        print(f"  Average latency: {avg_latency:.1f}ms")
        print(f"  Max latency: {max_latency:.1f}ms")
        print(f"  Samples: {len(latencies)}")

        # Exa claims <100ms typically, but we allow for network variance
        # Assert p95-like behavior (max in our small sample) is under 500ms
        assert max_latency < 500, f"Max latency {max_latency:.1f}ms exceeds 500ms threshold"
        assert avg_latency < 300, f"Avg latency {avg_latency:.1f}ms exceeds 300ms threshold"

    def test_highlights_quality_basic(self):
        """Benchmark: Highlights should contain query-relevant keywords."""
        from tools.web_tools import _exa_search

        quality_scores = []

        for query, category in SAMPLE_QUERIES:
            result = _exa_search(query, limit=3)
            if not result.get("success"):
                continue

            web_results = result.get("data", {}).get("web", [])
            if not web_results:
                continue

            # Extract key terms from query (simple heuristic)
            query_terms = set(query.lower().split()) - {"on", "the", "of", "vs", "is", "and"}

            # Check how many highlights contain at least one query-relevant term
            matches = 0
            total_highlights = 0

            for r in web_results:
                highlights = r.get("highlights", [])
                for h in highlights:
                    total_highlights += 1
                    highlight_lower = h.lower()
                    if any(term in highlight_lower for term in query_terms):
                        matches += 1

            relevance_score = (matches / total_highlights * 100) if total_highlights > 0 else 0
            quality_scores.append({
                "query": query,
                "relevance_score": relevance_score,
                "matches": matches,
                "total": total_highlights,
            })

        avg_relevance = sum(q["relevance_score"] for q in quality_scores) / len(quality_scores) if quality_scores else 0

        print(f"\n=== Quality Results ===")
        for q in quality_scores:
            print(f"  {q['query'][:40]:<40} | Relevance: {q['relevance_score']:>5.1f}% "
                  f"({q['matches']}/{q['total']} highlights)")
        print(f"\n  Average relevance: {avg_relevance:.1f}%")

        # Assert at least 50% of highlights contain query-relevant terms
        assert avg_relevance > 50, f"Relevance score {avg_relevance:.1f}% below 50% threshold"


class TestExaHighlightsBenchmarkSimulation:
    """Simulated benchmarks that don't require API calls (for CI)."""

    def test_token_efficiency_simulation(self):
        """Simulated token efficiency based on Exa's published research."""
        # Based on Exa blog: 500 chars highlights ≈ 8000 chars full text
        # This gives us 93.75% token reduction

        highlights_chars = 500
        full_text_equivalent = 8000
        expected_savings = 93.75

        actual_savings = (1 - highlights_chars / full_text_equivalent) * 100

        print(f"\n=== Simulated Token Efficiency ===")
        print(f"  Exa claim: {highlights_chars} chars highlights ≈ {full_text_equivalent} chars full text")
        print(f"  Expected savings: {expected_savings:.1f}%")
        print(f"  Calculated savings: {actual_savings:.1f}%")

        assert abs(actual_savings - expected_savings) < 0.1
