from education.service import EducationService
from education.mineru import MinerUResult


class FakeMinerUBackend:
    def parse_document(self, source_file, output_dir):
        markdown = """1. 已知 $a^2+b^2=c^2$，下列说法正确的是？
A. 勾股定理
B. 一元二次方程
C. 指数函数
D. 对数函数

答案：A

解析：由 $a^2+b^2=c^2$ 可知为勾股定理。
"""
        return MinerUResult(
            markdown=markdown,
            output_dir=output_dir,
            json_payload={"backend": "fake"},
            warnings=[],
        )


class FailingMinerUBackend:
    def parse_document(self, source_file, output_dir):
        raise RuntimeError("mineru parse failed")


def test_education_service_ingests_pdf_end_to_end(tmp_path, monkeypatch):
    fake_home = tmp_path / "custom_hermes_home"
    fake_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(fake_home))

    source_file = tmp_path / "algebra.pdf"
    source_file.write_bytes(b"%PDF-sample-content")

    service = EducationService(mineru_backend=FakeMinerUBackend())
    result = service.ingest_file(source_file)

    assert result.status == "indexed"
    assert result.document_id
    assert result.job_id
    assert result.raw_artifact_path.exists()
    assert result.normalized_artifact_path.exists()
    assert result.question_count == 1
    assert result.citation_status == "complete"

    questions = service.search_questions("勾股定理")
    assert len(questions) == 1
    assert questions[0]["citation_status"] == "complete"


def test_education_service_records_failure_and_preserves_raw_artifact(tmp_path, monkeypatch):
    fake_home = tmp_path / "custom_hermes_home"
    fake_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(fake_home))

    source_file = tmp_path / "broken.pdf"
    source_file.write_bytes(b"%PDF-broken")

    service = EducationService(mineru_backend=FailingMinerUBackend())
    result = service.ingest_file(source_file)

    assert result.status == "failed"
    assert result.error == "mineru parse failed"
    assert result.raw_artifact_path.exists()
    assert result.question_count == 0


def test_education_service_reuses_existing_document_for_duplicate_sha(tmp_path, monkeypatch):
    fake_home = tmp_path / "custom_hermes_home"
    fake_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(fake_home))

    source_file = tmp_path / "algebra.pdf"
    source_file.write_bytes(b"%PDF-same-content")

    service = EducationService(mineru_backend=FakeMinerUBackend())
    first = service.ingest_file(source_file)
    second = service.ingest_file(source_file)

    assert first.document_id == second.document_id
