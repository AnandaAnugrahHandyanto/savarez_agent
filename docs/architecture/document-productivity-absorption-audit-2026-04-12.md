# 文档生产力吸收审计（DOCX / XLSX / PDF）

## 结论

本轮已把 `docx` 与 `xlsx` 作为 **Hermes-native productivity skills** 落地；`pdf` 不另起重复 skill，先保留为 `ocr-and-documents` + `nano-pdf` 的组合覆盖，并明确其剩余缺口。当前文档文件工作流从“提示式覆盖”升级为“有独立 skill、可直接执行、可复用”。

## 本轮盘查范围

- 线上 Skills Hub / 本地 skills catalog / 仓库 `skills/`
- 现有 productivity skills：
  - `ocr-and-documents`
  - `nano-pdf`
  - `powerpoint`
  - `google-workspace`
- Office 低层复用锚点：
  - `skills/productivity/powerpoint/scripts/office/pack.py`

## 盘查发现

### 1. DOCX 缺口
此前仅在 `ocr-and-documents/SKILL.md` 中一句带过：
- `For DOCX: use python-docx`

问题：
- 没有完整触发条件
- 没有结构化提取/编辑示例
- 没有验证闭环
- 没有低层 XML/pack 复用说明

### 2. XLSX 缺口
此前没有独立的 `.xlsx` 文件工作流 skill。
现状只有：
- `google-workspace` 处理 Google Sheets
- `powerpoint/scripts/office/pack.py` 已支持 `.xlsx` repack

问题：
- 本地 Excel 文件与 Google Sheets 被混在一起
- 没有 openpyxl 读写 SOP
- 没有公式/缓存值/导出预览说明

### 3. PDF 现状
PDF 目前分成两类：
- `ocr-and-documents`：抽取、OCR、拆分/合并/搜索示例
- `nano-pdf`：自然语言编辑 PDF

判断：
- **抽取/编辑主链已覆盖**
- 但“完整 PDF 工作流”仍缺：表单、水印、批量整理、页面旋转、签章等
- 因此本轮先不重复造一个薄壳 `pdf` skill，避免目录膨胀

## 本轮已落地改动

### 新增 skills

| Skill | 路径 | 作用 |
|---|---|---|
| `docx` | `skills/productivity/docx/SKILL.md` | Word 文档读取、编辑、生成、元数据检查、低层 Office XML 工作流 |
| `xlsx` | `skills/productivity/xlsx/SKILL.md` | Excel 文件读取、写入、导出、公式说明、低层 Office XML 工作流 |

### 复用策略

| 能力 | 复用锚点 | 说明 |
|---|---|---|
| DOCX 低层打包 | `skills/productivity/powerpoint/scripts/office/pack.py` | 已支持 `.docx` repack，可直接复用 |
| XLSX 低层打包 | `skills/productivity/powerpoint/scripts/office/pack.py` | 已支持 `.xlsx` repack，可直接复用 |
| PDF 文本/OCR | `skills/productivity/ocr-and-documents` | 保持单一抽取入口 |
| PDF 自然语言编辑 | `skills/productivity/nano-pdf` | 保持编辑专用入口 |

## 为什么本轮不新增 `pdf` skill

因为会造成重复：
- 抽取类内容与 `ocr-and-documents` 重叠
- 编辑类内容与 `nano-pdf` 重叠
- 目前尚未整理出足够独立、完整、非重复的 PDF 全流程 SOP

因此当前最合理形态是：
- **读/OCR → `ocr-and-documents`**
- **改字/局部编辑 → `nano-pdf`**
- 后续若补齐表单/水印/签章/批量整理，再考虑汇总成独立 `pdf` skill

## 当前吸收完成度判断

| 方向 | 状态 | 判断 |
|---|---|---|
| DOCX | 已吸收 | 从一句提示升级为完整 skill |
| XLSX | 已吸收 | 本地 Excel 文件工作流已独立成 skill |
| PDF | 部分吸收 | 主链已可用，但完整工作流仍未封装成单 skill |

## 剩余可继续吸收项

### P1
1. 为 `ocr-and-documents` 增补“PDF workflow map”，明确与 `nano-pdf` 的边界。✅ 已补到 skill，并新增 `skills/productivity/ocr-and-documents/scripts/build_pdf_workflow_map.py`
2. 将 `docx` / `xlsx` 补入 catalog 与站点目录（若当前构建链不是自动枚举）。✅ 已在站点目录中可见
3. 补一轮最小动态验证：用样例 `.docx` / `.xlsx` 实际读写并 reopen 校验。
4. 为 `agentmail` 与 `siyuan` 补运行时验收阶梯说明，明确当前机器为什么停在“未配置 / 缺 token”边界。✅ 已补到各自 skill

### P2
1. 若后续出现高频需求，再新增统一 `pdf` skill：
   - merge / split / rotate / watermark / forms / compress / extract annotations
2. 抽一层通用 Office ZIP unpack helper，避免 `docx/xlsx/pptx` 各自写 unzip 示例。

## 验收口径

本轮只宣称：
- `docx` / `xlsx` 已在 Hermes 自有 skills 中落地
- PDF 仍采用组合式覆盖，而非完整独立 skill
- 未改 openclaw 工作区本体
