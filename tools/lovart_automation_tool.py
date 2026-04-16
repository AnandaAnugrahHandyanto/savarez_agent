#!/usr/bin/env python3
"""Lovart browser automation tool for Hermes."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from tools.registry import registry, tool_error, tool_result

LOVART_URL = "https://lovart.ai"
LOVART_SESSION_DIR = Path(__file__).resolve().parent / "lovart_session"
INPUT_SELECTORS = (
    "textarea",
    "form textarea",
    "textarea[placeholder]",
    "[data-testid*=\"prompt\"] textarea",
    "[contenteditable=\"true\"]",
    "[role=\"textbox\"]",
)

def _env_flag(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() not in {"0", "false", "no", "off"}

def _browser_channel() -> str | None:
    value = (os.getenv("LOVART_BROWSER_CHANNEL") or "chrome").strip()
    return value or None

def _load_playwright():
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    return sync_playwright, PlaywrightTimeoutError

def check_lovart_requirements() -> bool:
    try:
        _load_playwright()
        return True
    except Exception:
        return False

def _launch_context(headless: bool):
    sync_playwright, _ = _load_playwright()
    LOVART_SESSION_DIR.mkdir(parents=True, exist_ok=True)
    playwright = sync_playwright().start()
    launch_kwargs: dict[str, Any] = {
        "user_data_dir": str(LOVART_SESSION_DIR),
        "headless": headless,
        "viewport": {"width": 1440, "height": 960},
        "ignore_https_errors": True,
    }
    channel = _browser_channel()
    if channel:
        launch_kwargs["channel"] = channel
    try:
        context = playwright.chromium.launch_persistent_context(**launch_kwargs)
    except Exception:
        launch_kwargs.pop("channel", None)
        context = playwright.chromium.launch_persistent_context(**launch_kwargs)
    return playwright, context

def _open_page(context):
    page = context.pages[0] if context.pages else context.new_page()
    page.goto(LOVART_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)
    return page

def _find_input(page):
    _, PlaywrightTimeoutError = _load_playwright()
    for selector in INPUT_SELECTORS:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=4000)
            return locator, selector
        except PlaywrightTimeoutError:
            continue
    raise RuntimeError(
        "Could not find the Lovart prompt input. Run setup mode once and confirm the composer is visible."
    )

def prime_lovart_session(headless: bool = False) -> str:
    playwright = None
    context = None
    try:
        playwright, context = _launch_context(headless=headless)
        page = _open_page(context)
        print(f"Lovart opened at {page.url}")
        print(f"Session directory: {LOVART_SESSION_DIR}")
        print("Log in manually, then press Enter here to save the session and close the browser.")
        input()
        return tool_result(success=True, mode="setup", sessionDir=str(LOVART_SESSION_DIR), currentUrl=page.url)
    finally:
        if context is not None:
            context.close()
        if playwright is not None:
            playwright.stop()

def lovart_send_prompt(prompt: str, headless: bool | None = None) -> str:
    if not prompt or not prompt.strip():
        return tool_error("prompt is required")

    if not check_lovart_requirements():
        return tool_error(
            "Playwright is not installed in the Hermes runtime",
            installHint="/Users/vincentlai/.hermes/hermes-agent/venv/bin/python -m pip install playwright",
        )

    playwright = None
    context = None
    resolved_headless = _env_flag("LOVART_HEADLESS", True) if headless is None else headless
    try:
        playwright, context = _launch_context(headless=resolved_headless)
        page = _open_page(context)
        prompt_input, selector = _find_input(page)
        prompt_input.click(timeout=10000)
        prompt_input.fill(prompt.strip(), timeout=10000)
        prompt_input.press("Enter", timeout=10000)
        page.wait_for_timeout(5000)
        return tool_result(
            success=True,
            tool="lovart_send",
            prompt=prompt.strip(),
            url=page.url,
            sessionDir=str(LOVART_SESSION_DIR),
            selector=selector,
            headless=resolved_headless,
            message="Prompt submitted to Lovart.ai and left open for 5 seconds to confirm generation start.",
        )
    except Exception as exc:
        current_url = None
        screenshot_path = None
        if context is not None:
            try:
                page = context.pages[0] if context.pages else None
                if page is not None:
                    current_url = page.url
                    screenshot_path = LOVART_SESSION_DIR / "lovart_last_error.png"
                    page.screenshot(path=str(screenshot_path), full_page=True)
            except Exception:
                pass
        return tool_error(
            f"Lovart automation failed: {type(exc).__name__}: {exc}",
            currentUrl=current_url,
            screenshot=str(screenshot_path) if screenshot_path else None,
            sessionDir=str(LOVART_SESSION_DIR),
        )
    finally:
        if context is not None:
            context.close()
        if playwright is not None:
            playwright.stop()

LOVART_SEND_SCHEMA = {
    "name": "lovart_send",
    "description": "Send a design prompt to Lovart.ai using a saved persistent browser session.",
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The design prompt to send to Lovart.ai.",
            }
        },
        "required": ["prompt"],
    },
}

def _handle_lovart_send(args, **_kwargs):
    return lovart_send_prompt(args.get("prompt", ""))

registry.register(
    name="lovart_send",
    toolset="browser",
    schema=LOVART_SEND_SCHEMA,
    handler=_handle_lovart_send,
    check_fn=check_lovart_requirements,
    requires_env=[],
    is_async=False,
    emoji="🎨",
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lovart.ai automation helper for Hermes")
    parser.add_argument("prompt", nargs="?", default="", help="Prompt to send to Lovart.ai")
    parser.add_argument("--setup", action="store_true", help="Open Lovart with the persistent session and wait for manual login")
    parser.add_argument("--headful", action="store_true", help="Disable headless mode for manual testing")
    args = parser.parse_args()

    if args.setup:
        print(prime_lovart_session(headless=False))
    else:
        print(lovart_send_prompt(args.prompt, headless=not args.headful))
