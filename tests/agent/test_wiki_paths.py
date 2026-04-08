from pathlib import Path
from unittest.mock import patch

from agent import wiki_paths


class TestResolveObsidianVaultPath:
    def test_prefers_env_var(self):
        with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": "/tmp/vault"}, clear=False):
            path = wiki_paths.resolve_obsidian_vault_path({"knowledge": {"vault_path": "/tmp/other"}})
            assert path == Path("/tmp/vault")

    def test_uses_config_when_env_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            path = wiki_paths.resolve_obsidian_vault_path({"knowledge": {"vault_path": "~/Vault"}})
            assert path == Path.home() / "Vault"


class TestResolveLlmWikiPath:
    def test_prefers_explicit_env_var(self):
        with patch.dict("os.environ", {"LLM_WIKI_PATH": "/tmp/wiki"}, clear=False):
            path = wiki_paths.resolve_llm_wiki_path({"knowledge": {"wiki_path": "/tmp/other"}})
            assert path == Path("/tmp/wiki")

    def test_uses_config_when_set(self):
        with patch.dict("os.environ", {}, clear=True):
            path = wiki_paths.resolve_llm_wiki_path({"knowledge": {"wiki_path": "~/Wiki"}})
            assert path == Path.home() / "Wiki"

    def test_defaults_inside_obsidian_vault_when_no_explicit_path(self):
        legacy_root = Path("/tmp/nonexistent-hermes-kb-for-test")
        with patch.dict("os.environ", {}, clear=True):
            with patch.object(wiki_paths, "LEGACY_WIKI_ROOT", legacy_root):
                path = wiki_paths.resolve_llm_wiki_path(
                    {"knowledge": {"vault_path": "~/Vault", "agent_prefix": "Hermes"}}
                )
                assert path == Path.home() / "Vault" / "Hermes" / "Wiki"

    def test_prefers_existing_legacy_root(self, tmp_path, monkeypatch):
        legacy_root = tmp_path / "legacy-kb"
        legacy_root.mkdir()
        monkeypatch.setattr(wiki_paths, "LEGACY_WIKI_ROOT", legacy_root)

        with patch.dict("os.environ", {}, clear=True):
            path = wiki_paths.resolve_llm_wiki_path(
                {"knowledge": {"vault_path": "~/Vault", "agent_prefix": "Hermes"}}
            )
            assert path == legacy_root
