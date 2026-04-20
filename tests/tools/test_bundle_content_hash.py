"""Tests for bundle_content_hash handling of bytes content."""

from dataclasses import dataclass, field
from typing import Any, Dict, Union

import pytest

from tools.skills_hub import bundle_content_hash, SkillBundle


class TestBundleContentHashBytes:
    """bundle_content_hash must handle both str and bytes values in bundle.files."""

    def test_str_content(self):
        bundle = SkillBundle(
            name="test",
            files={"SKILL.md": "---\nname: test\n---\n# Hello\n"},
            source="test",
            identifier="test/test",
            trust_level="builtin",
        )
        h = bundle_content_hash(bundle)
        assert h.startswith("sha256:")
        assert len(h) == len("sha256:") + 16

    def test_bytes_content(self):
        bundle = SkillBundle(
            name="test",
            files={"icon.png": b"\x89PNG\r\n\x1a\n\x00\x00"},
            source="test",
            identifier="test/test",
            trust_level="builtin",
        )
        # Must not raise AttributeError: 'bytes' object has no attribute 'encode'
        h = bundle_content_hash(bundle)
        assert h.startswith("sha256:")

    def test_mixed_str_and_bytes(self):
        bundle = SkillBundle(
            name="test",
            files={
                "SKILL.md": "# Mixed bundle\n",
                "image.png": b"\x89PNG\r\n",
                "script.py": "print('hello')\n",
            },
            source="test",
            identifier="test/test",
            trust_level="builtin",
        )
        h = bundle_content_hash(bundle)
        assert h.startswith("sha256:")

    def test_deterministic(self):
        files = {"a.md": "hello", "b.bin": b"\x00\x01\x02"}
        b1 = SkillBundle(name="t", files=files, source="s", identifier="s/t", trust_level="b")
        b2 = SkillBundle(name="t", files=files, source="s", identifier="s/t", trust_level="b")
        assert bundle_content_hash(b1) == bundle_content_hash(b2)
