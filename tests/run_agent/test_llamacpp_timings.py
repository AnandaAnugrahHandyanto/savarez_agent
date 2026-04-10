"""Tests for llama.cpp timing extraction and local-only request gating."""

import sys
import types
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

sys.modules.setdefault("fire", types.SimpleNamespace(Fire=lambda *a, **k: None))
sys.modules.setdefault("firecrawl", types.SimpleNamespace(Firecrawl=object))
sys.modules.setdefault("fal_client", types.SimpleNamespace())

from run_agent import AIAgent


def _make_agent() -> AIAgent:
    agent = AIAgent.__new__(AIAgent)
    agent.base_url = "http://127.0.0.1:8080/v1"
    agent.api_mode = "chat_completions"
    agent._local_server_type = "llamacpp"
    agent._local_server_type_base_url = "http://127.0.0.1:8080/v1"
    return agent


def test_llamacpp_timings_are_requested_only_for_llamacpp():
    agent = _make_agent()
    assert agent._should_request_llamacpp_timings() is True

    agent._local_server_type = "ollama"
    assert agent._should_request_llamacpp_timings() is False


def test_extract_llamacpp_tps_from_response_timings():
    agent = _make_agent()
    response = SimpleNamespace(
        timings={
            "predicted_per_second": 52.94494935437416,
            "predicted_ms": 661.064,
            "predicted_n": 35,
        }
    )

    assert agent._extract_llamacpp_tps(response) == 52.94494935437416


def test_extract_llamacpp_tps_from_model_extra_timings():
    agent = _make_agent()
    response = SimpleNamespace(
        model_extra={
            "timings": {
                "predicted_n": 35,
                "predicted_ms": 700.0,
            }
        }
    )

    assert agent._extract_llamacpp_tps(response) == 50.0


def test_llamacpp_metrics_do_not_fall_back_to_wall_clock():
    agent = _make_agent()
    response = SimpleNamespace()

    assert agent._extract_llamacpp_tps(response) is None


def test_non_llamacpp_metrics_are_not_reported():
    agent = _make_agent()
    agent._local_server_type = "ollama"
    response = SimpleNamespace()

    assert agent._extract_llamacpp_tps(response) is None