"""Unit tests for agent.task_review — structured task-review engine."""

import pytest

from agent.task_review import TaskReviewResult, review_completed_task


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _payload(
    *,
    trigger_reasons=None,
    tools_used=None,
    completed=True,
    interrupted=False,
    final_response="Done",
    original_user_message="do something",
):
    """Build a minimal task-completion payload dict for testing."""
    return {
        "session_id": "test-session",
        "platform": "",
        "model": "test/model",
        "completed": completed,
        "interrupted": interrupted,
        "original_user_message": original_user_message,
        "final_response": final_response,
        "tool_call_count": len(tools_used or []),
        "tools_used": tools_used or [],
        "trigger_reasons": trigger_reasons or [],
    }


# ---------------------------------------------------------------------------
# TaskReviewResult dataclass
# ---------------------------------------------------------------------------

class TestTaskReviewResult:
    def test_is_frozen(self):
        r = TaskReviewResult(
            should_review_memory=False,
            should_review_skills=False,
            review_reasons=[],
            payload={},
        )
        with pytest.raises(AttributeError):
            r.should_review_memory = True  # type: ignore[misc]

    def test_fields_accessible(self):
        p = {"key": "val"}
        r = TaskReviewResult(
            should_review_memory=True,
            should_review_skills=False,
            review_reasons=["reason"],
            payload=p,
        )
        assert r.should_review_memory is True
        assert r.should_review_skills is False
        assert r.review_reasons == ["reason"]
        assert r.payload is p


# ---------------------------------------------------------------------------
# review_completed_task — input validation
# ---------------------------------------------------------------------------

class TestReviewCompletedTaskValidation:
    def test_none_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            review_completed_task(None)  # type: ignore[arg-type]

    def test_empty_dict_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            review_completed_task({})


# ---------------------------------------------------------------------------
# review_completed_task — decision logic
# ---------------------------------------------------------------------------

class TestReviewCompletedTaskDecisions:
    def test_no_triggers_returns_no_review(self):
        result = review_completed_task(_payload(trigger_reasons=[]))
        assert result.should_review_memory is False
        assert result.should_review_skills is False
        assert result.review_reasons == []

    def test_tool_used_triggers_skill_review(self):
        result = review_completed_task(
            _payload(trigger_reasons=["tool_used"], tools_used=["web_search"])
        )
        assert result.should_review_skills is True
        assert result.should_review_memory is False
        assert any("tools were used" in r for r in result.review_reasons)

    def test_explicit_memory_request_triggers_memory_review(self):
        result = review_completed_task(
            _payload(
                trigger_reasons=["explicit_memory_request"],
                original_user_message="remember this preference",
            )
        )
        assert result.should_review_memory is True
        assert result.should_review_skills is False
        assert any("explicitly asked" in r for r in result.review_reasons)

    def test_memory_tool_used_triggers_both(self):
        result = review_completed_task(
            _payload(
                trigger_reasons=["tool_used"],
                tools_used=["web_search", "memory"],
            )
        )
        assert result.should_review_memory is True
        assert result.should_review_skills is True
        assert len(result.review_reasons) == 2

    def test_user_profile_tool_triggers_memory(self):
        result = review_completed_task(
            _payload(
                trigger_reasons=["tool_used"],
                tools_used=["user_profile"],
            )
        )
        assert result.should_review_memory is True
        assert result.should_review_skills is True

    def test_combined_triggers(self):
        result = review_completed_task(
            _payload(
                trigger_reasons=["tool_used", "explicit_memory_request"],
                tools_used=["code_editor"],
            )
        )
        assert result.should_review_memory is True
        assert result.should_review_skills is True
        assert len(result.review_reasons) == 2

    def test_payload_passthrough(self):
        p = _payload(trigger_reasons=["tool_used"], tools_used=["web_search"])
        result = review_completed_task(p)
        assert result.payload is p

    def test_unknown_trigger_reason_ignored(self):
        result = review_completed_task(
            _payload(trigger_reasons=["some_future_reason"])
        )
        assert result.should_review_memory is False
        assert result.should_review_skills is False
        assert result.review_reasons == []
