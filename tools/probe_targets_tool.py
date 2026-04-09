#!/usr/bin/env python3
"""
Probe Targets Tool — parallel HTTP probe across a declarative target catalogue.

Given a value (e.g. a username) and a target set name (e.g. ``usernames``),
this tool fetches all targets in parallel and classifies each response as a
hit / miss / blocked / error / invalid.

The target catalogue is a YAML file at ``~/.hermes/probe-targets/<set>.yaml``
seeded by ``scripts/sync_sherlock_data.py`` from the sherlock-project site
database. The same tool can serve any future "check N targets in parallel"
use case (status pages, API health, price scrapers) simply by adding a new
YAML file — no code changes required.

Detection methods supported (per-target ``detect:`` field):
    status_code   — hit iff response.status_code != error_status (and < 400)
    body_contains — hit iff ANY of error_strings appears in the body
    body_absent   — hit iff NONE of error_strings appears in the body
    body_regex    — hit iff the regex matches the body
    redirects_to  — hit iff the final URL does NOT equal redirect_to

Result statuses:
    hit     — target confirms the value exists
    miss    — target confirms the value does not exist
    blocked — WAF / captcha / rate-limit (probe was inconclusive)
    error   — network / timeout / parse failure
    invalid — pre-validation regex rejected the value

Safety: the target catalogue is operator-controlled (YAML file), not LLM-
controlled. Only the *value* comes from the LLM, so SSRF is not a vector.
Values are pre-validated against a per-target or global regex before any
network I/O happens — this implements the
``feedback_validate_llm_tool_inputs`` guidance.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx

try:
    import yaml
except ImportError:  # pragma: no cover — pyyaml is a hard dep of hermes
    yaml = None  # type: ignore[assignment]

from tools.registry import registry

logger = logging.getLogger(__name__)


# ─── Constants ────────────────────────────────────────────────────────────────

PROBE_TARGETS_DIR = Path.home() / ".hermes" / "probe-targets"
DEFAULT_CONCURRENCY = 20
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.6 Safari/605.1.15"
)

# Max hits/errors to return to the LLM. Prevents a single call from blowing
# the context window if the user probes a common name that exists everywhere.
MAX_RESULTS_RETURNED = 60

# Cached loaded catalogues, keyed by YAML path + mtime. Reloaded on file change.
_CATALOGUE_CACHE: dict[tuple[str, float], dict[str, Any]] = {}


# ─── Result dataclass ─────────────────────────────────────────────────────────


@dataclass
class ProbeResult:
    name: str
    url: str
    status: str  # hit | miss | blocked | error | invalid
    http_status: Optional[int] = None
    elapsed_ms: int = 0
    detected_by: str = ""
    category: Optional[str] = None
    note: str = ""


# ─── Catalogue loading ────────────────────────────────────────────────────────


def _catalogue_path(target_set: str) -> Path:
    """Resolve a target-set name to a YAML file path."""
    # Strip any path characters an LLM might pass — we accept only a bare name.
    safe_name = re.sub(r"[^A-Za-z0-9_-]", "", target_set)
    if not safe_name:
        raise ValueError(f"Invalid target_set name: {target_set!r}")
    return PROBE_TARGETS_DIR / f"{safe_name}.yaml"


def _load_catalogue(target_set: str) -> dict[str, Any]:
    """Load a target catalogue YAML, cached by (path, mtime) for reuse."""
    if yaml is None:
        raise RuntimeError("PyYAML is not installed; cannot load probe targets")

    path = _catalogue_path(target_set)
    if not path.exists():
        raise FileNotFoundError(
            f"Target catalogue not found: {path}. "
            f"Run `python hermes-agent/scripts/sync_sherlock_data.py` to generate "
            f"the default 'usernames' catalogue."
        )

    mtime = path.stat().st_mtime
    cache_key = (str(path), mtime)
    cached = _CATALOGUE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    with path.open("r", encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}

    if not isinstance(doc, dict) or not isinstance(doc.get("targets"), list):
        raise ValueError(f"Catalogue at {path} has no 'targets' list")

    _CATALOGUE_CACHE[cache_key] = doc
    return doc


# ─── Value pre-validation ─────────────────────────────────────────────────────


def _compile_regex(pattern: Optional[str]) -> Optional[re.Pattern[str]]:
    if not pattern:
        return None
    try:
        return re.compile(pattern)
    except re.error as exc:
        logger.warning("Invalid regex %r: %s — ignoring", pattern, exc)
        return None


def _validate_value(
    value: str,
    target: dict[str, Any],
    global_regex: Optional[re.Pattern[str]],
) -> Optional[str]:
    """Return a reject reason string or None if the value passes."""
    per_target = _compile_regex(target.get("value_regex"))
    regex = per_target or global_regex
    if regex and not regex.match(value):
        return f"value does not match {regex.pattern}"
    return None


# ─── Placeholder substitution ─────────────────────────────────────────────────


def _interpolate(obj: Any, value: str) -> Any:
    """Replace ``{value}`` inside strings, dict values, and list items."""
    if isinstance(obj, str):
        return obj.replace("{value}", value)
    if isinstance(obj, dict):
        return {k: _interpolate(v, value) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_interpolate(v, value) for v in obj]
    return obj


# ─── WAF / block detection ────────────────────────────────────────────────────


_WAF_BODY_MARKERS = (
    "cloudflare",
    "just a moment",
    "please enable javascript and cookies",
    "attention required",
    "access denied",
    "captcha",
)


def _looks_blocked(status_code: int, body_lower: str) -> bool:
    """Heuristic: did a WAF/captcha page short-circuit the real response?"""
    if status_code == 429:
        return True
    if status_code in (403, 503) and any(m in body_lower for m in _WAF_BODY_MARKERS):
        return True
    if status_code == 200 and "captcha" in body_lower and "just a moment" in body_lower:
        return True
    return False


# ─── Per-target probe ─────────────────────────────────────────────────────────


async def _probe_one(
    target: dict[str, Any],
    value: str,
    client: httpx.AsyncClient,
    timeout: float,
    global_regex: Optional[re.Pattern[str]],
) -> ProbeResult:
    """Probe a single target and classify the response."""
    name = target.get("name", "<unnamed>")
    display_url = _interpolate(target.get("url", ""), value)
    category = target.get("category")

    # Pre-validate before spending any network I/O.
    reject = _validate_value(value, target, global_regex)
    if reject:
        return ProbeResult(
            name=name,
            url=display_url,
            status="invalid",
            category=category,
            detected_by="pre_validate",
            note=reject,
        )

    probe_url = _interpolate(target.get("url_probe") or target.get("url", ""), value)
    method = (target.get("method") or "GET").upper()
    headers = _interpolate(target.get("headers") or {}, value)
    body = _interpolate(target.get("body"), value) if target.get("body") is not None else None
    detect = target.get("detect", "status_code")

    started = time.monotonic()
    try:
        # httpx follow_redirects=True handles 3xx chains; we inspect response.url
        # for redirects_to detection.
        response = await client.request(
            method,
            probe_url,
            headers=headers or None,
            json=body if isinstance(body, (dict, list)) else None,
            content=body if isinstance(body, (str, bytes)) else None,
            timeout=timeout,
            follow_redirects=True,
        )
    except httpx.TimeoutException:
        return ProbeResult(
            name=name,
            url=display_url,
            status="error",
            category=category,
            elapsed_ms=int((time.monotonic() - started) * 1000),
            detected_by="timeout",
            note=f"timeout after {timeout}s",
        )
    except httpx.HTTPError as exc:
        return ProbeResult(
            name=name,
            url=display_url,
            status="error",
            category=category,
            elapsed_ms=int((time.monotonic() - started) * 1000),
            detected_by="http_error",
            note=f"{type(exc).__name__}: {exc}",
        )
    except Exception as exc:  # noqa: BLE001 — defensive: one bad target mustn't kill the run
        logger.debug("Unexpected error probing %s: %s", name, exc)
        return ProbeResult(
            name=name,
            url=display_url,
            status="error",
            category=category,
            elapsed_ms=int((time.monotonic() - started) * 1000),
            detected_by="exception",
            note=f"{type(exc).__name__}: {exc}",
        )

    elapsed_ms = int((time.monotonic() - started) * 1000)
    http_status = response.status_code

    # Read body lazily — only when the detect method needs it.
    needs_body = detect in {"body_contains", "body_absent", "body_regex"}
    body_text = ""
    if needs_body or http_status in (403, 429, 503):
        try:
            body_text = response.text
        except Exception:  # noqa: BLE001
            body_text = ""

    if _looks_blocked(http_status, body_text.lower()):
        return ProbeResult(
            name=name,
            url=display_url,
            status="blocked",
            http_status=http_status,
            category=category,
            elapsed_ms=elapsed_ms,
            detected_by="waf_heuristic",
            note=f"HTTP {http_status} with WAF markers",
        )

    # Apply the detection rule.
    hit = False
    detected_by = detect

    if detect == "status_code":
        error_status = int(target.get("error_status", 404))
        hit = http_status != error_status and http_status < 400
    elif detect == "body_contains":
        error_strings = target.get("error_strings") or []
        hit = any(s in body_text for s in error_strings)
    elif detect == "body_absent":
        error_strings = target.get("error_strings") or []
        # A hit means NONE of the "not found" markers are present.
        hit = not any(s in body_text for s in error_strings)
    elif detect == "body_regex":
        pattern = _compile_regex(target.get("body_regex"))
        hit = bool(pattern and pattern.search(body_text))
    elif detect == "redirects_to":
        redirect_to = target.get("redirect_to") or ""
        final_url = str(response.url)
        # Treat as hit iff the final URL does not match the "not found" destination.
        # Normalise trailing slashes to avoid spurious misses.
        hit = final_url.rstrip("/") != redirect_to.rstrip("/")
    else:
        return ProbeResult(
            name=name,
            url=display_url,
            status="error",
            http_status=http_status,
            category=category,
            elapsed_ms=elapsed_ms,
            detected_by="config",
            note=f"unknown detect type: {detect}",
        )

    # For body_absent, a clear 404 always means miss regardless of body content —
    # sherlock relies on this implicitly because body-based sites usually serve
    # their "not found" page at 200. When they 404, that's still definitive.
    if detect == "body_absent" and http_status == 404:
        hit = False

    return ProbeResult(
        name=name,
        url=display_url,
        status="hit" if hit else "miss",
        http_status=http_status,
        category=category,
        elapsed_ms=elapsed_ms,
        detected_by=detected_by,
    )


# ─── Target filtering ─────────────────────────────────────────────────────────


def _filter_targets(
    targets: list[dict[str, Any]],
    categories: Optional[list[str]],
    target_names: Optional[list[str]],
) -> list[dict[str, Any]]:
    """Apply optional category + name filters, preserving order."""
    result = targets
    if categories:
        wanted = {c.lower() for c in categories}
        result = [t for t in result if str(t.get("category", "")).lower() in wanted]
    if target_names:
        wanted_names = {n.lower() for n in target_names}
        result = [t for t in result if str(t.get("name", "")).lower() in wanted_names]
    return result


# ─── Top-level handler ────────────────────────────────────────────────────────


async def probe_targets_tool(
    value: str,
    target_set: str = "usernames",
    categories: Optional[list[str]] = None,
    target_names: Optional[list[str]] = None,
    concurrency: Optional[int] = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Main handler. Returns a JSON string."""
    value = (value or "").strip()
    if not value:
        return json.dumps({"error": "value is required"})

    try:
        doc = _load_catalogue(target_set)
    except FileNotFoundError as exc:
        return json.dumps({"error": str(exc)})
    except Exception as exc:
        return json.dumps({"error": f"failed to load catalogue: {type(exc).__name__}: {exc}"})

    targets = _filter_targets(doc.get("targets", []), categories, target_names)
    if not targets:
        return json.dumps({"error": "no targets matched the filters"})

    # Global pre-validation regex from catalogue header (falls back to None)
    pre = doc.get("pre_validate") or {}
    global_regex = _compile_regex(pre.get("value_regex"))

    effective_concurrency = int(concurrency or doc.get("concurrency") or DEFAULT_CONCURRENCY)
    effective_concurrency = max(1, min(effective_concurrency, 64))

    semaphore = asyncio.Semaphore(effective_concurrency)
    started = time.monotonic()

    limits = httpx.Limits(
        max_connections=effective_concurrency * 2,
        max_keepalive_connections=effective_concurrency,
    )
    async with httpx.AsyncClient(
        limits=limits,
        headers={"User-Agent": DEFAULT_USER_AGENT},
        http2=False,
    ) as client:

        async def bounded_probe(target: dict[str, Any]) -> ProbeResult:
            async with semaphore:
                return await _probe_one(
                    target=target,
                    value=value,
                    client=client,
                    timeout=timeout_seconds,
                    global_regex=global_regex,
                )

        results: list[ProbeResult] = await asyncio.gather(
            *(bounded_probe(t) for t in targets),
            return_exceptions=False,
        )

    elapsed_ms = int((time.monotonic() - started) * 1000)

    # Aggregate
    by_status: dict[str, list[ProbeResult]] = {
        "hit": [],
        "miss": [],
        "blocked": [],
        "error": [],
        "invalid": [],
    }
    for r in results:
        by_status.setdefault(r.status, []).append(r)

    # Sort hits by elapsed (fastest first) for a cleaner report.
    by_status["hit"].sort(key=lambda r: r.elapsed_ms)

    def _serialise(rs: list[ProbeResult], limit: int) -> list[dict[str, Any]]:
        return [asdict(r) for r in rs[:limit]]

    payload = {
        "target_set": target_set,
        "value": value,
        "summary": {
            "total": len(results),
            "hits": len(by_status["hit"]),
            "misses": len(by_status["miss"]),
            "blocked": len(by_status["blocked"]),
            "errors": len(by_status["error"]),
            "invalid": len(by_status["invalid"]),
            "concurrency": effective_concurrency,
            "elapsed_ms": elapsed_ms,
        },
        "hits": _serialise(by_status["hit"], MAX_RESULTS_RETURNED),
        "blocked": _serialise(by_status["blocked"], 20),
        "errors": _serialise(by_status["error"], 20),
    }

    if len(by_status["hit"]) > MAX_RESULTS_RETURNED:
        payload["summary"]["hits_truncated"] = True

    return json.dumps(payload, ensure_ascii=False)


# ─── Registry wiring ──────────────────────────────────────────────────────────


PROBE_TARGETS_SCHEMA = {
    "name": "probe_targets",
    "description": (
        "Probe a value (e.g. a username) across a declarative catalogue of websites "
        "in parallel. Returns a structured list of sites where the value exists ('hits'), "
        "plus counts of misses, blocked (WAF/captcha), errors, and invalid. "
        "The default target set 'usernames' covers ~460 social/forum/dev/creative platforms "
        "sourced from the sherlock-project database. Per-site username regexes are pre-validated "
        "before any network I/O. Use this for OSINT reconnaissance, username availability checks, "
        "or any other 'check N sites in parallel' task by swapping target_set."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "value": {
                "type": "string",
                "description": "The value to probe (e.g. a username). Pre-validated against per-target regex.",
            },
            "target_set": {
                "type": "string",
                "description": "Target catalogue name under ~/.hermes/probe-targets/. Default: 'usernames'.",
                "default": "usernames",
            },
            "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional: only probe targets in these categories.",
            },
            "target_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional: only probe targets whose name matches (e.g. ['GitHub', 'Twitter']).",
            },
            "concurrency": {
                "type": "integer",
                "description": "Max concurrent HTTP requests (default: catalogue default, usually 20, max 64).",
            },
            "timeout_seconds": {
                "type": "number",
                "description": "Per-request timeout in seconds. Default: 10.",
            },
        },
        "required": ["value"],
    },
}


def _check_probe_targets_available() -> bool:
    """Toolset availability: at least the default catalogue must exist."""
    if yaml is None:
        return False
    try:
        return _catalogue_path("usernames").exists()
    except Exception:
        return False


registry.register(
    name="probe_targets",
    toolset="web",
    schema=PROBE_TARGETS_SCHEMA,
    handler=lambda args, **kw: probe_targets_tool(
        value=args.get("value") or "",
        target_set=args.get("target_set") or "usernames",
        categories=args.get("categories"),
        target_names=args.get("target_names"),
        concurrency=args.get("concurrency"),
        timeout_seconds=float(args.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS),
    ),
    check_fn=_check_probe_targets_available,
    is_async=True,
    emoji="🎯",
    mutates=False,
    cache_config={"ttl": 300},  # 5-min cache — username existence changes slowly
)
