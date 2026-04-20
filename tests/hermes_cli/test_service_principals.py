from __future__ import annotations

import json

from hermes_cli.service_principals import (
    allowed_services_for_principal,
    is_service_allowed,
    load_service_principals_policy,
    resolve_canonical_principal,
)


def test_load_service_principals_policy_defaults_when_missing(tmp_path):
    policy = load_service_principals_policy(tmp_path / "missing.json")

    assert policy == {"version": 1, "default_deny": True, "principals": {}}


def test_resolve_canonical_principal_matches_aliases():
    policy = {
        "principals": {
            "rj@stratminds.vc": {
                "aliases": ["telegram:1643294159", "1643294159", "rj@stratminds.vc"],
                "services": {},
            }
        }
    }

    assert resolve_canonical_principal("telegram:1643294159", policy=policy) == "rj@stratminds.vc"
    assert resolve_canonical_principal("1643294159", policy=policy) == "rj@stratminds.vc"


def test_allowed_services_for_principal_filters_to_allowed_entries():
    policy = {
        "principals": {
            "rj@stratminds.vc": {
                "aliases": ["telegram:1643294159"],
                "services": {
                    "zoom": {"allow": True, "account": "rj@stratminds.vc"},
                    "grain": {"allow": True, "account": "rj@stratminds.vc"},
                    "granola": {"allow": False, "account": "rj@stratminds.vc"},
                },
            }
        }
    }

    allowed = allowed_services_for_principal("telegram:1643294159", policy=policy)

    assert set(allowed) == {"zoom", "grain"}


def test_is_service_allowed_requires_mapped_principal():
    policy = {
        "principals": {
            "rj@stratminds.vc": {
                "aliases": ["telegram:1643294159"],
                "services": {"zoom": {"allow": True}},
            }
        }
    }

    assert is_service_allowed("zoom", "telegram:1643294159", policy=policy) is True
    assert is_service_allowed("zoom", "telegram:999", policy=policy) is False
    assert is_service_allowed("grain", "telegram:1643294159", policy=policy) is False


def test_load_service_principals_policy_reads_json(tmp_path):
    path = tmp_path / "service_principals.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "default_deny": True,
                "principals": {
                    "rj@stratminds.vc": {
                        "aliases": ["telegram:1643294159"],
                        "services": {"zoom": {"allow": True}},
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    policy = load_service_principals_policy(path)

    assert policy["principals"]["rj@stratminds.vc"]["services"]["zoom"]["allow"] is True

