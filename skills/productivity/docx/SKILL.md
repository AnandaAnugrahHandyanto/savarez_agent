---
name: docx
description: Work with Microsoft Word .docx files locally — extract structured text, inspect tables and metadata, create or update documents with python-docx, and fall back to unpack/pack XML workflows when needed. Use for Word-specific reading/editing tasks instead of OCR.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Word, DOCX, Office, Documents, python-docx, Productivity]
    related_skills: [ocr-and-documents, powerpoint]
---

# DOCX

Use this skill when the task specifically involves `.docx` files: reading, extracting, editing, generating, or inspecting Word documents.

## When to use

- Read a local `.docx` without OCR
- Extract paragraphs, headings, tables, headers, footers, and core metadata
- Create or update a Word document programmatically
- Make targeted XML-level edits when `python-docx` is insufficient
- Validate a packed `.docx` after low-level edits

## Decision rule

1. **Need plain content or structured extraction?** Use `python-docx` first.
2. **Need simple edits / document generation?** Use `python-docx`.
3. **Need tracked low-level fixes or unsupported features?** Use Office XML unpack → edit → repack.
4. **Need OCR because the source is scanned PDF, not DOCX?** Use `ocr-and-documents` instead.

## Prerequisites

```bash
pip install python-docx lxml
```

Optional for tabular export:

```bash
pip install pandas
```

## Quick extraction

### Paragraph text

```bash
python3 - <<'PY'
from docx import Document

doc = Document('input.docx')
for i, p in enumerate(doc.paragraphs, 1):
    text = p.text.strip()
    if text:
        print(f'{i:03d}: {text}')
PY
```

### Tables

```bash
python3 - <<'PY'
from docx import Document

doc = Document('input.docx')
for t_idx, table in enumerate(doc.tables, 1):
    print(f'--- table {t_idx} ---')
    for row in table.rows:
        print(' | '.join(cell.text.strip() for cell in row.cells))
PY
```

### Core metadata

```bash
python3 - <<'PY'
from docx import Document

doc = Document('input.docx')
props = doc.core_properties
for key in ['author', 'title', 'subject', 'category', 'comments', 'created', 'modified']:
    print(f'{key}: {getattr(props, key)}')
PY
```

## Common write/edit patterns

### Create a new document

```bash
python3 - <<'PY'
from docx import Document

doc = Document()
doc.add_heading('Weekly Report', level=1)
doc.add_paragraph('Summary goes here.')
table = doc.add_table(rows=1, cols=2)
header = table.rows[0].cells
header[0].text = 'Metric'
header[1].text = 'Value'
for metric, value in [('Revenue', '$42k'), ('Users', '1280')]:
    row = table.add_row().cells
    row[0].text = metric
    row[1].text = value
doc.save('weekly-report.docx')
PY
```

### Replace text in paragraphs and table cells

```bash
python3 - <<'PY'
from docx import Document

src = 'input.docx'
out = 'output.docx'
replacements = {
    'Acme Corp': 'Acme Industries',
    'January 2026': 'February 2026',
}

doc = Document(src)
for p in doc.paragraphs:
    for old, new in replacements.items():
        if old in p.text:
            for run in p.runs:
                run.text = run.text.replace(old, new)
for table in doc.tables:
    for row in table.rows:
        for cell in row.cells:
            for old, new in replacements.items():
                if old in cell.text:
                    cell.text = cell.text.replace(old, new)
doc.save(out)
PY
```

### Read headings only

```bash
python3 - <<'PY'
from docx import Document

doc = Document('input.docx')
for p in doc.paragraphs:
    if p.style and p.style.name.startswith('Heading'):
        print(f'[{p.style.name}] {p.text.strip()}')
PY
```

## Low-level Office XML workflow

When `python-docx` can't express the needed change cleanly:

1. Copy the `.docx` to a temp workspace.
2. Unzip it to a directory.
3. Edit `word/document.xml` or related files.
4. Repack and validate.

### Unpack a DOCX

```bash
python3 - <<'PY'
import zipfile
from pathlib import Path

src = Path('input.docx')
out = Path('unpacked-docx')
out.mkdir(exist_ok=True)
with zipfile.ZipFile(src, 'r') as zf:
    zf.extractall(out)
print(out)
PY
```

Key files:

- `word/document.xml` — main body
- `word/styles.xml` — styles
- `word/header*.xml` / `word/footer*.xml` — headers/footers
- `docProps/core.xml` — core metadata
- `[Content_Types].xml` — content type declarations

### Repack after edits

Reuse the existing Office pack helper already in the repo:

```bash
python skills/productivity/powerpoint/scripts/office/pack.py unpacked-docx output.docx --original input.docx
```

If you don't have an original file for validation:

```bash
python skills/productivity/powerpoint/scripts/office/pack.py unpacked-docx output.docx --validate false
```

## Verification

Always verify separately from writing:

```bash
python3 - <<'PY'
from docx import Document

doc = Document('output.docx')
print('paragraphs', len(doc.paragraphs))
print('tables', len(doc.tables))
print('first_nonempty', next((p.text for p in doc.paragraphs if p.text.strip()), ''))
PY
```

Check file exists and is non-empty:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('output.docx')
print({'exists': p.exists(), 'size': p.stat().st_size if p.exists() else 0})
PY
```

## Pitfalls

- `paragraph.text = ...` can destroy run-level formatting; prefer run-wise replacement when formatting matters.
- Merged table cells may duplicate text unexpectedly; inspect row/cell output before bulk edits.
- `python-docx` does not fully support every Word feature (tracked changes, complex fields, some section/layout features).
- For low-level XML edits, keep namespace declarations intact or Word may repair/break the file.
- For scanned PDFs converted from Word, do **not** use this skill — route to `ocr-and-documents`.

## Recommended Hermes tool pattern

- Use `read_file` / `search_files` for evidence around generated helper code and docs.
- Use `execute_code` for extraction/transformation when the result needs filtering or looping.
- Use `terminal` for dependency checks / package installs / batch conversions.
- Verify the resulting `.docx` by reopening it with `python-docx` after edits.
