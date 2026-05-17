"""
Tests for agent/session_skill_analyzer.py
"""

import os
import tempfile
from pathlib import Path

import pytest

from agent.session_skill_analyzer import (
    _analyze_session_context,
    _match_skill_conditions,
    _scan_project_files,
    merge_preloads,
)


class TestScanProjectFiles:
    """Phase 1 project-file scanner tests."""

    def test_context_md_research_type(self, tmp_path: Path):
        (tmp_path / "CONTEXT.md").write_text("project.type: research\n")
        signals = _scan_project_files(tmp_path)
        assert "research" in signals["project_types"]

    def test_context_md_dev_type(self, tmp_path: Path):
        (tmp_path / "CONTEXT.md").write_text("project.type: dev\n")
        signals = _scan_project_files(tmp_path)
        assert "dev" in signals["project_types"]

    def test_context_md_skill_hint(self, tmp_path: Path):
        (tmp_path / "CONTEXT.md").write_text("skill: my-custom-skill\n")
        signals = _scan_project_files(tmp_path)
        assert "my-custom-skill" in signals["declared_skills"]

    def test_agents_md_skills_list(self, tmp_path: Path):
        (tmp_path / "AGENTS.md").write_text(
            "agent: my-agent\n  skills:\n    - skill: arxiv\n    - skill: knowledge-logging\n"
        )
        signals = _scan_project_files(tmp_path)
        assert "arxiv" in signals["declared_skills"]
        assert "knowledge-logging" in signals["declared_skills"]

    def test_package_json_react(self, tmp_path: Path):
        (tmp_path / "package.json").write_text('{"dependencies": {"react": "^18.0.0"}}')
        signals = _scan_project_files(tmp_path)
        assert "frontend" in signals["project_types"]

    def test_dockerfile_adds_docker_hint(self, tmp_path: Path):
        (tmp_path / "Dockerfile").write_text("FROM python:3.11-slim")
        signals = _scan_project_files(tmp_path)
        assert "docker" in signals["file_hints"]
        assert "docker" in signals["project_types"]

    def test_torch_import(self, tmp_path: Path):
        (tmp_path / "train.py").write_text("import torch\nimport torch.nn as nn\n")
        signals = _scan_project_files(tmp_path)
        assert "ml" in signals["project_types"]

    def test_no_cwd_returns_empty(self):
        signals = _scan_project_files(Path("/nonexistent/path"))
        assert signals["project_types"] == set()
        assert signals["declared_skills"] == set()
        assert signals["file_hints"] == set()


class TestMergePreloads:
    """merge_preloads() deduplication and ordering tests."""

    def test_deduplication(self):
        result = merge_preloads(
            auto_preloads=["a", "b", "a"],
            explicit_preloads=["b", "c"],
        )
        assert result == ["a", "b", "c"]

    def test_max_auto_limit(self):
        result = merge_preloads(
            auto_preloads=["a", "b", "c", "d", "e", "f"],
            explicit_preloads=[],
            max_auto=3,
        )
        assert len(result) == 3
        assert result == ["a", "b", "c"]

    def test_explicit_after_auto(self):
        result = merge_preloads(
            auto_preloads=["a", "b"],
            explicit_preloads=["c", "d"],
        )
        assert result == ["a", "b", "c", "d"]

    def test_empty_auto_uses_explicit(self):
        result = merge_preloads(
            auto_preloads=[],
            explicit_preloads=["x", "y"],
        )
        assert result == ["x", "y"]


class TestAnalyzeSessionContext:
    """_analyze_session_context() integration tests."""

    def test_none_cwd_uses_env_var(self, monkeypatch):
        monkeypatch.setenv("TERMINAL_CWD", "")
        result = _analyze_session_context()
        assert result == []

    def test_unknown_path_returns_empty(self):
        result = _analyze_session_context("/nonexistent/xyz")
        assert result == []
