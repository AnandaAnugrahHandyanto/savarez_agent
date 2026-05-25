"""Local Single Brain beta profile wiring checks.

These tests validate only local config/source behavior. They do not start or
restart the gateway, post to Slack, read vault data, or perform external writes.
"""

from pathlib import Path
import json

import pytest
import yaml

from gateway.config import PlatformConfig
from gateway.platforms.api_server import APIServerAdapter


REPO_ROOT = Path(__file__).resolve().parents[2]
SINGLEBRAIN_PROFILE = REPO_ROOT.parent / "profiles" / "single-brain"
CONFIG_PATH = SINGLEBRAIN_PROFILE / "config.yaml"
SOUL_PATH = SINGLEBRAIN_PROFILE / "SOUL.md"
PREFILL_PATH = SINGLEBRAIN_PROFILE / "approved-sources-prefill.json"

EXPECTED_ALLOWED = {
    "GET /health",
    "GET /health/detailed",
    "GET /v1/models",
    "GET /v1/capabilities",
    "POST /v1/chat/completions",
    "POST /v1/responses",
}
EXPECTED_DENIED = {
    "POST /v1/runs",
    "POST /v1/runs/*/approval",
    "POST /v1/runs/*/stop",
    "DELETE /v1/responses/*",
    "POST /api/jobs",
    "PATCH /api/jobs/*",
    "DELETE /api/jobs/*",
    "POST /api/jobs/*/pause",
    "POST /api/jobs/*/resume",
    "POST /api/jobs/*/run",
}


def _singlebrain_profile_config() -> dict:
    if not CONFIG_PATH.exists():
        pytest.skip(f"Single Brain profile config not present in this checkout: {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _singlebrain_api_server_block() -> dict:
    cfg = _singlebrain_profile_config()
    return ((cfg.get("platforms") or {}).get("api_server") or {})


def test_singlebrain_profile_wires_api_server_readonly_report_only_policy():
    api_server = _singlebrain_api_server_block()
    policy = ((api_server.get("extra") or {}).get("access_policy") or {})

    assert api_server.get("enabled") is True
    assert (api_server.get("extra") or {}).get("host") == "127.0.0.1"
    assert (api_server.get("extra") or {}).get("port") == 8642
    assert policy["name"] == "singlebrain-ambient-sg-beta"
    assert policy["mode"] == "read_only_report_only"
    assert set(policy["allowed_endpoints"]) == EXPECTED_ALLOWED
    assert set(policy["denied_endpoints"]) == EXPECTED_DENIED
    assert policy["report_path"] == "artifacts/singlebrain-gateway-api-access-report.jsonl"
    assert policy["external_writes_enabled"] is False
    assert policy["live_slack_posting_enabled"] is False
    assert policy["gateway_restart_enabled"] is False


def test_singlebrain_profile_policy_normalizes_and_blocks_write_endpoints():
    api_server = _singlebrain_api_server_block()
    adapter = APIServerAdapter(
        PlatformConfig(
            enabled=api_server.get("enabled", False),
            extra=api_server.get("extra") or {},
        )
    )

    advertised = adapter._access_policy_for_capabilities()
    assert advertised is not None
    assert advertised["mode"] == "read_only_report_only"
    assert "POST /v1/runs" in advertised["denied_endpoints"]

    denied = adapter._read_only_policy_denial("POST", "/v1/runs")
    assert denied is not None
    assert denied.status == 403

    wildcard_denied = adapter._read_only_policy_denial("POST", "/v1/runs/run_123/approval")
    assert wildcard_denied is not None
    assert wildcard_denied.status == 403

    sensitive_get_denials = [
        ("GET", "/v1/health"),
        ("GET", "/v1/responses/resp_123"),
        ("GET", "/v1/runs/run_123"),
        ("GET", "/v1/runs/run_123/events"),
        ("GET", "/api/jobs"),
        ("GET", "/api/jobs/job_123"),
    ]
    for method, path in sensitive_get_denials:
        denied = adapter._read_only_policy_denial(method, path)
        assert denied is not None, path
        assert denied.status == 403, path

    allowed_probe = adapter._read_only_policy_denial("GET", "/v1/capabilities")
    assert allowed_probe is None

    normal_read = adapter._read_only_policy_denial("POST", "/v1/chat/completions")
    assert normal_read is None


def test_singlebrain_profile_prompt_uses_permissioned_readonly_context_not_approved_corpus_gate():
    """Profile prompt/prefill must not regress to approved-source-block-only mode."""
    if not SOUL_PATH.exists() or not PREFILL_PATH.exists():
        pytest.skip(f"Single Brain prompt files not present in this checkout: {SINGLEBRAIN_PROFILE}")

    soul = SOUL_PATH.read_text(encoding="utf-8")
    prefill_messages = json.loads(PREFILL_PATH.read_text(encoding="utf-8"))
    prefill_policy_text = "\n".join(
        message.get("content", "").split("\n\n--- SOURCE:", 1)[0]
        for message in prefill_messages
    )
    policy_text = f"{soul}\n{prefill_policy_text}"

    assert "available permissioned read-only connector/docs context" in policy_text
    assert "Use available permissioned read-only connector/docs context for factual answers" in soul
    assert "Use ONLY this corpus" not in prefill_policy_text
    assert "Use only those source blocks for factual answers" not in policy_text
    assert "approved source blocks only" not in policy_text.lower()
    assert "approved source rows" not in policy_text.lower()
    assert "approved summary rows" not in policy_text.lower()
    assert "do not perform external writes" in policy_text.lower() or "you do not take actions" in policy_text.lower()
    assert "unrestricted dumps" in policy_text.lower() or "raw dumps" in policy_text.lower()
    assert "hr/recruiting/compensation" in policy_text.lower() or "hr/comp" in policy_text.lower()


def test_singlebrain_api_server_has_connector_access_not_no_mcp_muzzle():
    """API reads should have the Single Grain connector lane, not a no-MCP muzzle."""
    cfg = _singlebrain_profile_config()
    api_toolsets = ((cfg.get("platform_toolsets") or {}).get("api_server") or [])

    assert "singlegrain-gateway" in api_toolsets
    assert "no_mcp" not in api_toolsets
