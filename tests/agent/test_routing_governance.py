import json

from agent.routing_governance import (
    promote_route,
    read_rollout_state,
    rollback_route,
    validate_provider_routing_config,
    validate_smart_model_routing_config,
)


def test_validate_provider_routing_config_accepts_documented_shape():
    errors = validate_provider_routing_config(
        {
            "sort": "price",
            "only": ["Anthropic"],
            "ignore": ["Together"],
            "order": ["Anthropic", "Google"],
            "require_parameters": True,
            "data_collection": "deny",
        }
    )
    assert errors == []


def test_validate_provider_routing_config_rejects_invalid_values():
    errors = validate_provider_routing_config(
        {
            "sort": "cheapest",
            "only": "Anthropic",
            "data_collection": "maybe",
        }
    )
    assert any("sort" in err for err in errors)
    assert any("only" in err for err in errors)
    assert any("data_collection" in err for err in errors)


def test_validate_smart_model_routing_config_rejects_bad_rollout_settings():
    errors = validate_smart_model_routing_config(
        {
            "enabled": True,
            "require_qualified": True,
            "cheap_model": {"provider": "openrouter", "model": "google/gemini-2.5-flash"},
            "rollout": {"mode": "shipit", "max_percent": 150},
        }
    )
    assert any("rollout.mode" in err for err in errors)
    assert any("rollout.max_percent" in err for err in errors)


def test_promote_and_rollback_route_persist_rollout_state(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    promoted = promote_route(
        provider="openrouter",
        model="google/gemini-2.5-flash",
        reason="qualified in staging",
        rollout={"mode": "manual", "max_percent": 10},
    )
    assert promoted["current_route"]["model"] == "google/gemini-2.5-flash"
    assert promoted["qualified_routes"][0]["provider"] == "openrouter"

    rolled_back = rollback_route(reason="degraded quality")
    assert rolled_back["current_route"] is None
    assert rolled_back["previous_route"]["model"] == "google/gemini-2.5-flash"

    persisted = read_rollout_state()
    assert persisted["rollback"]["reason"] == "degraded quality"
    assert persisted["rollback"]["from_route"]["model"] == "google/gemini-2.5-flash"
    assert persisted["current_route"] is None


def test_promote_route_accumulates_unique_qualified_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    promote_route(provider="openrouter", model="google/gemini-2.5-flash", reason="first")
    promote_route(provider="openrouter", model="google/gemini-2.5-flash", reason="second")

    state = read_rollout_state()
    assert len(state["qualified_routes"]) == 1
    assert state["qualified_routes"][0]["qualification_reason"] == "second"
