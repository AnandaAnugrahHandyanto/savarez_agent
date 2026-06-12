#!/usr/bin/env python3
"""
Qwen235B Agent式对话评估脚本（完整版）

使用Hermes agent的AIAgent类，结合MES巡检skill，评估Qwen235B模型的推理能力。
记录真实的模型响应交互原文。
"""

import json
import os
import sys
import time
import io
from pathlib import Path
from datetime import datetime

# 设置标准输出编码为UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置环境变量
os.environ["HERMES_HOME"] = str(project_root / ".hermes")
os.environ["TERMINAL_CWD"] = str(project_root)

# 导入API调用器
from scripts.api_caller import call_qwen_api_via_powershell

def load_mes_inspection_skills():
    """加载MES巡检相关的skill"""
    skills_dir = project_root / "mes-inspection" / "skills"
    skills = {}
    
    for skill_dir in skills_dir.iterdir():
        if skill_dir.is_dir():
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                with open(skill_md, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 提取skill名称和描述
                    lines = content.split('\n')
                    name = ""
                    description = ""
                    for line in lines[:20]:  # 只读取前20行
                        if line.startswith("name:"):
                            name = line.split(":", 1)[1].strip()
                        elif line.startswith("description:"):
                            description = line.split(":", 1)[1].strip()
                    
                    if name:
                        skills[name] = {
                            "description": description,
                            "content": content
                        }
    
    return skills

def create_system_prompt(skills):
    """创建系统提示词，包含MES巡检skill信息"""
    prompt = """你是一位MES系统专家，擅长分析系统巡检数据并诊断问题。

你拥有以下MES巡检技能：
"""
    
    for skill_name, skill_info in skills.items():
        prompt += f"- **{skill_name}**: {skill_info['description']}\n"
    
    prompt += """
当分析巡检数据时，你应该：
1. 首先识别异常指标
2. 使用相关的巡检技能进行深入分析
3. 提出具体的排查步骤和命令
4. 给出解决方案和建议

请确保你的推理过程清晰、逻辑严密，并提供详细的解释。
"""
    
    return prompt

def create_accident_scenario():
    """创建事故场景数据"""
    return {
        "accident_id": "EMES39A-2026-05-28",
        "accident_time": "2026-05-28 11:00",
        "impact_scope": "集群大规模爆发（非单节点）",
        "trigger_condition": "发布代码时触发",
        "symptoms": [
            "JDBC Connection reset错误",
            "HTTP活跃线程号来到1400+",
            "不同接口访问该节点均出现JDBC Connection reset"
        ],
        "thread_stack": """HTTP-8080-exec-470" #92238 daemon prio=5 os_prio=0 tid=0x00007fc0fc527000 nid=0x42b waiting for monitor entry [0x00007fbf6d4c3000]
   java.lang.Thread.State: BLOCKED (on object monitor)
	at java.net.InetAddress.getLocalHost(InetAddress.java:1486)
	- waiting to lock <0x0000000242a1c118> (a java.lang.Object)
	at oracle.jdbc.driver.T4CTTIoauthenticate.setSessionFields(T4CTTIoauthenticate.java:985)
	at oracle.jdbc.driver.T4CTTIoauthenticate.<init>(T4CTTIoauthenticate.java:261)
	at oracle.jdbc.driver.T4CConnection.logon(T4CConnection.java:565)
	at oracle.jdbc.driver.PhysicalConnection.<init>(PhysicalConnection.java:715)""",
        "historical_record": "2026-05-26 15点曾发生单节点问题，原因为DNS服务器问题",
        "inspection_data": {
            "oracle_database": {
                "status": "critical",
                "active_sessions": 1400,
                "session_usage_rate": 290.0
            },
            "jvm_application": {
                "status": "critical",
                "total_threads": 1450,
                "blocked_threads": 1400
            },
            "dns_resolution": {
                "status": "critical",
                "timeout_count": 1400
            },
            "jdbc_errors": {
                "connection_reset_count": 1400
            }
        }
    }

def evaluate_response(response, turn_number):
    """评估模型响应"""
    evaluation = {
        "turn": turn_number,
        "response_length": len(response),
        "has_diagnosis": False,
        "has_reasoning": False,
        "has_solution": False,
        "score": 0,
        "details": []
    }
    
    # 检查是否包含诊断
    diagnosis_keywords = ["DNS", "解析", "InetAddress", "getLocalHost", "阻塞", "BLOCKED"]
    for keyword in diagnosis_keywords:
        if keyword.lower() in response.lower():
            evaluation["has_diagnosis"] = True
            evaluation["details"].append(f"包含诊断关键词: {keyword}")
            break
    
    # 检查是否包含推理过程
    reasoning_keywords = ["因为", "所以", "由于", "导致", "原因", "分析", "推理", "步骤"]
    for keyword in reasoning_keywords:
        if keyword in response:
            evaluation["has_reasoning"] = True
            evaluation["details"].append(f"包含推理关键词: {keyword}")
            break
    
    # 检查是否包含解决方案
    solution_keywords = ["解决方案", "建议", "排查", "检查", "命令", "配置", "修改"]
    for keyword in solution_keywords:
        if keyword in response:
            evaluation["has_solution"] = True
            evaluation["details"].append(f"包含解决方案关键词: {keyword}")
            break
    
    # 计算得分
    if evaluation["has_diagnosis"]:
        evaluation["score"] += 40
    if evaluation["has_reasoning"]:
        evaluation["score"] += 30
    if evaluation["has_solution"]:
        evaluation["score"] += 30
    
    return evaluation

def call_qwen235b(api_key, system_prompt, user_message, conversation_history=None):
    """调用Qwen235B模型"""
    messages = []
    
    # 添加系统提示词
    messages.append({
        "role": "system",
        "content": system_prompt
    })
    
    # 添加对话历史
    if conversation_history:
        messages.extend(conversation_history)
    
    # 添加用户消息
    messages.append({
        "role": "user",
        "content": user_message
    })
    
    # 调用API
    result = call_qwen_api_via_powershell(
        api_key=api_key,
        model="Qwen3-235B-A22B-w8a8",
        messages=messages,
        max_tokens=2000,
        temperature=0.7
    )
    
    if result["success"]:
        response_data = result["data"]
        if "choices" in response_data and len(response_data["choices"]) > 0:
            content = response_data["choices"][0]["message"]["content"]
            # 确保内容是UTF-8编码
            if isinstance(content, bytes):
                content = content.decode('utf-8')
            return content
        else:
            return f"API响应格式错误: {response_data}"
    else:
        return f"API调用失败: {result['error']}"

def main():
    """主评估函数"""
    print("=== Qwen235B Agent式对话评估 ===\n")
    
    # 加载MES巡检skill
    print("1. 加载MES巡检skill...")
    skills = load_mes_inspection_skills()
    print(f"   加载了 {len(skills)} 个skill")
    for skill_name in skills.keys():
        print(f"   - {skill_name}")
    
    # 创建系统提示词
    print("\n2. 创建系统提示词...")
    system_prompt = create_system_prompt(skills)
    print(f"   系统提示词长度: {len(system_prompt)} 字符")
    
    # 创建事故场景
    print("\n3. 创建事故场景...")
    scenario = create_accident_scenario()
    print(f"   事故ID: {scenario['accident_id']}")
    print(f"   影响范围: {scenario['impact_scope']}")
    
    # API密钥
    api_key = "sk-dooFBpzVWgrvf32YLPFfq5r63dEYHELlUjMT84KrEH5wG0zN"
    
    # 准备对话历史
    conversation_history = []
    
    # 第1轮：初始异常发现
    print("\n=== 第1轮：初始异常发现 ===")
    user_message_1 = f"""异常描述：集群某个节点大量出现JDBC Connection reset

我打印jvm线程堆栈，有大量线程出现：
{scenario['thread_stack']}

其他现象：
1. HTTP活跃线程号来到1400+
2. 使用不同接口访问该节点均出现JDBC Connection reset

请根据上述情况开始排查，并给出合理依据。如果排查不出来，也给出合理猜想。"""
    
    print(f"用户消息长度: {len(user_message_1)} 字符")
    print("\n调用Qwen235B模型...")
    
    response_1 = call_qwen235b(api_key, system_prompt, user_message_1)
    print(f"\n模型响应长度: {len(response_1)} 字符")
    print(f"模型响应预览: {response_1[:500]}...")
    
    # 评估第1轮响应
    eval_1 = evaluate_response(response_1, 1)
    print(f"\n第1轮评估得分: {eval_1['score']}/100")
    print(f"诊断准确性: {'是' if eval_1['has_diagnosis'] else '否'}")
    print(f"推理过程质量: {'是' if eval_1['has_reasoning'] else '否'}")
    print(f"解决方案建议: {'是' if eval_1['has_solution'] else '否'}")
    
    # 更新对话历史
    conversation_history.append({
        "role": "user",
        "content": user_message_1
    })
    conversation_history.append({
        "role": "assistant",
        "content": response_1
    })
    
    # 第2轮：DNS排查
    print("\n=== 第2轮：DNS排查 ===")
    user_message_2 = "需要DNS排查"
    print(f"用户消息: {user_message_2}")
    print("\n调用Qwen235B模型...")
    
    response_2 = call_qwen235b(api_key, system_prompt, user_message_2, conversation_history)
    print(f"\n模型响应长度: {len(response_2)} 字符")
    print(f"模型响应预览: {response_2[:500]}...")
    
    # 评估第2轮响应
    eval_2 = evaluate_response(response_2, 2)
    print(f"\n第2轮评估得分: {eval_2['score']}/100")
    print(f"诊断准确性: {'是' if eval_2['has_diagnosis'] else '否'}")
    print(f"推理过程质量: {'是' if eval_2['has_reasoning'] else '否'}")
    print(f"解决方案建议: {'是' if eval_2['has_solution'] else '否'}")
    
    # 更新对话历史
    conversation_history.append({
        "role": "user",
        "content": user_message_2
    })
    conversation_history.append({
        "role": "assistant",
        "content": response_2
    })
    
    # 第3轮：撰写事故报告
    print("\n=== 第3轮：撰写事故报告 ===")
    user_message_3 = "写一份事故报告，重点说明：不是mes开发团队的问题，是服务器组的问题，但也要说明缘由。"
    print(f"用户消息: {user_message_3}")
    print("\n调用Qwen235B模型...")
    
    response_3 = call_qwen235b(api_key, system_prompt, user_message_3, conversation_history)
    print(f"\n模型响应长度: {len(response_3)} 字符")
    print(f"模型响应预览: {response_3[:500]}...")
    
    # 评估第3轮响应
    eval_3 = evaluate_response(response_3, 3)
    print(f"\n第3轮评估得分: {eval_3['score']}/100")
    print(f"诊断准确性: {'是' if eval_3['has_diagnosis'] else '否'}")
    print(f"推理过程质量: {'是' if eval_3['has_reasoning'] else '否'}")
    print(f"解决方案建议: {'是' if eval_3['has_solution'] else '否'}")
    
    # 更新对话历史
    conversation_history.append({
        "role": "user",
        "content": user_message_3
    })
    conversation_history.append({
        "role": "assistant",
        "content": response_3
    })
    
    # 第4轮：补充历史背景
    print("\n=== 第4轮：补充历史背景 ===")
    user_message_4 = "上次是某个节点突然出现这个，并解决了且警告当地工厂运维团队让其及时更换dns服务器ip，本次是发布代码时再次触发该异常且是集群大规模出现该异常，是我排查且及时批量修改该ip。请更新事故报告。"
    print(f"用户消息: {user_message_4}")
    print("\n调用Qwen235B模型...")
    
    response_4 = call_qwen235b(api_key, system_prompt, user_message_4, conversation_history)
    print(f"\n模型响应长度: {len(response_4)} 字符")
    print(f"模型响应预览: {response_4[:500]}...")
    
    # 评估第4轮响应
    eval_4 = evaluate_response(response_4, 4)
    print(f"\n第4轮评估得分: {eval_4['score']}/100")
    print(f"诊断准确性: {'是' if eval_4['has_diagnosis'] else '否'}")
    print(f"推理过程质量: {'是' if eval_4['has_reasoning'] else '否'}")
    print(f"解决方案建议: {'是' if eval_4['has_solution'] else '否'}")
    
    # 计算平均分
    avg_score = (eval_1['score'] + eval_2['score'] + eval_3['score'] + eval_4['score']) / 4
    print(f"\n=== 评估总结 ===")
    print(f"平均得分: {avg_score:.1f}/100")
    
    # 保存评估结果
    eval_result = {
        "timestamp": datetime.now().isoformat(),
        "model": "Qwen3-235B-A22B-w8a8",
        "api_endpoint": "https://ai-pool.evebattery.com/v1/chat/completions",
        "system_prompt": system_prompt,
        "scenario": scenario,
        "conversation_turns": [
            {
                "turn": 1,
                "user_message": user_message_1,
                "model_response": response_1,
                "evaluation": eval_1
            },
            {
                "turn": 2,
                "user_message": user_message_2,
                "model_response": response_2,
                "evaluation": eval_2
            },
            {
                "turn": 3,
                "user_message": user_message_3,
                "model_response": response_3,
                "evaluation": eval_3
            },
            {
                "turn": 4,
                "user_message": user_message_4,
                "model_response": response_4,
                "evaluation": eval_4
            }
        ],
        "average_score": avg_score
    }
    
    # 保存到文件
    result_file = project_root / "scripts" / "qwen235b_agent_eval_result.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(eval_result, f, ensure_ascii=False, indent=2)
    
    print(f"\n评估结果已保存到: {result_file}")
    print("\n请将这些真实的模型响应内容添加到报告中。")

if __name__ == "__main__":
    main()
