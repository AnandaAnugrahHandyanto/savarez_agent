"""Pipecat production-transport smoke test (WP10 — DEFERRED / import-skipped).

Per spec §8.4, the Pipecat smoke may be "explicitly skipped with the WP0 wheel
finding logged." WP0 found pipecat-ai wheels resolve, but installing them
downgrades onnxruntime and perturbs the shared venv, so the actual integration is
deferred to a follow-on slice (see gateway/calls/native/streaming/pipecat_transport.py).

These tests therefore (a) skip cleanly when pipecat is not installed, and
(b) assert the deferral seam behaves as documented so the contract is locked in.
"""
from __future__ import annotations

import pytest

from gateway.calls.native.streaming.pipecat_transport import (
    PipecatIntegrationDeferred,
    build_pipeline,
)


def test_pipecat_not_required_for_slice1():
    """The reflex core does not import pipecat; the smoke is import-skipped."""
    pytest.importorskip(
        "pipecat",
        reason="Pipecat integration deferred to a follow-on slice (WP10); "
        "Slice 1 proves the reflex core in simulation.",
    )
    # If pipecat IS installed in some future environment, the follow-on slice will
    # replace this with a real one-turn-to-DONE pipeline assertion.
    pytest.skip("Pipecat production wiring is implemented in a follow-on slice.")


def test_build_pipeline_is_explicitly_deferred():
    """The seam fails loudly (not silently) if invoked before the follow-on slice."""
    with pytest.raises(PipecatIntegrationDeferred):
        build_pipeline()
