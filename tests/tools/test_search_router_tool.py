from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

from tools.search_router_tool import (
    DEFAULT_SEARCH_WORKER_TIMEOUT_SECONDS,
    _build_prompt,
    _run_worker,
    _select_worker_python,
    _summarize_packet,
    search_router_tool,
)


def test_search_router_tool_success(monkeypatch):
    packet = {
        "query_intent": "确认官方文档入口",
        "searches_performed": [{"tool": "web_search", "query": "Hermes Agent docs"}],
        "sources": [{"title": "Official Docs", "url": "https://hermes-agent.nousresearch.com/docs/", "source_type": "official"}],
        "key_findings": ["官方文档入口存在"],
        "conflicts": [],
        "unknowns": [],
        "recommended_next_step": "如需更细节，继续抽子页面",
    }

    def fake_run_worker(prompt: str, profile: str, provider: str, model: str):
        assert "任务目标" in prompt
        assert profile == "search-worker"
        assert provider == "ctyun"
        assert model == "DeepSeek-V4-Flash"
        return SimpleNamespace(returncode=0, stdout="前言\n```json\n" + json.dumps(packet, ensure_ascii=False) + "\n```", stderr="")

    monkeypatch.setattr("tools.search_router_tool._run_worker", fake_run_worker)
    payload = json.loads(search_router_tool(task_goal="确认官方文档入口"))

    assert payload["success"] is True
    assert payload["packet"]["query_intent"] == "确认官方文档入口"
    assert payload["issues"] == []
    assert "stdout 在 JSON 前包含额外文本" in payload["warnings"]
    assert "stdout 在 JSON 后包含额外文本" in payload["warnings"]
    assert "**结论**" in payload["assistant_brief"]
    assert "Official Docs" in payload["assistant_brief"]


def test_search_router_tool_success_when_output_is_bare_json(monkeypatch):
    packet = {
        "query_intent": "确认官方文档入口",
        "searches_performed": [{"tool": "web_search", "query": "Hermes Agent docs"}],
        "sources": [{"title": "Official Docs", "url": "https://hermes-agent.nousresearch.com/docs/", "source_type": "official"}],
        "key_findings": ["官方文档入口存在"],
        "conflicts": [],
        "unknowns": [],
        "recommended_next_step": "如需更细节，继续抽子页面",
    }

    def fake_run_worker(prompt: str, profile: str, provider: str, model: str):
        return SimpleNamespace(returncode=0, stdout=json.dumps(packet, ensure_ascii=False), stderr="")

    monkeypatch.setattr("tools.search_router_tool._run_worker", fake_run_worker)
    payload = json.loads(search_router_tool(task_goal="确认官方文档入口"))

    assert payload["success"] is True
    assert payload["issues"] == []


def test_search_router_tool_worker_failure(monkeypatch):
    def fake_run_worker(prompt: str, profile: str, provider: str, model: str):
        return SimpleNamespace(returncode=9, stdout="oops", stderr="boom")

    monkeypatch.setattr("tools.search_router_tool._run_worker", fake_run_worker)
    payload = json.loads(search_router_tool(task_goal="确认官方文档入口"))

    assert payload["success"] is False
    assert payload["error_type"] == "worker_process_failed"
    assert payload["exit_code"] == 9


def test_search_router_tool_parse_failure(monkeypatch):
    def fake_run_worker(prompt: str, profile: str, provider: str, model: str):
        return SimpleNamespace(returncode=0, stdout="没有json", stderr="")

    monkeypatch.setattr("tools.search_router_tool._run_worker", fake_run_worker)
    payload = json.loads(search_router_tool(task_goal="确认官方文档入口"))

    assert payload["success"] is False
    assert payload["error_type"] == "json_extract_or_parse_failed"


def test_search_router_tool_worker_timeout(monkeypatch):
    def fake_run_worker(prompt: str, profile: str, provider: str, model: str):
        raise subprocess.TimeoutExpired(
            cmd=["hermes", "chat"], timeout=DEFAULT_SEARCH_WORKER_TIMEOUT_SECONDS, output="partial out", stderr="partial err"
        )

    monkeypatch.setattr("tools.search_router_tool._run_worker", fake_run_worker)
    payload = json.loads(search_router_tool(task_goal="确认官方文档入口"))

    assert payload["success"] is False
    assert payload["error_type"] == "worker_timeout"
    assert payload["worker_profile"] == "search-worker"
    assert payload["worker_provider"] == "ctyun"
    assert payload["worker_model"] == "DeepSeek-V4-Flash"
    assert payload["stdout_head"] == "partial out"
    assert payload["stderr_tail"] == "partial err"


def test_build_prompt_enforces_stop_conditions():
    prompt = _build_prompt("确认官方文档入口", "官方源 + 中文公开讨论", 2)

    assert "达到 min_sources 且已有官方/一手源时，优先停止" in prompt
    assert "不要为了“更完整”而无限追加相近来源" in prompt
    assert "不要自行继续扩题" in prompt
    assert "如果输出任何 JSON 之外的前言、总结、解释、markdown 代码块或围栏，视为失败" in prompt


def test_summarize_packet_flattens_dicts():
    brief = _summarize_packet(
        {
            "key_findings": [{"a": "结论A", "b": "结论B"}],
            "sources": [{"title": "源1", "url": "https://x", "source_type": "official"}],
            "conflicts": [{"desc": "口径不同"}],
            "unknowns": [{"u": "版本号未确认"}],
            "recommended_next_step": {"n": "继续查 release"},
        }
    )

    assert "结论A" in brief
    assert "结论B" in brief
    assert "口径不同" in brief
    assert "版本号未确认" in brief
    assert "继续查 release" in brief


def test_select_worker_python_prefers_venv_then_dotvenv_then_sys_executable(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    venv_python = repo_root / "venv" / "bin" / "python"
    dotvenv_python = repo_root / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    dotvenv_python.parent.mkdir(parents=True)
    venv_python.write_text("#!/bin/sh\n")
    dotvenv_python.write_text("#!/bin/sh\n")

    monkeypatch.setattr("tools.search_router_tool.os.access", lambda path, mode: True)
    monkeypatch.setattr("tools.search_router_tool.sys.executable", "/fallback/python")

    assert _select_worker_python(repo_root) == str(venv_python)

    venv_python.unlink()
    assert _select_worker_python(repo_root) == str(dotvenv_python)

    dotvenv_python.unlink()
    assert _select_worker_python(repo_root) == "/fallback/python"


def test_run_worker_sanitizes_empty_profile_provider_and_model(monkeypatch, tmp_path):
    root = tmp_path / ".hermes"
    profile_dir = root / "profiles" / "search-worker"
    profile_dir.mkdir(parents=True)

    captured = {}

    def fake_run(cmd, capture_output, text, env, timeout):
        captured["cmd"] = cmd
        captured["env"] = env
        captured["timeout"] = timeout
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr("tools.search_router_tool.get_default_hermes_root", lambda: root)
    monkeypatch.setattr("tools.search_router_tool.subprocess.run", fake_run)
    monkeypatch.setattr("tools.search_router_tool._select_worker_python", lambda: "/repo/venv/bin/python")

    _run_worker(prompt="只输出{}", profile="", provider="", model="")

    assert captured["cmd"] == [
        "/repo/venv/bin/python",
        "-m",
        "hermes_cli.main",
        "chat",
        "-q",
        "只输出{}",
        "-Q",
    ]
    assert captured["env"]["HERMES_HOME"] == str(profile_dir)
    assert captured["timeout"] == DEFAULT_SEARCH_WORKER_TIMEOUT_SECONDS


def test_run_worker_includes_provider_and_model_only_when_non_empty(monkeypatch, tmp_path):
    root = tmp_path / ".hermes"
    profile_dir = root / "profiles" / "search-worker"
    profile_dir.mkdir(parents=True)

    captured = {}

    def fake_run(cmd, capture_output, text, env, timeout):
        captured["cmd"] = cmd
        captured["env"] = env
        captured["timeout"] = timeout
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr("tools.search_router_tool.get_default_hermes_root", lambda: root)
    monkeypatch.setattr("tools.search_router_tool.subprocess.run", fake_run)
    monkeypatch.setattr("tools.search_router_tool._select_worker_python", lambda: "/repo/venv/bin/python")

    _run_worker(prompt="只输出{}", profile="search-worker", provider="ctyun", model="DeepSeek-V4-Flash")

    assert captured["cmd"] == [
        "/repo/venv/bin/python",
        "-m",
        "hermes_cli.main",
        "chat",
        "-q",
        "只输出{}",
        "-Q",
        "--provider",
        "ctyun",
        "-m",
        "DeepSeek-V4-Flash",
    ]
    assert captured["env"]["HERMES_HOME"] == str(profile_dir)
    assert captured["timeout"] == DEFAULT_SEARCH_WORKER_TIMEOUT_SECONDS
