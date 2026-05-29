import pytest

from gateway.stream_consumer import GatewayStreamConsumer
from gateway.platforms.base import BasePlatformAdapter


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


@pytest.mark.parametrize("text", [
    "Here MEDIA:/My Docs/x.pdf",
    "**MEDIA:/tmp/x.png**",
    "Done. MEDIA:/tmp/a.png and more prose",
    r"got it MEDIA:C:\out\img.png",
    "MEDIA:/tmp/notes.md MEDIA:/tmp/notes.md",
    "no media here at all",
    "lowercase media:/tmp/a.png stays",
    "unknown MEDIA:/tmp/x.xyz stays",
])
def test_streaming_display_strip_matches_extractor_cleaning(text):
    # Zero-drift contract (behavioral, not "same object"): the streaming display
    # path must strip MEDIA: tags identically to the canonical extract_media
    # cleaner, however each is implemented. Survives a refactor that achieves
    # the same behavior without literally sharing one regex object.
    _media, extractor_cleaned = BasePlatformAdapter.extract_media(text)
    assert _clean(text).strip() == extractor_cleaned.strip()
