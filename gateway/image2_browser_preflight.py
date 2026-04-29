"""Hermes-owned Image2 browser/CDP preflight contract.

This module is deliberately verification-only. It validates a caller-provided or
job-local browser state snapshot before any future ChatGPT/OpenCLI generation
step is allowed to run. It never opens a browser, never starts OpenCLI, and never
falls back to an about:blank/new tab.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

BROWSER_ENV_OPTIONS = ("OPENCLI_CDP_URL", "CHATGPT_BROWSER_CDP_URL")
BROWSER_STATE_ENV = "IMAGE2_BROWSER_STATE_JSON"
BROWSER_STATE_FILES = ("browser_state.json", "browser_preflight_input.json")
CHATGPT_HOSTS = {"chatgpt.com", "www.chatgpt.com", "chat.openai.com"}
BLANK_URLS = {"about:blank", "chrome://newtab", "edge://newtab", "about:newtab"}


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_browser_state(
    *,
    job_dir: Path,
    environ: Mapping[str, str],
    browser_state: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    if browser_state is not None:
        return dict(browser_state), "argument", None

    env_path = str(environ.get(BROWSER_STATE_ENV) or "").strip()
    candidate_paths: list[Path] = []
    if env_path:
        candidate_paths.append(Path(env_path).expanduser())
    candidate_paths.extend(Path(job_dir) / name for name in BROWSER_STATE_FILES)

    for path in candidate_paths:
        if not path.is_file():
            continue
        try:
            value = _load_json(path)
        except Exception as exc:  # noqa: BLE001 - convert to fail-closed reason
            return None, str(path), f"browser_state_invalid: {exc}"
        if isinstance(value, Mapping):
            return dict(value), str(path), None
        return None, str(path), "browser_state_invalid: expected object"
    return None, None, None


def _has_cdp_url(environ: Mapping[str, str], state: Mapping[str, Any] | None) -> bool:
    if any(str(environ.get(key) or "").strip() for key in BROWSER_ENV_OPTIONS):
        return True
    if state and str(state.get("cdp_url") or state.get("browser_ws_endpoint") or "").strip():
        return True
    return False


def _active_url(state: Mapping[str, Any] | None) -> str:
    if not state:
        return ""
    return str(state.get("active_url") or state.get("url") or state.get("page_url") or "").strip()


def _url_reason(url: str) -> str | None:
    text = str(url or "").strip()
    lowered = text.lower()
    if not text:
        return "active_url_missing"
    if lowered in BLANK_URLS or lowered.startswith("about:"):
        return "blank_or_new_tab"
    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    if host not in CHATGPT_HOSTS:
        return "non_chatgpt_page"
    return None


def evaluate_browser_preflight(
    *,
    job_dir: Path,
    environ: Mapping[str, str] | None = None,
    browser_state: Mapping[str, Any] | None = None,
    write_result: bool = True,
) -> dict[str, Any]:
    """Return a fail-closed browser/CDP readiness decision.

    A passing result means only that a sanitized browser-state snapshot claims an
    already-reachable ChatGPT page. It does not prove generation worked and it
    never starts generation by itself.
    """
    root = Path(job_dir)
    env = dict(environ or {})
    state, state_source, load_error = _load_browser_state(job_dir=root, environ=env, browser_state=browser_state)
    active_url = _active_url(state)
    reasons: list[str] = []

    cdp_present = _has_cdp_url(env, state)
    if not cdp_present:
        reasons.append("cdp_url_missing")

    if load_error:
        reasons.append("browser_state_invalid")
    elif state is None:
        reasons.append("browser_state_missing")
    else:
        reachable = state.get("cdp_reachable")
        if reachable is not True:
            reasons.append("cdp_unreachable" if reachable is False else "cdp_reachability_unverified")
        url_reason = _url_reason(active_url)
        if url_reason:
            reasons.append(url_reason)

    result = {
        "status": "pass" if not reasons else "failed",
        "reasons": reasons,
        "cdp_url_present": cdp_present,
        "state_source": state_source,
        "active_url": active_url,
        "title": str((state or {}).get("title") or ""),
        "note": "preflight-only; no browser, OpenCLI, ChatGPT, Gemini, or Feishu side effect was run",
    }
    if load_error:
        result["state_error"] = load_error
    if write_result:
        root.mkdir(parents=True, exist_ok=True)
        (root / "browser_preflight_result.json").write_text(_safe_json(result), encoding="utf-8")
    return result
