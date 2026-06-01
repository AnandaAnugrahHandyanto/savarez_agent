"""Pipecat production transport + LLM-service seam (WP10 — DEFERRED).

Slice 1 proves the reflex core (`StreamingCallSession`) entirely in simulation.
This module is the *seam* where the production Pipecat pipeline will plug the
slice's ports onto the real SimpleX/aiortc audio path. It is intentionally a
documented stub: the integration itself is a follow-on slice.

Why deferred (decision recorded during WP10):
- WP0 confirmed `pipecat-ai==1.3.0` resolves on this interpreter, BUT installing
  it downgrades `onnxruntime` 1.26 -> 1.22 and pulls ~15 transitive deps into the
  shared venv, risking the existing faster-whisper / VAD stack.
- The adapter cannot be meaningfully verified without a live call, which is out of
  Slice 1 scope (sim-before-live). Shipping unrunnable adapter code would add risk
  without verification.
- Spec §8.4 DoD explicitly permits the Pipecat smoke to be "explicitly skipped with
  the WP0 wheel finding logged."

Intended production design (for the follow-on slice):

    SimplexAudioTransport(BaseTransport)
        - subclass Pipecat's BaseTransport.
        - inbound: from the existing aiortc RTCPeerConnection recv() loop
          (see gateway/calls/native/aiortc_engine.py), wrap each PCM16 chunk as
          pipecat InputAudioRawFrame and push into the pipeline.
        - outbound: consume OutputAudioRawFrame and enqueue PCM16 onto the aiortc
          AudioStreamTrack (mind pts/time_base/AUDIO_PTIME=0.02).
        - bridge flush_outbound() -> drop queued outbound frames on barge-in.

    HermesLLMService(LLMService)
        - subclass Pipecat's LLMService; run_inference() delegates to
          gateway.calls.native.streaming.brain.HermesSyncBrain (asyncio.to_thread
          around AIAgent.run_conversation), keeping Hermes the brain.

    VAD / turn detection: SileroVADAnalyzer + LocalSmartTurnAnalyzerV3 wired into
    the transport params (these need onnxruntime; resolve the wheel/env question in
    the follow-on).

The follow-on slice should: pin/segregate the pipecat dependency (optional extra or
isolated venv), implement the two classes above, and replace the import-skipped
smoke test with a real one-turn-to-DONE assertion.
"""
from __future__ import annotations


class PipecatIntegrationDeferred(NotImplementedError):
    """Raised if production Pipecat wiring is invoked before its follow-on slice."""


def build_pipeline(*_args: object, **_kwargs: object) -> object:
    """Placeholder for the production Pipecat pipeline builder.

    Deferred to a follow-on slice (see module docstring). The reflex core
    (`StreamingCallSession`) is fully usable and tested in simulation today.
    """
    raise PipecatIntegrationDeferred(
        "Pipecat production transport is deferred to a follow-on slice; "
        "Slice 1 ships the reflex core proven in simulation. See module docstring."
    )
