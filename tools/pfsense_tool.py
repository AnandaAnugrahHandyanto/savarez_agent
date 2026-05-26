"""pfSense tool for querying firewall/gateway status via REST API.

Registers a single LLM-callable tool:
- ``pfsense_query`` — query pfSense system information (summary, interfaces,
  gateways, firewall rules, DHCP leases, ARP table, services, DNS, VPNs,
  CARP status, or routing).

Authentication uses a pfSense API key via ``PFSENSE_API_KEY`` env var.
The pfSense URL is read from ``PFSENSE_URL`` (default: https://10.0.0.1).

Designed for pfSense REST API v2 (pfrest/pfSense-pkg-RESTAPI).
Endpoint paths derived from the OpenAPI v2.8.0 schema.
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

_PFSENSE_URL: str = ""
_PFSENSE_API_KEY: str = ""

_CTX = ssl._create_unverified_context()

# Default gateway IP (Mert's network: pfSense at 10.0.0.1)
_DEFAULT_URL = "https://10.0.0.1"


def _get_config():
    """Return (pfsense_url, pfsense_api_key) from env vars at call time."""
    return (
        (
            _PFSENSE_URL
            or os.getenv("PFSENSE_URL", _DEFAULT_URL)
        ).rstrip("/"),
        _PFSENSE_API_KEY or os.getenv("PFSENSE_API_KEY", ""),
    )


def _check_pfsense_available() -> bool:
    """Return True if PFSENSE_API_KEY is set so the tool is gated correctly."""
    _, key = _get_config()
    return bool(key)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _api_get(path: str, timeout: int = 15) -> dict:
    """Make a GET request to pfSense REST API v2 and return parsed JSON."""
    url, key = _get_config()
    if not key:
        return {"error": "PFSENSE_API_KEY not set. Add it to ~/.hermes/.env"}

    full_url = f"{url}/api/v2{path}"
    req = urllib.request.Request(full_url)
    req.add_header("X-API-Key", key)
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, context=_CTX, timeout=timeout) as resp:
            body = resp.read().decode()
            parsed = json.loads(body)
            # pfSense REST API v2 wraps response in {code, status, response_id, message, data, _links}
            # Return the full response so handlers can inspect error/data fields.
            return parsed
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        # Try to parse error JSON
        try:
            err_data = json.loads(body)
            return err_data
        except json.JSONDecodeError:
            pass
        if e.code == 401:
            return {"error": "Authentication failed (HTTP 401). Check your PFSENSE_API_KEY."}
        return {"error": f"HTTP {e.code}: {body[:500]}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection failed: {e.reason}"}
    except json.JSONDecodeError:
        return {"error": "API returned non-JSON response"}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def _format_uptime(seconds_str: str) -> str:
    """Format pfSense uptime string (e.g. '12:34:56' or seconds)."""
    if not seconds_str or seconds_str == "?":
        return "?"
    # pfSense may return uptime as HH:MM:SS
    if ":" in seconds_str:
        parts = seconds_str.split(":")
        if len(parts) == 3:
            h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
            days = h // 24
            hours = h % 24
            result = []
            if days > 0:
                result.append(f"{days}g")
            result.append(f"{hours}s")
            result.append(f"{m}d")
            return " ".join(result)
    return str(seconds_str)


def _format_bytes(n) -> str:
    """Format bytes to human-readable string."""
    if not n:
        return "0 B"
    try:
        n = int(n)
    except (ValueError, TypeError):
        return str(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n //= 1024
    return f"{n:.1f} PB"


def _extract_data(resp: dict) -> any:
    """Extract the 'data' field from a pfSense REST API v2 response.

    The API wraps responses in {code, status, response_id, message, data, _links}.
    For collection endpoints, data is a list. For detail endpoints, data is a dict.
    On error, returns the error info.
    """
    if "error" in resp:
        return resp
    # Check for API-level error
    if resp.get("code", 200) >= 400:
        return {"error": resp.get("message", "API returned error"), "response_id": resp.get("response_id")}
    data = resp.get("data")
    if data is None:
        # Some endpoints return data directly without wrapping
        return resp
    return data


def _ensure_list(data) -> list:
    """Return a list whether data is a single item or list."""
    if isinstance(data, list):
        return data
    if data is None:
        return []
    return [data]


# ---------------------------------------------------------------------------
# Query handlers
# ---------------------------------------------------------------------------


def _handle_summary() -> str:
    """Full system overview — system info, interfaces, gateways, services, DHCP, VPN."""
    system = _api_get("/status/system")
    interfaces = _api_get("/status/interfaces")
    gateways_resp = _api_get("/status/gateways")
    services_resp = _api_get("/status/services")
    dhcp_resp = _api_get("/status/dhcp_server/leases")
    ovpn_clients = _api_get("/status/openvpn/clients")
    ipsec_sas = _api_get("/status/ipsec/sas")

    summary = {"hostname": "?", "version": "?", "uptime": "?", "status": "UNKNOWN"}

    # System info
    sys_data = _extract_data(system)
    if isinstance(sys_data, dict) and "error" not in sys_data:
        summary["hostname"] = sys_data.get("hostname", "?")
        summary["version"] = sys_data.get("version", "?")
        summary["uptime"] = _format_uptime(sys_data.get("uptime", "?"))
        summary["cpu_load"] = sys_data.get("load_average", "?")
        summary["status"] = "ONLINE"

    # Interfaces
    if_data = _extract_data(interfaces)
    if isinstance(if_data, list):
        summary["interfaces"] = []
        for iface in if_data:
            name = iface.get("if", iface.get("descr", "?"))
            summary["interfaces"].append({
                "name": name,
                "enabled": iface.get("enable", True),
                "ipv4": iface.get("ipaddr", "?"),
                "status": iface.get("status", iface.get("link", "?")),
                "in": _format_bytes(iface.get("inpkts", 0)),
                "out": _format_bytes(iface.get("outpkts", 0)),
            })

    # Gateways
    gw_data = _extract_data(gateways_resp)
    if isinstance(gw_data, list):
        summary["gateways"] = []
        for gw in gw_data:
            summary["gateways"].append({
                "name": gw.get("name", "?"),
                "interface": gw.get("interface", "?"),
                "gateway_ip": gw.get("gateway", "?"),
                "status": gw.get("status", "?"),
                "delay": gw.get("delay", "?"),
                "loss": gw.get("loss", "?"),
            })

    # Services
    svc_data = _extract_data(services_resp)
    if isinstance(svc_data, list):
        summary["services"] = []
        for s in svc_data:
            summary["services"].append({
                "name": s.get("name", "?"),
                "description": s.get("description", ""),
                "running": s.get("running", False),
            })

    # DHCP leases count
    dhcp_data = _extract_data(dhcp_resp)
    if isinstance(dhcp_data, list):
        summary["dhcp_leases"] = len(dhcp_data)

    # OpenVPN clients count
    ovpn_data = _extract_data(ovpn_clients)
    if isinstance(ovpn_data, list):
        summary["openvpn_clients"] = len(ovpn_data)

    # IPsec SAs count
    ipsec_data = _extract_data(ipsec_sas)
    if isinstance(ipsec_data, list):
        summary["ipsec_sas"] = len(ipsec_data)

    return json.dumps(summary, indent=2, ensure_ascii=False)


def _handle_interfaces() -> str:
    """List all network interfaces with status."""
    resp = _api_get("/status/interfaces")
    data = _extract_data(resp)
    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)

    interfaces = []
    for iface in _ensure_list(data):
        interfaces.append({
            "name": iface.get("if", iface.get("descr", "?")),
            "ipv4": iface.get("ipaddr", "?"),
            "ipv6": iface.get("ipv6addr", ""),
            "subnet": iface.get("subnet", ""),
            "gateway": iface.get("gateway", ""),
            "status": iface.get("status", iface.get("link", "?")),
            "media": iface.get("media", iface.get("media_type", "")),
            "mtu": iface.get("mtu", iface.get("mtu", "")),
            "inpkts": iface.get("inpkts", 0),
            "outpkts": iface.get("outpkts", 0),
        })

    return json.dumps({"count": len(interfaces), "interfaces": interfaces}, indent=2, ensure_ascii=False)


def _handle_gateways() -> str:
    """List all configured gateways with status and latency."""
    resp = _api_get("/status/gateways")
    data = _extract_data(resp)
    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)

    gateways = []
    for gw in _ensure_list(data):
        gateways.append({
            "name": gw.get("name", "?"),
            "interface": gw.get("interface", "?"),
            "gateway_ip": gw.get("gateway", "?"),
            "status": gw.get("status", "?"),
            "delay": gw.get("delay", "?"),
            "loss": gw.get("loss", "?"),
            "stddev": gw.get("stddev", "?"),
            "monitor_ip": gw.get("monitor", "?"),
        })

    return json.dumps({"count": len(gateways), "gateways": gateways}, indent=2, ensure_ascii=False)


def _handle_services() -> str:
    """List pfSense services and running status."""
    resp = _api_get("/status/services")
    data = _extract_data(resp)
    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)

    services = []
    for s in _ensure_list(data):
        services.append({
            "name": s.get("name", "?"),
            "description": s.get("description", ""),
            "running": s.get("running", False),
        })

    return json.dumps({"count": len(services), "services": services}, indent=2, ensure_ascii=False)


def _handle_firewall_rules() -> str:
    """List firewall rules (read-only)."""
    resp = _api_get("/firewall/rules")
    data = _extract_data(resp)
    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)

    rules = []
    for r in _ensure_list(data):
        rules.append({
            "number": r.get("number", "?"),
            "type": r.get("type", "pass"),
            "interface": r.get("interface", "?"),
            "protocol": r.get("protocol", "any"),
            "source": r.get("source", "any"),
            "destination": r.get("destination", "any"),
            "port": r.get("destination_port", ""),
            "description": r.get("description", ""),
            "enabled": r.get("enabled", True),
        })

    return json.dumps({"count": len(rules), "rules": rules}, indent=2, ensure_ascii=False)


def _handle_dhcp_leases() -> str:
    """List DHCP leases."""
    resp = _api_get("/status/dhcp_server/leases")
    data = _extract_data(resp)
    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)

    leases = []
    for l in _ensure_list(data):
        leases.append({
            "ip": l.get("ip", "?"),
            "mac": l.get("mac", "?"),
            "hostname": l.get("hostname", ""),
            "start": l.get("start", ""),
            "end": l.get("end", ""),
            "online": l.get("online", l.get("active", "")),
            "if": l.get("if", ""),
        })

    return json.dumps({"count": len(leases), "leases": leases}, indent=2, ensure_ascii=False)


def _handle_arp_table() -> str:
    """List ARP table entries."""
    resp = _api_get("/diagnostics/arp_table")
    data = _extract_data(resp)
    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)

    entries = []
    for e in _ensure_list(data):
        entries.append({
            "ip": e.get("ip_address", e.get("ip", "?")),
            "mac": e.get("mac_address", e.get("mac", "?")),
            "interface": e.get("interface", "?"),
            "type": e.get("type", "?"),
            "hostname": e.get("hostname", ""),
        })

    return json.dumps({"count": len(entries), "entries": entries}, indent=2, ensure_ascii=False)


def _handle_dns_resolver() -> str:
    """List DNS resolver settings and status."""
    resp = _api_get("/services/dns_resolver/settings")
    data = _extract_data(resp)
    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)
    return json.dumps(data, indent=2, ensure_ascii=False)


def _handle_openvpn() -> str:
    """List OpenVPN servers and client connections."""
    servers_resp = _api_get("/status/openvpn/servers")
    clients_resp = _api_get("/status/openvpn/clients")

    result = {}

    svr_data = _extract_data(servers_resp)
    if isinstance(svr_data, list):
        result["servers"] = []
        for s in svr_data:
            result["servers"].append({
                "name": s.get("name", "?"),
                "mode": s.get("mode", "?"),
                "port": s.get("port", 0),
                "protocol": s.get("protocol", "?"),
                "connected": s.get("connected", 0),
            })
        result["server_count"] = len(result["servers"])

    cli_data = _extract_data(clients_resp)
    if isinstance(cli_data, list):
        result["clients"] = []
        for c in cli_data:
            result["clients"].append({
                "name": c.get("name", "?"),
                "status": c.get("status", "?"),
                "remote_host": c.get("remote_host", "?"),
                "remote_port": c.get("remote_port", 0),
            })
        result["client_count"] = len(result["clients"])

    return json.dumps(result, indent=2, ensure_ascii=False)


def _handle_ipsec() -> str:
    """List IPsec tunnel status (SAs)."""
    resp = _api_get("/status/ipsec/sas")
    data = _extract_data(resp)
    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)

    sas = []
    for sa in _ensure_list(data):
        sas.append({
            "name": sa.get("name", "?"),
            "status": sa.get("status", "?"),
            "local": sa.get("local", "?"),
            "remote": sa.get("remote", "?"),
            "bytes_in": _format_bytes(sa.get("bytes_in", 0)),
            "bytes_out": _format_bytes(sa.get("bytes_out", 0)),
        })

    return json.dumps({"count": len(sas), "ipsec_sas": sas}, indent=2, ensure_ascii=False)


def _handle_routes() -> str:
    """List routing gateways and static routes."""
    gw_resp = _api_get("/routing/gateways")
    static_resp = _api_get("/routing/static_route")

    result = {}

    gw_data = _extract_data(gw_resp)
    if isinstance(gw_data, list):
        result["gateways"] = []
        for g in gw_data:
            result["gateways"].append({
                "name": g.get("name", "?"),
                "gateway": g.get("gateway", "?"),
                "interface": g.get("interface", "?"),
                "default": g.get("is_default_gateway", False),
            })

    static_data = _extract_data(static_resp)
    if isinstance(static_data, list):
        result["static_routes"] = []
        for r in _ensure_list(static_data):
            result["static_routes"].append({
                "network": r.get("network", "?"),
                "gateway": r.get("gateway", "?"),
                "descr": r.get("descr", ""),
            })

    return json.dumps(result, indent=2, ensure_ascii=False)


def _handle_carp_status() -> str:
    """List CARP/HA status if configured."""
    resp = _api_get("/status/carp")
    data = _extract_data(resp)
    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)
    return json.dumps(data, indent=2, ensure_ascii=False)


def _handle_logs(action: str) -> str:
    """Read system/firewall/DHCP/auth logs."""
    log_map = {
        "system": "/status/logs/system",
        "firewall": "/status/logs/firewall",
        "dhcp": "/status/logs/dhcp",
        "auth": "/status/logs/auth",
        "openvpn": "/status/logs/openvpn",
    }
    path = log_map.get(action)
    if not path:
        valid = ", ".join(sorted(log_map))
        return json.dumps({"error": f"Unknown log type '{action}'. Valid: {valid}"})
    resp = _api_get(path)
    data = _extract_data(resp)
    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)
    return json.dumps(data, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_ACTIONS = {
    "summary": _handle_summary,
    "interfaces": _handle_interfaces,
    "gateways": _handle_gateways,
    "services": _handle_services,
    "firewall_rules": _handle_firewall_rules,
    "dhcp_leases": _handle_dhcp_leases,
    "arp_table": _handle_arp_table,
    "dns_resolver": _handle_dns_resolver,
    "openvpn": _handle_openvpn,
    "ipsec": _handle_ipsec,
    "routes": _handle_routes,
    "carp": _handle_carp_status,
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

PFSENSE_QUERY_SCHEMA = {
    "name": "pfsense_query",
    "description": (
        "Query a pfSense firewall/gateway over its REST API. "
        "Returns JSON with system information. "
        "Requires PFSENSE_API_KEY and PFSENSE_URL environment variables to be set. "
        "All operations are read-only. "
        "Uses pfSense REST API v2 (pfrest/pfSense-pkg-RESTAPI). "
        "Default PFSENSE_URL is https://10.0.0.1"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": (
                    "What information to retrieve:\n"
                    "- **summary**: Full system overview (hostname, version, uptime, interfaces, gateways, services, DHCP, VPN)\n"
                    "- **interfaces**: Network interface list with IPs, status, link state\n"
                    "- **gateways**: Gateway status with delay, packet loss, monitor IP\n"
                    "- **services**: pfSense service list with running/stopped status\n"
                    "- **firewall_rules**: Firewall rules (read-only, no modifications)\n"
                    "- **dhcp_leases**: DHCP lease list (IP, MAC, hostname, expiry)\n"
                    "- **arp_table**: ARP table entries\n"
                    "- **dns_resolver**: DNS resolver settings and status\n"
                    "- **openvpn**: OpenVPN server and client connection list\n"
                    "- **ipsec**: IPsec tunnel Security Association (SA) status\n"
                    "- **routes**: Routing gateways and static routes\n"
                    "- **carp**: CARP/HA failover status"
                ),
                "enum": [
                    "summary", "interfaces", "gateways", "services",
                    "firewall_rules", "dhcp_leases", "arp_table",
                    "dns_resolver", "openvpn", "ipsec", "routes", "carp",
                ],
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
    name="pfsense_query",
    toolset="pfsense",
    schema=PFSENSE_QUERY_SCHEMA,
    handler=lambda args, **kw: _handle_query(
        action=args.get("action", ""), task_id=kw.get("task_id")),
    check_fn=_check_pfsense_available,
    requires_env=["PFSENSE_API_KEY"],
    emoji="🛡️",
)