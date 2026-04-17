from education.service import EducationService
from education.mineru import MinerUResult


class FakeMinerUBackend:
    def parse_document(self, source_file, output_dir):
        markdown = """1. 计算：
$$x^2+y^2$$

答案：无法确定
"""
        return MinerUResult(
            markdown=markdown,
            output_dir=output_dir,
            json_payload={"backend": "fake"},
            warnings=["sample warning"],
        )


def test_ingestion_pipeline_stores_question_rows_and_citations(tmp_path, monkeypatch):
    fake_home = tmp_path / "custom_hermes_home"
    fake_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(fake_home))

    source_file = tmp_path / "geometry.pdf"
    source_file.write_bytes(b"%PDF-geometry")

    service = EducationService(mineru_backend=FakeMinerUBackend())
    result = service.ingest_file(source_file)

    assert result.question_count == 1

    db = service.db
    question_rows = db.search_questions("x^2+y^2")
    assert len(question_rows) == 1

    citation_rows = db.conn.execute(
        "SELECT * FROM question_citations WHERE question_id = ?",
        (question_rows[0]["id"],),
    ).fetchall()
    assert len(citation_rows) == 2
    assert all(row["integrity_status"] == "valid" for row in citation_rows)
