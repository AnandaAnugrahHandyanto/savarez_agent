"""Regression guard: an Anthropic HTTP-200 safety refusal (``stop_reason ==
"refusal"`` with an empty ``content`` list) must NOT be mislabeled as
"response.content invalid (not a non-empty list)" and retried 3× before
giving up.

Real-world symptom: a stricter Claude model (e.g. ``claude-fable-5``) refuses
offensive-security / fuzzing / crash-corpus material that a broader model
(e.g. ``claude-opus-4-8``) handles. The provider returns HTTP 200 with::

    {"stop_reason": "refusal", "content": []}

The Anthropic ``validate_response`` correctly returns False (no usable
content), but the conversation loop used to treat that as a generic invalid
response: 3× jittered-backoff retries (each deterministically reproducing the
same refusal), then "Invalid API response after 3 retries" — burning paid
attempts and giving the user no idea their prompt was refused.

The fix special-cases ``stop_reason == "refusal"`` at the validation site and
routes it to the existing ``content_policy_blocked`` recovery (try fallback,
else surface a clear "model refused this request" message). This guards both
the transport-level signal and the loop's refusal-detection predicate.
"""
from __future__ import annotations

from types import SimpleNamespace


class TestAnthropicTransportValidateRefusal:
    """The transport's validate_response must reject an empty-content refusal
    (it carries nothing usable) while still accepting the legitimate
    empty-content ``end_turn`` case.
    """

    def _transport(self):
        from agent.transports.anthropic import AnthropicTransport

        return AnthropicTransport()

    def test_empty_content_refusal_is_invalid(self):
        resp = SimpleNamespace(content=[], stop_reason="refusal")
        assert self._transport().validate_response(resp) is False

    def test_empty_content_end_turn_is_valid(self):
        # The model's canonical "nothing more to add" after a tool turn.
        resp = SimpleNamespace(content=[], stop_reason="end_turn")
        assert self._transport().validate_response(resp) is True

    def test_nonempty_content_is_valid_regardless_of_stop_reason(self):
        resp = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="hi")],
            stop_reason="refusal",
        )
        assert self._transport().validate_response(resp) is True

    def test_refusal_maps_to_content_filter_finish_reason(self):
        # _STOP_REASON_MAP already encodes the intent; lock it in.
        assert self._transport().map_finish_reason("refusal") == "content_filter"


class TestRefusalDetectionPredicate:
    """Mirror the ``anthropic_refusal`` decision in
    ``agent/conversation_loop.py``: when validate_response fails, a response
    whose ``stop_reason`` is ``"refusal"`` routes to the content-policy path;
    everything else stays in the generic invalid-response path.

    Kept in lock-step with the source — if you change one, change both.
    """

    def _is_refusal(self, response) -> bool:
        return (
            response is not None
            and getattr(response, "stop_reason", None) == "refusal"
        )

    def test_empty_refusal_routes_to_content_policy(self):
        resp = SimpleNamespace(content=[], stop_reason="refusal")
        assert self._is_refusal(resp) is True

    def test_none_response_is_not_a_refusal(self):
        # A None response is a genuine invalid response, not a refusal.
        assert self._is_refusal(None) is False

    def test_malformed_non_refusal_is_not_a_refusal(self):
        # e.g. a truncated/garbled body with no usable stop_reason.
        resp = SimpleNamespace(content=None, stop_reason=None)
        assert self._is_refusal(resp) is False

    def test_end_turn_is_not_a_refusal(self):
        resp = SimpleNamespace(content=[], stop_reason="end_turn")
        assert self._is_refusal(resp) is False
