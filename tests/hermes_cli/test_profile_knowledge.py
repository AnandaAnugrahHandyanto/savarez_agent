"""Tests for the per-specialist knowledge corpus module.

Three layers:

1. Schema layer — validate_corpus_entry / validate_gate_entry on dict
   fixtures, no filesystem.
2. IO + ingest layer — tmp_path-backed corpus directories; verify
   append, idempotency, query, status updates, index rebuild.
3. CLI layer — exit codes and JSON payloads through the ``main`` entry
   point with ``_profiles_root`` monkeypatched to ``tmp_path``.

The ``knowledge_corpus_matrix`` is exercised both directly and through
the CLI.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli import profile_knowledge as pk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def profiles_root(tmp_path: Path) -> Path:
    root = tmp_path / "profiles"
    root.mkdir()
    return root


def _make_profile(root: Path, name: str) -> Path:
    pdir = root / name
    pdir.mkdir()
    return pdir


def _good_entry(specialist: str = "gond") -> dict:
    return {
        "id": "deadbeef" * 4,
        "ingested_at": "2026-05-29T12:00:00Z",
        "specialist": specialist,
        "title": "sample entry",
        "source_type": "local_artifact",
        "tags": ["domain:engineering", "type:audit"],
        "confidence": pk.CONFIDENCE_VERIFIED,
        "status": pk.STATUS_ACTIVE,
        "provenance": {"ingested_by": "test", "ingest_version": 1},
    }


def _good_gate(specialist: str = "waukeen") -> dict:
    return {
        "id": "facefeed" * 4,
        "ingested_at": "2026-05-29T12:00:00Z",
        "specialist": specialist,
        "url": "https://example.com/paywalled",
        "title": "paywalled article",
        "gate_kind": "paywall",
        "tags": ["domain:finance"],
        "confidence": pk.CONFIDENCE_GATED_UNREAD,
        "status": pk.STATUS_ACTIVE,
        "provenance": {"ingested_by": "test", "ingest_version": 1},
    }


# ---------------------------------------------------------------------------
# Schema layer
# ---------------------------------------------------------------------------


def test_validate_corpus_entry_accepts_good_entry():
    assert pk.validate_corpus_entry(_good_entry()) == []


def test_validate_corpus_entry_reports_missing_keys():
    errs = pk.validate_corpus_entry({"id": "x", "specialist": "gond"})
    msg = "\n".join(errs)
    for key in (
        "ingested_at",
        "title",
        "source_type",
        "tags",
        "confidence",
        "status",
        "provenance",
    ):
        assert f"{key}: missing" in msg, key


def test_validate_corpus_entry_rejects_bad_confidence():
    entry = _good_entry()
    entry["confidence"] = "rumor"
    errs = pk.validate_corpus_entry(entry)
    assert any("confidence:" in e for e in errs)


def test_validate_corpus_entry_rejects_gated_unread_confidence():
    # gated_unread belongs in gates.jsonl, not corpus.jsonl.
    entry = _good_entry()
    entry["confidence"] = pk.CONFIDENCE_GATED_UNREAD
    errs = pk.validate_corpus_entry(entry)
    assert any("gated_unread" in e for e in errs)


def test_validate_corpus_entry_rejects_bad_status():
    entry = _good_entry()
    entry["status"] = "weird"
    errs = pk.validate_corpus_entry(entry)
    assert any("status:" in e for e in errs)


def test_validate_corpus_entry_rejects_non_string_tags():
    entry = _good_entry()
    entry["tags"] = ["good", 5, ""]
    errs = pk.validate_corpus_entry(entry)
    assert any("tags:" in e for e in errs)


def test_validate_gate_entry_accepts_good_gate():
    assert pk.validate_gate_entry(_good_gate()) == []


def test_validate_gate_entry_requires_gated_unread():
    gate = _good_gate()
    gate["confidence"] = pk.CONFIDENCE_VERIFIED
    errs = pk.validate_gate_entry(gate)
    assert any("gated_unread" in e for e in errs)


def test_validate_gate_entry_rejects_bad_gate_kind():
    gate = _good_gate()
    gate["gate_kind"] = "made_up"
    errs = pk.validate_gate_entry(gate)
    assert any("gate_kind:" in e for e in errs)


# ---------------------------------------------------------------------------
# Ingest — local artifact
# ---------------------------------------------------------------------------


def test_ingest_local_artifact_creates_entry_and_writes_files(profiles_root: Path, tmp_path: Path):
    pdir = _make_profile(profiles_root, "gond")
    art = tmp_path / "evidence.txt"
    art.write_text("hello evidence", encoding="utf-8")
    entry = pk.ingest_local_artifact(pdir, art, tags=["domain:engineering", "type:demo"])
    assert pk.corpus_path(pdir).is_file()
    assert pk.index_path(pdir).is_file()
    assert entry["confidence"] == pk.CONFIDENCE_VERIFIED
    assert entry["source_sha256"]
    assert entry["source_path"] == str(art.resolve())
    assert entry["tags"] == ["domain:engineering", "type:demo"]
    rows = pk.read_entries(pdir)
    assert len(rows) == 1
    assert rows[0]["id"] == entry["id"]


def test_ingest_local_artifact_is_idempotent_for_same_file(profiles_root: Path, tmp_path: Path):
    pdir = _make_profile(profiles_root, "gond")
    art = tmp_path / "evidence.txt"
    art.write_text("hello evidence", encoding="utf-8")
    e1 = pk.ingest_local_artifact(pdir, art, tags=["type:demo"])
    e2 = pk.ingest_local_artifact(pdir, art, tags=["type:demo"])
    assert e1["id"] == e2["id"]
    assert len(pk.read_entries(pdir)) == 1


def test_ingest_local_artifact_raises_for_missing_file(profiles_root: Path, tmp_path: Path):
    pdir = _make_profile(profiles_root, "gond")
    with pytest.raises(FileNotFoundError):
        pk.ingest_local_artifact(pdir, tmp_path / "nope.txt")


def test_ingest_notion_intake_artifact_records_provenance_and_is_idempotent(
    profiles_root: Path, tmp_path: Path
):
    pdir = _make_profile(profiles_root, "gond")
    art = tmp_path / "notion-abc123-closure.md"
    art.write_text("CLOSE_READY=yes\nsource finding\n", encoding="utf-8")
    item = {
        "id": "notion-abc123",
        "url": "https://notion.local/abc123",
        "title": "[Gond] Vytěžit zdroj",
        "priority": "2",
        "context": "Počítač",
        "last_edited_time": "2026-05-29T10:00:00Z",
    }
    e1 = pk.ingest_notion_intake_artifact(
        pdir,
        art,
        notion_item=item,
        artifact_kind="source_spike_closure",
        tags=["domain:engineering"],
        evidence_excerpt="CLOSE_READY=yes",
    )
    e2 = pk.ingest_notion_intake_artifact(
        pdir,
        art,
        notion_item=item,
        artifact_kind="source_spike_closure",
        tags=["domain:engineering"],
    )
    assert e1["id"] == e2["id"]
    assert len(pk.read_entries(pdir)) == 1
    assert e1["source_type"] == "notion_intake_artifact"
    assert e1["confidence"] == pk.CONFIDENCE_VERIFIED
    assert "type:notion_intake_artifact" in e1["tags"]
    assert "artifact_kind:source_spike_closure" in e1["tags"]
    assert "notion_id:notion-abc123" in e1["tags"]
    assert e1["provenance"]["notion_id"] == "notion-abc123"
    assert e1["provenance"]["notion_url"] == "https://notion.local/abc123"
    assert e1["provenance"]["verified_local_artifact"] is True
    assert e1["source_sha256"]


def test_ingest_notion_intake_artifact_rejects_missing_artifact(profiles_root: Path, tmp_path: Path):
    pdir = _make_profile(profiles_root, "gond")
    with pytest.raises(FileNotFoundError):
        pk.ingest_notion_intake_artifact(
            pdir,
            tmp_path / "missing.md",
            notion_item={"id": "n-missing", "title": "[Gond] missing"},
        )


def test_ingest_local_artifact_rejects_gated_unread_confidence(profiles_root: Path, tmp_path: Path):
    pdir = _make_profile(profiles_root, "gond")
    art = tmp_path / "evidence.txt"
    art.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError):
        pk.ingest_local_artifact(pdir, art, confidence=pk.CONFIDENCE_GATED_UNREAD)


# ---------------------------------------------------------------------------
# Ingest — orchestrator audit
# ---------------------------------------------------------------------------


def test_ingest_audit_log_extracts_excerpt(profiles_root: Path, tmp_path: Path):
    pdir = _make_profile(profiles_root, "gond")
    audit = tmp_path / "001.json"
    audit.write_text(
        json.dumps(
            {
                "stamp": "20260529T1416Z",
                "blocked_by_class": {"filip_approval": 5, "ema_review": 5},
                "snapshot_count": 140,
                "snapshot_stale": False,
            }
        ),
        encoding="utf-8",
    )
    entry = pk.ingest_audit_log(pdir, audit, tags=["domain:engineering"])
    assert entry["source_type"] == "orchestrator_audit"
    assert "type:orchestrator_audit" in entry["tags"]
    assert "blocked_total=10" in entry["evidence_excerpt"]
    assert entry["provenance"]["audit_stamp"] == "20260529T1416Z"


def test_ingest_audit_log_rejects_non_json(profiles_root: Path, tmp_path: Path):
    pdir = _make_profile(profiles_root, "gond")
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        pk.ingest_audit_log(pdir, bad)


# ---------------------------------------------------------------------------
# Ingest — gated source
# ---------------------------------------------------------------------------


def test_ingest_gated_source_records_metadata_only(profiles_root: Path):
    pdir = _make_profile(profiles_root, "waukeen")
    entry = pk.ingest_gated_source(
        pdir,
        "https://wsj.com/article/x",
        gate_kind="paywall",
        tags=["domain:finance"],
        notes="WSJ article, paywall observed at 2026-05-29",
    )
    assert entry["confidence"] == pk.CONFIDENCE_GATED_UNREAD
    assert entry["url"] == "https://wsj.com/article/x"
    assert pk.gates_path(pdir).is_file()
    # And corpus.jsonl is NOT populated.
    assert not pk.corpus_path(pdir).is_file() or pk.read_entries(pdir) == []


def test_ingest_gated_source_rejects_bad_gate_kind(profiles_root: Path):
    pdir = _make_profile(profiles_root, "waukeen")
    with pytest.raises(ValueError):
        pk.ingest_gated_source(pdir, "https://x", gate_kind="not_a_kind")


def test_ingest_gated_source_is_idempotent(profiles_root: Path):
    pdir = _make_profile(profiles_root, "waukeen")
    pk.ingest_gated_source(pdir, "https://x.com/a", gate_kind="paywall")
    pk.ingest_gated_source(pdir, "https://x.com/a", gate_kind="paywall")
    assert len(pk.read_gates(pdir)) == 1


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


def test_query_filters_by_tag_status_and_confidence(profiles_root: Path, tmp_path: Path):
    pdir = _make_profile(profiles_root, "gond")
    a = tmp_path / "a.txt"
    a.write_text("a", encoding="utf-8")
    b = tmp_path / "b.txt"
    b.write_text("b", encoding="utf-8")
    pk.ingest_local_artifact(pdir, a, tags=["domain:engineering", "type:audit"])
    pk.ingest_local_artifact(pdir, b, tags=["domain:engineering", "type:plan"])

    audit_rows = pk.query(pdir, tags=["type:audit"])
    assert len(audit_rows) == 1
    assert audit_rows[0]["title"] == "a.txt"

    plan_rows = pk.query(pdir, tags=["type:plan"])
    assert len(plan_rows) == 1
    assert plan_rows[0]["title"] == "b.txt"

    eng_rows = pk.query(pdir, tags=["domain:engineering"])
    assert len(eng_rows) == 2

    verified_rows = pk.query(pdir, confidence=pk.CONFIDENCE_VERIFIED)
    assert len(verified_rows) == 2


def test_query_can_include_gates(profiles_root: Path, tmp_path: Path):
    pdir = _make_profile(profiles_root, "waukeen")
    art = tmp_path / "report.md"
    art.write_text("ok", encoding="utf-8")
    pk.ingest_local_artifact(pdir, art, tags=["domain:finance"])
    pk.ingest_gated_source(
        pdir,
        "https://wsj.com/x",
        gate_kind="paywall",
        tags=["domain:finance"],
    )
    without = pk.query(pdir, tags=["domain:finance"])
    assert len(without) == 1
    with_ = pk.query(pdir, tags=["domain:finance"], include_gates=True)
    assert len(with_) == 2


# ---------------------------------------------------------------------------
# Status update
# ---------------------------------------------------------------------------


def test_update_status_rewrites_entry(profiles_root: Path, tmp_path: Path):
    pdir = _make_profile(profiles_root, "gond")
    art = tmp_path / "old.txt"
    art.write_text("old finding", encoding="utf-8")
    entry = pk.ingest_local_artifact(pdir, art, tags=["domain:engineering"])
    updated = pk.update_status(pdir, entry["id"], pk.STATUS_SUPERSEDED)
    assert updated["status"] == pk.STATUS_SUPERSEDED
    rows = pk.read_entries(pdir)
    assert len(rows) == 1
    assert rows[0]["status"] == pk.STATUS_SUPERSEDED


def test_update_status_raises_for_unknown_id(profiles_root: Path):
    pdir = _make_profile(profiles_root, "gond")
    with pytest.raises(KeyError):
        pk.update_status(pdir, "nope", pk.STATUS_SUPERSEDED)


def test_update_status_rejects_bad_status(profiles_root: Path):
    pdir = _make_profile(profiles_root, "gond")
    with pytest.raises(ValueError):
        pk.update_status(pdir, "any", "weird")


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------


def test_index_is_rebuilt_after_ingest(profiles_root: Path, tmp_path: Path):
    pdir = _make_profile(profiles_root, "gond")
    art = tmp_path / "evidence.txt"
    art.write_text("hello", encoding="utf-8")
    entry = pk.ingest_local_artifact(pdir, art, tags=["domain:engineering", "type:audit"])
    idx = json.loads(pk.index_path(pdir).read_text(encoding="utf-8"))
    assert idx["specialist"] == "gond"
    assert idx["counts"]["entries"] == 1
    assert idx["by_id"][entry["id"]]["status"] == pk.STATUS_ACTIVE
    assert "domain:engineering" in idx["by_tag"]
    assert "type:audit" in idx["by_tag"]
    assert "local_artifact" in idx["by_source_type"]


# ---------------------------------------------------------------------------
# Readiness matrix
# ---------------------------------------------------------------------------


def test_corpus_ready_false_when_no_corpus(profiles_root: Path):
    pdir = _make_profile(profiles_root, "gond")
    row = pk.corpus_ready(pdir)
    assert row["ok"] is False
    assert row["has_corpus_dir"] is False
    assert row["entries"] == 0


def test_corpus_ready_true_after_verified_ingest(profiles_root: Path, tmp_path: Path):
    pdir = _make_profile(profiles_root, "gond")
    art = tmp_path / "evidence.txt"
    art.write_text("hello", encoding="utf-8")
    pk.ingest_local_artifact(pdir, art, tags=["domain:engineering"])
    row = pk.corpus_ready(pdir)
    assert row["ok"] is True
    assert row["entries"] == 1
    assert row["verified_entries"] == 1
    assert row["invalid_entries"] == []


def test_corpus_ready_false_when_only_gates(profiles_root: Path):
    # A specialist with only gate metadata has no verified evidence.
    pdir = _make_profile(profiles_root, "waukeen")
    pk.ingest_gated_source(pdir, "https://x.com/a", gate_kind="paywall")
    row = pk.corpus_ready(pdir)
    assert row["ok"] is False
    assert row["entries"] == 0
    assert row["gates"] == 1


def test_corpus_ready_reports_invalid_entries(profiles_root: Path):
    pdir = _make_profile(profiles_root, "gond")
    # Write a bad entry directly to disk to simulate corruption.
    pk._ensure_corpus_dir(pdir)
    pk._append_jsonl(pk.corpus_path(pdir), {"id": "x", "specialist": "gond"})
    row = pk.corpus_ready(pdir)
    assert row["ok"] is False
    assert row["invalid_entries"], row


def test_knowledge_corpus_matrix_bulk(profiles_root: Path, tmp_path: Path):
    art = tmp_path / "f.txt"
    art.write_text("ok", encoding="utf-8")
    for name in ("gond", "helm"):
        pdir = _make_profile(profiles_root, name)
        pk.ingest_local_artifact(pdir, art, tags=["type:demo"], specialist=name)
    _make_profile(profiles_root, "tymora")  # no corpus
    matrix = pk.knowledge_corpus_matrix(["gond", "helm", "tymora"], profiles_root=profiles_root)
    assert matrix["all_ok"] is False
    by_name = {r["name"]: r for r in matrix["rows"]}
    assert by_name["gond"]["ok"] is True
    assert by_name["helm"]["ok"] is True
    assert by_name["tymora"]["ok"] is False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_ingest_file_emits_json(profiles_root: Path, tmp_path: Path, monkeypatch, capsys):
    pdir = _make_profile(profiles_root, "gond")
    monkeypatch.setattr(pk, "_profiles_root", lambda: profiles_root)
    art = tmp_path / "evidence.txt"
    art.write_text("ok", encoding="utf-8")
    rc = pk.main(
        ["ingest-file", "gond", str(art), "--tag", "domain:engineering", "--tag", "type:demo"]
    )
    out = capsys.readouterr().out
    payload = json.loads(out.strip())
    assert rc == 0
    assert payload["path"] == str(art.resolve())
    rows = pk.read_entries(pdir)
    assert len(rows) == 1


def test_cli_ingest_audit(profiles_root: Path, tmp_path: Path, monkeypatch, capsys):
    pdir = _make_profile(profiles_root, "gond")
    monkeypatch.setattr(pk, "_profiles_root", lambda: profiles_root)
    audit = tmp_path / "a.json"
    audit.write_text(
        json.dumps({"stamp": "20260529T1416Z", "blocked_by_class": {"filip_approval": 1}}),
        encoding="utf-8",
    )
    rc = pk.main(["ingest-audit", "gond", str(audit)])
    assert rc == 0
    rows = pk.read_entries(pdir)
    assert rows[0]["source_type"] == "orchestrator_audit"


def test_cli_ingest_gate_and_query_include_gates(
    profiles_root: Path, monkeypatch, capsys
):
    _make_profile(profiles_root, "waukeen")
    monkeypatch.setattr(pk, "_profiles_root", lambda: profiles_root)
    rc = pk.main(
        [
            "ingest-gate",
            "waukeen",
            "https://wsj.com/x",
            "--gate-kind",
            "paywall",
            "--tag",
            "domain:finance",
            "--notes",
            "observed paywall",
        ]
    )
    assert rc == 0
    capsys.readouterr()  # drain
    rc = pk.main(["query", "waukeen", "--include-gates", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 1
    assert payload[0]["confidence"] == pk.CONFIDENCE_GATED_UNREAD


def test_cli_status_updates_existing_entry(
    profiles_root: Path, tmp_path: Path, monkeypatch, capsys
):
    pdir = _make_profile(profiles_root, "gond")
    monkeypatch.setattr(pk, "_profiles_root", lambda: profiles_root)
    art = tmp_path / "ev.txt"
    art.write_text("ok", encoding="utf-8")
    entry = pk.ingest_local_artifact(pdir, art, tags=["type:demo"])
    rc = pk.main(["status", "gond", entry["id"], pk.STATUS_SUPERSEDED])
    assert rc == 0
    rows = pk.read_entries(pdir)
    assert rows[0]["status"] == pk.STATUS_SUPERSEDED


def test_cli_matrix_informational_by_default(profiles_root: Path, monkeypatch, capsys):
    monkeypatch.setattr(pk, "_profiles_root", lambda: profiles_root)
    rc = pk.main(["matrix"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "all_ok: no" in out


def test_cli_matrix_strict_fails_when_no_corpus(profiles_root: Path, monkeypatch):
    monkeypatch.setattr(pk, "_profiles_root", lambda: profiles_root)
    rc = pk.main(["matrix", "--strict"])
    assert rc == 1


def test_cli_matrix_json_payload_has_rows_for_known_specialists(
    profiles_root: Path, monkeypatch, capsys
):
    monkeypatch.setattr(pk, "_profiles_root", lambda: profiles_root)
    rc = pk.main(["matrix", "--json"])
    payload = json.loads(capsys.readouterr().out)
    names = [r["name"] for r in payload["rows"]]
    for s in pk.KNOWN_SPECIALISTS:
        assert s in names
    assert rc == 0


def test_cli_rebuild_index_creates_index_file(
    profiles_root: Path, tmp_path: Path, monkeypatch, capsys
):
    pdir = _make_profile(profiles_root, "gond")
    monkeypatch.setattr(pk, "_profiles_root", lambda: profiles_root)
    art = tmp_path / "ev.txt"
    art.write_text("ok", encoding="utf-8")
    pk.ingest_local_artifact(pdir, art, tags=["type:demo"])
    rc = pk.main(["rebuild-index", "gond"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out == str(pk.index_path(pdir))
    idx = json.loads(pk.index_path(pdir).read_text(encoding="utf-8"))
    assert idx["counts"]["entries"] == 1


def test_cli_unknown_profile_returns_nonzero(profiles_root: Path, monkeypatch):
    monkeypatch.setattr(pk, "_profiles_root", lambda: profiles_root)
    rc = pk.main(["query", "ghost"])
    assert rc == 2
