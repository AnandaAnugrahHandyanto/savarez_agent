"""Tests for _build_outbound_payload after removal of markdown table force-text workaround.

Issue #26658: Feishu now natively supports tables in post format, so the
_MARKDOWN_TABLE_RE workaround that forced table content to plain text
has been removed. Table content should now flow through the normal
markdown post pipeline.
"""

import json
import unittest
from unittest.mock import patch


class TestBuildOutboundPayload(unittest.TestCase):
    """_build_outbound_payload routes content to correct msg_type."""

    def setUp(self):
        from gateway.platforms.feishu import FeishuAdapter
        from gateway.config import PlatformConfig
        self.adapter = FeishuAdapter(PlatformConfig())

    def test_markdown_table_goes_to_post_not_text(self):
        """Table content now flows through post pipeline, not forced to text."""
        content = "| Name | Age |\n|------|-----|\n| Ada  | 30  |"
        msg_type, payload_json = self.adapter._build_outbound_payload(content)
        self.assertEqual(msg_type, "post", "Table content should be post, not text")
        payload = json.loads(payload_json)
        self.assertIn("zh_cn", payload)

    def test_plain_text_still_goes_to_text(self):
        """Plain text (no markdown) still goes to text mode."""
        msg_type, _ = self.adapter._build_outbound_payload("Hello world")
        self.assertEqual(msg_type, "text")

    def test_markdown_without_table_goes_to_post(self):
        """Non-table markdown (bold, italic) still goes to post."""
        msg_type, _ = self.adapter._build_outbound_payload("Hello **world**")
        self.assertEqual(msg_type, "post")

    def test_empty_content_goes_to_text(self):
        """Empty string falls through to text."""
        msg_type, _ = self.adapter._build_outbound_payload("")
        self.assertEqual(msg_type, "text")

    def test_no_reference_to_MARKDOWN_TABLE_RE(self):
        """Workaround constant is fully removed from the module."""
        import gateway.platforms.feishu as feishu_mod
        self.assertFalse(hasattr(feishu_mod, "_MARKDOWN_TABLE_RE"),
                         "_MARKDOWN_TABLE_RE must be removed")
