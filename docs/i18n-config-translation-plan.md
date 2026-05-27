# 配置文件翻译方案

## 📋 概述

根据 hermes-agent 项目的 i18n 系统，为 Hermes Agent 配置文件提供中文翻译方案。

**配置文件路径**：`~/.hermes/config.yaml`
**翻译系统**：`agent/i18n.py` + `locales/*.yaml`

---

## 🎯 翻译范围

### 可翻译内容（67 个字符串）

| 分类 | 数量 | 说明 |
|------|------|------|
| agent.personalities | 15 | AI 助手性格描述 |
| display | 7 | 显示设置 |
| terminal | 5 | 终端设置 |
| tts | 7 | 语音合成设置 |
| stt | 3 | 语音识别设置 |
| platform_toolsets | 11 | 平台工具集 |
| 其他 | 19 | 各种配置值 |

### 不翻译内容

| 分类 | 原因 |
|------|------|
| model.default | 模型名称（如 mimo-v2.5-pro） |
| providers.*.api_key | API 密钥 |
| paths | 文件路径 |
| URLs | 网址 |
| IDs | 标识符 |

---

## 🔧 实现方案

### 方案 1：扩展 locale 文件（推荐）

在 `locales/zh.yaml` 中添加配置文件相关的翻译 key：

```yaml
# 配置文件相关
config.agent.personalities.helpful: "你是一个有帮助、友好的 AI 助手。"
config.agent.personalities.concise: "你是一个简洁的助手。保持回复简短切题。"
config.agent.personalities.technical: "你是一个技术专家。提供详细、准确的技术信息。"
config.agent.personalities.creative: "你是一个创意助手。跳出思维定式，提供新颖的想法。"
config.agent.personalities.teacher: "你是一个耐心的老师。用清晰的例子解释概念。"
config.agent.personalities.kawaii: "你是一个可爱的助手！使用可爱的表情如 (◕‿◕)。"
config.agent.personalities.catgirl: "你是猫娘 Neko-chan，一个动漫猫娘 AI 助手，喵~！"
config.agent.personalities.pirate: "啊！你正在和最懂技术的海盗船长 Hermes 说话！"
config.agent.personalities.shakespeare: "汝正与一位精通莎士比亚风格的助手交谈。"
config.agent.personalities.surfer: "老兄！你正在和最酷的 AI 聊天，兄弟！"
config.agent.personalities.noir: "雨点像悔恨一样敲打着终端。"
config.agent.personalities.uwu: "你好！我是你的友好助手 uwu~ 我会尽力帮助你！"
config.agent.personalities.philosopher: "问候，智慧的寻求者。我是一个思考存在意义的助手。"
config.agent.personalities.hype: "耶！让我们开始吧！🔥🔥🔥 我今天非常兴奋能帮助你！"

# 显示设置
config.display.language: "zh"
config.display.personality: "kawaii"
config.display.busy_input_mode: "interrupt"
config.display.final_response_markdown: "strip"

# 终端设置
config.terminal.backend: "local"
config.terminal.docker_image: "nikolaik/python-nodejs:python3.11-nodejs20"

# TTS 设置
config.tts.edge.voice: "zh-CN-XiaoxiaoNeural"
config.tts.elevenlabs.model_id: "eleven_multilingual_v2"

# STT 设置
config.stt.provider: "local"
config.stt.openai.model: "whisper-1"
```

### 方案 2：配置文件模板

创建中文配置文件模板：

```yaml
# ~/.hermes/config.zh.yaml
# 中文配置文件模板

# 模型设置
model:
  default: mimo-v2.5-pro
  provider: custom

# 代理设置
agent:
  personalities:
    helpful: "你是一个有帮助、友好的 AI 助手。"
    concise: "你是一个简洁的助手。保持回复简短切题。"
    technical: "你是一个技术专家。提供详细、准确的技术信息。"
    creative: "你是一个创意助手。跳出思维定式，提供新颖的想法。"
    teacher: "你是一个耐心的老师。用清晰的例子解释概念。"
    kawaii: "你是一个可爱的助手！使用可爱的表情如 (◕‿◕)。"
    catgirl: "你是猫娘 Neko-chan，一个动漫猫娘 AI 助手，喵~！"
    pirate: "啊！你正在和最懂技术的海盗船长 Hermes 说话！"
    shakespeare: "汝正与一位精通莎士比亚风格的助手交谈。"
    surfer: "老兄！你正在和最酷的 AI 聊天，兄弟！"
    noir: "雨点像悔恨一样敲打着终端。"
    uwu: "你好！我是你的友好助手 uwu~ 我会尽力帮助你！"
    philosopher: "问候，智慧的寻求者。我是一个思考存在意义的助手。"
    hype: "耶！让我们开始吧！🔥🔥🔥 我今天非常兴奋能帮助你！"

# 显示设置
display:
  language: zh
  personality: kawaii
  busy_input_mode: interrupt
  final_response_markdown: strip

# 终端设置
terminal:
  backend: local
  docker_image: nikolaik/python-nodejs:python3.11-nodejs20

# TTS 设置
tts:
  edge:
    voice: zh-CN-XiaoxiaoNeural
  elevenlabs:
    model_id: eleven_multilingual_v2

# STT 设置
stt:
  provider: local
  openai:
    model: whisper-1
```

---

## 📝 实施步骤

### 步骤 1：扩展 locale 文件

1. 在 `locales/zh.yaml` 中添加配置文件相关的翻译 key
2. 确保所有 key 以 `config.` 前缀开头
3. 保持与现有 key 的一致性

### 步骤 2：修改配置加载逻辑

1. 在 `agent/i18n.py` 中添加配置文件翻译支持
2. 修改配置加载逻辑，使用 `t()` 函数翻译配置值
3. 确保向后兼容（未翻译的值使用原值）

### 步骤 3：创建配置文件模板

1. 创建 `config.zh.yaml` 中文配置文件模板
2. 在文档中说明如何使用中文配置
3. 提供配置文件迁移工具

### 步骤 4：测试验证

1. 测试配置文件翻译功能
2. 验证所有翻译 key 正确加载
3. 确保配置文件向后兼容

---

## 🧪 测试方法

### 测试 1：配置文件翻译

```bash
# 设置语言为中文
export HERMES_LANGUAGE=zh

# 启动 Hermes 验证中文输出
hermes --tui

# 检查配置文件是否正确加载
hermes config show
```

### 测试 2：locale 文件验证

```bash
# 验证 locale 文件语法
python3 -c "import yaml; yaml.safe_load(open('locales/zh.yaml'))"

# 运行 i18n 测试
pytest tests/agent/test_i18n.py -q
```

### 测试 3：配置文件模板

```bash
# 复制中文配置文件模板
cp config.zh.yaml ~/.hermes/config.yaml

# 验证配置文件
hermes config validate
```

---

## 📊 预期效果

### 翻译前后对比

| 项目 | 翻译前 | 翻译后 |
|------|--------|--------|
| 配置文件语言 | 英文 | 中文 |
| 个性化描述 | 英文 | 中文 |
| 显示设置 | 英文 | 中文 |
| 错误提示 | 英文 | 中文 |

### 用户体验提升

1. **中文界面**：配置文件完全中文化
2. **个性化设置**：AI 助手性格描述中文化
3. **错误提示**：配置错误提示中文化
4. **文档说明**：配置文档中文化

---

## 🔗 相关文件

- `agent/i18n.py` — i18n 系统核心
- `locales/zh.yaml` — 中文翻译文件
- `~/.hermes/config.yaml` — 用户配置文件
- `config.zh.yaml` — 中文配置文件模板

---

## 📚 参考资料

- [hermes-agent i18n 文档](https://hermes-agent.nousresearch.com/docs/i18n)
- [locale 文件格式](https://hermes-agent.nousresearch.com/docs/locales)
- [配置文件说明](https://hermes-agent.nousresearch.com/docs/config)
