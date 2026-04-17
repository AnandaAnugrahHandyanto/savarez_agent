import pytest

from gateway.config import Platform
from gateway.run import _thread_metadata_for_delivery


class TestMattermostThreadMetadataForDelivery:
    def test_preserves_explicit_thread_id(self):
        metadata = _thread_metadata_for_delivery(
            Platform.MATTERMOST,
            "channel",
            "root_post_123",
            "new_post_456",
        )
        assert metadata == {"thread_id": "root_post_123"}

    def test_synthesizes_thread_id_from_top_level_channel_post(self):
        metadata = _thread_metadata_for_delivery(
            Platform.MATTERMOST,
            "channel",
            None,
            "post_top_level_123",
        )
        assert metadata == {"thread_id": "post_top_level_123"}

    def test_does_not_synthesize_for_mattermost_dm(self):
        metadata = _thread_metadata_for_delivery(
            Platform.MATTERMOST,
            "dm",
            None,
            "post_dm_123",
        )
        assert metadata is None

    def test_does_not_synthesize_for_other_platforms(self):
        metadata = _thread_metadata_for_delivery(
            Platform.TELEGRAM,
            "channel",
            None,
            "post_top_level_123",
        )
        assert metadata is None
