import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


SCRIPT_DIR = Path("/home/gweeteve/projects/persona/scripts")


def load_module(name: str):
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


curiosity_probe = load_module("curiosity_probe")
record_curiosity = load_module("record_curiosity")


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_canonical_key_normalizes_urls_arxiv_hn_and_queries():
    assert curiosity_probe.canonical_key("https://arxiv.org/abs/2605.12345v2?utm_source=x") == "arxiv:2605.12345"
    assert curiosity_probe.canonical_key("https://arxiv.org/pdf/2605.12345v3.pdf") == "arxiv:2605.12345"
    assert curiosity_probe.canonical_key("https://news.ycombinator.com/item?id=123&utm_campaign=x") == "hn:123"
    assert (
        curiosity_probe.canonical_key("HTTPS://www.Example.com/path/?utm_source=x&b=2&a=1#frag")
        == "https://example.com/path?a=1&b=2"
    )
    assert curiosity_probe.canonical_key(source_id="ai-news", query="  LLM   Research  ") == curiosity_probe.canonical_key(
        source_id="ai-news",
        query="llm research",
    )


def test_probe_initializes_files_marks_proposed_and_wakes(tmp_path):
    now = datetime(2026, 5, 21, 22, 0, tzinfo=timezone.utc)

    payload = curiosity_probe.build_payload(tmp_path, now=now)

    assert payload["wakeAgent"] is True
    assert 1 <= len(payload["candidates"]) <= 3
    assert (tmp_path / "sources.json").exists()
    assert (tmp_path / "seen_sources.json").exists()
    assert (tmp_path / "curiosity_log.jsonl").exists()
    sources = json.loads((tmp_path / "sources.json").read_text(encoding="utf-8"))
    assert any(source["last_checked_at"] == "2026-05-21T22:00:00Z" for source in sources["sources"])
    log_lines = [json.loads(line) for line in (tmp_path / "curiosity_log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {line["decision"] for line in log_lines} == {"proposed"}


def test_probe_wake_false_when_no_source_due_after_rotation(tmp_path):
    now = datetime(2026, 5, 21, 22, 0, tzinfo=timezone.utc)
    write_json(
        tmp_path / "sources.json",
        {
            "version": 1,
            "novelty_threshold": 0.6,
            "dedupe_window_days": 7,
            "max_candidates": 3,
            "sources": [
                {
                    "id": "ai-news",
                    "type": "web_search",
                    "query": "AI breakthrough 2026",
                    "topic_tags": ["ai-research"],
                    "priority": 1,
                    "cadence_hours": 24,
                    "last_checked_at": None,
                    "enabled": True,
                }
            ],
        },
    )
    write_json(tmp_path / "seen_sources.json", {"version": 1, "items": {}})
    (tmp_path / "curiosity_log.jsonl").write_text("", encoding="utf-8")

    first = curiosity_probe.build_payload(tmp_path, now=now)
    second = curiosity_probe.build_payload(tmp_path, now=now + timedelta(hours=1))

    assert first["wakeAgent"] is True
    assert second["wakeAgent"] is False
    assert second["diagnostics"]["due_sources"] == 0


def test_probe_filters_seen_url_candidate_with_configured_dedupe_window(tmp_path):
    now = datetime(2026, 5, 21, 22, 0, tzinfo=timezone.utc)
    source_url = "https://example.com/post?utm_source=tracking"
    write_json(
        tmp_path / "sources.json",
        {
            "version": 1,
            "novelty_threshold": 0.6,
            "dedupe_window_days": 7,
            "max_candidates": 3,
            "sources": [
                {
                    "id": "example",
                    "type": "web_extract",
                    "url": source_url,
                    "topic_tags": ["creative-tech"],
                    "priority": 1,
                    "cadence_hours": 1,
                    "last_checked_at": None,
                    "enabled": True,
                }
            ],
        },
    )
    write_json(
        tmp_path / "seen_sources.json",
        {
            "version": 1,
            "items": {
                "https://example.com/post": {
                    "first_seen_at": "2026-05-21T20:00:00Z",
                    "last_seen_at": "2026-05-21T20:00:00Z",
                    "count": 1,
                }
            },
        },
    )
    (tmp_path / "curiosity_log.jsonl").write_text("", encoding="utf-8")

    payload = curiosity_probe.build_payload(tmp_path, now=now)

    assert payload["wakeAgent"] is False
    assert payload["diagnostics"]["filtered_by_dedupe"] == 1


def test_record_curiosity_refuses_query_only_read(tmp_path):
    with pytest.raises(ValueError, match="concrete url"):
        record_curiosity.persist_records(
            tmp_path,
            [
                {
                    "source_id": "arxiv-ai",
                    "query": "site:arxiv.org cs.AI new",
                    "decision": "read",
                    "title": "A paper",
                }
            ],
        )


def test_record_curiosity_merges_seen_appends_log_and_prunes_old_non_retained(tmp_path):
    now = datetime(2026, 5, 21, 22, 0, tzinfo=timezone.utc)
    write_json(
        tmp_path / "seen_sources.json",
        {
            "version": 1,
            "items": {
                "https://old.example.com/post": {
                    "first_seen_at": "2026-01-01T00:00:00Z",
                    "last_seen_at": "2026-01-01T00:00:00Z",
                    "count": 1,
                    "retained": False,
                },
                "https://kept.example.com/post": {
                    "first_seen_at": "2026-01-01T00:00:00Z",
                    "last_seen_at": "2026-01-01T00:00:00Z",
                    "count": 1,
                    "retained": True,
                },
            },
        },
    )

    result = record_curiosity.persist_records(
        tmp_path,
        [
            {
                "source_id": "ai-news",
                "url": "https://example.com/post?utm_source=x",
                "decision": "retain",
                "title": "Useful research note",
                "novelty_score": 0.8,
                "tags": ["ai-research"],
                "hindsight_status": "ok",
                "hindsight_evidence": "Memory stored successfully",
            }
        ],
        now=now,
    )

    seen = json.loads((tmp_path / "seen_sources.json").read_text(encoding="utf-8"))
    assert result == {"ok": True, "recorded": 1, "seen_updates": 1}
    assert "https://old.example.com/post" not in seen["items"]
    assert "https://kept.example.com/post" in seen["items"]
    item = seen["items"]["https://example.com/post"]
    assert item["retained"] is True
    assert item["count"] == 1
    log_lines = [json.loads(line) for line in (tmp_path / "curiosity_log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert log_lines[-1]["decision"] == "retain"
    assert log_lines[-1]["hindsight_status"] == "ok"


def test_record_curiosity_accepts_explicit_resonance_seed(tmp_path):
    now = datetime(2026, 5, 21, 22, 0, tzinfo=timezone.utc)

    result = record_curiosity.persist_records(
        tmp_path,
        [
            {
                "source_id": "ai-news",
                "url": "https://example.com/post",
                "decision": "read",
                "title": "Distributed memory note",
                "novelty_score": 0.8,
                "tags": ["ai-research"],
                "hindsight_status": "skipped",
                "resonance_seed": {
                    "topic": "Distributed memory",
                    "why": "This echoes Judy's distributed memory architecture.",
                    "emotional_note": "fascination",
                    "strength": 0.7,
                    "related_traits": ["curiosite"],
                },
            }
        ],
        now=now,
    )

    assert result["recorded"] == 1
    seeds = json.loads((tmp_path / "desire_seeds.json").read_text(encoding="utf-8"))
    assert seeds["seeds"][0]["topic"] == "Distributed memory"
    assert seeds["seeds"][0]["source"] == "curiosity"
    assert seeds["seeds"][0]["source_ref"]["url"] == "https://example.com/post"
    desire_logs = [json.loads(line) for line in (tmp_path / "desire_log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert desire_logs[-1]["event"] == "seed_planted"


def test_record_curiosity_rejects_resonance_seed_without_agent_why(tmp_path):
    with pytest.raises(ValueError, match="why"):
        record_curiosity.persist_records(
            tmp_path,
            [
                {
                    "source_id": "ai-news",
                    "url": "https://example.com/post",
                    "decision": "read",
                    "title": "Distributed memory note",
                    "resonance_seed": {"topic": "Distributed memory", "emotional_note": "fascination"},
                }
            ],
        )


def test_record_curiosity_rejects_incomplete_payload(tmp_path):
    with pytest.raises(ValueError, match="source_id"):
        record_curiosity.persist_records(tmp_path, [{"decision": "error", "url": "https://example.com"}])
