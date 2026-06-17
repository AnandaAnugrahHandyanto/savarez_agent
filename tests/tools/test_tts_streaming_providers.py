"""Tests for the ``StreamingTTSProvider`` ABC and registry.

These tests cover the generic dispatcher's contract surface added in
Task 1 of the streaming-TTS plan: the ABC requires ``stream()`` and the
three audio-format attributes, and the module-level registry is a
case-insensitive, whitespace-tolerant, sorted-on-read store of provider
classes keyed by name.

Nothing here talks to a real TTS engine or ``sounddevice``. The
``_make_fake_provider_class`` helper produces the smallest possible
subclass that satisfies the ABC, so the tests stay hermetic and fast.
"""

from __future__ import annotations

import pytest

from tools.tts_streaming import (
    StreamingTTSProvider,
    available,
    get,
    register,
)


@pytest.fixture(autouse=True)
def _clear_registry():
    """Snapshot and restore the registry around each test.

    The dispatcher is a module-level dict, and Tasks 3-7 will register
    real providers at import time. We snapshot on entry, clear for the
    duration of the test, then restore on exit so no test pollutes
    global state and no test depends on prior registration.
    """
    from tools import tts_streaming
    saved = dict(tts_streaming._PROVIDERS)
    tts_streaming._PROVIDERS.clear()
    yield
    tts_streaming._PROVIDERS.clear()
    tts_streaming._PROVIDERS.update(saved)


def _make_fake_provider_class(name: str = "fake"):
    """Build a minimal concrete ``StreamingTTSProvider`` and register it.

    Returns the class object (not an instance) so tests can both inspect
    the registered class via ``get(name)`` and instantiate it for
    behavioral checks.
    """
    @register(name)
    class FakeProvider(StreamingTTSProvider):
        sample_rate = 24000
        channels = 1
        sample_width = 2

        def stream(self, text):
            yield b"abc"
            yield b"def"
    return FakeProvider


# --- ABC contract ---


def test_abc_requires_stream_method():
    """Can't instantiate a subclass that doesn't implement ``stream()``.

    Python's ABC machinery raises ``TypeError`` at construction when an
    abstract method is unimplemented, which is the contract the
    dispatcher relies on.
    """
    class Incomplete(StreamingTTSProvider):
        sample_rate = 24000
        channels = 1
        sample_width = 2
    with pytest.raises(TypeError):
        Incomplete()


def test_concrete_provider_has_audio_format_attrs():
    """Subclass must expose the three audio-format attributes.

    The dispatcher reads ``sample_rate``, ``channels``, and
    ``sample_width`` off the instance to open the ``sounddevice``
    ``OutputStream`` with the right format, so each registered class
    must set them to concrete values.
    """
    Fake = _make_fake_provider_class("attrs_test")
    inst = Fake()
    assert inst.sample_rate == 24000
    assert inst.channels == 1
    assert inst.sample_width == 2
    # And the types match what ``sounddevice`` expects.
    assert isinstance(inst.sample_rate, int)
    assert isinstance(inst.channels, int)
    assert isinstance(inst.sample_width, int)


# --- Registry: round-trip and error reporting ---


def test_register_and_get_roundtrip():
    """``@register(name)`` stores the class and ``get(name)`` returns it."""
    Fake = _make_fake_provider_class("roundtrip")
    assert get("roundtrip") is Fake


def test_get_raises_for_unknown():
    """``get("nonexistent")`` raises ``KeyError`` whose message is actionable.

    The message must include both the unknown name (so the caller can
    log it) and the list of available names (so the user knows what's
    possible). This is the contract that lets the dispatcher surface a
    helpful error or fall back to a default.
    """
    _make_fake_provider_class("known")
    with pytest.raises(KeyError) as exc_info:
        get("nonexistent")
    msg = str(exc_info.value)
    assert "nonexistent" in msg
    assert "known" in msg


def test_get_unknown_error_includes_every_registered_name():
    """The error message enumerates *every* registered provider, not just one.

    Guards against a regression where the message would only mention the
    first registered name (e.g. from a ``next(iter(...))`` mistake).
    """
    _make_fake_provider_class("alpha")
    _make_fake_provider_class("beta")
    _make_fake_provider_class("gamma")
    with pytest.raises(KeyError) as exc_info:
        get("nope")
    msg = str(exc_info.value)
    assert "alpha" in msg
    assert "beta" in msg
    assert "gamma" in msg


# --- Registry: validation and normalization ---


def test_register_rejects_non_subclass():
    """``@register`` refuses classes that don't subclass ``StreamingTTSProvider``.

    This protects the dispatcher from a silent invariant violation —
    a class without ``stream()`` would only blow up at the first chunk
    yield, deep inside the audio callback, where the traceback is
    useless. Failing loudly at registration time keeps the bug close to
    its source.
    """
    class NotASubclass:
        pass
    with pytest.raises(TypeError):
        register("bad")(NotASubclass)


def test_register_rejects_non_class():
    """``@register`` also refuses non-class callables (e.g. plain functions).

    The decorator accepts ``Type[StreamingTTSProvider]``, so a function
    object should fail the same ``issubclass`` check.
    """
    def not_a_class():
        pass
    with pytest.raises(TypeError):
        register("bad_func")(not_a_class)


def test_available_returns_sorted():
    """``available()`` returns registered names in sorted order, regardless
    of registration order.
    """
    _make_fake_provider_class("zeta")
    _make_fake_provider_class("alpha")
    _make_fake_provider_class("mu")
    assert available() == ["alpha", "mu", "zeta"]


def test_register_normalizes_name_case():
    """``@register`` lower-cases the name; ``get`` does the same for look-ups.

    This is what makes ``register("ElevenLabs")`` and
    ``get("elevenlabs")`` (or ``get("ELEVENLABS")``) the same key, so
    user-supplied provider names from config files don't have to match
    the registration case exactly.
    """
    _make_fake_provider_class("MixedCase")
    # Direct lower-case lookup.
    assert get("mixedcase") is not None
    # Whitespace + different case still resolves to the same entry.
    assert get("  MIXEDCASE  ") is not None
    assert get("mixedcase") is get("  MIXEDCASE  ")


def test_available_empty_by_default():
    """No providers registered → empty list (the autouse fixture cleared)."""
    assert available() == []


# --- Behavioral contract of the ABC ---


def test_stream_yields_bytes():
    """``stream()`` is an iterator of ``bytes`` chunks.

    The dispatcher's audio callback writes whatever each ``yield``
    produces straight into ``sounddevice.OutputStream.write``, so the
    contract is simply "yield small ``bytes`` objects, in order". A
    trivial subclass that yields ``b"abc"``, ``b"def"`` should yield
    those exact bytes when iterated.
    """
    Fake = _make_fake_provider_class("yield_test")
    inst = Fake()
    chunks = list(inst.stream("hello"))
    assert chunks == [b"abc", b"def"]


def test_stream_is_lazy_iterator():
    """``stream()`` returns a lazy iterator, not a pre-computed list.

    Streaming is the whole point of this interface — eager evaluation
    would defeat the chunked-output design. We assert by tagging each
    checkpoint in the generator with a unique 2-tuple and confirming
    that the tags appear in the produced list at the right moment —
    no earlier, no later.
    """
    # Snapshot the pre-existing registration (the helper registers a
    # default ``FakeProvider``); we want to replace it with our own
    # tracking provider without affecting other tests.
    from tools import tts_streaming
    tts_streaming._PROVIDERS.pop("lazy_test", None)

    produced = []

    def tracking_stream(self, text):
        produced.append(("start", text))
        yield b"chunk1"
        produced.append(("after_first", text))
        yield b"chunk2"
        produced.append(("done", text))

    @register("lazy_test")
    class LazyProvider(StreamingTTSProvider):
        sample_rate = 24000
        channels = 1
        sample_width = 2
        stream = tracking_stream

    inst = LazyProvider()
    it = inst.stream("hi")
    # Nothing has been produced yet — the generator is un-started.
    assert produced == []
    # Pull the first chunk. A generator function runs up to the first
    # ``yield`` and pauses there, so the "start" tag has fired but
    # "after_first" has not — that line sits between the two yields.
    first = next(it)
    assert first == b"chunk1"
    assert produced == [("start", "hi")]
    # Pull the second chunk — the function resumes past the first
    # yield, "after_first" fires, and the second yield pauses.
    second = next(it)
    assert second == b"chunk2"
    assert produced == [("start", "hi"), ("after_first", "hi")]
    # Exhaust the iterator — the trailing "done" line runs at last.
    with pytest.raises(StopIteration):
        next(it)
    assert produced == [
        ("start", "hi"),
        ("after_first", "hi"),
        ("done", "hi"),
    ]
