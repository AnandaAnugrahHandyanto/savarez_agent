import builtins

import pytest

from gateway.calls.native.streaming import pipecat_runtime as pr


def test_absent_is_safe(monkeypatch):
    # Force the in-function import to fail, simulating the extra not installed.
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pipecat" or name.startswith("pipecat."):
            raise ImportError("simulated missing pipecat")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(pr, "_distribution_version", lambda _name: None)
    assert pr.pipecat_available() is False
    assert pr.pipecat_version() is None  # must not raise


@pytest.mark.skipif(not pr.pipecat_available(), reason="simplex-streaming extra not installed")
def test_present_reports_version():
    assert pr.pipecat_available() is True
    assert pr.pipecat_version() == "1.3.0"
