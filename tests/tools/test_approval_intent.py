"""Unit tests for the natural-language approval-intent classifier."""

from __future__ import annotations

import pytest

from tools.approval_intent import classify, is_approve_phrase, is_deny_phrase


class TestRequiredApprovePhrases:
    """All phrases listed in the spec MUST classify as approve."""

    @pytest.mark.parametrize("text", [
        "yes",
        "approved",
        "i approve",
        "approve",
        "execute",
        "execute this",
        "execute it",
        "do it",
        "do this",
        "run it",
        "run this",
        "run it now",
        "confirmed",
        "proceed",
    ])
    def test_spec_required_phrase_is_approve(self, text: str) -> None:
        assert classify(text) == "approve"
        assert is_approve_phrase(text) is True
        assert is_deny_phrase(text) is False


class TestNormalization:
    """Normalisation must accept casual capitalisation, punctuation, and fillers."""

    @pytest.mark.parametrize("text", [
        "Yes",
        "YES",
        "yes.",
        "yes!",
        "yes,",
        "  yes  ",
        "please approve",
        "just approve",
        "Approve.",
        "I APPROVE",
        "i  approve",
    ])
    def test_variant_still_approves(self, text: str) -> None:
        assert classify(text) == "approve", f"failed on {text!r}"


class TestDenyPhrases:
    @pytest.mark.parametrize("text", [
        "deny",
        "denied",
        "cancel",
        "reject",
        "rejected",
        "nevermind",
        "never mind",
    ])
    def test_deny_classification(self, text: str) -> None:
        assert classify(text) == "deny"
        assert is_deny_phrase(text) is True
        assert is_approve_phrase(text) is False


class TestCasualVerbsAreNotIntercepted:
    """Casual single-word replies like "ok", "go", "k", "y", "no", "stop"
    must NOT classify as approve or deny — they appear too often in
    normal chat while an approval is pending, and a misfire can execute
    a sensitive workflow.  This class is the
    regression line for that intentional narrowness (added after ultraqa
    flagged the original wider set as a false-positive risk).
    """

    @pytest.mark.parametrize("text", [
        "ok",
        "okay",
        "k",
        "y",
        "yep",
        "yeah",
        "go",
        "go ahead",
        "confirm",
        "no",
        "n",
        "nope",
        "abort",
        "stop",
    ])
    def test_casual_verb_returns_none(self, text: str) -> None:
        assert classify(text) is None, (
            f"{text!r} must NOT classify — it's too conversational"
        )


class TestSlashCommandsAreNotIntercepted:
    """Slash-prefixed input must fall through to normal dispatch."""

    @pytest.mark.parametrize("text", [
        "/approve",
        "/approve all",
        "/deny",
        "/yes",
        "  /approve  ",
    ])
    def test_slash_returns_none(self, text: str) -> None:
        assert classify(text) is None


class TestConversationalNoise:
    """Conversational text that *contains* an approval keyword as a
    substring must NOT classify — exact-phrase matching is the contract.
    """

    @pytest.mark.parametrize("text", [
        "yes please continue with the analysis",
        "I think yes is the right answer here",
        "approve the budget for next quarter",
        "should I approve this PR?",
        "do it tomorrow",
        "execute order 66",
        "no problem at all",
        "I don't want to do it like that",
        "",
        "   ",
        None,
    ])
    def test_substring_does_not_match(self, text) -> None:
        assert classify(text) is None


class TestStability:
    """The classifier must be deterministic and side-effect-free."""

    def test_idempotent(self) -> None:
        assert classify("yes") == classify("yes") == "approve"

    def test_no_state_leak_between_calls(self) -> None:
        assert classify("yes") == "approve"
        assert classify("random unrelated text") is None
        assert classify("yes") == "approve"

    def test_empty_string(self) -> None:
        assert classify("") is None

    def test_whitespace_only(self) -> None:
        assert classify("   \n\t  ") is None
