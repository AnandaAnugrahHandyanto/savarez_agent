---
name: xlsx
description: Work with Microsoft Excel .xlsx files locally — inspect sheets, extract ranges, update cells, create workbooks, and handle lightweight spreadsheet automation with openpyxl/pandas. Use for file-based spreadsheets, not Google Sheets.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Excel, XLSX, Spreadsheet, openpyxl, Productivity]
    related_skills: [google-workspace]
---

# XLSX

Use this skill when the task involves local `.xlsx` spreadsheets rather than Google Sheets.

## When to use

- Read workbook/sheet names
- Extract rows, ranges, formulas, and basic formatting-relevant values
- Update cells or append rows
- Create a new workbook from structured data
- Convert sheets to CSV/Markdown for inspection

## Decision rule

1. **Local `.xlsx` file** → use this skill.
2. **Google Sheets URL / workspace spreadsheet** → use `google-workspace`.
3. **Need heavy analytics after reading workbook data** → load with `openpyxl` or `pandas`, then process with `execute_code`.
4. **Need low-level Office ZIP/XML surgery** → unpack/edit/repack, then validate output.

## Prerequisites

```bash
pip install openpyxl pandas
```

## Quick inspection

### List sheet names

```bash
python3 - <<'PY'
from openpyxl import load_workbook
wb = load_workbook('workbook.xlsx', data_only=False)
print(wb.sheetnames)
PY
```

### Print rows from a sheet

```bash
python3 - <<'PY'
from openpyxl import load_workbook
wb = load_workbook('workbook.xlsx', data_only=True)
ws = wb['Sheet1']
for row in ws.iter_rows(min_row=1, max_row=10, values_only=True):
    print(row)
PY
```

### Workbook summary

```bash
python3 - <<'PY'
from openpyxl import load_workbook
wb = load_workbook('workbook.xlsx', data_only=False)
for name in wb.sheetnames:
    ws = wb[name]
    print({'sheet': name, 'max_row': ws.max_row, 'max_col': ws.max_column})
PY
```

## Common write/edit patterns

### Update specific cells

```bash
python3 - <<'PY'
from openpyxl import load_workbook

wb = load_workbook('input.xlsx')
ws = wb['Sheet1']
ws['B2'] = 'Updated'
ws['C2'] = 42
wb.save('output.xlsx')
PY
```

### Append rows

```bash
python3 - <<'PY'
from openpyxl import load_workbook

rows = [
    ['Alice', 95, 'pass'],
    ['Bob', 88, 'pass'],
]
wb = load_workbook('input.xlsx')
ws = wb['Sheet1']
for row in rows:
    ws.append(row)
wb.save('output.xlsx')
PY
```

### Create workbook from scratch

```bash
python3 - <<'PY'
from openpyxl import Workbook

wb = Workbook()
ws = wb.active
ws.title = 'Report'
ws.append(['Name', 'Score'])
ws.append(['Alice', 95])
ws.append(['Bob', 88])
wb.save('report.xlsx')
PY
```

### Export a sheet to Markdown-ish preview

```bash
python3 - <<'PY'
from openpyxl import load_workbook

wb = load_workbook('workbook.xlsx', data_only=True)
ws = wb['Sheet1']
for row in ws.iter_rows(values_only=True):
    print('| ' + ' | '.join('' if v is None else str(v) for v in row) + ' |')
PY
```

### Export all sheets to CSV

```bash
python3 - <<'PY'
from openpyxl import load_workbook
import csv
from pathlib import Path

wb = load_workbook('workbook.xlsx', data_only=True)
outdir = Path('xlsx-export')
outdir.mkdir(exist_ok=True)
for name in wb.sheetnames:
    ws = wb[name]
    with (outdir / f'{name}.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        for row in ws.iter_rows(values_only=True):
            writer.writerow(row)
print(outdir)
PY
```

## Formula handling

- `data_only=False` → read formulas like `=SUM(A1:A10)`
- `data_only=True` → read cached computed values if Excel previously saved them
- `openpyxl` does **not** calculate formulas itself

Example:

```bash
python3 - <<'PY'
from openpyxl import load_workbook
wb = load_workbook('workbook.xlsx', data_only=False)
ws = wb['Sheet1']
print('formula:', ws['D2'].value)
wb2 = load_workbook('workbook.xlsx', data_only=True)
print('cached_value:', wb2['Sheet1']['D2'].value)
PY
```

## Low-level Office XML workflow

For unsupported edits or corruption inspection:

### Unpack XLSX

```bash
python3 - <<'PY'
import zipfile
from pathlib import Path

src = Path('input.xlsx')
out = Path('unpacked-xlsx')
out.mkdir(exist_ok=True)
with zipfile.ZipFile(src, 'r') as zf:
    zf.extractall(out)
print(out)
PY
```

Key files:

- `xl/workbook.xml` — workbook metadata / sheet registry
- `xl/worksheets/sheet*.xml` — sheet contents
- `xl/sharedStrings.xml` — shared string table
- `xl/styles.xml` — styles
- `docProps/core.xml` — core metadata

### Repack after edits

```bash
python skills/productivity/powerpoint/scripts/office/pack.py unpacked-xlsx output.xlsx --validate false
```

## Verification

Always reopen the workbook after edits:

```bash
python3 - <<'PY'
from openpyxl import load_workbook
wb = load_workbook('output.xlsx', data_only=False)
print({'sheets': wb.sheetnames, 'active': wb.active.title})
for name in wb.sheetnames:
    ws = wb[name]
    print(name, ws.max_row, ws.max_column)
PY
```

Check file exists and size:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('output.xlsx')
print({'exists': p.exists(), 'size': p.stat().st_size if p.exists() else 0})
PY
```

## Pitfalls

- `openpyxl` preserves many workbook features, but complex charts/macros/pivot internals can be fragile.
- Formula results may look stale if the workbook was not recalculated in Excel/LibreOffice before reading with `data_only=True`.
- Empty trailing rows/columns can still affect `max_row` / `max_column`; inspect actual non-empty cells if exact dimensions matter.
- For big sheets, use `read_only=True` when only extracting data.
- `.xls` is a different format — convert first if needed.

## Recommended Hermes tool pattern

- Use `execute_code` when you need loops, filtering, multi-sheet export, or JSON summaries.
- Use `terminal` for package install, libreoffice conversion, or bulk file handling.
- Use `read_file` to inspect exported CSV/Markdown previews instead of dumping huge workbook content directly.
- Verify by reopening the saved workbook with `openpyxl`.
