from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[2] / "plugins" / "notebooklm"


def load_plugin():
    package_name = "notebooklm_test_plugin"
    for name in list(sys.modules):
        if name == package_name or name.startswith(f"{package_name}."):
            del sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        package_name,
        PLUGIN_DIR / "__init__.py",
        submodule_search_locations=[str(PLUGIN_DIR)],
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)
    return module


def make_settings(core, tmp_path, **overrides):
    state_dir = tmp_path / "state"
    values = {
        "project_number": "",
        "location": "global",
        "endpoint_location": "global",
        "notebook_id": "",
        "notebook_title": core.DEFAULT_NOTEBOOK_TITLE,
        "access_token": "",
        "use_gcloud_auth": False,
        "state_dir": state_dir,
        "source_dir": state_dir / "sources",
        "brainstorm_dir": state_dir / "brainstorms",
        "docs_dir": tmp_path / "_docs",
        "x_activity_log": state_dir / "lm-twitterer" / "activity.jsonl",
        "max_logs": 5,
        "max_x_events": 5,
        "max_source_chars": 20000,
        "max_post_chars": 280,
        "idea_count": 3,
        "provider": "",
        "model": "",
    }
    values.update(overrides)
    return core.Settings(**values)


def test_register_exposes_tools_and_cli_command():
    plugin = load_plugin()

    class Ctx:
        def __init__(self):
            self.tools = []
            self.commands = []
            self.cli_commands = []

        def register_tool(self, **kwargs):
            self.tools.append(kwargs)

        def register_command(self, *args, **kwargs):
            self.commands.append((args, kwargs))

        def register_cli_command(self, **kwargs):
            self.cli_commands.append(kwargs)

        @property
        def llm(self):
            return None

    ctx = Ctx()
    plugin.register(ctx)

    assert {tool["name"] for tool in ctx.tools} == {
        "notebooklm_status",
        "notebooklm_collect",
        "notebooklm_brainstorm",
        "notebooklm_sync",
        "notebooklm_run",
    }
    assert ctx.commands[0][0][0] == "notebooklm"
    assert ctx.cli_commands[0]["name"] == "notebooklm"


def test_collect_source_redacts_logs_and_x_activity(tmp_path):
    plugin = load_plugin()
    core = plugin.core
    docs_dir = tmp_path / "_docs"
    docs_dir.mkdir()
    (docs_dir / "2026-06-03_demo.md").write_text(
        "# Demo\n\nAPI_KEY=sk-secret-value-12345678901234567890123456789012\nShipped feature.",
        encoding="utf-8",
    )
    activity = tmp_path / "state" / "lm-twitterer" / "activity.jsonl"
    activity.parent.mkdir(parents=True)
    activity.write_text(
        json.dumps(
            {
                "action": "post",
                "dry_run": True,
                "ok": True,
                "tweet_text": "Draft with token=abcdef1234567890abcdef1234567890",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    cfg = make_settings(core, tmp_path, docs_dir=docs_dir, x_activity_log=activity)

    result = core.collect_source(cfg=cfg)

    assert result["ok"] is True
    text = Path(result["source_path"]).read_text(encoding="utf-8")
    assert "Shipped feature" in text
    assert "sk-secret" not in text
    assert "abcdef1234567890abcdef1234567890" not in text
    assert "X Event 1" in text


def test_brainstorm_uses_bound_llm_and_wraps_source(tmp_path):
    plugin = load_plugin()
    core = plugin.core
    cfg = make_settings(core, tmp_path)
    source = tmp_path / "source.md"
    source.write_text(
        "# Source\n\n### Important implementation\nVerified behavior.", encoding="utf-8"
    )
    captured = {}

    class FakeLLM:
        def complete(self, messages, **kwargs):
            captured["messages"] = messages
            captured["kwargs"] = kwargs

            class Result:
                text = "1. hook: shipped\n   draft post: Verified Hermes work.\n"

            return Result()

    core.bind_llm_factory(lambda: FakeLLM())
    result = core.brainstorm_posts(source_path=source, cfg=cfg, idea_count=1)

    assert result["ok"] is True
    assert captured["kwargs"]["purpose"] == "notebooklm.brainstorm"
    assert "<notebooklm_source_bundle>" in captured["messages"][1]["content"]
    output = Path(result["brainstorm_path"]).read_text(encoding="utf-8")
    assert "Verified Hermes work" in output


def test_sync_source_posts_text_content_payload(tmp_path, monkeypatch):
    plugin = load_plugin()
    core = plugin.core
    source = tmp_path / "source.md"
    source.write_text("# Source\ncontent", encoding="utf-8")
    cfg = make_settings(
        core,
        tmp_path,
        project_number="12345",
        notebook_id="nb1",
        access_token="token",
    )
    calls = []

    def fake_http_json(method, url, *, token, payload=None, timeout=60):
        calls.append(
            {
                "method": method,
                "url": url,
                "token": token,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return {"sources": [{"sourceId": {"id": "src1"}}]}

    monkeypatch.setattr(core, "_http_json", fake_http_json)
    result = core.sync_source(source_path=source, cfg=cfg)

    assert result["ok"] is True
    assert calls[0]["method"] == "POST"
    assert calls[0]["url"].endswith("/notebooks/nb1/sources:batchCreate")
    assert (
        calls[0]["payload"]["userContents"][0]["textContent"]["content"]
        == "# Source\ncontent"
    )


def test_sync_source_can_create_notebook_before_upload(tmp_path, monkeypatch):
    plugin = load_plugin()
    core = plugin.core
    source = tmp_path / "source.md"
    source.write_text("# Source\ncontent", encoding="utf-8")
    cfg = make_settings(core, tmp_path, project_number="12345", access_token="token")
    calls = []

    def fake_http_json(method, url, *, token, payload=None, timeout=60):
        calls.append((method, url, payload))
        if url.endswith("/notebooks"):
            return {"notebookId": "created-nb"}
        return {"sources": [{"sourceId": {"id": "src1"}}]}

    monkeypatch.setattr(core, "_http_json", fake_http_json)
    result = core.sync_source(source_path=source, create_if_missing=True, cfg=cfg)

    assert result["ok"] is True
    assert result["notebook_id"] == "created-nb"
    assert calls[0][1].endswith("/notebooks")
    assert calls[1][1].endswith("/notebooks/created-nb/sources:batchCreate")
