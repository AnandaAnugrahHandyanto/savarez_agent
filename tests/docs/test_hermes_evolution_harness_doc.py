"""Tests for the Hermes evolution harness benchmark doc."""

from pathlib import Path


def test_hermes_evolution_harness_doc_exists_and_is_specific():
    doc = Path("docs/boblab/hermes-evolution-harness.md")
    assert doc.exists(), "Expected the Hermes evolution harness doc to exist"

    content = doc.read_text()

    # Core project linkage
    assert "ADR-110" in content
    assert "BobLab" in content
    assert "Linear" in content

    # AutoAgent-style benchmark loop
    assert "keep/refine/discard" in content
    assert "benchmark" in content.lower()
    assert "implementation loop" in content.lower()

    # First concrete example from prior conversations
    assert "Reddit ingestion playbook" in content
    assert "duplicate-first preflight" in content
    assert "canonical target" in content
    assert "20260419_120319_12b8cd7c" in content
    assert "20260421_094459_f74e73fa" in content

    # Verification guidance
    assert "pytest tests/docs/test_hermes_evolution_harness_doc.py -q" in content
    assert "git diff --check" in content


def test_reddit_ingestion_benchmark_reference_exists_and_is_grounded():
    ref = Path.home() / ".hermes" / "skills" / "operational" / "hermes-evolution-harness" / "references" / "reddit-ingestion-benchmark.md"
    assert ref.exists(), "Expected the Reddit ingestion benchmark reference to exist"

    content = ref.read_text()
    assert "Reddit Ingestion Benchmark" in content
    assert "duplicate-first preflight" in content
    assert "canonical target" in content
    assert "Score / keep-discard rubric" in content
    assert "session reference" in content.lower()
