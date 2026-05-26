"""UnRAID tool for querying NAS system status via GraphQL API.

Registers a single LLM-callable tool:
- ``unraid_query`` — query UnRAID system information (info, disks, docker
  containers, notifications, or full summary).

Authentication uses an UnRAID API key via ``UNRAID_API_KEY`` env var.
The UnRAID URL is read from ``UNRAID_URL`` (default: https://unraid.local).

NOTE: The API key must have proper data access permissions (READ_ANY) for
data queries in UnRAID Settings → API Keys. Schema introspection queries
work without auth, but data queries require authorized API keys.
"""

import json
import logging
import os
import ssl
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_UNRAID_URL: str = ""
_UNRAID_API_KEY: str = ""

_CTX = ssl._create_unverified_context()


def _get_config():
    """Return (unraid_url, unraid_api_key) from env vars at call time."""
    return (
        (
            _UNRAID_URL
            or os.getenv("UNRAID_URL", "https://unraid.local")
        ).rstrip("/"),
        _UNRAID_API_KEY or os.getenv("UNRAID_API_KEY", ""),
    )


def _check_unraid_available() -> bool:
    """Return True if UNRAID_API_KEY is set."""
    _, key = _get_config()
    return bool(key)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _gql(query: str, timeout: int = 15) -> dict:
    """Send a GraphQL query to UnRAID and return parsed JSON."""
    url, key = _get_config()
    if not key:
        return {"error": "UNRAID_API_KEY not set. Add it to ~/.hermes/.env"}

    graphql_url = f"{url}/graphql"
    payload = json.dumps({"query": query}).encode()
    req = urllib.request.Request(graphql_url, data=payload)
    req.add_header("Content-Type", "application/json")
    req.add_header("x-api-key", key)

    try:
        with urllib.request.urlopen(req, context=_CTX, timeout=timeout) as resp:
            parsed = json.loads(resp.read().decode())
            # GraphQL returns 200 even when there are errors; check both paths
            if parsed.get("errors"):
                error_msgs = [e.get("message", "?") for e in parsed["errors"]]
                return {"error": "; ".join(error_msgs)}
            if parsed.get("data") is None:
                return {"error": "GraphQL returned null data"}
            return parsed
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        return {"error": f"HTTP {e.code}: {body[:300]}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection failed: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def _format_bytes(kb: int) -> str:
    """Format kilobytes to human-readable string."""
    if not kb:
        return "?"
    n = kb * 1024  # convert to bytes
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


# ---------------------------------------------------------------------------
# Query handlers
# ---------------------------------------------------------------------------


def _handle_info() -> str:
    """System info — CPU, OS, uptime."""
    # InfoOs fields: hostname, distro, kernel, uptime
    # InfoCpu fields: model, cores, threads
    # InfoVersions: has core (CoreVersions) and packages (PackageVersions)
    result = _gql("""
    {
      info {
        time
        cpu { model cores threads }
        os { hostname distro kernel uptime }
      }
    }
    """)
    if "error" in result:
        return json.dumps(result)

    data = result.get("data", {}).get("info", {})
    cpu = data.get("cpu", {})
    os_info = data.get("os", {})

    info = {
        "hostname": os_info.get("hostname", "?"),
        "os": "UnRAID",
        "distro": os_info.get("distro", "?"),
        "kernel": os_info.get("kernel", "?"),
        "uptime": os_info.get("uptime", "?"),
        "cpu": {
            "model": cpu.get("model", "?"),
            "cores": cpu.get("cores", 0),
            "threads": cpu.get("threads", 0),
        },
        "note": "Memory info unavailable via UnRAID GraphQL API",
    }
    return json.dumps(info, indent=2, ensure_ascii=False)


def _handle_disks() -> str:
    """List all disks."""
    # Disk fields: name, size(Float), type, serialNum, smartStatus(DiskSmartStatus), temperature(Float)
    result = _gql("{ disks { name size type serialNum temperature smartStatus } }")
    if "error" in result:
        return json.dumps(result)

    disks_data = result.get("data", {}).get("disks", [])
    disks = []
    for d in disks_data:
        smart = d.get("smartStatus")
        if isinstance(smart, dict):
            smart = smart.get("name", "?")
        disks.append({
            "name": d.get("name", "?"),
            "size": _format_bytes(d.get("size", 0)),
            "type": d.get("type", "?"),
            "serial": d.get("serialNum", "?"),
            "temperature": d.get("temperature", "?"),
            "smart_status": smart,
        })
    return json.dumps({"count": len(disks), "disks": disks}, indent=2, ensure_ascii=False)


def _handle_docker() -> str:
    """List Docker containers."""
    # Query: docker { containers { names, image, status, state { ... } } }
    result = _gql("{ docker { containers { names image status } } }")
    if "error" in result:
        return json.dumps(result)

    containers = result.get("data", {}).get("docker", {}).get("containers", [])
    formatted = []
    for c in containers:
        formatted.append({
            "name": (c.get("names") or ["?"])[0],
            "image": c.get("image", "?"),
            "status": c.get("status", "?"),
        })
    return json.dumps({"count": len(formatted), "containers": formatted}, indent=2, ensure_ascii=False)


def _handle_alerts() -> str:
    """List notifications / alerts."""
    # Notifications has: overview(NotificationOverview), warningsAndAlerts([Notification!]!)
    result = _gql("{ notifications { warningsAndAlerts { id } } }")
    if "error" in result:
        return json.dumps(result)

    alerts = result.get("data", {}).get("notifications", {}).get("warningsAndAlerts", [])
    return json.dumps({"count": len(alerts), "alerts": alerts}, indent=2, ensure_ascii=False)


def _handle_summary() -> str:
    """Full system summary."""
    info_result = _gql("""
    {
      info {
        time
        cpu { model cores threads }
        os { hostname distro kernel uptime }
      }
    }
    """)
    disks_result = _gql("{ disks { name size type serialNum temperature smartStatus } }")
    docker_result = _gql("{ docker { containers { names image status } } }")
    alerts_result = _gql("{ notifications { warningsAndAlerts { id } } }")

    summary = {"status": "unknown"}

    if "error" not in info_result:
        data = info_result.get("data", {}).get("info", {})
        cpu = data.get("cpu", {})
        os_info = data.get("os", {})
        summary["hostname"] = os_info.get("hostname", "?")
        summary["os"] = "UnRAID"
        summary["kernel"] = os_info.get("kernel", "?")
        summary["uptime"] = os_info.get("uptime", "?")
        summary["cpu"] = {
            "model": cpu.get("model", "?"),
            "cores": cpu.get("cores", 0),
        }
        summary["status"] = "ONLINE"

    if "error" not in disks_result:
        disks_data = disks_result.get("data", {}).get("disks", [])
        summary["disks"] = [
            {"name": d.get("name", "?"), "size": _format_bytes(d.get("size", 0)),
             "type": d.get("type", "?"), "smart": d.get("smartStatus", {})}
            for d in disks_data
        ]
        summary["disk_count"] = len(disks_data)
    else:
        summary["disks"] = []
        summary["disk_error"] = disks_result["error"]

    if "error" not in docker_result:
        containers = docker_result.get("data", {}).get("docker", {}).get("containers", [])
        summary["docker"] = [
            {"name": (c.get("names") or ["?"])[0], "image": c.get("image", "?"), "status": c.get("status", "?")}
            for c in containers
        ]
        summary["docker_count"] = len(containers)

    if "error" not in alerts_result:
        alerts = alerts_result.get("data", {}).get("notifications", {}).get("warningsAndAlerts", [])
        summary["alerts"] = alerts
        summary["alert_count"] = len(alerts)
    else:
        summary["alerts"] = []

    return json.dumps(summary, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_ACTIONS = {
    "summary": _handle_summary,
    "info": _handle_info,
    "disks": _handle_disks,
    "docker": _handle_docker,
    "alerts": _handle_alerts,
}


def _handle_query(action: str, task_id: str = None) -> str:
    """Dispatch to the appropriate handler."""
    handler = _ACTIONS.get(action)
    if not handler:
        valid = ", ".join(sorted(_ACTIONS))
        return json.dumps({
            "error": f"Unknown action '{action}'. Valid actions: {valid}",
        })
    return handler()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

UNRAID_QUERY_SCHEMA = {
    "name": "unraid_query",
    "description": (
        "Query an UnRAID server over its GraphQL API. "
        "Returns JSON with system information. "
        "Requires UNRAID_API_KEY and UNRAID_URL environment variables. "
        "All operations are read-only. "
        "Note: API key must have READ_ANY data permissions in UnRAID Settings."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": (
                    "What information to retrieve:\n"
                    "- **summary**: Full system overview (CPU, OS, disks, Docker, alerts)\n"
                    "- **info**: System information (OS, kernel, CPU, uptime)\n"
                    "- **disks**: Physical disk list with serial, size, SMART status\n"
                    "- **docker**: Docker container list (names, images, status)\n"
                    "- **alerts**: Active notifications and warnings"
                ),
                "enum": ["summary", "info", "disks", "docker", "alerts"],
            },
        },
        "required": ["action"],
    },
}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

from tools.registry import registry  # noqa: E402

registry.register(
    name="unraid_query",
    toolset="unraid",
    schema=UNRAID_QUERY_SCHEMA,
    handler=lambda args, **kw: _handle_query(
        action=args.get("action", ""), task_id=kw.get("task_id")),
    check_fn=_check_unraid_available,
    requires_env=["UNRAID_API_KEY"],
    emoji="🖥️",
)