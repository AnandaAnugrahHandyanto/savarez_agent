import pytest

from tools.web_tools import _log_safe_url, web_crawl_tool


def test_log_safe_url_redacts_credentials_query_and_fragment():
    secret_url = (
        "https://alice:s3cr3t@example.com/private/path"
        "?api_key=sk-test-12345678901234567890&sig=abcdef#token=xyz"
    )

    safe_url = _log_safe_url(secret_url)

    assert safe_url == "https://[REDACTED]@example.com/private/path?[REDACTED]#[REDACTED]"
    assert "alice" not in safe_url
    assert "s3cr3t" not in safe_url
    assert "sk-test-12345678901234567890" not in safe_url
    assert "sig=abcdef" not in safe_url
    assert "token=xyz" not in safe_url


@pytest.mark.asyncio
async def test_web_crawl_tool_does_not_log_secret_url(caplog, monkeypatch):
    secret_url = "https://example.com/private?api_key=sk-test-12345678901234567890#frag"

    monkeypatch.setattr("tools.web_tools._get_backend", lambda: "tavily")
    monkeypatch.setattr("tools.web_tools.check_auxiliary_model", lambda: False)
    monkeypatch.setattr("tools.web_tools.is_safe_url", lambda url: True)
    monkeypatch.setattr("tools.web_tools.check_website_access", lambda url: None)
    monkeypatch.setattr("tools.interrupt.is_interrupted", lambda: False)
    monkeypatch.setattr(
        "tools.web_tools._tavily_request",
        lambda endpoint, payload: {
            "results": [
                {
                    "url": secret_url,
                    "title": "Secret page",
                    "raw_content": "body",
                }
            ]
        },
    )

    caplog.set_level("INFO", logger="tools.web_tools")

    await web_crawl_tool(secret_url, use_llm_processing=False)

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "sk-test-12345678901234567890" not in log_text
    assert "api_key=" not in log_text
    assert "Tavily crawl: https://example.com/private?[REDACTED]#[REDACTED]" in log_text
