"""Tests for the gbrain MemoryProvider plugin.

The plugin must follow the Hermes memory provider contract documented at
https://hermes-agent.nousresearch.com/docs/developer-guide/memory-provider-plugin.
"""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest


_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


@pytest.fixture(autouse=True)
def _isolate_env(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.delenv("GBRAIN_DATABASE_URL", raising=False)
    monkeypatch.delenv("GBRAIN_HOME", raising=False)
    monkeypatch.delenv("GBRAIN_MEMORY_AUTO_SYNC", raising=False)
    monkeypatch.delenv("GBRAIN_MEMORY_MAX_RESULTS", raising=False)


class TestGBrainPluginFiles:
    def test_provider_directory_matches_docs(self):
        plugin_dir = Path(_repo_root) / "plugins" / "memory" / "gbrain"
        assert (plugin_dir / "__init__.py").exists()
        assert (plugin_dir / "plugin.yaml").exists()
        assert (plugin_dir / "README.md").exists()

    def test_plugin_yaml_metadata(self):
        import yaml

        meta = yaml.safe_load((Path(_repo_root) / "plugins" / "memory" / "gbrain" / "plugin.yaml").read_text())
        assert meta["name"] == "gbrain"
        assert "GBrain" in meta["description"]
        assert "on_memory_write" in meta.get("hooks", [])
        assert "on_pre_compress" in meta.get("hooks", [])


class TestGBrainMemoryProviderContract:
    def test_discovery_can_load_gbrain_provider(self, tmp_path, monkeypatch):
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        fake_gbrain = bin_dir / "gbrain"
        fake_gbrain.write_text("#!/bin/sh\necho gbrain test stub\n")
        fake_gbrain.chmod(fake_gbrain.stat().st_mode | stat.S_IXUSR)
        monkeypatch.setenv("PATH", str(bin_dir))

        from plugins.memory import load_memory_provider

        provider = load_memory_provider("gbrain")
        assert provider is not None
        assert provider.name == "gbrain"
        assert provider.is_available()

    def test_config_schema_is_minimal_and_profile_scoped(self):
        from plugins.memory.gbrain import GBrainMemoryProvider

        schema = GBrainMemoryProvider().get_config_schema()
        keys = [field["key"] for field in schema]
        assert keys == ["brain_slug_prefix", "auto_sync_turns", "capture_on_pre_compress", "max_results"]
        assert all(not field.get("secret") for field in schema)

    def test_save_config_writes_non_secret_config(self, tmp_path):
        from plugins.memory.gbrain import GBrainMemoryProvider
        import yaml

        hermes_home = tmp_path / ".hermes"
        provider = GBrainMemoryProvider()
        provider.save_config(
            {"brain_slug_prefix": "agents/hermes/memory", "auto_sync_turns": "true", "capture_on_pre_compress": "true", "max_results": "7"},
            str(hermes_home),
        )
        config = yaml.safe_load((hermes_home / "config.yaml").read_text())
        assert config["plugins"]["gbrain"]["brain_slug_prefix"] == "agents/hermes/memory"
        assert config["plugins"]["gbrain"]["auto_sync_turns"] == "true"
        assert config["plugins"]["gbrain"]["capture_on_pre_compress"] == "true"
        assert config["plugins"]["gbrain"]["max_results"] == "7"

    def test_initialize_uses_hermes_home_not_global_home(self, tmp_path):
        from plugins.memory.gbrain import GBrainMemoryProvider

        hermes_home = tmp_path / "profile-home"
        hermes_home.mkdir()
        provider = GBrainMemoryProvider(runner=lambda *a, **k: "")
        provider.initialize("session-1", hermes_home=str(hermes_home), user_id="tony", platform="telegram")
        assert provider._hermes_home == hermes_home
        assert provider._session_id == "session-1"
        assert provider._user_id == "tony"

    def test_tool_schemas_have_gbrain_namespace(self):
        from plugins.memory.gbrain import GBrainMemoryProvider

        schemas = GBrainMemoryProvider().get_tool_schemas()
        names = {schema["name"] for schema in schemas}
        assert names == {"gbrain_search", "gbrain_query", "gbrain_get", "gbrain_remember"}
        for schema in schemas:
            assert schema["parameters"]["type"] == "object"

    def test_search_tool_calls_gbrain_search_json(self, tmp_path):
        from plugins.memory.gbrain import GBrainMemoryProvider

        calls = []

        def fake_runner(args, timeout=10):
            calls.append(args)
            return json.dumps({"results": [{"slug": "people/tony", "title": "Tony"}]})

        provider = GBrainMemoryProvider(runner=fake_runner)
        provider.initialize("s1", hermes_home=str(tmp_path))
        result = json.loads(provider.handle_tool_call("gbrain_search", {"query": "Tony", "limit": 3}))
        assert result["results"][0]["slug"] == "people/tony"
        assert calls == [["gbrain", "--json", "search", "Tony", "--limit", "3"]]

    def test_query_tool_calls_gbrain_query_json(self, tmp_path):
        from plugins.memory.gbrain import GBrainMemoryProvider

        calls = []

        def fake_runner(args, timeout=20):
            calls.append(args)
            return json.dumps({"answer": "found"})

        provider = GBrainMemoryProvider(runner=fake_runner)
        provider.initialize("s1", hermes_home=str(tmp_path))
        result = json.loads(provider.handle_tool_call("gbrain_query", {"question": "What does Tony prefer?", "limit": 4, "no_expand": True}))
        assert result["answer"] == "found"
        assert calls == [["gbrain", "--json", "query", "What does Tony prefer?", "--limit", "4", "--no-expand"]]

    def test_remember_tool_writes_markdown_page_under_slug_prefix(self, tmp_path):
        from plugins.memory.gbrain import GBrainMemoryProvider

        calls = []

        def fake_runner(args, input_text=None, timeout=10):
            calls.append((args, input_text))
            return json.dumps({"slug": args[2], "ok": True})

        provider = GBrainMemoryProvider(runner=fake_runner, config={"brain_slug_prefix": "agents/hermes/memory"})
        provider.initialize("s1", hermes_home=str(tmp_path), user_id="u1")
        result = json.loads(provider.handle_tool_call("gbrain_remember", {"content": "Tony likes terse updates", "category": "preference"}))
        assert result["slug"].startswith("agents/hermes/memory/")
        assert calls[0][0] == ["gbrain", "put", result["slug"], "--content"]
        assert "Tony likes terse updates" in calls[0][1]
        assert "category: preference" in calls[0][1]

    def test_remember_tool_rejects_unsafe_slugs(self, tmp_path):
        from plugins.memory.gbrain import GBrainMemoryProvider

        calls = []

        def fake_runner(args, input_text=None, timeout=10):
            calls.append((args, input_text))
            return json.dumps({"ok": True})

        provider = GBrainMemoryProvider(runner=fake_runner)
        provider.initialize("s1", hermes_home=str(tmp_path))
        result = json.loads(provider.handle_tool_call("gbrain_remember", {"content": "safe body", "slug": "../secret"}))
        assert "invalid slug" in result["error"]
        assert calls == []

    def test_markdown_frontmatter_escapes_metadata(self, tmp_path):
        from plugins.memory.gbrain import GBrainMemoryProvider

        provider = GBrainMemoryProvider(runner=lambda *a, **k: "")
        provider.initialize("s1", hermes_home=str(tmp_path), user_id="user\nadmin: true")
        markdown = provider._build_markdown(
            content="Title\n---\nbody stays body",
            category="pref\nmalicious: true",
            source="test\nsource: injected",
        )
        frontmatter = markdown.split("---\n", 2)[1]
        assert "category: 'pref" in frontmatter
        assert "source: 'test" in frontmatter
        assert "user_id: 'user" in frontmatter
        assert "body stays body" in markdown

    def test_prefetch_returns_formatted_context_and_consumes_cache(self, tmp_path):
        from plugins.memory.gbrain import GBrainMemoryProvider

        def fake_runner(args, timeout=20):
            assert args[:4] == ["gbrain", "--json", "query", "ADU permit"]
            return json.dumps({"answer": "ADU permit is pending resubmittal", "sources": [{"slug": "projects/adu"}]})

        provider = GBrainMemoryProvider(runner=fake_runner)
        provider.initialize("s1", hermes_home=str(tmp_path))
        provider.queue_prefetch("ADU permit")
        provider.shutdown()
        context = provider.prefetch("ADU permit")
        assert "[GBrain Context]" in context
        assert "ADU permit is pending resubmittal" in context
        assert "projects/adu" in context
        assert provider.prefetch("ADU permit") == ""

    def test_on_memory_write_mirrors_builtin_memory_add(self, tmp_path):
        from plugins.memory.gbrain import GBrainMemoryProvider

        calls = []

        def fake_runner(args, input_text=None, timeout=10):
            calls.append((args, input_text))
            return json.dumps({"ok": True})

        provider = GBrainMemoryProvider(runner=fake_runner)
        provider.initialize("s1", hermes_home=str(tmp_path))
        provider.on_memory_write("add", "user", "Tony prefers direct yes/no answers")
        assert calls
        assert calls[0][0][0:2] == ["gbrain", "put"]
        assert "Tony prefers direct yes/no answers" in calls[0][1]
        assert "source: hermes-memory-tool" in calls[0][1]


    def test_put_markdown_uses_current_gbrain_content_flag(self, tmp_path):
        from plugins.memory.gbrain import GBrainMemoryProvider

        calls = []

        def fake_runner(args, input_text=None, timeout=10):
            calls.append((args, input_text))
            return json.dumps({"ok": True})

        provider = GBrainMemoryProvider(runner=fake_runner)
        provider.initialize("s1", hermes_home=str(tmp_path))
        provider.on_memory_write("add", "memory", "Hermes gbrain smoke fact")

        assert calls
        args, input_text = calls[0]
        assert args[:3] == ["gbrain", "put", args[2]]
        assert args[3] == "--content"
        assert input_text is not None
        assert "Hermes gbrain smoke fact" in input_text

    def test_on_pre_compress_extracts_recent_context(self, tmp_path):
        from plugins.memory.gbrain import GBrainMemoryProvider

        calls = []

        def fake_runner(args, input_text=None, timeout=10):
            calls.append((args, input_text))
            return json.dumps({"ok": True})

        provider = GBrainMemoryProvider(runner=fake_runner, config={"capture_on_pre_compress": "true"})
        provider.initialize("s1", hermes_home=str(tmp_path))
        contribution = provider.on_pre_compress([
            {"role": "user", "content": "Remember the ADU resubmittal is due Friday"},
            {"role": "assistant", "content": "Noted."},
        ])
        assert "GBrain captured" in contribution
        assert calls
        assert "ADU resubmittal" in calls[0][1]

    def test_on_pre_compress_defaults_off(self, tmp_path):
        from plugins.memory.gbrain import GBrainMemoryProvider

        runner = Mock(return_value=json.dumps({"ok": True}))
        provider = GBrainMemoryProvider(runner=runner)
        provider.initialize("s1", hermes_home=str(tmp_path))
        contribution = provider.on_pre_compress([{"role": "user", "content": "secret-ish context"}])
        assert contribution == ""
        assert runner.call_count == 0

    def test_on_session_switch_updates_cached_session_id(self, tmp_path):
        from plugins.memory.gbrain import GBrainMemoryProvider

        calls = []

        def fake_runner(args, input_text=None, timeout=10):
            calls.append((args, input_text))
            return json.dumps({"ok": True})

        provider = GBrainMemoryProvider(runner=fake_runner)
        provider.initialize("old-session", hermes_home=str(tmp_path))
        provider.on_session_switch("new-session", reset=True)
        provider.on_memory_write("add", "memory", "session switch smoke")
        assert "session_id: new-session" in calls[0][1]

    def test_capture_skips_secret_like_content(self, tmp_path):
        from plugins.memory.gbrain import GBrainMemoryProvider

        runner = Mock(return_value=json.dumps({"ok": True}))
        provider = GBrainMemoryProvider(runner=runner)
        provider.initialize("s1", hermes_home=str(tmp_path))
        provider.on_memory_write("add", "memory", "OPENAI_API_KEY=sk-test-secret")
        assert runner.call_count == 0

    def test_sync_turn_is_non_blocking_and_can_be_disabled(self, tmp_path, monkeypatch):
        from plugins.memory.gbrain import GBrainMemoryProvider

        runner = Mock(return_value=json.dumps({"ok": True}))
        provider = GBrainMemoryProvider(runner=runner, config={"auto_sync_turns": "false"})
        provider.initialize("s1", hermes_home=str(tmp_path))
        provider.sync_turn("user said durable thing", "assistant answered")
        provider.shutdown()
        assert runner.call_count == 0
