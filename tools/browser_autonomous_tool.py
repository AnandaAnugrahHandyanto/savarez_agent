"""
Autonomous Browser Tool — delegates goal-directed browsing to the browser-use Agent.

Unlike the step-by-step browser_* tools (navigate, click, type), this tool
takes a high-level goal (e.g. "find the pricing on example.com") and lets
browser-use's inner agent loop handle the planning and execution autonomously.

Requires: ``pip install browser-use``

The LLM used by the inner agent is resolved from Hermes's config — it uses the
same model/provider chain as the outer agent unless overridden via
``BROWSER_USE_LLM_MODEL`` env var.
"""

import json
import logging
import os
from typing import Optional

from tools.registry import registry

logger = logging.getLogger(__name__)

# Max browsing steps to prevent runaway token spend
_MAX_STEPS_CAP = 100

# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

_browser_use_available: Optional[bool] = None


def _check_browser_use() -> bool:
    """Return True if browser-use library is importable."""
    global _browser_use_available
    if _browser_use_available is not None:
        return _browser_use_available
    try:
        from browser_use import Agent  # noqa: F401
        _browser_use_available = True
    except ImportError:
        _browser_use_available = False
    return _browser_use_available


# ---------------------------------------------------------------------------
# URL safety
# ---------------------------------------------------------------------------

def _validate_url(url: str) -> Optional[str]:
    """Validate a URL using the same checks as browser_navigate.

    Returns an error string if the URL is unsafe, or None if OK.
    """
    if not url:
        return None

    try:
        from tools.url_safety import is_safe_url
        if not is_safe_url(url):
            return f"URL blocked by safety check (private/internal network): {url}"
    except ImportError:
        pass

    try:
        from tools.website_policy import check_website_access
        denial = check_website_access(url)
        if denial:
            return f"URL blocked by website policy: {denial}"
    except ImportError:
        pass

    return None


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------

def _ensure_hermes_env():
    """Load non-empty keys from ~/.hermes/.env without clobbering existing env vars."""
    from pathlib import Path
    env_path = Path.home() / ".hermes" / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # Only set if the value is non-empty AND we don't already have it
            if key and value and key not in os.environ:
                os.environ[key] = value
    except Exception as exc:
        logger.debug("Could not load ~/.hermes/.env: %s", exc)


def _make_llm():
    """Build a browser-use-compatible LLM from available API keys.

    Provider resolution order:
    1. BROWSER_USE_LLM_MODEL / _BASE_URL / _API_KEY env overrides
    2. OPENROUTER_API_KEY -> ChatOpenRouter
    3. ANTHROPIC_API_KEY -> ChatAnthropic direct
    4. OPENAI_API_KEY -> ChatOpenAI direct
    5. GOOGLE_API_KEY -> ChatOpenAI via Gemini OpenAI compat endpoint

    Raises RuntimeError if no API key is found.
    """
    _ensure_hermes_env()

    # Check for explicit override
    explicit_model = os.environ.get("BROWSER_USE_LLM_MODEL", "").strip()
    explicit_base = os.environ.get("BROWSER_USE_LLM_BASE_URL", "").strip()
    explicit_key = os.environ.get("BROWSER_USE_LLM_API_KEY", "").strip()

    if explicit_model and explicit_key:
        from browser_use import ChatOpenAI
        kwargs = {"model": explicit_model, "temperature": 0.1}
        if explicit_base:
            kwargs["base_url"] = explicit_base
        kwargs["api_key"] = explicit_key
        return ChatOpenAI(**kwargs)

    # Auto-detect from available keys
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    google_key = os.environ.get("GOOGLE_API_KEY", "").strip()

    # Try to read preferred model from config
    config_model = ""
    try:
        from hermes_cli.config import load_config
        cfg = load_config()
        config_model = cfg.get("model", {}).get("default", "")
    except Exception:
        pass

    # OpenRouter (supports all model prefixes, has dedicated class)
    if openrouter_key:
        from browser_use.llm.openrouter.chat import ChatOpenRouter
        model = config_model or "anthropic/claude-sonnet-4"
        return ChatOpenRouter(
            model=model,
            api_key=openrouter_key,
            temperature=0.1,
        )

    # Anthropic direct
    if anthropic_key:
        from browser_use import ChatAnthropic
        # Strip provider prefix if present
        model = config_model.replace("anthropic/", "") if config_model else "claude-sonnet-4-20250514"
        return ChatAnthropic(
            model=model,
            api_key=anthropic_key,
            temperature=0.1,
        )

    # OpenAI direct
    if openai_key:
        from browser_use import ChatOpenAI
        model = config_model if config_model and not config_model.startswith("anthropic/") else "gpt-4.1-mini"
        return ChatOpenAI(model=model, api_key=openai_key, temperature=0.1)

    # Google via OpenAI-compat
    if google_key:
        from browser_use import ChatOpenAI
        return ChatOpenAI(
            model="gemini-2.5-flash",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=google_key,
            temperature=0.1,
        )

    raise RuntimeError(
        "No LLM API key found for browser_use_agent. "
        "Set OPENROUTER_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, or "
        "GOOGLE_API_KEY in ~/.hermes/.env or your shell environment."
    )


# ---------------------------------------------------------------------------
# Core handler (async — dispatched via registry's _run_async bridge)
# ---------------------------------------------------------------------------

async def _browser_use_agent_handler(args: dict, **kwargs) -> str:
    """Async handler for the autonomous browser tool."""
    task = args.get("task", "")
    url = args.get("url")
    max_steps = min(args.get("max_steps", 15), _MAX_STEPS_CAP)
    use_vision = args.get("use_vision", False)

    if not task:
        return json.dumps({"error": "task is required"})

    # Validate starting URL if provided
    if url:
        url_error = _validate_url(url)
        if url_error:
            return json.dumps({"error": url_error})

    from browser_use import Agent, BrowserProfile

    profile = BrowserProfile(headless=True, keep_alive=False)

    try:
        llm = _make_llm()
    except RuntimeError as exc:
        return json.dumps({"error": str(exc)})

    full_task = task
    if url:
        full_task = f"Go to {url} and then: {task}"

    agent = Agent(
        task=full_task,
        llm=llm,
        browser_profile=profile,
        use_vision=use_vision,
        max_failures=3,
    )

    try:
        history = await agent.run(max_steps=max_steps)

        final = history.final_result()
        is_done = history.is_done()
        is_success = history.is_successful()
        steps = history.number_of_steps()
        duration = history.total_duration_seconds()
        visited_urls = history.urls()
        errors = [e for e in (history.errors() or []) if e is not None]

        result = {
            "success": bool(is_success),
            "done": bool(is_done),
            "result": final or "",
            "steps": steps,
            "duration_seconds": round(duration, 1) if duration else None,
            "urls_visited": visited_urls[:10] if visited_urls else [],
        }
        if errors:
            result["errors"] = [str(e)[:200] for e in errors[:3]]

        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({
            "success": False,
            "error": f"{type(exc).__name__}: {str(exc)[:500]}",
        }, ensure_ascii=False)
    finally:
        try:
            await agent.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Schema & Registration
# ---------------------------------------------------------------------------

BROWSER_USE_AGENT_SCHEMA = {
    "name": "browser_use_agent",
    "description": (
        "Autonomous browser agent that plans and executes browsing steps "
        "(navigate, click, type, scroll) on its own. Use ONLY for open-ended "
        "exploratory tasks where the workflow cannot be pre-planned — e.g. "
        "'research topic X across multiple sites' or 'find the cheapest flight "
        "across three airline sites'. For any well-defined workflow (known URL, "
        "known steps), PREFER the step-by-step tools: browser_navigate + "
        "browser_snapshot + browser_click + browser_type — they are cheaper, "
        "faster, give you visibility into each step, and route through the "
        "configured cloud provider (if any) for anti-detect stealth. For "
        "simple single-page reads, prefer web_search or web_extract."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": (
                    "The browsing goal in natural language. Be specific about "
                    "what information you need or what action to perform. "
                    "Example: 'Find the current price of Bitcoin on CoinGecko'"
                ),
            },
            "url": {
                "type": "string",
                "description": (
                    "Optional starting URL. If provided, the agent navigates "
                    "here first before working on the task."
                ),
            },
            "max_steps": {
                "type": "integer",
                "description": (
                    f"Maximum browsing steps (default: 15, max: {_MAX_STEPS_CAP}). "
                    "Increase for complex multi-page tasks."
                ),
                "default": 15,
            },
            "use_vision": {
                "type": "boolean",
                "description": "Enable screenshot-based vision for pages with poor accessibility trees (default: false, uses text snapshots).",
                "default": False,
            },
        },
        "required": ["task"],
    },
}

registry.register(
    name="browser_use_agent",
    toolset="browser",
    schema=BROWSER_USE_AGENT_SCHEMA,
    handler=_browser_use_agent_handler,
    check_fn=_check_browser_use,
    is_async=True,
    description="Autonomous browser agent for goal-directed web tasks",
    emoji="🤖",
    mutates=True,
)
