from pathlib import Path

from education.artifacts import ArtifactStore
from education.paths import artifacts_root


def test_artifact_store_saves_raw_pdf_under_hashed_directory(tmp_path, monkeypatch):
    fake_home = tmp_path / "custom_hermes_home"
    fake_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(fake_home))

    source_file = tmp_path / "algebra.pdf"
    source_file.write_bytes(b"%PDF-sample-content")

    store = ArtifactStore()
    stored = store.store_source_file(source_file)

    assert stored.kind == "raw"
    assert stored.path.exists()
    assert stored.path.suffix == ".pdf"
    assert stored.path.parent.parent == artifacts_root() / "raw"
    assert stored.original_filename == "algebra.pdf"
    assert stored.sha256


def test_artifact_store_accepts_docx_source_files(tmp_path, monkeypatch):
    fake_home = tmp_path / "custom_hermes_home"
    fake_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(fake_home))

    source_file = tmp_path / "worksheet.docx"
    source_file.write_bytes(b"PK\x03\x04fake-docx")

    store = ArtifactStore()
    stored = store.store_source_file(source_file)

    assert stored.path.exists()
    assert stored.path.suffix == ".docx"
    assert stored.original_filename == "worksheet.docx"


def test_artifact_store_writes_named_markdown_and_json_artifacts(tmp_path, monkeypatch):
    fake_home = tmp_path / "custom_hermes_home"
    fake_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(fake_home))

    store = ArtifactStore()
    markdown_artifact = store.write_named_artifact(
        kind="mineru",
        artifact_id="abc123",
        filename="result.md",
        content="# parsed",
    )
    json_artifact = store.write_named_artifact(
        kind="normalized",
        artifact_id="xyz789",
        filename="result.json",
        content='{"ok": true}',
    )

    assert markdown_artifact.path.read_text() == "# parsed"
    assert json_artifact.path.read_text() == '{"ok": true}'
    assert markdown_artifact.path.parent == artifacts_root() / "mineru" / "abc123"
    assert json_artifact.path.parent == artifacts_root() / "normalized" / "xyz789"


def test_artifact_store_writes_wiki_markdown(tmp_path, monkeypatch):
    fake_home = tmp_path / "custom_hermes_home"
    fake_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(fake_home))

    store = ArtifactStore()
    artifact = store.write_named_artifact(
        kind="wiki",
        artifact_id="doc001",
        filename="lesson.md",
        content="# Wiki page",
    )

    assert artifact.path.read_text() == "# Wiki page"
    assert artifact.path.parent == artifacts_root() / "wiki" / "doc001"


def test_artifact_store_rejects_unsupported_source_extensions(tmp_path, monkeypatch):
    fake_home = tmp_path / "custom_hermes_home"
    fake_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(fake_home))

    source_file = tmp_path / "notes.txt"
    source_file.write_text("not supported")

    store = ArtifactStore()

    try:
        store.store_source_file(source_file)
    except ValueError as exc:
        assert "Unsupported source file type" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported source extension")
