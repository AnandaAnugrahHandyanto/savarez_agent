"""Discord mention linter — catch malformed `<@…>` literals at write time.

Background
----------
The Discord gateway delivers cross-agent and inter-bot messages via
`<@SNOWFLAKE>` mentions, where SNOWFLAKE is a 17-20 digit integer assigned
by Discord. When a snowflake is malformed (asterisks, placeholders, role
syntax with `&`, non-digit characters, wrong length), the recipient bot
silently does not see the mention, and the message goes nowhere.

Production-incident history (see writer_ai#125):

* 2026-05-26: `agent/redact.py:_DISCORD_MENTION_RE` rewrote every
  `<@123456789012345678>` to `<@***>` at the persistence boundary,
  baking display-masked IDs into history, scrollback, and downstream
  artifacts (cron prompts, skill SOUL.md files, cached docs).
* Bots that then "copied a mention from scrollback" emitted `<@***>` or
  hallucinated role mentions like `<@&1508199352898814126>` — neither
  of which Discord delivers.
* The redact regex has been disabled in code, but the live-fire bug
  pattern (`<@*>`, `<@***>`, `<@&...>` for agent IDs) is still being
  copied around the fleet by humans and agents reading old context.

This module is the write-time guardrail:

* `find_malformed_mentions(text)` — pure function, no I/O, returns a list
  of `MentionFinding` records describing every malformed mention.
* `format_findings(findings)` — human-readable error string for surfacing
  via `tool_error()` in cron / skill / send-message guards.
* `has_malformed_mentions(text)` — boolean convenience wrapper.

Enforcement policy (by integration site):

* **Durable artifacts** (cron `create`/`update`, `skill_manage`
  `create`/`patch`/`edit`/`write_file`) → **HARD REJECT**. These outlive
  the session and contaminate future runs if they ship malformed.
* **Live outbound** (Discord adapter `send()` → `format_message()`) →
  **WARN-AND-PASS** with structured log. We never silently rewrite the
  payload again — that's how we got here.

Author: Rocket (rocket profile), Sprint 1 deliverable for #125.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

# Discord snowflakes are 17-20 digit integers. 17 was the lower bound at
# the API's inception; 20 is the practical ceiling under Twitter Snowflake
# math through 2154 AD. Anything outside that window is not a real
# Discord ID — almost always a placeholder, hallucinated digit count, or
# truncated copy-paste.
_SNOWFLAKE_MIN_LEN = 17
_SNOWFLAKE_MAX_LEN = 20

# Match every `<@…>` token we want to inspect. We deliberately do NOT
# anchor on `\d`, because a strict snowflake regex would silently skip
# the very malformed cases we exist to catch. The pattern body captures
# everything up to the first `>` (no nested `>` is legal inside a
# Discord mention), and the classifier picks it apart.
#
# Body alphabet: `\w` + `&` + `!` + `*` + a few stray ASCII punctuation
# we've observed in real failed sends (`#`, `-`, `_`, `:`). We do NOT
# include `<` or `>` so we can't run away across malformed tags.
_MENTION_TOKEN_RE = re.compile(r"<@([&!]?[\w*#:\-]*)>")

# Strict "looks legitimate" form: `<@SNOWFLAKE>` or `<@!SNOWFLAKE>`
# (the `!` prefix is the legacy "force-nickname" mention form, still
# emitted by some clients and accepted by Discord).
_VALID_USER_MENTION_RE = re.compile(
    rf"^!?\d{{{_SNOWFLAKE_MIN_LEN},{_SNOWFLAKE_MAX_LEN}}}$"
)

# Strict role mention: `<@&SNOWFLAKE>`. We tolerate these in some
# contexts (genuine Discord roles), but agent-routing code paths should
# not be emitting them — agents are users, not roles. The caller
# decides whether to accept these via the `allow_roles` flag.
_VALID_ROLE_MENTION_RE = re.compile(
    rf"^&\d{{{_SNOWFLAKE_MIN_LEN},{_SNOWFLAKE_MAX_LEN}}}$"
)

# Channel mention `<#1234567890>` is a different syntax entirely
# (note the leading `#`, not `@`), so it never enters this scanner.


class MentionKind:
    """Enum-style classifier for the kind of malformation we found."""

    ASTERISK_PLACEHOLDER = "asterisk_placeholder"  # <@***>, <@*>
    ROLE_MENTION = "role_mention"                  # <@&1234…>
    NON_NUMERIC = "non_numeric"                    # <@bot_id>, <@TONY>
    WRONG_LENGTH = "wrong_length"                  # <@123>, <@1234567890123456789012345>
    EMPTY = "empty"                                # <@>


@dataclass(frozen=True)
class MentionFinding:
    """One malformed-mention occurrence in a piece of text."""

    raw: str          # the literal token as it appeared, e.g. "<@***>"
    kind: str         # one of MentionKind.*
    start: int        # 0-indexed character offset in the scanned text
    end: int          # exclusive end offset
    hint: str         # short human-readable remediation pointer


def _classify(body: str) -> Optional[str]:
    """Return a MentionKind for malformed body, or None if body is valid.

    `body` is the captured group from `_MENTION_TOKEN_RE` — everything
    between `<@` and `>`. For `<@!?SNOWFLAKE>` we return None.
    """
    if not body:
        return MentionKind.EMPTY
    if "*" in body:
        return MentionKind.ASTERISK_PLACEHOLDER
    if _VALID_USER_MENTION_RE.match(body):
        return None
    if _VALID_ROLE_MENTION_RE.match(body):
        # Role mention. Caller decides whether to allow.
        return MentionKind.ROLE_MENTION
    # Strip a leading `!` (legacy nickname-mention form) before deciding
    # between non-numeric and wrong-length, so `<@!abc>` is correctly
    # classified as non-numeric rather than wrong-length.
    candidate = body[1:] if body.startswith("!") else body
    if not candidate.isdigit():
        return MentionKind.NON_NUMERIC
    return MentionKind.WRONG_LENGTH


def _hint_for(kind: str) -> str:
    if kind == MentionKind.ASTERISK_PLACEHOLDER:
        return (
            "Asterisk placeholder — this is the redacted display form, "
            "NOT a real Discord ID. Look up the numeric ID from your "
            "SOUL 'Bot Mention IDs' table and replace."
        )
    if kind == MentionKind.ROLE_MENTION:
        return (
            "Role mention (`<@&…>`) — agents are users, not roles. "
            "Use `<@SNOWFLAKE>` (no `&`)."
        )
    if kind == MentionKind.NON_NUMERIC:
        return (
            "Mention body contains non-digit characters. Discord IDs "
            "are 17-20 digit integers only. Replace placeholder text "
            "with the real numeric ID."
        )
    if kind == MentionKind.WRONG_LENGTH:
        return (
            f"Mention body is the wrong length. Discord snowflakes are "
            f"{_SNOWFLAKE_MIN_LEN}-{_SNOWFLAKE_MAX_LEN} digits. "
            "Re-copy the ID from your SOUL table."
        )
    if kind == MentionKind.EMPTY:
        return "Empty mention `<@>` — body is missing."
    return "Malformed Discord mention."


def find_malformed_mentions(
    text: str,
    *,
    allow_roles: bool = False,
) -> List[MentionFinding]:
    """Scan ``text`` and return a list of malformed-mention findings.

    Args:
        text: The text to scan. ``None`` or non-string returns ``[]``.
        allow_roles: When True, `<@&SNOWFLAKE>` role mentions are
            accepted (used when scanning content destined for a real
            Discord channel where roles are legitimate). Defaults to
            False — durable artifacts (cron prompts, skills) should
            not contain role mentions because they're never the right
            answer for agent routing.

    Returns:
        List of MentionFinding, one per malformed token, in left-to-right
        order. Empty list = clean.
    """
    if not isinstance(text, str) or not text:
        return []
    # Cheap pre-check: most strings have no `<@` at all.
    if "<@" not in text:
        return []
    findings: List[MentionFinding] = []
    for match in _MENTION_TOKEN_RE.finditer(text):
        body = match.group(1)
        kind = _classify(body)
        if kind is None:
            continue
        if kind == MentionKind.ROLE_MENTION and allow_roles:
            continue
        findings.append(
            MentionFinding(
                raw=match.group(0),
                kind=kind,
                start=match.start(),
                end=match.end(),
                hint=_hint_for(kind),
            )
        )
    return findings


def has_malformed_mentions(text: str, *, allow_roles: bool = False) -> bool:
    """Boolean convenience wrapper around `find_malformed_mentions`."""
    return bool(find_malformed_mentions(text, allow_roles=allow_roles))


def format_findings(
    findings: List[MentionFinding],
    *,
    source_label: str = "content",
    max_show: int = 5,
) -> str:
    """Format findings for surfacing in a tool-error response.

    Returns a multi-line string suitable for `tool_error()` payloads or
    structured logging. Truncates to ``max_show`` to avoid runaway
    payload sizes when a file is severely contaminated.
    """
    if not findings:
        return ""
    n = len(findings)
    head = (
        f"Malformed Discord mention(s) found in {source_label}: "
        f"{n} occurrence{'s' if n != 1 else ''}."
    )
    shown = findings[:max_show]
    lines = [
        f"  • `{f.raw}` at offset {f.start} → {f.kind}: {f.hint}"
        for f in shown
    ]
    body = "\n".join(lines)
    tail = ""
    if n > max_show:
        tail = f"\n  … and {n - max_show} more."
    return (
        f"{head}\n{body}{tail}\n\n"
        "Discord snowflakes are 17-20 digit integers (no asterisks, no "
        "role `&` prefix, no placeholder text). Look up the real ID "
        "from your SOUL 'Bot Mention IDs' table and substitute it in."
    )


__all__ = [
    "MentionFinding",
    "MentionKind",
    "find_malformed_mentions",
    "has_malformed_mentions",
    "format_findings",
]
