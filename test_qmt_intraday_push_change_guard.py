#!/usr/bin/env python3
"""Unit tests for qmt_intraday_push_change_guard.py"""

import json
import tempfile
from pathlib import Path

import pytest

from qmt_intraday_push_change_guard import (
    digest,
    extract_push_summary,
    normalize_report,
    detect_status,
    build_state,
)


class TestNormalizeReport:
    def test_removes_dates(self):
        text = "Report from 20260420 at 14:30"
        result = normalize_report(text)
        assert "20260420" not in result
        assert "<DATE>" in result

    def test_removes_paths(self):
        text = "/Users/zezesun/data/report.txt"
        result = normalize_report(text)
        assert "/Users/zezesun" not in result
        assert "<PATH>" in result

    def test_normalizes_whitespace(self):
        text = "Line   with    multiple     spaces"
        result = normalize_report(text)
        assert "Line with multiple spaces" in result


class TestExtractPushSummary:
    def test_extracts_action_line(self):
        report = """
## IM 极简摘要
- 自动动作：仅留备选
- 当前最强：无
"""
        result = extract_push_summary(report)
        assert result['action_line'] == '自动动作：仅留备选'
        assert result['best_line'] == '当前最强：无'

    def test_extracts_theme_and_template(self):
        report = """
## IM 极简摘要
- 题材判定：AI+算力
- 动作模板：首板强势（标签=强势首板/题材龙头）
"""
        result = extract_push_summary(report)
        assert result['theme_line'] == '题材判定：AI+算力'
        assert result['template_line'].startswith('动作模板：首板强势')
        assert result['reason_tags'] == ['强势首板', '题材龙头']

    def test_handles_missing_sections(self):
        report = "No IM summary here"
        result = extract_push_summary(report)
        assert result['action_line'] == ''
        assert result['best_line'] == ''
        assert result['reason_tags'] == []


class TestDecisionHash:
    def test_same_decision_same_hash(self, tmp_path):
        """相同决策内容应产生相同 decision_hash"""
        report1 = """
## IM 极简摘要
- 自动动作：仅留备选
- 当前最强：无
- 题材判定：AI
- 动作模板：观望
"""
        report2 = """
## IM 极简摘要
- 自动动作：仅留备选
- 当前最强：无
- 题材判定：AI
- 动作模板：观望

## 其他内容
这里的内容变化不应影响 decision_hash
"""
        report_path = tmp_path / "report.txt"
        state_path = tmp_path / "state.json"

        # First run
        report_path.write_text(report1, encoding='utf-8')
        status1, hash1, state1 = detect_status(report_path, state_path)
        assert status1 == 'CHANGED'  # 首次运行

        # Commit state
        state_path.write_text(json.dumps(state1, ensure_ascii=False), encoding='utf-8')

        # Second run with different content but same decision
        report_path.write_text(report2, encoding='utf-8')
        status2, hash2, state2 = detect_status(report_path, state_path)
        
        assert state2['decision_hash'] == state1['decision_hash']
        assert state2['content_changed'] is True  # 内容变了
        assert state2['decision_changed'] is False  # 决策未变
        assert status2 == 'UNCHANGED'  # 不应推送

    def test_different_decision_different_hash(self, tmp_path):
        """不同决策内容应产生不同 decision_hash"""
        report1 = """
## IM 极简摘要
- 自动动作：仅留备选
- 当前最强：无
"""
        report2 = """
## IM 极简摘要
- 自动动作：全部清仓
- 当前最强：600000
"""
        report_path = tmp_path / "report.txt"
        state_path = tmp_path / "state.json"

        # First run
        report_path.write_text(report1, encoding='utf-8')
        status1, hash1, state1 = detect_status(report_path, state_path)
        state_path.write_text(json.dumps(state1, ensure_ascii=False), encoding='utf-8')

        # Second run with different decision
        report_path.write_text(report2, encoding='utf-8')
        status2, hash2, state2 = detect_status(report_path, state_path)
        
        assert state2['decision_hash'] != state1['decision_hash']
        assert state2['decision_changed'] is True
        assert status2 == 'CHANGED'  # 应该推送


class TestDetectStatus:
    def test_missing_report(self, tmp_path):
        report_path = tmp_path / "nonexistent.txt"
        state_path = tmp_path / "state.json"
        status, hash_val, state = detect_status(report_path, state_path)
        assert status == 'MISSING'
        assert hash_val == ''

    def test_first_run_always_changed(self, tmp_path):
        """首次运行应标记为 CHANGED"""
        report_path = tmp_path / "report.txt"
        state_path = tmp_path / "state.json"
        report_path.write_text("## IM 极简摘要\n- 自动动作：观望", encoding='utf-8')
        
        status, hash_val, state = detect_status(report_path, state_path)
        assert status == 'CHANGED'
        assert state['decision_changed'] is True


class TestDigest:
    def test_consistent_hash(self):
        text = "test content"
        hash1 = digest(text)
        hash2 = digest(text)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

    def test_different_content_different_hash(self):
        hash1 = digest("content1")
        hash2 = digest("content2")
        assert hash1 != hash2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
