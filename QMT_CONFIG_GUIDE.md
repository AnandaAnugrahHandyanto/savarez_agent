# QMT 智能推送系统配置指南

## 数据源配置

### 1. Tushare（推荐用于历史数据）

注册并获取 token: https://tushare.pro/register

创建配置文件 `~/.hermes/config/tushare.json`:
```json
{
  "token": "your_tushare_token_here"
}
```

### 2. Akshare（免费，无需配置）

自动使用，无需配置。

### 3. QMT 远程 VM

如果有 Windows VM 运行 QMT，配置 SSH 访问：
```bash
# 在代码中使用
from qmt_data_source import RemoteVMDataSource
source = RemoteVMDataSource(
    host="192.168.1.100",
    user="Administrator",
    password="your_password"
)
```

## LLM 配置

### 1. OpenAI（推荐）

创建配置文件 `~/.hermes/config/openai.json`:
```json
{
  "api_key": "sk-your-openai-api-key",
  "model": "gpt-4o-mini",
  "base_url": "https://api.openai.com/v1"
}
```

或设置环境变量：
```bash
export OPENAI_API_KEY="sk-your-openai-api-key"
```

### 2. Anthropic Claude

创建配置文件 `~/.hermes/config/anthropic.json`:
```json
{
  "api_key": "sk-ant-your-anthropic-api-key",
  "model": "claude-3-5-sonnet-20241022"
}
```

或设置环境变量：
```bash
export ANTHROPIC_API_KEY="sk-ant-your-anthropic-api-key"
```

### 3. Ollama（本地免费）

安装 Ollama: https://ollama.ai/

下载模型：
```bash
ollama pull qwen2.5:14b
```

无需配置，自动使用 `http://localhost:11434`

### 4. 规则引擎（Fallback）

无需配置，当所有 LLM 不可用时自动使用。

## 优先级

### 数据源
1. 本地快照（最快）
2. Akshare（免费）
3. Tushare（需要 token）

### LLM
1. Ollama（本地免费）
2. OpenAI（推荐）
3. Anthropic（备选）
4. 规则引擎（Fallback）

## 测试配置

### 测试数据源
```bash
cd ~/.hermes/runtime-hermes-agent
python3 qmt_data_source.py test --source auto
```

### 测试 LLM
```bash
cd ~/.hermes/runtime-hermes-agent
python3 llm_client.py test --client auto
```

### 测试完整流程
```bash
cd ~/.hermes/runtime-hermes-agent
python3 qmt_smart_push_master.py
```

## 推荐配置

### 最小配置（免费）
- 数据源: Akshare
- LLM: 规则引擎

### 推荐配置
- 数据源: Tushare（历史数据）+ 本地快照（实时）
- LLM: Ollama（本地）或 OpenAI（云端）

### 专业配置
- 数据源: QMT 远程 VM（实时）+ Tushare（历史）
- LLM: OpenAI GPT-4 或 Claude 3.5 Sonnet
