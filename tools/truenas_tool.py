"""TrueNAS tool for querying NAS system status via REST API.

Registers a single LLM-callable tool:
- ``truenas_query`` — query TrueNAS system information (status, pools,
  disks, shares, alerts, services, or full summary).

Authentication uses a TrueNAS API key via ``TRUENAS_API_KEY`` env var.
The TrueNAS URL is read from ``TRUENAS_URL`` (default: https://truenas.local).
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

# Kept for backward compatibility (e.g. test monkeypatching); prefer _get_config().
_TRUENAS_URL: str = ""
_TRUENAS_API_KEY: str = ""

# TLS: TrueNAS uses self-signed certs by default, so we accept all.
_CTX = ssl._create_unverified_context()


def _get_config():
    """Return (truenas_url, truenas_api_key) from env vars at call time."""
    return (
        (
            _TRUENAS_URL
            or os.getenv("TRUENAS_URL", "https://truenas.local")
        ).rstrip("/"),
        _TRUENAS_API_KEY or os.getenv("TRUENAS_API_KEY", ""),
    )


def _check_truenas_available() -> bool:
    """Return True if TRUENAS_API_KEY is set so the tool is gated correctly."""
    _, key = _get_config()
    return bool(key)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _api_get(path: str, timeout: int = 15) -> dict:
    """Make a GET request to the TrueNAS REST API and return parsed JSON."""
    url, key = _get_config()
    if not key:
        return {"error": "TRUENAS_API_KEY not set. Add it to ~/.hermes/.env"}
    full_url = f"{url}/api/v2.0{path}"
    req = urllib.request.Request(full_url)
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, context=_CTX, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        return {"error": f"HTTP {e.code}: {body}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection failed: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def _format_bytes(n: int) -> str:
    """Format bytes to human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _format_disk(disk: dict) -> dict:
    """Compact disk summary."""
    return {
        "name": disk.get("name", "?"),
        "serial": disk.get("serial", "?"),
        "size": _format_bytes(disk.get("size", 0)),
        "model": disk.get("model", "?"),
        "pool": disk.get("pool", "-"),
        "rotation_rate": disk.get("rotation_rate", 0),
        "type": disk.get("type", "?"),
    }


def _format_pool(pool: dict) -> dict:
    """Compact pool summary."""
    topology = pool.get("topology", {})
    vdevs = []
    for vdev in topology.get("data", []):
        children = [
            c.get("name", "?") for c in vdev.get("children", [])
        ]
        vdevs.append({
            "type": vdev.get("type", "?"),
            "status": vdev.get("status", "?"),
            "disks": children,
        })
    scan = pool.get("scan", {})
    return {
        "name": pool.get("name", "?"),
        "status": pool.get("status", "?"),
        "healthy": pool.get("healthy", False),
        "size": _format_bytes(pool.get("size", 0)),
        "used": _format_bytes(pool.get("allocated", 0)),
        "free": _format_bytes(pool.get("free", 0)),
        "fragmentation": pool.get("fragmentation", "?"),
        "vdevs": vdevs,
        "last_scrub": scan.get("state", "?"),
        "scrub_errors": scan.get("errors", 0),
    }


# ---------------------------------------------------------------------------
# Query handlers
# ---------------------------------------------------------------------------


def _handle_summary() -> str:
    """Full system summary — system info + pools + alerts."""
    system = _api_get("/system/info")
    if "error" in system:
        return json.dumps(system)

    pools_data = _api_get("/pool")
    alerts_data = _api_get("/alert/list")

    pools = [_format_pool(p) for p in pools_data] if isinstance(pools_data, list) else []
    alerts = list(alerts_data) if isinstance(alerts_data, list) else []

    status = system.get("status", "?")
    # TrueNAS Scale doesn't return status in system/info; infer from pool health
    pool_healthy = all(p["healthy"] for p in pools) if pools else True

    summary = {
        "hostname": system.get("hostname", "?"),
        "version": system.get("version", "?"),
        "uptime": system.get("uptime", "?"),
        "cpu": system.get("model", "?"),
        "cores": system.get("physical_cores", "?"),
        "memory": _format_bytes(system.get("physmem", 0)),
        "timezone": system.get("timezone", "?"),
        "status": "ONLINE" if pool_healthy else "DEGRADED",
        "pools": pools,
        "alerts": alerts,
    }
    return json.dumps(summary, indent=2, ensure_ascii=False)


def _handle_pools() -> str:
    """List all pools with vdev topology and health."""
    data = _api_get("/pool")
    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)
    pools = [_format_pool(p) for p in data]
    return json.dumps({"count": len(pools), "pools": pools}, indent=2, ensure_ascii=False)


def _handle_disks() -> str:
    """List all disks with serial, model, size."""
    data = _api_get("/disk")
    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)
    disks = [_format_disk(d) for d in data]
    return json.dumps({"count": len(disks), "disks": disks}, indent=2, ensure_ascii=False)


def _handle_shares() -> str:
    """List SMB and NFS shares."""
    smb = _api_get("/sharing/smb")
    nfs = _api_get("/sharing/nfs")

    result = {}
    if isinstance(smb, list):
        result["smb"] = [
            {"name": s.get("name", "?"), "path": s.get("path", "?"), "enabled": s.get("enabled", False)}
            for s in smb
        ]
    elif isinstance(smb, dict) and "error" in smb:
        result["smb_error"] = smb["error"]

    if isinstance(nfs, list):
        result["nfs"] = [
            {"path": s.get("path", "?"), "enabled": s.get("enabled", False), "networks": s.get("networks", [])}
            for s in nfs
        ]
    elif isinstance(nfs, dict) and "error" in nfs:
        result["nfs_error"] = nfs["error"]

    result["smb_count"] = len(result.get("smb", []))
    result["nfs_count"] = len(result.get("nfs", []))
    return json.dumps(result, indent=2, ensure_ascii=False)


def _handle_alerts() -> str:
    """List active alerts/warnings."""
    data = _api_get("/alert/list")
    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)
    return json.dumps({"count": len(data), "alerts": data}, indent=2, ensure_ascii=False)


def _handle_services() -> str:
    """List services and their running/auto-start status."""
    data = _api_get("/service")
    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)

    # Known service labels for readability
    labels = {
        "cifs": "SMB", "nfs": "NFS", "ssh": "SSH",
        "ftp": "FTP", "tftp": "TFTP", "openvpn": "OpenVPN",
        "snmp": "SNMP", "ups": "UPS", "iscsitarget": "iSCSI",
        "webshell": "Web Shell", "nvmet": "NVMe-oF",
    }

    services = []
    for s in data:
        name = s.get("service", "?")
        services.append({
            "name": name,
            "label": labels.get(name, name),
            "running": s.get("state", False),
            "auto_start": s.get("enable", False),
        })

    return json.dumps({"count": len(services), "services": services}, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_ACTIONS = {
    "summary": _handle_summary,
    "pools": _handle_pools,
    "disks": _handle_disks,
    "shares": _handle_shares,
    "alerts": _handle_alerts,
    "services": _handle_services,
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

TRUENAS_QUERY_SCHEMA = {
    "name": "truenas_query",
    "description": (
        "Query a TrueNAS Scale system over its REST API. "
        "Returns JSON with system information. "
        "Requires TRUENAS_API_KEY and TRUENAS_URL environment variables to be set. "
        "All operations are read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": (
                    "What information to retrieve:\n"
                    "- **summary**: Full system overview (hostname, version, uptime, CPU, RAM, pool health, alerts)\n"
                    "- **pools**: ZFS pool list with vdev topology, health, capacity\n"
                    "- **disks**: Physical disk list with serial, model, size\n"
                    "- **shares**: SMB and NFS share list\n"
                    "- **alerts**: Active alerts and warnings\n"
                    "- **services**: Service status (running/stopped, auto-start enabled)"
                ),
                "enum": ["summary", "pools", "disks", "shares", "alerts", "services"],
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
    name="truenas_query",
    toolset="truenas",
    schema=TRUENAS_QUERY_SCHEMA,
    handler=lambda args, **kw: _handle_query(
        action=args.get("action", ""), task_id=kw.get("task_id")),
    check_fn=_check_truenas_available,
    requires_env=["TRUENAS_API_KEY"],
    emoji="🖥️",
)
