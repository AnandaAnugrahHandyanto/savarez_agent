"""Regression tests: background review tool whitelist includes read_file.

Covers the fix for silent review failures caused by the runtime whitelist
excluding read-only file access (issue #15204, PR #27422).  The review fork
needs read_file to inspect source files when authoring skills, but must
NOT have write_file / patch / search_files (the rest of the file toolset).
"""

from unittest.mock import patch
import threading


def _make_stub(agent_cls):
    """Bare-minimum AIAgent look-alike for _spawn_background_review."""
    a = object.__new__(agent_cls)
    a.model = "test"
    a.platform = "test"
    a.provider = "openai"
    a.session_id = "s-001"
    a.quiet_mode = True
    a._memory_store = None
    a._memory_enabled = True
    a._user_profile_enabled = False
    a._memory_nudge_interval = 5
    a._skill_nudge_interval = 5
    a.background_review_callback = None
    a.status_callback = None
    a._cached_system_prompt = None
    import datetime as _dt
    a.session_start = _dt.datetime(2026, 6, 1)
    a._MEMORY_REVIEW_PROMPT = "memory"
    a._SKILL_REVIEW_PROMPT = "skills"
    a._COMBINED_REVIEW_PROMPT = "both"
    a.enabled_toolsets = ["memory", "skills"]
    a.disabled_toolsets = []
    return a


class _InlineThread:
    """Run target synchronously so tests don't need real threads."""

    def __init__(self, *, target=None, daemon=None, name=None):
        self._fn = target

    def start(self):
        if self._fn:
            self._fn()


def _spawn_and_capture(agent_cls, *, review_memory=True, review_skills=True):
    """Spawn a background review and return captured whitelist + prompt."""
    import run_agent
    from hermes_cli import plugins as _plugins

    agent = _make_stub(agent_cls)
    captured = {"whitelist": None, "deny": None, "prompt": None}

    def _grab_whitelist(whitelist, deny_msg_fmt=None):
        captured["whitelist"] = set(whitelist)
        captured["deny"] = deny_msg_fmt

    def _grab_run(self, *, user_message, conversation_history=None):
        captured["prompt"] = user_message
        raise SystemExit("captured")

    with (
        patch.object(run_agent.AIAgent, "__init__", lambda s, *a, **k: None),
        patch.object(_plugins, "set_thread_tool_whitelist", _grab_whitelist),
        patch.object(run_agent.AIAgent, "run_conversation", _grab_run),
        patch("threading.Thread", _InlineThread),
    ):
        try:
            agent._spawn_background_review(
                messages_snapshot=[],
                review_memory=review_memory,
                review_skills=review_skills,
            )
        except SystemExit:
            pass  # expected — raised after capture

    return agent, captured


class TestWhitelistComposition:
    """read_file must be present; write_file / patch / search_files must not."""

    def test_read_file_allowed(self):
        _, cap = _spawn_and_capture(
            __import__("run_agent").AIAgent
        )
        assert "read_file" in cap["whitelist"], (
            f"read_file missing from whitelist: {cap['whitelist']}"
        )

    def test_write_file_denied(self):
        _, cap = _spawn_and_capture(
            __import__("run_agent").AIAgent
        )
        assert "write_file" not in cap["whitelist"]

    def test_patch_denied(self):
        _, cap = _spawn_and_capture(
            __import__("run_agent").AIAgent
        )
        assert "patch" not in cap["whitelist"]

    def test_search_files_denied(self):
        _, cap = _spawn_and_capture(
            __import__("run_agent").AIAgent
        )
        assert "search_files" not in cap["whitelist"]

    def test_dangerous_tools_still_denied(self):
        _, cap = _spawn_and_capture(
            __import__("run_agent").AIAgent
        )
        for tool in ("terminal", "send_message", "delegate_task",
                      "execute_code", "web_search"):
            assert tool not in cap["whitelist"], f"{tool} leaked into whitelist"

    def test_memory_and_skills_still_allowed(self):
        _, cap = _spawn_and_capture(
            __import__("run_agent").AIAgent
        )
        for tool in ("memory", "skill_manage", "skill_view", "skills_list"):
            assert tool in cap["whitelist"], f"{tool} missing from whitelist"


class TestDenyMessage:
    """Deny message must mention read_file so logs are clear."""

    def test_deny_mentions_read_file(self):
        _, cap = _spawn_and_capture(
            __import__("run_agent").AIAgent
        )
        assert "read_file" in cap["deny"]

    def test_deny_mentions_memory_skill(self):
        _, cap = _spawn_and_capture(
            __import__("run_agent").AIAgent
        )
        assert "memory" in cap["deny"]
        assert "skill" in cap["deny"]


class TestPromptContent:
    """Review prompt must instruct the fork about read_file usage."""

    def test_prompt_mentions_read_file(self):
        _, cap = _spawn_and_capture(
            __import__("run_agent").AIAgent,
            review_skills=True,
        )
        assert "read_file" in cap["prompt"]

    def test_prompt_mentions_read_only(self):
        _, cap = _spawn_and_capture(
            __import__("run_agent").AIAgent,
            review_skills=True,
        )
        # should say "read-only" or "read only" — not imply write access
        assert "read" in cap["prompt"].lower()

    def test_prompt_warns_about_private_content(self):
        _, cap = _spawn_and_capture(
            __import__("run_agent").AIAgent,
            review_skills=True,
        )
        # privacy guard: don't dump local file contents into durable skills
        assert "private" in cap["prompt"].lower() or "copy" in cap["prompt"].lower()
