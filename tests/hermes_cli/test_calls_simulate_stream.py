"""Tests for the `calls simplex-simulate-stream` CLI subcommand (WP9)."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from hermes_cli.calls import cmd_calls


def test_simplex_simulate_stream_normal_turn_json(capsys):
    """Normal turn: one completed record, outbound frames > 0, no flushes."""
    rc = cmd_calls(
        SimpleNamespace(
            calls_command="simplex-simulate-stream",
            call_id="cli-stream-sim",
            contact_id="sim-contact",
            caller_text="what's the weather",
            response_text="It's sunny today.",
            barge_in=False,
            brain_delay_ms=0,
            json=True,
        )
    )

    result = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert result["ok"] is True
    assert result["code"] == "call_stream_simulation_passed"
    assert result["call_id"] == "cli-stream-sim"
    assert len(result["turns"]) == 1
    turn = result["turns"][0]
    assert turn["ended_reason"] == "completed"
    assert turn["interrupted"] is False
    assert result["outbound_audio_frames"] > 0
    assert result["flushes"] == []


def test_simplex_simulate_stream_barge_in_json(capsys):
    """Barge-in turn: ended_reason barged_in, interrupted True, barge_in in flushes."""
    rc = cmd_calls(
        SimpleNamespace(
            calls_command="simplex-simulate-stream",
            call_id="cli-barge-sim",
            contact_id="sim-contact",
            caller_text="hold on stop",
            response_text="one two three four five six seven eight nine ten",
            barge_in=True,
            brain_delay_ms=0,
            json=True,
        )
    )

    result = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert result["ok"] is True
    assert len(result["turns"]) == 1
    turn = result["turns"][0]
    assert turn["ended_reason"] == "barged_in"
    assert turn["interrupted"] is True
    assert "barge_in" in result["flushes"]


def test_simplex_simulate_stream_plain_text_output(capsys):
    """Non-JSON output still has PASS status and key fields."""
    rc = cmd_calls(
        SimpleNamespace(
            calls_command="simplex-simulate-stream",
            call_id="plain-test",
            contact_id="sim-contact",
            caller_text="hello",
            response_text="hi there",
            barge_in=False,
            brain_delay_ms=0,
            json=False,
        )
    )

    output = capsys.readouterr().out
    assert rc == 0
    assert "PASS" in output
    assert "call_stream_simulation_passed" in output
    assert "plain-test" in output
    assert "turns: 1" in output


def test_simplex_simulate_stream_defaults_work(capsys):
    """Omitted optional args use sensible defaults and still pass."""
    rc = cmd_calls(
        SimpleNamespace(
            calls_command="simplex-simulate-stream",
            call_id=None,
            contact_id=None,
            caller_text=None,
            response_text=None,
            barge_in=False,
            brain_delay_ms=0,
            json=True,
        )
    )

    result = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert result["ok"] is True
    assert result["call_id"] == "stream-sim"
