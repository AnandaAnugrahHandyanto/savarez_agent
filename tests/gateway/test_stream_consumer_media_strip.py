from gateway.stream_consumer import GatewayStreamConsumer
from gateway.platforms.base import _MEDIA_TAG_RE


def _clean(text):
    return GatewayStreamConsumer._clean_for_display(text)


def test_spaced_media_path_fully_stripped_from_display():
    # Old blind \S+ left "Docs/x.pdf" visible; shared anchored grammar strips it.
    assert "Docs" not in _clean("Here MEDIA:/My Docs/x.pdf")
    assert "MEDIA:" not in _clean("Here MEDIA:/My Docs/x.pdf")


def test_bold_wrapped_media_stripped_from_display():
    out = _clean("**MEDIA:/tmp/x.png**")
    assert "MEDIA:" not in out
    assert "*" not in out


def test_stream_consumer_shares_base_pattern_object():
    # Guard against re-introducing a separate (driftable) copy.
    assert GatewayStreamConsumer._MEDIA_RE is _MEDIA_TAG_RE
