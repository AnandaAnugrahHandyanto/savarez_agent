# Hermes 当前技能资产盘点与优化分析（2026-04-12）

## 一、结论

当前 Hermes 技能资产已经形成 **128 个本地可用技能** 的稳定底座：
- **built-in：80**
- **optional：48**
- 另有外部索引候选 **521**（Anthropic 16 + LobeHub 505），作为后续吸收池。

整体判断：
1. **数量已经够大，当前主要问题不是少，而是治理不均衡。**
2. **最需要优化的是“技能治理体系”**，不是继续盲目扩容。
3. 当前技能资产存在三类核心问题：
   - **测试覆盖明显不足**：本地 128 个技能，仅约 10 个有显式 tests/skills 回归覆盖。
   - **分类体系不统一**：`other` 类别过大，built-in 与 optional 的分类口径不完全一致。
   - **文档成熟度不均**：头部技能已有 Verification / Pitfalls / scripts / references，尾部技能仍偏“说明书式”，可执行性弱。
4. **下一阶段应从“吸收导向”切换到“治理导向”**：先标准化、可验证化、可索引化，再继续大规模吸收。

---

## 二、当前技能全量整理

### 2.1 总体规模

来自 `website/src/data/skills.json` 的当前统计：

- 总 skills：**649**
- 本地 skills：**128**
  - built-in：**80**
  - optional：**48**
- 外部 skills：**521**
  - Anthropic：**16**
  - LobeHub：**505**

### 2.2 built-in（80）

```text
apple-notes, apple-reminders, arxiv, ascii-art, ascii-video, audiocraft-audio-generation, axolotl, blogwatcher, claude-code, clip, codebase-inspection, codex, docx, dogfood, dspy, evaluating-llms-harness, excalidraw, find-nearby, findmy, fine-tuning-with-trl, gguf-quantization, gif-search, github-auth, github-code-review, github-issues, github-pr-workflow, github-repo-management, godmode, google-workspace, grpo-rl-training, guidance, heartmula, hermes-agent, himalaya, huggingface-hub, imessage, jupyter-live-kernel, linear, llama-cpp, llm-wiki, manim-video, mcporter, minecraft-modpack-server, modal-serverless-gpu, nano-pdf, native-mcp, notion, obliteratus, obsidian, ocr-and-documents, opencode, openhue, outlines, p5js, peft-fine-tuning, plan, pokemon-player, polymarket, popular-web-designs, powerpoint, pytorch-fsdp, requesting-code-review, research-paper-writing, segment-anything-model, serving-llms-vllm, skill-creator, songsee, songwriting-and-ai-music, stable-diffusion-image-generation, subagent-driven-development, systematic-debugging, test-driven-development, unsloth, webhook-subscriptions, weights-and-biases, whisper, writing-plans, xitter, xlsx, youtube-content
```

#### built-in 分类分布
- mlops: **22**
- other: **10**
- productivity: **8**
- creative: **7**
- software-development: **7**
- github: **6**
- research: **5**
- apple: **4**
- autonomous-ai-agents: **4**
- media: **4**
- gaming: **2**
- social-media: **1**

### 2.3 optional（48）

```text
1password, agentmail, base, bioinformatics, blackbox, blender-mcp, blogwatcher-a-share, canvas, chroma, distributed-llm-pretraining-torchtitan, docker-management, domain-intel, duckduckgo-search, faiss, fastmcp, gitnexus-explorer, hermes-atropos-environments, honcho, huggingface-accelerate, huggingface-tokenizers, inference-sh-cli, instructor, lambda-labs-gpu-cloud, llava, meme-generation, memento-flashcards, nemo-curator, neuroskill-bci, one-three-one-rule, openclaw-migration, optimizing-attention-flash, oss-forensics, parallel-cli, parallel-cli-a-share, pinecone, pytorch-lightning, qdrant-vector-search, qmd, qmd-a-share, scrapling, sherlock, simpo-training, siyuan, slime-rl-training, solana, sparse-autoencoder-training, telephony, tensorrt-llm
```

#### optional 分类分布
- mlops: **18**
- research: **10**
- other: **8**
- productivity: **4**
- security: **3**
- autonomous-ai-agents: **2**
- creative: **2**
- health: **1**

### 2.4 本地重点技能簇

#### A. 软件开发/代理执行链
- `systematic-debugging`
- `test-driven-development`
- `requesting-code-review`
- `writing-plans`
- `subagent-driven-development`
- `plan`
- `skill-creator`
- `claude-code` / `codex` / `opencode` / `hermes-agent`

**评价**：这是 Hermes 最成熟、最可复用的技能簇之一，流程性强，验证结构较完整。

#### B. 文档/办公生产力链
- `google-workspace`
- `notion`
- `linear`
- `powerpoint`
- `docx`
- `xlsx`
- `nano-pdf`
- `ocr-and-documents`
- optional: `canvas`, `siyuan`, `memento-flashcards`, `telephony`, `agentmail`

**评价**：最近吸收质量提升最快，但还缺统一的“文档工作流编排层”。

#### C. MCP / Agent Infra 链
- `native-mcp`
- `mcporter`
- optional: `fastmcp`
- `dogfood`
- `webhook-subscriptions`
- `honcho`

**评价**：这是 Hermes 差异化优势区，值得继续加码工程化与文档化。

#### D. ML / MLOps 大簇
- built-in + optional 合计占比最高
- 覆盖训练、推理、评测、向量库、模型、云、研究等子域

**评价**：广度很强，但技能间一致性和可验证性参差不齐，是治理成本最高的区块。

#### E. 研究 / 情报链
- `arxiv`, `blogwatcher`, `llm-wiki`, `polymarket`
- optional: `domain-intel`, `duckduckgo-search`, `gitnexus-explorer`, `parallel-cli`, `qmd`, `scrapling`, `bioinformatics`

**评价**：搜集能力丰富，但很多偏“单技能孤岛”，缺统一路由与组合模板。

---

## 三、现状分析：主要问题

### 3.1 测试覆盖严重不均
当前 `tests/skills/` 下显式存在的技能相关测试只有约 10 个：
- `test_telephony_skill.py`
- `test_extract_skills_index.py`
- `test_youtube_quiz.py`
- `test_memento_cards.py`
- `test_agentmail_skill.py`
- `test_siyuan_skill.py`
- `test_openclaw_migration.py`
- `test_stock_skill_helpers.py`
- `test_google_workspace_api.py`
- `test_google_oauth_setup.py`

**问题判断**：
- 128 个本地技能里，真正有显式回归保护的比例偏低。
- 当前回归保护更多集中在“最近新增/最近吸收”的技能，而不是全局系统性覆盖。

**影响**：
- 技能文档更新后容易悄悄失效。
- scripts / references / setup 步骤可能漂移，但 CI 不会报警。

### 3.2 分类体系存在“other”黑洞
统计里：
- built-in `other = 10`
- optional `other = 8`

**问题判断**：
- `other` 过大，说明技能 taxonomy 不够稳定。
- 可被更细分到 `mcp / infra / domain / migration / communication / security / devops` 的项，仍落在模糊类别下。

**影响**：
- 自动路由命中率变差。
- 技能目录浏览体验差。
- 后续吸收新技能时更难判断落类。

### 3.3 文档质量两极分化
成熟技能通常具备：
- Verification
- Pitfalls
- scripts/
- references/
- 真实命令
- 动态验收路径

例如：
- `docx`
- `xlsx`
- `dogfood`
- `agentmail`
- `siyuan`
- `telephony`
- `powerpoint`

但仍有不少技能更像：
- 工具介绍
- 能力摘要
- 缺少 runtime acceptance ladder
- 缺少 smoke test
- 缺少 failure modes

**问题判断**：
- 技能资产已经从“内容库”发展成“可执行操作系统”，但并非所有技能都按这个标准建设。

### 3.4 组合工作流不足
很多能力已经具备，但缺少组合层：
- 文档链：`ocr-and-documents + nano-pdf + docx + xlsx + powerpoint`
- 研究链：`duckduckgo-search + scrapling + qmd + llm-wiki + blogwatcher`
- MCP 链：`fastmcp + native-mcp + mcporter`
- QA 链：`dogfood + browser + console + evidence report`

**问题判断**：
- 现在的能力更像“强原子技能集合”，但缺少“默认编排套路”。
- 用户提复杂任务时，路由仍然较依赖模型临场判断，而不是沉淀好的工作流技能。

### 3.5 optional 与 built-in 的升级标准尚未制度化
目前 optional 中已有一批高价值技能接近 built-in 水平：
- `fastmcp`
- `honcho`
- `agentmail`
- `siyuan`
- `telephony`
- `docker-management`
- `duckduckgo-search`
- `domain-intel`

**问题判断**：
- 缺少“晋升标准”：什么条件下 optional 应进入 built-in。
- 导致高价值技能长期停留在 optional，发现率和默认利用率受限。

---

## 四、优化方向（按优先级）

### P0：建立技能治理基线
这是当前最重要的优化，不做这个，继续扩容只会增加维护债。

#### 建议 1：建立 Skill Quality Rubric（质量分级）
每个 skill 至少打 4 个维度：
- **D0 文档存在**
- **D1 有可执行命令/脚本**
- **D2 有 verification / pitfalls / setup 边界**
- **D3 有 pytest 或 smoke test**
- **D4 有 live/runtime 验收证据**

目标：
- 所有 built-in 至少到 **D2**
- 关键 built-in / 高价值 optional 至少到 **D3**
- 外部吸收候选必须先达到 **D2** 才能正式纳入目录

#### 建议 2：建立 skills CI 清单
最少要自动检查：
- frontmatter 完整性
- catalog 与技能目录一致性
- references/scripts 链接有效性
- 是否存在 Verification / Pitfalls 标题
- 可选 smoke test 是否存在

### P1：重构分类体系
#### 建议 3：清理 `other`
把 `other` 拆分优先迁出到：
- `mcp`
- `infra`
- `communication`
- `migration`
- `security`
- `agent-ops`

目标：
- `other` 控制在总量 **< 5%**。

#### 建议 4：built-in / optional 共用一套 taxonomy
否则站点目录、skills.json、路由逻辑会越来越乱。

### P1：建设组合型 workflow skills
#### 建议 5：新增少量高价值编排技能，而不是继续加原子技能
优先建议：
1. **document-workbench**
   - 路由 `pdf/docx/xlsx/pptx/ocr`
   - 吸收现有办公技能为统一入口
2. **research-pipeline**
   - 路由 `ddg + scrapling + qmd + llm-wiki + blogwatcher`
3. **mcp-builder**（Hermes-native）
   - 路由 `fastmcp + native-mcp + mcporter`
4. **webapp-testing-plus** 或直接增强 `dogfood`
   - 吸收 `webapp-testing` checklist / evidence schema

### P1：建立 optional → built-in 晋升机制
#### 建议 6：定义晋升条件
建议满足以下条件即可候选晋升：
- 最近 30 天高频使用 / 高频盘查命中
- 文档达到 D3
- 与 Hermes 核心工作流高度相关
- 非强凭据依赖或已有清晰 setup 边界

优先候选：
- `fastmcp`
- `honcho`
- `duckduckgo-search`
- `domain-intel`
- `docker-management`

### P2：补齐测试空白带
#### 建议 7：先给头部高价值技能补 smoke tests
优先顺序：
1. `docx`
2. `xlsx`
3. `ocr-and-documents`
4. `dogfood`
5. `fastmcp`
6. `docker-management`
7. `domain-intel`
8. `duckduckgo-search`
9. `powerpoint`
10. `mcporter` / `native-mcp`

### P2：增强索引与发现能力
#### 建议 8：在 `skills.json` 加更多治理字段
建议新增：
- `quality_tier`
- `has_tests`
- `has_verification_section`
- `has_pitfalls_section`
- `has_scripts`
- `has_references`
- `runtime_validated`
- `promotion_candidate`

这样后续盘查、站点筛选、自动推荐都会更强。

---

## 五、最值得立即执行的动作

### 立即动作 1
做一个 **skills inventory generator**：
- 自动扫描 `skills/`、`optional-skills/`
- 输出每个 skill 的：分类、来源、tests、scripts、references、verification、pitfalls、quality tier
- 生成 markdown + json 报表

### 立即动作 2
补一个 **skills governance 文档**：
- taxonomy 规则
- 晋升标准
- 最低文档标准
- 最低测试标准
- 吸收流程标准

### 立即动作 3
发起一轮 **P0 测试补齐**：
- `docx`
- `xlsx`
- `fastmcp`
- `dogfood`
- `domain-intel`
- `duckduckgo-search`

### 立即动作 4
开始做 **workflow 化吸收**，而不是继续收散技能：
- `mcp-builder`
- `document-workbench`
- `research-pipeline`

---

## 六、最终判断

Hermes 现在的技能资产已经不是“少”，而是**大而不齐**。
下一步最优策略不是继续追求数量，而是：

1. **先治理**：分类、测试、验收、索引标准化
2. **再编排**：把强原子技能组合成高价值工作流 skill
3. **最后再吸收**：只吸收能显著补 workflow 缺口的官方/外部能力

一句话：
**从“技能仓库”升级成“技能操作系统”。**
