"""Tests for GitHubSource repo-root plugin discovery (.claude-plugin support)."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from tools.skills_hub import GitHubAuth, GitHubSource, SkillBundle


# ---------------------------------------------------------------------------
# _fetch_marketplace_json
# ---------------------------------------------------------------------------


@patch("tools.skills_hub._write_index_cache", new=lambda *a, **kw: None)
@patch("tools.skills_hub._read_index_cache", return_value=None)
class TestFetchMarketplaceJson:
    def _source(self):
        auth = MagicMock(spec=GitHubAuth)
        auth.get_headers.return_value = {}
        return GitHubSource(auth=auth)

    @patch.object(GitHubSource, "_fetch_file_content")
    def test_returns_plugins_list_from_valid_marketplace_json(self, mock_fetch, _cache):
        mock_fetch.return_value = json.dumps({
            "name": "test-marketplace",
            "plugins": [
                {"name": "plugin-a", "source": "./plugins/a", "description": "Plugin A"},
                {"name": "plugin-b", "source": "./plugins/b", "description": "Plugin B"},
            ],
        })
        src = self._source()
        plugins = src._fetch_marketplace_json("owner/repo")
        assert len(plugins) == 2
        assert plugins[0]["name"] == "plugin-a"
        mock_fetch.assert_called_once_with("owner/repo", ".claude-plugin/marketplace.json")

    @patch.object(GitHubSource, "_fetch_file_content")
    def test_returns_empty_list_when_file_missing(self, mock_fetch, _cache):
        mock_fetch.return_value = None
        src = self._source()
        assert src._fetch_marketplace_json("owner/repo") == []

    @patch.object(GitHubSource, "_fetch_file_content")
    def test_returns_empty_list_on_invalid_json(self, mock_fetch, _cache):
        mock_fetch.return_value = "not json {{"
        src = self._source()
        assert src._fetch_marketplace_json("owner/repo") == []

    @patch.object(GitHubSource, "_fetch_file_content")
    def test_returns_empty_list_when_no_plugins_key(self, mock_fetch, _cache):
        mock_fetch.return_value = json.dumps({"name": "test"})
        src = self._source()
        assert src._fetch_marketplace_json("owner/repo") == []


# ---------------------------------------------------------------------------
# _resolve_plugin_source
# ---------------------------------------------------------------------------


class TestResolvePluginSource:
    def _source(self):
        auth = MagicMock(spec=GitHubAuth)
        auth.get_headers.return_value = {}
        return GitHubSource(auth=auth)

    def test_string_relative_path_dot_slash(self):
        src = self._source()
        repo, path = src._resolve_plugin_source("./plugins/formatter", "owner/repo")
        assert repo == "owner/repo"
        assert path == "plugins/formatter"

    def test_string_relative_path_just_dot(self):
        src = self._source()
        repo, path = src._resolve_plugin_source("./", "owner/repo")
        assert repo == "owner/repo"
        assert path == ""

    def test_github_object_source(self):
        src = self._source()
        source = {"source": "github", "repo": "company/plugin"}
        repo, path = src._resolve_plugin_source(source, "owner/repo")
        assert repo == "company/plugin"
        assert path == ""

    def test_url_object_source_github_https(self):
        src = self._source()
        source = {"source": "url", "url": "https://github.com/obra/superpowers.git"}
        repo, path = src._resolve_plugin_source(source, "owner/repo")
        assert repo == "obra/superpowers"
        assert path == ""

    def test_url_object_source_github_no_git_suffix(self):
        src = self._source()
        source = {"source": "url", "url": "https://github.com/obra/superpowers"}
        repo, path = src._resolve_plugin_source(source, "owner/repo")
        assert repo == "obra/superpowers"
        assert path == ""

    def test_git_subdir_object_source(self):
        src = self._source()
        source = {
            "source": "git-subdir",
            "url": "https://github.com/acme/monorepo.git",
            "path": "tools/plugin",
        }
        repo, path = src._resolve_plugin_source(source, "owner/repo")
        assert repo == "acme/monorepo"
        assert path == "tools/plugin"

    def test_npm_source_returns_none(self):
        src = self._source()
        source = {"source": "npm", "package": "@acme/plugin"}
        result = src._resolve_plugin_source(source, "owner/repo")
        assert result is None

    def test_url_non_github_returns_none(self):
        src = self._source()
        source = {"source": "url", "url": "https://gitlab.com/team/plugin.git"}
        result = src._resolve_plugin_source(source, "owner/repo")
        assert result is None

    def test_unknown_object_source_returns_none(self):
        src = self._source()
        source = {"source": "unknown", "foo": "bar"}
        result = src._resolve_plugin_source(source, "owner/repo")
        assert result is None


# ---------------------------------------------------------------------------
# _select_plugins — name_hint auto-select
# ---------------------------------------------------------------------------


class TestSelectPluginNameHint:
    def _source(self):
        auth = MagicMock(spec=GitHubAuth)
        auth.get_headers.return_value = {}
        return GitHubSource(auth=auth)

    def test_auto_selects_by_name_hint(self):
        src = self._source()
        plugins = [
            {"name": "alpha", "description": "A"},
            {"name": "beta", "description": "B"},
        ]
        selected = src._select_plugins(plugins, name_hint="beta")
        assert len(selected) == 1
        assert selected[0]["name"] == "beta"

    def test_falls_through_to_prompt_when_hint_not_found(self):
        src = self._source()
        plugins = [
            {"name": "alpha", "description": "A"},
            {"name": "beta", "description": "B"},
        ]
        with patch("builtins.input", side_effect=EOFError):
            selected = src._select_plugins(plugins, name_hint="nonexistent")
        assert selected == []

    def test_no_hint_single_plugin_auto_selects(self):
        src = self._source()
        plugins = [{"name": "only", "description": "Only one"}]
        selected = src._select_plugins(plugins)
        assert len(selected) == 1
        assert selected[0]["name"] == "only"

    def test_multi_select_comma_separated(self):
        src = self._source()
        plugins = [
            {"name": "alpha", "description": "A"},
            {"name": "beta", "description": "B"},
            {"name": "gamma", "description": "C"},
        ]
        with patch("builtins.input", return_value="1,3"):
            selected = src._select_plugins(plugins)
        assert len(selected) == 2
        assert selected[0]["name"] == "alpha"
        assert selected[1]["name"] == "gamma"

    def test_multi_select_all(self):
        src = self._source()
        plugins = [
            {"name": "alpha", "description": "A"},
            {"name": "beta", "description": "B"},
        ]
        with patch("builtins.input", return_value="all"):
            selected = src._select_plugins(plugins)
        assert len(selected) == 2


class TestFetchPluginFromMarketplaceMetadata:
    def _source(self):
        auth = MagicMock(spec=GitHubAuth)
        auth.get_headers.return_value = {}
        return GitHubSource(auth=auth)

    @patch.object(GitHubSource, "_download_directory")
    def test_stores_marketplace_plugin_in_metadata(self, mock_download):
        mock_download.return_value = {
            "skills/foo/SKILL.md": "---\nname: foo\n---\n",
        }
        src = self._source()
        plugin = {"name": "my-plugin", "source": "./"}
        bundle = src._fetch_plugin_from_marketplace(plugin, "owner/repo", 0)
        assert bundle is not None
        assert bundle.metadata.get("marketplace_plugin") == "my-plugin"

    @patch.object(GitHubSource, "_download_directory")
    def test_downloads_only_declared_skill_paths(self, mock_download):
        """When plugin has a 'skills' list, only those directories are fetched."""
        mock_download.side_effect = lambda repo, path: {
            "SKILL.md": f"---\nname: {path.split('/')[-1]}\n---\n",
            "helper.py": "# helper",
        } if path else {}

        src = self._source()
        plugin = {
            "name": "doc-skills",
            "source": "./",
            "skills": ["./skills/xlsx", "./skills/pdf"],
        }
        bundle = src._fetch_plugin_from_marketplace(plugin, "owner/repo", 0)
        assert bundle is not None
        assert bundle.name == "doc-skills"
        # Should have called _download_directory for each skill path, not repo root
        assert mock_download.call_count == 2
        calls = [c.args for c in mock_download.call_args_list]
        assert ("owner/repo", "skills/xlsx") in calls
        assert ("owner/repo", "skills/pdf") in calls
        # Files should be namespaced under skill path
        assert "skills/xlsx/SKILL.md" in bundle.files
        assert "skills/pdf/SKILL.md" in bundle.files

    @patch.object(GitHubSource, "_download_directory")
    def test_falls_back_to_full_download_without_skills_list(self, mock_download):
        """Without a 'skills' list, downloads the full source path."""
        mock_download.return_value = {"SKILL.md": "---\nname: test\n---\n"}
        src = self._source()
        plugin = {"name": "full-plugin", "source": "./"}
        bundle = src._fetch_plugin_from_marketplace(plugin, "owner/repo", 0)
        assert bundle is not None
        mock_download.assert_called_once_with("owner/repo", "")


# ---------------------------------------------------------------------------
# _download_directory_via_tree — empty path (repo root)
# ---------------------------------------------------------------------------


class TestDownloadDirectoryEmptyPath:
    def _source(self):
        auth = MagicMock(spec=GitHubAuth)
        auth.get_headers.return_value = {}
        return GitHubSource(auth=auth)

    @patch.object(GitHubSource, "_fetch_file_content")
    @patch("tools.skills_hub.httpx.get")
    def test_tree_api_handles_empty_path_for_repo_root(self, mock_get, mock_fetch_file):
        """When path is empty, all blobs in the tree should be included."""
        repo_resp = MagicMock()
        repo_resp.status_code = 200
        repo_resp.json.return_value = {"default_branch": "main"}

        tree_resp = MagicMock()
        tree_resp.status_code = 200
        tree_resp.json.return_value = {
            "truncated": False,
            "tree": [
                {"type": "blob", "path": "SKILL.md"},
                {"type": "blob", "path": "skills/foo/SKILL.md"},
                {"type": "tree", "path": "skills/foo"},
            ],
        }
        mock_get.side_effect = [repo_resp, tree_resp]
        mock_fetch_file.side_effect = lambda repo, path: f"content of {path}"

        src = self._source()
        files = src._download_directory_via_tree("owner/repo", "")
        assert files is not None
        assert "SKILL.md" in files
        assert "skills/foo/SKILL.md" in files


# ---------------------------------------------------------------------------
# _resolve_repo_root
# ---------------------------------------------------------------------------


class TestResolveRepoRoot:
    def _source(self):
        auth = MagicMock(spec=GitHubAuth)
        auth.get_headers.return_value = {}
        return GitHubSource(auth=auth)

    @patch.object(GitHubSource, "_download_directory")
    @patch.object(GitHubSource, "_fetch_marketplace_json")
    def test_follows_marketplace_json_single_plugin_string_source(
        self, mock_marketplace, mock_download
    ):
        mock_marketplace.return_value = [
            {"name": "my-plugin", "source": "./", "description": "A plugin"},
        ]
        mock_download.return_value = {
            "skills/foo/SKILL.md": "---\nname: foo\n---\n",
            "plugin.json": "{}",
        }
        src = self._source()
        bundle = src._resolve_repo_root("owner/repo")
        assert bundle is not None
        assert bundle.name == "my-plugin"

    @patch.object(GitHubSource, "_download_directory")
    @patch.object(GitHubSource, "_fetch_marketplace_json")
    def test_follows_marketplace_json_github_object_source(
        self, mock_marketplace, mock_download
    ):
        mock_marketplace.return_value = [
            {
                "name": "ext-plugin",
                "source": {"source": "github", "repo": "other/repo"},
                "description": "External",
            },
        ]
        mock_download.return_value = {
            "skills/bar/SKILL.md": "---\nname: bar\n---\n",
        }
        src = self._source()
        bundle = src._resolve_repo_root("owner/repo")
        assert bundle is not None
        assert bundle.name == "ext-plugin"
        mock_download.assert_called_with("other/repo", "")

    @patch.object(GitHubSource, "_download_directory")
    @patch.object(GitHubSource, "_fetch_marketplace_json")
    def test_falls_back_to_repo_root_when_no_marketplace_json(
        self, mock_marketplace, mock_download
    ):
        mock_marketplace.return_value = []
        mock_download.return_value = {
            "skills/baz/SKILL.md": "---\nname: baz\n---\n",
            "commands/cmd.md": "# cmd",
        }
        src = self._source()
        bundle = src._resolve_repo_root("owner/repo")
        assert bundle is not None
        assert bundle.name == "repo"
        mock_download.assert_called_with("owner/repo", "")

    @patch.object(GitHubSource, "_download_directory")
    @patch.object(GitHubSource, "_fetch_marketplace_json")
    def test_returns_none_when_repo_root_download_empty(
        self, mock_marketplace, mock_download
    ):
        mock_marketplace.return_value = []
        mock_download.return_value = {}
        src = self._source()
        bundle = src._resolve_repo_root("owner/repo")
        assert bundle is None

    @patch.object(GitHubSource, "_download_directory")
    @patch.object(GitHubSource, "_fetch_marketplace_json")
    def test_depth_1_does_not_follow_marketplace_json(
        self, mock_marketplace, mock_download
    ):
        mock_download.return_value = {"skills/x/SKILL.md": "---\nname: x\n---\n"}
        src = self._source()
        bundle = src._resolve_repo_root("other/repo", _depth=1)
        assert bundle is not None
        assert bundle.name == "repo"
        mock_marketplace.assert_not_called()


# ---------------------------------------------------------------------------
# fetch() / inspect() — 2-part identifier
# ---------------------------------------------------------------------------


class TestFetchTwoPartIdentifier:
    def _source(self):
        auth = MagicMock(spec=GitHubAuth)
        auth.get_headers.return_value = {}
        return GitHubSource(auth=auth)

    @patch.object(GitHubSource, "_resolve_repo_root")
    def test_fetch_delegates_two_part_to_resolve_repo_root(self, mock_resolve):
        mock_resolve.return_value = SkillBundle(
            name="superpowers",
            files={"SKILL.md": "# test"},
            source="github",
            identifier="obra/superpowers",
            trust_level="community",
        )
        src = self._source()
        bundle = src.fetch("obra/superpowers")
        assert bundle is not None
        assert bundle.name == "superpowers"
        mock_resolve.assert_called_once_with("obra/superpowers", plugin_name=None)

    @patch.object(GitHubSource, "_download_directory")
    def test_fetch_three_part_still_works(self, mock_download):
        mock_download.return_value = {"SKILL.md": "---\nname: test\n---\n"}
        src = self._source()
        bundle = src.fetch("owner/repo/skills/test")
        assert bundle is not None
        assert bundle.name == "test"


class TestInspectTwoPartIdentifier:
    def _source(self):
        auth = MagicMock(spec=GitHubAuth)
        auth.get_headers.return_value = {}
        return GitHubSource(auth=auth)

    @patch.object(GitHubSource, "_fetch_marketplace_json")
    @patch.object(GitHubSource, "_fetch_file_content")
    def test_inspect_two_part_returns_meta_from_marketplace_json(
        self, mock_fetch_file, mock_marketplace
    ):
        mock_fetch_file.return_value = None
        mock_marketplace.return_value = [
            {"name": "superpowers", "source": "./", "description": "Core skills"},
        ]
        src = self._source()
        meta = src.inspect("obra/superpowers")
        assert meta is not None
        assert meta.name == "superpowers"
        assert meta.description == "Core skills"

    @patch.object(GitHubSource, "_fetch_file_content")
    def test_inspect_three_part_still_works(self, mock_fetch_file):
        mock_fetch_file.return_value = "---\nname: test\ndescription: Test\n---\n"
        src = self._source()
        meta = src.inspect("owner/repo/skills/test")
        assert meta is not None
        assert meta.name == "test"


# ---------------------------------------------------------------------------
# End-to-end integration
# ---------------------------------------------------------------------------


@patch("tools.skills_hub._write_index_cache", new=lambda *a, **kw: None)
@patch("tools.skills_hub._read_index_cache", return_value=None)
class TestEndToEndRepoRootInstall:

    def _source(self):
        auth = MagicMock(spec=GitHubAuth)
        auth.get_headers.return_value = {}
        return GitHubSource(auth=auth)

    @patch.object(GitHubSource, "_download_directory")
    @patch.object(GitHubSource, "_fetch_file_content")
    def test_full_flow_marketplace_json_with_relative_source(
        self, mock_fetch_file, mock_download, _cache
    ):
        marketplace_json = json.dumps({
            "name": "superpowers-dev",
            "plugins": [
                {
                    "name": "superpowers",
                    "source": "./",
                    "description": "Core skills library",
                    "version": "5.0.7",
                },
            ],
        })

        def fetch_file_side_effect(repo, path):
            if path == "SKILL.md":
                return None
            if path == ".claude-plugin/marketplace.json":
                return marketplace_json
            return None

        mock_fetch_file.side_effect = fetch_file_side_effect
        mock_download.return_value = {
            "skills/brainstorming/SKILL.md": "---\nname: brainstorming\n---\n",
            "skills/debugging/SKILL.md": "---\nname: debugging\n---\n",
            ".claude-plugin/plugin.json": '{"name": "superpowers"}',
        }

        src = self._source()
        bundle = src.fetch("obra/superpowers")
        assert bundle is not None
        assert bundle.name == "superpowers"
        assert bundle.source == "github"
        assert "skills/brainstorming/SKILL.md" in bundle.files

    @patch.object(GitHubSource, "_download_directory")
    @patch.object(GitHubSource, "_fetch_file_content")
    def test_full_flow_marketplace_json_with_github_object_source(
        self, mock_fetch_file, mock_download, _cache
    ):
        marketplace_json = json.dumps({
            "name": "my-marketplace",
            "plugins": [
                {
                    "name": "ext-tool",
                    "source": {"source": "github", "repo": "other/tool"},
                    "description": "External tool",
                },
            ],
        })

        def fetch_file_side_effect(repo, path):
            if repo == "owner/marketplace" and path == "SKILL.md":
                return None
            if repo == "owner/marketplace" and path == ".claude-plugin/marketplace.json":
                return marketplace_json
            if repo == "other/tool" and path == "SKILL.md":
                return None
            return None

        mock_fetch_file.side_effect = fetch_file_side_effect
        mock_download.return_value = {
            "skills/tool/SKILL.md": "---\nname: tool\n---\n",
        }

        src = self._source()
        bundle = src.fetch("owner/marketplace")
        assert bundle is not None
        assert bundle.name == "ext-tool"

    @patch.object(GitHubSource, "_download_directory")
    @patch.object(GitHubSource, "_fetch_file_content")
    def test_full_flow_marketplace_json_with_url_object_source(
        self, mock_fetch_file, mock_download, _cache
    ):
        marketplace_json = json.dumps({
            "name": "my-marketplace",
            "plugins": [
                {
                    "name": "url-plugin",
                    "source": {
                        "source": "url",
                        "url": "https://github.com/obra/superpowers.git",
                    },
                    "description": "URL-sourced plugin",
                },
            ],
        })

        def fetch_file_side_effect(repo, path):
            if repo == "owner/repo" and path == "SKILL.md":
                return None
            if repo == "owner/repo" and path == ".claude-plugin/marketplace.json":
                return marketplace_json
            if repo == "obra/superpowers" and path == "SKILL.md":
                return None
            return None

        mock_fetch_file.side_effect = fetch_file_side_effect
        mock_download.return_value = {
            "skills/tdd/SKILL.md": "---\nname: tdd\n---\n",
        }

        src = self._source()
        bundle = src.fetch("owner/repo")
        assert bundle is not None
        assert bundle.name == "url-plugin"
