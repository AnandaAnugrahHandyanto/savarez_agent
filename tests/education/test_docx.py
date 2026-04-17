from education.docx import DocxPreparationError, prepare_for_mineru


def test_prepare_for_mineru_accepts_docx_extension(tmp_path):
    source_file = tmp_path / "worksheet.docx"
    source_file.write_bytes(b"PK\x03\x04fake-docx")

    try:
        prepare_for_mineru(source_file, tmp_path / "prepared")
    except DocxPreparationError as exc:
        assert ".docx" in str(exc)
        assert "converter" in str(exc).lower()
    else:
        raise AssertionError("Expected DOCX preparation to require a converter seam")


def test_prepare_for_mineru_reports_original_path_in_error(tmp_path):
    source_file = tmp_path / "lesson.docx"
    source_file.write_bytes(b"PK\x03\x04fake-docx")

    try:
        prepare_for_mineru(source_file, tmp_path / "prepared")
    except DocxPreparationError as exc:
        assert str(source_file) in str(exc)
    else:
        raise AssertionError("Expected DOCX preparation to fail without converter support")
