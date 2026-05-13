"""dp_cli_wrapper: JSON parsing, error handling, model drift guard."""
from __future__ import annotations

import json

import pytest

from deepparser_api.dp_cli_wrapper import _parse_ask_result, _parse_upload_result
from deepparser_api.models import DPCLIAskResult, DPCLIParseResult

from .conftest import PINNED_ASK_JSON, PINNED_PARSE_JSON

# Note: all tests in this file are synchronous (_parse_* helpers are not async)


# ---------------------------------------------------------------------------
# _parse_upload_result — pinned JSON must produce expected DPCLIParseResult
# ---------------------------------------------------------------------------

def test_parse_upload_result_pinned_json() -> None:
    result = _parse_upload_result(json.dumps(PINNED_PARSE_JSON))
    assert isinstance(result, DPCLIParseResult)
    assert result.file_id == "file-abc123"
    assert result.folder_id == "folder-xyz789"
    assert result.file_name == "test.pdf"
    assert result.extension == "pdf"
    assert result.pages == 4
    assert result.tables == 2


def test_parse_upload_result_non_json_raises() -> None:
    with pytest.raises(RuntimeError, match="non-JSON"):
        _parse_upload_result("this is not json")


def test_parse_upload_result_not_ok_raises() -> None:
    payload = json.dumps({"ok": False, "error": "quota exceeded"})
    with pytest.raises(RuntimeError, match="quota exceeded"):
        _parse_upload_result(payload)


def test_parse_upload_result_no_uploads_raises() -> None:
    payload = json.dumps({"ok": True, "uploads": []})
    with pytest.raises(RuntimeError, match="no uploads"):
        _parse_upload_result(payload)


def test_parse_upload_result_missing_file_id_raises() -> None:
    bad = {
        "ok": True,
        "uploads": [
            {
                "result": {
                    "response": {
                        "body": {
                            "data": {
                                # id is missing
                                "folder_id": "f1",
                                "file_name": "x.pdf",
                                "extension": "pdf",
                            }
                        }
                    }
                }
            }
        ],
    }
    with pytest.raises(RuntimeError, match="no file_id"):
        _parse_upload_result(json.dumps(bad))


# ---------------------------------------------------------------------------
# _parse_ask_result — pinned JSON must produce expected DPCLIAskResult
# ---------------------------------------------------------------------------

def test_parse_ask_result_pinned_json() -> None:
    result = _parse_ask_result(json.dumps(PINNED_ASK_JSON))
    assert isinstance(result, DPCLIAskResult)
    assert result.answer == "The total contract value is $84,000."
    assert len(result.citations) == 1
    assert result.citations[0].filename == "test.pdf"
    assert result.citations[0].page == 2


def test_parse_ask_result_non_json_raises() -> None:
    with pytest.raises(RuntimeError, match="non-JSON"):
        _parse_ask_result("not json at all")


def test_parse_ask_result_not_ok_raises() -> None:
    payload = json.dumps({"ok": False, "error": "file not found"})
    with pytest.raises(RuntimeError, match="file not found"):
        _parse_ask_result(payload)


def test_parse_ask_result_no_citations_ok() -> None:
    payload = json.dumps({
        "ok": True,
        "response": {"body": {"answer": "42", "citations": []}},
    })
    result = _parse_ask_result(payload)
    assert result.answer == "42"
    assert result.citations == []


def test_parse_ask_result_citations_missing_fields() -> None:
    """Citations with only filename (page/cell can be None)."""
    payload = json.dumps({
        "ok": True,
        "response": {
            "body": {
                "answer": "Something",
                "citations": [{"filename": "doc.pdf"}],
            }
        },
    })
    result = _parse_ask_result(payload)
    assert result.citations[0].page is None
    assert result.citations[0].cell is None
