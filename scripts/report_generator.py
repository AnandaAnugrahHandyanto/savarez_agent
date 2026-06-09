#!/usr/bin/env python3
"""
报告生成器
生成Markdown格式的评估报告
"""

from datetime import datetime


def generate_evaluation_report(scenario_data, api_response, evaluation_result, output_file=None):
    """
    生成评估报告
    
    Args:
        scenario_data (dict): 事故场景数据
        api_response (dict): API响应
        evaluation_result (dict): 评估结果
        output_file (str): 输出文件路径
        
    Returns:
        str: 报告内容
    """
    # 提取模型响应文本（使用.get()防御性访问）
    choices = api_response.get("choices", [])
    if choices and len(choices) > 0:
        first_choice = choices[0]
        message = first_choice.get("message", {})
        model_response = message.get("content", "API响应缺少content字段")
    elif "error" in api_response:
        model_response = f"API调用失败: {api_response.get('error', '未知错误')}"
    else:
        model_response = "无法解析API响应"
    
    # 提取评估结果各字段（使用.get()防御性访问）
    total_score = evaluation_result.get('total_score', 0)
    summary = evaluation_result.get('summary', {})
    conclusion = summary.get('conclusion', '无结论')
    strengths = summary.get('strengths', [])
    weaknesses = summary.get('weaknesses', [])
    recommendations = summary.get('recommendations', [])
    
    diagnostic = evaluation_result.get('diagnostic_accuracy', {})
    diag_score = diagnostic.get('score', 0)
    diag_analysis = diagnostic.get('analysis', '无分析')
    diag_keywords = diagnostic.get('keywords_found', [])
    
    reasoning = evaluation_result.get('reasoning_quality', {})
    reason_score = reasoning.get('score', 0)
    reason_analysis = reasoning.get('analysis', '无分析')
    reason_steps = reasoning.get('steps_found', 0)
    reason_connectors = reasoning.get('connectors_found', 0)
    reason_length = reasoning.get('response_length', 0)
    
    solution = evaluation_result.get('solution_quality', {})
    sol_score = solution.get('score', 0)
    sol_analysis = solution.get('analysis', '无分析')
    sol_measures = solution.get('specific_measures_found', 0)
    
    # 提取场景数据（使用.get()防御性访问）
    accident_summary = scenario_data.get('accident_summary', {})
    acc_time = accident_summary.get('time', '未知')
    acc_scope = accident_summary.get('scope', '未知')
    acc_symptom = accident_summary.get('symptom', '未知')
    acc_trigger = accident_summary.get('trigger', '未知')
    acc_history = accident_summary.get('history', '无')
    
    oracle_data = scenario_data.get('oracle', {})
    jvm_data = scenario_data.get('jvm', {})
    network_data = scenario_data.get('network', {})
    
    # 生成报告内容
    report = f"""# Qwen235B MES巡检推理能力评估报告

**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 执行摘要

**总体评分**: {total_score}/5.0

**结论**: {conclusion}

## 事故场景概述

**事故时间**: {acc_time}

**影响范围**: {acc_scope}

**问题症状**: {acc_symptom}

**触发条件**: {acc_trigger}

**历史记录**: {acc_history}

## 模拟巡检数据

### Oracle数据库检查
```json
{format_json(oracle_data)}
```

### JVM应用检查
```json
{format_json(jvm_data)}
```

### 网络检查
```json
{format_json(network_data)}
```

## 模型推理响应

```
{model_response}
```

## 详细评估

### 1. 诊断准确性 (权重: 40%)

**评分**: {diag_score}/5

**分析**: {diag_analysis}

**发现的关键词**: {', '.join(diag_keywords) if diag_keywords else '无'}

### 2. 推理过程质量 (权重: 30%)

**评分**: {reason_score}/5

**分析**: {reason_analysis}

**推理步骤数**: {reason_steps}

**逻辑连接词数**: {reason_connectors}

**响应长度**: {reason_length} 字符

### 3. 解决方案建议 (权重: 30%)

**评分**: {sol_score}/5

**分析**: {sol_analysis}

**具体措施提及数**: {sol_measures}

## 总体评估

**加权总分计算**:
- 诊断准确性: {diag_score} × 0.4 = {diag_score * 0.4}
- 推理过程质量: {reason_score} × 0.3 = {reason_score * 0.3}
- 解决方案建议: {sol_score} × 0.3 = {sol_score * 0.3}
- **总分**: {total_score}

## 结论与建议

**结论**: {conclusion}

**优势**:
{format_list(strengths)}

**不足**:
{format_list(weaknesses)}

**建议**:
{format_list(recommendations)}

## 附录

### API调用信息
- **模型**: Qwen3-235B-A22B-w8a8
- **API端点**: https://ai-pool.evebattery.com/v1/chat/completions
- **最大token数**: 2000
- **温度参数**: 0.7

---
*本报告由Qwen235B MES巡检推理能力评估脚本自动生成*
"""
    
    # 保存到文件
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"报告已保存到: {output_file}")
    
    return report


def format_json(data):
    """格式化JSON数据"""
    import json
    return json.dumps(data, indent=2, ensure_ascii=False)


def format_list(items):
    """格式化列表"""
    if not items:
        return "- 无"
    return "\n".join(f"- {item}" for item in items)


if __name__ == "__main__":
    # 测试报告生成
    test_scenario = {
        "oracle": {"status": "critical"},
        "jvm": {"status": "critical"},
        "network": {"status": "critical"},
        "accident_summary": {
            "time": "2026-05-28 11:00",
            "scope": "集群大规模爆发",
            "symptom": "JDBC Connection reset",
            "trigger": "发布代码时触发",
            "history": "历史记录"
        }
    }
    
    test_api_response = {
        "choices": [
            {
                "message": {
                    "content": "测试响应内容"
                }
            }
        ]
    }
    
    test_evaluation = {
        "total_score": 4.0,
        "diagnostic_accuracy": {"score": 4, "analysis": "测试分析", "keywords_found": ["dns"]},
        "reasoning_quality": {"score": 4, "analysis": "测试分析", "steps_found": 3, "connectors_found": 2, "response_length": 100},
        "solution_quality": {"score": 4, "analysis": "测试分析", "specific_measures_found": 3},
        "summary": {
            "conclusion": "良好",
            "strengths": ["优势1"],
            "weaknesses": ["不足1"],
            "recommendations": ["建议1"]
        }
    }
    
    report = generate_evaluation_report(test_scenario, test_api_response, test_evaluation, "test_report.md")
    print("测试报告已生成")
