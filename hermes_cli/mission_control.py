"""Privacy-minimized Mission Control snapshot for the Hermes dashboard.

This module turns the external Claude Agent blueprint into a live Hermes
operations cockpit.  It deliberately separates:

- static source coverage (what the guide contains), from
- live readiness evidence (what this Hermes runtime currently exposes).

The dashboard should never need to read local files directly or receive raw
logs, prompts, commands, env values, or chat content.  Keep this module as the
single server-only aggregation boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Iterable

from hermes_cli.config import get_hermes_home, load_config

SOURCE_URL = "https://claude-agent-2.vercel.app/"

BLUEPRINT_STEPS: list[dict[str, Any]] = [
    {
        "id": "step-1",
        "number": "01",
        "title": "Create your Telegram bot",
        "domain": "interface",
        "part": "MVP",
        "summary": "Create a BotFather token, collect the allowed Telegram user ID, and lock the bot to the operator.",
        "route": "/channels",
    },
    {
        "id": "step-2",
        "number": "02",
        "title": "Get an LLM key",
        "domain": "model",
        "part": "MVP",
        "summary": "Choose Anthropic, OpenRouter, Ollama, or another model provider through env/config.",
        "route": "/models",
    },
    {
        "id": "step-3",
        "number": "03",
        "title": "Bootstrap the project",
        "domain": "runtime",
        "part": "MVP",
        "summary": "Create the TypeScript project skeleton, dependencies, folders, and gitignore boundary.",
        "route": "/system",
    },
    {
        "id": "step-4",
        "number": "04",
        "title": ".env template",
        "domain": "configuration",
        "part": "MVP",
        "summary": "Centralize provider, Telegram, identity, database, and optional integration settings.",
        "route": "/env",
    },
    {
        "id": "step-5",
        "number": "05",
        "title": "Write your soul",
        "domain": "identity",
        "part": "MVP",
        "summary": "Define the operator-facing personality and personal context without reusing a public prompt verbatim.",
        "route": "/config",
    },
    {
        "id": "step-6",
        "number": "06",
        "title": "Config loader",
        "domain": "configuration",
        "part": "MVP",
        "summary": "Load typed runtime configuration from env and defaults so deployment changes do not touch code.",
        "route": "/config",
    },
    {
        "id": "step-7",
        "number": "07",
        "title": "Tier 1 + 2 — SQLite memory",
        "domain": "memory",
        "part": "MVP",
        "summary": "Store durable facts plus a rolling conversation buffer with summarisation of older messages.",
        "route": "/sessions",
    },
    {
        "id": "step-8",
        "number": "08",
        "title": "Tier 3 — Pinecone semantic memory",
        "domain": "memory",
        "part": "MVP optional",
        "summary": "Add semantic recall across many past conversations with a scoped vector database key.",
        "route": "/system",
    },
    {
        "id": "step-9",
        "number": "09",
        "title": "LLM layer",
        "domain": "model",
        "part": "MVP",
        "summary": "Wrap model calls behind a provider-agnostic chat interface.",
        "route": "/models",
    },
    {
        "id": "step-10",
        "number": "10",
        "title": "Tools — what makes it an agent",
        "domain": "tools",
        "part": "MVP",
        "summary": "Expose safe, typed tools such as shell, files, web, memory, and integrations.",
        "route": "/system",
    },
    {
        "id": "step-11",
        "number": "11",
        "title": "The agent loop (with tool-calling)",
        "domain": "agent-loop",
        "part": "MVP",
        "summary": "Build the prompt, call the LLM, execute tools, append observations, and continue until a response is ready.",
        "route": "/chat",
    },
    {
        "id": "step-12",
        "number": "12",
        "title": "Telegram bot",
        "domain": "interface",
        "part": "MVP",
        "summary": "Run the Telegram adapter with whitelist auth and text/voice message handling.",
        "route": "/channels",
    },
    {
        "id": "step-13",
        "number": "13",
        "title": "Heartbeat scheduler",
        "domain": "automation",
        "part": "MVP",
        "summary": "Schedule proactive check-ins and recurring tasks.",
        "route": "/cron",
    },
    {
        "id": "step-14",
        "number": "14",
        "title": "Tie it together",
        "domain": "runtime",
        "part": "MVP",
        "summary": "Initialize memory, semantic recall, bot adapters, and background schedulers in one entrypoint.",
        "route": "/system",
    },
    {
        "id": "step-15",
        "number": "15",
        "title": "Run it",
        "domain": "runtime",
        "part": "MVP",
        "summary": "Start the agent, message it, inspect errors, and confirm the feedback loop works.",
        "route": "/system",
    },
    {
        "id": "step-16",
        "number": "16",
        "title": "Stream responses",
        "domain": "interface",
        "part": "Beyond MVP",
        "summary": "Stream or edit live responses so long tool chains do not leave the user blind.",
        "route": "/chat",
    },
    {
        "id": "step-17",
        "number": "17",
        "title": "Reflection",
        "domain": "memory",
        "part": "Beyond MVP",
        "summary": "Run a consolidation pass that distills conversations into long-term memory.",
        "route": "/system",
    },
    {
        "id": "step-18",
        "number": "18",
        "title": "Auto-skill creation",
        "domain": "skills",
        "part": "Beyond MVP",
        "summary": "After complex successful work, capture the procedure as a portable SKILL.md.",
        "route": "/skills",
    },
    {
        "id": "step-19",
        "number": "19",
        "title": "Voice transcription",
        "domain": "voice",
        "part": "Beyond MVP",
        "summary": "Transcribe Telegram voice notes and optionally respond with voice.",
        "route": "/channels",
    },
    {
        "id": "step-20",
        "number": "20",
        "title": "Multi-user mode",
        "domain": "interface",
        "part": "Beyond MVP",
        "summary": "Namespace memory and message state per authorized user or team member.",
        "route": "/pairing",
    },
    {
        "id": "step-21",
        "number": "21",
        "title": "MCP server integration",
        "domain": "tools",
        "part": "Production-grade",
        "summary": "Attach pre-built MCP servers such as Gmail, Notion, Slack, Supabase, Linear, and GitHub.",
        "route": "/mcp",
    },
    {
        "id": "step-22",
        "number": "22",
        "title": "Permission / approval flow",
        "domain": "safety",
        "part": "Production-grade",
        "summary": "Require approval for destructive or expensive tools and keep an auto-accept escape hatch explicit.",
        "route": "/system",
    },
    {
        "id": "step-22-5",
        "number": "22½",
        "title": "Prompt-injection defence",
        "domain": "safety",
        "part": "Production-grade",
        "summary": "Treat tool outputs as untrusted, wrap them in markers, and prevent scraped/email content from issuing commands.",
        "route": "/system",
    },
    {
        "id": "step-23",
        "number": "23",
        "title": "Cost & token tracking",
        "domain": "analytics",
        "part": "Production-grade",
        "summary": "Record per-request token usage and cost so model bills do not surprise the operator.",
        "route": "/analytics",
    },
    {
        "id": "step-24",
        "number": "24",
        "title": "Mission Control dashboard",
        "domain": "dashboard",
        "part": "Production-grade",
        "summary": "Expose memory, task, cost, and runtime state through a Vite/React cockpit.",
        "route": "/mission-control",
    },
    {
        "id": "step-25",
        "number": "25",
        "title": "Hosting in production",
        "domain": "hosting",
        "part": "Production-grade",
        "summary": "Choose Docker on a VPS, Railway, or systemd/home-server hosting with safe networking.",
        "route": "/system",
    },
    {
        "id": "step-26",
        "number": "26",
        "title": "Testing",
        "domain": "quality",
        "part": "Production-grade",
        "summary": "Unit-test deterministic pieces, snapshot-test prompts, and run fake-LLM integration tests.",
        "route": "/system",
    },
]

HERMES_FEATURES: list[dict[str, str]] = [
    {"id": "H1", "title": "4-layer memory", "summary": "MEMORY.md / USER.md / SKILL.md / SQLite+FTS5 separates facts, preferences, procedures, and episodic recall.", "where": "Step 7, 17, 18", "domain": "memory"},
    {"id": "H2", "title": "GEPA reflection", "summary": "Nightly dreaming pass consolidates conversations into core memory.", "where": "Step 17", "domain": "memory"},
    {"id": "H3", "title": "Auto-skill creation", "summary": "After 5+ tool calls, the agent writes SKILL.md so future similar work is faster.", "where": "Step 18", "domain": "skills"},
    {"id": "H4", "title": "15+ messaging gateways", "summary": "Telegram, Discord, Slack, WhatsApp, Signal, Matrix, Email, SMS, iMessage, DingTalk, Feishu, and more.", "where": "Step 12 → extend", "domain": "interface"},
    {"id": "H5", "title": "6 deploy backends", "summary": "Local, Docker, SSH, Daytona, Singularity, and Modal execution backends.", "where": "Step 25", "domain": "hosting"},
    {"id": "H6", "title": "Real-time voice", "summary": "Voice in/out via CLI, Telegram, and Discord.", "where": "Step 19", "domain": "voice"},
    {"id": "H7", "title": "Pluggable memory backends", "summary": "Swap memory engines such as Mem0, Honcho, or Byterover without rewriting the agent.", "where": "Custom adapter", "domain": "memory"},
    {"id": "H8", "title": "Skill trust levels", "summary": "Builtin / Official / Trusted / Community source trust gradient for permissions.", "where": "Step 22", "domain": "safety"},
    {"id": "H9", "title": "Bounded memory budgets", "summary": "Hard caps force durable consolidation instead of prompt bloat.", "where": "Step 7 + 17", "domain": "memory"},
    {"id": "H10", "title": "TokenMix optimisation", "summary": "Reduce redundant reasoning/token paths for faster multi-step work.", "where": "Advanced", "domain": "analytics"},
    {"id": "H11", "title": "agentskills.io standard", "summary": "Skills portable across Hermes, Claude Code, Cursor, and Codex.", "where": "Step 18", "domain": "skills"},
]

OPENCLAW_FEATURES: list[dict[str, str]] = [
    {"id": "O1", "title": "22 messaging channels", "summary": "Every Hermes adapter plus iMessage, Nostr, IRC, WeChat, Twitch, and Google Chat.", "where": "Step 12 → extend", "domain": "interface"},
    {"id": "O2", "title": "Native mobile clients", "summary": "macOS, iOS, and Android clients with voice wake-word.", "where": "Out of scope", "domain": "interface"},
    {"id": "O3", "title": "ClawHub skill registry", "summary": "Distribute and install third-party skills publicly.", "where": "Step 18", "domain": "skills"},
    {"id": "O4", "title": "Multi-agent orchestration", "summary": "Spawn sub-agents in parallel for delegated tasks.", "where": "Custom — fork agent.ts", "domain": "agent-loop"},
    {"id": "O5", "title": "Sandboxed tool execution", "summary": "Run shell commands in Docker / SSH / OpenShell-style isolation.", "where": "Step 22 + 25", "domain": "safety"},
    {"id": "O6", "title": "Open Gateway Protocol", "summary": "Cross-harness federation so agents can talk to other agents.", "where": "Out of scope", "domain": "interface"},
    {"id": "O7", "title": "Per-command approval flow", "summary": "Inline approve/deny flow for destructive tool calls.", "where": "Step 22", "domain": "safety"},
    {"id": "O8", "title": "Auto-approve toggle", "summary": "Trust-level escape hatch when the operator does not want to babysit safe calls.", "where": "Step 22", "domain": "safety"},
    {"id": "O9", "title": "Live Canvas UI", "summary": "Visual editor where the agent edits files in real time.", "where": "Step 24", "domain": "dashboard"},
    {"id": "O10", "title": "Tailscale-recommended self-host", "summary": "Mesh-VPN to a home server with no public ports.", "where": "Step 25", "domain": "hosting"},
]

_STATE_WEIGHT = {"active": 100, "partial": 68, "watch": 38, "planned": 18}


@dataclass(frozen=True)
class CapabilityState:
    state: str
    score: int
    evidence: list[str]
    next: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except Exception:
        return default


def _home() -> Path:
    return Path(get_hermes_home()).expanduser().resolve()


def _compact_path(path: Path | str | None, home: Path | None = None) -> str | None:
    if path is None:
        return None
    home = home or _home()
    raw = str(path)
    try:
        p = Path(raw).expanduser().resolve()
        if p == home:
            return "~/.hermes"
        if p.is_relative_to(home):
            rel = p.relative_to(home)
            return "~/.hermes" if str(rel) == "." else f"~/.hermes/{rel.as_posix()}"
        user_home = Path.home().resolve()
        if p == user_home:
            return "~"
        if p.is_relative_to(user_home):
            return f"~/{p.relative_to(user_home).as_posix()}"
    except Exception:
        pass
    # Do not expose arbitrary absolute paths.  Keep only the terminal label.
    name = Path(raw).name
    return name or "configured"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _env_families(home: Path) -> dict[str, Any]:
    env_path = home / ".env"
    families: set[str] = set()
    configured = 0
    present_keys = 0
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"\'')
            present_keys += 1
            if value:
                configured += 1
            upper = key.upper()
            if "TELEGRAM" in upper:
                families.add("telegram")
            elif "DISCORD" in upper:
                families.add("discord")
            elif "SLACK" in upper:
                families.add("slack")
            elif "OPENROUTER" in upper:
                families.add("openrouter")
            elif "ANTHROPIC" in upper:
                families.add("anthropic")
            elif "OPENAI" in upper or "VOICE_TOOLS_OPENAI" in upper:
                families.add("openai")
            elif "PINECONE" in upper:
                families.add("pinecone")
            elif "SUPABASE" in upper:
                families.add("supabase")
            elif "GEMINI" in upper or "GOOGLE" in upper:
                families.add("gemini")
            elif "HASS" in upper or "HOMEASSISTANT" in upper:
                families.add("homeassistant")
            elif value:
                families.add("other")
    return {
        "filePresent": env_path.exists(),
        "path": _compact_path(env_path, home),
        "presentKeys": present_keys,
        "configuredKeys": configured,
        "families": sorted(families),
    }


def _state_db_metrics(home: Path) -> dict[str, Any]:
    path = home / "state.db"
    base: dict[str, Any] = {
        "dbPresent": path.exists(),
        "path": _compact_path(path, home),
        "total": 0,
        "active": 0,
        "archived": 0,
        "messages": 0,
        "toolCalls": 0,
        "inputTokens": 0,
        "outputTokens": 0,
        "reasoningTokens": 0,
        "estimatedCostUsd": 0.0,
        "sources": {},
        "recent": [],
        "latestAgeSeconds": None,
    }
    if not path.exists():
        return base
    try:
        con = sqlite3.connect(path)
        con.row_factory = sqlite3.Row
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "sessions" in tables:
            cols = {r[1] for r in con.execute("PRAGMA table_info(sessions)")}
            base["total"] = _safe_int(con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0])
            if "archived" in cols:
                base["archived"] = _safe_int(con.execute("SELECT COUNT(*) FROM sessions WHERE archived=1").fetchone()[0])
                base["active"] = max(base["total"] - base["archived"], 0)
            else:
                base["active"] = base["total"]
            for column, key in [
                ("tool_call_count", "toolCalls"),
                ("input_tokens", "inputTokens"),
                ("output_tokens", "outputTokens"),
                ("reasoning_tokens", "reasoningTokens"),
            ]:
                if column in cols:
                    base[key] = _safe_int(con.execute(f"SELECT COALESCE(SUM({column}), 0) FROM sessions").fetchone()[0])
            if "estimated_cost_usd" in cols:
                base["estimatedCostUsd"] = round(float(con.execute("SELECT COALESCE(SUM(estimated_cost_usd), 0) FROM sessions").fetchone()[0] or 0), 4)
            if "source" in cols:
                base["sources"] = {
                    str(row[0]): _safe_int(row[1])
                    for row in con.execute("SELECT source, COUNT(*) FROM sessions GROUP BY source ORDER BY COUNT(*) DESC LIMIT 12")
                }
            order_col = "started_at" if "started_at" in cols else "rowid"
            # Keep recent activity privacy-minimized: session titles and IDs can
            # be conversation-derived, so expose only coarse labels/counts/ages.
            select_cols = [c for c in ["source", "model", "started_at", "message_count"] if c in cols]
            if select_cols:
                recent = []
                for row in con.execute(f"SELECT {', '.join(select_cols)} FROM sessions ORDER BY {order_col} DESC LIMIT 6"):
                    raw = dict(row)
                    item: dict[str, Any] = {}
                    if raw.get("source"):
                        item["source"] = str(raw.get("source"))
                    if raw.get("model"):
                        item["model"] = str(raw.get("model"))
                    if "message_count" in raw:
                        item["messageCount"] = _safe_int(raw.get("message_count"), 0)
                    started = raw.get("started_at")
                    if isinstance(started, (int, float)):
                        item["startedAgeSeconds"] = max(0, int(time.time() - float(started)))
                        if base["latestAgeSeconds"] is None:
                            base["latestAgeSeconds"] = item["startedAgeSeconds"]
                    recent.append(item)
                base["recent"] = recent
        if "messages" in tables:
            base["messages"] = _safe_int(con.execute("SELECT COUNT(*) FROM messages").fetchone()[0])
        con.close()
    except Exception as exc:
        base["error"] = f"state-db-unavailable:{exc.__class__.__name__}"
    return base


def _skill_metrics(home: Path) -> dict[str, Any]:
    skill_root = home / "skills"
    files = list(skill_root.rglob("SKILL.md")) if skill_root.exists() else []
    by_category: dict[str, int] = {}
    spotlight: list[dict[str, str]] = []
    for p in files:
        try:
            rel = p.relative_to(skill_root)
            category = rel.parts[0] if len(rel.parts) > 1 else "uncategorized"
            by_category[category] = by_category.get(category, 0) + 1
            if len(spotlight) < 6:
                spotlight.append({"name": p.parent.name, "category": category})
        except Exception:
            continue
    usage = _read_json(skill_root / ".usage.json") if skill_root.exists() else None
    usage_count = len(usage) if isinstance(usage, dict) else 0
    return {
        "rootPresent": skill_root.exists(),
        "path": _compact_path(skill_root, home),
        "total": len(files),
        "usageTracked": usage_count,
        "categories": by_category,
        "spotlight": spotlight,
    }


def _cron_metrics(home: Path) -> dict[str, Any]:
    jobs_path = home / "cron" / "jobs.json"
    payload = _read_json(jobs_path)
    jobs: list[dict[str, Any]] = []
    if isinstance(payload, list):
        jobs = [j for j in payload if isinstance(j, dict)]
    elif isinstance(payload, dict):
        raw_jobs = payload.get("jobs")
        if isinstance(raw_jobs, dict):
            jobs = [j for j in raw_jobs.values() if isinstance(j, dict)]
        elif isinstance(raw_jobs, list):
            jobs = [j for j in raw_jobs if isinstance(j, dict)]
        elif all(isinstance(v, dict) for v in payload.values()):
            jobs = [v for v in payload.values() if isinstance(v, dict)]
    enabled = 0
    schedules: list[str] = []
    deliveries: dict[str, int] = {}
    for job in jobs:
        disabled = job.get("disabled") or job.get("paused") or job.get("enabled") is False
        if not disabled:
            enabled += 1
        schedule = str(job.get("schedule") or job.get("cron") or "").strip()
        if schedule and len(schedules) < 6:
            schedules.append(schedule)
        deliver = str(job.get("deliver") or job.get("target") or "origin")
        deliveries[deliver] = deliveries.get(deliver, 0) + 1
    return {
        "filePresent": jobs_path.exists(),
        "path": _compact_path(jobs_path, home),
        "total": len(jobs),
        "enabled": enabled,
        "paused": max(len(jobs) - enabled, 0),
        "sampleSchedules": schedules,
        "deliveries": deliveries,
    }


def _mcp_metrics(cfg: dict[str, Any]) -> dict[str, Any]:
    servers: dict[str, Any] = {}
    root_servers = cfg.get("mcp_servers") if isinstance(cfg, dict) else None
    if isinstance(root_servers, dict):
        servers.update(root_servers)
    # Backwards-compatible fallback for older/experimental config shape.
    mcp = cfg.get("mcp") if isinstance(cfg, dict) else None
    nested_servers = mcp.get("servers") if isinstance(mcp, dict) else None
    if isinstance(nested_servers, dict):
        servers.update(nested_servers)
    return {
        "configured": len(servers),
        "servers": sorted(str(k) for k in servers.keys())[:12],
        "enabled": sum(1 for v in servers.values() if not (isinstance(v, dict) and v.get("enabled") is False)),
    }


def _model_metrics(cfg: dict[str, Any]) -> dict[str, Any]:
    raw_model = cfg.get("model")
    raw_agent = cfg.get("agent")
    raw_delegation = cfg.get("delegation")
    agent: dict[str, Any] = raw_agent if isinstance(raw_agent, dict) else {}
    delegation: dict[str, Any] = raw_delegation if isinstance(raw_delegation, dict) else {}
    if isinstance(raw_model, dict):
        model_name = str(raw_model.get("default") or raw_model.get("model") or raw_model.get("name") or "auto")
        provider = raw_model.get("provider") or cfg.get("provider")
    else:
        model_name = str(raw_model or "auto")
        provider = cfg.get("provider")
    if not isinstance(provider, str) or not provider.strip():
        provider = model_name.split("/", 1)[0] if "/" in model_name else "auto"
    return {
        "provider": provider,
        "model": model_name,
        "reasoning": agent.get("reasoning_effort") or delegation.get("reasoning_effort") or "default",
        "delegationProvider": delegation.get("provider") or None,
        "maxTurns": _safe_int(agent.get("max_turns"), 0),
    }


def _gateway_metrics(cfg: dict[str, Any], env_info: dict[str, Any]) -> dict[str, Any]:
    configured_families = [f for f in env_info.get("families", []) if f in {"telegram", "discord", "slack", "matrix", "signal", "email", "sms", "homeassistant"}]
    platforms_cfg = ((cfg.get("gateway") or {}).get("platforms") or {}) if isinstance(cfg.get("gateway"), dict) else {}
    if isinstance(platforms_cfg, dict):
        for name, pcfg in platforms_cfg.items():
            if isinstance(pcfg, dict) and pcfg.get("enabled"):
                configured_families.append(str(name))
    running = False
    pid = None
    runtime_state = "unknown"
    try:
        from gateway.status import get_running_pid, read_runtime_status

        pid = get_running_pid()
        running = bool(pid)
        status = read_runtime_status()
        if isinstance(status, dict):
            runtime_state = str(status.get("state") or status.get("status") or ("running" if running else "stopped"))
    except Exception:
        runtime_state = "unavailable"
    unique = sorted(set(configured_families))
    return {
        "running": running,
        "pidPresent": bool(pid),
        "state": runtime_state,
        "configuredPlatforms": unique,
        "configuredCount": len(unique),
    }


def _tool_metrics(cfg: dict[str, Any]) -> dict[str, Any]:
    toolsets = cfg.get("toolsets") or []
    disabled = ((cfg.get("agent") or {}).get("disabled_toolsets") or []) if isinstance(cfg.get("agent"), dict) else []
    return {
        "configuredToolsets": list(toolsets) if isinstance(toolsets, list) else [],
        "configuredToolsetCount": len(toolsets) if isinstance(toolsets, list) else 0,
        "disabledToolsets": list(disabled) if isinstance(disabled, list) else [],
        "toolSearch": bool(((cfg.get("tools") or {}).get("tool_search")) if isinstance(cfg.get("tools"), dict) else False),
    }


def _safety_metrics(cfg: dict[str, Any]) -> dict[str, Any]:
    raw_approvals = cfg.get("approvals")
    raw_security = cfg.get("security")
    raw_terminal = cfg.get("terminal")
    approvals: dict[str, Any] = raw_approvals if isinstance(raw_approvals, dict) else {}
    security: dict[str, Any] = raw_security if isinstance(raw_security, dict) else {}
    terminal: dict[str, Any] = raw_terminal if isinstance(raw_terminal, dict) else {}
    return {
        "approvalsMode": approvals.get("mode") or "manual",
        "cronApprovalsMode": approvals.get("cron_mode") or approvals.get("mode") or "manual",
        "redactSecrets": security.get("redact_secrets") is not False,
        "tirithEnabled": bool(security.get("tirith_enabled")),
        "terminalBackend": terminal.get("backend") or "local",
        "privateUrlsAllowed": bool(security.get("allow_private_urls")),
    }


def _identity_metrics(home: Path) -> dict[str, Any]:
    soul = home / "soul.md"
    memory_file = home / "MEMORY.md"
    user_file = home / "USER.md"
    # Active installs can use lowercase memory files as well; only expose sizes.
    files = [p for p in [soul, memory_file, user_file, home / "memory.md", home / "user.md"] if p.exists()]
    return {
        "soulPresent": soul.exists(),
        "profileFiles": len(files),
        "totalBytes": sum(p.stat().st_size for p in files if p.exists()),
        "files": [_compact_path(p, home) for p in files[:5]],
    }


def _build_runtime(cfg: dict[str, Any], home: Path) -> dict[str, Any]:
    env_info = _env_families(home)
    runtime = {
        "generatedAt": _now_iso(),
        "home": "~/.hermes",
        "model": _model_metrics(cfg),
        "env": env_info,
        "identity": _identity_metrics(home),
        "sessions": _state_db_metrics(home),
        "skills": _skill_metrics(home),
        "cron": _cron_metrics(home),
        "mcp": _mcp_metrics(cfg),
        "gateway": _gateway_metrics(cfg, env_info),
        "tools": _tool_metrics(cfg),
        "safety": _safety_metrics(cfg),
        "voice": {
            "sttEnabled": bool(((cfg.get("stt") or {}).get("enabled")) if isinstance(cfg.get("stt"), dict) else False),
            "sttProvider": ((cfg.get("stt") or {}).get("provider")) if isinstance(cfg.get("stt"), dict) else None,
            "ttsProvider": ((cfg.get("tts") or {}).get("provider")) if isinstance(cfg.get("tts"), dict) else None,
        },
        "dashboard": {
            "missionControlRoute": "/mission-control",
            "sourceRoute": SOURCE_URL,
            "authGated": True,
        },
    }
    return runtime


def _state(state: str, evidence: Iterable[str], next_action: str) -> CapabilityState:
    return CapabilityState(state=state, score=_STATE_WEIGHT[state], evidence=[e for e in evidence if e], next=next_action)


def _readiness_for_feature(feature_id: str, runtime: dict[str, Any]) -> CapabilityState:
    sessions = runtime["sessions"]
    skills = runtime["skills"]
    cron = runtime["cron"]
    mcp = runtime["mcp"]
    gateway = runtime["gateway"]
    safety = runtime["safety"]
    voice = runtime["voice"]
    tools = runtime["tools"]
    env_info = runtime["env"]

    if feature_id == "H1":
        if runtime["identity"]["profileFiles"] and sessions["dbPresent"]:
            return _state("active", [f"{sessions['total']} session(s) in SQLite store", f"{skills['total']} skill(s) installed"], "Keep memory budgets healthy and consolidate recurring lessons.")
        return _state("partial", ["Memory files or SQLite store are not both present"], "Enable memory files and keep the session store writable.")
    if feature_id == "H2":
        if cron["enabled"]:
            return _state("partial", [f"{cron['enabled']} enabled cron job(s) can run reflection-style passes"], "Add a dedicated nightly reflection/curator job if not present.")
        return _state("watch", ["No enabled cron jobs detected"], "Create a self-contained nightly consolidation cron job.")
    if feature_id in {"H3", "H11", "O3"}:
        return _state("active" if skills["total"] else "partial", [f"{skills['total']} installed skill(s)", f"usage tracked for {skills['usageTracked']} skill(s)"], "Keep auto-created skills reviewed and curated.")
    if feature_id in {"H4", "O1"}:
        return _state("active" if gateway["configuredCount"] else "partial", [f"{gateway['configuredCount']} configured platform family/families", f"gateway state: {gateway['state']}"], "Enable only platforms that have real operator value.")
    if feature_id in {"H5", "O5"}:
        backend = safety["terminalBackend"]
        return _state("active" if backend else "partial", [f"terminal backend: {backend}", f"configured toolsets: {tools['configuredToolsetCount']}"], "Prefer isolated backends for untrusted or expensive commands.")
    if feature_id == "H6":
        active = voice["sttEnabled"] or bool(voice["ttsProvider"])
        return _state("active" if active else "watch", [f"STT enabled: {voice['sttEnabled']}", f"TTS provider: {voice['ttsProvider'] or 'not configured'}"], "Wire STT/TTS only where voice actually speeds you up.")
    if feature_id == "H7":
        provider = "builtin"
        return _state("partial", [f"memory provider: {provider}"], "Add Honcho/Mem0/etc. only if builtin memory becomes limiting.")
    if feature_id == "H8":
        return _state("active", ["skills are source-scoped in the dashboard", "plugins expose trust/source metadata"], "Keep community skills behind review before enabling broad permissions.")
    if feature_id == "H9":
        return _state("active", ["memory/user profile limits are part of Hermes config", "session compression is supported"], "Watch memory saturation and prune stale facts.")
    if feature_id == "H10":
        return _state("planned", ["Token/cost analytics exist; TokenMix-specific optimisation is not a live signal"], "Treat as advanced optimisation after high-value flows are stable.")
    if feature_id == "O2":
        return _state("planned", ["Dashboard is responsive web; native mobile clients are outside this repository"], "Use the web dashboard on mobile before funding native clients.")
    if feature_id == "O4":
        return _state("active", ["delegate_task subagents and kanban workers are supported", "parallel child cap is configurable"], "Use subagents for independent workstreams, not shared-file conflicts.")
    if feature_id == "O6":
        return _state("planned", ["MCP/tool protocols exist; Open Gateway federation is not configured"], "Keep this as a future interoperability project.")
    if feature_id in {"O7", "O8"}:
        mode = safety["approvalsMode"]
        return _state("active", [f"approvals mode: {mode}", f"secret redaction: {safety['redactSecrets']}"], "Keep destructive approvals visible; use smart/off only intentionally.")
    if feature_id == "O9":
        return _state("partial", ["Mission Control dashboard is the live cockpit route", "file/canvas edit UI is separate from this snapshot"], "Promote high-value cards into editable Live Canvas widgets later.")
    if feature_id == "O10":
        fams = set(env_info.get("families", []))
        if "tailscale" in fams:
            return _state("partial", ["tailscale-related env family detected"], "Verify mesh access and avoid public ports.")
        return _state("watch", ["No Tailscale-specific signal detected"], "Prefer mesh VPN or SSH tunnel if exposing a home server.")
    return _state("watch", ["No feature-specific readiness rule"], "Inspect runtime evidence manually.")


def _readiness_for_step(step: dict[str, Any], runtime: dict[str, Any]) -> CapabilityState:
    domain = step["domain"]
    route = step.get("route")
    if domain == "model":
        model = runtime["model"]
        return _state("active", [f"provider: {model['provider']}", f"model: {model['model']}", f"reasoning: {model['reasoning']}"], "Keep model routing visible in Models and Config.")
    if domain == "memory":
        return _state("active" if runtime["sessions"]["dbPresent"] else "partial", [f"session DB present: {runtime['sessions']['dbPresent']}", f"messages counted: {runtime['sessions']['messages']}"], "Continue consolidating important facts into memory/skills.")
    if domain == "skills":
        return _state("active" if runtime["skills"]["total"] else "partial", [f"{runtime['skills']['total']} installed skill(s)"], "Create skills only from reusable, verified workflows.")
    if domain == "automation":
        return _state("active" if runtime["cron"]["total"] else "watch", [f"{runtime['cron']['total']} cron job(s), {runtime['cron']['enabled']} enabled"], "Schedule recurring work only with self-contained prompts.")
    if domain == "tools":
        if step["id"] == "step-21":
            return _state("active" if runtime["mcp"]["configured"] else "watch", [f"{runtime['mcp']['configured']} MCP server(s) configured"], "Install MCP servers only for workflows you actually use.")
        return _state("active", [f"configured toolset count: {runtime['tools']['configuredToolsetCount']}"], "Keep powerful tools behind the right platform/toolset scope.")
    if domain == "interface":
        return _state("active" if runtime["gateway"]["configuredCount"] else "partial", [f"configured platform families: {runtime['gateway']['configuredCount']}", f"gateway running: {runtime['gateway']['running']}"], "Use Pairing/Channels for multi-user safety.")
    if domain == "voice":
        return _state("active" if runtime["voice"]["sttEnabled"] else "watch", [f"STT provider: {runtime['voice']['sttProvider'] or 'not enabled'}", f"TTS provider: {runtime['voice']['ttsProvider'] or 'not configured'}"], "Enable voice where Telegram/Discord audio saves time.")
    if domain == "safety":
        return _state("active", [f"approvals mode: {runtime['safety']['approvalsMode']}", f"secret redaction: {runtime['safety']['redactSecrets']}"], "Never expose raw tool output/logs in the dashboard.")
    if domain == "analytics":
        tokens = runtime["sessions"]["inputTokens"] + runtime["sessions"]["outputTokens"]
        return _state("active" if tokens else "partial", [f"tracked tokens: {tokens}", f"estimated cost USD: {runtime['sessions']['estimatedCostUsd']}"], "Enable token analytics in dashboard config when useful.")
    if domain == "dashboard":
        return _state("active", ["/mission-control route exposes this blueprint", "server-only snapshot protects local state"], "Keep coverage and readiness distinct.")
    if domain == "hosting":
        return _state("partial", [f"terminal backend: {runtime['safety']['terminalBackend']}", "hosting posture depends on deployment target"], "Prefer low-cost VPS/mesh networking over low-value complexity.")
    if domain == "quality":
        return _state("active", ["Python regression tests cover the snapshot endpoint", "frontend build validates TypeScript route"], "Run browser smoke on desktop and mobile before shipping.")
    if domain in {"configuration", "identity", "runtime", "agent-loop"}:
        return _state("active", [f"dashboard route: {route}", f"Hermes home exposed as {runtime['home']}"], "Keep config readable while secrets stay server-only.")
    return _state("watch", ["No domain-specific rule"], "Review manually.")


def _coverage(runtime: dict[str, Any]) -> dict[str, Any]:
    step_rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    domain_scores: dict[str, list[int]] = {}

    for step in BLUEPRINT_STEPS:
        readiness = _readiness_for_step(step, runtime)
        row = {
            **step,
            "sourceUrl": f"{SOURCE_URL}#{step['id']}",
            "status": readiness.state,
            "readiness": readiness.score,
            "evidence": readiness.evidence,
            "next": readiness.next,
            "missionControl": step.get("route") == "/mission-control",
        }
        step_rows.append(row)
        domain_scores.setdefault(step["domain"], []).append(readiness.score)

    for feature in [*HERMES_FEATURES, *OPENCLAW_FEATURES]:
        readiness = _readiness_for_feature(feature["id"], runtime)
        row = {
            **feature,
            "status": readiness.state,
            "readiness": readiness.score,
            "evidence": readiness.evidence,
            "next": readiness.next,
        }
        feature_rows.append(row)
        domain_scores.setdefault(feature["domain"], []).append(readiness.score)

    all_rows = [*step_rows, *feature_rows]
    counts: dict[str, int] = {"active": 0, "partial": 0, "watch": 0, "planned": 0}
    for row in all_rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    total = len(all_rows)
    readiness = round(sum(row["readiness"] for row in all_rows) / total) if total else 0
    domains = [
        {"name": name, "score": round(sum(scores) / len(scores)), "items": len(scores)}
        for name, scores in sorted(domain_scores.items())
        if scores
    ]
    domains.sort(key=lambda d: (d["score"], d["name"]))
    return {
        "summary": {"total": total, "readiness": readiness, "counts": counts},
        "steps": step_rows,
        "features": feature_rows,
        "domains": domains,
        "weakestDomains": domains[:5],
    }


def _action_queue(runtime: dict[str, Any], coverage: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    weakest = coverage.get("weakestDomains", [])[:3]
    for idx, domain in enumerate(weakest, start=1):
        actions.append({
            "rank": idx,
            "tone": "now" if domain["score"] < 55 else "next",
            "title": f"Strengthen {domain['name']}",
            "reason": f"Average readiness {domain['score']} across {domain['items']} mapped item(s).",
            "route": "/mission-control",
        })
    if runtime["gateway"]["configuredCount"] == 0:
        actions.append({"rank": len(actions) + 1, "tone": "now", "title": "Configure one gateway", "reason": "Messaging is the only useful interface if the agent is not reachable.", "route": "/channels"})
    if runtime["cron"]["enabled"] == 0:
        actions.append({"rank": len(actions) + 1, "tone": "next", "title": "Add one reflection or heartbeat cron", "reason": "The blueprint expects proactive/background consolidation.", "route": "/cron"})
    if runtime["skills"]["total"] == 0:
        actions.append({"rank": len(actions) + 1, "tone": "next", "title": "Install or create reusable skills", "reason": "Skills are the reusable procedure layer of the agent.", "route": "/skills"})
    return actions[:8]


def _privacy_boundaries() -> list[dict[str, str]]:
    return [
        {"label": "Session content", "policy": "counts only", "detail": "No chat text, tool outputs, or reasoning bodies leave the server snapshot."},
        {"label": "Secrets", "policy": "never values", "detail": "Env files are reduced to counts and provider families only."},
        {"label": "Local paths", "policy": "compacted", "detail": "Hermes-owned paths render as ~/.hermes; arbitrary absolutes collapse to labels."},
        {"label": "Commands/logs", "policy": "metadata", "detail": "The cockpit exposes status/readiness, not shell commands or log tails."},
    ]


def build_mission_control_snapshot() -> dict[str, Any]:
    """Return a deterministic, privacy-minimized Mission Control snapshot."""
    home = _home()
    try:
        cfg = load_config()
    except Exception:
        cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}
    runtime = _build_runtime(cfg, home)
    coverage = _coverage(runtime)
    return {
        "ok": True,
        "source": {
            "url": SOURCE_URL,
            "title": "Claude Agent",
            "lastChecked": _now_iso(),
            "extractedWith": "Hermes Mission Control server snapshot",
            "note": "Source guide says 26 build steps; the page also contains a 22½ prompt-injection defence anchor, tracked here as its own required item.",
        },
        "blueprint": {
            "stepCount": len(BLUEPRINT_STEPS),
            "numberedStepCount": 26,
            "hermesFeatureCount": len(HERMES_FEATURES),
            "openclawFeatureCount": len(OPENCLAW_FEATURES),
            "parts": ["MVP", "Beyond MVP", "Production-grade"],
        },
        "runtime": runtime,
        "coverage": coverage,
        "actionQueue": _action_queue(runtime, coverage),
        "privacy": _privacy_boundaries(),
        "deviceProof": {
            "principles": [
                "safe-area aware responsive grids",
                "horizontal overflow guarded by min-w-0 and wrapped text",
                "reduced-motion friendly static gradients",
                "touch targets sized for mobile navigation",
            ],
            "breakpoints": ["mobile", "tablet", "desktop", "wide cockpit"],
        },
    }


def mission_control_summary() -> dict[str, Any]:
    """Small summary shape for health checks and future sidebar chips."""
    snapshot = build_mission_control_snapshot()
    return {
        "ok": snapshot["ok"],
        "readiness": snapshot["coverage"]["summary"]["readiness"],
        "totalItems": snapshot["coverage"]["summary"]["total"],
        "counts": snapshot["coverage"]["summary"]["counts"],
        "topAction": snapshot["actionQueue"][0] if snapshot["actionQueue"] else None,
        "runtime": {
            "sessions": snapshot["runtime"]["sessions"]["total"],
            "skills": snapshot["runtime"]["skills"]["total"],
            "cron": snapshot["runtime"]["cron"]["total"],
            "mcp": snapshot["runtime"]["mcp"]["configured"],
        },
    }


__all__ = [
    "BLUEPRINT_STEPS",
    "HERMES_FEATURES",
    "OPENCLAW_FEATURES",
    "build_mission_control_snapshot",
    "mission_control_summary",
]
