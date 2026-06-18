"""
Inspector HTTP server — read-only meta API for external containers.

Allows external Docker containers (ClaudeCode, Antigravity, etc.) to query
the native HermesAgent instance for public status, skills, and configuration.

Security principles:
- GET-only endpoints
- No API keys, tokens, auth.json, .env, sessions, or memories exposed
- Sensitive config keys (api_key, token, secret, password) are structurally excluded
- Binds to 127.0.0.1 by default; override via HERMES_INSPECTOR_HOST / HERMES_INSPECTOR_PORT
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    web = None  # type: ignore[assignment]
    AIOHTTP_AVAILABLE = False

logger = logging.getLogger(__name__)

# Regex: catches pattern-based variants (api_key, API_KEY, ApiKey, …).
_SENSITIVE_KEY_PATTERNS = re.compile(
    r"(api[_-]?key|apikey|token|secret|password|passwd|auth|credential|bearer)",
    re.IGNORECASE,
)

# Exact-match allowlist for common sensitive key names that the regex may miss:
# abbreviations ("pass"), hyphenated forms ("api-key" → normalized), and
# compound names whose substrings don't trigger the regex anchors.
_SENSITIVE_KEY_SET: frozenset = frozenset({
    "api_key", "apikey",
    "token", "access_token", "refresh_token", "id_token",
    "secret", "client_secret", "app_secret", "signing_secret", "webhook_secret",
    "password", "passwd", "pass",
    "auth", "authorization",
    "credential", "credentials",
    "bearer",
    "private_key", "privatekey", "signing_key",
    "session_key", "session_token",
    "hmac_key", "encryption_key",
})


def _is_sensitive_key(key: str) -> bool:
    """Return True if *key* should be redacted from public output.

    Two complementary strategies so neither alone is a single point of failure:
    the regex catches pattern-based variants; the exact-match set catches
    abbreviated or hyphenated forms the regex might miss.
    """
    normalized = str(key).lower().replace("-", "_")
    return normalized in _SENSITIVE_KEY_SET or bool(_SENSITIVE_KEY_PATTERNS.search(str(key)))


# Frontmatter description extractor
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_DESCRIPTION_RE = re.compile(r"^description:\s*(.+)$", re.MULTILINE)
_NAME_RE = re.compile(r"^name:\s*(.+)$", re.MULTILINE)
_CATEGORY_RE = re.compile(r"^\s*category:\s*(.+)$", re.MULTILINE)




def _extract_frontmatter(text: str) -> dict:
    """Extract key-value pairs from a SKILL.md YAML frontmatter block."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    front = m.group(1)
    result: dict = {}

    name_m = _NAME_RE.search(front)
    if name_m:
        result["name"] = name_m.group(1).strip()

    desc_m = _DESCRIPTION_RE.search(front)
    if desc_m:
        result["description"] = desc_m.group(1).strip()

    cat_m = _CATEGORY_RE.search(front)
    if cat_m:
        result["category"] = cat_m.group(1).strip()

    return result


def _scrub_sensitive(obj: Any, _depth: int = 0) -> Any:
    """Recursively remove sensitive keys from a dict using regex + allowlist."""
    if _depth > 20:
        return obj
    if isinstance(obj, dict):
        return {
            k: _scrub_sensitive(v, _depth + 1)
            for k, v in obj.items()
            if not _is_sensitive_key(k)
        }
    if isinstance(obj, list):
        return [_scrub_sensitive(item, _depth + 1) for item in obj]
    return obj


class InspectorServer:
    """Read-only HTTP server exposing HermesAgent public metadata."""

    def __init__(
        self,
        host: str,
        port: int,
        gateway_state_file: str,
        hermes_home: str,
    ) -> None:
        if not AIOHTTP_AVAILABLE:
            raise RuntimeError(
                "aiohttp is required for InspectorServer. "
                "Install with: pip install aiohttp"
            )
        self._host = host
        self._port = port
        self._gateway_state_file = Path(gateway_state_file)
        self._hermes_home = Path(hermes_home)
        self._skills_dir = self._hermes_home / "skills"
        self._config_file = self._hermes_home / "config.yaml"
        self._start_time = time.monotonic()
        self._runner: Optional[Any] = None
        self._site: Optional[Any] = None

    _LOCALHOST_BINDS = {"127.0.0.1", "::1", "localhost"}

    def _cors_headers(self) -> dict:
        # Omit CORS headers when bound to a non-loopback interface so that
        # browsers cannot make cross-origin requests to an Inspector exposed
        # on 0.0.0.0 (e.g. inside Docker).
        if self._host not in self._LOCALHOST_BINDS:
            return {}
        return {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }

    def _json_response(self, data: Any, status: int = 200) -> "web.Response":
        return web.Response(
            text=json.dumps(data, ensure_ascii=False),
            status=status,
            content_type="application/json",
            headers=self._cors_headers(),
        )

    # ── Internal helpers ──────────────────────────────────────────────

    def _read_gateway_state(self) -> dict:
        """Read gateway_state.json, returning empty dict on any error."""
        try:
            raw = self._gateway_state_file.read_text(encoding="utf-8").strip()
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _read_config_yaml(self) -> dict:
        """Read config.yaml as a plain dict; returns empty dict on any error."""
        try:
            import yaml  # type: ignore[import]
            raw = self._config_file.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _iter_skill_dirs(self):
        """Yield (slug, skill_md_path) for every SKILL.md under the skills dir.

        Follows symlinks (most installed skills are symlinked from ~/.agents/skills/).
        Supports flat layout (skill-name/SKILL.md) and one-level nested layout
        (category/skill-name/SKILL.md).  Hidden directories (starting with '.')
        are skipped.
        """
        if not self._skills_dir.is_dir():
            return
        for top in sorted(self._skills_dir.iterdir()):
            if top.name.startswith("."):
                continue
            if not top.is_dir():          # follows symlinks
                continue
            direct = top / "SKILL.md"
            if direct.is_file():
                yield top.name, direct
                continue
            # Nested: category/skill-name/SKILL.md
            for sub in sorted(top.iterdir()):
                if sub.name.startswith(".") or not sub.is_dir():
                    continue
                nested = sub / "SKILL.md"
                if nested.is_file():
                    yield f"{top.name}/{sub.name}", nested

    def _list_skills(self) -> list[dict]:
        """Scan ~/.hermes/skills/ and return a list of public skill metadata."""
        skills = []
        for slug, skill_md in self._iter_skill_dirs():
            try:
                text = skill_md.read_text(encoding="utf-8")
            except OSError:
                continue
            meta = _extract_frontmatter(text)
            skills.append({
                "slug": slug,
                "name": meta.get("name") or slug.split("/")[-1],
                "category": meta.get("category"),
                "description": meta.get("description"),
            })
        return skills

    def _get_skill_content(self, slug: str) -> Optional[str]:
        """Return the full SKILL.md text for a slug (flat or nested), or None.

        Path traversal is prevented by the allowlist regex — no '..' components
        are possible, so we do NOT resolve symlinks (most skills are symlinked
        from ~/.agents/skills/ and resolving breaks the relative_to check).
        """
        # Allow: letters, digits, hyphens, underscores, and ONE internal slash
        if not re.match(r"^[a-zA-Z0-9_\-]+(/[a-zA-Z0-9_\-]+)?$", slug):
            return None
        skill_md = self._skills_dir / slug / "SKILL.md"
        if not skill_md.is_file():   # follows symlinks — correct
            return None
        try:
            return skill_md.read_text(encoding="utf-8")
        except OSError:
            return None

    # ── Route handlers ────────────────────────────────────────────────

    async def _handle_health(self, request: "web.Request") -> "web.Response":
        return self._json_response({
            "status": "ok",
            "pid": os.getpid(),
            "uptime_seconds": round(time.monotonic() - self._start_time, 2),
        })

    async def _handle_status(self, request: "web.Request") -> "web.Response":
        state = self._read_gateway_state()
        config = self._read_config_yaml()

        model_cfg = config.get("model", {}) if isinstance(config.get("model"), dict) else {}
        runtime_cfg = config.get("runtime", {}) if isinstance(config.get("runtime"), dict) else {}

        return self._json_response({
            "model": model_cfg.get("default"),
            "provider": model_cfg.get("provider"),
            "api_mode": runtime_cfg.get("api_mode"),
            "gateway_state": state.get("gateway_state"),
            "active_agents": state.get("active_agents", 0),
            "platforms": state.get("platforms", {}),
        })

    async def _handle_skills_list(self, request: "web.Request") -> "web.Response":
        return self._json_response(self._list_skills())

    async def _handle_skill_detail(self, request: "web.Request") -> "web.Response":
        # Support both flat (/skills/name) and nested (/skills/category/name) slugs
        slug = request.match_info.get("slug", "")
        content = self._get_skill_content(slug)
        if content is None:
            return self._json_response(
                {"error": "not_found", "message": f"Skill '{slug}' not found"},
                status=404,
            )
        return self._json_response({"slug": slug, "content": content})

    async def _handle_config_public(self, request: "web.Request") -> "web.Response":
        config = self._read_config_yaml()

        # Allow-list approach: only expose known safe top-level sections,
        # then scrub any remaining sensitive keys inside them.
        safe_keys = {"model", "agent", "toolsets", "compression", "language", "locale", "ui"}
        public: dict = {}
        for key in safe_keys:
            if key in config:
                public[key] = _scrub_sensitive(config[key])

        return self._json_response(public)

    async def _handle_options(self, request: "web.Request") -> "web.Response":
        """CORS preflight handler."""
        return web.Response(status=204, headers=self._cors_headers())

    # ── Lifecycle ─────────────────────────────────────────────────────

    def _build_app(self) -> "web.Application":
        app = web.Application()
        app.router.add_get("/health", self._handle_health)
        app.router.add_get("/status", self._handle_status)
        app.router.add_get("/skills", self._handle_skills_list)
        # {slug:.+} matches both flat (name) and nested (category/name) slugs
        app.router.add_get(r"/skills/{slug:.+}", self._handle_skill_detail)
        app.router.add_get("/config/public", self._handle_config_public)
        # CORS preflight
        app.router.add_route("OPTIONS", "/{path_info:.*}", self._handle_options)
        return app

    async def start(self) -> None:
        """Start the Inspector HTTP server."""
        app = self._build_app()
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(
            self._runner,
            host=self._host,
            port=self._port,
        )
        await self._site.start()
        logger.debug(
            "Inspector server started on http://%s:%s", self._host, self._port
        )

    async def stop(self) -> None:
        """Stop the Inspector HTTP server gracefully."""
        if self._runner is not None:
            try:
                await self._runner.cleanup()
            except Exception as exc:
                logger.debug("Inspector server cleanup error: %s", exc)
            self._runner = None
            self._site = None
            logger.debug("Inspector server stopped")
