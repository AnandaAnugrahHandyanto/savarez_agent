"""Tests for atomic_roundtrip_yaml_save() — comment-preserving full-state writes.

This helper backs tui_gateway/server.py:_save_cfg(), which used to call
yaml.safe_dump and silently clobber user-edited config files on every
TUI/gateway setting change (e.g. /personality, /reasoning, /details_mode).
"""

import pytest
import yaml


class TestAtomicRoundtripYamlSave:
    @pytest.fixture
    def config_path(self, tmp_path):
        return tmp_path / "config.yaml"

    def test_creates_file_when_missing(self, config_path):
        from utils import atomic_roundtrip_yaml_save

        atomic_roundtrip_yaml_save(config_path, {"model": {"default": "test-model"}})

        assert config_path.exists()
        assert yaml.safe_load(config_path.read_text())["model"]["default"] == "test-model"

    def test_preserves_top_level_key_order(self, config_path):
        """Existing top-level keys keep their author-intended ordering."""
        config_path.write_text(
            "model:\n"
            "  default: claude-opus-4-7\n"
            "providers: {}\n"
            "agent:\n"
            "  max_turns: 90\n"
            "display:\n"
            "  skin: default\n",
            encoding="utf-8",
        )

        from utils import atomic_roundtrip_yaml_save

        # Pass keys in alphabetical order to make sure dict iteration order
        # in the caller doesn't accidentally rewrite the file alphabetically
        # (the old yaml.safe_dump bug).
        atomic_roundtrip_yaml_save(
            config_path,
            {
                "agent": {"max_turns": 100},
                "display": {"skin": "mono"},
                "model": {"default": "claude-opus-4-7"},
                "providers": {},
            },
        )

        text = config_path.read_text(encoding="utf-8")
        top_keys = [
            line.split(":", 1)[0]
            for line in text.splitlines()
            if line and not line.startswith(" ") and not line.startswith("#")
        ]
        # Comments are stripped from `top_keys` above, so the surviving
        # order should match the original file, NOT alphabetical.
        assert top_keys == ["model", "providers", "agent", "display"]

    def test_preserves_comments(self, config_path):
        config_path.write_text(
            "# header comment\n"
            "model:\n"
            "  # inline note\n"
            "  default: claude-opus-4-7\n"
            "display:\n"
            "  skin: default  # trailing note\n",
            encoding="utf-8",
        )

        from utils import atomic_roundtrip_yaml_save

        atomic_roundtrip_yaml_save(
            config_path,
            {
                "model": {"default": "claude-opus-4-7"},
                "display": {"skin": "mono"},
            },
        )

        text = config_path.read_text(encoding="utf-8")
        assert "# header comment" in text
        assert "# inline note" in text
        assert "# trailing note" in text
        assert yaml.safe_load(text)["display"]["skin"] == "mono"

    def test_preserves_readable_unicode(self, config_path):
        """Personalities with kaomoji/Chinese characters stay readable on disk
        instead of getting mangled to \\uXXXX escapes (the headline bug:
        kawaii/catgirl personality emoji turning into \\u30CE\\uFF65)."""
        config_path.write_text(
            "agent:\n"
            "  personalities:\n"
            "    catgirl: \"nya (=^･ω･^=) 你好\"\n"
            "display:\n"
            "  skin: default\n",
            encoding="utf-8",
        )

        from utils import atomic_roundtrip_yaml_save

        atomic_roundtrip_yaml_save(
            config_path,
            {
                "agent": {"personalities": {"catgirl": "nya (=^･ω･^=) 你好"}},
                "display": {"skin": "mono"},
            },
        )

        text = config_path.read_text(encoding="utf-8")
        assert "你好" in text
        assert "(=^･ω･^=)" in text
        assert "\\u4f60" not in text
        assert "\\u30CE" not in text

    def test_appends_new_keys(self, config_path):
        config_path.write_text(
            "model:\n"
            "  default: test-model\n",
            encoding="utf-8",
        )

        from utils import atomic_roundtrip_yaml_save

        atomic_roundtrip_yaml_save(
            config_path,
            {
                "model": {"default": "test-model"},
                "display": {"personality": "noir"},
                "agent": {"system_prompt": "you are noir"},
            },
        )

        result = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert result["model"]["default"] == "test-model"
        assert result["display"]["personality"] == "noir"
        assert result["agent"]["system_prompt"] == "you are noir"

    def test_deletes_keys_missing_from_new_state(self, config_path):
        """Mirrors the cfg.pop()-then-_save_cfg(cfg) pattern in tui_gateway:
        e.g. /prompt clear removes custom_prompt entirely."""
        config_path.write_text(
            "model:\n"
            "  default: test-model\n"
            "custom_prompt: 'old prompt'\n",
            encoding="utf-8",
        )

        from utils import atomic_roundtrip_yaml_save

        atomic_roundtrip_yaml_save(
            config_path,
            {"model": {"default": "test-model"}},
        )

        result = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert "custom_prompt" not in result
        assert result["model"]["default"] == "test-model"

    def test_overwrites_scalar_value(self, config_path):
        config_path.write_text(
            "display:\n"
            "  personality: noir\n",
            encoding="utf-8",
        )

        from utils import atomic_roundtrip_yaml_save

        atomic_roundtrip_yaml_save(
            config_path,
            {"display": {"personality": "kawaii"}},
        )

        result = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert result["display"]["personality"] == "kawaii"

    def test_overwrites_list_wholesale(self, config_path):
        config_path.write_text(
            "toolsets:\n"
            "  - one\n"
            "  - two\n",
            encoding="utf-8",
        )

        from utils import atomic_roundtrip_yaml_save

        atomic_roundtrip_yaml_save(config_path, {"toolsets": ["three"]})

        result = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert result["toolsets"] == ["three"]

    def test_recurses_into_nested_dicts(self, config_path):
        """Deep mutations target the matching subtree, not the whole parent.

        Without this, writing display.personality would drop sibling display.skin.
        """
        config_path.write_text(
            "display:\n"
            "  skin: default\n"
            "  personality: noir\n"
            "  compact: false\n",
            encoding="utf-8",
        )

        from utils import atomic_roundtrip_yaml_save

        atomic_roundtrip_yaml_save(
            config_path,
            {
                "display": {
                    "skin": "default",
                    "personality": "kawaii",
                    "compact": False,
                }
            },
        )

        result = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert result["display"]["skin"] == "default"
        assert result["display"]["personality"] == "kawaii"
        assert result["display"]["compact"] is False
