# DeepParser Benchmark

**10 documents · 50 Q&A pairs · DeepParser vs LlamaIndex (v0.12.x)**

Win threshold for moat validation: **≥70% on DWG + Excel-embedded PDF docs**.

---

## Quick start

```bash
# 1. Install deps
pip install -e ".[dev]"
pip install "llama-index-core>=0.12,<0.13" "llama-index-llms-openai>=0.3" "llama-index-embeddings-openai>=0.3"

# 2. Set env vars
export DEEPPARSER_API_KEY=dp_live_...
export DEEPPARSER_BASE_URL=https://your-deepparser.fly.dev
export OPENAI_API_KEY=sk-...

# 3. Add benchmark docs (see "Document checklist" below)
#    Place files in benchmark/docs/ matching the filenames in qa_pairs.json

# 4. Run both systems
python benchmark/runner.py

# 5. Score the answers interactively
python benchmark/score.py

# 6. View report
cat benchmark/results/report.md
```

---

## Document checklist

Place these files in `benchmark/docs/` before running:

| File | Category | Description |
|------|----------|-------------|
| `d01_budget_report.pdf` | Excel PDF | Annual dept budget, exported from Excel |
| `d02_project_tracker.pdf` | Excel PDF | Project status tracker with gantt table |
| `d03_inventory_list.pdf` | Excel PDF | Warehouse inventory with SKUs + prices |
| `d04_financial_statements.pdf` | Excel PDF | P&L + balance sheet, multi-page |
| `d05_scanned_contract.pdf` | Scanned PDF | Scanned paper contract, ≥150 DPI |
| `d06_scanned_invoice.pdf` | Scanned PDF | Scanned invoice with line items |
| `d07_floor_plan.dwg` | DWG | Architectural floor plan with area labels |
| `d08_structural_plan.dwg` | DWG | Structural drawing with beam schedule |
| `d09_mep_drawing.dwg` | DWG | MEP drawing with equipment schedule |
| `d10_bom.pdf` | Excel PDF | Bill of Materials with nested hierarchy |

**Source tips:**
- Excel PDFs: export any existing spreadsheet as PDF (File → Save As → PDF). Keep original Excel format intact — don't re-save from PDF.
- Scanned PDFs: use any scanned paper document. 150–300 DPI is sufficient.
- DWG files: use any AutoCAD-format `.dwg` file. The `工业AO生反池MBR膜池20230407.dwg` test file from the P0 audit works for D07/D08/D09.

---

## Runner options

```bash
# Run only DeepParser (skip LlamaIndex)
python benchmark/runner.py --system deepparser

# Run only one document
python benchmark/runner.py --doc D07

# Resume interrupted run (already-completed pairs are skipped automatically)
python benchmark/runner.py
```

---

## Scoring

```bash
# Interactive scoring (label all unscored pairs)
python benchmark/score.py

# Print report only (no prompts)
python benchmark/score.py --report
```

For each Q&A pair, enter:
- `d` — DeepParser answer is correct or more complete
- `l` — LlamaIndex answer is correct or more complete  
- `t` — Tie (both correct, both wrong, or too close to call)
- `s` — Skip (come back later)
- `q` — Quit and save progress

Progress is saved after every labeled pair. Ctrl+C is safe.

---

## Output files

| File | Description |
|------|-------------|
| `results/deepparser.jsonl` | Raw DeepParser answers (one JSON line per question) |
| `results/llamaindex.jsonl` | Raw LlamaIndex answers |
| `results/scored.json` | Human-labeled scores |
| `results/report.md` | Win-rate table + methodology — paste into README |
| `results/summary.json` | Machine-readable summary `{win_rate, moat_validated, ...}` |

`results/` is gitignored except for a committed snapshot of the final scored results.

---

## Committing results

After the benchmark is complete:

```bash
git add benchmark/results/scored.json benchmark/results/report.md benchmark/results/summary.json
git commit -m "benchmark: run 50-pair DeepParser vs LlamaIndex comparison"
```

The raw `.jsonl` files are gitignored (they contain verbatim LLM outputs which can be large).

---

## LlamaIndex version pinning

The runner uses `llama-index-core` ≥0.12,<0.13 with default settings:
- Embeddings: `text-embedding-ada-002` (OpenAI)
- LLM: GPT-4o (OpenAI default)
- Index: `VectorStoreIndex` with `SimpleNodeParser`
- No custom chunking, no re-ranking

This is a fair baseline: the default configuration a new user would get by following LlamaIndex's quickstart.
