import json

import pytest

from tools import web_tools


def test_web_extract_schema_exposes_document_parsing_options():
    schema = web_tools.WEB_EXTRACT_SCHEMA
    description = schema["description"]
    properties = schema["parameters"]["properties"]

    assert "DOCX" in description
    assert "XLSX" in description
    assert "pdf_mode" in properties
    assert properties["pdf_mode"]["enum"] == ["auto", "fast", "ocr"]
    assert "pdf_max_pages" in properties


@pytest.mark.asyncio
async def test_web_extract_passes_pdf_parser_options_to_firecrawl(monkeypatch):
    calls = []

    class FakeFirecrawlClient:
        def scrape(self, **kwargs):
            calls.append(kwargs)
            return {
                "markdown": "parsed pdf markdown",
                "metadata": {
                    "title": "Quarterly Report",
                    "sourceURL": kwargs["url"],
                },
            }

    monkeypatch.setattr(web_tools, "_get_backend", lambda: "firecrawl")
    monkeypatch.setattr(web_tools, "_get_firecrawl_client", lambda: FakeFirecrawlClient())
    monkeypatch.setattr(web_tools, "is_safe_url", lambda url: True)
    monkeypatch.setattr(web_tools, "check_website_access", lambda url: None)
    monkeypatch.setattr("tools.interrupt.is_interrupted", lambda: False)

    result = json.loads(
        await web_tools.web_extract_tool(
            ["https://example.com/report.pdf"],
            format="markdown",
            use_llm_processing=False,
            pdf_mode="ocr",
            pdf_max_pages=7,
        )
    )

    assert result["results"][0]["content"] == "parsed pdf markdown"
    assert calls == [
        {
            "url": "https://example.com/report.pdf",
            "formats": ["markdown"],
            "parsers": [{"type": "pdf", "mode": "ocr", "max_pages": 7}],
        }
    ]
