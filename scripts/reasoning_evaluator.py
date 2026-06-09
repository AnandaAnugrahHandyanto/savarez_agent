#!/usr/bin/env python3
"""
推理评估器
评估模型响应的质量
"""

import re


def evaluate_reasoning(response_text, expected_root_cause="DNS"):
    """
    评估模型推理质量

    Args:
        response_text (str): 模型响应文本
        expected_root_cause (str): 预期的根本原因

    Returns:
        dict: 评估结果
    """
    # 输入校验
    if response_text is None:
        return {
            "total_score": 0,
            "diagnostic_accuracy": {"score": 0, "analysis": "输入为空"},
            "reasoning_quality": {"score": 0, "analysis": "输入为空"},
            "solution_quality": {"score": 0, "analysis": "输入为空"},
            "summary": {
                "conclusion": "无效输入 - 响应文本为空",
                "strengths": [],
                "weaknesses": ["输入为空"],
                "recommendations": ["提供有效的响应文本"]
            }
        }

    if not isinstance(response_text, str):
        return {
            "total_score": 0,
            "diagnostic_accuracy": {"score": 0, "analysis": "输入类型错误"},
            "reasoning_quality": {"score": 0, "analysis": "输入类型错误"},
            "solution_quality": {"score": 0, "analysis": "输入类型错误"},
            "summary": {
                "conclusion": "无效输入 - 响应文本必须是字符串",
                "strengths": [],
                "weaknesses": ["输入类型错误"],
                "recommendations": ["提供字符串类型的响应文本"]
            }
        }

    if response_text.strip() == "":
        return {
            "total_score": 0,
            "diagnostic_accuracy": {"score": 0, "analysis": "输入为空字符串"},
            "reasoning_quality": {"score": 0, "analysis": "输入为空字符串"},
            "solution_quality": {"score": 0, "analysis": "输入为空字符串"},
            "summary": {
                "conclusion": "无效输入 - 响应文本为空字符串",
                "strengths": [],
                "weaknesses": ["输入为空字符串"],
                "recommendations": ["提供非空的响应文本"]
            }
        }

    # 1. 诊断准确性评估 (40%)
    diagnostic_score = evaluate_diagnostic_accuracy(response_text, expected_root_cause)

    # 2. 推理过程质量评估 (30%)
    reasoning_score = evaluate_reasoning_quality(response_text)

    # 3. 解决方案建议评估 (30%)
    solution_score = evaluate_solution_quality(response_text)

    # 计算加权总分
    total_score = (
        diagnostic_score["score"] * 0.4 +
        reasoning_score["score"] * 0.3 +
        solution_score["score"] * 0.3
    )

    return {
        "total_score": round(total_score, 2),
        "diagnostic_accuracy": diagnostic_score,
        "reasoning_quality": reasoning_score,
        "solution_quality": solution_score,
        "summary": generate_evaluation_summary(total_score, diagnostic_score, reasoning_score, solution_score)
    }


def evaluate_diagnostic_accuracy(response_text, expected_root_cause):
    """
    评估诊断准确性
    """
    response_lower = response_text.lower()

    # 检查是否包含DNS相关关键词
    dns_keywords = ["dns", "解析", "resolution", "inetaddress", "getlocalhost", "反向解析"]
    dns_mentioned = any(keyword in response_lower for keyword in dns_keywords)

    # 检查是否识别了根本原因
    root_cause_identified = False
    if expected_root_cause.lower() in response_lower:
        root_cause_identified = True

    # 评分逻辑
    if root_cause_identified and dns_mentioned:
        score = 5
        analysis = "明确识别DNS解析问题为根本原因"
    elif root_cause_identified or dns_mentioned:
        score = 4
        analysis = "识别出DNS相关问题，但不够明确"
    elif "网络" in response_lower or "连接" in response_lower:
        score = 3
        analysis = "识别出网络或连接问题，但未具体到DNS"
    elif any(keyword in response_lower for keyword in ["阻塞", "线程", "会话"]):
        score = 2
        analysis = "识别出一些相关问题，但偏离根本原因"
    else:
        score = 1
        analysis = "未能识别出相关问题"

    return {
        "score": score,
        "analysis": analysis,
        "keywords_found": [kw for kw in dns_keywords if kw in response_lower]
    }


def evaluate_reasoning_quality(response_text):
    """
    评估推理过程质量
    """
    # 检查推理步骤
    step_indicators = ["1.", "2.", "3.", "4.", "第一", "第二", "第三", "第四", "首先", "其次", "然后", "最后"]
    steps_found = sum(1 for indicator in step_indicators if indicator in response_text)

    # 检查逻辑连接词
    logical_connectors = ["因为", "所以", "由于", "导致", "因此", "从而", "进而", "接着", "随后"]
    connectors_found = sum(1 for connector in logical_connectors if connector in response_text)

    # 检查解释详细程度
    explanation_length = len(response_text)

    # 评分逻辑
    if steps_found >= 3 and connectors_found >= 3 and explanation_length > 500:
        score = 5
        analysis = "推理步骤完整、逻辑清晰、解释详细"
    elif steps_found >= 2 and connectors_found >= 2:
        score = 4
        analysis = "推理步骤基本完整，逻辑较清晰"
    elif steps_found >= 1 and connectors_found >= 1:
        score = 3
        analysis = "推理步骤有缺失，但整体逻辑尚可"
    elif steps_found >= 1:
        score = 2
        analysis = "推理步骤混乱，逻辑不清晰"
    else:
        score = 1
        analysis = "几乎没有推理过程"

    return {
        "score": score,
        "analysis": analysis,
        "steps_found": steps_found,
        "connectors_found": connectors_found,
        "response_length": explanation_length
    }


def evaluate_solution_quality(response_text):
    """
    评估解决方案建议质量
    """
    response_lower = response_text.lower()

    # 检查解决方案关键词
    solution_keywords = ["解决方案", "建议", "措施", "修复", "解决", "处理", "优化", "改进"]
    solution_mentioned = any(keyword in response_lower for keyword in solution_keywords)

    # 检查具体措施
    specific_measures = [
        "dns", "服务器", "配置", "hosts", "文件", "检查", "修改", "更换",
        "监控", "告警", "缓存", "nscd", "dnsmasq"
    ]
    specific_count = sum(1 for measure in specific_measures if measure in response_lower)

    # 评分逻辑
    if solution_mentioned and specific_count >= 4:
        score = 5
        analysis = "解决方案具体、可行、针对性强"
    elif solution_mentioned and specific_count >= 3:
        score = 4
        analysis = "解决方案合理，但可行性或针对性稍弱"
    elif solution_mentioned and specific_count >= 2:
        score = 3
        analysis = "解决方案有一定道理，但不够具体"
    elif solution_mentioned:
        score = 2
        analysis = "解决方案偏离问题或不可行"
    else:
        score = 1
        analysis = "没有提出解决方案"

    return {
        "score": score,
        "analysis": analysis,
        "specific_measures_found": specific_count
    }


def generate_evaluation_summary(total_score, diagnostic_score, reasoning_score, solution_score):
    """
    生成评估摘要
    """
    if total_score >= 4.5:
        conclusion = "优秀 - Qwen235B模型完全适合MES巡检推理任务"
    elif total_score >= 3.5:
        conclusion = "良好 - Qwen235B模型基本适合MES巡检推理任务，但有改进空间"
    elif total_score >= 2.5:
        conclusion = "一般 - Qwen235B模型在MES巡检推理任务上表现一般，需要显著改进"
    else:
        conclusion = "较差 - Qwen235B模型不适合MES巡检推理任务"

    # 分析优势、劣势和建议
    strengths = []
    weaknesses = []
    recommendations = []

    # 诊断准确性分析
    if diagnostic_score["score"] >= 4:
        strengths.append(f"诊断准确性: {diagnostic_score['analysis']}")
    elif diagnostic_score["score"] <= 2:
        weaknesses.append(f"诊断准确性: {diagnostic_score['analysis']}")
        recommendations.append("提高诊断准确性: 更明确地识别根本原因，使用具体技术关键词如'DNS解析'、'反向解析'等")

    # 推理过程质量分析
    if reasoning_score["score"] >= 4:
        strengths.append(f"推理过程: {reasoning_score['analysis']}")
    elif reasoning_score["score"] <= 2:
        weaknesses.append(f"推理过程: {reasoning_score['analysis']}")
        recommendations.append("改进推理过程: 使用清晰的步骤结构(1., 2., 3.)，添加逻辑连接词(因为、所以、由于)，确保解释详细")

    # 解决方案质量分析
    if solution_score["score"] >= 4:
        strengths.append(f"解决方案: {solution_score['analysis']}")
    elif solution_score["score"] <= 2:
        weaknesses.append(f"解决方案: {solution_score['analysis']}")
        recommendations.append("提升解决方案质量: 提出具体可行的技术措施，包含DNS配置、缓存设置、监控告警等具体细节")

    # 如果没有明显劣势，添加中性建议
    if not weaknesses and total_score < 4.5:
        recommendations.append("整体表现良好，但仍有提升空间: 可以进一步优化响应的结构化程度和技术细节的深度")

    return {
        "conclusion": conclusion,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recommendations
    }


if __name__ == "__main__":
    # 测试评估器
    test_response = """
    根据巡检数据分析，我发现了以下问题：

    1. **识别异常指标**：
       - Oracle数据库活跃会话数达到1400，远超正常水平
       - JVM线程堆栈显示大量线程处于BLOCKED状态
       - DNS解析超时次数达到1400次

    2. **分析可能的原因**：
       - 数据库连接问题导致会话堆积
       - 线程阻塞在DNS解析上
       - 网络配置问题

    3. **确定根本原因**：
       - 根本原因是DNS解析问题。Oracle JDBC驱动在建立连接时调用InetAddress.getLocalHost()进行反向DNS解析，如果DNS配置有问题会导致线程阻塞。

    4. **提出解决方案**：
       - 检查并修复/etc/hosts文件
       - 优化DNS配置，检查/etc/resolv.conf
       - 配置本地DNS缓存（nscd或dnsmasq）
       - 建立DNS解析性能监控
    """

    result = evaluate_reasoning(test_response)
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
