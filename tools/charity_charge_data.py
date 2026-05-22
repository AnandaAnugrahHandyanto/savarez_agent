"""Charity Charge Phase 1 data-plane tool scaffolds.

These tools intentionally do not perform live API calls yet. They provide stable
schemas, credential gating, and stub responses so the Phase 1 handlers can be
filled in once Charity Charge credentials land.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home
from hermes_cli.config import get_env_value
from tools.registry import registry

TOOLSET = "charity-charge-data"
STUB_MESSAGE = "Tool scaffolded but handler not implemented"

BIGQUERY_CREDENTIALS = ["~/.hermes/secrets/bq-service-account.json"]
HUBSPOT_CREDENTIALS = ["HUBSPOT_ACCESS_TOKEN"]
GOOGLE_ADS_CREDENTIALS = [
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_OAUTH_CLIENT_ID",
    "GOOGLE_ADS_OAUTH_CLIENT_SECRET",
    "GOOGLE_ADS_REFRESH_TOKEN",
    "GOOGLE_ADS_CUSTOMER_ID",
]
AHREFS_CREDENTIALS = ["AHREFS_API_KEY"]
GSC_CREDENTIALS = ["~/.hermes/secrets/gsc-oauth.json", "GSC_PROPERTY_URL"]


def _hermes_secret_path(filename: str) -> Path:
    return get_hermes_home() / "secrets" / filename


def _missing_env_vars(names: list[str]) -> list[str]:
    return [name for name in names if not str(get_env_value(name) or "").strip()]


def _missing_files(paths: list[Path]) -> list[str]:
    missing: list[str] = []
    hermes_home = get_hermes_home()
    for path in paths:
        if not path.exists() or not path.is_file():
            try:
                display = "~/.hermes/" + str(path.relative_to(hermes_home))
            except ValueError:
                display = str(path)
            missing.append(display)
    return missing


def _missing_bigquery_credentials() -> list[str]:
    return _missing_files([_hermes_secret_path("bq-service-account.json")])


def _missing_hubspot_credentials() -> list[str]:
    return _missing_env_vars(HUBSPOT_CREDENTIALS)


def _missing_google_ads_credentials() -> list[str]:
    return _missing_env_vars(GOOGLE_ADS_CREDENTIALS)


def _missing_ahrefs_credentials() -> list[str]:
    return _missing_env_vars(AHREFS_CREDENTIALS)


def _missing_gsc_credentials() -> list[str]:
    return _missing_files([_hermes_secret_path("gsc-oauth.json")]) + _missing_env_vars(["GSC_PROPERTY_URL"])


def check_bigquery_requirements() -> bool:
    """Return True when the BigQuery service account file is present."""
    return not _missing_bigquery_credentials()


def check_hubspot_requirements() -> bool:
    """Return True when the HubSpot access token is present."""
    return not _missing_hubspot_credentials()


def check_google_ads_requirements() -> bool:
    """Return True when all Google Ads OAuth/developer credentials are present."""
    return not _missing_google_ads_credentials()


def check_ahrefs_requirements() -> bool:
    """Return True when the Ahrefs API key is present."""
    return not _missing_ahrefs_credentials()


def check_gsc_requirements() -> bool:
    """Return True when GSC OAuth file and property URL are present."""
    return not _missing_gsc_credentials()


def _stub_response(expected_credentials: list[str], missing: list[str]) -> str:
    if missing:
        return json.dumps(
            {
                "error": f"not configured: missing {', '.join(missing)}",
                "expected_credentials": expected_credentials,
            }
        )
    return json.dumps(
        {
            "status": "stub",
            "message": STUB_MESSAGE,
            "expected_credentials": expected_credentials,
        }
    )


def _tool_bigquery_query(args: dict[str, Any], **_: Any) -> str:
    return _stub_response(BIGQUERY_CREDENTIALS, _missing_bigquery_credentials())


def _tool_hubspot_query(args: dict[str, Any], **_: Any) -> str:
    return _stub_response(HUBSPOT_CREDENTIALS, _missing_hubspot_credentials())


def _tool_google_ads_query(args: dict[str, Any], **_: Any) -> str:
    return _stub_response(GOOGLE_ADS_CREDENTIALS, _missing_google_ads_credentials())


def _tool_ahrefs_query(args: dict[str, Any], **_: Any) -> str:
    return _stub_response(AHREFS_CREDENTIALS, _missing_ahrefs_credentials())


def _tool_gsc_query(args: dict[str, Any], **_: Any) -> str:
    return _stub_response(GSC_CREDENTIALS, _missing_gsc_credentials())


BIGQUERY_SCHEMA = {
    "name": "tool_bigquery_query",
    "description": "Run a read-only BigQuery SQL query for Charity Charge Phase 1 analytics. Scaffold only until handler implementation lands.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "StandardSQL query to run. Handler should reject mutation statements when implemented.",
            },
            "parameters": {
                "type": "object",
                "description": "Optional named query parameters for parameterized StandardSQL.",
                "additionalProperties": True,
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum rows to return from the completed query.",
                "minimum": 1,
                "maximum": 1000,
                "default": 100,
            },
            "dry_run": {
                "type": "boolean",
                "description": "Validate and estimate the query without executing it.",
                "default": False,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

HUBSPOT_SCHEMA = {
    "name": "tool_hubspot_query",
    "description": "Query HubSpot CRM objects for Charity Charge Phase 1. Scaffold only until handler implementation lands.",
    "parameters": {
        "type": "object",
        "properties": {
            "object_type": {
                "type": "string",
                "description": "HubSpot CRM object type, such as contacts, companies, deals, tickets, or a custom object name.",
            },
            "properties": {
                "type": "array",
                "description": "CRM properties to include in the response.",
                "items": {"type": "string"},
                "default": [],
            },
            "filters": {
                "type": "array",
                "description": "HubSpot search filter groups or simplified filters for the eventual handler.",
                "items": {"type": "object", "additionalProperties": True},
                "default": [],
            },
            "limit": {
                "type": "integer",
                "description": "Maximum HubSpot records to return.",
                "minimum": 1,
                "maximum": 100,
                "default": 10,
            },
            "after": {
                "type": "string",
                "description": "Optional HubSpot paging cursor.",
            },
        },
        "required": ["object_type"],
        "additionalProperties": False,
    },
}

GOOGLE_ADS_SCHEMA = {
    "name": "tool_google_ads_query",
    "description": "Run a Google Ads GAQL query for Charity Charge Phase 1. Scaffold only until handler implementation lands.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Google Ads Query Language (GAQL) query.",
            },
            "customer_id": {
                "type": "string",
                "description": "Optional Google Ads customer ID override. Defaults to GOOGLE_ADS_CUSTOMER_ID.",
                "pattern": "^(\\d{10}|\\d{3}-\\d{3}-\\d{4})$",
            },
            "page_size": {
                "type": "integer",
                "description": "Requested page size for SearchGoogleAds when implemented.",
                "minimum": 1,
                "maximum": 10000,
                "default": 1000,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

AHREFS_SCHEMA = {
    "name": "tool_ahrefs_query",
    "description": "Query Ahrefs API v3 for Charity Charge Phase 1 SEO data. Scaffold only until handler implementation lands.",
    "parameters": {
        "type": "object",
        "properties": {
            "endpoint": {
                "type": "string",
                "description": "Ahrefs API v3 endpoint path, for example site-explorer/backlinks or subscription-info/limits-and-usage.",
            },
            "params": {
                "type": "object",
                "description": "Query string parameters for the Ahrefs endpoint.",
                "additionalProperties": {"type": ["string", "number", "integer", "boolean", "array"]},
                "default": {},
            },
        },
        "required": ["endpoint"],
        "additionalProperties": False,
    },
}

GSC_SCHEMA = {
    "name": "tool_gsc_query",
    "description": "Query Google Search Console search analytics for Charity Charge Phase 1. Scaffold only until handler implementation lands.",
    "parameters": {
        "type": "object",
        "properties": {
            "property_url": {
                "type": "string",
                "description": "Optional Search Console site URL override. Defaults to GSC_PROPERTY_URL.",
            },
            "start_date": {
                "type": "string",
                "description": "Start date in YYYY-MM-DD format.",
                "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
            },
            "end_date": {
                "type": "string",
                "description": "End date in YYYY-MM-DD format.",
                "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
            },
            "dimensions": {
                "type": "array",
                "description": "Search Analytics dimensions such as query, page, country, device, date, or searchAppearance.",
                "items": {
                    "type": "string",
                    "enum": ["query", "page", "country", "device", "date", "searchAppearance"],
                },
                "default": ["query"],
            },
            "row_limit": {
                "type": "integer",
                "description": "Maximum Search Console rows to return.",
                "minimum": 1,
                "maximum": 25000,
                "default": 1000,
            },
            "start_row": {
                "type": "integer",
                "description": "Zero-based result offset for pagination.",
                "minimum": 0,
                "default": 0,
            },
        },
        "required": ["start_date", "end_date"],
        "additionalProperties": False,
    },
}

registry.register(
    name="tool_bigquery_query",
    toolset=TOOLSET,
    schema=BIGQUERY_SCHEMA,
    handler=_tool_bigquery_query,
    check_fn=check_bigquery_requirements,
    requires_env=BIGQUERY_CREDENTIALS,
    description=BIGQUERY_SCHEMA["description"],
    emoji="📊",
)

registry.register(
    name="tool_hubspot_query",
    toolset=TOOLSET,
    schema=HUBSPOT_SCHEMA,
    handler=_tool_hubspot_query,
    check_fn=check_hubspot_requirements,
    requires_env=HUBSPOT_CREDENTIALS,
    description=HUBSPOT_SCHEMA["description"],
    emoji="🧲",
)

registry.register(
    name="tool_google_ads_query",
    toolset=TOOLSET,
    schema=GOOGLE_ADS_SCHEMA,
    handler=_tool_google_ads_query,
    check_fn=check_google_ads_requirements,
    requires_env=GOOGLE_ADS_CREDENTIALS,
    description=GOOGLE_ADS_SCHEMA["description"],
    emoji="📣",
)

registry.register(
    name="tool_ahrefs_query",
    toolset=TOOLSET,
    schema=AHREFS_SCHEMA,
    handler=_tool_ahrefs_query,
    check_fn=check_ahrefs_requirements,
    requires_env=AHREFS_CREDENTIALS,
    description=AHREFS_SCHEMA["description"],
    emoji="🔎",
)

registry.register(
    name="tool_gsc_query",
    toolset=TOOLSET,
    schema=GSC_SCHEMA,
    handler=_tool_gsc_query,
    check_fn=check_gsc_requirements,
    requires_env=GSC_CREDENTIALS,
    description=GSC_SCHEMA["description"],
    emoji="📈",
)
