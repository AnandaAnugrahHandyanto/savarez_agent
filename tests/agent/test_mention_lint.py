"""Tests for agent.mention_lint — Discord mention-malformation guardrail.

Each test pins one production-incident shape from writer_ai#125. When
you add a new malformation kind, add it both here and as a new
MentionKind entry — that way the failure mode is documented in tests.
"""

from __future__ import annotations

import pytest

from agent.mention_lint import (
    MentionFinding,
    MentionKind,
    find_malformed_mentions,
    format_findings,
    has_malformed_mentions,
)


# ─────────────────────────────────────────────────────────────────────
# 1. Valid mentions — must NOT trigger findings
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "text",
    [
        # The real bot IDs from the live SOUL "Bot Mention IDs" table.
        "<@1508163422481678526>",                # Tony
        "<@1508196967287886045> JARVIS — ping",  # JARVIS, with trailing prose
        "<@1508199506150166658>",                # Fury
        "<@1508267393380519936>",                # Rocket (self)
        # Legacy nickname-mention form (still legal on the wire).
        "<@!1508163422481678526>",
        # Embedded inside a longer sentence.
        "Hey <@1508282388399001742> Thor — what's the deal with #standups?",
        # Channel mentions (`<#…>`) use a different syntax and must be ignored.
        "Posted to <#1508197668382576950> for visibility.",
        # No mention at all.
        "Just plain prose, nothing to see here.",
        "",
        None,
    ],
)
def test_valid_mentions_pass(text):
    assert find_malformed_mentions(text) == []
    assert has_malformed_mentions(text) is False


# ─────────────────────────────────────────────────────────────────────
# 2. Asterisk placeholders — THE original incident shape
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "text,raw",
    [
        ("<@***>", "<@***>"),                # canonical Banner shape
        ("<@*> Hawkeye", "<@*>"),            # single-asterisk variant
        ("<@****>", "<@****>"),              # four-asterisk variant
        ("hello <@***> Fury — see attached", "<@***>"),  # embedded
    ],
)
def test_asterisk_placeholder_is_flagged(text, raw):
    findings = find_malformed_mentions(text)
    assert len(findings) == 1
    assert findings[0].kind == MentionKind.ASTERISK_PLACEHOLDER
    assert findings[0].raw == raw
    assert "redacted display form" in findings[0].hint or "Asterisk" in findings[0].hint


# ─────────────────────────────────────────────────────────────────────
# 3. Role mentions — hallucinated `<@&…>` for agent IDs
# ─────────────────────────────────────────────────────────────────────

def test_role_mention_is_flagged_by_default():
    # Real failure from 2026-05-26: bot kept emitting role-syntax IDs
    # for agent routing, which Discord silently drops.
    text = "<@&1508199352898814126> Tony — question."
    findings = find_malformed_mentions(text)
    assert len(findings) == 1
    assert findings[0].kind == MentionKind.ROLE_MENTION
    assert findings[0].raw == "<@&1508199352898814126>"


def test_role_mention_can_be_allowed_for_channels_with_real_roles():
    # When scanning content destined for a Discord channel where roles
    # are legitimate (e.g. a server admin posting `<@&moderators>`),
    # allow_roles=True suppresses the finding.
    text = "<@&1508199352898814126> heads up"
    assert find_malformed_mentions(text, allow_roles=True) == []
    assert has_malformed_mentions(text, allow_roles=True) is False


# ─────────────────────────────────────────────────────────────────────
# 4. Non-numeric mention bodies — placeholder text where digits belong
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "text,raw",
    [
        ("<@bot_id> Fury", "<@bot_id>"),
        ("<@TONY>", "<@TONY>"),
        ("<@your_id_here> please replace", "<@your_id_here>"),
        ("<@!abc> legacy-form non-numeric", "<@!abc>"),
    ],
)
def test_non_numeric_body_is_flagged(text, raw):
    findings = find_malformed_mentions(text)
    assert len(findings) == 1
    assert findings[0].kind == MentionKind.NON_NUMERIC
    assert findings[0].raw == raw


# ─────────────────────────────────────────────────────────────────────
# 5. Wrong-length snowflakes — typos, truncation, hallucinated digits
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "text,raw",
    [
        ("<@123>", "<@123>"),                      # way too short
        ("<@1234567890123456>", "<@1234567890123456>"),  # 16 — off-by-one
        # 21 digits — one over the upper bound.
        ("<@123456789012345678901>", "<@123456789012345678901>"),
        ("<@!12345>", "<@!12345>"),                # legacy form, too short
    ],
)
def test_wrong_length_snowflake_is_flagged(text, raw):
    findings = find_malformed_mentions(text)
    assert len(findings) == 1, f"got {findings!r}"
    assert findings[0].kind == MentionKind.WRONG_LENGTH
    assert findings[0].raw == raw


# ─────────────────────────────────────────────────────────────────────
# 6. Empty body — `<@>`
# ─────────────────────────────────────────────────────────────────────

def test_empty_body_is_flagged():
    findings = find_malformed_mentions("here is <@> nothing")
    assert len(findings) == 1
    assert findings[0].kind == MentionKind.EMPTY
    assert findings[0].raw == "<@>"


# ─────────────────────────────────────────────────────────────────────
# 7. Mixed valid + invalid in the same text
# ─────────────────────────────────────────────────────────────────────

def test_mixed_valid_and_invalid_returns_only_invalid_findings():
    text = (
        "<@1508163422481678526> Tony — looped in <@***> Fury, "
        "cc <@&1508199352898814126>, ping <@bot_id> too."
    )
    findings = find_malformed_mentions(text)
    assert len(findings) == 3
    kinds = [f.kind for f in findings]
    assert kinds == [
        MentionKind.ASTERISK_PLACEHOLDER,
        MentionKind.ROLE_MENTION,
        MentionKind.NON_NUMERIC,
    ]
    # Offsets are returned in source order.
    assert findings[0].start < findings[1].start < findings[2].start


# ─────────────────────────────────────────────────────────────────────
# 8. format_findings() — error-payload shape
# ─────────────────────────────────────────────────────────────────────

def test_format_findings_empty_returns_empty_string():
    assert format_findings([]) == ""


def test_format_findings_includes_count_and_remediation():
    findings = find_malformed_mentions("<@***> and <@bot_id>")
    msg = format_findings(findings, source_label="cron prompt")
    assert "cron prompt" in msg
    assert "2 occurrences" in msg
    assert "<@***>" in msg
    assert "<@bot_id>" in msg
    # The remediation pointer should mention the SOUL table.
    assert "SOUL" in msg


def test_format_findings_truncates_long_lists():
    text = " ".join(["<@***>"] * 20)
    findings = find_malformed_mentions(text)
    assert len(findings) == 20
    msg = format_findings(findings, max_show=3)
    assert "20 occurrences" in msg
    assert "and 17 more" in msg


# ─────────────────────────────────────────────────────────────────────
# 9. Defensive: non-string inputs do not raise
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", [None, 42, 3.14, [], {}, object()])
def test_non_string_input_returns_empty(bad):
    assert find_malformed_mentions(bad) == []
    assert has_malformed_mentions(bad) is False
