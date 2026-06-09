#!/usr/bin/env python3
"""推理评估器测试"""

import sys
import os

# 添加scripts目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reasoning_evaluator import (
    evaluate_reasoning,
    evaluate_diagnostic_accuracy,
    evaluate_reasoning_quality,
    evaluate_solution_quality,
    generate_evaluation_summary
)


def test_evaluate_diagnostic_accuracy_dns_identified():
    """测试：识别DNS问题时得高分"""
    response = "根本原因是DNS解析问题，导致线程阻塞"
    result = evaluate_diagnostic_accuracy(response, "DNS")
    assert result["score"] == 5, f"期望5分，实际{result['score']}分"
    assert "dns" in result["keywords_found"]


def test_evaluate_diagnostic_accuracy_dns_mentioned():
    """测试：提到DNS但不够明确"""
    response = "可能是DNS或网络问题"
    result = evaluate_diagnostic_accuracy(response, "DNS")
    assert result["score"] >= 4, f"期望>=4分，实际{result['score']}分"


def test_evaluate_diagnostic_accuracy_network_only():
    """测试：只识别网络问题"""
    response = "网络连接有问题"
    result = evaluate_diagnostic_accuracy(response, "DNS")
    assert result["score"] == 3, f"期望3分，实际{result['score']}分"


def test_evaluate_reasoning_quality_good():
    """测试：推理过程质量好"""
    response = """
    1. 首先，分析异常指标
    2. 其次，确定可能原因
    3. 然后，验证根本原因
    4. 最后，提出解决方案
    因为DNS问题导致线程阻塞，所以需要检查配置。
    """
    result = evaluate_reasoning_quality(response)
    assert result["score"] >= 3, f"期望>=3分，实际{result['score']}分"


def test_evaluate_reasoning_quality_poor():
    """测试：推理过程质量差"""
    response = "有问题"
    result = evaluate_reasoning_quality(response)
    assert result["score"] <= 2, f"期望<=2分，实际{result['score']}分"


def test_evaluate_solution_quality_good():
    """测试：解决方案质量好"""
    response = """
    解决方案：
    1. 检查并修复/etc/hosts文件
    2. 优化DNS配置
    3. 配置本地DNS缓存nscd
    4. 建立监控告警
    """
    result = evaluate_solution_quality(response)
    assert result["score"] >= 4, f"期望>=4分，实际{result['score']}分"


def test_evaluate_solution_quality_no_solution():
    """测试：没有解决方案"""
    response = "问题分析完成"
    result = evaluate_solution_quality(response)
    assert result["score"] == 1, f"期望1分，实际{result['score']}分"


def test_evaluate_reasoning_total_score():
    """测试：总分计算"""
    response = """
    根本原因是DNS解析问题。

    1. 首先识别异常指标
    2. 然后分析根本原因
    3. 最后提出解决方案

    解决方案：检查hosts文件，配置DNS缓存nscd。
    """
    result = evaluate_reasoning(response, "DNS")
    assert "total_score" in result
    assert 0 <= result["total_score"] <= 5
    assert "diagnostic_accuracy" in result
    assert "reasoning_quality" in result
    assert "solution_quality" in result
    assert "summary" in result


def test_generate_evaluation_summary_excellent():
    """测试：优秀评级"""
    result = generate_evaluation_summary(
        4.6,
        {"score": 5, "analysis": "优秀"},
        {"score": 5, "analysis": "优秀"},
        {"score": 5, "analysis": "优秀"}
    )
    assert "优秀" in result["conclusion"]


def test_generate_evaluation_summary_poor():
    """测试：较差评级"""
    result = generate_evaluation_summary(
        1.5,
        {"score": 1, "analysis": "差"},
        {"score": 1, "analysis": "差"},
        {"score": 1, "analysis": "差"}
    )
    assert "较差" in result["conclusion"]


def test_evaluate_reasoning_none_input():
    """测试：None输入返回0分"""
    result = evaluate_reasoning(None)
    assert result["total_score"] == 0
    assert "无效输入" in result["summary"]["conclusion"]


def test_evaluate_reasoning_empty_string():
    """测试：空字符串输入返回0分"""
    result = evaluate_reasoning("")
    assert result["total_score"] == 0
    assert "无效输入" in result["summary"]["conclusion"]


def test_evaluate_reasoning_whitespace_only():
    """测试：纯空白字符串输入返回0分"""
    result = evaluate_reasoning("   \n\t  ")
    assert result["total_score"] == 0
    assert "无效输入" in result["summary"]["conclusion"]


def test_evaluate_reasoning_invalid_type():
    """测试：非字符串类型输入返回0分"""
    result = evaluate_reasoning(123)
    assert result["total_score"] == 0
    assert "无效输入" in result["summary"]["conclusion"]


if __name__ == "__main__":
    # 运行所有测试
    tests = [
        test_evaluate_diagnostic_accuracy_dns_identified,
        test_evaluate_diagnostic_accuracy_dns_mentioned,
        test_evaluate_diagnostic_accuracy_network_only,
        test_evaluate_reasoning_quality_good,
        test_evaluate_reasoning_quality_poor,
        test_evaluate_solution_quality_good,
        test_evaluate_solution_quality_no_solution,
        test_evaluate_reasoning_total_score,
        test_generate_evaluation_summary_excellent,
        test_generate_evaluation_summary_poor,
        test_evaluate_reasoning_none_input,
        test_evaluate_reasoning_empty_string,
        test_evaluate_reasoning_whitespace_only,
        test_evaluate_reasoning_invalid_type,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n结果: {passed} 通过, {failed} 失败")
    sys.exit(0 if failed == 0 else 1)
