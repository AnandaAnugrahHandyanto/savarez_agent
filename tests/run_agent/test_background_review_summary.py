"""Tests for AIAgent._summarize_background_review_actions.

Regression coverage for issue #14944: the background memory/skill review used
to re-surface tool results that were already present in the conversation
history before the review started (e.g. an earlier "Cron job '...' created.").

Regression coverage for issue #46897: the background review used to surface
"Skill '<name>' created" notifications based solely on the skill-write
tool's ``success: true`` flag, without verifying the skill is actually
loadable from the live session's skill search roots. When the spawned
review agent resolved a different ``HERMES_HOME``/profile root than the
live session, the user was told a skill was created that the live session
could never load.
"""

import json
from unittest.mock import patch

from run_agent import AIAgent


_summarize = AIAgent._summarize_background_review_actions


def _tool_msg(tool_call_id, payload):
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(payload),
    }


def test_skips_prior_tool_messages_by_tool_call_id():
    """Stale 'created' tool result from prior history must not be re-surfaced."""
    prior_payload = {"success": True, "message": "Cron job 'remind-me' created."}
    new_payload = {
        "success": True,
        "message": "Entry added",
        "target": "user",
    }

    snapshot = [
        {"role": "user", "content": "create a reminder"},
        _tool_msg("call_old", prior_payload),
        {"role": "assistant", "content": "done"},
    ]
    review_messages = list(snapshot) + [
        {"role": "user", "content": "<review prompt>"},
        _tool_msg("call_new", new_payload),
    ]

    actions = _summarize(review_messages, snapshot)

    assert "Cron job 'remind-me' created." not in actions
    assert "User profile updated" in actions


def test_includes_genuinely_new_actions():
    new_payload = {
        "success": True,
        "message": "Memory entry created.",
    }
    review_messages = [_tool_msg("call_new", new_payload)]

    actions = _summarize(review_messages, prior_snapshot=[])

    assert actions == ["Memory entry created."]


def test_falls_back_to_content_equality_when_tool_call_id_missing():
    """If a tool message has no tool_call_id, match prior entries by content."""
    payload = {"success": True, "message": "Cron job 'X' created."}
    raw = json.dumps(payload)
    prior_msg = {"role": "tool", "content": raw}  # no tool_call_id
    review_messages = [
        {"role": "tool", "content": raw},  # same content -> stale, skip
        _tool_msg("call_new", {"success": True, "message": "Skill created."}),
    ]

    actions = _summarize(review_messages, [prior_msg])

    assert "Cron job 'X' created." not in actions
    assert "Skill created." in actions


def test_ignores_failed_tool_results():
    bad = {"success": False, "message": "something created but failed"}
    review_messages = [_tool_msg("call_new", bad)]

    actions = _summarize(review_messages, [])

    assert actions == []


def test_handles_non_json_tool_content_gracefully():
    review_messages = [
        {"role": "tool", "tool_call_id": "x", "content": "not-json"},
        _tool_msg("call_y", {"success": True, "message": "Memory updated."}),
    ]

    actions = _summarize(review_messages, [])

    assert actions == ["Memory updated."]


def test_empty_inputs():
    assert _summarize([], []) == []
    assert _summarize(None, None) == []


def test_added_message_relabels_by_target():
    review_messages = [
        _tool_msg(
            "c1",
            {"success": True, "message": "Entry added to store.", "target": "memory"},
        )
    ]

    actions = _summarize(review_messages, [])

    assert actions == ["Memory updated"]


def test_removed_or_replaced_relabels_by_target():
    review_messages = [
        _tool_msg(
            "c1",
            {"success": True, "message": "Entry removed.", "target": "user"},
        ),
        _tool_msg(
            "c2",
            {"success": True, "message": "Entry replaced.", "target": "memory"},
        ),
    ]

    actions = _summarize(review_messages, [])

    assert "User profile updated" in actions
    assert "Memory updated" in actions


# ---------------------------------------------------------------------------
# Issue #46897 — skill loadability check
# ---------------------------------------------------------------------------
#
# Each test below targets one of the layers documented in
# .automation-worktrees/.../fix__46897-bg-review-skill-loadable/LAYERS.md
# (L1 = probe, L2 = regex, L3 = helper, L4 = warning + drop) plus the
# edge cases (E1–E5). The tests must FAIL on the pre-fix code (the
# notification leaks) and PASS on the post-fix code (the notification is
# suppressed when the skill is not in the live session's SKILLS_DIR /
# external_dirs).

def _setup_skill_in_session_root(tmp_path, skill_name):
    """Create a real SKILL.md under tmp_path/<skill_name>/ so the loadability
    live ``skill_view`` resolver can find it. Returns the patched
    context-manager pair: (skills_dir, external_dirs) for use in
    ``with`` stacks.
    """
    skill_dir = tmp_path / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_name}\ndescription: test skill\n---\n# body\n",
        encoding="utf-8",
    )
    return tmp_path


def test_l1_skill_created_surfaces_when_skill_is_in_session_root(tmp_path):
    """L1: when the written skill is loadable through the live session's
    ``skill_view`` search path, the action is kept."""
    root = _setup_skill_in_session_root(tmp_path, "alpha-skill")
    with patch("tools.skills_tool.SKILLS_DIR", root), \
         patch("agent.skill_utils.get_external_skills_dirs", return_value=[]):
        actions = _summarize(
            [
                _tool_msg(
                    "c1",
                    {
                        "success": True,
                        "message": "Skill 'alpha-skill' created.",
                        "path": str(root / "alpha-skill"),
                    },
                )
            ],
            [],
        )
    assert "Skill 'alpha-skill' created." in actions


def test_l1_skill_created_suppressed_when_skill_not_in_session_root(tmp_path):
    """L1: when the tool reported success but the skill's SKILL.md is NOT
    reachable from the parent process's roots (writer-root != reader-root,
    e.g. background review spawned with a different HERMES_HOME), the
    notification must be suppressed — the user should NOT be told a skill
    was created that their session cannot load.
    """
    # Tool reports a path under /tmp/writer-root, but the live session's
    # search roots point at tmp_path/reader-root (no overlap).
    writer_root = tmp_path / "writer-root" / "ghost-skill"
    writer_root.mkdir(parents=True)
    (writer_root / "SKILL.md").write_text("---\nname: ghost-skill\n---\n", encoding="utf-8")
    reader_root = tmp_path / "reader-root"
    reader_root.mkdir()
    with patch("tools.skills_tool.SKILLS_DIR", reader_root), \
         patch("agent.skill_utils.get_external_skills_dirs", return_value=[]):
        actions = _summarize(
            [
                _tool_msg(
                    "c1",
                    {
                        "success": True,
                        "message": "Skill 'ghost-skill' created.",
                        "path": str(writer_root),
                    },
                )
            ],
            [],
        )
    assert "Skill 'ghost-skill' created." not in actions
    assert actions == []


def test_l2_regex_extracts_skill_name_from_canonical_message():
    """L2: the helper regex must reliably extract the skill name from the
    canonical ``Skill '<name>' created./updated.`` message shape. The
    match is what the loadability probe uses to look up the skill — if
    this regex is wrong, the probe runs against the wrong name and the
    user gets a misleading notification either way.
    """
    from agent.background_review import _SKILL_ACTION_PATTERN

    match = _SKILL_ACTION_PATTERN.search("Skill 'alpha-skill' created.")
    assert match is not None
    assert match.group(1) == "alpha-skill"
    match = _SKILL_ACTION_PATTERN.search("Skill 'multi-word-name' updated.")
    assert match is not None
    assert match.group(1) == "multi-word-name"
    # Names with hyphens, digits, and underscores — the validator's
    # [a-zA-Z0-9_-]+ charset.
    match = _SKILL_ACTION_PATTERN.search("Skill 'mlops_2-camelCase' created.")
    assert match is not None
    assert match.group(1) == "mlops_2-camelCase"
    # No match for non-skill actions.
    assert _SKILL_ACTION_PATTERN.search("Memory entry created.") is None
    assert _SKILL_ACTION_PATTERN.search("Cron job 'foo' created.") is None


def test_l3_helper_finds_skill_in_local_root(tmp_path):
    """L3: the private ``_is_skill_in_session_root(name)`` helper must find
    a skill whose SKILL.md lives in the local SKILLS_DIR."""
    from agent.background_review import _is_skill_in_session_root

    _setup_skill_in_session_root(tmp_path, "l3-skill")
    with patch("tools.skills_tool.SKILLS_DIR", tmp_path), \
         patch("agent.skill_utils.get_external_skills_dirs", return_value=[]):
        assert _is_skill_in_session_root("l3-skill") is True


def test_l3_helper_returns_false_for_missing_skill(tmp_path):
    """L3: helper returns False when the named skill is not in the session
    roots (the L1 case) — also handles the case where the SKILLS_DIR
    itself does not exist.
    """
    from agent.background_review import _is_skill_in_session_root

    # Empty local dir, no skill
    tmp_path.mkdir(exist_ok=True)
    with patch("tools.skills_tool.SKILLS_DIR", tmp_path), \
         patch("agent.skill_utils.get_external_skills_dirs", return_value=[]):
        assert _is_skill_in_session_root("nonexistent") is False
    # Local dir doesn't exist at all
    missing = tmp_path / "does-not-exist"
    with patch("tools.skills_tool.SKILLS_DIR", missing), \
         patch("agent.skill_utils.get_external_skills_dirs", return_value=[]):
        assert _is_skill_in_session_root("any") is False


def test_l3_helper_finds_skill_in_external_dir(tmp_path):
    """L3: helper also searches external skill directories configured for
    the live session — the case where the user has set
    ``skills.external_dirs`` in ``~/.hermes/config.yaml`` and the new
    skill was written there.
    """
    from agent.background_review import _is_skill_in_session_root

    ext = tmp_path / "external"
    ext.mkdir()
    skill = ext / "ext-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\nname: ext-skill\n---\n", encoding="utf-8")
    with patch("tools.skills_tool.SKILLS_DIR", tmp_path / "empty-local"), \
         patch("agent.skill_utils.get_external_skills_dirs", return_value=[ext]):
        assert _is_skill_in_session_root("ext-skill") is True


def test_l4_warning_logged_and_action_dropped_when_skill_unreachable(tmp_path, caplog):
    """L4: when the loadability probe fails, the action is dropped AND a
    WARNING log records the divergence so an operator can correlate the
    "user got a 'created' line" complaint with the actual writer-root.
    The log must include both the path the tool reported and the
    session's SKILLS_DIR — that's the diagnostic value.
    """
    writer_root = tmp_path / "writer"
    ghost = writer_root / "ghost4"
    ghost.mkdir(parents=True)
    (ghost / "SKILL.md").write_text("---\nname: ghost4\n---\n", encoding="utf-8")
    reader_root = tmp_path / "reader"
    reader_root.mkdir()
    import logging as _logging
    with patch("tools.skills_tool.SKILLS_DIR", reader_root), \
         patch("agent.skill_utils.get_external_skills_dirs", return_value=[]):
        with caplog.at_level(_logging.WARNING, logger="agent.background_review"):
            actions = _summarize(
                [
                    _tool_msg(
                        "c1",
                        {
                            "success": True,
                            "message": "Skill 'ghost4' created.",
                            "path": str(ghost),
                        },
                    )
                ],
                [],
            )
    assert actions == []
    assert any("ghost4" in rec.message and str(reader_root) in rec.message for rec in caplog.records), (
        f"expected a WARNING log mentioning the skill name AND the reader root, got: "
        f"{[r.message for r in caplog.records]}"
    )


# --- Edge cases --------------------------------------------------------------


def test_e1_memory_and_user_profile_actions_bypass_probe(tmp_path):
    """E1: memory and user-profile actions are not skills; the loadability
    probe must NOT apply to them. The session root could be entirely
    empty and these should still surface.
    """
    actions = _summarize(
        [
            _tool_msg(
                "c1",
                {
                    "success": True,
                    "message": "Entry added to store.",
                    "target": "memory",
                },
            ),
            _tool_msg(
                "c2",
                {
                    "success": True,
                    "message": "Entry added to store.",
                    "target": "user",
                },
            ),
        ],
        [],
    )
    assert "Memory updated" in actions
    assert "User profile updated" in actions


def test_e2_malformed_tool_payload_still_skipped_safely():
    """E2: non-JSON content (or JSON without ``success: true``) must not
    regress under the new probe. Mirrors the existing graceful-skip
    behavior for #14944.
    """
    bad = {"success": False, "message": "Skill 'x' created.", "target": "skill"}
    actions = _summarize([_tool_msg("c1", bad)], [])
    assert actions == []
    # Non-JSON content
    actions = _summarize(
        [{"role": "tool", "tool_call_id": "x", "content": "not-json"}],
        [],
    )
    assert actions == []


def test_e3_skill_name_with_regex_special_chars_still_probed(tmp_path):
    """E3: even though the validator restricts names to [a-zA-Z0-9_-]+,
    the probe must not blow up if a name contains regex-special chars.
    """
    from agent.background_review import _is_skill_in_session_root

    weird_name = "dot.skill+name"  # would be a regex bomb if not escaped
    skill_dir = tmp_path / weird_name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {weird_name}\n---\n", encoding="utf-8"
    )
    with patch("tools.skills_tool.SKILLS_DIR", tmp_path), \
         patch("agent.skill_utils.get_external_skills_dirs", return_value=[]):
        # Must not raise; the existing validator would reject the name,
        # but the probe should be defensive.
        result = _is_skill_in_session_root(weird_name)
    # skill_view can resolve the direct directory path, so the result should be True.
    assert result is True


def test_e4_skill_loadable_matches_skill_view_alias_conventions():
    """E4: the probe matches the live ``skill_view`` resolver, including
    both parent-directory and frontmatter-name lookup conventions.
    """
    from agent.background_review import _is_skill_in_session_root
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        td_path = __import__("pathlib").Path(td)
        # dir name = "real-dir-name", frontmatter name = "different"
        skill = td_path / "real-dir-name"
        skill.mkdir()
        (skill / "SKILL.md").write_text(
            "---\nname: different\n---\n", encoding="utf-8"
        )
        with patch("tools.skills_tool.SKILLS_DIR", td_path), \
             patch("agent.skill_utils.get_external_skills_dirs", return_value=[]):
            assert _is_skill_in_session_root("real-dir-name") is True
            assert _is_skill_in_session_root("different") is True


def test_e5_skill_view_failure_suppresses_without_crashing(caplog):
    """E5: if the live resolver raises, the summary must suppress the skill
    notification and log a warning rather than crashing the post-turn review.
    """
    from agent.background_review import _is_skill_in_session_root
    import logging as _logging

    with patch("tools.skills_tool.skill_view", side_effect=RuntimeError("bad config")), \
         caplog.at_level(_logging.WARNING, logger="agent.background_review"):
        result = _is_skill_in_session_root("lives-locally")
    assert result is False
    assert any("failed to verify skill" in rec.message for rec in caplog.records)
