import json

from gateway.config import Platform, GatewayConfig, PlatformConfig
from gateway.relationship_profiles import (
    build_relationship_context_prompt,
    canonical_identity_key,
    ensure_profile,
    final_openness,
    inner_state_multiplier,
    raw_openness,
    record_exchange,
)
from gateway.session import SessionSource, build_session_context, build_session_context_prompt


def test_canonical_identity_prefers_alt_user_id():
    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="chat-1",
        user_id="42",
        user_id_alt="stable-42",
    )

    assert canonical_identity_key(source) == "telegram:user:stable-42"


def test_profile_store_creates_profile_and_records_exchange(tmp_path):
    path = tmp_path / "profiles.json"
    source = SessionSource(platform=Platform.TELEGRAM, chat_id="1", user_id="u1", user_name="Alice")
    identity_key = canonical_identity_key(source)

    profile = ensure_profile(identity_key, source=source, path=path)
    record_exchange(identity_key, source=source, path=path)

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert profile["role"] == "stranger"
    assert stored["profiles"][identity_key]["total_exchanges"] == 1
    assert stored["profiles"][identity_key]["display_name"] == "Alice"


def test_openness_neutral_inner_state_multiplier():
    raw = raw_openness({"trust": 0.5, "safety": 0.5, "familiarity": 0.5, "consent": 0.5, "reciprocity": 0.5})

    assert raw == 0.5
    assert inner_state_multiplier({"stress": 0.5}) == 1.0
    assert inner_state_multiplier({"stress": 0.0}) == 0.75
    assert final_openness(raw, {"stress": 0.0}) == 0.375


def test_relationship_context_prompt_includes_boundaries_and_group_safety(tmp_path):
    path = tmp_path / "profiles.json"
    source = SessionSource(
        platform=Platform.DISCORD,
        chat_id="group-1",
        chat_type="group",
        user_id="alice",
        user_name="Alice",
    )
    ctx = build_session_context(
        source,
        GatewayConfig(platforms={Platform.DISCORD: PlatformConfig(enabled=True, token="fake")}),
    )
    identity_key = canonical_identity_key(source)
    ensure_profile(identity_key, source=source, path=path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["profiles"][identity_key]["boundaries"] = ["Do not discuss topic X"]
    path.write_text(json.dumps(data), encoding="utf-8")

    prompt = build_relationship_context_prompt(ctx, path=path)

    assert identity_key in prompt
    assert "Do not discuss topic X" in prompt
    assert "Group safety" in prompt


def test_session_context_prompt_injects_relationship_context(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_PERSONA_DIR", str(tmp_path))
    source = SessionSource(platform=Platform.TELEGRAM, chat_id="1", chat_type="dm", user_id="u1")
    ctx = build_session_context(
        source,
        GatewayConfig(platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="fake")}),
    )

    prompt = build_session_context_prompt(ctx)

    assert "Judy Relationship Context" in prompt
    assert "telegram:user:u1" in prompt
    assert "private memories are scoped per interlocutor" in prompt
