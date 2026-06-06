"""invest 프로파일 firecrawl hard-deny 가드 검증 (BACKLOG 치명#2).

config opt-in으로도 풀 수 없는 코드레벨 denylist가 직접선택(firecrawl provider)·
폴백(crawl4ai → firecrawl) 양 경로를 차단하는지 확인한다.
"""
import asyncio


def _set_profile(monkeypatch, name):
    monkeypatch.setattr("hermes_cli.profiles.get_active_profile_name", lambda: name)


def test_denied_flag_for_invest_watcher(monkeypatch):
    from plugins.web import firecrawl_denied_for_active_profile
    _set_profile(monkeypatch, "invest-watcher")
    assert firecrawl_denied_for_active_profile() is True


def test_not_denied_for_news_curator(monkeypatch):
    from plugins.web import firecrawl_denied_for_active_profile
    _set_profile(monkeypatch, "news-curator")
    assert firecrawl_denied_for_active_profile() is False


def test_profile_detect_failure_is_not_denied(monkeypatch):
    """프로파일 판정 예외 시 가드는 보류(False) — config fail-closed가 받친다."""
    from plugins.web import firecrawl_denied_for_active_profile

    def _boom():
        raise RuntimeError("no profile")
    monkeypatch.setattr("hermes_cli.profiles.get_active_profile_name", _boom)
    assert firecrawl_denied_for_active_profile() is False


def test_crawl4ai_fallback_hard_denied_even_when_config_optin(monkeypatch):
    """invest는 config가 firecrawl 폴백을 opt-in 해도 hard-deny가 이긴다."""
    _set_profile(monkeypatch, "invest-watcher")
    monkeypatch.setattr("plugins.web.crawl4ai.provider._config_fallback_enabled", lambda: True)
    from plugins.web.crawl4ai.provider import _fallback_disabled
    assert _fallback_disabled() is True


def test_crawl4ai_fallback_allowed_for_news_when_optin(monkeypatch):
    """news-curator는 opt-in 하면 폴백 허용(가드 무관)."""
    _set_profile(monkeypatch, "news-curator")
    monkeypatch.setattr("plugins.web.crawl4ai.provider._config_fallback_enabled", lambda: True)
    from plugins.web.crawl4ai.provider import _fallback_disabled
    assert _fallback_disabled() is False


def test_firecrawl_provider_unavailable_for_invest(monkeypatch):
    _set_profile(monkeypatch, "invest-watcher")
    from plugins.web.firecrawl.provider import FirecrawlWebSearchProvider
    assert FirecrawlWebSearchProvider().is_available() is False


def test_firecrawl_search_denied_for_invest(monkeypatch):
    _set_profile(monkeypatch, "invest-watcher")
    from plugins.web.firecrawl.provider import FirecrawlWebSearchProvider
    r = FirecrawlWebSearchProvider().search("anything", limit=3)
    assert r["success"] is False and "denied" in r["error"].lower()


def test_firecrawl_extract_denied_for_invest(monkeypatch):
    _set_profile(monkeypatch, "invest-watcher")
    from plugins.web.firecrawl.provider import FirecrawlWebSearchProvider
    res = asyncio.run(FirecrawlWebSearchProvider().extract(["https://example.com"]))
    assert res and "denied" in (res[0].get("error") or "").lower()
