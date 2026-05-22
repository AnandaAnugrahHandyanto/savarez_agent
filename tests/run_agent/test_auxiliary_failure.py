"""Tests for user-visible auxiliary failure handling."""

from __future__ import annotations

import logging

import run_agent
from run_agent import AIAgent


def test_title_generation_failure_logs_without_user_warning(caplog):
    agent = object.__new__(AIAgent)
    warnings = []
    agent._emit_warning = warnings.append
    agent._summarize_api_error = lambda exc: (_ for _ in ()).throw(
        AssertionError("title generation should not summarize provider errors")
    )

    with caplog.at_level(logging.WARNING, logger=run_agent.logger.name):
        agent._emit_auxiliary_failure("title generation", RuntimeError("blocked"))

    assert warnings == []
    assert "Auxiliary title generation failed: blocked" in caplog.text


def test_non_title_auxiliary_failure_still_emits_user_warning():
    agent = object.__new__(AIAgent)
    warnings = []
    agent._emit_warning = warnings.append
    agent._summarize_api_error = lambda exc: "compact detail"

    agent._emit_auxiliary_failure("background review", RuntimeError("raw detail"))

    assert warnings == ["⚠ Auxiliary background review failed: compact detail"]
