"""Feature-shape anchor for the OpenRouter STT provider (#24415).

Drives the exact end-to-end shape from the issue's "Proposed
Solution" section so a future refactor that drops any of the four
contract bullet points fails with an explicit "#24415" message.

The feature contract from the issue:

  1. ``stt.provider: openrouter`` in config is honoured.
  2. The OpenAI SDK gets called with
     ``base_url=https://openrouter.ai/api/v1``.
  3. Authorisation uses ``OPENROUTER_API_KEY`` from the env (the
     same env var the LLM stack reads).
  4. The default model is ``openai/whisper-1``.
  5. The provider lives in the auto-detect chain so a user who only
     has ``OPENROUTER_API_KEY`` set (no other STT key) gets STT for
     free.

This module ships ONE focused end-to-end test that asserts every
bullet at once.  Why a single test instead of five: the issue's
acceptance criterion is the user-visible round trip, not any
individual internal helper -- if any link breaks, the whole chain
fails.

Why this proves the feature is wired: on upstream/main the test
fails with ``AssertionError: #24415 anchor: ...`` because either
the dispatch returns a "no provider available" error (provider name
unknown) or the OpenAI SDK is never reached at all.  After the
feature lands the test passes.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in (
        "OPENROUTER_API_KEY",
        "VOICE_TOOLS_OPENAI_KEY",
        "OPENAI_API_KEY",
        "GROQ_API_KEY",
        "MISTRAL_API_KEY",
        "XAI_API_KEY",
        "STT_OPENROUTER_BASE_URL",
        "STT_OPENROUTER_MODEL",
        "HERMES_LOCAL_STT_COMMAND",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def sample_audio(tmp_path):
    audio_path = tmp_path / "voice.ogg"
    audio_path.write_bytes(b"fake-ogg-bytes")
    return str(audio_path)


def _build_fake_openai_module(transcript: str = "hello from openrouter"):
    """Mock the openai package surface ``_transcribe_openrouter``
    actually consumes."""
    fake = MagicMock()
    fake.OpenAI.return_value.audio.transcriptions.create.return_value = transcript

    class _APIError(Exception):
        pass

    class _APIConnectionError(Exception):
        pass

    class _APITimeoutError(Exception):
        pass

    fake.APIError = _APIError
    fake.APIConnectionError = _APIConnectionError
    fake.APITimeoutError = _APITimeoutError
    return fake


class TestOpenRouterSttFeatureContract:
    def test_full_user_round_trip_honours_issue_contract(
        self, monkeypatch, sample_audio,
    ):
        """End-to-end #24415 anchor:

        Given:
          * ``OPENROUTER_API_KEY=sk-or-real`` in env (the same key
            the LLM stack reads).
          * ``stt.provider: openrouter`` in config (no other STT
            keys set).

        When transcribe_audio() is called,

        Then ALL of the following must hold:
          * The result reports ``provider == "openrouter"``.
          * The OpenAI SDK was constructed with
            ``base_url=https://openrouter.ai/api/v1``.
          * The OpenAI SDK was constructed with
            ``api_key=sk-or-real``.
          * The transcription call used model ``openai/whisper-1``
            (the documented default).

        On upstream/main this whole chain fails -- the provider
        name is unknown to ``_get_provider``, dispatch returns a
        "no provider available" error, and the OpenAI SDK is never
        constructed.  After the fix it passes.
        """
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-real")

        fake_openai_module = _build_fake_openai_module(
            transcript="hello from openrouter",
        )

        cfg = {"enabled": True, "provider": "openrouter"}
        with patch(
            "tools.transcription_tools._load_stt_config",
            return_value=cfg,
        ), patch(
            "tools.transcription_tools._HAS_FASTER_WHISPER", False
        ), patch(
            "tools.transcription_tools._has_local_command",
            return_value=False,
        ), patch(
            "tools.transcription_tools._HAS_OPENAI", True
        ), patch.dict("sys.modules", {"openai": fake_openai_module}):
            from tools.transcription_tools import transcribe_audio
            result = transcribe_audio(sample_audio)

        # ---- Bullet 1+3: provider routes to openrouter, not "none" ------
        assert result["success"] is True, (
            "#24415 anchor: stt.provider=openrouter with OPENROUTER_API_KEY "
            f"set must succeed -- got error: {result.get('error')!r}.  This "
            "means _get_provider does not recognise 'openrouter' or the "
            "dispatch in transcribe_audio is missing -- the feature is "
            "not wired."
        )
        assert result["provider"] == "openrouter", (
            "#24415 anchor: provider field in the response must be "
            f"'openrouter', got {result.get('provider')!r}"
        )
        assert result["transcript"] == "hello from openrouter"

        # ---- Bullet 2: OpenAI SDK called with OpenRouter base_url -------
        assert fake_openai_module.OpenAI.called, (
            "#24415 anchor: the OpenAI SDK was never constructed -- the "
            "OpenRouter dispatch path is not reaching _transcribe_openrouter"
        )
        sdk_kwargs = fake_openai_module.OpenAI.call_args.kwargs
        assert sdk_kwargs["base_url"] == "https://openrouter.ai/api/v1", (
            "#24415 anchor: OpenAI SDK base_url must be the OpenRouter "
            f"endpoint, got {sdk_kwargs.get('base_url')!r}"
        )

        # ---- Bullet 3: env key reached the SDK --------------------------
        assert sdk_kwargs["api_key"] == "sk-or-real", (
            "#24415 anchor: OPENROUTER_API_KEY must reach the OpenAI SDK "
            f"unchanged, got {sdk_kwargs.get('api_key')!r}"
        )

        # ---- Bullet 4: default model = openai/whisper-1 -----------------
        create_kwargs = (
            fake_openai_module.OpenAI.return_value
            .audio.transcriptions.create.call_args.kwargs
        )
        assert create_kwargs["model"] == "openai/whisper-1", (
            "#24415 anchor: default OpenRouter STT model must be "
            f"'openai/whisper-1', got {create_kwargs.get('model')!r}"
        )

    def test_auto_detect_lights_up_with_only_openrouter_key(
        self, monkeypatch, sample_audio,
    ):
        """Bullet 5 from the issue: a user who has ONLY
        ``OPENROUTER_API_KEY`` set (no Groq / OpenAI / xAI key, no
        explicit ``stt.provider``, no local backend) must get STT
        via OpenRouter -- the provider has to be in the auto-detect
        chain, not just an opt-in setting."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-real")

        fake_openai_module = _build_fake_openai_module()
        cfg = {"enabled": True}  # no provider, no per-provider config

        with patch(
            "tools.transcription_tools._load_stt_config",
            return_value=cfg,
        ), patch(
            "tools.transcription_tools._HAS_FASTER_WHISPER", False
        ), patch(
            "tools.transcription_tools._has_local_command",
            return_value=False,
        ), patch(
            "tools.transcription_tools._HAS_OPENAI", True
        ), patch(
            "tools.transcription_tools._has_openai_audio_backend",
            return_value=False,
        ), patch.dict("sys.modules", {"openai": fake_openai_module}):
            from tools.transcription_tools import transcribe_audio
            result = transcribe_audio(sample_audio)

        assert result["success"] is True and result["provider"] == "openrouter", (
            "#24415 anchor: with only OPENROUTER_API_KEY set and no other "
            "STT backend available, auto-detect MUST land on the openrouter "
            f"provider -- got result={result!r}.  Without this the user has "
            "no STT at all, which is the headline regression the feature "
            "request was filed to prevent."
        )
