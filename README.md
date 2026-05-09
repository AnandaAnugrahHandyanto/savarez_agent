# 🧠 ThinkCheck × Hermes — 水晶之心

> 为开源智能体 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 装上自我审视的“逻辑之眼”。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![ThinkCheck](https://img.shields.io/badge/ThinkCheck-3.0-orange.svg)](https://github.com/luoxuejian000/-thinkcheck-lib-)
[![Forked from Hermes](https://img.shields.io/badge/forked%20from-NousResearch%2Fhermes--agent-green.svg)](https://github.com/NousResearch/hermes-agent)

本项目是 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 的增强分支。它在保留原项目所有强大能力（自我进化、三层记忆、广泛模型支持）的基础上，深度集成了自研的 **ThinkCheck 3.0 推理评估引擎**。

**它的独特之处在于**：Hermes Agent 在生成文本后，可自动调用 ThinkCheck 进行“逻辑体检”，评估其推理质量（U统一性/D发展性/A对抗性/H和谐度），并给出通俗的改进建议。这使得“水晶之心”不止是一个能干的 Agent，更是一个能自我审视、持续进化的可靠伙伴。

---

## ✨ 与官方版本的核心区别

| 能力维度 | 官方 Hermes Agent | 🧠 水晶之心 (本仓库) |
| :--- | :--- | :--- |
| **推理质量评估** | ❌ 不支持 | ✅ 支持，提供U/D/A/H四维诊断报告 |
| **内容逻辑自检** | ❌ 不支持 | ✅ 支持，可自动发现并标注逻辑矛盾 |
| **概念漂移检测** | ❌ 不支持 | ✅ 支持，精准定位术语在不同上下文中的含义偏移 |
| **自我审视工具** | 无 | `thinkcheck_evaluate`，可被 Agent 自主调用 |

---

## 🧪 ThinkCheck 3.0 评估引擎

本仓库集成的 **ThinkCheck 3.0**，是一款基于晶脉哲学与谐振理论开发的AI推理质量诊断系统。

**四维评估指标**：
- **U (统一性)**：概念在文本中使用的语义一致性。
- **D (发展性)**：论证层次递进与新信息引入的节奏。
- **A (对抗性)**：文本内部逻辑矛盾的密度。
- **H (和谐度)**：综合前三项后得出的整体推理健康度。

**核心文件一览**：
- `thinkcheck_harmony/` — ThinkCheck 3.0 核心引擎的完整代码。
- `tools/thinkcheck_tool.py` — 将引擎注册为 Hermes Agent 可调用工具的入口。
- `demo_thinkcheck.py` — 可直接运行的测试脚本，直观展示诊断效果。

---

## 🚀 快速体验

### 1. 克隆仓库
```bash
git clone https://github.com/luoxuejian000/hermes-agent.git
cd hermes-agent
```

### 2. 安装依赖
```bash
# 安装 Hermes Agent 核心依赖
pip install -e .

# 安装 ThinkCheck 所需依赖
pip install sentence-transformers scikit-learn numpy
```

### 3. 运行演示脚本
```bash
python demo_thinkcheck.py
```
您将看到一段预设文本的完整 U/D/A/H 诊断结果和通俗解读。

### 4. 在 Hermes 对话中调用
启动 Hermes 后，直接向它发送：
> 请用 thinkcheck_evaluate 工具评估下面这段话的推理质量：
> "这个项目成本是100万元。实际上，这个项目的预算是200万元。"

Hermes 会返回 U/D/A/H 四维评估结果和通俗解读。

### 5. 作为 MCP 服务使用（可选）
将 `thinkcheck_mcp_server.py` 启动为 MCP 服务，可被 OpenClaw 等其他 Agent 框架调用。
详见 [ThinkCheck 主仓库](https://github.com/luoxuejian000/-thinkcheck-lib-)。

---

## 📁 项目结构（新增部分）

```
hermes-agent/
├── thinkcheck_harmony/          # ThinkCheck 3.0 核心评估引擎
│   ├── core.py                  # 和谐度计算引擎 (H = λU·U + λD·D - λA·A)
│   ├── evaluator.py             # 主评估器 HarmonyEvaluator
│   ├── concept_graph.py         # 概念关系图 (关系本体论实现)
│   ├── contradiction_detector.py # 矛盾检测器 (矛盾动力论实现)
│   ├── report.py                # 评估报告数据结构
│   ├── intervention/            # 矛盾捕获器模块
│   │   ├── term_alignment.py    # 术语共识工作坊
│   │   └── weight_negotiation.py # 权重协商会议
│   ├── presets/                 # 领域预设 (法律/医疗/金融/通用)
│   └── utils/                   # 工具模块 (嵌入模型、文本处理)
├── tools/
│   └── thinkcheck_tool.py       # Hermes 工具注册入口
├── demo_thinkcheck.py           # 集成演示脚本
├── demo_simple.py               # 简化版演示脚本
├── demo_output.py               # 输出测试脚本
└── test_import.py               # 导入测试脚本
```

---

## 📄 开源许可与致谢

本项目遵循 [MIT License](LICENSE)。
核心的自我进化与记忆系统由 [NousResearch](https://github.com/NousResearch) 的 Hermes Agent 驱动。
集成的评估引擎为独立自研的 [ThinkCheck 产品家族](https://github.com/luoxuejian000/-thinkcheck-lib-)。

---

## 🔗 相关项目

| 项目 | 说明 | 链接 |
| :--- | :--- | :--- |
| ThinkCheck 主仓库 | 包含 1.0 ~ 4.0 完整演进史 | [查看](https://github.com/luoxuejian000/-thinkcheck-lib-) |
| ThinkCheck Lite | 轻量版 AI 矛盾检测工具 | [查看](https://github.com/luoxuejian000/thinkcheck-lite) |
| ThinkCheck 3.0 SDK | 通用谐振评估 SDK | [查看](https://github.com/luoxuejian000/-thinkcheck-lib-/tree/3.0-harmony-sdk) |
| ThinkCheck 4.0 鸿蒙版 | 鸿蒙原生推理诊断引擎 | [查看](https://github.com/luoxuejian000/-thinkcheck-lib-/tree/4.0-harmony-competition) |
```
