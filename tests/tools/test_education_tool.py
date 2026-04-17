from tools.registry import discover_builtin_tools, registry


def test_education_tool_registers_expected_tool_names():
    discover_builtin_tools()
    registered = {entry.name for entry in registry._snapshot_entries()}

    assert "education_ingest_document" in registered
    assert "education_ingest_status" in registered
    assert "education_search_questions" in registered
    assert "education_render_wiki" in registered
    assert "education_export_question_bank" in registered


def test_education_tool_handlers_return_json_serializable_output(monkeypatch):
    import tools.education_tool as education_tool

    class FakeService:
        def ingest_file(self, path):
            return {
                "document_id": "doc001",
                "job_id": "job001",
                "status": "indexed",
                "raw_artifact_path": "/tmp/raw.pdf",
                "normalized_artifact_path": "/tmp/normalized.md",
                "question_count": 1,
                "citation_status": "complete",
                "error": None,
            }

    monkeypatch.setattr(education_tool, "EducationService", lambda: FakeService())

    result = education_tool._education_ingest_document({"path": "/tmp/sample.pdf"})

    assert '"document_id": "doc001"' in result
    assert '"status": "indexed"' in result
