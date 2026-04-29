"""Eval 018: agent.title_generator.generate_title has timeout default = 60.0."""

import inspect

from agent.title_generator import generate_title


def test_generate_title_timeout_default() -> None:
    sig = inspect.signature(generate_title)
    assert "timeout" in sig.parameters, (
        "generate_title is missing a `timeout` parameter"
    )
    default = sig.parameters["timeout"].default
    assert default == 60.0, (
        f"expected timeout default 60.0, got {default!r}"
    )
