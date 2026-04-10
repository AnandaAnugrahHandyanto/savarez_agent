"""Dashboard data layer — pulls from SessionDB, MemoryStore, SkinConfig."""

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_constants import get_hermes_home


def _get_db() -> Any:
    from hermes_state import SessionDB
    return SessionDB()


def get_recent_sessions(limit: int = 30) -> List[Dict[str, Any]]:
    db = _get_db()
    try:
        return db.list_sessions_rich(limit=limit)
    finally:
        db.close()


def get_usage_stats() -> Dict[str, Any]:
    """Aggregate usage stats across all sessions."""
    db = _get_db()
    try:
        cursor = db._conn.execute("""
            SELECT
                COUNT(*) as total_sessions,
                COALESCE(SUM(message_count), 0) as total_messages,
                COALESCE(SUM(tool_call_count), 0) as total_tool_calls,
                COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                COALESCE(SUM(output_tokens), 0) as total_output_tokens,
                COALESCE(SUM(COALESCE(actual_cost_usd, estimated_cost_usd, 0)), 0) as total_cost,
                MIN(started_at) as first_session,
                MAX(started_at) as last_session
            FROM sessions
        """)
        row = cursor.fetchone()
        if not row:
            return {}
        return dict(row)
    finally:
        db.close()


def get_daily_activity(days: int = 14) -> List[Dict[str, Any]]:
    """Sessions per day for the last N days."""
    db = _get_db()
    cutoff = time.time() - (days * 86400)
    try:
        cursor = db._conn.execute("""
            SELECT
                DATE(started_at, 'unixepoch', 'localtime') as day,
                COUNT(*) as sessions,
                COALESCE(SUM(message_count), 0) as messages,
                COALESCE(SUM(COALESCE(actual_cost_usd, estimated_cost_usd, 0)), 0) as cost
            FROM sessions
            WHERE started_at > ?
            GROUP BY day
            ORDER BY day
        """, (cutoff,))
        return [dict(r) for r in cursor.fetchall()]
    finally:
        db.close()


def get_model_breakdown() -> List[Dict[str, Any]]:
    """Usage breakdown by model."""
    db = _get_db()
    try:
        cursor = db._conn.execute("""
            SELECT
                COALESCE(model, 'unknown') as model,
                COUNT(*) as sessions,
                COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens,
                COALESCE(SUM(COALESCE(actual_cost_usd, estimated_cost_usd, 0)), 0) as cost
            FROM sessions
            GROUP BY model
            ORDER BY sessions DESC
            LIMIT 10
        """)
        return [dict(r) for r in cursor.fetchall()]
    finally:
        db.close()


def search_sessions(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """FTS5 search across session messages."""
    db = _get_db()
    try:
        return db.search_messages(query, limit=limit)
    except Exception:
        return []
    finally:
        db.close()


def read_memory_file(filename: str) -> str:
    """Read MEMORY.md or USER.md."""
    path = get_hermes_home() / "memories" / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def get_memory_entries() -> List[str]:
    raw = read_memory_file("MEMORY.md")
    if not raw.strip():
        return []
    return [e.strip() for e in raw.split("\n§\n") if e.strip()]


def get_user_entries() -> List[str]:
    raw = read_memory_file("USER.md")
    if not raw.strip():
        return []
    return [e.strip() for e in raw.split("\n§\n") if e.strip()]


def _ensure_skin_loaded():
    """Make sure the skin engine is initialized from config."""
    from hermes_cli.skin_engine import get_active_skin_name
    if get_active_skin_name() == "default":
        try:
            import yaml
            config_path = get_hermes_home() / "config.yaml"
            if config_path.exists():
                with open(config_path) as f:
                    config = yaml.safe_load(f) or {}
                from hermes_cli.skin_engine import init_skin_from_config
                init_skin_from_config(config)
        except Exception:
            pass


def get_skin_pantheon() -> List[Dict[str, str]]:
    """Get pantheon data from active skin."""
    try:
        _ensure_skin_loaded()
        from hermes_cli.skin_engine import get_active_skin
        skin = get_active_skin()
        return skin.pantheon if skin.pantheon else []
    except Exception:
        return []


def get_skin_colors() -> Dict[str, str]:
    try:
        _ensure_skin_loaded()
        from hermes_cli.skin_engine import get_active_skin
        return get_active_skin().colors
    except Exception:
        return {}


def format_timestamp(ts: float) -> str:
    if not ts:
        return "—"
    dt = datetime.fromtimestamp(ts)
    now = datetime.now()
    if dt.date() == now.date():
        return dt.strftime("today %H:%M")
    elif dt.date() == (now - timedelta(days=1)).date():
        return dt.strftime("yesterday %H:%M")
    return dt.strftime("%b %d %H:%M")


def format_cost(cost: float) -> str:
    if not cost or cost == 0:
        return "$0.00"
    if cost < 0.01:
        return f"${cost:.4f}"
    return f"${cost:.2f}"


def format_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def get_session_detail(session_id: str) -> Optional[Dict[str, Any]]:
    """Get full session metadata."""
    db = _get_db()
    try:
        return db.get_session(session_id)
    finally:
        db.close()


def get_session_messages(session_id: str) -> List[Dict[str, Any]]:
    """Get all messages for a session with tool call details."""
    db = _get_db()
    try:
        return db.get_messages(session_id)
    finally:
        db.close()


def get_tool_heavy_sessions(limit: int = 30) -> List[Dict[str, Any]]:
    """Sessions sorted by tool_call_count descending — the busiest sessions."""
    db = _get_db()
    try:
        cursor = db._conn.execute("""
            SELECT s.*,
                COALESCE(
                    (SELECT SUBSTR(REPLACE(REPLACE(m.content, X'0A', ' '), X'0D', ' '), 1, 63)
                     FROM messages m
                     WHERE m.session_id = s.id AND m.role = 'user' AND m.content IS NOT NULL
                     ORDER BY m.timestamp, m.id LIMIT 1),
                    ''
                ) AS preview
            FROM sessions s
            WHERE s.tool_call_count > 0
            ORDER BY s.tool_call_count DESC
            LIMIT ?
        """, (limit,))
        return [dict(r) for r in cursor.fetchall()]
    finally:
        db.close()


def get_tool_call_breakdown() -> List[Dict[str, Any]]:
    """Count tool calls by tool_name across all sessions."""
    db = _get_db()
    try:
        cursor = db._conn.execute("""
            SELECT
                COALESCE(tool_name, 'unknown') as tool,
                COUNT(*) as calls
            FROM messages
            WHERE role = 'tool' AND tool_name IS NOT NULL
            GROUP BY tool_name
            ORDER BY calls DESC
            LIMIT 20
        """)
        return [dict(r) for r in cursor.fetchall()]
    finally:
        db.close()


def get_local_model_sessions(limit: int = 50) -> List[Dict[str, Any]]:
    """Sessions using local models (localhost/lmstudio/ollama providers)."""
    db = _get_db()
    try:
        cursor = db._conn.execute("""
            SELECT *
            FROM sessions
            WHERE billing_base_url LIKE '%localhost%'
               OR billing_base_url LIKE '%127.0.0.1%'
               OR billing_base_url LIKE '%0.0.0.0%'
               OR billing_provider LIKE '%custom%'
               OR billing_provider LIKE '%local%'
               OR model LIKE '%llama%'
               OR model LIKE '%mistral%'
               OR model LIKE '%qwen%'
               OR model LIKE '%gemma%'
               OR model LIKE '%phi%'
               OR model LIKE '%deepseek%'
            ORDER BY started_at DESC
            LIMIT ?
        """, (limit,))
        return [dict(r) for r in cursor.fetchall()]
    finally:
        db.close()


def get_local_model_stats() -> Dict[str, Any]:
    """Aggregate stats for local model usage."""
    db = _get_db()
    try:
        cursor = db._conn.execute("""
            SELECT
                COUNT(*) as sessions,
                COALESCE(SUM(message_count), 0) as messages,
                COALESCE(SUM(tool_call_count), 0) as tool_calls,
                COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens,
                COALESCE(AVG(input_tokens + output_tokens), 0) as avg_tokens_per_session
            FROM sessions
            WHERE billing_base_url LIKE '%localhost%'
               OR billing_base_url LIKE '%127.0.0.1%'
               OR billing_base_url LIKE '%0.0.0.0%'
               OR billing_provider LIKE '%custom%'
               OR billing_provider LIKE '%local%'
               OR model LIKE '%llama%'
               OR model LIKE '%mistral%'
               OR model LIKE '%qwen%'
               OR model LIKE '%gemma%'
               OR model LIKE '%phi%'
               OR model LIKE '%deepseek%'
        """)
        row = cursor.fetchone()
        return dict(row) if row else {}
    finally:
        db.close()


def get_hermes_config() -> Dict[str, Any]:
    """Read the full config.yaml."""
    import yaml
    config_path = get_hermes_home() / "config.yaml"
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def get_active_model_info() -> Dict[str, Any]:
    """Get currently configured model, provider, and base_url."""
    cfg = get_hermes_config()
    model_cfg = cfg.get("model", {})
    default_model = model_cfg.get("default", "unknown")
    provider = model_cfg.get("provider", "unknown")

    base_url = None
    provider_name = None
    if provider.startswith("custom:"):
        provider_name = provider.split(":", 1)[1]
        for p in cfg.get("custom_providers", []):
            if p.get("name") == provider_name:
                base_url = p.get("base_url", "")
                break

    context_length = None
    if provider_name:
        for p in cfg.get("custom_providers", []):
            if p.get("name") == provider_name:
                models = p.get("models", {})
                if isinstance(models, dict):
                    meta = models.get(default_model)
                    if isinstance(meta, dict):
                        ctx = meta.get("context_length")
                        if ctx is not None:
                            try:
                                context_length = int(ctx)
                            except (TypeError, ValueError):
                                context_length = None
                break

    return {
        "model": default_model,
        "provider": provider,
        "provider_name": provider_name,
        "base_url": base_url or "",
        "context_length": context_length,
    }


def get_custom_providers() -> List[Dict[str, Any]]:
    """List all custom providers from config.yaml."""
    cfg = get_hermes_config()
    providers = []
    for p in cfg.get("custom_providers", []):
        name = p.get("name", "?")
        url = p.get("base_url", "")
        models = p.get("models", {})
        model_list = []
        for model_id, meta in models.items():
            ctx = meta.get("context_length", 0) if isinstance(meta, dict) else 0
            model_list.append({"id": model_id, "context_length": ctx})
        providers.append({
            "name": name,
            "base_url": url,
            "api_key": p.get("api_key", ""),
            "models": model_list,
        })
    return providers


def get_lmstudio_models(base_url: str = "http://localhost:1234/v1") -> List[Dict[str, Any]]:
    """Probe LM Studio for loaded models."""
    try:
        import httpx
        resp = httpx.get(f"{base_url}/models", timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", [])
    except Exception:
        pass
    return []


def resolve_dashboard_context_input(
    raw: str, provider_name: str, model_id: str,
) -> tuple:
    """Parse context window from dashboard field.

    Empty input: reuse existing ``context_length`` for ``model_id`` on
    ``provider_name``, or default ``32768``.

    Accepts plain integers, optional ``_``/``,`` separators, or a trailing
    ``k``/``K`` suffix (e.g. ``128k`` → 131072).

    Returns ``(tokens, None)`` on success, or ``(None, error_message)``.
    """
    raw = (raw or "").strip()
    if not raw:
        for p in get_custom_providers():
            if p.get("name") == provider_name:
                for m in p.get("models", []):
                    if m.get("id") == model_id:
                        c = m.get("context_length") or 0
                        if isinstance(c, int) and c > 0:
                            return c, None
                        try:
                            c = int(c)
                            if c > 0:
                                return c, None
                        except (TypeError, ValueError):
                            pass
                break
        return 32768, None

    s = raw.replace("_", "").replace(",", "").strip().lower()
    mult = 1
    if len(s) > 1 and s[-1] == "k":
        s = s[:-1]
        mult = 1024
    if not s.isdigit():
        return None, "Invalid context — use a number (e.g. 131072 or 128k)"
    n = int(s) * mult
    if n <= 0:
        return None, "Context must be a positive number"
    return n, None


def switch_active_model(model_id: str, provider_name: str) -> bool:
    """Switch the active model+provider in config.yaml. Returns True on success."""
    import yaml
    config_path = get_hermes_home() / "config.yaml"
    if not config_path.exists():
        return False
    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}

        if "model" not in cfg:
            cfg["model"] = {}
        cfg["model"]["default"] = model_id
        cfg["model"]["provider"] = f"custom:{provider_name}"

        from utils import atomic_yaml_write
        atomic_yaml_write(config_path, cfg)
        return True
    except Exception:
        return False


def ensure_provider_has_model(provider_name: str, model_id: str,
                               context_length: int = 32768) -> bool:
    """Upsert model_id under the provider with context_length (writes config.yaml)."""
    import yaml
    config_path = get_hermes_home() / "config.yaml"
    if not config_path.exists():
        return False
    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}

        for p in cfg.get("custom_providers", []):
            if p.get("name") == provider_name:
                models = p.get("models", {})
                if not isinstance(models, dict):
                    models = {}
                existing = models.get(model_id)
                if isinstance(existing, dict):
                    existing["context_length"] = int(context_length)
                    models[model_id] = existing
                else:
                    models[model_id] = {"context_length": int(context_length)}
                p["models"] = models

                from utils import atomic_yaml_write
                atomic_yaml_write(config_path, cfg)
                return True
        return False
    except Exception:
        return False


def get_local_model_breakdown() -> List[Dict[str, Any]]:
    """Usage breakdown for local models only."""
    db = _get_db()
    try:
        cursor = db._conn.execute("""
            SELECT
                COALESCE(model, 'unknown') as model,
                COUNT(*) as sessions,
                COALESCE(SUM(message_count), 0) as messages,
                COALESCE(SUM(input_tokens + output_tokens), 0) as tokens
            FROM sessions
            WHERE billing_base_url LIKE '%localhost%'
               OR billing_base_url LIKE '%127.0.0.1%'
               OR billing_base_url LIKE '%0.0.0.0%'
               OR billing_provider LIKE '%custom%'
               OR billing_provider LIKE '%local%'
               OR model LIKE '%llama%'
               OR model LIKE '%mistral%'
               OR model LIKE '%qwen%'
               OR model LIKE '%gemma%'
               OR model LIKE '%phi%'
               OR model LIKE '%deepseek%'
            GROUP BY model
            ORDER BY sessions DESC
        """)
        return [dict(r) for r in cursor.fetchall()]
    finally:
        db.close()


def get_tool_stats_by_god() -> Dict[str, Dict[str, Any]]:
    """Get tool call statistics grouped by pantheon god.
    
    Returns dict mapping god_name -> {calls, success_rate, avg_latency, tools}.
    Uses the tool_god_mapping from the active skin.
    """
    try:
        _ensure_skin_loaded()
        from hermes_cli.skin_engine import get_active_skin
        skin = get_active_skin()
        tool_god_mapping = skin.tool_god_mapping
    except Exception:
        tool_god_mapping = {}
    
    tool_breakdown = get_tool_call_breakdown()
    
    god_stats: Dict[str, Dict[str, Any]] = {}
    for item in tool_breakdown:
        tool_name = item.get("tool", "unknown")
        calls = item.get("calls", 0)
        
        god_name = tool_god_mapping.get(tool_name, "Hermes")
        
        if god_name not in god_stats:
            god_stats[god_name] = {
                "calls": 0,
                "tools": [],
                "tool_details": [],
            }
        
        god_stats[god_name]["calls"] += calls
        god_stats[god_name]["tools"].append(tool_name)
        god_stats[god_name]["tool_details"].append({
            "name": tool_name,
            "calls": calls,
        })
    
    return god_stats


def get_execution_lane_stats() -> List[Dict[str, Any]]:
    """Get statistics for each execution lane defined in the skin.
    
    Returns list of lane stats with real data from tool calls.
    """
    try:
        _ensure_skin_loaded()
        from hermes_cli.skin_engine import get_active_skin
        skin = get_active_skin()
        execution_lanes = skin.execution_lanes
        pantheon = skin.pantheon
    except Exception:
        return []
    
    if not execution_lanes:
        return []
    
    tool_breakdown = get_tool_call_breakdown()
    tool_calls_map = {item.get("tool", ""): item.get("calls", 0) for item in tool_breakdown}
    
    total_calls = sum(tool_calls_map.values()) or 1
    
    lane_stats = []
    for lane in execution_lanes:
        lane_name = lane.get("name", "UNKNOWN")
        god_name = lane.get("god", "Hermes")
        tools = lane.get("tools", [])
        color = lane.get("color", "#FFD700")
        icon = lane.get("icon", "◈")
        desc = lane.get("desc", "")
        
        lane_calls = sum(tool_calls_map.get(t, 0) for t in tools)
        pct = int((lane_calls / total_calls) * 100) if total_calls > 0 else 0
        
        god_data = None
        for g in pantheon:
            if g.get("name") == god_name:
                god_data = g
                break
        
        lane_stats.append({
            "name": lane_name,
            "god": god_name,
            "god_data": god_data,
            "icon": icon,
            "color": color,
            "desc": desc,
            "tools": tools,
            "calls": lane_calls,
            "pct": pct,
            "latency_ms": 0,
        })
    
    return lane_stats


def get_pantheon_activity() -> List[Dict[str, Any]]:
    """Get activity metrics for each god in the pantheon.
    
    Returns list of god activity data with call counts and status.
    """
    try:
        _ensure_skin_loaded()
        from hermes_cli.skin_engine import get_active_skin
        skin = get_active_skin()
        pantheon = skin.pantheon
    except Exception:
        return []
    
    if not pantheon:
        return []
    
    god_stats = get_tool_stats_by_god()
    total_calls = sum(g.get("calls", 0) for g in god_stats.values()) or 1
    
    activity = []
    for god in pantheon:
        god_name = god.get("name", "Unknown")
        stats = god_stats.get(god_name, {"calls": 0, "tools": []})
        calls = stats.get("calls", 0)
        pct = int((calls / total_calls) * 100) if total_calls > 0 else 0
        
        if calls > 50:
            status = "active"
        elif calls > 10:
            status = "ready"
        else:
            status = "idle"
        
        activity.append({
            **god,
            "calls": calls,
            "pct": pct,
            "status": status,
            "tools": stats.get("tools", []),
        })
    
    return activity


def get_recent_notifications(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent session events formatted as divine notifications.
    
    Returns list of notification dicts with level, message, timestamp.
    """
    db = _get_db()
    try:
        cursor = db._conn.execute("""
            SELECT
                id,
                started_at,
                title,
                model,
                message_count,
                tool_call_count,
                COALESCE(actual_cost_usd, estimated_cost_usd, 0) as cost
            FROM sessions
            ORDER BY started_at DESC
            LIMIT ?
        """, (limit,))
        rows = [dict(r) for r in cursor.fetchall()]
    finally:
        db.close()
    
    notifications = []
    for row in rows:
        ts = row.get("started_at", 0)
        title = row.get("title") or "Untitled session"
        model = (row.get("model") or "unknown").split("/")[-1]
        msgs = row.get("message_count", 0)
        tools = row.get("tool_call_count", 0)
        cost = row.get("cost", 0)
        
        if tools > 20:
            level = "warn"
            msg = f"Heavy forging: {title[:30]} ({tools} strikes)"
        elif cost > 0.50:
            level = "info"
            msg = f"Costly decree: {title[:30]} (${cost:.2f})"
        else:
            level = "success"
            msg = f"Session: {title[:35]}"
        
        notifications.append({
            "level": level,
            "message": msg,
            "timestamp": ts,
            "model": model,
            "session_id": row.get("id", ""),
        })
    
    return notifications


def get_flow_data(session_id: str = None) -> Dict[str, Any]:
    """Get data for the divine flow diagram.
    
    If session_id provided, shows flow for that session.
    Otherwise shows aggregate flow from recent sessions.
    """
    if session_id:
        messages = get_session_messages(session_id)
        tool_sequence = []
        for msg in messages:
            if msg.get("role") == "tool":
                tool_name = msg.get("tool_name", "unknown")
                tool_sequence.append(tool_name)
        return {
            "session_id": session_id,
            "tool_sequence": tool_sequence,
            "total_tools": len(tool_sequence),
        }
    
    lane_stats = get_execution_lane_stats()
    return {
        "session_id": None,
        "lanes": lane_stats,
        "total_calls": sum(l.get("calls", 0) for l in lane_stats),
    }


def get_cost_breakdown(days: int = 30) -> Dict[str, Any]:
    """Get cost breakdown for the cost tracker widget.
    
    Returns daily, weekly, monthly costs and model breakdown.
    """
    db = _get_db()
    now = time.time()
    
    try:
        cursor = db._conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN started_at > ? THEN COALESCE(actual_cost_usd, estimated_cost_usd, 0) ELSE 0 END), 0) as daily,
                COALESCE(SUM(CASE WHEN started_at > ? THEN COALESCE(actual_cost_usd, estimated_cost_usd, 0) ELSE 0 END), 0) as weekly,
                COALESCE(SUM(CASE WHEN started_at > ? THEN COALESCE(actual_cost_usd, estimated_cost_usd, 0) ELSE 0 END), 0) as monthly,
                COALESCE(SUM(COALESCE(actual_cost_usd, estimated_cost_usd, 0)), 0) as total
            FROM sessions
        """, (now - 86400, now - 7*86400, now - 30*86400))
        row = cursor.fetchone()
        
        cursor2 = db._conn.execute("""
            SELECT
                COALESCE(model, 'unknown') as model,
                COALESCE(SUM(COALESCE(actual_cost_usd, estimated_cost_usd, 0)), 0) as cost
            FROM sessions
            WHERE started_at > ?
            GROUP BY model
            ORDER BY cost DESC
            LIMIT 5
        """, (now - 30*86400,))
        model_costs = [dict(r) for r in cursor2.fetchall()]
        
    finally:
        db.close()
    
    return {
        "daily": row["daily"] if row else 0,
        "weekly": row["weekly"] if row else 0,
        "monthly": row["monthly"] if row else 0,
        "total": row["total"] if row else 0,
        "model_breakdown": model_costs,
    }


def get_skin_execution_lanes() -> List[Dict[str, Any]]:
    """Get execution lane definitions from the active skin."""
    try:
        _ensure_skin_loaded()
        from hermes_cli.skin_engine import get_active_skin
        skin = get_active_skin()
        return skin.execution_lanes if skin.execution_lanes else []
    except Exception:
        return []


def get_skin_flow_diagram() -> str:
    """Get the flow diagram template from the active skin."""
    try:
        _ensure_skin_loaded()
        from hermes_cli.skin_engine import get_active_skin
        skin = get_active_skin()
        return skin.flow_diagram if skin.flow_diagram else ""
    except Exception:
        return ""


def get_skin_hero_frames() -> List[str]:
    """Get hero animation frames from the active skin."""
    try:
        _ensure_skin_loaded()
        from hermes_cli.skin_engine import get_active_skin
        skin = get_active_skin()
        return skin.hero_frames if skin.hero_frames else []
    except Exception:
        return []


def get_skin_dashboard_settings() -> Dict[str, Any]:
    """Get dashboard-specific settings from the active skin."""
    try:
        _ensure_skin_loaded()
        from hermes_cli.skin_engine import get_active_skin
        skin = get_active_skin()
        return skin.dashboard if skin.dashboard else {}
    except Exception:
        return {}


def get_skin_notifications_config() -> Dict[str, str]:
    """Get notification icons from the active skin."""
    try:
        _ensure_skin_loaded()
        from hermes_cli.skin_engine import get_active_skin
        skin = get_active_skin()
        return skin.notifications if skin.notifications else {}
    except Exception:
        return {}


def get_gods_with_pixel_art() -> List[Dict[str, Any]]:
    """Get all gods with their pixel art, lore, abilities, and quotes.
    
    Returns list of god data dicts with:
    - name, icon, face, title, domain, color
    - pixel_art (braille art string)
    - lore (backstory text)
    - abilities (list of power descriptions)
    - quotes (list of divine quotes)
    """
    try:
        _ensure_skin_loaded()
        from hermes_cli.skin_engine import get_active_skin
        skin = get_active_skin()
        pantheon = skin.pantheon if skin.pantheon else []
        
        gods_data = []
        for god in pantheon:
            god_name = god.get("name", "Unknown")
            
            god_data = {
                "name": god_name,
                "icon": god.get("icon", "✦"),
                "face": god.get("face", "(-_-)"),
                "title": god.get("title", ""),
                "domain": god.get("domain", ""),
                "color": skin.get_god_color(god_name) if hasattr(skin, 'get_god_color') else "#FFD700",
                "pixel_art": skin.get_god_pixel_art(god_name) if hasattr(skin, 'get_god_pixel_art') else "",
                "lore": skin.get_god_lore(god_name) if hasattr(skin, 'get_god_lore') else "",
                "abilities": skin.get_god_abilities(god_name) if hasattr(skin, 'get_god_abilities') else [],
                "quotes": skin.get_god_quotes(god_name) if hasattr(skin, 'get_god_quotes') else [],
            }
            gods_data.append(god_data)
        
        return gods_data
    except Exception:
        return []


def get_god_detail(god_name: str) -> Dict[str, Any]:
    """Get detailed information for a specific god.
    
    Returns dict with all god data including pixel art, lore, abilities, quotes.
    """
    try:
        _ensure_skin_loaded()
        from hermes_cli.skin_engine import get_active_skin
        skin = get_active_skin()
        pantheon = skin.pantheon if skin.pantheon else []
        
        for god in pantheon:
            if god.get("name") == god_name:
                return {
                    "name": god_name,
                    "icon": god.get("icon", "✦"),
                    "face": god.get("face", "(-_-)"),
                    "title": god.get("title", ""),
                    "domain": god.get("domain", ""),
                    "color": skin.get_god_color(god_name) if hasattr(skin, 'get_god_color') else "#FFD700",
                    "pixel_art": skin.get_god_pixel_art(god_name) if hasattr(skin, 'get_god_pixel_art') else "",
                    "lore": skin.get_god_lore(god_name) if hasattr(skin, 'get_god_lore') else "",
                    "abilities": skin.get_god_abilities(god_name) if hasattr(skin, 'get_god_abilities') else [],
                    "quotes": skin.get_god_quotes(god_name) if hasattr(skin, 'get_god_quotes') else [],
                }
        return {}
    except Exception:
        return {}
