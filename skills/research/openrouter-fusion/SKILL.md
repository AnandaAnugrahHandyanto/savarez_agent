---
name: openrouter-fusion
description: >
  OpenRouter Fusion 評審團 — 多模型審議流程。用於核實聲明、高風險研究、模型 benchmark 驗證、
  多來源矛盾時的交叉比對。觸發方式：/fusion <prompt> 或自然語言關鍵字。
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [fusion, openrouter, verification, research, multi-model]
    requires_env: [OPENROUTER_API_KEY]
---

# OpenRouter Fusion 評審團

Fusion 是 OpenRouter 的 bounded multi-model deliberation pipeline。一組廉價模型（panel）各自回答同一個問題，再由一個高階模型（judge）整合出最終結論。

## 架構

```
使用者 prompt
    ↓
┌─────────────────────────────────────────────┐
│  Panel（budget preset）                      │
│  • ~google/gemini-flash-latest              │
│  • deepseek/deepseek-v3.2                   │
│  • ~moonshotai/kimi-latest                  │
│                                             │
│  各自獨立回答 + 可呼叫 web_search/web_fetch  │
└─────────────┬───────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│  Judge（合成模型）                            │
│  • ~anthropic/claude-opus-latest             │
│                                             │
│  綜合 panel 答案，給出最終 verdict            │
└─────────────┬───────────────────────────────┘
              ↓
        最終 fused answer
```

## 何時用 Fusion

| 場景 | 範例 |
|------|------|
| 文章/聲明核實 | 「核實這篇文的內容」「這是真的嗎」 |
| 模型 benchmark 聲明 | 「GPT-5.5 真的打敗 Opus 了嗎」 |
| 高風險技術判斷 | 「這個 PCB 製程參數合理嗎」 |
| 多來源矛盾 | 「三篇論文說法不一樣，哪個對」 |
| 投資/市場分析 | 「這支股票分析報告可信嗎」 |
| 供應鏈/合規驗證 | 「這個 RoHS 聲明有沒有問題」 |

## 何時不用 Fusion

| 場景 | 原因 |
|------|------|
| 一般聊天 | 殺雞用牛刀，浪費 API 額度 |
| 私密/敏感資料 | Fusion 透過 OpenRouter 外部 API，不適合公司內部機密 |
| 本地工具可驗證 | 能用 `terminal`、`browser`、`web_search` 直接查的就不用 |
| 純數學計算 | 模型不擅長精確計算，用 code_execution |
| 時效性極高的即時資訊 | web_search 更快，Fusion 延遲 10-30 秒 |

## 觸發方式

### 1. 明確指令
```
/fusion <prompt>
```

### 2. 自然語言觸發（Hermes agent 判斷）
當使用者說出以下關鍵字時，agent 應主動考慮使用 `openrouter_fusion` tool：

- 「核實」「查證」「驗證」「fact check」
- 「評審團」「多模型」「fusion」
- 「可信嗎」「真的嗎」「有沒有問題」
- 「交叉比對」「不同來源怎麼說」

### 3. Agent 自主判斷
當任務同時滿足以下條件時，agent 可自行決定使用：
- 聲明涉及多個不確定來源
- 錯誤成本高（投資、合規、安全）
- 使用者顯然需要高可信度答案

## Presets

| Preset | Panel | Judge | 適用場景 |
|--------|-------|-------|----------|
| `budget`（預設） | Gemini Flash + DeepSeek V3.2 + Kimi | Claude Opus | 日常核實、成本敏感 |
| `quality` | OpenRouter 預設 | OpenRouter 預設 | 高品質需求 |
| `custom` | 自定 1-8 個模型 | 可指定 | 特定領域驗證 |

## 回覆格式

Fusion 回覆應包含：

```
🧬 **Fusion verdict** · `12.3s` · judge: `claude-opus` · tokens: `42`

結論：可信 / 部分可信 / 不可信 / 無法核實

證據：
1. Panel model A 說...
2. Panel model B 說...
3. Panel model C 說...

Judge 綜合判斷：...
```

## 成本控制

- budget preset 使用 3 個便宜模型 + 1 個高階 judge
- 每次 Fusion 呼叫約消耗 500-2000 tokens（視 prompt 長度）
- 建議：一天不超過 20 次 Fusion 呼叫
- 如果 prompt 可以用單次 web_search 解決，優先用 web_search

## 程式碼位置

| 檔案 | 內容 |
|------|------|
| `tools/openrouter_fusion_tool.py` | Fusion tool 實作 + registry 註冊 |
| `hermes_cli/commands.py` | `/fusion` CommandDef |
| `gateway/run.py` | `_handle_fusion_command` gateway handler |
| `toolsets.py` | `fusion` toolset 定義 |
| `tests/tools/test_openrouter_fusion_tool.py` | tool 單元測試 |
| `tests/tools/test_fusion_command.py` | command + handler 測試 |
