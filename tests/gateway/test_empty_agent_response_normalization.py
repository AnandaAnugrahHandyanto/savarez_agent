from gateway.run import _normalize_empty_agent_response


def test_partial_empty_response_becomes_actionable_message():
    result = {
        "api_calls": 3,
        "partial": True,
        "error": "Codex response remained incomplete after 3 continuation attempts",
    }

    message = _normalize_empty_agent_response(result, "")

    assert message == (
        "⚠️ Processing stopped: Codex response remained incomplete after 3 "
        "continuation attempts. Try again."
    )


def test_partial_synthetic_raw_error_is_not_sent_directly():
    result = {
        "api_calls": 3,
        "partial": True,
        "error": "Codex response remained incomplete after 3 continuation attempts",
    }

    message = _normalize_empty_agent_response(
        result,
        "⚠️ Codex response remained incomplete after 3 continuation attempts",
    )

    assert message == (
        "⚠️ Processing stopped: Codex response remained incomplete after 3 "
        "continuation attempts. Try again."
    )


def test_failed_synthetic_raw_error_is_normalized():
    result = {
        "api_calls": 1,
        "failed": True,
        "error": "provider exploded",
    }

    message = _normalize_empty_agent_response(result, "⚠️ provider exploded")

    assert message == (
        "The request failed: provider exploded\n"
        "Try again or use /reset to start a fresh session."
    )


def test_real_nonempty_response_is_preserved():
    result = {
        "api_calls": 1,
        "partial": True,
        "error": "provider exploded",
    }

    assert _normalize_empty_agent_response(result, "I recovered and finished.") == "I recovered and finished."
