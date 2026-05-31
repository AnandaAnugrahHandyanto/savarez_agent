from gateway.platforms.base import BasePlatformAdapter, MediaKind


def test_media_kind_has_four_members():
    assert {k.name for k in MediaKind} == {"IMAGE", "VIDEO", "VOICE", "DOCUMENT"}


def test_base_default_is_fail_closed_empty():
    assert BasePlatformAdapter.MEDIA_KINDS == frozenset()
