"""Tests for the Proactive Communication Loop."""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from hermes_cli.proactive_communication_loop import (
    ProactiveCommunicationLoop,
    SynthesisResult,
    THRESHOLD_SCORES,
    _build_synthesis_prompt,
    _parse_synthesis_response,
    _get_threshold_score,
    register_threshold,
    BartokGraphContext,
    BartokGraphConnection,
)


# ──────────────────────────────────────────────────────────────────────
# Threshold constants
# ──────────────────────────────────────────────────────────────────────


def test_conservative_is_highest_threshold():
    assert THRESHOLD_SCORES["conservative"] > THRESHOLD_SCORES["balanced"] > THRESHOLD_SCORES["eager"]


def test_all_thresholds_between_zero_and_one():
    for name, score in THRESHOLD_SCORES.items():
        assert 0.0 <= score <= 1.0, f"{name} out of range"


# ──────────────────────────────────────────────────────────────────────
# Response parser
# ──────────────────────────────────────────────────────────────────────


def test_parse_valid_json():
    raw = json.dumps({
        "should_send": True, "message": "Hey, found something.",
        "novelty": 0.8, "relevance": 0.9,
        "connection_type": "temporal_bridge",
        "reasoning": "Completed task.", "candidates": [],
    })
    result = _parse_synthesis_response(raw)
    assert result["should_send"] is True
    assert result["novelty"] == pytest.approx(0.8)
    assert result["connection_type"] == "temporal_bridge"


def test_parse_markdown_fence():
    raw = "```json\n{\"should_send\": false, \"message\": null, \"novelty\": 0.1, \"relevance\": 0.2, \"connection_type\": \"none\", \"reasoning\": \"nothing\", \"candidates\": []}\n```"
    result = _parse_synthesis_response(raw)
    assert result["should_send"] is False


def test_parse_malformed_returns_no_send():
    result = _parse_synthesis_response("not json!!!")
    assert result["should_send"] is False
    assert result["message"] is None
    assert "parse failure" in result["reasoning"]


# ──────────────────────────────────────────────────────────────────────
# Prompt builder
# ──────────────────────────────────────────────────────────────────────


def test_prompt_without_graph_has_no_bartokgraph_section():
    prompt = _build_synthesis_prompt("user: hello", "(none)", graph_ctx=None)
    assert "RECENT CONVERSATION HISTORY" in prompt
    assert "BARTOKGRAPH CONNECTIONS" not in prompt  # section only appears when connections exist
    assert "should_send" in prompt


def test_prompt_with_graph_connections_includes_bartokgraph_section():
    conn = BartokGraphConnection(
        node_a_content="soil carbon",
        node_b_content="Kenya soil project",
        connection_type="temporal_bridge",
        strength=0.8,
        days_apart=21,
        explanation="both discuss soil carbon",
    )
    graph_ctx = BartokGraphContext(connections=[conn], provider_name="mock")
    prompt = _build_synthesis_prompt("user: soil", "(none)", graph_ctx=graph_ctx)
    assert "BARTOKGRAPH CONNECTIONS" in prompt
    assert "TEMPORAL_BRIDGE" in prompt
    assert "soil carbon" in prompt
    assert "Kenya" in prompt


def test_prompt_with_empty_connections_has_no_bartokgraph_section():
    graph_ctx = BartokGraphContext(connections=[], provider_name="mock")
    prompt = _build_synthesis_prompt("history", "(none)", graph_ctx=graph_ctx)
    assert "BARTOKGRAPH CONNECTIONS" not in prompt  # section only appears when connections exist


def test_prompt_instructs_natural_message():
    prompt = _build_synthesis_prompt("h", "n", graph_ctx=None)
    assert "natural" in prompt.lower() or "conversation" in prompt.lower()
    # Must explicitly tell agent NOT to mention BartokGraph in the message
    assert "Never mention BartokGraph" in prompt or "mechanism" in prompt


# ──────────────────────────────────────────────────────────────────────
# Custom threshold registration
# ──────────────────────────────────────────────────────────────────────


def test_register_custom_threshold():
    @register_threshold("pcl_test_always")
    class AlwaysSend:
        def should_send(self, result: SynthesisResult) -> bool:
            return True

    from hermes_cli.proactive_communication_loop import _registered_thresholds
    assert "pcl_test_always" in _registered_thresholds
    result = SynthesisResult(False, None, "", 0.0, 0.0, 0.0)
    assert _registered_thresholds["pcl_test_always"].should_send(result) is True


def test_custom_threshold_can_block():
    @register_threshold("pcl_test_never")
    class NeverSend:
        def should_send(self, result: SynthesisResult) -> bool:
            return False

    score = _get_threshold_score("pcl_test_never", 0.9, {"novelty": 0.9, "relevance": 0.9, "message": "hi"})
    # Custom "never" threshold should return score > 1.0 (impossible to exceed)
    assert score > 1.0


# ──────────────────────────────────────────────────────────────────────
# ProactiveCommunicationLoop — error handling
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_synthesis_no_send_on_exception():
    """Any error → no-send result, never raises."""
    db = MagicMock()
    db.get_messages_since.side_effect = RuntimeError("db exploded")
    db.get_proactive_sent.return_value = []
    cfg = MagicMock()
    cfg.get.return_value = "conservative"

    with patch("hermes_cli.proactive_communication_loop.ProactiveCommunicationLoop._try_load_bartokgraph", return_value=None):
        loop = ProactiveCommunicationLoop(session_db=db, config=cfg)
    result = await loop.run_synthesis("session-1")

    assert result.should_send is False
    assert result.message is None


@pytest.mark.asyncio
async def test_run_synthesis_no_send_on_empty_history():
    db = MagicMock()
    db.get_messages_since.return_value = []
    db.get_proactive_sent.return_value = []
    cfg = MagicMock()
    cfg.get.return_value = "conservative"

    with patch("hermes_cli.proactive_communication_loop.ProactiveCommunicationLoop._try_load_bartokgraph", return_value=None):
        loop = ProactiveCommunicationLoop(session_db=db, config=cfg)
    result = await loop.run_synthesis("session-empty")

    assert result.should_send is False
    assert "no conversation history" in result.reasoning


@pytest.mark.asyncio
async def test_run_synthesis_respects_daily_limit():
    """If daily limit reached, never sends."""
    db = MagicMock()
    db.get_messages_since.return_value = [{"role": "user", "content": "hello"}]
    db.get_proactive_sent.return_value = [{"summary": "sent one"}]  # already sent today
    cfg = MagicMock()
    cfg.get.side_effect = lambda k, d=None: {
        "proactive_communication.threshold": "conservative",
        "proactive_communication.max_per_day": 1,  # limit = 1
    }.get(k, d)

    with patch("hermes_cli.proactive_communication_loop.ProactiveCommunicationLoop._try_load_bartokgraph", return_value=None):
        loop = ProactiveCommunicationLoop(session_db=db, config=cfg)
    result = await loop.run_synthesis("session-limited")

    assert result.should_send is False
    assert "daily message limit" in result.reasoning


# ──────────────────────────────────────────────────────────────────────
# End-to-end: high-quality synthesis sends, low-quality doesn't
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_high_score_sends_with_conservative_threshold():
    """High novelty + relevance → sends even with conservative threshold."""
    db = MagicMock()
    db.get_messages_since.return_value = [
        {"role": "user", "content": "can you check the logs for errors?"},
        {"role": "assistant", "content": "Scanning now."},
    ]
    db.get_proactive_sent.return_value = []
    cfg = MagicMock()
    cfg.get.side_effect = lambda k, d=None: {
        "proactive_communication.threshold": "conservative",
        "proactive_communication.max_per_day": 3,
        "proactive_communication.bartokgraph.enabled": False,
    }.get(k, d)

    with patch("hermes_cli.proactive_communication_loop.ProactiveCommunicationLoop._try_load_bartokgraph", return_value=None):
        loop = ProactiveCommunicationLoop(session_db=db, config=cfg)

    high_score = json.dumps({
        "should_send": True,
        "message": "Hey — finished the log scan. Errors repeat every 4h at :15. Cron job.",
        "novelty": 0.9, "relevance": 0.88,
        "connection_type": "none",
        "reasoning": "Completed task with clear result.",
        "candidates": ["log result"],
    })
    with patch.object(loop, "_call_synthesis_model", new=AsyncMock(return_value=high_score)):
        result = await loop.run_synthesis("session-logs")

    assert result.should_send is True
    assert result.message is not None
    assert result.novelty_score == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_low_score_blocked_by_conservative_threshold():
    """Low scores → no send even if model says should_send=True."""
    db = MagicMock()
    db.get_messages_since.return_value = [{"role": "user", "content": "hi"}]
    db.get_proactive_sent.return_value = []
    cfg = MagicMock()
    cfg.get.side_effect = lambda k, d=None: {
        "proactive_communication.threshold": "conservative",
        "proactive_communication.max_per_day": 3,
        "proactive_communication.bartokgraph.enabled": False,
    }.get(k, d)

    with patch("hermes_cli.proactive_communication_loop.ProactiveCommunicationLoop._try_load_bartokgraph", return_value=None):
        loop = ProactiveCommunicationLoop(session_db=db, config=cfg)

    low_score = json.dumps({
        "should_send": True,  # model says yes — scores say no
        "message": "Just checking in!",
        "novelty": 0.2, "relevance": 0.3,
        "connection_type": "none",
        "reasoning": "low novelty",
        "candidates": [],
    })
    with patch.object(loop, "_call_synthesis_model", new=AsyncMock(return_value=low_score)):
        result = await loop.run_synthesis("session-low")

    # combined = 0.6*0.2 + 0.4*0.3 = 0.24 < 0.75 (conservative)
    assert result.should_send is False


@pytest.mark.asyncio
async def test_bartokgraph_temporal_bridge_triggers_send():
    """A BartokGraph temporal bridge with high scores → sends."""
    db = MagicMock()
    db.get_messages_since.return_value = [
        {"role": "user", "content": "working on soil carbon analysis today"},
    ]
    db.get_proactive_sent.return_value = []
    cfg = MagicMock()
    cfg.get.side_effect = lambda k, d=None: {
        "proactive_communication.threshold": "conservative",
        "proactive_communication.max_per_day": 3,
        "proactive_communication.bartokgraph.enabled": True,
        "proactive_communication.bartokgraph.workspace": "~",
    }.get(k, d)

    mock_graph = MagicMock()
    mock_graph.get_connections = AsyncMock(return_value=BartokGraphContext(
        connections=[BartokGraphConnection(
            node_a_content="soil carbon",
            node_b_content="Kenya soil project from 3 weeks ago",
            connection_type="temporal_bridge",
            strength=0.85,
            days_apart=21,
            explanation="same concept appeared 21 days ago",
        )],
        provider_name="mock",
    ))

    with patch("hermes_cli.proactive_communication_loop.ProactiveCommunicationLoop._try_load_bartokgraph", return_value=mock_graph):
        loop = ProactiveCommunicationLoop(session_db=db, config=cfg)

    bridge_msg = json.dumps({
        "should_send": True,
        "message": "You worked on soil carbon 3 weeks ago in the Kenya project. The approach you found then applies here.",
        "novelty": 0.88, "relevance": 0.85,
        "connection_type": "temporal_bridge",
        "reasoning": "BartokGraph temporal bridge — high novelty.",
        "candidates": ["Kenya soil project"],
    })
    with patch.object(loop, "_call_synthesis_model", new=AsyncMock(return_value=bridge_msg)):
        result = await loop.run_synthesis("session-bridge")

    assert result.should_send is True
    assert result.connection_type == "temporal_bridge"
    assert "Kenya" in (result.message or "")
