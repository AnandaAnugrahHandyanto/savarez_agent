# AgentMail / SiYuan / PDF Runtime Follow-up Audit（2026-04-12）

## 结论

本轮继续推进后，三条链路的状态已经清晰：

1. **AgentMail**：根因已确认——之前的超时不是 AgentMail 坏掉，而是我们把一个**长驻 stdio MCP server**误当成 `--help` 型 CLI 做探针；现已改成“启动后存活”探测，并补测试与文档。
2. **SiYuan**：已具备 token 预检、workspace 生成脚本、pytest 覆盖，但当前机器未注入 `SIYUAN_TOKEN`，无法做 live notebook/search 验收。
3. **PDF**：已把组合式工作流从“口头边界”升级为“skill 内工作流地图 + 可执行生成脚本”，当前无需重复造薄壳 `pdf` skill。
4. **DOCX / XLSX**：已完成 Hermes-native skill 落地，且已在当前机器完成最小 create→reopen 动态验收，不再只是目录存在。

## 实机证据

### AgentMail
```bash
python3 optional-skills/email/agentmail/scripts/check_agentmail.py
# 脚本可运行；live 配置状态取决于 runtime 配置与凭据
```

### SiYuan
```bash
python3 optional-skills/productivity/siyuan/scripts/check_siyuan.py
# {"ok": false, "error": "missing_siyuan_token", ...}
```

### PDF
```bash
python3 skills/productivity/ocr-and-documents/scripts/build_pdf_workflow_map.py
# {"ok": true, "output": "/tmp/hermes_pdf_workflow_map.json", "entrypoint_count": 4, "gap_count": 6}
```

### DOCX / XLSX
```bash
python3 - <<'PY'
from docx import Document
from openpyxl import Workbook, load_workbook
from pathlib import Path
base=Path('/tmp/hermes_office_verify')
base.mkdir(exist_ok=True)

p=base/'sample.docx'
d=Document()
d.add_heading('Hermes Verify', level=1)
d.add_paragraph('alpha')
t=d.add_table(rows=2, cols=2)
t.rows[0].cells[0].text='k'; t.rows[0].cells[1].text='v'
t.rows[1].cells[0].text='x'; t.rows[1].cells[1].text='1'
d.save(p)
d2=Document(p)
print({'docx_exists':p.exists(),'docx_size':p.stat().st_size,'docx_paragraphs':len(d2.paragraphs),'docx_tables':len(d2.tables),'docx_first':next((pp.text for pp in d2.paragraphs if pp.text.strip()),'')})

x=base/'sample.xlsx'
wb=Workbook(); ws=wb.active; ws.title='Data'; ws['A1']='metric'; ws['B1']='value'; ws['A2']='count'; ws['B2']=7; wb.save(x)
wb2=load_workbook(x,data_only=False)
ws2=wb2['Data']
print({'xlsx_exists':x.exists(),'xlsx_size':x.stat().st_size,'xlsx_sheets':wb2.sheetnames,'a1':ws2['A1'].value,'b2':ws2['B2'].value})
PY
# {'docx_exists': True, 'docx_size': 36761, 'docx_paragraphs': 2, 'docx_tables': 1, 'docx_first': 'Hermes Verify'}
# {'xlsx_exists': True, 'xlsx_size': 4860, 'xlsx_sheets': ['Data'], 'a1': 'metric', 'b2': 7}
```

### Regression
```bash
./.venv/bin/python -m pytest -q tests/skills/test_agentmail_skill.py tests/skills/test_siyuan_skill.py tests/skills/test_stock_skill_helpers.py
```

## 本轮落地改动

- `optional-skills/email/agentmail/SKILL.md`
  - 把 runtime acceptance ladder 从错误的 `--help` 探针，改成 stdio 长驻 server 验收口径
- `optional-skills/email/agentmail/scripts/check_agentmail.py`
  - 用“启动后存活 8 秒”替代 `npx agentmail-mcp --help` 假探针
- `tests/skills/test_agentmail_skill.py`
  - 重写 success/timeout 断言，并新增长驻进程探针单测
- `optional-skills/productivity/siyuan/SKILL.md`
  - 新增 runtime acceptance ladder
- `skills/productivity/ocr-and-documents/SKILL.md`
  - 新增 PDF Workflow Map
- `skills/productivity/ocr-and-documents/scripts/build_pdf_workflow_map.py`
  - 新增机器可执行工作流地图生成脚本
- `docs/architecture/document-productivity-absorption-audit-2026-04-12.md`
  - 更新剩余缺口与已完成项

## 当前仍缺什么

### P0
- AgentMail 真实 API key + Hermes 进程重启后的 `list_inboxes / create_inbox / send_message` 动态证据
- SiYuan 真实 token 环境下的 `createNotebook / createDocWithMd / fullTextSearchBlock` 动态证据

### P1
- `docx` / `xlsx` pytest 样例化验收（当前已完成 create→reopen 最小动态验收）
- PDF 高级缺口：watermark / forms / annotation / signing / batch normalization
- `mcp-builder` / `doc-coauthoring` / `webapp-testing` 的 Hermes-native 增量吸收

## 判断

当前 AgentMail 这条线已经从“错误失败”修正为“本地探针通过、live MCP 仍待 runtime 凭据环境验收”。
当前 SiYuan 处于“脚本与测试齐备，但凭据缺失”的明确边界。
当前 PDF 不该重复造 skill，而应继续补高级操作闭环。
当前 DOCX/XLSX 已经进入可验证状态，下一步只需把动态样例固化为测试资产。
