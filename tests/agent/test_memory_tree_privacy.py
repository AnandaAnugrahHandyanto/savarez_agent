from __future__ import annotations

import json
from pathlib import Path


def _write_state(home: Path, outputs: dict[str, str]) -> None:
    data_dir = home / "data" / "memory-tree-lite"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "state.json").write_text(
        json.dumps(
            {
                "schema": "memory-tree-lite-state-v1",
                "outputs": outputs,
            }
        ),
        encoding="utf-8",
    )


def test_privacy_scan_is_clean_for_normal_pack(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    pack = tmp_path / "data" / "memory-tree-lite" / "recent.md"
    pack.parent.mkdir(parents=True)
    pack.write_text("# Recent\nNo secrets here.\n", encoding="utf-8")
    _write_state(tmp_path, {"recent": str(pack)})

    from agent.memory_tree_privacy import scan_memory_tree_privacy, format_privacy_text

    report = scan_memory_tree_privacy()

    assert report.summary["findings"] == 0
    assert report.findings == []
    assert format_privacy_text(report) == ""


def test_privacy_scan_flags_secret_like_lines_with_bounded_context(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    pack = tmp_path / "data" / "memory-tree-lite" / "recent.md"
    pack.parent.mkdir(parents=True)
    pack.write_text(
        "# Recent\nOPENAI_API_KEY=sk-abc123456789SECRETSECRET\nnormal line\n",
        encoding="utf-8",
    )
    _write_state(tmp_path, {"recent": str(pack)})

    from agent.memory_tree_privacy import scan_memory_tree_privacy

    report = scan_memory_tree_privacy(max_snippet_chars=30)

    assert report.summary["findings"] == 1
    finding = report.findings[0]
    assert finding.kind == "secret_assignment"
    assert finding.pack == "recent"
    assert finding.line == 2
    assert finding.path == str(pack)
    assert "OPENAI_API_KEY" in finding.snippet
    assert len(finding.snippet) <= 30
    assert "SECRETSECRET" not in finding.snippet


def test_privacy_json_is_bounded_and_source_rich(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    pack = tmp_path / "data" / "memory-tree-lite" / "recent.md"
    pack.parent.mkdir(parents=True)
    pack.write_text("\n".join(f"token_{i}=abc123SECRETSECRET" for i in range(20)), encoding="utf-8")
    _write_state(tmp_path, {"recent": str(pack)})

    from agent.memory_tree_privacy import format_privacy_json, scan_memory_tree_privacy

    text = format_privacy_json(scan_memory_tree_privacy(), max_chars=700)
    payload = json.loads(text)

    assert payload["schema"] == "memory-tree-privacy-v1"
    assert payload["total_findings"] == 20
    assert payload["truncated"] is True
    assert payload["findings"]
    assert set(payload["findings"][0]) >= {"pack", "path", "line", "kind", "severity", "snippet"}
    assert len(text) <= 700


def test_privacy_scan_ignores_normal_ids_and_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    pack = tmp_path / "data" / "memory-tree-lite" / "recent.md"
    pack.parent.mkdir(parents=True, exist_ok=True)
    pack.write_text(
        "source_id: alice-kang-qiao-admissions-followup-20260703\n"
        "  \"id\": \"alice-kang-qiao-admissions-followup-20260703\",\n"
        "  \"cron_job_id\": \"3cf17b9e5c4c\",\n"
        "  \"poller\": \"/home/prodesign/.pd-one/scripts/schedule_watch.py poll\",\n"
        "  \"evidence\": \"kept Honcho recallMode=tools/contextTokens=500/dialecticMaxChars=400\",\n",
        encoding="utf-8",
    )
    _write_state(tmp_path, {"recent": str(pack)})

    from agent.memory_tree_privacy import scan_memory_tree_privacy

    report = scan_memory_tree_privacy()

    assert report.findings == []


def test_privacy_scan_flags_bearer_tokens_without_leaking_value(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    pack = tmp_path / "data" / "memory-tree-lite" / "recent.md"
    pack.parent.mkdir(parents=True, exist_ok=True)
    pack.write_text("Authorization: Bearer abcdefghijklmnopqrstuvwxyz1234567890\n", encoding="utf-8")
    _write_state(tmp_path, {"recent": str(pack)})

    from agent.memory_tree_privacy import scan_memory_tree_privacy

    report = scan_memory_tree_privacy()

    assert len(report.findings) == 1
    assert report.findings[0].kind == "bearer_token"
    assert report.findings[0].snippet == "Authorization: Bearer <redacted>"
