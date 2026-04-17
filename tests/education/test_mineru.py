from pathlib import Path

from education.mineru import CliMinerUBackend, MinerUUnavailableError


def test_cli_mineru_backend_raises_when_binary_missing(tmp_path):
    backend = CliMinerUBackend(binary="missing-mineru")

    source_file = tmp_path / "algebra.pdf"
    source_file.write_bytes(b"%PDF-sample-content")
    output_dir = tmp_path / "out"

    try:
        backend.parse_document(source_file, output_dir)
    except MinerUUnavailableError as exc:
        assert "missing-mineru" in str(exc)
    else:
        raise AssertionError("Expected MinerUUnavailableError when binary is missing")


def test_cli_mineru_backend_builds_command_for_pdf(tmp_path):
    backend = CliMinerUBackend(binary="mineru")

    source_file = tmp_path / "algebra.pdf"
    source_file.write_bytes(b"%PDF-sample-content")
    output_dir = tmp_path / "out"

    command = backend.build_command(source_file, output_dir)

    assert command[0] == "mineru"
    assert str(source_file) in command
    assert str(output_dir) in command


def test_fake_parse_result_can_preserve_formula_markdown(tmp_path):
    backend = CliMinerUBackend(binary="mineru")
    formula_markdown = "题目：已知 $a^2+b^2=c^2$，求 $$x^2+y^2$$"

    result = backend._build_result(
        markdown=formula_markdown,
        output_dir=tmp_path,
        json_payload={"ok": True},
        warnings=["sample"],
    )

    assert result.markdown == formula_markdown
    assert result.json_payload == {"ok": True}
    assert result.warnings == ["sample"]
