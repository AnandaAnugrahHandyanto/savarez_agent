"""
ThinkCheck 工具 - 基于晶脉哲学与谐振理论
用于评估 AI 生成文本的推理质量
作者：李广好
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thinkcheck_harmony import HarmonyEvaluator

def evaluate_text(text: str) -> dict:
    evaluator = HarmonyEvaluator(domain="general")
    report = evaluator.evaluate(text)
    result = report.to_dict()
    h = result['H']
    if h > 0.6:
        verdict = "✅ 推理较为健康，逻辑自洽"
    elif h > 0.4:
        verdict = "⚠️ 存在一些逻辑问题，建议重点关注 U/A 指标"
    else:
        verdict = "❌ 推理质量较差，可能存在概念漂移或内在矛盾"
    result['verdict'] = verdict
    return result

from hermes.tools import tool

@tool(
    name="thinkcheck_evaluate",
    description="评估一段 AI 生成文本的推理质量。返回 U(统一性)、D(发展性)、A(对抗性)、H(和谐度) 四个指标，并给出通俗解读。"
)
def thinkcheck_tool(text: str) -> dict:
    return evaluate_text(text)