"""The standalone core must derive opaque refs, never echo raw ids."""

from contextops_ese import safe_ref


def test_safe_ref_is_opaque_and_does_not_contain_raw_id():
    raw = "hermes-session-9f3c-message-00042"
    token = safe_ref(raw)
    assert raw not in token
    assert token.startswith("ref:")
    assert len(token) <= 24


def test_safe_ref_is_deterministic():
    assert safe_ref("abc") == safe_ref("abc")
    assert safe_ref("abc") != safe_ref("abd")


def test_safe_ref_rejects_empty_id():
    import pytest

    with pytest.raises(ValueError):
        safe_ref("   ")
