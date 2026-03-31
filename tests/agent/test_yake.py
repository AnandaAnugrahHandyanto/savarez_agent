"""Tests for YAKE keyword extraction — ported from HiveMind Rust."""

import sys
import os

# Ensure the agent module is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agent.yake import extract_keywords, STOPWORDS


SAMPLE_TEXT = """
Machine learning is a subset of artificial intelligence that focuses on building
systems that learn from data. Deep learning, a specialized form of machine learning,
uses neural networks with many layers. Natural language processing enables computers
to understand human language. Computer vision allows machines to interpret visual data.
Reinforcement learning trains agents through reward signals in an environment.
"""


def test_basic_extraction_returns_keywords():
    """extract_keywords should return a non-empty list of strings."""
    result = extract_keywords(SAMPLE_TEXT)
    assert isinstance(result, list)
    assert len(result) > 0
    assert all(isinstance(kw, str) for kw in result)


def test_stopwords_are_filtered():
    """No keyword should be a bare stopword."""
    result = extract_keywords(SAMPLE_TEXT)
    for kw in result:
        # Single-word keywords must not be stopwords
        if " " not in kw:
            assert kw not in STOPWORDS, f"Stopword '{kw}' should not appear as keyword"


def test_empty_input():
    """Empty or whitespace-only input returns empty list."""
    assert extract_keywords("") == []
    assert extract_keywords("   ") == []
    assert extract_keywords("\n\n") == []


def test_short_input():
    """Very short input with only stopwords returns empty list."""
    assert extract_keywords("the a an") == []
    # Single meaningful word should still work
    result = extract_keywords("Python Python Python programming programming")
    assert len(result) >= 1


def test_ngram_extraction():
    """Multi-word keyphrases (bigrams/trigrams) should appear when text supports them."""
    text = (
        "machine learning is transforming natural language processing. "
        "machine learning models improve natural language processing tasks. "
        "deep machine learning networks advance natural language processing research."
    )
    result = extract_keywords(text)
    # Should have at least one multi-word phrase
    multi_word = [kw for kw in result if " " in kw]
    assert len(multi_word) > 0, f"Expected multi-word keyphrases, got: {result}"


def test_dedup_substring_removal():
    """If 'machine learning' is selected, 'machine' alone should be deduplicated out."""
    text = (
        "machine learning is powerful. machine learning advances science. "
        "machine learning drives innovation. machine learning solves problems. "
        "machine learning enables automation."
    )
    result = extract_keywords(text)
    # Should not have both 'machine' and 'machine learning'
    for i, kw1 in enumerate(result):
        for j, kw2 in enumerate(result):
            if i != j:
                assert kw1 not in kw2 and kw2 not in kw1, (
                    f"Redundant pair: '{kw1}' and '{kw2}'"
                )


def test_returns_max_8():
    """Should never return more than 8 keywords."""
    long_text = " ".join(
        f"topic{i} concept{i} idea{i} theory{i}." for i in range(50)
    )
    result = extract_keywords(long_text)
    assert len(result) <= 8


def test_numeric_only_filtered():
    """Pure numeric tokens should not appear as keywords."""
    text = "In 2024 the 500 researchers published 100 papers on quantum computing."
    result = extract_keywords(text)
    for kw in result:
        for word in kw.split():
            assert not word.isdigit(), f"Numeric token '{word}' in keyword '{kw}'"
