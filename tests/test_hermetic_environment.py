"""Regression coverage for process-level pytest environment isolation."""

from __future__ import annotations

import os

import tests.conftest as hermes_conftest


def test_kanban_env_pins_do_not_leak_from_pytest_process_env():
    """Ambient Kanban pins must not be visible inside test bodies.

    Hermes sessions and dispatcher workers legitimately export these variables,
    so local developer shells can carry them into `pytest`. The global hermetic
    fixture owns clearing them; individual Kanban tests opt back in with
    `monkeypatch.setenv(...)` when a variable is part of the behavior under test.
    """

    leaked = {
        name: os.environ[name]
        for name in sorted(hermes_conftest._HERMES_KANBAN_BEHAVIORAL_VARS)
        if name in os.environ
    }

    assert leaked == {}


def test_tests_can_still_set_kanban_env_pins_explicitly(monkeypatch):
    """The hermetic fixture clears ambient state, not test-local setup."""

    monkeypatch.setenv("HERMES_KANBAN_BOARD", "explicit-test-board")

    assert os.environ["HERMES_KANBAN_BOARD"] == "explicit-test-board"
