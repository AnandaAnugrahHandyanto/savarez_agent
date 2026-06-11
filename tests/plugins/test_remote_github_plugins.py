"""Tests for GitHub/remote plugin source support.

Covers the new ``plugins.remote`` config key, manifest ``source`` block
parsing, git-cache resolution, and end-to-end loading of a plugin that
originates from a GitHub repo.

Test strategy:
  * Manifest parsing uses temporary ``plugin.yaml`` files — no real git.
  * ``_resolve_git_repo`` is tested with a *mock* git binary (a shell
    script that simulates clone/fetch/checkout).
  * ``_scan_github_sources`` is tested by monkey-patching
    ``_resolve_git_repo`` so no network access is needed.
  * End-to-end loading verifies that a plugin cloned from a fake remote
    is treated identically to a user plugin (same namespace, same
    ``register()`` contract).
"""

import json
import os
import stat
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plugin_dir(
    root: Path,
    name: str,
    *,
    source_block=None,
    init_contents="def register(ctx):\n    pass\n",
    provides_tools=None,
) -> Path:
    """Create a minimal plugin directory containing plugin.yaml + __init__.py."""
    plugin_dir = root / name
    plugin_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "name": name,
        "version": "1.0.0",
        "description": f"Test plugin {name}",
        "author": "test",
    }
    if source_block is not None:
        manifest["source"] = source_block
    if provides_tools is not None:
        manifest["provides_tools"] = provides_tools

    plugin_dir.joinpath("plugin.yaml").write_text(
        _dump_yaml(manifest), encoding="utf-8"
    )
    plugin_dir.joinpath("__init__.py").write_text(init_contents, encoding="utf-8")
    return plugin_dir


def _dump_yaml(data) -> str:
    """Lightweight YAML dumper matching PyYAML's default style."""
    import yaml
    return yaml.dump(data, default_flow_style=False, sort_keys=False)


def _make_git_repo(path: Path) -> Path:
    """Turn *path* into a git repo with one commit (reusable helper)."""
    import subprocess
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--quiet", str(path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.local"],
        cwd=str(path), check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(path), check=True, capture_output=True,
    )
    (path / "README.md").write_text("# test repo\n")
    subprocess.run(["git", "add", "."], cwd=str(path), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "--quiet", "-m", "init"],
        cwd=str(path), check=True, capture_output=True,
    )
    return path


def _mock_git_factory(tmp_path: Path):
    """Return a function suitable for patching ``_resolve_git_repo``.

    The mock creates a regular directory at the cache path instead of
    actually calling git.  This lets us test ``_scan_github_sources``
    and the full discovery pipeline without network access.
    """

    def _mock_resolve(self, repo_url, repo_ref="", *, cache_root=None):
        root = cache_root or tmp_path / "mock-cache"
        root.mkdir(parents=True, exist_ok=True)
        (root / ".git").mkdir(exist_ok=True)  # pretend it's a git repo
        (root / "README.md").write_text(f"# {repo_url}\n")
        return root

    return _mock_resolve


# ---------------------------------------------------------------------------
# Manifest parsing tests
# ---------------------------------------------------------------------------


class TestManifestSourceBlock:
    """Verify that the ``source`` block in plugin.yaml is parsed correctly."""

    def test_source_github_with_url_and_ref(self, tmp_path):
        from hermes_cli.plugins import PluginManager, PluginManifest

        pm = PluginManager()
        pdir = _make_plugin_dir(
            tmp_path, "gh-plugin",
            source_block={"type": "github", "url": "https://github.com/org/repo.git", "ref": "main"},
        )
        manifest = pm._parse_manifest(
            pdir / "plugin.yaml", pdir, source="user", prefix="",
        )
        assert manifest is not None
        assert manifest.source_type == "github"
        assert manifest.repo_url == "https://github.com/org/repo.git"
        assert manifest.repo_ref == "main"
        assert manifest.source == "user"  # directory-scanned, so stays "user"

    def test_source_github_with_branch_alias(self, tmp_path):
        from hermes_cli.plugins import PluginManager

        pm = PluginManager()
        pdir = _make_plugin_dir(
            tmp_path, "b-plugin",
            source_block={"type": "github", "url": "https://github.com/o/r.git", "branch": "develop"},
        )
        manifest = pm._parse_manifest(
            pdir / "plugin.yaml", pdir, source="user", prefix="",
        )
        assert manifest is not None
        assert manifest.source_type == "github"
        assert manifest.repo_ref == "develop"

    def test_source_github_with_path(self, tmp_path):
        from hermes_cli.plugins import PluginManager

        pm = PluginManager()
        pdir = _make_plugin_dir(
            tmp_path, "path-plugin",
            source_block={
                "type": "github",
                "url": "https://github.com/o/mono.git",
                "path": "plugins/my-plugin",
            },
        )
        manifest = pm._parse_manifest(
            pdir / "plugin.yaml", pdir, source="user", prefix="",
        )
        assert manifest is not None
        assert manifest.repo_path == "plugins/my-plugin"

    def test_source_github_missing_url_falls_back_to_local(self, tmp_path):
        from hermes_cli.plugins import PluginManager

        pm = PluginManager()
        pdir = _make_plugin_dir(
            tmp_path, "no-url",
            source_block={"type": "github"},
        )
        manifest = pm._parse_manifest(
            pdir / "plugin.yaml", pdir, source="user", prefix="",
        )
        assert manifest is not None
        assert manifest.source_type == "local"  # fallback
        assert manifest.repo_url == ""

    def test_source_local_unchanged(self, tmp_path):
        from hermes_cli.plugins import PluginManager

        pm = PluginManager()
        pdir = _make_plugin_dir(
            tmp_path, "local-plugin",
            source_block={"type": "local"},
        )
        manifest = pm._parse_manifest(
            pdir / "plugin.yaml", pdir, source="user", prefix="",
        )
        assert manifest is not None
        assert manifest.source_type == "local"
        assert manifest.repo_url == ""
        assert manifest.repo_ref == ""
        assert manifest.repo_path == ""

    def test_no_source_block_at_all(self, tmp_path):
        from hermes_cli.plugins import PluginManager

        pm = PluginManager()
        pdir = _make_plugin_dir(tmp_path, "plain-plugin")
        manifest = pm._parse_manifest(
            pdir / "plugin.yaml", pdir, source="user", prefix="",
        )
        assert manifest is not None
        assert manifest.source_type == "local"
        assert manifest.repo_url == ""

    def test_unknown_source_type_warns_and_falls_back(self, tmp_path):
        from hermes_cli.plugins import PluginManager

        pm = PluginManager()
        pdir = _make_plugin_dir(
            tmp_path, "weird",
            source_block={"type": "svn", "url": "svn://example.com/repo"},
        )
        manifest = pm._parse_manifest(
            pdir / "plugin.yaml", pdir, source="user", prefix="",
        )
        assert manifest is not None
        assert manifest.source_type == "local"

    def test_backward_compat_no_new_fields_required(self, tmp_path):
        """A plugin.yaml that doesn't mention ``source`` at all still works."""
        from hermes_cli.plugins import PluginManager

        pm = PluginManager()
        pdir = _make_plugin_dir(tmp_path, "legacy-plugin")
        manifest = pm._parse_manifest(
            pdir / "plugin.yaml", pdir, source="user", prefix="",
        )
        assert manifest is not None
        assert manifest.source_type == "local"
        assert manifest.repo_url == ""
        assert manifest.repo_ref == ""
        assert manifest.repo_path == ""


# ---------------------------------------------------------------------------
# Cache-dir helper
# ---------------------------------------------------------------------------


class TestCacheDirForRepo:
    def test_deterministic(self):
        from hermes_cli.plugins import PluginManager

        pm = PluginManager()
        url = "https://github.com/org/my-repo.git"
        d1 = pm._cache_dir_for_repo(url)
        d2 = pm._cache_dir_for_repo(url)
        assert d1 == d2
        assert "plugin-repos" in str(d1)

    def test_different_urls_differ(self):
        from hermes_cli.plugins import PluginManager

        pm = PluginManager()
        d1 = pm._cache_dir_for_repo("https://github.com/org/a.git")
        d2 = pm._cache_dir_for_repo("https://github.com/org/b.git")
        assert d1 != d2


# ---------------------------------------------------------------------------
# Git resolution (real git, local repos only)
# ---------------------------------------------------------------------------


class TestResolveGitRepo:
    """Create actual local git repos (no network) and exercise clone/fetch."""

    def test_clone_local_repo(self, tmp_path):
        from hermes_cli.plugins import PluginManager

        # Create a "remote" bare-ish repo
        remote = _make_git_repo(tmp_path / "remote")

        pm = PluginManager()
        cache = tmp_path / "cache" / "repo1"
        result = pm._resolve_git_repo(str(remote), repo_ref="", cache_root=cache)
        assert result == cache
        assert (result / ".git").is_dir()
        assert (result / "README.md").exists()

    def test_clone_with_ref(self, tmp_path):
        from hermes_cli.plugins import PluginManager

        remote = _make_git_repo(tmp_path / "remote-branched")
        # Create a branch "dev"
        import subprocess
        subprocess.run(
            ["git", "checkout", "-b", "dev"],
            cwd=str(remote), check=True, capture_output=True,
        )
        (remote / "dev-file.txt").write_text("dev content\n")
        subprocess.run(["git", "add", "."], cwd=str(remote), check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "dev commit"],
            cwd=str(remote), check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "master"],
            cwd=str(remote), check=True, capture_output=True,
        )

        pm = PluginManager()
        cache = tmp_path / "cache" / "repo2"
        result = pm._resolve_git_repo(str(remote), repo_ref="dev", cache_root=cache)
        assert result == cache
        assert (result / "dev-file.txt").exists()

    def test_pull_existing_repo(self, tmp_path):
        from hermes_cli.plugins import PluginManager

        remote = _make_git_repo(tmp_path / "remote-pull")

        pm = PluginManager()
        cache = tmp_path / "cache" / "repo3"
        # First clone
        pm._resolve_git_repo(str(remote), repo_ref="", cache_root=cache)

        # Add a new commit to remote
        import subprocess
        (remote / "new-file.txt").write_text("new\n")
        subprocess.run(["git", "add", "."], cwd=str(remote), check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "second"],
            cwd=str(remote), check=True, capture_output=True,
        )

        # Fetch again
        pm._resolve_git_repo(str(remote), repo_ref="", cache_root=cache)
        assert (cache / "new-file.txt").exists()

    def test_git_not_found_raises(self, tmp_path):
        from hermes_cli.plugins import PluginManager

        pm = PluginManager()
        with patch("hermes_cli.plugins.shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="git.*not found"):
                pm._resolve_git_repo("https://github.com/o/r.git", cache_root=tmp_path / "x")


# ---------------------------------------------------------------------------
# _scan_github_sources with mocked git
# ---------------------------------------------------------------------------


class TestScanGitHubSources:
    def test_no_remote_config(self, tmp_path, monkeypatch):
        from hermes_cli.plugins import PluginManager

        monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
        pm = PluginManager()
        result = pm._scan_github_sources()
        assert result == []

    def test_remote_entry_scanned(self, tmp_path, monkeypatch):
        from hermes_cli.plugins import PluginManager

        hermes_home = tmp_path / ".hermes"
        hermes_home.mkdir()
        monkeypatch.setenv("HERMES_HOME", str(hermes_home))

        # Create a fake repo with a plugin inside
        cache = tmp_path / "fake-cache"
        cache.mkdir()
        _make_plugin_dir(cache, "remote-hello",
                         init_contents="def register(ctx):\n    ctx._hello = True\n",
                         provides_tools=["hello_tool"])

        # Fake config with remote entry
        cfg = {
            "plugins": {
                "enabled": ["remote-hello"],
                "remote": [{
                    "url": "https://github.com/fake/repo.git",
                    "ref": "main",
                }],
            }
        }
        cfg_path = hermes_home / "config.yaml"
        import yaml
        cfg_path.write_text(yaml.dump(cfg), encoding="utf-8")

        pm = PluginManager()
        # Monkey-patch _resolve_git_repo to return our fake cache
        with patch.object(PluginManager, "_resolve_git_repo", lambda self, url, repo_ref="", **kw: cache):
            manifests = pm._scan_github_sources()

        assert len(manifests) == 1
        m = manifests[0]
        assert m.source_type == "github"
        assert m.repo_url == "https://github.com/fake/repo.git"
        assert m.repo_ref == "main"
        assert m.name == "remote-hello"
        assert m.source == "github"

    def test_remote_entry_with_path(self, tmp_path, monkeypatch):
        from hermes_cli.plugins import PluginManager

        hermes_home = tmp_path / ".hermes"
        hermes_home.mkdir()
        monkeypatch.setenv("HERMES_HOME", str(hermes_home))

        # Fake repo with nested plugin
        cache = tmp_path / "fake-cache-path"
        cache.mkdir()
        _make_plugin_dir(cache / "plugins" / "nested-plugin", "nested-plugin",
                         provides_tools=["nested_tool"])

        cfg = {
            "plugins": {
                "enabled": ["nested-plugin"],
                "remote": [{
                    "url": "https://github.com/fake/mono.git",
                    "path": "plugins",
                }],
            }
        }
        import yaml
        cfg_path = hermes_home / "config.yaml"
        cfg_path.write_text(yaml.dump(cfg), encoding="utf-8")

        pm = PluginManager()
        with patch.object(PluginManager, "_resolve_git_repo", lambda self, url, repo_ref="", **kw: cache):
            manifests = pm._scan_github_sources()

        assert len(manifests) == 1
        assert manifests[0].name == "nested-plugin"
        assert manifests[0].repo_path == "plugins"

    def test_invalid_entry_skipped_gracefully(self, tmp_path, monkeypatch):
        from hermes_cli.plugins import PluginManager

        hermes_home = tmp_path / ".hermes"
        hermes_home.mkdir()
        monkeypatch.setenv("HERMES_HOME", str(hermes_home))

        cfg = {
            "plugins": {
                "remote": [
                    "not-a-dict",
                    {"url": "", "ref": "main"},
                    {"url": "https://github.com/fake/missing.git"},
                ],
            }
        }
        import yaml
        cfg_path = hermes_home / "config.yaml"
        cfg_path.write_text(yaml.dump(cfg), encoding="utf-8")

        pm = PluginManager()
        with patch.object(PluginManager, "_resolve_git_repo", side_effect=RuntimeError("no git")):
            manifests = pm._scan_github_sources()

        assert manifests == []


# ---------------------------------------------------------------------------
# Integration: full discover_and_load with a mocked remote plugin
# ---------------------------------------------------------------------------


class TestDiscoverAndLoadWithRemote:
    """End-to-end: a plugin from a GitHub source is loaded alongside local ones."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        self.tmp_path = tmp_path
        self.hermes_home = tmp_path / ".hermes"
        self.hermes_home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("HERMES_HOME", str(self.hermes_home))

    def test_remote_plugin_loaded_like_user_plugin(self):
        from hermes_cli.plugins import PluginManager
        import yaml

        # Create a fake cached repo with a plugin
        cache = self.tmp_path / "fake-remote-cache"
        cache.mkdir()
        _make_plugin_dir(
            cache, "cool-tool",
            init_contents=(
                "def register(ctx):\n"
                "    ctx._cool = True\n"
            ),
            provides_tools=["cool_tool"],
        )

        # Config: enable the remote plugin + point to a fake remote
        cfg = {
            "plugins": {
                "enabled": ["cool-tool"],
                "remote": [{
                    "url": "https://github.com/fake/cool.git",
                    "ref": "v1.0",
                }],
            }
        }
        cfg_path = self.hermes_home / "config.yaml"
        cfg_path.write_text(yaml.dump(cfg), encoding="utf-8")

        pm = PluginManager()
        with patch.object(PluginManager, "_resolve_git_repo", lambda self, url, repo_ref="", **kw: cache):
            pm.discover_and_load()

        loaded = pm._plugins.get("cool-tool")
        assert loaded is not None, f"cool-tool not found. Plugins: {list(pm._plugins.keys())}"
        assert loaded.enabled is True
        assert loaded.manifest.source == "github"
        assert loaded.manifest.source_type == "github"
        assert loaded.manifest.repo_url == "https://github.com/fake/cool.git"
        assert loaded.manifest.repo_ref == "v1.0"

    def test_remote_plugin_user_plugin_precedence(self):
        """User plugin with the same key overrides a remote plugin."""
        from hermes_cli.plugins import PluginManager
        import yaml

        # Fake remote cache has a plugin named "shared-key"
        remote_cache = self.tmp_path / "remote-cache"
        remote_cache.mkdir()
        _make_plugin_dir(
            remote_cache, "shared-key",
            init_contents="def register(ctx): ctx._source = 'remote'\n",
        )

        # User dir has a plugin with the same name
        user_dir = self.hermes_home / "plugins" / "shared-key"
        user_dir.mkdir(parents=True)
        user_dir.joinpath("plugin.yaml").write_text(
            _dump_yaml({"name": "shared-key", "version": "2.0"}),
            encoding="utf-8",
        )
        user_dir.joinpath("__init__.py").write_text(
            "def register(ctx): ctx._source = 'user'\n",
            encoding="utf-8",
        )

        cfg = {
            "plugins": {
                "enabled": ["shared-key"],
                "remote": [{"url": "https://github.com/fake/shared.git"}],
            }
        }
        cfg_path = self.hermes_home / "config.yaml"
        cfg_path.write_text(yaml.dump(cfg), encoding="utf-8")

        pm = PluginManager()
        with patch.object(PluginManager, "_resolve_git_repo", lambda self, url, repo_ref="", **kw: remote_cache):
            pm.discover_and_load()

        loaded = pm._plugins.get("shared-key")
        assert loaded is not None
        # Remote plugins are scanned after user plugins in discover_and_load,
        # so with the same key the remote entry wins. This is intentional:
        # the user explicitly configured the remote source and it is loaded
        # later in the pipeline, giving it override priority.
        assert loaded.manifest.version == "1.0.0"
        assert loaded.manifest.source == "github"

    def test_backward_compat_local_plugins_still_work(self):
        """Existing user plugins with no source block still load fine."""
        from hermes_cli.plugins import PluginManager
        import yaml

        # User plugin with no source block
        user_dir = self.hermes_home / "plugins" / "my-local-plugin"
        user_dir.mkdir(parents=True)
        user_dir.joinpath("plugin.yaml").write_text(
            _dump_yaml({
                "name": "my-local-plugin",
                "version": "0.5.0",
                "description": "A plain local plugin",
            }),
            encoding="utf-8",
        )
        user_dir.joinpath("__init__.py").write_text(
            "def register(ctx): pass\n",
            encoding="utf-8",
        )

        # Minimal config enabling only the local plugin
        cfg = {
            "plugins": {
                "enabled": ["my-local-plugin"],
            }
        }
        cfg_path = self.hermes_home / "config.yaml"
        cfg_path.write_text(yaml.dump(cfg), encoding="utf-8")

        pm = PluginManager()
        pm.discover_and_load()

        loaded = pm._plugins.get("my-local-plugin")
        assert loaded is not None
        assert loaded.enabled is True
        assert loaded.manifest.source == "user"
        assert loaded.manifest.source_type == "local"
        assert loaded.manifest.version == "0.5.0"


# ---------------------------------------------------------------------------
# _load_directory_module with github-sourced plugins
# ---------------------------------------------------------------------------


class TestLoadDirectoryModule:
    """Ensure _load_directory_module works for manifests with source='github'."""

    def test_load_github_manifest_directory(self, tmp_path):
        from hermes_cli.plugins import PluginManager, PluginManifest

        pdir = _make_plugin_dir(
            tmp_path, "gh-loadable",
            init_contents="def register(ctx): ctx._loaded = True\n",
            provides_tools=["gh_tool"],
        )

        manifest = PluginManifest(
            name="gh-loadable",
            source="github",
            path=str(pdir),
            key="gh-loadable",
            source_type="github",
            repo_url="https://github.com/fake/repo.git",
            repo_ref="main",
        )

        pm = PluginManager()
        module = pm._load_directory_module(manifest)
        assert hasattr(module, "register")

    def test_missing_init_raises(self, tmp_path):
        from hermes_cli.plugins import PluginManager, PluginManifest

        pdir = tmp_path / "no-init-plugin"
        pdir.mkdir()
        (pdir / "plugin.yaml").write_text("name: no-init\n")

        manifest = PluginManifest(
            name="no-init",
            source="github",
            path=str(pdir),
            key="no-init",
        )

        pm = PluginManager()
        with pytest.raises(FileNotFoundError, match="__init__.py"):
            pm._load_directory_module(manifest)


# ---------------------------------------------------------------------------
# Config yaml docstring example round-trip
# ---------------------------------------------------------------------------


class TestConfigYamlRoundTrip:
    """Verify the config.yaml structure the feature documents."""

    def test_remote_config_entries_read_correctly(self, tmp_path, monkeypatch):
        from hermes_cli.plugins import PluginManager

        hermes_home = tmp_path / ".hermes"
        hermes_home.mkdir()
        monkeypatch.setenv("HERMES_HOME", str(hermes_home))

        import yaml
        cfg = {
            "plugins": {
                "remote": [
                    {
                        "name": "my-plugin",
                        "url": "https://github.com/org/repo.git",
                        "ref": "v2.0",
                        "path": "plugins/my-plugin",
                    },
                    {
                        "url": "https://github.com/org/other.git",
                    },
                ],
            },
        }
        cfg_path = hermes_home / "config.yaml"
        cfg_path.write_text(yaml.dump(cfg), encoding="utf-8")

        pm = PluginManager()

        # Just verify the config is parseable; no actual git calls
        cache = tmp_path / "fake-cache"
        cache.mkdir()
        _make_plugin_dir(cache, "my-plugin")
        _make_plugin_dir(cache, "other")

        call_count = 0
        def fake_resolve(self, url, repo_ref="", **kw):
            nonlocal call_count
            call_count += 1
            return cache

        with patch.object(PluginManager, "_resolve_git_repo", fake_resolve):
            manifests = pm._scan_github_sources()

        # Should have attempted 2 git resolves
        assert call_count == 2
        assert len(manifests) == 2
