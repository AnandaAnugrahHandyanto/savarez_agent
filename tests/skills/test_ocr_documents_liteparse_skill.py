from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "skills" / "productivity" / "ocr-and-documents" / "scripts" / "extract_liteparse.py"
PYMUPDF_SCRIPT = SCRIPT.with_name("extract_pymupdf.py")


@pytest.fixture()
def liteparse_module():
    spec = importlib.util.spec_from_file_location("extract_liteparse", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def pymupdf_module():
    spec = importlib.util.spec_from_file_location("extract_pymupdf", PYMUPDF_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_parse_command_defaults_to_fast_text_path(liteparse_module):
    cmd = liteparse_module.build_parse_command(
        "/usr/local/bin/lit",
        "document.pdf",
        output_format="json",
        target_pages="1-5,10",
        output="output.json",
    )

    assert cmd == [
        "/usr/local/bin/lit",
        "parse",
        "document.pdf",
        "--format",
        "json",
        "--quiet",
        "--no-ocr",
        "--target-pages",
        "1-5,10",
        "-o",
        "output.json",
    ]


def test_check_reports_missing_liteparse_as_optional(liteparse_module, monkeypatch, capsys):
    monkeypatch.setattr(liteparse_module, "which", lambda name: None)

    result = liteparse_module.run(liteparse_module.parse_args(["--check"]))

    assert result == 1
    assert "LiteParse CLI not found" in capsys.readouterr().out


def test_missing_liteparse_falls_back_to_pymupdf_for_text(liteparse_module, monkeypatch, capsys):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(liteparse_module, "subprocess", subprocess)
    monkeypatch.setattr(liteparse_module.subprocess, "run", fake_run)

    result = liteparse_module.run_pymupdf_fallback(
        "document.pdf",
        target_pages="1-5,10",
        output=None,
    )

    assert result == 0
    assert calls == [
        (
            [
                sys.executable,
                str(SCRIPT.with_name("extract_pymupdf.py")),
                "document.pdf",
                "--pages",
                "0-4,9",
            ],
            {"check": False},
        )
    ]
    assert "falling back to extract_pymupdf.py" in capsys.readouterr().err


def test_missing_liteparse_json_does_not_fake_structured_output(liteparse_module, monkeypatch, capsys):
    monkeypatch.setattr(liteparse_module, "find_liteparse_cli", lambda: None)
    monkeypatch.setattr(
        liteparse_module,
        "run_pymupdf_fallback",
        lambda *args, **kwargs: pytest.fail("JSON fallback should not run"),
    )

    result = liteparse_module.run(liteparse_module.parse_args(["document.pdf", "--json"]))

    assert result == 127
    assert "required for structured JSON output" in capsys.readouterr().err


def test_pymupdf_page_parser_accepts_fallback_page_lists(pymupdf_module):
    assert pymupdf_module.parse_pages("0-4,9,11-12") == [0, 1, 2, 3, 4, 9, 11, 12]
