from gateway.context_handoff import resolve_context_handoff_policy, should_handoff_context


def test_context_handoff_uses_safe_absolute_cap_before_context_ratio():
    policy = resolve_context_handoff_policy(
        {"compression": {"handoff_threshold": 0.75, "handoff_max_prompt_tokens": 60000}},
        context_length=200_000,
    )

    assert policy.enabled is True
    assert policy.token_threshold == 60_000
    assert should_handoff_context(tokens=59_999, message_count=10, policy=policy) is False
    assert should_handoff_context(tokens=60_000, message_count=10, policy=policy) is True


def test_context_handoff_can_be_disabled():
    policy = resolve_context_handoff_policy(
        {"compression": {"handoff_enabled": False, "handoff_max_prompt_tokens": 60000}},
        context_length=200_000,
    )

    assert policy.enabled is False
    assert should_handoff_context(tokens=90_000, message_count=500, policy=policy) is False


def test_context_handoff_keeps_existing_hard_message_limit():
    policy = resolve_context_handoff_policy(
        {"compression": {"hygiene_hard_message_limit": 400}},
        context_length=200_000,
    )

    assert should_handoff_context(tokens=1_000, message_count=399, policy=policy) is False
    assert should_handoff_context(tokens=1_000, message_count=400, policy=policy) is True
