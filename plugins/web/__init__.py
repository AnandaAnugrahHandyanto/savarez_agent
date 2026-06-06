# Bundled web search providers — plugins/web/.
#
# Each subdirectory follows the image_gen plugin layout:
#   plugins/web/<name>/{plugin.yaml, __init__.py, provider.py}
#
# They auto-load via kind: backend and register via
# ctx.register_web_search_provider() into agent.web_search_registry.

# Firecrawl이 **코드레벨에서 금지된** 프로파일(도메인 정책 hard-deny).
# config opt-in(``web.extract_fallback: firecrawl``)으로도 풀 수 없는, config
# 손상·오설정에 독립적인 최종 가드.
#   근거(BACKLOG 치명#2, 2026-06-06): invest 도메인은 외부 SaaS(firecrawl) 차단이
#   원칙. config fail-closed 게이트(crawl4ai provider) 위에 프로파일 denylist를
#   얹어, 설정이 어떻게 바뀌어도 invest-watcher가 firecrawl로 새지 않게 한다.
# 신규 금지 프로파일은 여기에 1줄 추가한다.
FIRECRAWL_DENY_PROFILES = frozenset({"invest-watcher"})


def firecrawl_denied_for_active_profile() -> bool:
    """활성 프로파일이 Firecrawl hard-deny 대상이면 True.

    직접선택(firecrawl provider)·폴백(crawl4ai → firecrawl) 양쪽에서 호출해
    config와 무관하게 차단한다. 프로파일 판정 실패 시 False(이 가드는 보류)이며,
    그 경우에도 crawl4ai의 config fail-closed 게이트가 기본 차단을 유지한다.
    """
    try:
        from hermes_cli.profiles import get_active_profile_name

        return (get_active_profile_name() or "").strip() in FIRECRAWL_DENY_PROFILES
    except Exception:
        return False
