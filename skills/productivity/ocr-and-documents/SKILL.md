---
name: ocr-and-documents
description: "Extract text from PDFs and scanned documents."
version: 2.4.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [PDF, Documents, Research, Arxiv, Text-Extraction, OCR]
    related_skills: [powerpoint]
---

# PDF & Document Extraction

For DOCX: use `python-docx` (parses actual document structure, far better than OCR).
For PPTX: see the `powerpoint` skill (uses `python-pptx` with full slide/notes support).
This skill covers **PDFs and scanned documents**.

## Step 1: Remote URL Available?

If the document has a URL, **always try `web_extract` first**:

```
web_extract(urls=["https://arxiv.org/pdf/2402.03300"])
web_extract(urls=["https://example.com/report.pdf"])
```

This handles PDF-to-markdown conversion via Firecrawl with no local dependencies.

Only use local extraction when: the file is local, web_extract fails, or you need batch processing.

## Step 2: Choose Local Extractor

| Feature | LiteParse (`lit`, optional) | pymupdf (~25MB) | marker-pdf (~3-5GB) |
|---------|-----------------------------|-----------------|---------------------|
| **Text-based PDF** | ✅ fast, spatial JSON/text | ✅ | ✅ |
| **Scanned PDF (OCR)** | Optional OCR; tessdata may be required | ❌ | ✅ (90+ languages) |
| **Tables** | ✅ layout/bbox metadata | ✅ (basic) | ✅ (high accuracy) |
| **Equations / LaTeX** | ❌ | ❌ | ✅ |
| **Code blocks** | ❌ | ❌ | ✅ |
| **Forms** | ❌ | ❌ | ✅ |
| **Headers/footers removal** | ❌ | ❌ | ✅ |
| **Reading order detection** | Basic spatial ordering | ❌ | ✅ |
| **Images extraction** | Page screenshots | ✅ (embedded) | ✅ (with context) |
| **Images → text (OCR)** | Optional OCR; depends on OCR data/server | ❌ | ✅ |
| **EPUB** | Via conversion only | ✅ | ✅ |
| **Markdown output** | ❌ (text/JSON only) | ✅ (via pymupdf4llm) | ✅ (native, higher quality) |
| **Install size** | Small optional CLI/package | ~25MB | ~3-5GB (PyTorch + models) |
| **Speed** | Fast local PDFium path | Instant | ~1-14s/page (CPU), ~0.2s/page (GPU) |

**Decision**: For local text-based PDFs, try LiteParse first if `lit` is already installed. Use pymupdf when LiteParse is unavailable, when you need PDF edits such as split/merge/search, or when you need markdown. Use marker-pdf for OCR-heavy scans, equations, forms, or complex layout analysis.

If the user needs marker capabilities but the system lacks ~5GB free disk:
> "This document needs OCR/advanced extraction (marker-pdf), which requires ~5GB for PyTorch and models. Your system has [X]GB free. Options: free up space, provide a URL so I can use web_extract, or I can try pymupdf which works for text-based PDFs but not scanned documents or equations."

---

## LiteParse (optional fast text path)

LiteParse is an optional local parser. Do not require it for existing PDF extraction: the helper script falls back to pymupdf for plain text when `lit` is missing. It is read-only; keep using pymupdf/nano-pdf for PDF creation, splitting, merging, search, and edits.

```bash
# Optional install path; do not install unless the user wants this backend.
pip install liteparse
```

**Via helper script**:
```bash
python scripts/extract_liteparse.py --check
python scripts/extract_liteparse.py document.pdf              # Text, no OCR, falls back to pymupdf
python scripts/extract_liteparse.py document.pdf --json       # Structured JSON with boxes/font metadata
python scripts/extract_liteparse.py document.pdf --pages 1-5  # LiteParse uses 1-based page selectors
python scripts/extract_liteparse.py document.pdf --output out.txt
python scripts/extract_liteparse.py document.pdf --screenshots screenshots/
```

**Direct CLI**:
```bash
lit parse document.pdf --format text --no-ocr
lit parse document.pdf --format json -o output.json --no-ocr
lit screenshot document.pdf -o screenshots/
```

Use `--ocr` only when OCR is explicitly needed and the local LiteParse install has usable Tesseract data or an OCR server configured. This skill does not install OCR data.

---

## pymupdf (lightweight)

```bash
pip install pymupdf pymupdf4llm
```

**Via helper script**:
```bash
python scripts/extract_pymupdf.py document.pdf              # Plain text
python scripts/extract_pymupdf.py document.pdf --markdown    # Markdown
python scripts/extract_pymupdf.py document.pdf --tables      # Tables
python scripts/extract_pymupdf.py document.pdf --images out/ # Extract images
python scripts/extract_pymupdf.py document.pdf --metadata    # Title, author, pages
python scripts/extract_pymupdf.py document.pdf --pages 0-4   # Specific pages
```

**Inline**:
```bash
python3 -c "
import pymupdf
doc = pymupdf.open('document.pdf')
for page in doc:
    print(page.get_text())
"
```

---

## marker-pdf (high-quality OCR)

```bash
# Check disk space first
python scripts/extract_marker.py --check

pip install marker-pdf
```

**Via helper script**:
```bash
python scripts/extract_marker.py document.pdf                # Markdown
python scripts/extract_marker.py document.pdf --json         # JSON with metadata
python scripts/extract_marker.py document.pdf --output_dir out/  # Save images
python scripts/extract_marker.py scanned.pdf                 # Scanned PDF (OCR)
python scripts/extract_marker.py document.pdf --use_llm      # LLM-boosted accuracy
```

**CLI** (installed with marker-pdf):
```bash
marker_single document.pdf --output_dir ./output
marker /path/to/folder --workers 4    # Batch
```

---

## Arxiv Papers

```
# Abstract only (fast)
web_extract(urls=["https://arxiv.org/abs/2402.03300"])

# Full paper
web_extract(urls=["https://arxiv.org/pdf/2402.03300"])

# Search
web_search(query="arxiv GRPO reinforcement learning 2026")
```

## Split, Merge & Search

pymupdf handles these natively — use `execute_code` or inline Python:

```python
# Split: extract pages 1-5 to a new PDF
import pymupdf
doc = pymupdf.open("report.pdf")
new = pymupdf.open()
for i in range(5):
    new.insert_pdf(doc, from_page=i, to_page=i)
new.save("pages_1-5.pdf")
```

```python
# Merge multiple PDFs
import pymupdf
result = pymupdf.open()
for path in ["a.pdf", "b.pdf", "c.pdf"]:
    result.insert_pdf(pymupdf.open(path))
result.save("merged.pdf")
```

```python
# Search for text across all pages
import pymupdf
doc = pymupdf.open("report.pdf")
for i, page in enumerate(doc):
    results = page.search_for("revenue")
    if results:
        print(f"Page {i+1}: {len(results)} match(es)")
        print(page.get_text("text"))
```

No extra dependencies needed — pymupdf covers split, merge, search, and text extraction in one package.

---

## Notes

- `web_extract` is always first choice for URLs
- LiteParse is optional and fast for local text-based PDFs; use it only when `lit` is already available or the user asks to install it
- pymupdf is the safe default — instant, no models, works everywhere
- marker-pdf is for OCR, scanned docs, equations, complex layouts — install only when needed
- Helper scripts accept `--help` for full usage
- marker-pdf downloads ~2.5GB of models to `~/.cache/huggingface/` on first use
- For Word docs: `pip install python-docx` (better than OCR — parses actual structure)
- For PowerPoint: see the `powerpoint` skill (uses python-pptx)
